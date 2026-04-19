"""Snapshot of the legacy fragment-stitched FastAPI server module.

This file is for inspection only.
The canonical server now lives in explicit imported modules under src/guppy/api/.
"""

# === BEGIN _server_fragment_bootstrap.py ===
"""
guppy_api.py â€” FastAPI server for remote Guppy access
======================================================

Provides REST API and WebSocket endpoints for browser and mobile access to Guppy.
Includes Turnstile authentication and JWT session management.

Endpoints:
- POST /chat â€” Send text message, get response
- POST /chat/voice â€” Upload audio, get transcription + response
- GET /status â€” Health check + current context
- WebSocket /ws â€” Streaming responses

Security:
- Turnstile validation on write endpoints
- JWT session tokens (24h expiry)
- Rate limiting and request validation
"""

import json
import hashlib
import importlib.util
import logging
import os
import re
import secrets
import sqlite3
import tempfile
import time
import asyncio
import threading
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from functools import partial
from typing import Optional, AsyncGenerator, Any, Dict, List
from pathlib import Path
from collections import Counter

from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from jose import JWTError, jwt
import urllib.request

from src.guppy.paths import CONFIG_DIR, RUNTIME_DIR
from utils.env_bootstrap import load_env_file
try:
    from utils import secret_store as _secret_store
    _SECRET_STORE_AVAILABLE = True
except ImportError:
    _secret_store = None  # type: ignore[assignment]
    _SECRET_STORE_AVAILABLE = False

load_env_file(override=True)

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# Import Guppy core functionality
try:
    import guppy_core as core
    GUPPY_CORE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Guppy core not available: {e}")
    GUPPY_CORE_AVAILABLE = False
    core = None

try:
    import guppy_voice as voice
    GUPPY_VOICE_AVAILABLE = True
except Exception as e:
    print(f"Warning: Guppy voice not available: {e}")
    GUPPY_VOICE_AVAILABLE = False
    voice = None

try:
    import guppy_memory as memory
    GUPPY_MEMORY_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Guppy memory not available: {e}")
    GUPPY_MEMORY_AVAILABLE = False
    memory = None

try:
    from guppy_daemon import get_daemon_manager
    GUPPY_DAEMON_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Guppy daemon not available: {e}")
    GUPPY_DAEMON_AVAILABLE = False
    def get_daemon_manager():
        return None

GUPPY_AVAILABLE = GUPPY_CORE_AVAILABLE and GUPPY_MEMORY_AVAILABLE

# Import authentication
try:
    from src.guppy.api.auth import (
        create_access_token, verify_token, require_turnstile,
        require_rate_limit, require_auth_rate_limit,
        verify_turnstile_token as verify_turnstile_token_auth, validate_environment
    )
except ImportError as e:
    print(f"Warning: Auth module not available: {e}")
    # Fallback functions for development
    def create_access_token(data): return "dev-token"
    def verify_token(): return "dev-user"
    def require_turnstile(): return "dev-token"
    def require_rate_limit(user_id="dev"): return user_id
    def require_auth_rate_limit(): return "dev-auth"
    async def verify_turnstile_token_auth(token): return True
    def validate_environment(): return False

# Configure logging
logging.basicConfig(level=logging.INFO)

try:
    from inference_router import get_router
    INFERENCE_ROUTER_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Inference router not available: {e}")
    INFERENCE_ROUTER_AVAILABLE = False

try:
    from src.guppy.api.response_cache import (
        build_response_cache_key,
        get_cached_response,
        response_cache_enabled,
        set_cached_response,
    )
except Exception:
    def build_response_cache_key(*, message: str, system_prompt: str, mode: str = "auto", instance_name: str | None = None, instance_type: str | None = None) -> str:
        return ""

    def get_cached_response(cache_key: str) -> str | None:
        return None

    def response_cache_enabled() -> bool:
        return False

    def set_cached_response(cache_key: str, response_text: str) -> None:
        return None


logger = logging.getLogger(__name__)

try:
    from utils.session_logger import log_session_event, tail_session_events, rotate_jsonl_file
except Exception:
    def log_session_event(*_args, **_kwargs):
        return
    def tail_session_events(limit: int = 50):
        return []
    def rotate_jsonl_file(*_args, **_kwargs):
        return

try:
    from utils.safe_io import write_json_atomic
    _ATOMIC_JSON_IO = True
except Exception:
    _ATOMIC_JSON_IO = False

    def write_json_atomic(_path, _data):
        return False

try:
    from utils.instance_logger import append_instance_log, delete_instance_log, read_instance_log_summary, read_instance_log_tail
    _INSTANCE_LOGGER_AVAILABLE = True
except Exception:
    _INSTANCE_LOGGER_AVAILABLE = False

    def append_instance_log(*_args, **_kwargs):
        return None

    def delete_instance_log(*_args, **_kwargs):
        return None

    def read_instance_log_tail(*_args, **_kwargs):
        return []

    def read_instance_log_summary(*_args, **_kwargs):
        return {"entry_count": 0, "roles": {}, "statuses": {}, "window_days": 30}

from src.guppy.workspace_governance import (
    auth_mode_label,
    check_instance_tool_permission,
    instance_policy_backend_available,
    resolve_instance_permissions,
    set_instance_tool_permission_policy,
)

_INSTANCE_CAPABILITIES_AVAILABLE = instance_policy_backend_available()

try:
    from utils.connector_manager import (
        connector_inventory,
        run_connector_action,
        save_workspace_connector_binding,
        workspace_connector_inventory,
    )
    _CONNECTOR_MANAGER_AVAILABLE = True
except Exception:
    _CONNECTOR_MANAGER_AVAILABLE = False

    def connector_inventory():
        return []

    def run_connector_action(
        connector_id: str,
        action: str,
        *,
        provider: str = "",
        account_id: str = "",
        secret_key: str = "",
        secret_value: str = "",
    ):
        del connector_id, action, provider, account_id, secret_key, secret_value
        return {"ok": False, "summary": "connector manager unavailable", "status": {}}

    def save_workspace_connector_binding(
        workspace_name: str,
        connector_id: str,
        payload: dict[str, Any],
        *,
        config_path=None,
    ):
        del workspace_name, connector_id, payload, config_path
        return None

    def workspace_connector_inventory(workspace_name: str, *, config_path=None):
        del workspace_name, config_path
        return []

try:
    from utils.personalization_config import (
        build_persona_prompt_overlay,
        ensure_personalization_scaffold,
        load_persona_config_with_diagnostics,
        load_provider_registry_with_diagnostics,
        load_voice_bindings_with_diagnostics,
    )
    _PERSONALIZATION_BOOTSTRAP_AVAILABLE = True
except Exception:
    _PERSONALIZATION_BOOTSTRAP_AVAILABLE = False

    def build_persona_prompt_overlay(*, requested_persona: str = "", model_id: str = "", persona_config: dict[str, Any] | None = None):
        del requested_persona, model_id, persona_config
        return {}, ""

from src.guppy.api._server_fragment_models import (
    ChatRequest,
    ConnectorActionRequest,
    InstanceConfigRequest,
    InstanceConnectorBindingRequest,
    InstanceGovernanceRequest,
    InstanceQueryRequest,
    RepairRequest,
    TokenResponse,
    TurnstileToken,
    VoiceChatRequest,
)

# â”€â”€ Configuration â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

# JWT settings (now imported from auth module)
from src.guppy.api.auth import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, DEV_MODE

# Server settings
HOST = "127.0.0.1"
PORT = int(os.environ.get("GUPPY_API_PORT", "8081"))
CHAT_TIMEOUT_SECONDS = float(os.environ.get("GUPPY_CHAT_TIMEOUT_SECONDS", "120"))
VOICE_TIMEOUT_SECONDS = float(os.environ.get("GUPPY_VOICE_TIMEOUT_SECONDS", "180"))
VOICE_UPLOAD_MAX_BYTES = int(os.environ.get("GUPPY_VOICE_UPLOAD_MAX_BYTES", str(10 * 1024 * 1024)))
VOICE_UPLOAD_CHUNK_BYTES = int(os.environ.get("GUPPY_VOICE_UPLOAD_CHUNK_BYTES", str(1024 * 1024)))
SLOW_REQUEST_MS = int(os.environ.get("GUPPY_SLOW_REQUEST_MS", "1500"))
STATUS_CACHE_TTL_SECONDS = float(os.environ.get("GUPPY_STATUS_CACHE_TTL_SECONDS", "120.0"))
STARTUP_CHECK_TTL_SECONDS = float(os.environ.get("GUPPY_STARTUP_CHECK_TTL_SECONDS", "60.0"))
API_OWNS_DAEMON = os.environ.get("GUPPY_API_OWNS_DAEMON", "0").strip().lower() in {"1", "true", "yes", "on"}
STATUS_INCLUDE_WINDOW_CONTEXT = os.environ.get("GUPPY_STATUS_INCLUDE_WINDOW_CONTEXT", "0").strip().lower() in {"1", "true", "yes", "on"}

_default_origins = [
    "http://localhost:8081",
    "http://127.0.0.1:8081",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
_configured_origins = os.environ.get("GUPPY_ALLOWED_ORIGINS", "").strip()
ALLOWED_ORIGINS = [
    origin.strip() for origin in _configured_origins.split(",") if origin.strip()
] if _configured_origins else _default_origins

_status_cache = {
    "expires_at": 0.0,
    "payload": None,
}

_startup_check_cache = {
    "expires_at": 0.0,
    "payload": None,
}
_startup_check_cache_lock = threading.Lock()
_startup_check_refresh_inflight = False

_runtime_dir = RUNTIME_DIR
_config_dir = CONFIG_DIR
_instances_path = _config_dir / "instances.json"
_connector_bindings_path = _config_dir / "connector_bindings.json"
_instance_state_path = _runtime_dir / "instance_state.json"
_REPAIR_TOKEN_FILE = _runtime_dir / "repair_token.txt"
_REPAIR_TOKEN: str = ""  # set once in lifespan; read by _require_repair_token
_ops_telemetry_db = _runtime_dir / "ops_telemetry.sqlite3"
_SQLITE_TIMEOUT_SECONDS = float(os.environ.get("GUPPY_SQLITE_TIMEOUT_SECONDS", "10.0"))
_SQLITE_BUSY_TIMEOUT_MS = int(os.environ.get("GUPPY_SQLITE_BUSY_TIMEOUT_MS", "5000"))
_stream_jsonl_map = {
    "session_events": _runtime_dir / "session_events.jsonl",
    "router_scorecard": _runtime_dir / "router_scorecard.jsonl",
    "agent_performance": _runtime_dir / "agent_performance.jsonl",
    "integration_events": _runtime_dir / "integration_events.jsonl",
    "reminder_events": _runtime_dir / "reminder_events.jsonl",
}
_INTEGRATION_HEARTBEAT_SECONDS = float(os.environ.get("GUPPY_INTEGRATION_HEARTBEAT_SECONDS", "900"))
_last_integration_heartbeat_ts = 0.0
_integration_heartbeat_lock = threading.Lock()
_instance_query_lock = threading.Lock()

# Detect voice backends once at module load so /status never pays import probe cost
def _detect_voice_backends() -> tuple[str, str, list[str]]:
    tts, stt, details = "sapi", "none", []
    try:
        if importlib.util.find_spec("kokoro") is not None:
            tts = "kokoro"
            details.append("kokoro module found")
        else:
            details.append("kokoro unavailable -> sapi fallback")
    except Exception:
        details.append("kokoro unavailable -> sapi fallback")

    probe_whisper = os.environ.get("GUPPY_API_PROBE_WHISPER", "0").strip().lower() in {"1", "true", "yes", "on"}
    try:
        # Avoid importing native torch/ctranslate stacks at module import-time by default.
        if importlib.util.find_spec("faster_whisper") is not None:
            if probe_whisper:
                from faster_whisper import WhisperModel as _WM  # noqa: F401
                stt = "whisper"
                details.append("faster-whisper import ok")
            else:
                stt = "whisper"
                details.append("faster-whisper module found (lazy import)")
        else:
            raise ImportError("faster_whisper module not found")
    except Exception:
        try:
            if importlib.util.find_spec("speech_recognition") is not None:
                stt = "google"
                details.append("speech_recognition module found")
            else:
                details.append("no transcription backend available")
        except Exception:
            details.append("no transcription backend available")
    return tts, stt, details

_VOICE_TTS_BACKEND, _VOICE_STT_BACKEND, _VOICE_BACKEND_DETAILS = _detect_voice_backends()

_api_metrics_lock = threading.Lock()
_api_metrics = {
    "started_at": datetime.now(timezone.utc).isoformat(),
    "requests_total": 0,
    "errors_total": 0,
    "slow_requests": 0,
    "latency_total_ms": 0.0,
    "path_counts": {},
    "status_counts": {},
}

_CHAT_IDEMPOTENCY_TTL_SECONDS = max(
    60.0,
    float(os.environ.get("GUPPY_CHAT_IDEMPOTENCY_TTL_SECONDS", "300") or "300"),
)
_chat_idempotency_lock = threading.Lock()
_chat_idempotency_records: Dict[str, Dict[str, Any]] = {}


def _prune_chat_idempotency_records(now: float | None = None) -> None:
    cutoff = (time.monotonic() if now is None else now) - _CHAT_IDEMPOTENCY_TTL_SECONDS
    stale_keys = [
        key
        for key, record in _chat_idempotency_records.items()
        if float(record.get("created_at", 0.0) or 0.0) < cutoff
    ]
    for key in stale_keys:
        _chat_idempotency_records.pop(key, None)


def _build_chat_request_fingerprint(request: "ChatRequest") -> str:
    payload = {
        "message": request.message,
        "session_id": request.session_id or "",
        "mode": request.mode or "",
        "persona": request.persona or "",
        "history": request.history or [],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _register_chat_idempotency_key(key: str, fingerprint: str) -> tuple[bool, threading.Event]:
    now = time.monotonic()
    with _chat_idempotency_lock:
        _prune_chat_idempotency_records(now)
        record = _chat_idempotency_records.get(key)
        if isinstance(record, dict):
            return False, record["event"]
        event = threading.Event()
        _chat_idempotency_records[key] = {
            "created_at": now,
            "event": event,
            "fingerprint": fingerprint,
            "response": None,
            "error": None,
            "status": None,
            "headers": None,
        }
        return True, event


def _resolve_chat_idempotency_key(key: str, fingerprint: str) -> Dict[str, Any] | None:
    with _chat_idempotency_lock:
        record = _chat_idempotency_records.get(key)
        if not isinstance(record, dict):
            return None
        if str(record.get("fingerprint", "") or "") != fingerprint:
            return None
        event = record.get("event")
        if not isinstance(event, threading.Event) or not event.is_set():
            return None
        response = record.get("response")
        payload: Dict[str, Any] = {
            "status": int(record.get("status", 500) or 500),
            "headers": dict(record.get("headers", {})) if isinstance(record.get("headers"), dict) else None,
        }
        if isinstance(response, dict):
            payload["response"] = dict(response)
            return payload
        error = record.get("error")
        if error:
            payload["error"] = error
            return payload
        return None


def _takeover_chat_idempotency_key(key: str, fingerprint: str) -> tuple[bool, threading.Event, bool]:
    now = time.monotonic()
    with _chat_idempotency_lock:
        _prune_chat_idempotency_records(now)
        record = _chat_idempotency_records.get(key)
        if isinstance(record, dict):
            event = record.get("event")
            if not isinstance(event, threading.Event):
                event = threading.Event()
            stored_fingerprint = str(record.get("fingerprint", "") or "")
            if stored_fingerprint == fingerprint:
                return False, event, False
            if not event.is_set():
                return False, event, False
            _chat_idempotency_records.pop(key, None)
        event = threading.Event()
        _chat_idempotency_records[key] = {
            "created_at": now,
            "event": event,
            "fingerprint": fingerprint,
            "response": None,
            "error": None,
            "status": None,
            "headers": None,
        }
        return True, event, True


def _complete_chat_idempotency_key(
    key: str,
    *,
    response: Dict[str, Any] | None = None,
    error: Any = None,
    status_code: int = 200,
    headers: Dict[str, str] | None = None,
) -> None:
    with _chat_idempotency_lock:
        record = _chat_idempotency_records.get(key)
        if not isinstance(record, dict):
            return
        record["created_at"] = time.monotonic()
        record["response"] = dict(response) if isinstance(response, dict) else None
        record["error"] = error
        record["status"] = int(status_code or 500)
        record["headers"] = dict(headers) if isinstance(headers, dict) else None
        event = record.get("event")
        if isinstance(event, threading.Event):
            event.set()


def _clear_chat_idempotency_key(key: str) -> None:
    with _chat_idempotency_lock:
        _chat_idempotency_records.pop(key, None)

# â”€â”€ Pydantic Models â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_RICH_PROMPT_DIRECT_CUES = (
    "remember",
    "recall",
    "earlier",
    "previous",
    "follow up",
    "continue",
    "same as",
    "project",
    "task",
    "todo",
    "debug",
    "refactor",
    "design",
    "compare",
    "tradeoff",
    "teach",
    "explain",
    "why",
    "how",
)


def _should_use_rich_chat_prompt_context(request: ChatRequest) -> bool:
    return _should_use_rich_prompt_context(
        message=request.message,
        mode=request.mode,
        history=request.history,
    )


def _should_use_rich_prompt_context(
    *,
    message: str,
    mode: str | None = None,
    history: Any = None,
) -> bool:
    if _sanitize_chat_history(history):
        return True

    normalized_mode = str(mode or "auto").strip().lower()
    if normalized_mode in {"teaching", "code", "vault"}:
        return True

    normalized_message = str(message or "").strip()
    if not normalized_message:
        return False
    if len(normalized_message) >= 80:
        return True

    normalized = re.sub(r"\s+", " ", normalized_message.lower())
    if any(cue in normalized for cue in _RICH_PROMPT_DIRECT_CUES):
        return True
    if "?" in normalized_message and len(normalized.split()) >= 10:
        return True
    return False


def _build_chat_system_prompt(
    *,
    message: str,
    session_id: str | None = None,
    mode: str | None = None,
    persona: str | None = None,
    model_id: str | None = None,
    history: Any = None,
) -> str:
    use_rich_prompt_context = _should_use_rich_prompt_context(
        message=message,
        mode=mode,
        history=history,
    )
    system_prompt = core.get_startup_system(
        session_id=session_id,
        query_context=message,
        include_memory_context=use_rich_prompt_context,
        include_semantic_context=use_rich_prompt_context,
    )
    try:
        _persona_payload, overlay = build_persona_prompt_overlay(
            requested_persona=str(persona or "").strip(),
            model_id=str(model_id or "").strip(),
        )
        if overlay:
            system_prompt += "\n\n" + overlay
    except Exception:
        pass
    return system_prompt


async def _save_voice_upload_tempfile(file: UploadFile) -> str:
    """Stream an uploaded audio file to disk with size and type guardrails."""
    filename = str(getattr(file, "filename", "") or "").strip()
    content_type = str(getattr(file, "content_type", "") or "").strip().lower()
    if not filename:
        raise HTTPException(status_code=400, detail="Audio file is required")
    if content_type and not (content_type.startswith("audio/") or content_type == "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Unsupported audio upload type")

    suffix = Path(filename).suffix or ".wav"
    bytes_written = 0
    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = temp_file.name
            while True:
                chunk = await file.read(VOICE_UPLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > VOICE_UPLOAD_MAX_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Audio upload exceeds {VOICE_UPLOAD_MAX_BYTES} bytes",
                    )
                temp_file.write(chunk)
        if bytes_written <= 0:
            raise HTTPException(status_code=400, detail="Audio file was empty")
        return temp_path
    except HTTPException:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)
        raise
    except Exception:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)
        raise
    finally:
        await file.close()


