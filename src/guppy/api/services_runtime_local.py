from __future__ import annotations

import json
import threading
import time
import urllib.request
from typing import Any, Optional


_VALID_BACKENDS = {"ollama", "lmstudio", "lemonade", "vllm", "auto"}
_LMSTUDIO_DEFAULT_URL = "http://127.0.0.1:1234"
_VLLM_DEFAULT_URL = "http://127.0.0.1:8000"


def selected_local_runtime_backend(owner: Any) -> str:
    """Return the active backend name. 'auto' is resolved to the detected backend."""
    raw = str(owner.os.environ.get("GUPPY_LOCAL_RUNTIME_BACKEND", "auto") or "auto").strip().lower()
    if raw not in _VALID_BACKENDS:
        raw = "auto"
    if raw == "auto":
        try:
            from src.guppy.inference.local_client import active_backend
            return active_backend()
        except Exception:
            return "ollama"
    return raw


def local_runtime_base_url(owner: Any, backend: str) -> str:
    normalized = (backend or "ollama").strip().lower()
    if normalized == "lemonade":
        return str(
            owner.os.environ.get("GUPPY_LEMONADE_BASE_URL", owner._DEFAULT_LEMONADE_BASE_URL)
            or owner._DEFAULT_LEMONADE_BASE_URL
        ).strip()
    if normalized == "lmstudio":
        return str(
            owner.os.environ.get("GUPPY_LMSTUDIO_BASE_URL", _LMSTUDIO_DEFAULT_URL)
            or _LMSTUDIO_DEFAULT_URL
        ).strip()
    if normalized == "vllm":
        return str(
            owner.os.environ.get("GUPPY_VLLM_BASE_URL", _VLLM_DEFAULT_URL)
            or _VLLM_DEFAULT_URL
        ).strip()
    return str(
        owner.os.environ.get("GUPPY_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        or "http://127.0.0.1:11434"
    ).strip()


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


def warm_lmstudio_chat_lane(owner: Any, model: str) -> tuple[bool, str]:
    normalized_model = str(model or "").strip()
    if not normalized_model:
        return False, "no LM Studio model configured for warmup"
    payload = {
        "model": normalized_model,
        "messages": [{"role": "user", "content": "ok"}],
        "stream": False,
        "max_tokens": 1,
    }
    base = owner._local_runtime_base_url("lmstudio").rstrip("/")
    req = urllib.request.Request(
        f"{base}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=owner._LOCAL_RUNTIME_WARM_TIMEOUT_SECONDS) as resp:
        data = json.loads(resp.read())
    choices = data.get("choices", []) if isinstance(data, dict) else []
    if not choices:
        return False, "LM Studio warmup returned no choices"
    return True, f"{normalized_model} warm"


def warm_vllm_chat_lane(owner: Any, model: str) -> tuple[bool, str]:
    normalized_model = str(model or "guppy").strip()
    payload = {
        "model": normalized_model,
        "messages": [{"role": "user", "content": "ok"}],
        "stream": False,
        "max_tokens": 1,
    }
    base = owner._local_runtime_base_url("vllm").rstrip("/")
    req = urllib.request.Request(
        f"{base}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=owner._LOCAL_RUNTIME_WARM_TIMEOUT_SECONDS) as resp:
        data = json.loads(resp.read())
    choices = data.get("choices", []) if isinstance(data, dict) else []
    if not choices:
        return False, "vLLM warmup returned no choices"
    return True, f"{normalized_model} warm via vLLM"


def warm_lemonade_chat_lane(owner: Any, model: str) -> tuple[bool, str]:
    normalized_model = str(model or "").strip()
    if not normalized_model:
        return False, "no Lemonade model configured for warmup"
    payload = {
        "model": normalized_model,
        "messages": [
            {"role": "system", "content": "warmup"},
            {"role": "user", "content": "ok"},
        ],
        "stream": False,
        "max_tokens": 1,
    }
    req = urllib.request.Request(
        f"{owner._local_runtime_base_url('lemonade').rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=owner._LOCAL_RUNTIME_WARM_TIMEOUT_SECONDS) as resp:
        data = json.loads(resp.read())
    choices = data.get("choices", []) if isinstance(data, dict) else []
    if not choices:
        return False, "Lemonade warmup returned no chat choices"
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

    ok = False
    detail = ""
    try:
        if backend == "lemonade":
            ok, detail = warm_lemonade_chat_lane(owner, model)
        elif backend == "lmstudio":
            ok, detail = warm_lmstudio_chat_lane(owner, model)
        elif backend == "vllm":
            ok, detail = warm_vllm_chat_lane(owner, model)
        else:
            ok, detail = warm_ollama_chat_lane(owner, model)
    except Exception as exc:
        ok = False
        detail = str(exc)
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


def _build_missing_local_runtime_payload(
    owner: Any,
    *,
    backend: str,
    role_models: dict[str, str],
    policy: dict[str, Any],
    warm_status: dict[str, Any],
    active_chat_model: str,
    detail: str,
) -> dict[str, Any]:
    owner._trigger_local_runtime_warm_refresh(force=False)
    return {
        "backend": backend,
        "base_url": owner._local_runtime_base_url(backend),
        "state": "MISSING",
        "detail": detail,
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


def build_local_runtime_status(owner: Any) -> dict[str, Any]:
    backend = owner._selected_local_runtime_backend()
    role_models = owner._local_runtime_role_models(backend)
    active_chat_model = owner._current_local_runtime_chat_model(backend)
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
        elif backend == "lmstudio":
            base = owner._local_runtime_base_url("lmstudio").rstrip("/")
            req = urllib.request.Request(
                f"{base}/v1/models",
                headers={"Accept": "application/json"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                data = json.loads(resp.read())
            items = data.get("data", []) if isinstance(data, dict) else []
            model_ids = {
                str(item.get("id", "")).strip()
                for item in items
                if isinstance(item, dict) and str(item.get("id", "")).strip()
            }
            detail = "LM Studio model registry reachable"
        elif backend == "vllm":
            base = owner._local_runtime_base_url("vllm").rstrip("/")
            req = urllib.request.Request(
                f"{base}/v1/models",
                headers={"Accept": "application/json"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                data = json.loads(resp.read())
            items = data.get("data", []) if isinstance(data, dict) else []
            model_ids = {
                str(item.get("id", "")).strip()
                for item in items
                if isinstance(item, dict) and str(item.get("id", "")).strip()
            }
            detail = "vLLM model registry reachable"
        else:
            ollama_base = owner._local_runtime_base_url("ollama").rstrip("/")
            req = urllib.request.Request(
                f"{ollama_base}/api/tags",
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
        return _build_missing_local_runtime_payload(
            owner,
            backend=backend,
            role_models=role_models,
            policy=policy,
            warm_status=warm_status,
            active_chat_model=active_chat_model,
            detail=str(exc),
        )

    available_roles = sorted([role for role, model in role_models.items() if model and model in model_ids])
    missing_roles = sorted([role for role, model in role_models.items() if model and model not in model_ids])
    if available_roles and not missing_roles:
        state = "READY"
    elif available_roles:
        state = "PARTIAL"
    else:
        state = "MISSING"

    if backend in {"ollama", "vllm"} and available_roles and str(warm_status.get("chat_state", "UNKNOWN") or "UNKNOWN") == "UNKNOWN":
        owner._trigger_local_runtime_warm_refresh(force=False)
    if backend in {"ollama", "vllm"} and available_roles and not bool(warm_status.get("chat_ready", False)) and state == "READY":
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


def call_vllm_chat(
    owner: Any,
    user_text: str,
    system_prompt: str,
    *,
    model_override: Optional[str] = None,
) -> str:
    model_name = str(model_override or "").strip() or "guppy"
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        "stream": False,
        "max_tokens": 2048,
    }
    base = owner._local_runtime_base_url("vllm").rstrip("/")
    req = urllib.request.Request(
        f"{base}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=owner.CHAT_TIMEOUT_SECONDS) as resp:
        data = json.loads(resp.read())
    choices = data.get("choices", []) if isinstance(data, dict) else []
    if not choices:
        raise RuntimeError("vLLM returned no chat choices.")
    message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
    content = str(message.get("content", "") or "").strip()
    if not content:
        raise RuntimeError("vLLM returned an empty response.")
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
    if backend == "lemonade":
        return owner._call_lemonade_chat(
            user_text,
            system_prompt,
            model_override=model_override,
        )
    if backend == "vllm":
        return call_vllm_chat(
            owner,
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
