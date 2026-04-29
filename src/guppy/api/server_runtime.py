"""Explicit FastAPI server module.

Readiness and status routes now live in first-class imported modules backed by
`ServerContext`, while the remaining legacy helpers are still being peeled away
from the former fragment-stitched implementation.
"""

# === BEGIN _server_fragment_bootstrap.py ===
"""
guppy_api.py - FastAPI server for remote Guppy access
======================================================

Provides REST API and WebSocket endpoints for browser and mobile access to Guppy.
Includes Turnstile authentication and JWT session management.

Endpoints:
- POST /chat - Send text message, get response
- POST /chat/voice - Upload audio, get transcription + response
- GET /status - Health check + current context
- WebSocket /ws - Streaming responses

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
import sys
import tempfile
import time
import asyncio
import threading
from datetime import datetime, timezone
from functools import partial
from typing import Optional, AsyncGenerator, Any, Dict, List
from pathlib import Path
from collections import Counter

from fastapi import HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect, Depends
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
_import_warnings: list[str] = []

try:
    import guppy_core as core
    GUPPY_CORE_AVAILABLE = True
except ImportError as e:
    _import_warnings.append(f"guppy_core: {e}")
    GUPPY_CORE_AVAILABLE = False
    core = None

try:
    from src.guppy.voice import voice
    GUPPY_VOICE_AVAILABLE = True
except Exception as e:
    _import_warnings.append(f"voice: {e}")
    GUPPY_VOICE_AVAILABLE = False
    voice = None

try:
    from src.guppy.memory import memory
    GUPPY_MEMORY_AVAILABLE = True
except ImportError as e:
    _import_warnings.append(f"memory: {e}")
    GUPPY_MEMORY_AVAILABLE = False
    memory = None

try:
    from src.guppy.daemon.daemon import get_daemon_manager
    GUPPY_DAEMON_AVAILABLE = True
except ImportError as e:
    _import_warnings.append(f"daemon: {e}")
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
    from src.guppy.inference.router import get_router
    INFERENCE_ROUTER_AVAILABLE = True
except ImportError as e:
    _import_warnings.append(f"inference_router: {e}")
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

if _import_warnings:
    logger.warning(
        "Server started with %d optional subsystem(s) unavailable: %s",
        len(_import_warnings),
        "; ".join(_import_warnings),
    )

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
from src.guppy.api.routes_core import build_core_router
from src.guppy.api.routes_instances import build_instances_router
from src.guppy.api.routes_models import build_models_router
from src.guppy.api.routes_ops import build_ops_router
from src.guppy.api.routes_providers import build_providers_router
from src.guppy.api.routes_realtime import build_realtime_router
from src.guppy.api.routes_workspaces import build_workspaces_router
from src.guppy.api.routes_chat_history import build_chat_history_router
from src.guppy.api.routes_settings import build_settings_router
from src.guppy.api.routes_tools import build_tools_router
from src.guppy.api.routes_agents import build_agents_router
from src.guppy.api.routes_inference_metrics import build_inference_metrics_router
from src.guppy.api.routes_launcher import build_launcher_router
from src.guppy.api.routes_provider_management import build_provider_management_router
from src.guppy.api.routes_queue import build_queue_router
from src.guppy.api.routes_pipeline import build_pipeline_router
from src.guppy.api.routes_backends import build_backends_router
from src.guppy.api.routes_voice import build_voice_router
from src.guppy.api.runtime_state import ServerRuntimeState
from src.guppy.api.server_paths import ServerPathConfig
from src.guppy.api.server_runtime_startup_support import (
    bind_startup_support,
    build_lifespan,
)
from src.guppy.api.server_runtime_auth_request_support import bind_auth_request_support
from src.guppy.api.server_runtime_shell_support import (
    build_server_shell,
    detect_voice_backends,
)
from src.guppy.api.server_runtime_bindings import (
    bind_owner,
    bind_owner_async,
    build_owner_binding_alias_map,
    call_module_attr,
    module_owner,
)
from src.guppy.api import server_runtime_path_support
from src.guppy.api import (
    services_briefing,
    services_host,
    services_instances,
    services_ops,
    services_realtime,
    services_runtime,
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
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
]
_configured_origins = os.environ.get("GUPPY_ALLOWED_ORIGINS", "").strip()
_parsed_origins = [o.strip() for o in _configured_origins.split(",") if o.strip()] if _configured_origins else []

if _parsed_origins:
    ALLOWED_ORIGINS = _parsed_origins
elif DEV_MODE:
    ALLOWED_ORIGINS = ["*"]
else:
    ALLOWED_ORIGINS = _default_origins

_path_config = ServerPathConfig.from_roots(CONFIG_DIR, RUNTIME_DIR)
_runtime_dir = _path_config.runtime_dir
_config_dir = _path_config.config_dir
_instances_path = _path_config.instances_path
_connector_bindings_path = _path_config.connector_bindings_path
_instance_state_path = _path_config.instance_state_path
_REPAIR_TOKEN_FILE = _path_config.repair_token_file
_REPAIR_TOKEN: str = ""  # set once in lifespan; read by _require_repair_token
_ops_telemetry_db = _path_config.ops_telemetry_db
_SQLITE_TIMEOUT_SECONDS = float(os.environ.get("GUPPY_SQLITE_TIMEOUT_SECONDS", "10.0"))
_SQLITE_BUSY_TIMEOUT_MS = int(os.environ.get("GUPPY_SQLITE_BUSY_TIMEOUT_MS", "5000"))
_stream_jsonl_map = dict(_path_config.stream_jsonl_map)
_INTEGRATION_HEARTBEAT_SECONDS = float(os.environ.get("GUPPY_INTEGRATION_HEARTBEAT_SECONDS", "900"))
_instance_query_lock = threading.Lock()
_runtime_state = ServerRuntimeState(started_at=datetime.now(timezone.utc).isoformat())
_status_cache = _runtime_state.status_cache
_startup_check_cache = _runtime_state.startup_check_cache
_startup_check_cache_lock = _runtime_state.startup_check_cache_lock

_voice_backends = detect_voice_backends(
    environ=os.environ,
    find_spec=importlib.util.find_spec,
)
_VOICE_TTS_BACKEND = _voice_backends.tts_backend
_VOICE_STT_BACKEND = _voice_backends.stt_backend
_VOICE_BACKEND_DETAILS = _voice_backends.details

_api_metrics_lock = _runtime_state.api_metrics_lock
_api_metrics = _runtime_state.api_metrics

_module_owner = partial(module_owner, __name__)
_call_module_attr = partial(call_module_attr, __name__)
_bind_owner = partial(bind_owner, __name__)
_bind_owner_async = partial(bind_owner_async, __name__)
_apply_path_config = _bind_owner(server_runtime_path_support.apply_path_config)
_set_path_config_for_tests = _bind_owner(server_runtime_path_support.set_path_config_for_tests)
globals().update(
    build_owner_binding_alias_map(
        bind_owner=_bind_owner,
        bind_owner_async=_bind_owner_async,
        services_realtime_module=services_realtime,
        services_ops_module=services_ops,
        services_instances_module=services_instances,
        services_host_module=services_host,
        services_briefing_module=services_briefing,
        services_runtime_module=services_runtime,
    )
)

_startup_support = bind_startup_support(
    bind_owner=_bind_owner,
    services_host_module=services_host,
    services_runtime_module=services_runtime,
)
_auth_request_support = bind_auth_request_support(
    bind_owner=_bind_owner,
    module_owner=_module_owner,
    services_host_module=services_host,
    services_ops_module=services_ops,
    require_rate_limit=require_rate_limit,
    require_auth_rate_limit=require_auth_rate_limit,
    verify_turnstile_token_auth=verify_turnstile_token_auth,
    create_access_token=create_access_token,
    access_token_expire_minutes=ACCESS_TOKEN_EXPIRE_MINUTES,
)
_read_repair_token = _startup_support.read_repair_token
_restart_managed_daemon = _startup_support.restart_managed_daemon
_set_repair_token = _startup_support.set_repair_token
_secret_ready = _startup_support.secret_ready
_build_startup_readiness_payload = _startup_support.build_startup_readiness_payload
_startup_readiness_snapshot = _startup_support.startup_readiness_snapshot
_startup_readiness_cached_or_unknown = _startup_support.startup_readiness_cached_or_unknown
_startup_readiness_cached_or_snapshot = _startup_support.startup_readiness_cached_or_snapshot
_startup_readiness_cache_expired = _startup_support.startup_readiness_cache_expired
_trigger_startup_readiness_refresh = _startup_support.trigger_startup_readiness_refresh
_require_repair_token = _auth_request_support.require_repair_token

lifespan = build_lifespan(
    module_owner=_module_owner,
    validate_environment=validate_environment,
    ensure_instance_scaffold=_ensure_m2_instance_scaffold,
    startup_host=services_host.startup_host,
    shutdown_host=services_host.shutdown_host,
)

_server_shell = build_server_shell(
    owner=sys.modules[__name__],
    allowed_origins=ALLOWED_ORIGINS,
    lifespan=lifespan,
    auth_request_support=_auth_request_support,
    voice_probe=_voice_backends,
)
app = _server_shell.app

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
_local_runtime_warm_cache = _runtime_state.local_runtime_warm_cache
_local_runtime_warm_lock = _runtime_state.local_runtime_warm_lock

_server_context = _server_shell.server_context

app.include_router(build_core_router(_server_context))

_server_context.require_repair_token = _require_repair_token
_instances_router = build_instances_router(_server_context)
app.include_router(_instances_router)               # /instances/...
app.include_router(_instances_router, prefix="/api") # /api/instances/... (web UI prefix)

app.include_router(build_models_router(_server_context))
app.include_router(build_providers_router(_server_context))
app.include_router(build_workspaces_router(_server_context))
app.include_router(build_chat_history_router(_server_context))
app.include_router(build_settings_router(_server_context))
_tools_router = build_tools_router(_server_context)
app.include_router(_tools_router)               # /tools
app.include_router(_tools_router, prefix="/api") # /api/tools (web UI prefix)
app.include_router(build_ops_router(_server_context))

_realtime_router = build_realtime_router(_server_context)
app.include_router(_realtime_router)               # /chat
app.include_router(_realtime_router, prefix="/api") # /api/chat (web UI prefix)

app.include_router(build_agents_router(_server_context))            # /api/agents
app.include_router(build_inference_metrics_router(_server_context)) # /api/inference/metrics
app.include_router(build_launcher_router(_server_context))          # /api/launcher
app.include_router(build_provider_management_router(_server_context)) # /api/providers/health|config
app.include_router(build_queue_router(_server_context))             # /api/queue
app.include_router(build_pipeline_router(_server_context))          # /api/pipeline
app.include_router(build_backends_router(_server_context))          # /api/backends/llamacpp
app.include_router(build_voice_router(_server_context))             # /api/voices

from src.guppy.api.routes_reminders import build_reminders_router
app.include_router(build_reminders_router(_server_context))         # /api/reminders

from src.guppy.api.routes_calibre import build_calibre_router, build_kindle_router
app.include_router(build_calibre_router(_server_context))           # /api/calibre/*
app.include_router(build_kindle_router(_server_context))            # /api/kindle/*

from src.guppy.api.routes_screenpipe import build_screenpipe_router
app.include_router(build_screenpipe_router(_server_context))        # /api/screenpipe/*

from src.guppy.api.routes_acquisition import build_acquisition_router
app.include_router(build_acquisition_router(_server_context))       # /api/acquisition/*

from src.guppy.api.routes_tier3 import build_tier3_router
app.include_router(build_tier3_router(_server_context))             # /api/tier3/*

from src.guppy.api.routes_booklet import build_booklet_router
app.include_router(build_booklet_router(_server_context))           # /api/booklet/*

from src.guppy.api.routes_library import build_library_router
app.include_router(build_library_router(_server_context))           # /api/library/*

from src.guppy.api.routes_files import build_files_router
app.include_router(build_files_router(_server_context))             # /api/files/*, /api/system/*, /api/clipboard

from src.guppy.api.routes_drop import build_drop_router
app.include_router(build_drop_router(_server_context))              # /api/drop/*

from src.guppy.api.routes_surface import build_surface_router
app.include_router(build_surface_router(_server_context))           # /api/surface/*

from src.guppy.api.routes_companion import build_companion_router
app.include_router(build_companion_router(_server_context))         # /api/companion/*

from src.guppy.api.routes_workspace_data import build_workspace_data_router
app.include_router(build_workspace_data_router(_server_context))    # /api/workspace/*

from src.guppy.api.routes_codespace import build_codespace_router
app.include_router(build_codespace_router(_server_context))         # /api/codespace/*

from src.guppy.api.routes_screen_monitor import build_screen_monitor_router
app.include_router(build_screen_monitor_router(_server_context))    # /api/screen/*

from src.guppy.api.routes_voip import build_voip_router
app.include_router(build_voip_router(_server_context))              # /api/voip/*

from src.guppy.api.routes_calendar import build_calendar_router
app.include_router(build_calendar_router(_server_context))          # /api/calendar/*

from src.guppy.api.routes_email import build_email_router
app.include_router(build_email_router(_server_context))             # /api/email/*

from src.guppy.api.routes_media import build_media_router
app.include_router(build_media_router(_server_context))             # /api/media/*

from src.guppy.api.routes_documents import build_documents_router
app.include_router(build_documents_router(_server_context))         # /api/documents/*

# Start background services
try:
    from src.guppy.codespace.codespace_triage import start_watchdog as _start_watchdog
    _start_watchdog()
except Exception as _triage_exc:
    logger.warning("Triage watchdog failed to start: %s", _triage_exc)

try:
    from src.guppy.api.routes_screen_monitor import start_monitor as _start_screen_monitor
    _start_screen_monitor()
except Exception as _screen_exc:
    logger.warning("Screen monitor failed to start: %s", _screen_exc)

# Serve static web UI files
try:
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse, JSONResponse
    from pathlib import Path as PathlibPath
    _static_path = PathlibPath(__file__).parent.parent.parent.parent / "static"
    if _static_path.exists():
        # Serve asset files (JS/CSS/etc.) from /assets/*
        app.mount("/assets", StaticFiles(directory=str(_static_path / "assets")), name="assets")

        # SPA fallback via 404 exception handler — this is safer than a
        # /{full_path:path} catch-all route because it never competes with
        # registered API routes for path matching priority (Starlette 1.x).
        # API 404s keep their JSON shape; only unknown non-API paths get the SPA.
        _spa_index = str(_static_path / "index.html")
        _NON_SPA_PREFIXES = (
            "/api/", "/providers/", "/metrics/", "/status",
            "/logs/", "/telemetry/", "/repair", "/auth/",
        )

        @app.exception_handler(404)
        async def _spa_404(request: Any, exc: Any):
            path = request.url.path
            if any(path.startswith(p) for p in _NON_SPA_PREFIXES):
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            return FileResponse(_spa_index)

except Exception as e:
    logger.warning(f"Could not mount static files: {e}")
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
