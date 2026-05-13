from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Optional

from src.guppy.inference.local_client import (
    _BACKEND_DEFAULT_MODELS,
    _BACKENDS,
    _DEFAULT_BACKEND,
    _LLAMACPP_MODEL_ROUTE,
    _resolve_url,
    active_backend,
    list_local_models,
    local_chat,
    probe_backends,
)

_log = logging.getLogger(__name__)

_PROBE_CACHE_TTL_SECONDS = float(os.environ.get("GUPPY_BACKEND_PROBE_TTL_SECONDS", "5"))
_MODEL_LIST_TTL_SECONDS = float(os.environ.get("GUPPY_MODEL_LIST_TTL_SECONDS", "20"))
_PROBE_CACHE: dict[str, Any] = {"expires_at": 0.0, "payload": {}}
_MODEL_LIST_CACHE: dict[str, tuple[float, list[str]]] = {}

_ROLE_MODEL_FALLBACKS = {
    "fast":    "Hermes-4.3-36B-heretic.Q4_K_M.gguf",
    "complex": "Hermes-4.3-36B-heretic.Q4_K_M.gguf",
    "teach":   "Hermes-4.3-36B-heretic.Q4_K_M.gguf",
    "code":    "Hermes-4.3-36B-heretic.Q4_K_M.gguf",
    "vault":   "Hermes-4.3-36B-heretic.Q4_K_M.gguf",
}


def _canonical_backend(raw_backend: str | None) -> str:
    backend = str(raw_backend or "").strip().lower()
    if backend in _BACKENDS:
        return backend
    if backend == "auto" or not backend:
        return active_backend()
    # Legacy values such as ollama/lmstudio/lemonade intentionally collapse
    # through local_client so one registry owns local runtime truth.
    return active_backend()


def _backend_for_model(model: str, fallback_backend: str) -> str:
    normalized_model = str(model or "").strip().lower()
    if normalized_model in _LLAMACPP_MODEL_ROUTE:
        return _LLAMACPP_MODEL_ROUTE[normalized_model]
    if normalized_model in _BACKENDS:
        return normalized_model
    fallback = _canonical_backend(fallback_backend)
    return fallback if fallback in _BACKENDS else _DEFAULT_BACKEND


def _model_for_backend(backend: str) -> str:
    resolved = _canonical_backend(backend)
    return _BACKEND_DEFAULT_MODELS.get(resolved, _BACKEND_DEFAULT_MODELS[_DEFAULT_BACKEND])


def selected_local_runtime_backend(owner: Any) -> str:
    """Return the active llama.cpp/local-harness backend."""
    raw = str(owner.os.environ.get("GUPPY_LOCAL_RUNTIME_BACKEND", "auto") or "auto").strip().lower()
    try:
        return _canonical_backend(raw)
    except Exception as exc:
        _log.debug("Backend resolution failed, defaulting to %s: %s", _DEFAULT_BACKEND, exc)
        return _DEFAULT_BACKEND


def local_runtime_base_url(owner: Any, backend: str) -> str:
    del owner
    return _resolve_url(_canonical_backend(backend))


def resolve_local_runtime_model(
    owner: Any,
    backend: str,
    role: str,
    *,
    fallback: str = "",
) -> str:
    del backend
    normalized_role = (role or "").strip().lower()
    fallback_model = _ROLE_MODEL_FALLBACKS.get(normalized_role, fallback) or fallback

    if owner.INFERENCE_ROUTER_AVAILABLE:
        try:
            router = owner.get_router()
            router_attr = {
                "fast": "LOCAL_FAST_MODEL",
                "complex": "LOCAL_MODEL",
                "teach": "LOCAL_TEACH_MODEL",
                "code": "LOCAL_CODE_MODEL",
                "vault": "LOCAL_VAULT_MODEL",
            }.get(normalized_role)
            if router_attr:
                return str(getattr(router, router_attr, fallback_model) or fallback_model).strip()
        except Exception as exc:
            _log.debug("Router model resolution failed for role %r: %s", role, exc)
    return str(fallback_model or _model_for_backend(_DEFAULT_BACKEND)).strip()


