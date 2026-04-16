from __future__ import annotations

import json
import threading
import time
import urllib.request
from typing import Any, Optional


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


def build_startup_readiness_payload(owner: Any) -> dict:
    jwt_ready = secret_ready(owner.os.environ.get("GUPPY_JWT_SECRET", ""))
    turnstile_ready = secret_ready(owner.os.environ.get("TURNSTILE_SECRET", ""))
    local_runtime = owner._build_local_runtime_status()
    local_runtime_ready_for_chat = bool(local_runtime.get("chat_ready", False))

    auth_state = "READY" if (owner.DEV_MODE or (jwt_ready and turnstile_ready)) else "MISSING"
    if owner.DEV_MODE:
        auth_detail = "development mode enabled; strict auth checks bypassed"
    elif auth_state == "READY":
        auth_detail = "strict auth secrets configured"
    else:
        auth_detail = "missing one or more strict auth secrets"

    ollama_state = "MISSING"
    ollama_detail = "Guppy core unavailable"
    ollama_model = (owner.os.environ.get("OLLAMA_MODEL", "guppy") or "guppy").strip()
    if owner.GUPPY_CORE_AVAILABLE:
        try:
            ok, err = owner.core.check_ollama(ollama_model)
            ollama_state = "READY" if ok else "MISSING"
            ollama_detail = "model reachable" if ok else err
        except Exception as exc:
            ollama_state = "MISSING"
            ollama_detail = str(exc)

    voice_state = "MISSING"
    voice_detail = "voice module unavailable"
    voice_status = {
        "tts_backend": "unknown",
        "stt_backend": "unknown",
        "wake_backend": "idle",
    }
    if owner.GUPPY_VOICE_AVAILABLE:
        voice_state = "PARTIAL"
        voice_detail = "voice module available (detailed backend status in /status)"

    daemon_status = owner._read_daemon_runtime_status()
    daemon_state = str(daemon_status.get("state", "UNKNOWN") or "UNKNOWN")
    daemon_detail = str(daemon_status.get("detail", "") or "daemon runtime unavailable")

    memory_state = "READY" if owner.GUPPY_MEMORY_AVAILABLE else "MISSING"
    memory_detail = (
        "memory module available"
        if owner.GUPPY_MEMORY_AVAILABLE
        else "memory module unavailable"
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
    states = [
        auth_state,
        ollama_state,
        voice_state,
        daemon_state,
        memory_state,
        local_runtime_state,
    ]
    overall = (
        "READY"
        if all(state == "READY" for state in states)
        else ("PARTIAL" if any(state in {"READY", "PARTIAL"} for state in states) else "MISSING")
    )

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


def selected_local_runtime_backend(owner: Any) -> str:
    backend = str(owner.os.environ.get("GUPPY_LOCAL_RUNTIME_BACKEND", "ollama") or "ollama").strip().lower()
    return backend if backend in {"ollama", "lemonade"} else "ollama"


def local_runtime_base_url(owner: Any, backend: str) -> str:
    normalized = (backend or "ollama").strip().lower()
    if normalized == "lemonade":
        return str(
            owner.os.environ.get("GUPPY_LEMONADE_BASE_URL", owner._DEFAULT_LEMONADE_BASE_URL)
            or owner._DEFAULT_LEMONADE_BASE_URL
        ).strip()
    return "http://127.0.0.1:11434"


def resolve_local_runtime_model(
    owner: Any,
    backend: str,
    role: str,
    *,
    fallback: str = "",
) -> str:
    normalized_backend = (backend or "ollama").strip().lower()
    normalized_role = (role or "").strip().lower()
    if normalized_backend == "lemonade":
        env_name = owner._LEMONADE_ROLE_ENV.get(normalized_role)
        if env_name:
            return str(owner.os.environ.get(env_name, fallback) or fallback).strip()
        return str(fallback or "").strip()

    if owner.INFERENCE_ROUTER_AVAILABLE:
        try:
            router = owner.get_router()
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


def local_runtime_role_models(owner: Any, backend: str) -> dict[str, str]:
    return {
        "fast": resolve_local_runtime_model(owner, backend, "fast", fallback="guppy-fast"),
        "complex": resolve_local_runtime_model(owner, backend, "complex", fallback="guppy"),
        "teach": resolve_local_runtime_model(owner, backend, "teach", fallback="guppy-teach"),
        "code": resolve_local_runtime_model(owner, backend, "code", fallback="guppy-code"),
        "vault": resolve_local_runtime_model(owner, backend, "vault", fallback="vault-scraper"),
    }


def warm_ollama_chat_lane(owner: Any, model: str, keep_alive: str = "20m") -> tuple[bool, str]:
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
    with urllib.request.urlopen(req, timeout=owner._LOCAL_RUNTIME_WARM_TIMEOUT_SECONDS) as resp:
        data = json.loads(resp.read())
    if isinstance(data, dict) and data.get("error"):
        return False, str(data.get("error"))
    return True, f"{normalized_model} warm"


def current_local_runtime_chat_model(owner: Any, backend: str) -> str:
    role_models = owner._local_runtime_role_models(backend)
    return str(role_models.get("complex") or role_models.get("fast") or "").strip()


def refresh_local_runtime_warm_status(owner: Any, force: bool = False) -> dict[str, Any]:
    backend = owner._selected_local_runtime_backend()
    model = owner._current_local_runtime_chat_model(backend)
    now = time.time()
    state = owner._runtime_state
    with state.local_runtime_warm_lock:
        cached = dict(state.local_runtime_warm_cache)
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
            "expires_at": now + max(30.0, owner._LOCAL_RUNTIME_WARM_TTL_SECONDS),
            "chat_ready": True,
            "chat_state": "READY",
            "chat_detail": "Lemonade backend selected; chat lane treated as ready when registry is reachable",
        }
    else:
        ok, detail = warm_ollama_chat_lane(owner, model)
        payload = {
            "backend": backend,
            "model": model,
            "checked_at": now,
            "expires_at": now + max(30.0, owner._LOCAL_RUNTIME_WARM_TTL_SECONDS),
            "chat_ready": bool(ok),
            "chat_state": "READY" if ok else "WARMING",
            "chat_detail": str(detail or ("local runtime warmed" if ok else "local runtime warmup failed")),
        }
    state = owner._runtime_state
    with state.local_runtime_warm_lock:
        state.local_runtime_warm_cache.update(payload)
        return dict(state.local_runtime_warm_cache)


