"""Compatibility snapshot of the assembled FastAPI server module.

This module preserves the fully assembled server shape for inspection and
rebuild workflows. The canonical runtime behavior now lives in explicit
helpers under ``src/guppy/api/``.
"""

# Compatibility note: this snapshot keeps the assembled module import surface
# available for inspection and rebuild tools, while the canonical runtime lives
# in smaller helpers under src/guppy/api/.
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
import importlib.util
import logging
import os
import re
import secrets
import sys
import tempfile
import time
import asyncio
import threading
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from functools import partial
from types import SimpleNamespace
from typing import Optional, AsyncGenerator, Any, Dict, List
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from jose import JWTError, jwt
import urllib.request

from src.guppy.paths import CONFIG_DIR, RUNTIME_DIR
from src.guppy.api.chat_idempotency import (
    build_chat_request_fingerprint,
    complete_chat_idempotency_key,
    register_chat_idempotency_key,
    resolve_chat_idempotency_key,
    takeover_chat_idempotency_key,
)
from src.guppy.api.instance_state_support import (
    activate_instance_state as _activate_instance_state,
    default_instance_state as _default_instance_state,
    get_instance_entry as _get_instance_entry,
    instance_config_entry as _instance_config_entry,
    instance_limits_payload as _instance_limits_payload,
    instance_names as _instance_names,
    normalize_instance_state as _normalize_instance_state,
    normalize_instances_config as _normalize_instances_config,
    upsert_instance_config as _upsert_instance_config,
)
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
from src.guppy.api import (
    services_briefing,
    services_instances,
    services_ops,
    services_realtime,
    services_runtime,
    snapshot_route_support,
    services_telemetry,
    snapshot_instances_support,
    snapshot_telemetry_support,
)
from src.guppy.api.status_support import (
    build_startup_check_response,
    build_status_response,
)

# Configuration

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
_path_config = SimpleNamespace(
    config_dir=_config_dir,
    runtime_dir=_runtime_dir,
    instances_path=_instances_path,
    connector_bindings_path=_connector_bindings_path,
    instance_state_path=_instance_state_path,
)

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

# â”€â”€ Pydantic Models â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _should_use_rich_chat_prompt_context(request: ChatRequest) -> bool:
    return services_realtime.should_use_rich_chat_prompt_context(request)


def _should_use_rich_prompt_context(
    *,
    message: str,
    mode: str | None = None,
    history: Any = None,
) -> bool:
    return services_realtime.should_use_rich_prompt_context(
        message=message,
        mode=mode,
        history=history,
    )


def _build_chat_system_prompt(
    *,
    message: str,
    session_id: str | None = None,
    mode: str | None = None,
    persona: str | None = None,
    model_id: str | None = None,
    history: Any = None,
) -> str:
    return services_realtime.build_chat_system_prompt(
        _module_owner(),
        message=message,
        session_id=session_id,
        mode=mode,
        persona=persona,
        model_id=model_id,
        history=history,
    )


async def _save_voice_upload_tempfile(file: UploadFile) -> str:
    return await services_realtime.save_voice_upload_tempfile(_module_owner(), file)


def _read_jsonl_tail(path: Path, limit: int = 50):
    return services_ops.read_jsonl_tail(path, limit=limit)

# === END _server_fragment_bootstrap.py ===

# === BEGIN _server_fragment_instances_telemetry.py ===
def _ensure_m2_instance_scaffold() -> None:
    services_instances.ensure_m2_instance_scaffold(_module_owner())


def _load_instances_config() -> dict[str, Any]:
    return services_instances.load_instances_config(_module_owner())