def local_runtime_role_models(owner: Any, backend: str) -> dict[str, str]:
    return {
        "fast": resolve_local_runtime_model(owner, backend, "fast"),
        "complex": resolve_local_runtime_model(owner, backend, "complex"),
        "teach": resolve_local_runtime_model(owner, backend, "teach"),
        "code": resolve_local_runtime_model(owner, backend, "code"),
        "vault": resolve_local_runtime_model(owner, backend, "vault"),
    }


def warm_ollama_chat_lane(owner: Any, model: str, keep_alive: str = "20m") -> tuple[bool, str]:
    """Compatibility wrapper for the old binding name.

    The implementation now warms the canonical llama.cpp/OpenAI-compatible
    backend selected by local_client; it never calls Ollama.
    """
    del keep_alive
    normalized_model = str(model or "").strip() or owner._current_local_runtime_chat_model(
        owner._selected_local_runtime_backend()
    )
    if not normalized_model:
        return False, "no local model configured for warmup"
    backend = _backend_for_model(normalized_model, owner._selected_local_runtime_backend())
    try:
        result = local_chat(
            normalized_model,
            [{"role": "user", "content": "ok"}],
            timeout=int(owner._LOCAL_RUNTIME_WARM_TIMEOUT_SECONDS),
            num_predict=1,
            max_retries=0,
            backend=backend,
        )
    except Exception as exc:
        return False, f"{backend} warmup error: {exc}"
    if result is None:
        return False, f"{backend} warmup returned no response"
    return True, f"{normalized_model} warm via {backend}"


def current_local_runtime_chat_model(owner: Any, backend: str) -> str:
    role_models = owner._local_runtime_role_models(backend)
    return str(role_models.get("complex") or role_models.get("fast") or _model_for_backend(backend)).strip()


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

    ok, detail = warm_ollama_chat_lane(owner, model)
    payload = {
        "backend": backend,
        "model": model,
        "checked_at": now,
        "expires_at": now + max(30.0, owner._LOCAL_RUNTIME_WARM_TTL_SECONDS),
        "chat_ready": bool(ok),
        "chat_state": "READY" if ok else "FAILED",
        "chat_detail": str(detail or ("local runtime warmed" if ok else "local runtime warmup failed")),
    }
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
            with state.local_runtime_warm_lock:
                state.local_runtime_warm_refresh_inflight = False

    threading.Thread(target=_worker, daemon=True).start()


def fetch_lemonade_model_ids(owner: Any, timeout: float = 4.0) -> set[str]:
    del owner, timeout
    return set()


def _runtime_policy_payload() -> dict[str, Any]:
    try:
        from src.guppy.local_llm.manifest import (
            get_local_llm_policy_summary,
            load_local_llm_manifest,
        )

        return get_local_llm_policy_summary(load_local_llm_manifest())
    except Exception:
        return {}


def _role_backend_map(role_models: dict[str, str], selected_backend: str) -> dict[str, str]:
    return {
        role: _backend_for_model(model, selected_backend)
        for role, model in role_models.items()
        if str(model or "").strip()
    }


def _probe_backends_cached(timeout: float = 1.0) -> dict[str, bool]:
    now = time.time()
    payload = _PROBE_CACHE.get("payload", {})
    if payload and float(_PROBE_CACHE.get("expires_at", 0.0)) > now:
        return dict(payload)
    live = probe_backends(timeout=timeout)
    _PROBE_CACHE["payload"] = dict(live)
    _PROBE_CACHE["expires_at"] = now + max(1.0, _PROBE_CACHE_TTL_SECONDS)
    return dict(live)


def _list_models_cached(backend: str, timeout: float = 2.0) -> list[str]:
    now = time.time()
    cached = _MODEL_LIST_CACHE.get(backend)
    if cached and cached[0] > now:
        return list(cached[1])
    models = sorted(list_local_models(backend, timeout=timeout))
    _MODEL_LIST_CACHE[backend] = (now + max(5.0, _MODEL_LIST_TTL_SECONDS), list(models))
    return models


