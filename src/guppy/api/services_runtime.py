from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from typing import Any

from src.guppy.api.services_runtime_local import (
    build_local_runtime_status,
    call_lemonade_chat,
    call_selected_local_runtime,
    current_local_runtime_chat_model,
    fetch_lemonade_model_ids,
    local_runtime_base_url,
    local_runtime_role_models,
    local_runtime_warm_cached_or_unknown,
    refresh_local_runtime_warm_status,
    resolve_local_runtime_model,
    selected_local_runtime_backend,
    trigger_local_runtime_warm_refresh,
    warm_ollama_chat_lane,
)


def secret_ready(value: str) -> bool:
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


def _is_ready_state(state: str) -> bool:
    return str(state or "").strip().upper() in {"READY", "OPTIONAL", "SKIPPED"}


def _aggregate_required_states(states: list[str]) -> str:
    normalized = [str(state or "").strip().upper() for state in states if str(state or "").strip()]
    if not normalized or any(state in {"UNKNOWN"} for state in normalized):
        return "UNKNOWN"
    if any(state == "MISSING" for state in normalized):
        return "MISSING"
    if any(state == "PARTIAL" for state in normalized):
        return "PARTIAL"
    if all(_is_ready_state(state) for state in normalized):
        return "READY"
    return "PARTIAL"


def _runtime_health_label(overall: str) -> str:
    normalized = str(overall or "").strip().upper()
    if normalized == "READY":
        return "healthy"
    if normalized in {"PARTIAL", "UNKNOWN"}:
        return "degraded"
    return "error"


def build_startup_readiness_payload(owner: Any) -> dict:
    jwt_ready = secret_ready(owner.os.environ.get("GUPPY_JWT_SECRET", ""))
    turnstile_ready = secret_ready(owner.os.environ.get("TURNSTILE_SECRET", ""))
    selected_backend = owner._selected_local_runtime_backend()
    local_runtime = owner._build_local_runtime_status()
    local_runtime_ready_for_chat = bool(local_runtime.get("chat_ready", False))

    auth_state = "READY" if (owner.DEV_MODE or (jwt_ready and turnstile_ready)) else "MISSING"
    if owner.DEV_MODE:
        auth_detail = "development mode enabled; strict auth checks bypassed"
    elif auth_state == "READY":
        auth_detail = "strict auth secrets configured"
    else:
        auth_detail = "missing one or more strict auth secrets"

    ollama_state = "SKIPPED" if selected_backend != "ollama" else "MISSING"
    ollama_detail = (
        f"Ollama check skipped because {selected_backend} is the selected local runtime"
        if selected_backend != "ollama"
        else "Guppy core unavailable"
    )
    ollama_model = (owner.os.environ.get("OLLAMA_MODEL", "guppy") or "guppy").strip()
    if selected_backend == "ollama" and owner.GUPPY_CORE_AVAILABLE:
        try:
            ok, err = owner.core.check_ollama(ollama_model)
            ollama_state = "READY" if ok else "MISSING"
            ollama_detail = "model reachable" if ok else err
        except Exception as exc:
            ollama_state = "MISSING"
            ollama_detail = str(exc)

    voice_state = "OPTIONAL"
    voice_detail = "voice features are optional and no voice runtime is configured"
    voice_status = {
        "tts_backend": "unknown",
        "stt_backend": "unknown",
        "wake_backend": "idle",
    }
    if owner.GUPPY_VOICE_AVAILABLE:
        voice_status = {
            "tts_backend": str(owner._VOICE_TTS_BACKEND or "unknown"),
            "stt_backend": str(owner._VOICE_STT_BACKEND or "unknown"),
            "wake_backend": "idle",
        }
        voice_backends = {voice_status["tts_backend"].lower(), voice_status["stt_backend"].lower()}
        ready_backends = {backend for backend in voice_backends if backend not in {"", "none", "unknown"}}
        voice_state = "READY" if len(ready_backends) >= 2 else "PARTIAL" if ready_backends else "OPTIONAL"
        voice_detail = (
            "voice backends configured"
            if voice_state == "READY"
            else "voice module available but one or more voice backends still need setup"
        )

    daemon_status = owner._read_daemon_runtime_status()
    daemon_state = str(daemon_status.get("state", "UNKNOWN") or "UNKNOWN")
    daemon_detail = str(daemon_status.get("detail", "") or "daemon runtime unavailable")

    memory_state = "READY" if owner.GUPPY_MEMORY_AVAILABLE else "OPTIONAL"
    memory_detail = (
        "memory module available"
        if owner.GUPPY_MEMORY_AVAILABLE
        else "memory module unavailable; launcher can still run without memory support"
    )

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
    overall = _aggregate_required_states([auth_state, daemon_state, local_runtime_state])

    return {
        "overall": overall,
        "checks": {
            "auth": {
                "state": auth_state,
                "detail": auth_detail,
                "dev_mode": bool(owner.DEV_MODE),
                "jwt_ready": jwt_ready,
                "turnstile_ready": turnstile_ready,
            },
            "ollama": {
                "state": ollama_state,
                "detail": ollama_detail,
                "model": ollama_model,
            },
            "local_runtime": local_runtime,
            "voice": {"state": voice_state, "detail": voice_detail, **voice_status},
            "daemon": {
                "state": daemon_state,
                "detail": daemon_detail,
                "available": bool(daemon_status.get("available", False)),
                "owns_daemon": bool(daemon_status.get("owns_daemon", False)),
                "running": bool(daemon_status.get("running", False)),
            },
            "memory": {"state": memory_state, "detail": memory_detail},
        },
    }


