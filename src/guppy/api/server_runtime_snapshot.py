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
    realtime_inference_support,
    services_briefing,
    services_instances,
    services_ops,
    services_realtime,
    services_runtime,
    snapshot_runtime_support,
    snapshot_status_context_support,
    snapshot_realtime_support,
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
from src.guppy.api.snapshot_voice_support import detect_voice_backends as _detect_voice_backends
from src.guppy.api.snapshot_app_bootstrap import (
    configure_app as _configure_snapshot_app,
    create_lifespan as _create_snapshot_lifespan,
)
from src.guppy.api.snapshot_status_routes import register_status_routes as _register_snapshot_status_routes

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

# === END _server_fragment_instances_telemetry.py ===

# === BEGIN _server_fragment_ops.py ===
_request_is_morning_brief = services_briefing.request_is_morning_brief

# â”€â”€ Authentication â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

# Remove duplicate JWT functions - now imported from auth module

# â”€â”€ FastAPI App â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def _module_owner() -> Any:
    return sys.modules[__name__]

lifespan = _create_snapshot_lifespan(_module_owner())
app = _configure_snapshot_app(_module_owner(), lifespan=lifespan)

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


def _bind_runtime_service(func):
    def wrapper(*args, **kwargs):
        return func(_module_owner(), *args, **kwargs)

    return wrapper


_ensure_m2_instance_scaffold = _bind_runtime_service(services_instances.ensure_m2_instance_scaffold)
_load_instances_config = _bind_runtime_service(services_instances.load_instances_config)
_load_instance_state = _bind_runtime_service(services_instances.load_instance_state)
_save_instance_state = _bind_runtime_service(services_instances.save_instance_state)
_save_instances_config = _bind_runtime_service(services_instances.save_instances_config)
_load_normalized_instance_bundle = _bind_runtime_service(services_instances.load_normalized_instance_bundle)
_get_active_instance_context = _bind_runtime_service(services_instances.get_active_instance_context)
_read_resource_envelope_status = partial(
    services_ops.read_resource_envelope_status,
    _module_owner(),
    missing_message="resource envelope status not available",
    unavailable_message="resource envelope status unreadable",
)
_latest_stress_report_path = _bind_runtime_service(services_ops.latest_stress_report_path)
_latest_daily_report_path = _bind_runtime_service(services_briefing.latest_daily_report_path)
_build_morning_brief_response = _bind_runtime_service(services_briefing.build_morning_brief_response)
_collect_runtime_bundle = _bind_runtime_service(services_ops.collect_runtime_bundle)
_do_repair_action = _bind_runtime_service(services_ops.do_repair_action)
_secret_ready = snapshot_runtime_support.secret_ready
_build_startup_readiness_payload = _bind_runtime_service(services_runtime.build_startup_readiness_payload)
_startup_readiness_snapshot = _bind_runtime_service(services_runtime.startup_readiness_snapshot)
_startup_readiness_cached_or_unknown = _bind_runtime_service(services_runtime.startup_readiness_cached_or_unknown)
_startup_readiness_cached_or_snapshot = _bind_runtime_service(services_runtime.startup_readiness_cached_or_snapshot)
_startup_readiness_cache_expired = _bind_runtime_service(services_runtime.startup_readiness_cache_expired)
_trigger_startup_readiness_refresh = _bind_runtime_service(services_runtime.trigger_startup_readiness_refresh)

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
_emit_integration_heartbeat = _bind_runtime_service(snapshot_runtime_support.emit_integration_heartbeat)

# === END _server_fragment_local_runtime.py ===

# === BEGIN _server_fragment_runtime_status.py ===
async def _run_blocking(func, *args, timeout_seconds: float, **kwargs):
    return await services_realtime.run_blocking(
        func,
        *args,
        timeout_seconds=timeout_seconds,
        **kwargs,
    )


_extract_text_from_anthropic_blocks = services_realtime.extract_text_from_anthropic_blocks
_sanitize_chat_history = services_realtime.sanitize_chat_history
_build_router_messages = services_realtime.build_router_messages
_request_is_cacheable = _bind_runtime_service(services_realtime.request_is_cacheable)
_augment_system_with_history = services_realtime.augment_system_with_history
_is_rate_limited_error = services_realtime.is_rate_limited_error
_call_unified_inference = _bind_runtime_service(services_realtime.call_unified_inference)
_call_claude_with_tools = _bind_runtime_service(realtime_inference_support.call_claude_with_tools)

# === END _server_fragment_runtime_status.py ===

# === BEGIN _server_fragment_runtime_calls.py ===
_call_ollama_with_tools = _bind_runtime_service(realtime_inference_support.call_ollama_with_tools)


async def _stream_chunks(text: str) -> AsyncGenerator[str, None]:
    for chunk in text.split():
        yield chunk + " "

# â”€â”€ Routes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "Guppy API is running", "status": "healthy"}


_register_snapshot_status_routes(app, _module_owner())


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
    return await snapshot_realtime_support.chat_response(_module_owner(), request)

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
    return await snapshot_realtime_support.chat_voice_response(
        _module_owner(),
        file=file,
        session_id=session_id,
        use_claude=use_claude,
    )

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for streaming responses."""
    await snapshot_realtime_support.websocket_response(_module_owner(), websocket)

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