def build_local_runtime_status(owner: Any) -> dict[str, Any]:
    backend = owner._selected_local_runtime_backend()
    role_models = owner._local_runtime_role_models(backend)
    active_chat_model = owner._current_local_runtime_chat_model(backend)
    warm_status = owner._local_runtime_warm_cached_or_unknown()
    policy = _runtime_policy_payload()

    live_backends = _probe_backends_cached(timeout=1.0)
    role_backends = _role_backend_map(role_models, backend)
    active_backend_live = bool(live_backends.get(backend, False))
    relevant_backends = sorted(set(role_backends.values()) | {backend})

    backend_models: dict[str, list[str]] = {}
    for runtime_backend in relevant_backends:
        if not live_backends.get(runtime_backend, False):
            backend_models[runtime_backend] = []
            continue
        try:
            backend_models[runtime_backend] = _list_models_cached(runtime_backend, timeout=2.0)
        except Exception:
            backend_models[runtime_backend] = []

    available_roles = sorted(
        role for role, runtime_backend in role_backends.items() if live_backends.get(runtime_backend, False)
    )
    missing_roles = sorted(
        role for role, runtime_backend in role_backends.items() if not live_backends.get(runtime_backend, False)
    )

    if available_roles and not missing_roles:
        state = "READY"
        detail = "llama.cpp role backends reachable"
    elif available_roles:
        state = "PARTIAL"
        detail = "some llama.cpp role backends are reachable"
    else:
        state = "MISSING"
        detail = f"no configured llama.cpp/local harness backends reachable; selected {backend}"

    if active_backend_live and str(warm_status.get("chat_state", "UNKNOWN") or "UNKNOWN") == "UNKNOWN":
        owner._trigger_local_runtime_warm_refresh(force=False)
    if active_backend_live and not bool(warm_status.get("chat_ready", False)) and state == "READY":
        state = "PARTIAL"
        detail = f"{detail} | chat lane warming"

    return {
        "backend": backend,
        "base_url": owner._local_runtime_base_url(backend),
        "state": state,
        "detail": detail,
        "role_models": role_models,
        "role_backends": role_backends,
        "available_roles": available_roles,
        "missing_roles": missing_roles,
        "models": backend_models.get(backend, []),
        "backend_models": backend_models,
        "backends": {
            name: {
                "alive": bool(live_backends.get(name, False)),
                "base_url": _resolve_url(name),
                "model": _BACKEND_DEFAULT_MODELS.get(name, name),
            }
            for name in sorted(_BACKENDS)
        },
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
    del owner, user_text, system_prompt, model_override
    raise RuntimeError("Lemonade is no longer a routed local backend; use a llama.cpp backend.")


def call_selected_local_runtime(
    owner: Any,
    user_text: str,
    system_prompt: str,
    *,
    instance_name: Optional[str] = None,
    instance_type: Optional[str] = None,
    model_override: Optional[str] = None,
) -> str:
    del instance_name, instance_type
    selected_backend = owner._selected_local_runtime_backend()
    model = str(model_override or "").strip() or owner._current_local_runtime_chat_model(selected_backend)
    if not model:
        model = _model_for_backend(selected_backend)
    backend = _backend_for_model(model, selected_backend)

    no_tools_note = (
        "[SYSTEM NOTE: You have NO access to external tools, APIs, or the internet in this local text lane. "
        "Do NOT output tool call tags or markup. Respond directly using your knowledge only.]\n\n"
    )
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": no_tools_note + system_prompt})
    messages.append({"role": "user", "content": user_text})

    result = local_chat(
        model,
        messages,
        backend=backend,
        timeout=int(getattr(owner, "CHAT_TIMEOUT_SECONDS", 120)),
        num_predict=2048,
    )
    if not result:
        raise RuntimeError(f"Local runtime backend '{backend}' returned no response for model '{model}'.")
    content = str(result.get("response", "") or "").strip()
    if not content:
        raise RuntimeError(f"Local runtime backend '{backend}' returned an empty response for model '{model}'.")

    from src.guppy.api.realtime_inference_support import _clean_llamacpp_response

    return _clean_llamacpp_response(content)