def _load_instance_state(config: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    return services_instances.load_instance_state(_module_owner(), config)


def _save_instance_state(state: dict[str, Any]) -> None:
    services_instances.save_instance_state(_module_owner(), state)


def _save_instances_config(config: dict[str, Any]) -> None:
    services_instances.save_instances_config(_module_owner(), config)


def _load_normalized_instance_bundle(*, persist_repairs: bool = False) -> tuple[dict[str, Any], dict[str, Any], list[str], list[str]]:
    return services_instances.load_normalized_instance_bundle(
        _module_owner(),
        persist_repairs=persist_repairs,
    )


def _get_active_instance_context() -> tuple[str | None, str | None, str | None, str | None]:
    return services_instances.get_active_instance_context(_module_owner())


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
    return services_ops.read_resource_envelope_status(
        _module_owner(),
        missing_message="resource envelope status not available",
        unavailable_message="resource envelope status unreadable",
    )


# === END _server_fragment_instances_telemetry.py ===

# === BEGIN _server_fragment_ops.py ===
def _latest_stress_report_path() -> Path | None:
    return services_ops.latest_stress_report_path(_module_owner())


_request_is_morning_brief = services_briefing.request_is_morning_brief


def _latest_daily_report_path() -> Path | None:
    return services_briefing.latest_daily_report_path(_module_owner())


def _build_morning_brief_response() -> str:
    return services_briefing.build_morning_brief_response(_module_owner())


def _collect_runtime_bundle() -> dict[str, Any]:
    return services_ops.collect_runtime_bundle(_module_owner())


def _do_repair_action(action: str, dry_run: bool) -> dict[str, Any]:
    return services_ops.do_repair_action(_module_owner(), action, dry_run)


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
    return services_runtime.build_startup_readiness_payload(_module_owner())


def _startup_readiness_snapshot() -> dict:
    return services_runtime.startup_readiness_snapshot(_module_owner())


def _startup_readiness_cached_or_unknown() -> dict:
    return services_runtime.startup_readiness_cached_or_unknown(_module_owner())


def _startup_readiness_cached_or_snapshot() -> dict:
    return services_runtime.startup_readiness_cached_or_snapshot(_module_owner())


def _startup_readiness_cache_expired() -> bool:
    return services_runtime.startup_readiness_cache_expired(_module_owner())


def _trigger_startup_readiness_refresh() -> None:
    services_runtime.trigger_startup_readiness_refresh(_module_owner())

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
_runtime_state = SimpleNamespace(
    startup_check_cache=_startup_check_cache,
    startup_check_cache_lock=_startup_check_cache_lock,
    startup_check_refresh_inflight=False,
    local_runtime_warm_cache={
        "backend": "",
        "model": "",
        "checked_at": 0.0,
        "expires_at": 0.0,
        "chat_ready": False,
        "chat_state": "UNKNOWN",
        "chat_detail": "local runtime warmup not checked yet",
    },
    local_runtime_warm_lock=threading.Lock(),
    local_runtime_warm_refresh_inflight=False,
)
_local_runtime_warm_cache = _runtime_state.local_runtime_warm_cache
_local_runtime_warm_lock = _runtime_state.local_runtime_warm_lock


def _module_owner() -> Any:
    return sys.modules[__name__]


def _bind_runtime_service(func):
    def wrapper(*args, **kwargs):
        return func(_module_owner(), *args, **kwargs)

    return wrapper


_selected_local_runtime_backend = _bind_runtime_service(services_runtime.selected_local_runtime_backend)
_local_runtime_base_url = _bind_runtime_service(services_runtime.local_runtime_base_url)
_resolve_local_runtime_model = _bind_runtime_service(services_runtime.resolve_local_runtime_model)
_local_runtime_role_models = _bind_runtime_service(services_runtime.local_runtime_role_models)
_warm_ollama_chat_lane = _bind_runtime_service(services_runtime.warm_ollama_chat_lane)
_current_local_runtime_chat_model = _bind_runtime_service(services_runtime.current_local_runtime_chat_model)
_refresh_local_runtime_warm_status = _bind_runtime_service(services_runtime.refresh_local_runtime_warm_status)
_local_runtime_warm_cached_or_unknown = _bind_runtime_service(services_runtime.local_runtime_warm_cached_or_unknown)
_trigger_local_runtime_warm_refresh = _bind_runtime_service(services_runtime.trigger_local_runtime_warm_refresh)
_fetch_lemonade_model_ids = _bind_runtime_service(services_runtime.fetch_lemonade_model_ids)
_build_local_runtime_status = _bind_runtime_service(services_runtime.build_local_runtime_status)
_call_lemonade_chat = _bind_runtime_service(services_runtime.call_lemonade_chat)
_call_selected_local_runtime = _bind_runtime_service(services_runtime.call_selected_local_runtime)
_build_instance_list_response = _bind_runtime_service(snapshot_instances_support.build_instance_list_response)
_create_or_update_instance_response = _bind_runtime_service(snapshot_instances_support.create_or_update_instance_response)
_save_instance_governance_response = _bind_runtime_service(snapshot_instances_support.save_instance_governance_response)
_list_connectors_response = _bind_runtime_service(snapshot_instances_support.list_connectors_response)
_run_connector_action_response = _bind_runtime_service(snapshot_instances_support.run_connector_action_response)
_list_instance_connectors_response = _bind_runtime_service(snapshot_instances_support.list_instance_connectors_response)
_save_instance_connector_binding_response = _bind_runtime_service(snapshot_instances_support.save_instance_connector_binding_response)
_activate_instance_response = _bind_runtime_service(snapshot_instances_support.activate_instance_response)
_delete_instance_response = _bind_runtime_service(snapshot_instances_support.delete_instance_response)
_build_instance_logs_response = _bind_runtime_service(snapshot_instances_support.build_instance_logs_response)

# === END _server_fragment_local_runtime.py ===

# === BEGIN _server_fragment_runtime_status.py ===
async def _run_blocking(func, *args, timeout_seconds: float, **kwargs):
    return await services_realtime.run_blocking(
        func,
        *args,
        timeout_seconds=timeout_seconds,
        **kwargs,
    )


def _extract_text_from_anthropic_blocks(blocks) -> str:
    return services_realtime.extract_text_from_anthropic_blocks(blocks)


def _sanitize_chat_history(history: Any, limit: int = 12) -> list[dict[str, str]]:
    return services_realtime.sanitize_chat_history(history, limit=limit)


def _build_router_messages(system_prompt: str, user_text: str, history: list[dict[str, str]]) -> list[dict[str, str]]:
    return services_realtime.build_router_messages(system_prompt, user_text, history)


def _request_is_cacheable(request: ChatRequest) -> bool:
    return services_realtime.request_is_cacheable(_module_owner(), request)


def _augment_system_with_history(system_prompt: str, history: list[dict[str, str]]) -> str:
    return services_realtime.augment_system_with_history(system_prompt, history)


def _is_rate_limited_error(error: Exception | str) -> bool:
    return services_realtime.is_rate_limited_error(error)


def _call_unified_inference(
    user_text: str,
    system_prompt: str,
    mode: Optional[str] = None,
    history: Optional[list[dict[str, str]]] = None,
    instance_name: Optional[str] = None,
    instance_type: Optional[str] = None,
) -> str:
    return services_realtime.call_unified_inference(
        _module_owner(),
        user_text,
        system_prompt,
        mode=mode,
        history=history,
        instance_name=instance_name,
        instance_type=instance_type,
    )



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


def _build_status_support_context() -> SimpleNamespace:
    return SimpleNamespace(
        owner=SimpleNamespace(
            GUPPY_MEMORY_AVAILABLE=GUPPY_MEMORY_AVAILABLE,
            GUPPY_VOICE_AVAILABLE=GUPPY_VOICE_AVAILABLE,
            GUPPY_DAEMON_AVAILABLE=GUPPY_DAEMON_AVAILABLE,
            _VOICE_TTS_BACKEND=_VOICE_TTS_BACKEND,
            _VOICE_STT_BACKEND=_VOICE_STT_BACKEND,
            _VOICE_BACKEND_DETAILS=_VOICE_BACKEND_DETAILS,
            _read_daemon_runtime_status=_read_daemon_runtime_status,
            _startup_readiness_cached_or_unknown=_startup_readiness_cached_or_unknown,
            _build_local_runtime_status=_build_local_runtime_status,
            _read_resource_envelope_status=_read_resource_envelope_status,
            _startup_readiness_snapshot=_startup_readiness_snapshot,
            _startup_readiness_cache_expired=_startup_readiness_cache_expired,
            _trigger_startup_readiness_refresh=_trigger_startup_readiness_refresh,
        ),
        guppy_core_available=GUPPY_CORE_AVAILABLE,
        status_cache=_status_cache,
        status_cache_ttl_seconds=STATUS_CACHE_TTL_SECONDS,
        status_include_window_context=STATUS_INCLUDE_WINDOW_CONTEXT,
        guppy_daemon_available=GUPPY_DAEMON_AVAILABLE,
        read_window_context=_read_window_context,
    )


@app.get("/status")
async def get_status(user_id: str = Depends(require_rate_limit)):
    """Get system status and current context."""
    del user_id

    try:
        return await build_status_response(_build_status_support_context())
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        log_session_event("api", "status_failed", level="error", error=str(e))
        return {"status": "error", "message": str(e)}


@app.get("/startup/check")
async def startup_check(deep: bool = False, user_id: str = Depends(require_rate_limit)):
    """Startup readiness checks (cached by default, deep probe when requested)."""
    del user_id
    snapshot = await build_startup_check_response(_build_status_support_context(), deep=deep)
    log_session_event("api", "startup_check", level="info", overall=snapshot.get("overall", "unknown"))
    return snapshot


@app.get("/instances")
async def list_instances(user_id: str = Depends(require_rate_limit)):
    """Contract-first M2 endpoint: list configured instances with lightweight runtime state."""
    del user_id
    return _build_instance_list_response()


@app.post("/instances")
async def create_or_update_instance(
    request: InstanceConfigRequest,
    user_id: str = Depends(require_rate_limit),
):
    del user_id
    return _create_or_update_instance_response(request)


@app.post("/instances/{name}/governance")
async def save_instance_governance(
    name: str,
    request: InstanceGovernanceRequest,
    user_id: str = Depends(require_rate_limit),
):
    del user_id
    return _save_instance_governance_response(name, request)


@app.get("/connectors")
async def list_connectors(user_id: str = Depends(require_rate_limit)):
    del user_id
    return _list_connectors_response()


@app.post("/connectors/{connector_id}/verify")
async def verify_connector(
    connector_id: str,
    request: ConnectorActionRequest,
    user_id: str = Depends(require_rate_limit),
):
    del user_id
    return _run_connector_action_response(connector_id, "verify", request)


@app.post("/connectors/{connector_id}/connect")
async def connect_connector(
    connector_id: str,
    request: ConnectorActionRequest,
    user_id: str = Depends(require_rate_limit),
):
    del user_id
    return _run_connector_action_response(connector_id, "connect", request)


@app.post("/connectors/{connector_id}/reconnect")
async def reconnect_connector(
    connector_id: str,
    request: ConnectorActionRequest,
    user_id: str = Depends(require_rate_limit),
):
    del user_id
    return _run_connector_action_response(connector_id, "reconnect", request)


@app.post("/connectors/{connector_id}/disconnect")
async def disconnect_connector(
    connector_id: str,
    request: ConnectorActionRequest,
    user_id: str = Depends(require_rate_limit),
):
    del user_id
    return _run_connector_action_response(connector_id, "disconnect", request)


@app.get("/instances/{name}/connectors")
async def list_instance_connectors(
    name: str,
    user_id: str = Depends(require_rate_limit),
):
    del user_id
    return _list_instance_connectors_response(name)


@app.post("/instances/{name}/connectors/{connector_id}")
async def save_instance_connector_binding(
    name: str,
    connector_id: str,
    request: InstanceConnectorBindingRequest,
    user_id: str = Depends(require_rate_limit),
):
    del user_id
    return _save_instance_connector_binding_response(name, connector_id, request)


@app.post("/instances/{name}/activate")
async def activate_instance(
    name: str,
    user_id: str = Depends(require_rate_limit),
):
    del user_id
    return _activate_instance_response(name)


@app.delete("/instances/{name}")
async def delete_instance(
    name: str,
    user_id: str = Depends(require_rate_limit),
):
    del user_id
    return _delete_instance_response(name)

# === END _server_fragment_runtime_calls.py ===

# === BEGIN _server_fragment_routes_core.py ===
@app.get("/instances/{name}/logs")
async def get_instance_logs(
    name: str,
    limit: int = 50,
    user_id: str = Depends(require_rate_limit),
):
    del user_id
    return _build_instance_logs_response(name, limit=limit)


@app.post("/instances/{name}/query")
async def query_instance(
    name: str,
    request: InstanceQueryRequest,
    user_id: str = Depends(require_rate_limit),
):
    del user_id
    return await snapshot_route_support.query_instance_response(_module_owner(), name, request)


@app.get("/logs/recent")
async def get_recent_logs(
    limit: int = 100,
    user_id: str = Depends(require_rate_limit),
):
    del user_id
    return snapshot_route_support.recent_logs_response(_module_owner(), limit=limit)


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
    return snapshot_telemetry_support.build_telemetry_query_response(
        _module_owner(),
        stream=stream,
        event=event,
        level=level,
        since_minutes=since_minutes,
        limit=limit,
        backend=backend,
    )


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
    return snapshot_telemetry_support.build_telemetry_report_response(
        _module_owner(),
        stream=stream,
        since_minutes=since_minutes,
        limit=limit,
        backend=backend,
    )


def _require_repair_token(request: Request) -> None:
    """Dependency: verify X-Repair-Token matches the in-memory token set at startup."""
    services_ops.require_repair_token(_module_owner(), request)


@app.get("/repair-token/refresh")
async def repair_token_refresh(_req: Request):
    client_ip = _req.client.host if _req.client else ""
    return snapshot_route_support.repair_token_refresh_response(_module_owner(), client_ip)


@app.post("/repair")
async def repair_runtime(
    request: RepairRequest,
    _req: Request,
    user_id: str = Depends(require_rate_limit),
    _tok: None = Depends(_require_repair_token),
):
    del user_id
    return await snapshot_route_support.repair_runtime_response(_module_owner(), request)


@app.get("/revenue/dashboard")
async def get_revenue_dashboard(user_id: str = Depends(require_rate_limit)):
    del user_id
    return snapshot_route_support.revenue_dashboard_response(_module_owner())

@app.post("/chat")
async def chat(request: ChatRequest, user_id: str = Depends(require_rate_limit)):
    """Send text message and get response."""
    del user_id

    if not GUPPY_CORE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Guppy core not available")

    idempotency_key = str(request.idempotency_key or "").strip()
    request_fingerprint = build_chat_request_fingerprint(
        message=request.message,
        session_id=request.session_id,
        mode=request.mode,
        persona=request.persona,
        history=request.history,
    ) if idempotency_key else ""
    idempotency_owner = False
    if idempotency_key:
        while True:
            idempotency_owner, idempotency_event = register_chat_idempotency_key(idempotency_key, request_fingerprint)
            if idempotency_owner:
                break
            await _run_blocking(
                idempotency_event.wait,
                timeout_seconds=max(CHAT_TIMEOUT_SECONDS, 120.0),
            )
            idempotent_result = resolve_chat_idempotency_key(idempotency_key, request_fingerprint)
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
            idempotency_owner, idempotency_event, took_ownership = takeover_chat_idempotency_key(
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
                complete_chat_idempotency_key(idempotency_key, response=payload, status_code=200)
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
                            complete_chat_idempotency_key(idempotency_key, response=payload, status_code=200)
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
            complete_chat_idempotency_key(idempotency_key, response=payload, status_code=200)
        return payload

    except HTTPException as exc:
        if idempotency_owner and idempotency_key:
            complete_chat_idempotency_key(
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
            complete_chat_idempotency_key(idempotency_key, error=str(e), status_code=500)
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