def local_runtime_warm_cached_or_unknown(owner: Any) -> dict[str, Any]:
    backend = owner._selected_local_runtime_backend()
    model = owner._current_local_runtime_chat_model(backend)
    now = time.time()
    state = owner._runtime_state
    with state.local_runtime_warm_lock:
        cached = dict(state.local_runtime_warm_cache)
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


def trigger_local_runtime_warm_refresh(owner: Any, force: bool = False) -> None:
    state = owner._runtime_state
    with state.local_runtime_warm_lock:
        if state.local_runtime_warm_refresh_inflight:
            return
        if not force:
            cached = dict(state.local_runtime_warm_cache)
            now = time.time()
            if float(cached.get("expires_at", 0.0) or 0.0) > now:
                return
        state.local_runtime_warm_refresh_inflight = True

    def _worker() -> None:
        try:
            owner._refresh_local_runtime_warm_status(force=True)
        except Exception:
            pass
        finally:
            state = owner._runtime_state
            with state.local_runtime_warm_lock:
                state.local_runtime_warm_refresh_inflight = False

    threading.Thread(target=_worker, daemon=True).start()


def fetch_lemonade_model_ids(owner: Any, timeout: float = 4.0) -> set[str]:
    req = urllib.request.Request(
        f"{owner._local_runtime_base_url('lemonade').rstrip('/')}/models",
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


def build_local_runtime_status(owner: Any) -> dict[str, Any]:
    backend = owner._selected_local_runtime_backend()
    role_models = owner._local_runtime_role_models(backend)
    active_chat_model = owner._current_local_runtime_chat_model(backend)
    model_ids: set[str] = set()
    detail = ""
    policy: dict[str, Any] = {}
    warm_status = owner._local_runtime_warm_cached_or_unknown()

    try:
        from src.guppy.local_llm.manifest import get_local_llm_policy_summary, load_local_llm_manifest

        policy = get_local_llm_policy_summary(load_local_llm_manifest())
    except Exception:
        policy = {}

    try:
        if backend == "lemonade":
            model_ids = owner._fetch_lemonade_model_ids()
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
        owner._trigger_local_runtime_warm_refresh(force=False)
        return {
            "backend": backend,
            "base_url": owner._local_runtime_base_url(backend),
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

    available_roles = sorted(
        [role for role, model in role_models.items() if model and model in model_ids]
    )
    missing_roles = sorted(
        [role for role, model in role_models.items() if model and model not in model_ids]
    )
    if available_roles and not missing_roles:
        state = "READY"
    elif available_roles:
        state = "PARTIAL"
    else:
        state = "MISSING"

    if backend == "ollama" and available_roles and str(warm_status.get("chat_state", "UNKNOWN") or "UNKNOWN") == "UNKNOWN":
        owner._trigger_local_runtime_warm_refresh(force=False)
    if backend == "ollama" and available_roles and not bool(warm_status.get("chat_ready", False)) and state == "READY":
        state = "PARTIAL"
        detail = f"{detail} | chat lane warming"

    return {
        "backend": backend,
        "base_url": owner._local_runtime_base_url(backend),
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


def call_lemonade_chat(
    owner: Any,
    user_text: str,
    system_prompt: str,
    *,
    model_override: Optional[str] = None,
) -> str:
    model_name = str(model_override or "").strip()
    if not model_name:
        role_models = owner._local_runtime_role_models("lemonade")
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
        f"{owner._local_runtime_base_url('lemonade').rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=owner.CHAT_TIMEOUT_SECONDS) as resp:
        data = json.loads(resp.read())
    choices = data.get("choices", []) if isinstance(data, dict) else []
    if not choices:
        raise RuntimeError("Lemonade returned no chat choices.")
    message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
    content = str(message.get("content", "") or "").strip()
    if not content:
        raise RuntimeError("Lemonade returned an empty response.")
    return content


def call_selected_local_runtime(
    owner: Any,
    user_text: str,
    system_prompt: str,
    *,
    instance_name: Optional[str] = None,
    instance_type: Optional[str] = None,
    model_override: Optional[str] = None,
) -> str:
    backend = owner._selected_local_runtime_backend()
    warm_status = owner._local_runtime_warm_cached_or_unknown()
    if backend == "ollama" and not bool(warm_status.get("chat_ready", False)):
        owner._trigger_local_runtime_warm_refresh(force=True)
        warm_model = str(
            warm_status.get("model", "") or owner._current_local_runtime_chat_model(backend)
        )
        warm_detail = str(
            warm_status.get("chat_detail", "") or "local runtime is still warming up"
        )
        raise RuntimeError(
            f"Local runtime is still warming up for {warm_model or 'the configured model'}. {warm_detail}"
        )
    if backend == "lemonade":
        return owner._call_lemonade_chat(
            user_text,
            system_prompt,
            model_override=model_override,
        )
    return owner._call_ollama_with_tools(
        user_text,
        system_prompt,
        instance_name=instance_name,
        instance_type=instance_type,
        model_override=model_override,
    )
