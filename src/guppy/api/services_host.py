from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any


def emit_integration_heartbeat(owner: Any, reason: str) -> None:
    state = owner._runtime_state
    now = time.time()
    with state.integration_heartbeat_lock:
        if now - state.last_integration_heartbeat_ts < max(60.0, owner._INTEGRATION_HEARTBEAT_SECONDS):
            return
        state.last_integration_heartbeat_ts = now

    path = owner._path_config.stream_jsonl_map["integration_events"]
    ts = owner.datetime.now(owner.timezone.utc).isoformat()
    record = {
        "timestamp": ts,
        "ts": ts,
        "event_type": "integration_heartbeat",
        "event": "integration_heartbeat",
        "level": "info",
        "payload": {"state": "idle", "reason": reason},
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        owner.rotate_jsonl_file(path)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")
    except Exception:
        return


def _mark_daemon_runtime(
    owner: Any,
    *,
    state: str,
    detail: str,
    running: bool | None = None,
) -> dict[str, Any]:
    payload = {
        "state": str(state or "UNKNOWN").upper(),
        "detail": str(detail or "").strip() or "daemon runtime state unavailable",
        "available": bool(owner.GUPPY_DAEMON_AVAILABLE),
        "owns_daemon": bool(owner.API_OWNS_DAEMON),
        "running": bool(running) if running is not None else False,
        "last_changed_at": owner.datetime.now(owner.timezone.utc).isoformat(),
    }
    owner._runtime_state.daemon_runtime = payload
    return dict(payload)


def read_daemon_runtime_status(owner: Any) -> dict[str, Any]:
    state = owner._runtime_state
    payload = dict(getattr(state, "daemon_runtime", {}) or {})
    if payload:
        payload.setdefault("available", bool(owner.GUPPY_DAEMON_AVAILABLE))
        payload.setdefault("owns_daemon", bool(owner.API_OWNS_DAEMON))
        payload.setdefault("running", False)
        payload.setdefault("state", "UNKNOWN")
        payload.setdefault("detail", "daemon runtime state unavailable")
        return payload
    return _mark_daemon_runtime(
        owner,
        state="READY" if owner.GUPPY_DAEMON_AVAILABLE else "MISSING",
        detail="daemon module available" if owner.GUPPY_DAEMON_AVAILABLE else "daemon module unavailable",
        running=False,
    )


def get_managed_daemon(owner: Any) -> Any | None:
    if not owner.GUPPY_DAEMON_AVAILABLE:
        _mark_daemon_runtime(owner, state="MISSING", detail="daemon module unavailable", running=False)
        return None
    try:
        daemon = owner.get_daemon_manager()
    except Exception as exc:
        _mark_daemon_runtime(owner, state="ERROR", detail=f"daemon manager failed: {exc}", running=False)
        raise
    if daemon is None:
        _mark_daemon_runtime(owner, state="MISSING", detail="daemon manager unavailable", running=False)
        return None
    running = bool(getattr(daemon, "is_running", False))
    detail = "daemon manager ready"
    if owner.API_OWNS_DAEMON and running:
        detail = "daemon running under API management"
    elif owner.API_OWNS_DAEMON:
        detail = "daemon manager ready but not running"
    _mark_daemon_runtime(owner, state="READY", detail=detail, running=running)
    return daemon


def read_window_context(owner: Any) -> dict[str, Any]:
    if not owner.STATUS_INCLUDE_WINDOW_CONTEXT or not owner.GUPPY_DAEMON_AVAILABLE:
        return {}
    try:
        daemon = get_managed_daemon(owner)
    except Exception:
        return {}
    watcher = getattr(daemon, "window_watcher", None) if daemon is not None else None
    if watcher is None:
        return {}
    try:
        return watcher.get_enhanced_context() or {}
    except Exception:
        return {}


def _set_repair_token(owner: Any, token: str) -> str:
    normalized = str(token or "").strip()
    owner._runtime_state.repair_token = normalized
    owner._REPAIR_TOKEN = normalized
    return normalized


def set_repair_token(owner: Any, token: str) -> str:
    return _set_repair_token(owner, token)


def read_repair_token(owner: Any, *, allow_persistent_fallback: bool = True) -> str:
    state = owner._runtime_state
    token = str(owner._REPAIR_TOKEN or "").strip()
    if token:
        state.repair_token = token
        return token

    token = str(getattr(state, "repair_token", "") or "").strip()
    if token and allow_persistent_fallback:
        owner._REPAIR_TOKEN = token
        return token

    if not allow_persistent_fallback:
        state.repair_token = ""
        return ""

    if owner._SECRET_STORE_AVAILABLE and owner._secret_store is not None:
        try:
            token = str(owner._secret_store.get_secret("repair_token") or "").strip()
        except Exception:
            token = ""
        if token:
            return _set_repair_token(owner, token)

    repair_token_file = owner._path_config.repair_token_file
    if repair_token_file.exists():
        try:
            token = repair_token_file.read_text(encoding="utf-8").strip()
        except Exception:
            token = ""
        if token:
            return _set_repair_token(owner, token)
    return ""


def _initialize_repair_token(owner: Any) -> None:
    owner._path_config.runtime_dir.mkdir(parents=True, exist_ok=True)
    repair_token_file = owner._path_config.repair_token_file
    token = _set_repair_token(owner, owner.secrets.token_hex(32))
    if owner._SECRET_STORE_AVAILABLE and owner._secret_store.set_secret("repair_token", token):
        owner.logger.info("Repair token stored in OS credential store")
        try:
            if repair_token_file.exists():
                repair_token_file.unlink()
        except Exception as exc:
            owner.logger.warning("Could not remove stale repair token fallback file: %s", exc)
    else:
        try:
            repair_token_file.write_text(token, encoding="utf-8")
            try:
                os.chmod(repair_token_file, 0o600)
            except Exception:
                pass
            owner.logger.info("Repair token written to %s", repair_token_file)
        except Exception as exc:
            owner.logger.warning("Could not write repair token: %s", exc)


def restart_managed_daemon(owner: Any, dry_run: bool = False) -> dict[str, Any]:
    try:
        daemon = get_managed_daemon(owner)
    except Exception as exc:
        return {"ok": False, "summary": f"daemon manager failed: {exc}"}
    if daemon is None:
        payload = read_daemon_runtime_status(owner)
        return {"ok": False, "summary": payload.get("detail", "daemon manager unavailable")}
    if dry_run:
        return {
            "ok": True,
            "summary": "dry-run restart: would stop then start daemon manager",
        }
    try:
        if hasattr(daemon, "stop"):
            daemon.stop()
        if hasattr(daemon, "start"):
            daemon.start()
        running = bool(getattr(daemon, "is_running", False))
        _mark_daemon_runtime(
            owner,
            state="READY",
            detail="daemon manager restarted",
            running=running,
        )
        return {"ok": True, "summary": "daemon manager restarted"}
    except Exception as exc:
        _mark_daemon_runtime(
            owner,
            state="ERROR",
            detail=f"daemon restart failed: {exc}",
            running=False,
        )
        return {"ok": False, "summary": f"daemon restart failed: {exc}"}


async def startup_host(owner: Any) -> None:
    _initialize_repair_token(owner)

    if owner._PERSONALIZATION_BOOTSTRAP_AVAILABLE:
        try:
            created = await asyncio.to_thread(owner.ensure_personalization_scaffold)
            personalization_diagnostics = {
                "persona_config.json": (await asyncio.to_thread(owner.load_persona_config_with_diagnostics))[1],
                "provider_registry.json": (await asyncio.to_thread(owner.load_provider_registry_with_diagnostics))[1],
                "voice_bindings.json": (await asyncio.to_thread(owner.load_voice_bindings_with_diagnostics))[1],
            }
            if created:
                owner.logger.info(
                    "Personalization scaffold initialized: %s",
                    ",".join(sorted(created.keys())),
                )
            problems = [
                f"{name}: {messages[0]}"
                for name, messages in personalization_diagnostics.items()
                if messages
            ]
            if problems:
                owner.logger.warning(
                    "Personalization scaffold normalized malformed config: %s",
                    " | ".join(problems),
                )
        except Exception as exc:
            owner.logger.warning("Personalization scaffold initialization failed: %s", exc)

    try:
        await asyncio.to_thread(owner._startup_readiness_snapshot)
    except Exception as exc:
        owner.logger.warning("Startup readiness warmup failed: %s", exc)

    try:
        owner._trigger_local_runtime_warm_refresh(force=True)
    except Exception as exc:
        owner.logger.warning("Local runtime warmup trigger failed: %s", exc)

    owner._emit_integration_heartbeat("api_startup")

    if owner.API_OWNS_DAEMON and owner.GUPPY_DAEMON_AVAILABLE:
        try:
            daemon = get_managed_daemon(owner)
            if daemon is None:
                owner.logger.warning("API will run in limited mode without daemon context")
                return
            if hasattr(daemon, "is_running") and daemon.is_running:
                _mark_daemon_runtime(
                    owner,
                    state="READY",
                    detail="daemon already running",
                    running=True,
                )
                owner.logger.info("Guppy daemon already running - using existing instance")
            else:
                daemon.start()
                _mark_daemon_runtime(
                    owner,
                    state="READY",
                    detail="daemon started by API host",
                    running=bool(getattr(daemon, "is_running", True)),
                )
                owner.logger.info("Guppy daemon started")
        except Exception as exc:
            _mark_daemon_runtime(owner, state="ERROR", detail=f"daemon startup failed: {exc}", running=False)
            owner.logger.error("Failed to initialize daemon: %s", exc)
            owner.logger.warning("API will run in limited mode without daemon context")
    elif owner.GUPPY_DAEMON_AVAILABLE:
        _mark_daemon_runtime(
            owner,
            state="READY",
            detail="daemon module available; ownership handled outside API",
            running=False,
        )
        owner.logger.info("API running in supervised mode (daemon ownership disabled)")
    else:
        _mark_daemon_runtime(owner, state="MISSING", detail="daemon module unavailable", running=False)
        owner.logger.warning("Guppy daemon not available - running in API-only mode")


async def shutdown_host(owner: Any) -> None:
    try:
        _set_repair_token(owner, "")
        if owner._SECRET_STORE_AVAILABLE:
            owner._secret_store.delete_secret("repair_token")
        repair_token_file = owner._path_config.repair_token_file
        if repair_token_file.exists():
            repair_token_file.unlink()
    except Exception as exc:
        owner.logger.warning("Failed to remove repair token: %s", exc)

    if owner.API_OWNS_DAEMON and owner.GUPPY_AVAILABLE:
        try:
            daemon = get_managed_daemon(owner)
            if daemon is not None:
                daemon.stop()
                _mark_daemon_runtime(owner, state="READY", detail="daemon stopped by API host", running=False)
                owner.logger.info("Guppy daemon stopped")
        except Exception as exc:
            _mark_daemon_runtime(owner, state="ERROR", detail=f"daemon shutdown failed: {exc}", running=False)
            owner.logger.error("Failed to stop daemon: %s", exc)


def record_request_failure(owner: Any, request: Any, status_code: int, elapsed_ms: float) -> None:
    state = owner._runtime_state
    owner.log_session_event(
        "api",
        "request_failed",
        level="error",
        method=request.method,
        path=request.url.path,
        status_code=status_code,
        elapsed_ms=round(elapsed_ms, 2),
    )
    with state.api_metrics_lock:
        metrics = state.api_metrics
        metrics["requests_total"] += 1
        metrics["errors_total"] += 1
        metrics["latency_total_ms"] += elapsed_ms
        metrics["path_counts"][request.url.path] = metrics["path_counts"].get(request.url.path, 0) + 1
        metrics["status_counts"][str(status_code)] = metrics["status_counts"].get(str(status_code), 0) + 1
        if elapsed_ms >= owner.SLOW_REQUEST_MS:
            metrics["slow_requests"] += 1


def record_request_completion(owner: Any, request: Any, response: Any, elapsed_ms: float) -> None:
    state = owner._runtime_state
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
    with state.api_metrics_lock:
        metrics = state.api_metrics
        metrics["requests_total"] += 1
        metrics["latency_total_ms"] += elapsed_ms
        metrics["path_counts"][request.url.path] = metrics["path_counts"].get(request.url.path, 0) + 1
        metrics["status_counts"][str(response.status_code)] = metrics["status_counts"].get(str(response.status_code), 0) + 1
        if response.status_code >= 500:
            metrics["errors_total"] += 1
        if elapsed_ms >= owner.SLOW_REQUEST_MS:
            metrics["slow_requests"] += 1

    if elapsed_ms >= owner.SLOW_REQUEST_MS:
        owner.logger.warning(
            "Slow request: %s %s -> %s in %.2fms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
    owner._emit_integration_heartbeat("api_request")
    owner.log_session_event(
        "api",
        "request_complete",
        level="warning" if elapsed_ms >= owner.SLOW_REQUEST_MS else "info",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        elapsed_ms=round(elapsed_ms, 2),
    )
