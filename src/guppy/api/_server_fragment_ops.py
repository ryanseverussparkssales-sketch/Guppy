from src.guppy.api import _server_fragment_ops_briefing_support as _briefing_support
from src.guppy.api.server_runtime_bindings import bind_owner as _bind_fragment_owner_factory


_bind_fragment_owner = partial(_bind_fragment_owner_factory, __name__)


def _latest_stress_report_path() -> Path | None:
    reports = sorted(_runtime_dir.glob("stress_report_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return reports[0] if reports else None


_normalize_brief_text = _briefing_support.normalize_brief_text
_looks_like_brief_affirmation = _briefing_support.looks_like_brief_affirmation
_history_offered_morning_brief = _briefing_support.history_offered_morning_brief
_request_is_morning_brief = _briefing_support.request_is_morning_brief
_latest_daily_report_path = _bind_fragment_owner(_briefing_support.latest_daily_report_path)
_strip_markdown_prefix = _briefing_support.strip_markdown_prefix
_parse_markdown_sections = _briefing_support.parse_markdown_sections
_preview_markdown_section = _briefing_support.preview_markdown_section
_preview_plain_block = _briefing_support.preview_plain_block
_build_morning_brief_response = _bind_fragment_owner(_briefing_support.build_morning_brief_response)


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
    local_model = str(local_runtime.get("chat_model") or local_runtime.get("model") or "").strip()
    states = [auth_state, voice_state, daemon_state, memory_state, local_runtime_state]
    overall = "READY" if all(s == "READY" for s in states) else ("PARTIAL" if any(s in {"READY", "PARTIAL"} for s in states) else "MISSING")

    return {
        "overall": overall,
        "checks": {
            "auth": {"state": auth_state, "detail": auth_detail, "dev_mode": bool(DEV_MODE), "jwt_ready": jwt_ready, "turnstile_ready": turnstile_ready},
            "ollama": {"state": local_runtime_state, "detail": "legacy alias; see local_runtime", "model": local_model},
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
            "ollama": {"state": "UNKNOWN", "detail": "legacy alias; see local_runtime", "model": ""},
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