def _read_jsonl_tail(path: Path, limit: int = 50):
    lim = max(1, min(int(limit), 500))
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    out = []
    for line in lines[-lim:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            out.append({"raw": line, "parse_error": True})
    return out

# === END _server_fragment_bootstrap.py ===

# === BEGIN _server_fragment_instances_telemetry.py ===
def _ensure_m2_instance_scaffold() -> None:
    _config_dir.mkdir(parents=True, exist_ok=True)
    _runtime_dir.mkdir(parents=True, exist_ok=True)

    if not _instances_path.exists():
        _instances_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "active_instance": "guppy-primary",
                    "instances": [
                        {
                            "name": "guppy-primary",
                            "description": "Primary foreground assistant instance",
                            "mode": "auto",
                            "persona": "guppy",
                            "voice": "default",
                            "enabled": True,
                            "type": "user_instance",
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        },
                        {
                            "name": "builder-collab",
                            "description": "Background collaborator instance",
                            "mode": "teaching",
                            "persona": "guppy",
                            "voice": "default",
                            "enabled": False,
                            "type": "builder_instance",
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        },
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    if not _instance_state_path.exists():
        _instance_state_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "active_instance": "guppy-primary",
                    "instances": {
                        "guppy-primary": {
                            "status": "idle",
                            "last_message": "",
                            "last_updated": None,
                            "message_count": 0,
                            "model_currently_using": "auto",
                        },
                        "builder-collab": {
                            "status": "idle",
                            "last_message": "",
                            "last_updated": None,
                            "message_count": 0,
                            "model_currently_using": "teaching",
                        },
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )


def _load_instances_config() -> dict[str, Any]:
    _ensure_m2_instance_scaffold()
    try:
        data = json.loads(_instances_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _load_instance_state(config: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    _ensure_m2_instance_scaffold()
    try:
        data = json.loads(_instance_state_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_instance_state(state: dict[str, Any]) -> None:
    _instance_state_path.parent.mkdir(parents=True, exist_ok=True)
    if _ATOMIC_JSON_IO:
        if not write_json_atomic(_instance_state_path, state):
            raise OSError(f"Failed to write instance state atomically: {_instance_state_path}")
    else:
        _instance_state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _save_instances_config(config: dict[str, Any]) -> None:
    _instances_path.parent.mkdir(parents=True, exist_ok=True)
    if _ATOMIC_JSON_IO:
        if not write_json_atomic(_instances_path, config):
            raise OSError(f"Failed to write instances config atomically: {_instances_path}")
    else:
        _instances_path.write_text(json.dumps(config, indent=2), encoding="utf-8")


def _load_normalized_instance_bundle(*, persist_repairs: bool = False) -> tuple[dict[str, Any], dict[str, Any], list[str], list[str]]:
    raw_config = _load_instances_config()
    config, config_warnings = _normalize_instances_config(raw_config)
    if persist_repairs and raw_config != config:
        _save_instances_config(config)
        config_warnings = list(config_warnings) + ["persisted normalized instances config"]

    raw_state = _load_instance_state(config)
    state, state_warnings = _normalize_instance_state(
        raw_state,
        valid_names=_instance_names(config),
        active_instance=str(config.get("active_instance", "guppy-primary")),
    )
    if persist_repairs and raw_state != state:
        _save_instance_state(state)
        state_warnings = list(state_warnings) + ["persisted normalized instance runtime state"]

    return config, state, config_warnings, state_warnings


def _instance_config_entry(
    *,
    name: str,
    description: str = "",
    mode: str = "auto",
    persona: str = "guppy",
    voice: str = "default",
    enabled: bool = True,
    instance_type: str = "user_instance",
    created_at: str | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "mode": mode,
        "persona": persona,
        "voice": voice,
        "enabled": enabled,
        "type": instance_type,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
    }


def _default_instance_state(mode: str = "auto") -> dict[str, Any]:
    return {
        "status": "idle",
        "last_message": "",
        "last_updated": None,
        "message_count": 0,
        "model_currently_using": mode,
    }


def _instance_names(config: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for item in config.get("instances", []):
        if isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            if name:
                names.append(name)
    return names


def _get_instance_entry(config: dict[str, Any], name: str) -> dict[str, Any] | None:
    target = str(name or "").strip()
    for item in config.get("instances", []):
        if isinstance(item, dict) and str(item.get("name", "")).strip() == target:
            return item
    return None


def _get_active_instance_context() -> tuple[str | None, str | None, str | None, str | None]:
    config, _state, _warnings, _state_warnings = _load_normalized_instance_bundle(persist_repairs=True)
    active_name = str(config.get("active_instance", "")).strip()
    entry = _get_instance_entry(config, active_name)
    instance_type = str((entry or {}).get("type", "user_instance") or "user_instance").strip() or "user_instance"
    persona = str((entry or {}).get("persona", "guppy") or "guppy").strip() or "guppy"
    voice = str((entry or {}).get("voice", "default") or "default").strip() or "default"
    return (active_name or None, instance_type, persona, voice)


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _normalize_instances_config(raw: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    version = max(1, _coerce_int(raw.get("version", 1), 1))
    raw_instances = raw.get("instances")
    if not isinstance(raw_instances, list):
        warnings.append("instances must be a list; using default instance set")
        raw_instances = []

    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    for idx, entry in enumerate(raw_instances):
        if not isinstance(entry, dict):
            warnings.append(f"instances[{idx}] ignored: expected object")
            continue
        name = str(entry.get("name", "")).strip()
        if not name:
            warnings.append(f"instances[{idx}] ignored: missing name")
            continue
        if name in seen:
            warnings.append(f"instances[{idx}] ignored: duplicate name '{name}'")
            continue
        seen.add(name)
        items.append(
            _instance_config_entry(
                name=name,
                description=str(entry.get("description", "")).strip(),
                mode=str(entry.get("mode", "auto") or "auto").strip().lower() or "auto",
                persona=str(entry.get("persona", "guppy") or "guppy").strip() or "guppy",
                voice=str(entry.get("voice", "default") or "default").strip() or "default",
                enabled=bool(entry.get("enabled", True)),
                instance_type=str(entry.get("type", "user_instance") or "user_instance").strip() or "user_instance",
                created_at=str(entry.get("created_at", "")).strip() or None,
            )
        )

    if not items:
        warnings.append("no valid instance entries found; restored default primary instance")
        items = [
            _instance_config_entry(
                name="guppy-primary",
                description="Primary foreground assistant instance",
                mode="auto",
                persona="guppy",
                voice="default",
                enabled=True,
                instance_type="user_instance",
            )
        ]

    configured_active = str(raw.get("active_instance", "")).strip()
    valid_names = [item["name"] for item in items]
    active_instance = configured_active if configured_active in valid_names else valid_names[0]
    if configured_active and configured_active not in valid_names:
        warnings.append(f"active_instance '{configured_active}' not found; using '{active_instance}'")
    elif not configured_active:
        warnings.append(f"active_instance missing; using '{active_instance}'")

    return {
        "version": version,
        "active_instance": active_instance,
        "instances": items,
    }, warnings


def _normalize_instance_state(
    raw: dict[str, Any],
    *,
    valid_names: list[str],
    active_instance: str,
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    raw_instances = raw.get("instances")
    if not isinstance(raw_instances, dict):
        warnings.append("state.instances must be an object; rebuilding instance runtime state")
        raw_instances = {}

    normalized_instances: dict[str, dict[str, Any]] = {}
    for key in raw_instances.keys():
        if key not in valid_names:
            warnings.append(f"state instance '{key}' ignored: not present in config")

    allowed_status = {"idle", "busy", "error", "starting", "active", "running"}
    for name in valid_names:
        entry = raw_instances.get(name, {})
        if not isinstance(entry, dict):
            warnings.append(f"state for '{name}' invalid; resetting to defaults")
            entry = {}

        status = str(entry.get("status", "idle") or "idle").strip().lower()
        if status not in allowed_status:
            warnings.append(f"state for '{name}' had invalid status '{status}'; using 'idle'")
            status = "idle"

        message_count = max(0, _coerce_int(entry.get("message_count", 0), 0))
        normalized_instances[name] = {
            "status": status,
            "last_message": str(entry.get("last_message", "") or ""),
            "last_updated": entry.get("last_updated"),
            "message_count": message_count,
            "model_currently_using": str(entry.get("model_currently_using", "") or ""),
        }

    active = active_instance if active_instance in valid_names else (valid_names[0] if valid_names else "guppy-primary")
    active_slots = 0
    for name, item in normalized_instances.items():
        if name == active:
            item["status"] = "active"
            active_slots += 1
            continue
        if item.get("status") in {"active", "running", "busy"}:
            if active_slots < 2:
                if item.get("status") == "active":
                    item["status"] = "running"
                active_slots += 1
            else:
                item["status"] = "idle"
    return {
        "version": 1,
        "active_instance": active,
        "instances": normalized_instances,
    }, warnings


def _upsert_instance_config(
    config: dict[str, Any],
    payload: InstanceConfigRequest,
) -> tuple[dict[str, Any], str]:
    items = list(config.get("instances", [])) if isinstance(config.get("instances"), list) else []
    target = (payload.name or "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="instance name is required")

    existing_idx = -1
    existing_created_at = None
    for idx, item in enumerate(items):
        if isinstance(item, dict) and str(item.get("name", "")).strip() == target:
            existing_idx = idx
            existing_created_at = str(item.get("created_at", "")).strip() or None
            break

    if existing_idx < 0 and len(items) >= 5:
        raise HTTPException(status_code=409, detail="instance limit reached (max 5 configured)")

    entry = _instance_config_entry(
        name=target,
        description=(payload.description or "").strip(),
        mode=(payload.mode or "auto").strip().lower() or "auto",
        persona=(payload.persona or "guppy").strip() or "guppy",
        voice=(payload.voice or "default").strip() or "default",
        enabled=bool(payload.enabled),
        instance_type=(payload.type or "user_instance").strip() or "user_instance",
        created_at=existing_created_at,
    )
    action = "updated" if existing_idx >= 0 else "created"
    if existing_idx >= 0:
        items[existing_idx] = entry
    else:
        items.append(entry)
    config["instances"] = items
    if str(config.get("active_instance", "")).strip() not in _instance_names(config):
        config["active_instance"] = target
    return config, action


def _activate_instance_state(state: dict[str, Any], target: str) -> dict[str, Any]:
    instances = state.get("instances", {}) if isinstance(state.get("instances"), dict) else {}
    current_active = str(state.get("active_instance", "")).strip()
    if current_active and current_active in instances and current_active != target:
        previous = instances.get(current_active)
        if isinstance(previous, dict) and previous.get("status") != "busy":
            previous["status"] = "idle"
    target_entry = instances.get(target)
    if isinstance(target_entry, dict):
        target_entry["status"] = "active"
        target_entry["last_updated"] = datetime.now(timezone.utc).isoformat()
    state["active_instance"] = target
    return state


def _instance_limits_payload(config: dict[str, Any], state: dict[str, Any]) -> dict[str, int]:
    config_items = config.get("instances", []) if isinstance(config.get("instances"), list) else []
    configured = len([item for item in config_items if isinstance(item, dict) and str(item.get("name", "")).strip()])
    runtime_items = state.get("instances", {}) if isinstance(state.get("instances"), dict) else {}
    active_runtime = 0
    for item in runtime_items.values():
        if not isinstance(item, dict):
            continue
        status = str(item.get("status", "idle") or "idle").strip().lower()
        if status in {"active", "running", "busy"}:
            active_runtime += 1
    return {
        "configured": configured,
        "max_configured": 5,
        "active_runtime": active_runtime,
        "max_active_runtime": 2,
    }


def _emit_integration_heartbeat(reason: str) -> None:
    global _last_integration_heartbeat_ts
    now = time.time()
    with _integration_heartbeat_lock:
        if now - _last_integration_heartbeat_ts < max(60.0, _INTEGRATION_HEARTBEAT_SECONDS):
            return
        _last_integration_heartbeat_ts = now

    path = _stream_jsonl_map["integration_events"]
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ts": datetime.now(timezone.utc).isoformat(),
        "event_type": "integration_heartbeat",
        "event": "integration_heartbeat",
        "level": "info",
        "payload": {
            "state": "idle",
            "reason": reason,
        },
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        rotate_jsonl_file(path)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=True) + "\n")
    except Exception:
        return


def _read_resource_envelope_status() -> dict[str, Any]:
    path = _runtime_dir / "resource_envelope.status.json"
    if not path.exists():
        return {
            "state": "unknown",
            "message": "resource envelope status not available",
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {
        "state": "unknown",
        "message": "resource envelope status unreadable",
    }


def _parse_iso_ts(ts_value: Any) -> datetime | None:
    if not ts_value:
        return None
    try:
        txt = str(ts_value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(txt)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    vals = sorted(float(v) for v in values)
    idx = max(0, int(len(vals) * 0.95) - 1)
    return vals[idx]


def _query_sqlite_telemetry(
    stream: str | None,
    event: str | None,
    level: str | None,
    since_minutes: int | None,
    limit: int,
) -> list[dict[str, Any]]:
    if not _ops_telemetry_db.exists():
        return []

    where = []
    params: list[Any] = []
    if stream:
        where.append("stream = ?")
        params.append(stream)
    if event:
        where.append("event = ?")
        params.append(event)
    if level:
        where.append("level = ?")
        params.append(level)
    if since_minutes is not None and since_minutes >= 0:
        cutoff = datetime.now(timezone.utc).timestamp() - (int(since_minutes) * 60)
        where.append("strftime('%s', ts) >= ?")
        params.append(cutoff)

    query = "SELECT ts, stream, event, level, payload_json FROM operational_events"
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    out: list[dict[str, Any]] = []
    try:
        from utils.db_utils import open_db as _open_db
        conn = _open_db(
            _ops_telemetry_db,
            timeout=_SQLITE_TIMEOUT_SECONDS,
            busy_timeout_ms=_SQLITE_BUSY_TIMEOUT_MS,
        )
        try:
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()
    except Exception:
        return []

    for ts, stream_name, event_name, lvl, payload_json in reversed(rows):
        payload: dict[str, Any] | Any
        try:
            payload = json.loads(payload_json)
        except Exception:
            payload = {"raw": str(payload_json), "parse_error": True}
        out.append({
            "ts": ts,
            "stream": stream_name,
            "event": event_name,
            "level": lvl,
            "payload": payload,
        })
    return out


def _query_jsonl_telemetry(
    stream: str | None,
    event: str | None,
    level: str | None,
    since_minutes: int | None,
    limit: int,
) -> list[dict[str, Any]]:
    requested_streams = [stream] if stream else list(_stream_jsonl_map.keys())
    cutoff = None
    if since_minutes is not None and since_minutes >= 0:
        cutoff = datetime.now(timezone.utc).timestamp() - (int(since_minutes) * 60)

    events: list[dict[str, Any]] = []
    for stream_name in requested_streams:
        path = _stream_jsonl_map.get(stream_name)
        if path is None:
            continue
        for row in _read_jsonl_tail(path, limit=max(limit * 3, 120)):
            evt_name = str(row.get("event", row.get("event_type", ""))).strip()
            evt_level = str(row.get("level", "")).strip().lower() or "info"
            ts_txt = row.get("ts", row.get("timestamp"))
            ts_obj = _parse_iso_ts(ts_txt)
            if cutoff is not None:
                if ts_obj is None or ts_obj.timestamp() < cutoff:
                    continue
            if event and evt_name != event:
                continue
            if level and evt_level != level:
                continue
            events.append({
                "ts": ts_txt,
                "stream": stream_name,
                "event": evt_name or "event",
                "level": evt_level,
                "payload": row,
            })

    events.sort(key=lambda item: _parse_iso_ts(item.get("ts")) or datetime.min.replace(tzinfo=timezone.utc))
    if len(events) > limit:
        events = events[-limit:]
    return events


def _build_telemetry_report(events: list[dict[str, Any]]) -> dict[str, Any]:
    stream_counts = Counter()
    event_counts = Counter()
    level_counts = Counter()
    latencies: list[float] = []
    slow_count = 0

    for item in events:
        stream_counts[str(item.get("stream", "unknown"))] += 1
        event_counts[str(item.get("event", "event"))] += 1
        level_counts[str(item.get("level", "info"))] += 1

        payload = item.get("payload")
        if isinstance(payload, dict):
            raw_latency = payload.get("latency_ms", payload.get("elapsed_ms"))
            if isinstance(raw_latency, (int, float)):
                lat = float(raw_latency)
                latencies.append(lat)
                if lat >= SLOW_REQUEST_MS:
                    slow_count += 1

    latest_ts = None
    if events:
        latest_ts = events[-1].get("ts")

    return {
        "count": len(events),
        "latest_ts": latest_ts,
        "streams": dict(stream_counts),
        "events": dict(event_counts.most_common(20)),
        "levels": dict(level_counts),
        "latency": {
            "samples": len(latencies),
            "avg_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
            "p95_ms": round(_p95(latencies), 2) if latencies else 0.0,
            "slow_count": slow_count,
            "slow_threshold_ms": SLOW_REQUEST_MS,
        },
    }

# === END _server_fragment_instances_telemetry.py ===

# === BEGIN _server_fragment_ops.py ===
def _latest_stress_report_path() -> Path | None:
    reports = sorted(_runtime_dir.glob("stress_report_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return reports[0] if reports else None


_MORNING_BRIEF_DIRECT_PHRASES = (
    "morning brief",
    "morning briefing",
    "daily brief",
    "daily briefing",
)
_MORNING_BRIEF_AFFIRMATIONS = (
    "yes",
    "yes please",
    "yeah",
    "yep",
    "sure",
    "ok",
    "okay",
    "please",
    "do it",
    "go ahead",
    "lets",
    "let's",
    "sounds good",
)


def _normalize_brief_text(text: Any) -> str:
    raw = str(text or "").strip().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9']+", " ", raw)).strip()


def _looks_like_brief_affirmation(text: Any) -> bool:
    compact = _normalize_brief_text(text)
    if not compact:
        return False
    if compact in _MORNING_BRIEF_AFFIRMATIONS:
        return True
    return any(compact.startswith(f"{phrase} ") for phrase in _MORNING_BRIEF_AFFIRMATIONS)


def _history_offered_morning_brief(history: Any) -> bool:
    if not isinstance(history, list):
        return False
    for item in reversed(history[-6:]):
        if not isinstance(item, dict):
            continue
        if str(item.get("role", "")).strip().lower() != "assistant":
            continue
        content = _normalize_brief_text(item.get("content", ""))
        if "morning brief" not in content:
            continue
        if any(phrase in content for phrase in ("shall i", "i can", "prepare", "proceed", "give you")):
            return True
    return False


def _request_is_morning_brief(request: ChatRequest) -> bool:
    message = _normalize_brief_text(request.message)
    if any(phrase in message for phrase in _MORNING_BRIEF_DIRECT_PHRASES):
        return True
    return _looks_like_brief_affirmation(message) and _history_offered_morning_brief(request.history)


def _latest_daily_report_path() -> Path | None:
    reports_dir = _runtime_dir / "daily_reports"
    if not reports_dir.exists():
        return None
    today_name = f"{datetime.now().strftime('%Y-%m-%d')}.md"
    today_path = reports_dir / today_name
    if today_path.exists():
        return today_path
    reports = sorted(reports_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return reports[0] if reports else None


def _strip_markdown_prefix(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^\s*(?:[-*]|\d+\.)\s*", "", cleaned)
    cleaned = cleaned.replace("**", "").replace("`", "")
    return cleaned.strip()


def _parse_markdown_sections(markdown_text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = ""
    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("## "):
            current = line[3:].strip().lower()
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(line)
    return sections


def _preview_markdown_section(lines: list[str], limit: int = 3) -> list[str]:
    preview: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("|"):
            if line.startswith("|-"):
                continue
            cols = [part.strip() for part in line.strip("|").split("|")]
            if len(cols) >= 2 and cols[0].lower() != "topic":
                preview.append(_strip_markdown_prefix(f"{cols[0]}: {cols[1]}"))
            continue
        preview.append(_strip_markdown_prefix(line))
        if len(preview) >= limit:
            break
    return preview[:limit]


def _preview_plain_block(text: str, limit: int = 3) -> list[str]:
    lines = [_strip_markdown_prefix(line) for line in str(text or "").splitlines() if str(line).strip()]
    return [line for line in lines if line][:limit]


def _build_morning_brief_response() -> str:
    now_local = datetime.now().astimezone()
    lines = [f"Morning brief for {now_local.strftime('%A, %B %d, %Y')}."]

    report_path = _latest_daily_report_path()
    report_sections: dict[str, list[str]] = {}
    if report_path is not None:
        try:
            report_sections = _parse_markdown_sections(report_path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            report_sections = {}

    key_actions = _preview_markdown_section(report_sections.get("key actions", []), limit=3)
    carry_forward = _preview_markdown_section(report_sections.get("carry-forward items", []), limit=3)
    world_news = _preview_markdown_section(report_sections.get("world news", []), limit=3)

    if key_actions:
        lines.append("")
        lines.append("Top priorities:")
        lines.extend(f"- {item}" for item in key_actions)

    pending_tasks = ""
    if GUPPY_MEMORY_AVAILABLE and hasattr(memory, "get_tasks"):
        try:
            pending_tasks = str(memory.get_tasks("pending") or "").strip()
        except Exception:
            pending_tasks = ""
    task_preview = []
    if pending_tasks and not pending_tasks.lower().startswith("no pending tasks"):
        task_preview = _preview_plain_block(pending_tasks, limit=3)
    if task_preview:
        lines.append("")
        lines.append("Pending tasks:")
        lines.extend(f"- {item}" for item in task_preview)

    if world_news:
        lines.append("")
        lines.append("World watch:")
        lines.extend(f"- {item}" for item in world_news)

    if carry_forward:
        lines.append("")
        lines.append("Carry-forward:")
        lines.extend(f"- {item}" for item in carry_forward)

    resource = _read_resource_envelope_status()
    startup = _startup_readiness_cached_or_unknown()
    resource_state = str(resource.get("state", "unknown")).strip().lower() or "unknown"
    resource_message = str(resource.get("message", "resource envelope status unavailable")).strip()
    startup_state = str(startup.get("overall", "UNKNOWN")).strip().lower() or "unknown"
    lines.append("")
    lines.append(f"System status: resource envelope {resource_state}; startup readiness {startup_state}.")
    if resource_message:
        lines.append(f"Runtime note: {resource_message.rstrip('.')}.")

    if report_path is not None:
        report_label = f"today's report" if report_path.name == f"{now_local.strftime('%Y-%m-%d')}.md" else "latest report"
        lines.append(f"Full details are in {report_label}: runtime/daily_reports/{report_path.name}.")
    elif len(lines) == 3:
        lines.append("No saved daily report is available yet, so this brief is using live runtime context only.")

    return "\n".join(lines)


def _collect_runtime_bundle() -> dict[str, Any]:
    status_files = [
        _runtime_dir / "guppy.status",
        _runtime_dir / "resource_envelope.status.json",
    ]
    out: dict[str, Any] = {
        "runtime_dir": str(_runtime_dir),
        "files": {},
    }
    latest_report = _latest_stress_report_path()
    if latest_report and latest_report.exists():
        out["latest_stress_report"] = str(latest_report)
        try:
            out["files"][latest_report.name] = json.loads(latest_report.read_text(encoding="utf-8"))
        except Exception:
            out["files"][latest_report.name] = {"error": "unreadable"}
    else:
        out["latest_stress_report"] = None

    for path in status_files:
        if not path.exists():
            out["files"][path.name] = {"missing": True}
            continue
        try:
            out["files"][path.name] = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            out["files"][path.name] = {"error": "unreadable"}
    return out


def _do_repair_action(action: str, dry_run: bool) -> dict[str, Any]:
    act = (action or "").strip().lower()
    if act == "warmup":
        if dry_run:
            return {"ok": True, "summary": "dry-run warmup: would refresh startup readiness and clear status cache"}
        _startup_readiness_snapshot()
        _status_cache["expires_at"] = 0.0
        _status_cache["payload"] = None
        return {"ok": True, "summary": "startup readiness refreshed; status cache invalidated"}

    if act == "restart_daemon":
        if not GUPPY_DAEMON_AVAILABLE:
            return {"ok": False, "summary": "daemon module unavailable"}
        daemon = get_daemon_manager()
        if daemon is None:
            return {"ok": False, "summary": "daemon manager unavailable"}
        if dry_run:
            return {"ok": True, "summary": "dry-run restart: would stop then start daemon manager"}
        if hasattr(daemon, "stop"):
            daemon.stop()
        if hasattr(daemon, "start"):
            daemon.start()
        return {"ok": True, "summary": "daemon manager restarted"}

    if act == "audit_runtime":
        bundle = _collect_runtime_bundle()
        if dry_run:
            return {
                "ok": True,
                "summary": "dry-run diagnostics: would collect latest stress report and runtime status files",
                "bundle_preview": {
                    "latest_stress_report": bundle.get("latest_stress_report"),
                    "file_count": len((bundle.get("files") or {}).keys()),
                },
            }
        out = _runtime_dir / f"diagnostics_bundle_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        out.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
        return {"ok": True, "summary": f"diagnostics bundle written: {out.name}", "bundle_path": str(out)}

    raise HTTPException(status_code=400, detail="unsupported action (expected: warmup|restart_daemon|audit_runtime)")


def _secret_ready(value: str) -> bool:
    val = (value or "").strip()
    if not val:
        return False
    placeholder_tokens = {
        "change-me",
        "dev-only-change-me",
        "replace-me",
        "your_",
        "your-",
        "example",
        "placeholder",
    }
    low = val.lower()
    return not any(tok in low for tok in placeholder_tokens)


def _build_startup_readiness_payload() -> dict:
    jwt_ready = _secret_ready(os.environ.get("GUPPY_JWT_SECRET", ""))
    turnstile_ready = _secret_ready(os.environ.get("TURNSTILE_SECRET", ""))
    local_runtime = _build_local_runtime_status()
    local_runtime_ready_for_chat = bool(local_runtime.get("chat_ready", False))

    auth_state = "READY" if (DEV_MODE or (jwt_ready and turnstile_ready)) else "MISSING"
    if DEV_MODE:
        auth_detail = "development mode enabled; strict auth checks bypassed"
    elif auth_state == "READY":
        auth_detail = "strict auth secrets configured"
    else:
        auth_detail = "missing one or more strict auth secrets"

    ollama_state = "MISSING"
    ollama_detail = "Guppy core unavailable"
    ollama_model = (os.environ.get("OLLAMA_MODEL", "guppy") or "guppy").strip()
    if GUPPY_CORE_AVAILABLE:
        try:
            ok, err = core.check_ollama(ollama_model)
            ollama_state = "READY" if ok else "MISSING"
            ollama_detail = "model reachable" if ok else err
        except Exception as e:
            ollama_state = "MISSING"
            ollama_detail = str(e)

    voice_state = "MISSING"
    voice_detail = "voice module unavailable"
    voice_status = {
        "tts_backend": "unknown",
        "stt_backend": "unknown",
        "wake_backend": "idle",
    }
    if GUPPY_VOICE_AVAILABLE:
        # Keep startup check fast: avoid heavyweight backend imports/initialization here.
        voice_state = "PARTIAL"
        voice_detail = "voice module available (detailed backend status in /status)"

    daemon_state = "READY" if GUPPY_DAEMON_AVAILABLE else "MISSING"
    daemon_detail = "daemon module available" if GUPPY_DAEMON_AVAILABLE else "daemon module unavailable"

    memory_state = "READY" if GUPPY_MEMORY_AVAILABLE else "MISSING"
    memory_detail = "memory module available" if GUPPY_MEMORY_AVAILABLE else "memory module unavailable"

    local_runtime_state = str(local_runtime.get("state", "UNKNOWN") or "UNKNOWN")
    if local_runtime_state == "READY" and not local_runtime_ready_for_chat:
        local_runtime_state = "PARTIAL"
        detail = str(local_runtime.get("detail", "") or "local runtime reachable")
        chat_detail = str(local_runtime.get("chat_detail", "") or "chat lane warming")
        local_runtime = {
            **local_runtime,
            "state": local_runtime_state,
            "detail": f"{detail} | {chat_detail}",
        }
    states = [auth_state, ollama_state, voice_state, daemon_state, memory_state, local_runtime_state]
    overall = "READY" if all(s == "READY" for s in states) else ("PARTIAL" if any(s in {"READY", "PARTIAL"} for s in states) else "MISSING")

    return {
        "overall": overall,
        "checks": {
            "auth": {"state": auth_state, "detail": auth_detail, "dev_mode": bool(DEV_MODE), "jwt_ready": jwt_ready, "turnstile_ready": turnstile_ready},
            "ollama": {"state": ollama_state, "detail": ollama_detail, "model": ollama_model},
            "local_runtime": local_runtime,
            "voice": {"state": voice_state, "detail": voice_detail, **voice_status},
            "daemon": {"state": daemon_state, "detail": daemon_detail},
            "memory": {"state": memory_state, "detail": memory_detail},
        },
    }


def _startup_readiness_snapshot() -> dict:
    with _startup_check_cache_lock:
        now = time.time()
        if _startup_check_cache["payload"] is not None and _startup_check_cache["expires_at"] > now:
            return _startup_check_cache["payload"]

    payload = _build_startup_readiness_payload()

    now = time.time()
    with _startup_check_cache_lock:
        _startup_check_cache["payload"] = payload
        _startup_check_cache["expires_at"] = now + STARTUP_CHECK_TTL_SECONDS
        return payload


def _startup_readiness_cached_or_unknown() -> dict:
    with _startup_check_cache_lock:
        payload = _startup_check_cache.get("payload")
        if payload is not None:
            return payload
    return {
        "overall": "UNKNOWN",
        "checks": {
            "auth": {"state": "UNKNOWN", "detail": "startup checks not run yet"},
            "ollama": {"state": "UNKNOWN", "detail": "startup checks not run yet", "model": (os.environ.get("OLLAMA_MODEL", "guppy") or "guppy").strip()},
            "local_runtime": {
                "state": "UNKNOWN",
                "detail": "startup checks not run yet",
                "backend": _selected_local_runtime_backend(),
                "chat_ready": False,
                "chat_state": "UNKNOWN",
                "chat_detail": "local runtime warmup not checked yet",
                "chat_model": _current_local_runtime_chat_model(_selected_local_runtime_backend()),
            },
            "voice": {"state": "UNKNOWN", "detail": "startup checks not run yet", "tts_backend": "unknown", "stt_backend": "unknown", "wake_backend": "unknown"},
            "daemon": {"state": "UNKNOWN", "detail": "startup checks not run yet"},
            "memory": {"state": "UNKNOWN", "detail": "startup checks not run yet"},
        },
    }


def _startup_readiness_cached_or_snapshot() -> dict:
    """Return cached startup readiness immediately when available, else compute once."""
    with _startup_check_cache_lock:
        payload = _startup_check_cache.get("payload")
        if payload is not None:
            return payload
    return _startup_readiness_snapshot()


def _startup_readiness_cache_expired() -> bool:
    with _startup_check_cache_lock:
        return _startup_check_cache.get("expires_at", 0.0) <= time.time()


def _trigger_startup_readiness_refresh() -> None:
    """Refresh startup readiness in the background without blocking request handlers."""
    global _startup_check_refresh_inflight
    with _startup_check_cache_lock:
        if _startup_check_refresh_inflight:
            return
        _startup_check_refresh_inflight = True

    def _worker() -> None:
        global _startup_check_refresh_inflight
        try:
            _startup_readiness_snapshot()
        except Exception:
            pass
        finally:
            with _startup_check_cache_lock:
                _startup_check_refresh_inflight = False

    threading.Thread(target=_worker, daemon=True).start()

# â”€â”€ Authentication â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

# Remove duplicate JWT functions - now imported from auth module

# â”€â”€ FastAPI App â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Validate env and optionally manage daemon lifecycle when explicitly enabled."""
    validate_environment()
    _ensure_m2_instance_scaffold()

    # Generate a per-process repair token so only trusted local callers can POST /repair
    global _REPAIR_TOKEN
    _runtime_dir.mkdir(parents=True, exist_ok=True)
    _REPAIR_TOKEN = secrets.token_hex(32)
    # Prefer OS credential store; file write is the fallback for systems
    # where keyring is unavailable (e.g. headless containers).
    if _SECRET_STORE_AVAILABLE and _secret_store.set_secret("repair_token", _REPAIR_TOKEN):
        logger.info("Repair token stored in OS credential store")
        # Ensure stale fallback files cannot carry an old token across restarts.
        try:
            if _REPAIR_TOKEN_FILE.exists():
                _REPAIR_TOKEN_FILE.unlink()
        except Exception as e:
            logger.warning("Could not remove stale repair token fallback file: %s", e)
    else:
        try:
            _REPAIR_TOKEN_FILE.write_text(_REPAIR_TOKEN, encoding="utf-8")
            try:
                os.chmod(_REPAIR_TOKEN_FILE, 0o600)
            except Exception:
                pass
            logger.info("Repair token written to %s", _REPAIR_TOKEN_FILE)
        except Exception as e:
            logger.warning("Could not write repair token: %s", e)

    if _PERSONALIZATION_BOOTSTRAP_AVAILABLE:
        try:
            created = await asyncio.to_thread(ensure_personalization_scaffold)
            personalization_diagnostics = {
                "persona_config.json": (await asyncio.to_thread(load_persona_config_with_diagnostics))[1],
                "provider_registry.json": (await asyncio.to_thread(load_provider_registry_with_diagnostics))[1],
                "voice_bindings.json": (await asyncio.to_thread(load_voice_bindings_with_diagnostics))[1],
            }
            if created:
                logger.info("Personalization scaffold initialized: %s", ",".join(sorted(created.keys())))
            problems = [
                f"{name}: {messages[0]}"
                for name, messages in personalization_diagnostics.items()
                if messages
            ]
            if problems:
                logger.warning("Personalization scaffold normalized malformed config: %s", " | ".join(problems))
        except Exception as e:
            logger.warning("Personalization scaffold initialization failed: %s", e)

    # Pre-warm readiness cache so first user-facing status calls are not blocked by Ollama probe latency.
    try:
        await asyncio.to_thread(_startup_readiness_snapshot)
    except Exception as e:
        logger.warning("Startup readiness warmup failed: %s", e)

    try:
        _trigger_local_runtime_warm_refresh(force=True)
    except Exception as e:
        logger.warning("Local runtime warmup trigger failed: %s", e)

    _emit_integration_heartbeat("api_startup")

    if API_OWNS_DAEMON and GUPPY_DAEMON_AVAILABLE:
        try:
            daemon = get_daemon_manager()
            if hasattr(daemon, "is_running") and daemon.is_running:
                logger.info("Guppy daemon already running - using existing instance")
            else:
                daemon.start()
                logger.info("Guppy daemon started")
        except Exception as e:
            logger.error("Failed to initialize daemon: %s", e)
            logger.warning("API will run in limited mode without daemon context")
    elif GUPPY_DAEMON_AVAILABLE:
        logger.info("API running in supervised mode (daemon ownership disabled)")
    else:
        logger.warning("Guppy daemon not available - running in API-only mode")

    try:
        yield
    finally:
        try:
            if _SECRET_STORE_AVAILABLE:
                _secret_store.delete_secret("repair_token")
            if _REPAIR_TOKEN_FILE.exists():
                _REPAIR_TOKEN_FILE.unlink()
        except Exception as e:
            logger.warning("Failed to remove repair token: %s", e)
        if API_OWNS_DAEMON and GUPPY_AVAILABLE:
            try:
                daemon = get_daemon_manager()
                daemon.stop()
                logger.info("Guppy daemon stopped")
            except Exception as e:
                logger.error("Failed to stop daemon: %s", e)


app = FastAPI(
    title="Guppy API",
    description="Remote access API for Guppy AI assistant",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for web access
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Repair-Token", "X-Turnstile-Token"],
)


@app.middleware("http")
async def request_timing_middleware(request: Request, call_next):
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        log_session_event(
            "api",
            "request_failed",
            level="error",
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            elapsed_ms=round(elapsed_ms, 2),
        )
        with _api_metrics_lock:
            _api_metrics["requests_total"] += 1
            _api_metrics["errors_total"] += 1
            _api_metrics["latency_total_ms"] += elapsed_ms
            _api_metrics["path_counts"][request.url.path] = _api_metrics["path_counts"].get(request.url.path, 0) + 1
            _api_metrics["status_counts"][str(status_code)] = _api_metrics["status_counts"].get(str(status_code), 0) + 1
            if elapsed_ms >= SLOW_REQUEST_MS:
                _api_metrics["slow_requests"] += 1
        raise

    elapsed_ms = (time.perf_counter() - started) * 1000.0
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"

    with _api_metrics_lock:
        _api_metrics["requests_total"] += 1
        _api_metrics["latency_total_ms"] += elapsed_ms
        _api_metrics["path_counts"][request.url.path] = _api_metrics["path_counts"].get(request.url.path, 0) + 1
        _api_metrics["status_counts"][str(status_code)] = _api_metrics["status_counts"].get(str(status_code), 0) + 1
        if status_code >= 500:
            _api_metrics["errors_total"] += 1
        if elapsed_ms >= SLOW_REQUEST_MS:
            _api_metrics["slow_requests"] += 1

    if elapsed_ms >= SLOW_REQUEST_MS:
        logger.warning(
            "Slow request: %s %s -> %s in %.2fms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
    _emit_integration_heartbeat("api_request")
    log_session_event(
        "api",
        "request_complete",
        level="warning" if elapsed_ms >= SLOW_REQUEST_MS else "info",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        elapsed_ms=round(elapsed_ms, 2),
    )
    return response

# === END _server_fragment_ops.py ===

# === BEGIN _server_fragment_local_runtime.py ===
_DEFAULT_LEMONADE_BASE_URL = "http://localhost:13305/api/v1"
_LEMONADE_ROLE_ENV = {
    "fast": "GUPPY_LEMONADE_FAST_MODEL",
    "complex": "GUPPY_LEMONADE_COMPLEX_MODEL",
    "teach": "GUPPY_LEMONADE_TEACH_MODEL",
    "code": "GUPPY_LEMONADE_CODE_MODEL",
    "vault": "GUPPY_LEMONADE_VAULT_MODEL",
}
_LOCAL_RUNTIME_WARM_TTL_SECONDS = float(os.environ.get("GUPPY_LOCAL_RUNTIME_WARM_TTL_SECONDS", "300.0"))
_LOCAL_RUNTIME_WARM_TIMEOUT_SECONDS = float(os.environ.get("GUPPY_LOCAL_RUNTIME_WARM_TIMEOUT_SECONDS", "20.0"))
_local_runtime_warm_cache = {
    "backend": "",
    "model": "",
    "checked_at": 0.0,
    "expires_at": 0.0,
    "chat_ready": False,
    "chat_state": "UNKNOWN",
    "chat_detail": "local runtime warmup not checked yet",
}
_local_runtime_warm_lock = threading.Lock()
_local_runtime_warm_refresh_inflight = False


def _selected_local_runtime_backend() -> str:
    backend = str(os.environ.get("GUPPY_LOCAL_RUNTIME_BACKEND", "ollama") or "ollama").strip().lower()
    return backend if backend in {"ollama", "lemonade"} else "ollama"


def _local_runtime_base_url(backend: str) -> str:
    normalized = (backend or "ollama").strip().lower()
    if normalized == "lemonade":
        return str(os.environ.get("GUPPY_LEMONADE_BASE_URL", _DEFAULT_LEMONADE_BASE_URL) or _DEFAULT_LEMONADE_BASE_URL).strip()
    return "http://127.0.0.1:11434"


def _resolve_local_runtime_model(
    backend: str,
    role: str,
    *,
    fallback: str = "",
) -> str:
    normalized_backend = (backend or "ollama").strip().lower()
    normalized_role = (role or "").strip().lower()
    if normalized_backend == "lemonade":
        env_name = _LEMONADE_ROLE_ENV.get(normalized_role)
        if env_name:
            return str(os.environ.get(env_name, fallback) or fallback).strip()
        return str(fallback or "").strip()

    if INFERENCE_ROUTER_AVAILABLE:
        try:
            router = get_router()
            if normalized_role == "fast":
                return str(getattr(router, "LOCAL_FAST_MODEL", fallback) or fallback).strip()
            if normalized_role == "complex":
                return str(getattr(router, "LOCAL_MODEL", fallback) or fallback).strip()
            if normalized_role == "teach":
                return str(getattr(router, "LOCAL_TEACH_MODEL", fallback) or fallback).strip()
            if normalized_role == "code":
                return str(getattr(router, "LOCAL_CODE_MODEL", fallback) or fallback).strip()
            if normalized_role == "vault":
                return str(getattr(router, "LOCAL_VAULT_MODEL", fallback) or fallback).strip()
        except Exception:
            pass
    return str(fallback or "").strip()


def _local_runtime_role_models(backend: str) -> dict[str, str]:
    return {
        "fast": _resolve_local_runtime_model(backend, "fast", fallback="guppy-fast"),
        "complex": _resolve_local_runtime_model(backend, "complex", fallback="guppy"),
        "teach": _resolve_local_runtime_model(backend, "teach", fallback="guppy-teach"),
        "code": _resolve_local_runtime_model(backend, "code", fallback="guppy-code"),
        "vault": _resolve_local_runtime_model(backend, "vault", fallback="vault-scraper"),
    }


def _warm_ollama_chat_lane(model: str, keep_alive: str = "20m") -> tuple[bool, str]:
    normalized_model = str(model or "").strip()
    if not normalized_model:
        return False, "no Ollama model configured for warmup"
    payload = {
        "model": normalized_model,
        "prompt": "warmup",
        "stream": False,
        "keep_alive": keep_alive,
        "options": {"num_predict": 1},
    }
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=_LOCAL_RUNTIME_WARM_TIMEOUT_SECONDS) as resp:
        data = json.loads(resp.read())
    if isinstance(data, dict) and data.get("error"):
        return False, str(data.get("error"))
    return True, f"{normalized_model} warm"


def _current_local_runtime_chat_model(backend: str) -> str:
    role_models = _local_runtime_role_models(backend)
    return str(
        role_models.get("complex")
        or role_models.get("fast")
        or ""
    ).strip()


def _refresh_local_runtime_warm_status(force: bool = False) -> dict[str, Any]:
    backend = _selected_local_runtime_backend()
    model = _current_local_runtime_chat_model(backend)
    now = time.time()
    with _local_runtime_warm_lock:
        cached = dict(_local_runtime_warm_cache)
        if (
            not force
            and cached.get("backend") == backend
            and cached.get("model") == model
            and float(cached.get("expires_at", 0.0) or 0.0) > now
        ):
            return cached

    if backend == "lemonade":
        payload = {
            "backend": backend,
            "model": model,
            "checked_at": now,
            "expires_at": now + max(30.0, _LOCAL_RUNTIME_WARM_TTL_SECONDS),
            "chat_ready": True,
            "chat_state": "READY",
            "chat_detail": "Lemonade backend selected; chat lane treated as ready when registry is reachable",
        }
    else:
        ok, detail = _warm_ollama_chat_lane(model)
        payload = {
            "backend": backend,
            "model": model,
            "checked_at": now,
            "expires_at": now + max(30.0, _LOCAL_RUNTIME_WARM_TTL_SECONDS),
            "chat_ready": bool(ok),
            "chat_state": "READY" if ok else "WARMING",
            "chat_detail": str(detail or ("local runtime warmed" if ok else "local runtime warmup failed")),
        }
    with _local_runtime_warm_lock:
        _local_runtime_warm_cache.update(payload)
        return dict(_local_runtime_warm_cache)


def _local_runtime_warm_cached_or_unknown() -> dict[str, Any]:
    backend = _selected_local_runtime_backend()
    model = _current_local_runtime_chat_model(backend)
    now = time.time()
    with _local_runtime_warm_lock:
        cached = dict(_local_runtime_warm_cache)
        if (
            cached.get("backend") == backend
            and cached.get("model") == model
            and float(cached.get("expires_at", 0.0) or 0.0) > now
        ):
            return cached
    return {
        "backend": backend,
        "model": model,
        "checked_at": 0.0,
        "expires_at": 0.0,
        "chat_ready": False,
        "chat_state": "UNKNOWN",
        "chat_detail": "local runtime warmup not checked yet",
    }


def _trigger_local_runtime_warm_refresh(force: bool = False) -> None:
    global _local_runtime_warm_refresh_inflight
    with _local_runtime_warm_lock:
        if _local_runtime_warm_refresh_inflight:
            return
        if not force:
            cached = dict(_local_runtime_warm_cache)
            now = time.time()
            if float(cached.get("expires_at", 0.0) or 0.0) > now:
                return
        _local_runtime_warm_refresh_inflight = True

    def _worker() -> None:
        global _local_runtime_warm_refresh_inflight
        try:
            _refresh_local_runtime_warm_status(force=True)
        except Exception:
            pass
        finally:
            with _local_runtime_warm_lock:
                _local_runtime_warm_refresh_inflight = False

    threading.Thread(target=_worker, daemon=True).start()


def _fetch_lemonade_model_ids(timeout: float = 4.0) -> set[str]:
    req = urllib.request.Request(
        f"{_local_runtime_base_url('lemonade').rstrip('/')}/models",
        headers={"Accept": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    items = data.get("data", []) if isinstance(data, dict) else []
    return {
        str(item.get("id", "")).strip()
        for item in items
        if isinstance(item, dict) and str(item.get("id", "")).strip()
    }


def _build_local_runtime_status() -> dict[str, Any]:
    backend = _selected_local_runtime_backend()
    role_models = _local_runtime_role_models(backend)
    active_chat_model = _current_local_runtime_chat_model(backend)
    model_ids: set[str] = set()
    detail = ""
    policy: dict[str, Any] = {}
    warm_status = _local_runtime_warm_cached_or_unknown()

    try:
        from src.guppy.local_llm.manifest import get_local_llm_policy_summary, load_local_llm_manifest

        policy = get_local_llm_policy_summary(load_local_llm_manifest())
    except Exception:
        policy = {}

    try:
        if backend == "lemonade":
            model_ids = _fetch_lemonade_model_ids()
            detail = "Lemonade model registry reachable"
        else:
            req = urllib.request.Request(
                "http://127.0.0.1:11434/api/tags",
                headers={"Accept": "application/json"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                data = json.loads(resp.read())
            items = data.get("models", []) if isinstance(data, dict) else []
            model_ids = {
                str(item.get("name", "")).strip()
                for item in items
                if isinstance(item, dict) and str(item.get("name", "")).strip()
            }
            detail = "Ollama model registry reachable"
    except Exception as exc:
        _trigger_local_runtime_warm_refresh(force=False)
        return {
            "backend": backend,
            "base_url": _local_runtime_base_url(backend),
            "state": "MISSING",
            "detail": str(exc),
            "role_models": role_models,
            "available_roles": [],
            "missing_roles": [role for role, model in role_models.items() if model],
            "models": [],
            "policy": policy,
            "chat_ready": bool(warm_status.get("chat_ready", False)),
            "chat_state": str(warm_status.get("chat_state", "UNKNOWN") or "UNKNOWN"),
            "chat_detail": str(warm_status.get("chat_detail", "") or ""),
            "chat_model": str(warm_status.get("model", "") or active_chat_model),
        }

    available_roles = sorted([role for role, model in role_models.items() if model and model in model_ids])
    missing_roles = sorted([role for role, model in role_models.items() if model and model not in model_ids])
    if available_roles and not missing_roles:
        state = "READY"
    elif available_roles:
        state = "PARTIAL"
    else:
        state = "MISSING"

    if backend == "ollama" and available_roles and str(warm_status.get("chat_state", "UNKNOWN") or "UNKNOWN") == "UNKNOWN":
        _trigger_local_runtime_warm_refresh(force=False)
    if backend == "ollama" and available_roles and not bool(warm_status.get("chat_ready", False)) and state == "READY":
        state = "PARTIAL"
        detail = f"{detail} | chat lane warming"

    return {
        "backend": backend,
        "base_url": _local_runtime_base_url(backend),
        "state": state,
        "detail": detail,
        "role_models": role_models,
        "available_roles": available_roles,
        "missing_roles": missing_roles,
        "models": sorted(model_ids),
        "policy": policy,
        "chat_ready": bool(warm_status.get("chat_ready", False)),
        "chat_state": str(warm_status.get("chat_state", "UNKNOWN") or "UNKNOWN"),
        "chat_detail": str(warm_status.get("chat_detail", "") or ""),
        "chat_model": str(warm_status.get("model", "") or active_chat_model),
    }


def _call_lemonade_chat(
    user_text: str,
    system_prompt: str,
    *,
    model_override: Optional[str] = None,
) -> str:
    model_name = str(model_override or "").strip()
    if not model_name:
        role_models = _local_runtime_role_models("lemonade")
        model_name = role_models.get("complex", "")
    if not model_name:
        raise RuntimeError("No Lemonade model configured for this route.")

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        "stream": False,
    }
    req = urllib.request.Request(
        f"{_local_runtime_base_url('lemonade').rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=CHAT_TIMEOUT_SECONDS) as resp:
        data = json.loads(resp.read())
    choices = data.get("choices", []) if isinstance(data, dict) else []
    if not choices:
        raise RuntimeError("Lemonade returned no chat choices.")
    message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
    content = str(message.get("content", "") or "").strip()
    if not content:
        raise RuntimeError("Lemonade returned an empty response.")
    return content


def _call_selected_local_runtime(
    user_text: str,
    system_prompt: str,
    *,
    instance_name: Optional[str] = None,
    instance_type: Optional[str] = None,
    model_override: Optional[str] = None,
) -> str:
    backend = _selected_local_runtime_backend()
    warm_status = _local_runtime_warm_cached_or_unknown()
    if backend == "ollama" and not bool(warm_status.get("chat_ready", False)):
        _trigger_local_runtime_warm_refresh(force=True)
        warm_model = str(warm_status.get("model", "") or _current_local_runtime_chat_model(backend))
        warm_detail = str(warm_status.get("chat_detail", "") or "local runtime is still warming up")
        raise RuntimeError(
            f"Local runtime is still warming up for {warm_model or 'the configured model'}. {warm_detail}"
        )
    if backend == "lemonade":
        return _call_lemonade_chat(
            user_text,
            system_prompt,
            model_override=model_override,
        )
    return _call_ollama_with_tools(
        user_text,
        system_prompt,
        instance_name=instance_name,
        instance_type=instance_type,
        model_override=model_override,
    )

# === END _server_fragment_local_runtime.py ===

# === BEGIN _server_fragment_runtime_status.py ===
async def _run_blocking(func, *args, timeout_seconds: float, **kwargs):
    """Run blocking work in a thread with a hard timeout."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(partial(func, *args, **kwargs)),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Request timed out") from exc


def _extract_text_from_anthropic_blocks(blocks) -> str:
    parts = []
    for b in blocks:
        if getattr(b, "type", None) == "text" and getattr(b, "text", "").strip():
            parts.append(b.text.strip())
    return "\n".join(parts).strip()


def _sanitize_chat_history(history: Any, limit: int = 12) -> list[dict[str, str]]:
    if not isinstance(history, list):
        return []
    out: list[dict[str, str]] = []
    for item in history[-max(1, limit):]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if role not in {"user", "assistant"} or not content:
            continue
        out.append({"role": role, "content": content[:2000]})
    return out


def _build_router_messages(system_prompt: str, user_text: str, history: list[dict[str, str]]) -> list[dict[str, str]]:
    trimmed = list(history)
    if trimmed and trimmed[-1].get("role") == "user" and trimmed[-1].get("content", "").strip() == user_text.strip():
        trimmed = trimmed[:-1]

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(trimmed)
    messages.append({"role": "user", "content": user_text})
    return messages


def _request_is_cacheable(request: ChatRequest) -> bool:
    if not response_cache_enabled():
        return False
    if request.session_id:
        return False
    if _sanitize_chat_history(request.history):
        return False
    mode = (request.mode or "auto").strip().lower()
    if mode in {"teaching", "vault"}:
        return False
    return bool((request.message or "").strip())


def _augment_system_with_history(system_prompt: str, history: list[dict[str, str]]) -> str:
    if not history:
        return system_prompt
    lines = ["LIVE SESSION HISTORY (RECENT TURNS):"]
    for item in history[-8:]:
        speaker = "Ryan" if item.get("role") == "user" else "Guppy"
        snippet = item.get("content", "").replace("\n", " ").strip()
        if len(snippet) > 240:
            snippet = snippet[:240] + "..."
        lines.append(f"- {speaker}: {snippet}")
    return f"{system_prompt}\n\n" + "\n".join(lines)


def _is_rate_limited_error(error: Exception | str) -> bool:
    txt = str(error or "").lower()
    return "429" in txt or "rate limit" in txt or "too many requests" in txt


def _call_unified_inference(
    user_text: str,
    system_prompt: str,
    mode: Optional[str] = None,
    history: Optional[list[dict[str, str]]] = None,
    instance_name: Optional[str] = None,
    instance_type: Optional[str] = None,
) -> str:
    """
    NEW: Unified inference using intelligent router.
    Priority: local (guppy) -> haiku -> sonnet
    Automatically falls back if local model is unavailable.

    This is now the PRIMARY inference method.
    """
    if not GUPPY_CORE_AVAILABLE:
        raise RuntimeError("Guppy core not available.")

    if not INFERENCE_ROUTER_AVAILABLE:
        # Fallback to Claude if router unavailable
        logger.warning("Router unavailable, falling back to Claude")
        return _call_claude_with_tools(
            user_text,
            system_prompt,
            instance_name=instance_name,
            instance_type=instance_type,
        )

    router = get_router()
    clean_history = _sanitize_chat_history(history)
    augmented_system_prompt = _augment_system_with_history(system_prompt, clean_history)
    router_messages = _build_router_messages(augmented_system_prompt, user_text, clean_history)
    requested_mode = (mode or os.environ.get("GUPPY_DEFAULT_MODE", "auto") or "auto").strip().lower()

    try:
        # Local-only mode for overnight low-compute reliability.
        if requested_mode == "local":
            task_type = router._classify_task(user_text, augmented_system_prompt)
            model_name = router.LOCAL_TIER_MAP.get(task_type, router.LOCAL_MODEL)
            paired = os.environ.get("GUPPY_LOCAL_PAIRED", "0").strip().lower() in {"1", "true", "yes", "on"}
            if paired and task_type != "simple":
                result = router.query_local_paired(
                    augmented_system_prompt,
                    user_text,
                    task_type,
                    core.TOOLS,
                    router_messages,
                )
                if not result:
                    raise RuntimeError("Local-only paired mode failed (Ollama/model unavailable)")
                response = str(result.get("response", "")).strip()
                if not response:
                    raise RuntimeError("Local-only paired mode returned empty response")
                source = str(result.get("source", "local"))
                metadata = dict(result.get("metadata", {}))
            else:
                response = _call_selected_local_runtime(
                    user_text,
                    augmented_system_prompt,
                    instance_name=instance_name,
                    instance_type=instance_type,
                    model_override=model_name,
                )
                source = "local"
                metadata = {"route_mode": "local", "model": model_name}
        elif requested_mode == "code":
            result = router.query_with_boost(
                system_prompt=augmented_system_prompt,
                user_text=user_text,
                model=router.LOCAL_CODE_MODEL,
                boost_mode=router.HAIKU_BOOST_CODE_REVIEW,
                tools=None,
                messages=router_messages,
            )
            if not result:
                raise RuntimeError("Code mode local model unavailable")
            response = str(result.get("response", ""))
            source = str(result.get("source", "local"))
            metadata = dict(result.get("metadata", {}))
        else:
            route_decision = router.resolve_ui_route(
                user_text=user_text,
                system_prompt=augmented_system_prompt,
                mode=requested_mode,
                api_key_available=bool(getattr(router, "anthropic_available", False)),
            )
            executor = str(route_decision.get("executor", "") or "").strip().lower()
            target_model = str(route_decision.get("model", "") or "").strip()
            backup_model = str(route_decision.get("backup_model", "") or "").strip()

            if executor == "error":
                raise RuntimeError(str(route_decision.get("error") or route_decision.get("route_reason") or "Requested route unavailable"))

            if executor == "claude":
                response = _call_claude_with_tools(
                    user_text,
                    augmented_system_prompt,
                    instance_name=instance_name,
                    instance_type=instance_type,
                    preferred_model=target_model or None,
                    backup_model=backup_model or None,
                )
                source = "haiku" if "haiku" in (target_model or "").lower() else "sonnet"
                metadata = {"route_decision": route_decision}
            elif executor in {"ollama", "ollama_paired"}:
                if executor == "ollama_paired":
                    result = router.query_local_paired(
                        augmented_system_prompt,
                        user_text,
                        str(route_decision.get("task_type", "complex") or "complex"),
                        core.TOOLS,
                        router_messages,
                    )
                    if not result:
                        raise RuntimeError("Local paired route failed")
                    response = str(result.get("response", "")).strip()
                    if not response:
                        raise RuntimeError("Local paired route returned empty response")
                    source = str(result.get("source", "local"))
                    metadata = dict(result.get("metadata", {}))
                else:
                    response = _call_selected_local_runtime(
                        user_text,
                        augmented_system_prompt,
                        instance_name=instance_name,
                        instance_type=instance_type,
                        model_override=target_model or None,
                    )
                    source = "local"
                    metadata = {"route_decision": route_decision}
            else:
                response, source, metadata = router.query_smart(
                    system_prompt=augmented_system_prompt,
                    user_text=user_text,
                    tools=core.TOOLS,
                    messages=router_messages,
                )

        logger.info(f"Inference completed via {source}. Tokens: {metadata.get('usage', {}).get('output_tokens', '?')}")
        return response

    except Exception as e:
        # Do NOT fall back to Claude when mode is explicitly 'local' or 'code' â€”
        # those modes are intentional; silently spending cloud quota is wrong and
        # hides the real error (e.g. Ollama not running).
        if requested_mode in {"local", "code", "claude", "ollama"}:
            logger.error(f"Inference failed in explicit mode '{requested_mode}': {e}")
            raise
        logger.error(f"Unified inference failed: {e}. Escalating to Claude Sonnet.")
        # Final fallback to Claude (auto/teaching/default modes only).
        # If cloud quota is throttled, fall back to local Ollama text mode before giving up.
        try:
            return _call_claude_with_tools(
                user_text,
                augmented_system_prompt,
                instance_name=instance_name,
                instance_type=instance_type,
            )
        except Exception as cloud_error:
            if _is_rate_limited_error(cloud_error):
                logger.warning("Claude fallback hit rate limits; trying local Ollama fallback")
                return _call_ollama_with_tools(
                    user_text,
                    augmented_system_prompt,
                    instance_name=instance_name,
                    instance_type=instance_type,
                )
            raise



def _call_claude_with_tools(
    user_text: str,
    system_prompt: str,
    *,
    instance_name: Optional[str] = None,
    instance_type: Optional[str] = None,
    preferred_model: Optional[str] = None,
    backup_model: Optional[str] = None,
) -> str:
    if not ANTHROPIC_AVAILABLE:
        raise RuntimeError("Anthropic SDK is not installed.")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")

    primary_model = str(preferred_model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")).strip() or "claude-sonnet-4-6"
    backup_model_name = str(backup_model or os.environ.get("ANTHROPIC_BACKUP_MODEL", "claude-haiku-4-5-20251001")).strip()
    model_chain = [primary_model] + ([backup_model_name] if backup_model_name and backup_model_name != primary_model else [])

    client = anthropic.Anthropic(api_key=api_key)
    msgs = [{"role": "user", "content": user_text}]
    final_text = ""

    while True:
        resp = None
        last_err = None
        for model_name in model_chain:
            try:
                resp = client.messages.create(
                    model=model_name,
                    max_tokens=4096,
                    system=system_prompt,
                    tools=core.TOOLS,
                    messages=msgs,
                )
                break
            except Exception as e:
                last_err = e
        if resp is None:
            raise RuntimeError(f"Claude request failed on all configured models: {last_err}")

        msgs.append({"role": "assistant", "content": resp.content})
        block_text = _extract_text_from_anthropic_blocks(resp.content)
        if block_text:
            final_text = block_text

        tool_uses = [b for b in resp.content if getattr(b, "type", None) == "tool_use"]
        if not tool_uses or getattr(resp, "stop_reason", "") == "end_turn":
            break

        results = []
        for tu in tool_uses:
            result = core.run_tool(
                tu.name,
                tu.input,
                instance_name=instance_name,
                instance_type=instance_type,
            )
            results.append({"type": "tool_result", "tool_use_id": tu.id, "content": str(result)})
        msgs.append({"role": "user", "content": results})

    return final_text or "No response produced."

# === END _server_fragment_runtime_status.py ===

# === BEGIN _server_fragment_runtime_calls.py ===
def _call_ollama_with_tools(
    user_text: str,
    system_prompt: str,
    *,
    instance_name: Optional[str] = None,
    instance_type: Optional[str] = None,
    model_override: Optional[str] = None,
) -> str:
    model = str(model_override or os.environ.get("OLLAMA_MODEL", "guppy")).strip() or "guppy"
    ok, err = core.check_ollama(model)
    if not ok:
        raise RuntimeError(err)

    all_msgs = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}]
    ollama_tools = core.to_ollama_tools(core.TOOLS)
    final_text = ""

    while True:
        payload = json.dumps({
            "model": model,
            "messages": all_msgs,
            "tools": ollama_tools,
            "stream": False,
            "keep_alive": "10m",
            "options": {"temperature": 0.8, "top_p": 0.95, "top_k": 40, "num_predict": 512},
        }).encode()
        req = urllib.request.Request(
            "http://localhost:11434/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read().decode())

        msg = data.get("message", {})
        content = (msg.get("content") or "").strip()
        if content:
            final_text = content

        tool_calls = msg.get("tool_calls") or []
        clean_assistant = {"role": "assistant", "content": content}
        if tool_calls:
            clean_assistant["tool_calls"] = tool_calls
        all_msgs.append(clean_assistant)

        if not tool_calls:
            break

        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            result = core.run_tool(
                name,
                args if isinstance(args, dict) else {},
                instance_name=instance_name,
                instance_type=instance_type,
            )
            all_msgs.append({"role": "tool", "content": str(result)})

    return final_text or "No response produced."


async def _stream_chunks(text: str) -> AsyncGenerator[str, None]:
    for chunk in text.split():
        yield chunk + " "

# â”€â”€ Routes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "Guppy API is running", "status": "healthy"}


@app.get("/metrics")
async def get_metrics(user_id: str = Depends(require_rate_limit)):
    """Runtime metrics for API and tool execution health."""
    del user_id
    with _api_metrics_lock:
        requests_total = _api_metrics["requests_total"]
        avg_latency_ms = (_api_metrics["latency_total_ms"] / requests_total) if requests_total else 0.0
        payload = {
            "started_at": _api_metrics["started_at"],
            "requests_total": requests_total,
            "errors_total": _api_metrics["errors_total"],
            "slow_requests": _api_metrics["slow_requests"],
            "average_latency_ms": round(avg_latency_ms, 2),
            "path_counts": dict(_api_metrics["path_counts"]),
            "status_counts": dict(_api_metrics["status_counts"]),
        }

    if GUPPY_CORE_AVAILABLE and hasattr(core, "get_tool_health_snapshot"):
        try:
            payload["tool_runner"] = core.get_tool_health_snapshot()
        except Exception as e:
            payload["tool_runner_error"] = str(e)
    return payload

@app.post("/auth/verify", response_model=TokenResponse)
async def auth_verify_turnstile_token(
    request: TurnstileToken,
    _auth_limiter: str = Depends(require_auth_rate_limit)
):
    """Verify Turnstile token and issue JWT."""
    if not await verify_turnstile_token_auth(request.token):
        raise HTTPException(status_code=400, detail="Invalid Turnstile token")

    # Issue JWT token
    access_token = create_access_token(data={"sub": "guppy_user"})
    return TokenResponse(
        access_token=access_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@app.get("/auth/self-check")
async def auth_self_check(user_id: str = Depends(require_rate_limit)):
    """Local auth handshake probe for launcher diagnostics."""
    return {
        "ok": True,
        "user_id": user_id,
        "mode": "dev" if DEV_MODE else "strict",
    }


@app.get("/status")
async def get_status(user_id: str = Depends(require_rate_limit)):
    """Get system status and current context."""
    del user_id

    if not GUPPY_CORE_AVAILABLE:
        return {"status": "error", "message": "Guppy core not available"}

    try:
        now = time.time()
        if _status_cache["payload"] is not None and _status_cache["expires_at"] > now:
            return _status_cache["payload"]

        context = {}
        if STATUS_INCLUDE_WINDOW_CONTEXT and GUPPY_DAEMON_AVAILABLE:
            daemon = get_daemon_manager()
            if daemon and getattr(daemon, "window_watcher", None):
                try:
                    context = await asyncio.wait_for(
                        asyncio.to_thread(daemon.window_watcher.get_enhanced_context),
                        timeout=0.2,
                    )
                except Exception:
                    # Keep /status responsive even when watcher context polling stalls.
                    context = {}

        voice_tts = _VOICE_TTS_BACKEND if GUPPY_VOICE_AVAILABLE else "none"
        voice_stt = _VOICE_STT_BACKEND if GUPPY_VOICE_AVAILABLE else "none"
        voice_status = {
            "available": GUPPY_VOICE_AVAILABLE,
            "tts_backend": voice_tts,
            "stt_backend": voice_stt,
            "details": _VOICE_BACKEND_DETAILS if GUPPY_VOICE_AVAILABLE else [],
        }

        payload = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "context": context,
            "memory_available": GUPPY_MEMORY_AVAILABLE,
            "voice_available": GUPPY_VOICE_AVAILABLE,
            "voice_tts_backend": voice_tts,
            "voice_stt_backend": voice_stt,
            "voice_status": voice_status,
            "daemon_available": GUPPY_DAEMON_AVAILABLE,
            "startup_readiness": _startup_readiness_cached_or_unknown(),
            "local_runtime": _build_local_runtime_status(),
            "resource_envelope": _read_resource_envelope_status(),
        }
        _status_cache["payload"] = payload
        _status_cache["expires_at"] = now + STATUS_CACHE_TTL_SECONDS
        return payload
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        log_session_event("api", "status_failed", level="error", error=str(e))
        return {"status": "error", "message": str(e)}


@app.get("/startup/check")
async def startup_check(deep: bool = False, user_id: str = Depends(require_rate_limit)):
    """Startup readiness checks (cached by default, deep probe when requested)."""
    del user_id
    if deep:
        snapshot = await asyncio.to_thread(_startup_readiness_snapshot)
    else:
        snapshot = _startup_readiness_cached_or_unknown()
        if snapshot.get("overall") == "UNKNOWN" or _startup_readiness_cache_expired():
            _trigger_startup_readiness_refresh()
    log_session_event("api", "startup_check", level="info", overall=snapshot.get("overall", "unknown"))
    return snapshot


def _governance_summary_payload(instance_name: str, instance_type: str) -> dict[str, Any]:
    permissions = resolve_instance_permissions(instance_name, instance_type)
    return {
        "auth_mode": str(permissions.get("_auth_mode", "runtime_default") or "runtime_default"),
        "auth_mode_label": auth_mode_label(str(permissions.get("_auth_mode", "runtime_default") or "runtime_default")),
        "tool_allow": list(permissions.get("_tool_allow", [])),
        "tool_block": list(permissions.get("_tool_block", [])),
        "endpoint_allow": list(permissions.get("_endpoint_allow", [])),
        "endpoint_block": list(permissions.get("_endpoint_block", [])),
        "policy_note": str(permissions.get("_policy_note", "") or ""),
        "capabilities": {
            "read": bool(permissions.get("read", False)),
            "write": bool(permissions.get("write", False)),
            "execute": bool(permissions.get("execute", False)),
            "network": bool(permissions.get("network", False)),
        },
    }


def _workspace_connector_payload(instance_name: str) -> list[dict[str, Any]]:
    return workspace_connector_inventory(instance_name, config_path=_config_dir / "connector_bindings.json")


def _connector_inventory_payload() -> list[dict[str, Any]]:
    return connector_inventory()


@app.get("/instances")
async def list_instances(user_id: str = Depends(require_rate_limit)):
    """Contract-first M2 endpoint: list configured instances with lightweight runtime state."""
    del user_id
    config, state, config_warnings, state_warnings = _load_normalized_instance_bundle(persist_repairs=True)

    items: list[dict[str, Any]] = []
    instance_state = state.get("instances", {}) if isinstance(state, dict) else {}
    for item in config.get("instances", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        st = instance_state.get(name, {}) if isinstance(instance_state, dict) else {}
        items.append(
            {
                "name": name,
                "description": str(item.get("description", "")),
                "mode": str(item.get("mode", "auto") or "auto"),
                "persona": str(item.get("persona", "guppy") or "guppy"),
                "voice": str(item.get("voice", "default") or "default"),
                "type": str(item.get("type", "user_instance") or "user_instance"),
                "created_at": item.get("created_at"),
                "enabled": bool(item.get("enabled", True)),
                "status": str(st.get("status", "idle")),
                "last_message": str(st.get("last_message", "")),
                "last_updated": st.get("last_updated"),
                "message_count": int(st.get("message_count", 0) or 0),
                "model_currently_using": str(st.get("model_currently_using", item.get("mode", "auto")) or "auto"),
                "governance": _governance_summary_payload(name, str(item.get("type", "user_instance") or "user_instance")),
                "connectors": _workspace_connector_payload(name),
            }
        )
    limits = _instance_limits_payload(config, state)
    warnings = config_warnings + state_warnings
    if limits["configured"] >= limits["max_configured"]:
        warnings.append("configured instance cap reached (5 / 5)")
    if limits["active_runtime"] >= limits["max_active_runtime"]:
        warnings.append("runtime-active instance cap reached (2 / 2)")

    return {
        "version": int(config.get("version", 1) or 1),
        "active_instance": str(config.get("active_instance", "guppy-primary")),
        "instances": items,
        "limits": limits,
        "warnings": warnings,
    }


@app.post("/instances")
async def create_or_update_instance(
    request: InstanceConfigRequest,
    user_id: str = Depends(require_rate_limit),
):
    del user_id
    raw_config = _load_instances_config()
    config, _warnings = _normalize_instances_config(raw_config)
    config, action = _upsert_instance_config(config, request)
    _save_instances_config(config)

    names = _instance_names(config)
    raw_state = _load_instance_state(config)
    state, _state_warnings = _normalize_instance_state(
        raw_state,
        valid_names=names,
        active_instance=str(config.get("active_instance", names[0] if names else "guppy-primary")),
    )
    instances = state.get("instances", {}) if isinstance(state.get("instances"), dict) else {}
    instances[str(request.name).strip()] = _default_instance_state((request.mode or "auto").strip().lower() or "auto")
    state["instances"] = instances
    _activate_instance_state(state, str(config.get("active_instance", names[0] if names else request.name)).strip())
    _save_instance_state(state)
    limits = _instance_limits_payload(config, state)

    return {
        "ok": True,
        "action": action,
        "instance": str(request.name).strip(),
        "active_instance": str(config.get("active_instance", "guppy-primary")),
        "limits": limits,
    }


@app.post("/instances/{name}/governance")
async def save_instance_governance(
    name: str,
    request: InstanceGovernanceRequest,
    user_id: str = Depends(require_rate_limit),
):
    del user_id
    target = (name or "").strip()
    config, _state, _warnings, _state_warnings = _load_normalized_instance_bundle(persist_repairs=True)
    target_entry = _get_instance_entry(config, target)
    if not isinstance(target_entry, dict):
        raise HTTPException(status_code=404, detail=f"unknown instance: {target}")
    instance_type = str(target_entry.get("type", "user_instance") or "user_instance").strip() or "user_instance"
    resolved = resolve_instance_permissions(target, instance_type)
    set_instance_tool_permission_policy(
        target,
        {
            "read": bool(resolved.get("read", False)),
            "write": bool(resolved.get("write", False)),
            "execute": bool(resolved.get("execute", False)),
            "network": bool(resolved.get("network", False)),
            "auth_mode": request.auth_mode,
            "tool_allow": request.tool_allow,
            "tool_block": request.tool_block,
            "endpoint_allow": request.endpoint_allow,
            "endpoint_block": request.endpoint_block,
            "policy_note": request.policy_note,
        },
    )
    return {
        "ok": True,
        "instance": target,
        "governance": _governance_summary_payload(target, instance_type),
    }


@app.get("/connectors")
async def list_connectors(user_id: str = Depends(require_rate_limit)):
    del user_id
    return {
        "connectors": _connector_inventory_payload(),
    }


@app.post("/connectors/{connector_id}/verify")
async def verify_connector(
    connector_id: str,
    request: ConnectorActionRequest,
    user_id: str = Depends(require_rate_limit),
):
    del user_id
    result = run_connector_action(
        connector_id,
        "verify",
        provider=request.provider,
        account_id=request.account_id,
        secret_key=request.secret_key,
        secret_value=request.secret_value,
    )
    return {"connector": str(connector_id or "").strip().lower(), **result}


@app.post("/connectors/{connector_id}/connect")
async def connect_connector(
    connector_id: str,
    request: ConnectorActionRequest,
    user_id: str = Depends(require_rate_limit),
):
    del user_id
    result = run_connector_action(
        connector_id,
        "connect",
        provider=request.provider,
        account_id=request.account_id,
        secret_key=request.secret_key,
        secret_value=request.secret_value,
    )
    return {"connector": str(connector_id or "").strip().lower(), **result}


@app.post("/connectors/{connector_id}/reconnect")
async def reconnect_connector(
    connector_id: str,
    request: ConnectorActionRequest,
    user_id: str = Depends(require_rate_limit),
):
    del user_id
    result = run_connector_action(
        connector_id,
        "reconnect",
        provider=request.provider,
        account_id=request.account_id,
        secret_key=request.secret_key,
        secret_value=request.secret_value,
    )
    return {"connector": str(connector_id or "").strip().lower(), **result}


@app.post("/connectors/{connector_id}/disconnect")
async def disconnect_connector(
    connector_id: str,
    request: ConnectorActionRequest,
    user_id: str = Depends(require_rate_limit),
):
    del user_id
    result = run_connector_action(
        connector_id,
        "disconnect",
        provider=request.provider,
        account_id=request.account_id,
        secret_key=request.secret_key,
        secret_value=request.secret_value,
    )
    return {"connector": str(connector_id or "").strip().lower(), **result}


@app.get("/instances/{name}/connectors")
async def list_instance_connectors(
    name: str,
    user_id: str = Depends(require_rate_limit),
):
    del user_id
    target = (name or "").strip()
    config, _state, _warnings, _state_warnings = _load_normalized_instance_bundle(persist_repairs=True)
    target_entry = _get_instance_entry(config, target)
    if not isinstance(target_entry, dict):
        raise HTTPException(status_code=404, detail=f"unknown instance: {target}")
    return {
        "instance": target,
        "connectors": _workspace_connector_payload(target),
    }


@app.post("/instances/{name}/connectors/{connector_id}")
async def save_instance_connector_binding(
    name: str,
    connector_id: str,
    request: InstanceConnectorBindingRequest,
    user_id: str = Depends(require_rate_limit),
):
    del user_id
    target = (name or "").strip()
    normalized_connector = (connector_id or "").strip().lower()
    config, _state, _warnings, _state_warnings = _load_normalized_instance_bundle(persist_repairs=True)
    target_entry = _get_instance_entry(config, target)
    if not isinstance(target_entry, dict):
        raise HTTPException(status_code=404, detail=f"unknown instance: {target}")
    save_workspace_connector_binding(
        target,
        normalized_connector,
        {
            "enabled": bool(request.enabled),
            "account_id": request.account_id,
            "provider": request.provider,
            "action_allow": request.action_allow,
            "action_block": request.action_block,
            "endpoint_allow": request.endpoint_allow,
            "endpoint_block": request.endpoint_block,
            "note": request.note,
        },
        config_path=_config_dir / "connector_bindings.json",
    )
    return {
        "ok": True,
        "instance": target,
        "connector": normalized_connector,
        "connectors": _workspace_connector_payload(target),
    }


@app.post("/instances/{name}/activate")
async def activate_instance(
    name: str,
    user_id: str = Depends(require_rate_limit),
):
    del user_id
    target = (name or "").strip()
    raw_config = _load_instances_config()
    config, _warnings = _normalize_instances_config(raw_config)
    names = _instance_names(config)
    if target not in names:
        raise HTTPException(status_code=404, detail=f"unknown instance: {target}")

    config["active_instance"] = target
    _save_instances_config(config)

    raw_state = _load_instance_state(config)
    state, _state_warnings = _normalize_instance_state(
        raw_state,
        valid_names=names,
        active_instance=target,
    )
    _activate_instance_state(state, target)
    _save_instance_state(state)
    return {
        "ok": True,
        "active_instance": target,
        "limits": _instance_limits_payload(config, state),
    }


@app.delete("/instances/{name}")
async def delete_instance(
    name: str,
    user_id: str = Depends(require_rate_limit),
):
    del user_id
    target = (name or "").strip()
    raw_config = _load_instances_config()
    config, _warnings = _normalize_instances_config(raw_config)
    items = list(config.get("instances", [])) if isinstance(config.get("instances"), list) else []
    kept = [item for item in items if not (isinstance(item, dict) and str(item.get("name", "")).strip() == target)]
    if len(kept) == len(items):
        raise HTTPException(status_code=404, detail=f"unknown instance: {target}")
    if not kept:
        raise HTTPException(status_code=400, detail="cannot delete the last configured instance")

    config["instances"] = kept
    names = _instance_names(config)
    if str(config.get("active_instance", "")).strip() == target:
        config["active_instance"] = names[0]
    _save_instances_config(config)

    raw_state = _load_instance_state(config)
    state, _state_warnings = _normalize_instance_state(
        raw_state,
        valid_names=names,
        active_instance=str(config.get("active_instance", names[0])),
    )
    instances = state.get("instances", {}) if isinstance(state.get("instances"), dict) else {}
    instances.pop(target, None)
    state["instances"] = instances
    _save_instance_state(state)
    if _INSTANCE_LOGGER_AVAILABLE:
        delete_instance_log(target)
    return {
        "ok": True,
        "deleted": target,
        "active_instance": str(config.get("active_instance", names[0])),
        "limits": _instance_limits_payload(config, state),
    }

# === END _server_fragment_runtime_calls.py ===

# === BEGIN _server_fragment_routes_core.py ===
@app.get("/instances/{name}/logs")
async def get_instance_logs(
    name: str,
    limit: int = 50,
    user_id: str = Depends(require_rate_limit),
):
    del user_id
    target = (name or "").strip()
    raw_config = _load_instances_config()
    config, _warnings = _normalize_instances_config(raw_config)
    if target not in _instance_names(config):
        raise HTTPException(status_code=404, detail=f"unknown instance: {target}")
    return {
        "instance": target,
        "entries": read_instance_log_tail(target, limit=limit) if _INSTANCE_LOGGER_AVAILABLE else [],
        "summary": read_instance_log_summary(target) if _INSTANCE_LOGGER_AVAILABLE else {"entry_count": 0, "roles": {}, "statuses": {}},
    }


@app.post("/instances/{name}/query")
async def query_instance(
    name: str,
    request: InstanceQueryRequest,
    user_id: str = Depends(require_rate_limit),
):
    """Contract-first M2 endpoint: bounded synchronous inter-instance query.

    M2.0 semantics:
    - single in-flight cross-instance query globally
    - returns status=busy if another query is running
    - returns status=timeout for bounded timeout exhaustion
    """
    del user_id
    target = (name or "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="instance name is required")
    if not GUPPY_CORE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Guppy core not available")

    config, state, _config_warnings, _state_warnings = _load_normalized_instance_bundle(persist_repairs=True)
    names = _instance_names(config)
    if target not in names:
        raise HTTPException(status_code=404, detail=f"unknown instance: {target}")
    target_entry = _get_instance_entry(config, target) or {}
    target_type = str(target_entry.get("type", "user_instance") or "user_instance").strip() or "user_instance"
    source_instance = (request.source_instance or "launcher").strip() or "launcher"
    if source_instance != "launcher":
        if source_instance not in names:
            raise HTTPException(status_code=404, detail=f"unknown source instance: {source_instance}")
        source_entry = _get_instance_entry(config, source_instance) or {}
        source_type = str(source_entry.get("type", "user_instance") or "user_instance").strip() or "user_instance"
        allowed, reason, _permissions = check_instance_tool_permission(
            "query_instance",
            instance_name=source_instance,
            instance_type=source_type,
            endpoint=f"instance://{target}",
            metadata={"target_instance": target},
        )
        if not allowed:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"workspace {source_instance} cannot use cross-workspace query right now: "
                    f"{reason or 'query permission denied'}"
                ),
            )

    if not _instance_query_lock.acquire(blocking=False):
        return {
            "status": "busy",
            "source_instance": source_instance,
            "target_instance": target,
            "response": "",
            "tokens_used": 0,
            "model": "",
            "duration_ms": 0,
        }

    started = time.perf_counter()
    try:
        timeout_s = max(0.5, min(float(request.timeout_s or 5.0), 5.0))
        query_text = (request.message or "").strip()
        if not query_text:
            raise HTTPException(status_code=400, detail="message is required")

        mode = "auto"
        for item in config.get("instances", []):
            if isinstance(item, dict) and str(item.get("name", "")).strip() == target:
                mode = str(item.get("mode", "auto") or "auto").strip().lower()
                break

        system_prompt = _build_chat_system_prompt(
            session_id=f"instance-{target}",
            message=query_text,
            mode=mode,
            persona=str(target_entry.get("persona", "guppy") or "guppy").strip() or "guppy",
            model_id="",
        )
        try:
            response = await _run_blocking(
                _call_unified_inference,
                query_text,
                system_prompt,
                mode,
                None,
                instance_name=target,
                instance_type=target_type,
                timeout_seconds=timeout_s,
            )
            status = "ok"
        except HTTPException as e:
            if e.status_code == 504:
                response = ""
                status = "timeout"
            else:
                raise

        duration_ms = int((time.perf_counter() - started) * 1000)

        instances = state.setdefault("instances", {}) if isinstance(state, dict) else {}
        if isinstance(instances, dict):
            inst = instances.setdefault(target, {})
            if isinstance(inst, dict):
                inst["status"] = "busy" if status == "busy" else "running"
                inst["last_message"] = query_text[:200]
                inst["last_updated"] = datetime.now(timezone.utc).isoformat()
                inst["message_count"] = int(inst.get("message_count", 0) or 0) + 1
                inst["model_currently_using"] = mode
            _save_instance_state(state)

        if _INSTANCE_LOGGER_AVAILABLE:
            append_instance_log(
                target,
                {
                    "role": "user",
                    "source_instance": source_instance,
                    "message": query_text,
                    "status": status,
                    "model": mode,
                },
            )
            if response:
                append_instance_log(
                    target,
                    {
                        "role": "assistant",
                        "source_instance": target,
                        "message": response,
                        "status": status,
                        "model": mode,
                        "duration_ms": duration_ms,
                    },
                )

        return {
            "status": status,
            "source_instance": source_instance,
            "target_instance": target,
            "response": response,
            "tokens_used": max(1, len(response) // 4) if response else 0,
            "model": mode,
            "duration_ms": duration_ms,
        }
    finally:
        _instance_query_lock.release()


@app.get("/logs/recent")
async def get_recent_logs(
    limit: int = 100,
    user_id: str = Depends(require_rate_limit),
):
    """Return recent structured events for fast review during active sessions."""
    del user_id
    lim = max(1, min(int(limit), 300))
    runtime_dir = _runtime_dir
    return {
        "session_events": tail_session_events(limit=lim),
        "agent_performance": _read_jsonl_tail(runtime_dir / "agent_performance.jsonl", limit=lim),
        "integration_events": _read_jsonl_tail(runtime_dir / "integration_events.jsonl", limit=lim),
    }


@app.get("/telemetry/query")
async def telemetry_query(
    stream: Optional[str] = None,
    event: Optional[str] = None,
    level: Optional[str] = None,
    since_minutes: int = 1440,
    limit: int = 200,
    backend: str = "auto",
    user_id: str = Depends(require_rate_limit),
):
    """Query operational telemetry with filters (SQLite-first with JSONL fallback)."""
    del user_id
    lim = max(1, min(int(limit), 1000))
    since = max(0, int(since_minutes))
    stream_key = (stream or "").strip() or None
    event_key = (event or "").strip() or None
    level_key = (level or "").strip().lower() or None
    backend_key = (backend or "auto").strip().lower()
    if backend_key not in {"auto", "sqlite", "jsonl"}:
        raise HTTPException(status_code=400, detail="backend must be one of: auto, sqlite, jsonl")

    events: list[dict[str, Any]] = []
    source = backend_key
    if backend_key in {"auto", "sqlite"}:
        events = _query_sqlite_telemetry(stream_key, event_key, level_key, since, lim)
        source = "sqlite"

    if backend_key == "jsonl" or (backend_key == "auto" and not events):
        events = _query_jsonl_telemetry(stream_key, event_key, level_key, since, lim)
        source = "jsonl"

    return {
        "source": source,
        "count": len(events),
        "filters": {
            "stream": stream_key,
            "event": event_key,
            "level": level_key,
            "since_minutes": since,
            "limit": lim,
        },
        "events": events,
    }


@app.get("/telemetry/report")
async def telemetry_report(
    stream: Optional[str] = None,
    since_minutes: int = 1440,
    limit: int = 1000,
    backend: str = "auto",
    user_id: str = Depends(require_rate_limit),
):
    """Return summarized telemetry report for dashboards and ops checks."""
    del user_id
    lim = max(1, min(int(limit), 2000))
    since = max(0, int(since_minutes))
    stream_key = (stream or "").strip() or None
    backend_key = (backend or "auto").strip().lower()
    if backend_key not in {"auto", "sqlite", "jsonl"}:
        raise HTTPException(status_code=400, detail="backend must be one of: auto, sqlite, jsonl")

    events: list[dict[str, Any]] = []
    source = backend_key
    if backend_key in {"auto", "sqlite"}:
        events = _query_sqlite_telemetry(stream_key, None, None, since, lim)
        source = "sqlite"

    if backend_key == "jsonl" or (backend_key == "auto" and not events):
        events = _query_jsonl_telemetry(stream_key, None, None, since, lim)
        source = "jsonl"

    report = _build_telemetry_report(events)
    return {
        "source": source,
        "window": {
            "stream": stream_key,
            "since_minutes": since,
            "limit": lim,
        },
        "report": report,
    }


def _require_repair_token(request: Request) -> None:
    """Dependency: verify X-Repair-Token matches the in-memory token set at startup."""
    provided = (request.headers.get("X-Repair-Token") or "").strip()

    if not _REPAIR_TOKEN:
        log_session_event(
            "api",
            "repair_token_rejected",
            level="warning",
            reason_code="repair_token_uninitialized",
            has_header=bool(provided),
        )
        raise HTTPException(
            status_code=403,
            detail={"code": "repair_token_uninitialized", "message": "Invalid repair token"},
        )

    if not provided:
        log_session_event(
            "api",
            "repair_token_rejected",
            level="warning",
            reason_code="repair_token_missing",
            has_header=False,
        )
        raise HTTPException(
            status_code=403,
            detail={"code": "repair_token_missing", "message": "Invalid repair token"},
        )

    if not secrets.compare_digest(_REPAIR_TOKEN, provided):
        log_session_event(
            "api",
            "repair_token_rejected",
            level="warning",
            reason_code="repair_token_mismatch",
            has_header=True,
        )
        raise HTTPException(
            status_code=403,
            detail={"code": "repair_token_mismatch", "message": "Invalid repair token"},
        )


@app.get("/repair-token/refresh")
async def repair_token_refresh(_req: Request):
    """
    Re-read the current repair token from the OS credential store (or fallback file)
    and return it to a local caller.

    Security: localhost-only. Only 127.0.0.1 may call this endpoint.
    Purpose: allows the launcher to recover after an API restart rotates the token
    in cases where the OS keyring read in the launcher fails or races.
    The endpoint itself carries no auth requirement because it is the auth source.
    """
    client_ip = _req.client.host if _req.client else ""
    if client_ip not in ("127.0.0.1", "::1", "localhost", ""):
        log_session_event(
            "api", "repair_token_refresh_rejected",
            level="warning", client_ip=client_ip,
        )
        raise HTTPException(status_code=403, detail="localhost only")

    # Prefer the active in-memory token first. Keyring/file can lag behind restarts.
    token = _REPAIR_TOKEN or ""
    if _SECRET_STORE_AVAILABLE and _secret_store is not None:
        try:
            token = token or (_secret_store.get_secret("repair_token") or "")
        except Exception:
            pass
    if not token and _REPAIR_TOKEN_FILE.exists():
        try:
            token = _REPAIR_TOKEN_FILE.read_text(encoding="utf-8").strip()
        except Exception:
            pass

    log_session_event(
        "api", "repair_token_refresh",
        level="info", client_ip=client_ip, has_token=bool(token),
    )
    return {"repair_token": token}


@app.post("/repair")
async def repair_runtime(
    request: RepairRequest,
    _req: Request,
    user_id: str = Depends(require_rate_limit),
    _tok: None = Depends(_require_repair_token),
):
    """Guarded internal repair entrypoint for launcher/operator flows."""
    del user_id
    action = (request.action or "").strip().lower()
    dry_run = bool(request.dry_run)
    result = await asyncio.to_thread(_do_repair_action, action, dry_run)
    log_session_event(
        "api",
        "repair_runtime",
        level="info",
        action=action,
        dry_run=dry_run,
        ok=bool(result.get("ok", False)),
        summary=str(result.get("summary", "")),
    )
    return {
        "action": action,
        "dry_run": dry_run,
        **result,
    }


@app.get("/revenue/dashboard")
async def get_revenue_dashboard(user_id: str = Depends(require_rate_limit)):
    """Return structured revenue and pipeline dashboard data."""
    del user_id
    if not GUPPY_MEMORY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Memory module not available")
    if not hasattr(memory, "get_revenue_dashboard_data"):
        raise HTTPException(status_code=503, detail="Revenue dashboard not configured")

    try:
        return memory.get_revenue_dashboard_data()
    except Exception as e:
        logger.error(f"Revenue dashboard failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat(request: ChatRequest, user_id: str = Depends(require_rate_limit)):
    """Send text message and get response."""
    del user_id

    if not GUPPY_CORE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Guppy core not available")

    idempotency_key = str(request.idempotency_key or "").strip()
    request_fingerprint = _build_chat_request_fingerprint(request) if idempotency_key else ""
    idempotency_owner = False
    if idempotency_key:
        while True:
            idempotency_owner, idempotency_event = _register_chat_idempotency_key(idempotency_key, request_fingerprint)
            if idempotency_owner:
                break
            await _run_blocking(
                idempotency_event.wait,
                timeout_seconds=max(CHAT_TIMEOUT_SECONDS, 120.0),
            )
            idempotent_result = _resolve_chat_idempotency_key(idempotency_key, request_fingerprint)
            if isinstance(idempotent_result, dict):
                response_payload = idempotent_result.get("response")
                if isinstance(response_payload, dict):
                    return response_payload
                if "error" in idempotent_result:
                    raise HTTPException(
                        status_code=int(idempotent_result.get("status", 500) or 500),
                        detail=idempotent_result.get("error"),
                        headers=idempotent_result.get("headers") if isinstance(idempotent_result.get("headers"), dict) else None,
                    )
            idempotency_owner, idempotency_event, took_ownership = _takeover_chat_idempotency_key(
                idempotency_key,
                request_fingerprint,
            )
            if idempotency_owner and took_ownership:
                break

    try:
        active_instance_name, active_instance_type, active_instance_persona, _active_instance_voice = _get_active_instance_context()
        if _request_is_morning_brief(request):
            response = _build_morning_brief_response()
            log_session_event(
                "api",
                "morning_brief_served",
                level="info",
                session_id=request.session_id or "",
                instance_name=active_instance_name,
                used_saved_report=bool(_latest_daily_report_path()),
            )
            if request.session_id and GUPPY_MEMORY_AVAILABLE:
                for role, content in (("user", request.message), ("assistant", response)):
                    try:
                        memory.save_message(request.session_id, role, content)
                    except Exception as exc:
                        logger.error(
                            "morning brief memory.save_message failed session_id=%r role=%s error=%s",
                            request.session_id,
                            role,
                            exc,
                        )
            payload = {"response": response, "session_id": request.session_id, "brief": True}
            if idempotency_owner and idempotency_key:
                _complete_chat_idempotency_key(idempotency_key, response=payload, status_code=200)
            return payload

        system_prompt = _build_chat_system_prompt(
            session_id=request.session_id,
            message=request.message,
            mode=request.mode,
            persona=request.persona or active_instance_persona,
            model_id=request.mode,
            history=request.history,
        )

        cache_key = None
        if INFERENCE_ROUTER_AVAILABLE and _request_is_cacheable(request):
            try:
                router = get_router()
                task_type = router._classify_task(request.message, system_prompt)
                if task_type == "simple":
                    cache_key = build_response_cache_key(
                        message=request.message,
                        system_prompt=system_prompt,
                        mode=request.mode or "auto",
                        instance_name=active_instance_name,
                        instance_type=active_instance_type,
                    )
                    cached_response = get_cached_response(cache_key)
                    if cached_response:
                        payload = {"response": cached_response, "session_id": request.session_id, "cached": True}
                        if idempotency_owner and idempotency_key:
                            _complete_chat_idempotency_key(idempotency_key, response=payload, status_code=200)
                        return payload
            except Exception as e:
                logger.debug("Response cache lookup skipped: %s", e)

        response = await _run_blocking(
            _call_unified_inference,
            request.message,
            system_prompt,
            request.mode,
            request.history,
            instance_name=active_instance_name,
            instance_type=active_instance_type,
            timeout_seconds=CHAT_TIMEOUT_SECONDS,
        )

        if cache_key and response.strip():
            try:
                set_cached_response(cache_key, response)
            except Exception as e:
                logger.debug("Response cache store skipped: %s", e)

        if request.session_id and GUPPY_MEMORY_AVAILABLE:
            memory.save_message(request.session_id, "user", request.message)
            memory.save_message(request.session_id, "assistant", response)

        payload = {"response": response, "session_id": request.session_id}
        if idempotency_owner and idempotency_key:
            _complete_chat_idempotency_key(idempotency_key, response=payload, status_code=200)
        return payload

    except HTTPException as exc:
        if idempotency_owner and idempotency_key:
            _complete_chat_idempotency_key(
                idempotency_key,
                error=getattr(exc, "detail", "chat request failed"),
                status_code=int(getattr(exc, "status_code", 500) or 500),
                headers=getattr(exc, "headers", None),
            )
        raise
    except Exception as e:
        logger.error(f"Chat request failed: {e}")
        log_session_event(
            "api",
            "chat_failed",
            level="error",
            session_id=request.session_id or "",
            use_claude=bool(request.use_claude),
            error=str(e),
        )
        if idempotency_owner and idempotency_key:
            _complete_chat_idempotency_key(idempotency_key, error=str(e), status_code=500)
        raise HTTPException(status_code=500, detail=str(e))

# === END _server_fragment_routes_core.py ===

# === BEGIN _server_fragment_routes_ops.py ===
@app.post("/chat/voice")
async def chat_voice(
    file: UploadFile = File(...),
    session_id: Optional[str] = None,
    use_claude: Optional[bool] = True,
    user_id: str = Depends(require_rate_limit)
):
    """Upload audio file and get transcription + response."""
    del user_id

    if not GUPPY_CORE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Guppy core not available")

    if not GUPPY_VOICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Voice processing not available")

    try:
        active_instance_name, active_instance_type, active_instance_persona, _active_instance_voice = _get_active_instance_context()
        temp_path = await _save_voice_upload_tempfile(file)

        try:
            # Transcribe audio
            voice_handler = await _run_blocking(
                voice.GuppyVoice,
                timeout_seconds=VOICE_TIMEOUT_SECONDS,
            )
            if hasattr(voice_handler, "transcribe_audio"):
                transcription = await _run_blocking(
                    voice_handler.transcribe_audio,
                    temp_path,
                    timeout_seconds=VOICE_TIMEOUT_SECONDS,
                )
            elif hasattr(voice_handler, "whisper_model") and voice_handler.whisper_model:
                segments, _info = await _run_blocking(
                    voice_handler.whisper_model.transcribe,
                    temp_path,
                    timeout_seconds=VOICE_TIMEOUT_SECONDS,
                )
                transcription = " ".join(seg.text for seg in segments).strip()
            else:
                raise HTTPException(status_code=503, detail="Voice transcription engine not available")

            if not transcription:
                raise HTTPException(status_code=400, detail="Could not transcribe audio")

            # Get response using transcribed text
            system_prompt = _build_chat_system_prompt(
                session_id=session_id,
                message=transcription,
                persona=active_instance_persona,
                model_id="",
            )

            # Route through priority chain: local (guppy) -> haiku -> sonnet
            response = await _run_blocking(
                _call_unified_inference,
                transcription,
                system_prompt,
                instance_name=active_instance_name,
                instance_type=active_instance_type,
                timeout_seconds=CHAT_TIMEOUT_SECONDS,
            )

            # Store in memory if session provided and memory is available
            if session_id and GUPPY_MEMORY_AVAILABLE:
                memory.save_message(session_id, "user", f"[Voice] {transcription}")
                memory.save_message(session_id, "assistant", response)

            return {
                "transcription": transcription,
                "response": response,
                "session_id": session_id
            }

        finally:
            # Clean up temp file
            Path(temp_path).unlink(missing_ok=True)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice chat request failed: {e}")
        log_session_event(
            "api",
            "voice_chat_failed",
            level="error",
            session_id=session_id or "",
            use_claude=bool(use_claude),
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for streaming responses."""
    await websocket.accept()

    try:
        # Receive initial auth message
        auth_data = await websocket.receive_json()
        token = auth_data.get("token")

        if not token:
            await websocket.send_json({"error": "Authentication required"})
            await websocket.close()
            return

        # Verify token
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            _ = payload.get("sub")  # validated but not used beyond auth check
        except JWTError:
            await websocket.send_json({"error": "Invalid token"})
            await websocket.close()
            return

        await websocket.send_json({"status": "authenticated"})

        # Handle streaming chat
        while True:
            try:
                data = await websocket.receive_json()
                message = data.get("message")
                session_id = data.get("session_id")
                mode = data.get("mode")
                use_claude = data.get("use_claude", True)

                if not message:
                    continue

                if not GUPPY_CORE_AVAILABLE:
                    await websocket.send_json({"error": "Guppy core not available"})
                    continue

                # Get system prompt
                active_instance_name, active_instance_type, active_instance_persona, _active_instance_voice = _get_active_instance_context()
                system_prompt = _build_chat_system_prompt(
                    session_id=session_id,
                    message=message,
                    mode=mode,
                    persona=data.get("persona") or active_instance_persona,
                    model_id=mode or "",
                )

                # Stream response â€” route through priority chain: local (guppy) -> haiku -> sonnet
                text = await _run_blocking(
                    _call_unified_inference,
                    message,
                    system_prompt,
                    instance_name=active_instance_name,
                    instance_type=active_instance_type,
                    timeout_seconds=CHAT_TIMEOUT_SECONDS,
                )
                async for chunk in _stream_chunks(text):
                    await websocket.send_json({"chunk": chunk})

                await websocket.send_json({"done": True})

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                log_session_event("api", "ws_error", level="error", error=str(e))
                await websocket.send_json({"error": str(e)})

    except Exception as e:
        logger.error(f"WebSocket connection failed: {e}")
        log_session_event("api", "ws_connection_failed", level="error", error=str(e))

# â”€â”€ Main â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

if __name__ == "__main__":
    api_reload = os.environ.get("GUPPY_API_RELOAD", "").strip().lower() in {"1", "true", "yes", "on"}
    if not api_reload:
        api_reload = DEV_MODE

        uvicorn.run(
            "src.guppy.api.server:app",
        host=HOST,
        port=PORT,
        reload=api_reload,
        log_level="info"
    )

# === END _server_fragment_routes_ops.py ===