def build_runtime_status_payload(
    owner: Any,
    *,
    context: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    voice_tts = owner._VOICE_TTS_BACKEND if owner.GUPPY_VOICE_AVAILABLE else "none"
    voice_stt = owner._VOICE_STT_BACKEND if owner.GUPPY_VOICE_AVAILABLE else "none"
    voice_status = {
        "available": owner.GUPPY_VOICE_AVAILABLE,
        "tts_backend": voice_tts,
        "stt_backend": voice_stt,
        "details": owner._VOICE_BACKEND_DETAILS if owner.GUPPY_VOICE_AVAILABLE else [],
    }
    startup_readiness = owner._startup_readiness_cached_or_unknown()
    startup_overall = str(startup_readiness.get("overall", "UNKNOWN") or "UNKNOWN").strip().upper()
    local_runtime = owner._build_local_runtime_status()
    overall = startup_overall if startup_overall != "UNKNOWN" else str(local_runtime.get("state", "UNKNOWN") or "UNKNOWN").strip().upper()
    payload = {
        "status": _runtime_health_label(overall),
        "timestamp": str(timestamp or datetime.now(timezone.utc).isoformat()),
        "context": dict(context or {}),
        "memory_available": owner.GUPPY_MEMORY_AVAILABLE,
        "voice_available": owner.GUPPY_VOICE_AVAILABLE,
        "voice_tts_backend": voice_tts,
        "voice_stt_backend": voice_stt,
        "voice_status": voice_status,
        "daemon_available": owner.GUPPY_DAEMON_AVAILABLE,
        "daemon_runtime": owner._read_daemon_runtime_status(),
        "startup_readiness": startup_readiness,
        "local_runtime": local_runtime,
        "resource_envelope": owner._read_resource_envelope_status(),
    }
    return payload


def startup_readiness_snapshot(owner: Any) -> dict:
    state = owner._runtime_state
    with state.startup_check_cache_lock:
        now = time.time()
        if (
            state.startup_check_cache["payload"] is not None
            and state.startup_check_cache["expires_at"] > now
        ):
            return state.startup_check_cache["payload"]

    payload = owner._build_startup_readiness_payload()

    now = time.time()
    state = owner._runtime_state
    with state.startup_check_cache_lock:
        state.startup_check_cache["payload"] = payload
        state.startup_check_cache["expires_at"] = now + owner.STARTUP_CHECK_TTL_SECONDS
        return payload


def startup_readiness_cached_or_unknown(owner: Any) -> dict:
    state = owner._runtime_state
    with state.startup_check_cache_lock:
        payload = state.startup_check_cache.get("payload")
        if payload is not None:
            return payload
    backend = owner._selected_local_runtime_backend()
    return {
        "overall": "UNKNOWN",
        "checks": {
            "auth": {"state": "UNKNOWN", "detail": "startup checks not run yet"},
            "ollama": {
                "state": "UNKNOWN",
                "detail": "startup checks not run yet",
                "model": (owner.os.environ.get("OLLAMA_MODEL", "guppy") or "guppy").strip(),
            },
            "local_runtime": {
                "state": "UNKNOWN",
                "detail": "startup checks not run yet",
                "backend": backend,
                "chat_ready": False,
                "chat_state": "UNKNOWN",
                "chat_detail": "local runtime warmup not checked yet",
                "chat_model": owner._current_local_runtime_chat_model(backend),
            },
            "voice": {
                "state": "UNKNOWN",
                "detail": "startup checks not run yet",
                "tts_backend": "unknown",
                "stt_backend": "unknown",
                "wake_backend": "unknown",
            },
            "daemon": {"state": "UNKNOWN", "detail": "startup checks not run yet"},
            "memory": {"state": "UNKNOWN", "detail": "startup checks not run yet"},
        },
    }


def startup_check_payload(owner: Any, *, deep: bool = False) -> dict[str, Any]:
    if deep:
        return owner._startup_readiness_snapshot()
    snapshot = owner._startup_readiness_cached_or_unknown()
    if snapshot.get("overall") == "UNKNOWN" or owner._startup_readiness_cache_expired():
        owner._trigger_startup_readiness_refresh()
    return snapshot


def startup_readiness_cached_or_snapshot(owner: Any) -> dict:
    state = owner._runtime_state
    with state.startup_check_cache_lock:
        payload = state.startup_check_cache.get("payload")
        if payload is not None:
            return payload
    return owner._startup_readiness_snapshot()


def startup_readiness_cache_expired(owner: Any) -> bool:
    state = owner._runtime_state
    with state.startup_check_cache_lock:
        return state.startup_check_cache.get("expires_at", 0.0) <= time.time()


def trigger_startup_readiness_refresh(owner: Any) -> None:
    state = owner._runtime_state
    with state.startup_check_cache_lock:
        if state.startup_check_refresh_inflight:
            return
        state.startup_check_refresh_inflight = True

    def _worker() -> None:
        try:
            owner._startup_readiness_snapshot()
        except Exception:
            pass
        finally:
            state = owner._runtime_state
            with state.startup_check_cache_lock:
                state.startup_check_refresh_inflight = False

    threading.Thread(target=_worker, daemon=True).start()
