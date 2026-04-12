"""
guppy_api.py — FastAPI server for remote Guppy access
======================================================

Provides REST API and WebSocket endpoints for browser and mobile access to Guppy.
Includes Turnstile authentication and JWT session management.

Endpoints:
- POST /chat — Send text message, get response
- POST /chat/voice — Upload audio, get transcription + response
- GET /status — Health check + current context
- WebSocket /ws — Streaming responses

Security:
- Turnstile validation on write endpoints
- JWT session tokens (24h expiry)
- Rate limiting and request validation
"""

import json
import logging
import os
import tempfile
import time
import asyncio
import threading
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Optional, AsyncGenerator
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from jose import JWTError, jwt
import urllib.request

from utils.env_bootstrap import load_env_file

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
    from guppy_api_auth import (
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


logger = logging.getLogger(__name__)

try:
    from utils.session_logger import log_session_event, tail_session_events
except Exception:
    def log_session_event(*_args, **_kwargs):
        return
    def tail_session_events(limit: int = 50):
        return []

# ── Configuration ──────────────────────────────────────────────────────────────

# JWT settings (now imported from auth module)
from guppy_api_auth import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, DEV_MODE

# Server settings
HOST = "127.0.0.1"
PORT = int(os.environ.get("GUPPY_API_PORT", "8081"))
CHAT_TIMEOUT_SECONDS = float(os.environ.get("GUPPY_CHAT_TIMEOUT_SECONDS", "120"))
VOICE_TIMEOUT_SECONDS = float(os.environ.get("GUPPY_VOICE_TIMEOUT_SECONDS", "180"))
SLOW_REQUEST_MS = int(os.environ.get("GUPPY_SLOW_REQUEST_MS", "1500"))
STATUS_CACHE_TTL_SECONDS = float(os.environ.get("GUPPY_STATUS_CACHE_TTL_SECONDS", "120.0"))
STARTUP_CHECK_TTL_SECONDS = float(os.environ.get("GUPPY_STARTUP_CHECK_TTL_SECONDS", "60.0"))

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

# Detect voice backends once at module load so /status never pays import probe cost
def _detect_voice_backends() -> tuple[str, str, list[str]]:
    tts, stt, details = "sapi", "none", []
    try:
        from kokoro import KPipeline as _KP  # noqa: F401
        tts = "kokoro"
        details.append("kokoro import ok")
    except Exception:
        details.append("kokoro unavailable -> sapi fallback")
    try:
        from faster_whisper import WhisperModel as _WM  # noqa: F401
        stt = "whisper"
        details.append("faster-whisper import ok")
    except Exception:
        try:
            import speech_recognition as _sr  # noqa: F401
            stt = "google"
            details.append("speech_recognition import ok")
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

# ── Pydantic Models ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    use_claude: Optional[bool] = True

class VoiceChatRequest(BaseModel):
    session_id: Optional[str] = None
    use_claude: Optional[bool] = True

class TurnstileToken(BaseModel):
    token: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


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


def _startup_readiness_snapshot() -> dict:
    now = time.time()
    if _startup_check_cache["payload"] is not None and _startup_check_cache["expires_at"] > now:
        return _startup_check_cache["payload"]

    jwt_ready = _secret_ready(os.environ.get("GUPPY_JWT_SECRET", ""))
    turnstile_ready = _secret_ready(os.environ.get("TURNSTILE_SECRET", ""))

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

    states = [auth_state, ollama_state, voice_state, daemon_state, memory_state]
    overall = "READY" if all(s == "READY" for s in states) else ("PARTIAL" if any(s in {"READY", "PARTIAL"} for s in states) else "MISSING")

    payload = {
        "overall": overall,
        "checks": {
            "auth": {"state": auth_state, "detail": auth_detail, "dev_mode": bool(DEV_MODE), "jwt_ready": jwt_ready, "turnstile_ready": turnstile_ready},
            "ollama": {"state": ollama_state, "detail": ollama_detail, "model": ollama_model},
            "voice": {"state": voice_state, "detail": voice_detail, **voice_status},
            "daemon": {"state": daemon_state, "detail": daemon_detail},
            "memory": {"state": memory_state, "detail": memory_detail},
        },
    }
    _startup_check_cache["payload"] = payload
    _startup_check_cache["expires_at"] = now + STARTUP_CHECK_TTL_SECONDS
    return payload

# ── Authentication ─────────────────────────────────────────────────────────────

# Remove duplicate JWT functions - now imported from auth module

# ── FastAPI App ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Manage startup and shutdown for daemon-backed services."""
    validate_environment()

    if GUPPY_DAEMON_AVAILABLE:
        try:
            daemon = get_daemon_manager()
            if hasattr(daemon, "is_running") and daemon.is_running:
                logger.info("Guppy daemon already running - using existing instance")
            else:
                daemon.start()
                logger.info("Guppy daemon started")
        except Exception as e:
            logger.error(f"Failed to initialize daemon: {e}")
            logger.warning("API will run in limited mode without daemon context")
    else:
        logger.warning("Guppy daemon not available - running in API-only mode")

    try:
        yield
    finally:
        if GUPPY_AVAILABLE:
            try:
                daemon = get_daemon_manager()
                daemon.stop()
                logger.info("Guppy daemon stopped")
            except Exception as e:
                logger.error(f"Failed to stop daemon: {e}")


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
    allow_methods=["*"],
    allow_headers=["*"],
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


async def _run_blocking(func, *args, timeout_seconds: float):
    """Run blocking work in a thread with a hard timeout."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(func, *args),
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


def _call_unified_inference(user_text: str, system_prompt: str) -> str:
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
        return _call_claude_with_tools(user_text, system_prompt)
    
    router = get_router()
    
    try:
        # Try unified inference (local first, then cloud)
        response, source, metadata = router.query(
            system_prompt=system_prompt,
            user_text=user_text,
            tools=core.TOOLS,
            prefer_local=True  # Prefer local model
        )
        
        logger.info(f"Inference completed via {source}. Tokens: {metadata.get('usage', {}).get('output_tokens', '?')}")
        return response
    
    except Exception as e:
        logger.error(f"Unified inference failed: {e}. Escalating to Claude Sonnet.")
        # Final fallback to Claude
        return _call_claude_with_tools(user_text, system_prompt)



def _call_claude_with_tools(user_text: str, system_prompt: str) -> str:
    if not ANTHROPIC_AVAILABLE:
        raise RuntimeError("Anthropic SDK is not installed.")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")

    primary_model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6").strip() or "claude-sonnet-4-6"
    backup_model = os.environ.get("ANTHROPIC_BACKUP_MODEL", "claude-haiku-4-5-20251001").strip()
    model_chain = [primary_model] + ([backup_model] if backup_model and backup_model != primary_model else [])

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
            result = core.run_tool(tu.name, tu.input)
            results.append({"type": "tool_result", "tool_use_id": tu.id, "content": str(result)})
        msgs.append({"role": "user", "content": results})

    return final_text or "No response produced."


def _call_ollama_with_tools(user_text: str, system_prompt: str) -> str:
    model = os.environ.get("OLLAMA_MODEL", "guppy").strip() or "guppy"
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
            result = core.run_tool(name, args if isinstance(args, dict) else {})
            all_msgs.append({"role": "tool", "content": str(result)})

    return final_text or "No response produced."


async def _stream_chunks(text: str) -> AsyncGenerator[str, None]:
    for chunk in text.split():
        yield chunk + " "

# ── Routes ────────────────────────────────────────────────────────────────────

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
        if GUPPY_DAEMON_AVAILABLE:
            daemon = get_daemon_manager()
            context = daemon.window_watcher.get_enhanced_context() if daemon else {}

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
            "startup_readiness": await asyncio.to_thread(_startup_readiness_snapshot),
        }
        _status_cache["payload"] = payload
        _status_cache["expires_at"] = now + STATUS_CACHE_TTL_SECONDS
        return payload
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        log_session_event("api", "status_failed", level="error", error=str(e))
        return {"status": "error", "message": str(e)}


@app.get("/startup/check")
async def startup_check(user_id: str = Depends(require_rate_limit)):
    """Explicit startup readiness checks for UI diagnostics and launch gating."""
    del user_id
    snapshot = await asyncio.to_thread(_startup_readiness_snapshot)
    log_session_event("api", "startup_check", level="info", overall=snapshot.get("overall", "unknown"))
    return snapshot


@app.get("/logs/recent")
async def get_recent_logs(
    limit: int = 100,
    user_id: str = Depends(require_rate_limit),
):
    """Return recent structured events for fast review during active sessions."""
    del user_id
    lim = max(1, min(int(limit), 300))
    runtime_dir = Path(__file__).resolve().parent / "runtime"
    return {
        "session_events": tail_session_events(limit=lim),
        "agent_performance": _read_jsonl_tail(runtime_dir / "agent_performance.jsonl", limit=lim),
        "integration_events": _read_jsonl_tail(runtime_dir / "integration_events.jsonl", limit=lim),
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

    try:
        # Get fresh system prompt with context
        system_prompt = core.get_startup_system(
            session_id=request.session_id,
            query_context=request.message
        )

        # Route through priority chain: local (guppy) -> haiku -> sonnet
        response = await _run_blocking(
            _call_unified_inference,
            request.message,
            system_prompt,
            timeout_seconds=CHAT_TIMEOUT_SECONDS,
        )

        # Store in memory if session provided and memory is available
        if request.session_id and GUPPY_MEMORY_AVAILABLE:
            memory.save_message(request.session_id, "user", request.message)
            memory.save_message(request.session_id, "assistant", response)

        return {"response": response, "session_id": request.session_id}

    except HTTPException:
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
        raise HTTPException(status_code=500, detail=str(e))

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
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

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
            system_prompt = core.get_startup_system(
                session_id=session_id,
                query_context=transcription
            )

            # Route through priority chain: local (guppy) -> haiku -> sonnet
            response = await _run_blocking(
                _call_unified_inference,
                transcription,
                system_prompt,
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
                use_claude = data.get("use_claude", True)

                if not message:
                    continue

                if not GUPPY_CORE_AVAILABLE:
                    await websocket.send_json({"error": "Guppy core not available"})
                    continue

                # Get system prompt
                system_prompt = core.get_startup_system(
                    session_id=session_id,
                    query_context=message
                )

                # Stream response — route through priority chain: local (guppy) -> haiku -> sonnet
                text = await _run_blocking(
                    _call_unified_inference,
                    message,
                    system_prompt,
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

# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    api_reload = os.environ.get("GUPPY_API_RELOAD", "").strip().lower() in {"1", "true", "yes", "on"}
    if not api_reload:
        api_reload = DEV_MODE

    uvicorn.run(
        "guppy_api:app",
        host=HOST,
        port=PORT,
        reload=api_reload,
        log_level="info"
    )