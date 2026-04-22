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


