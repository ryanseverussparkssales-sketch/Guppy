"""DEPRECATED — Tranche C.

All warmup logic has migrated:
  - KV cache priming → routes_backends._warm_kv_cache() + _WARMUP_SYSTEM_PROMPTS
  - Model lifecycle + health → services_model_manager.py

This file is kept only for import compatibility during the transition.
Remove after Tranche E cleanup sweep.
"""
from __future__ import annotations

import warnings

warnings.warn(
    "services_runtime_warmup is deprecated (Tranche C). "
    "Use services_model_manager.get_model_health() instead.",
    DeprecationWarning,
    stacklevel=2,
)

import json
import threading
import time
import urllib.request
from typing import Any


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
    try:
        from src.guppy.inference.local_client import local_chat as _local_chat
        result = _local_chat(
            model,
            [{"role": "user", "content": "ok"}],
            timeout=int(owner._LOCAL_RUNTIME_WARM_TIMEOUT_SECONDS),
            num_predict=1,
            backend="lmstudio",
        )
        if result is not None:
            return True, f"lmstudio warm (model: {result.get('model', model)})"
        return False, "LM Studio warmup returned no response"
    except Exception as exc:
        return False, f"LM Studio warmup error: {exc}"


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
