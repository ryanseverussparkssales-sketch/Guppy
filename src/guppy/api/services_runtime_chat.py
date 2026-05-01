from __future__ import annotations

import json
import urllib.request
from typing import Any, Optional


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


def call_lmstudio_chat(
    owner: Any,
    user_text: str,
    system_prompt: str,
    *,
    model_override: Optional[str] = None,
) -> str:
    from src.guppy.inference.local_client import local_chat as _local_chat
    model = str(model_override or "").strip() or owner._current_local_runtime_chat_model("lmstudio")
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_text})
    timeout = int(getattr(owner, "CHAT_TIMEOUT_SECONDS", 60))
    result = _local_chat(model, messages, timeout=timeout, num_predict=1024, backend="lmstudio")
    if result is None:
        raise RuntimeError("LM Studio returned no response.")
    content = str(result.get("response", "") or "").strip()
    if not content:
        raise RuntimeError("LM Studio returned an empty response.")
    return content



def call_textgen_webui_chat(
    owner: Any,
    user_text: str,
    system_prompt: str,
    *,
    model_override: Optional[str] = None,
) -> str:
    """Call text-generation-webui API for chat completion."""
    model_name = str(model_override or "").strip() or owner._current_local_runtime_chat_model("text-generation-webui")
    if not model_name:
        model_name = "model"  # Default fallback
    
    payload = {
        "mode": "chat-instruct",
        "character": "Assistant",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
    }
    
    base = owner._local_runtime_base_url("text-generation-webui").rstrip("/")
    req = urllib.request.Request(
        f"{base}/api/v1/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    
    try:
        with urllib.request.urlopen(req, timeout=owner.CHAT_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read())
    except urllib.error.URLError as e:
        raise RuntimeError(f"text-generation-webui unavailable: {e}") from e
    
    # Handle response - text-gen returns different formats depending on mode
    if isinstance(data, dict):
        # Try chat format first
        if "messages" in data and isinstance(data["messages"], list) and data["messages"]:
            message = data["messages"][-1]
            if isinstance(message, dict):
                content = str(message.get("content", "") or "").strip()
                if content:
                    return content
        # Try direct response field
        if "response" in data:
            content = str(data.get("response", "") or "").strip()
            if content:
                return content
    
    raise RuntimeError("text-generation-webui returned no valid response.")


def call_llamacpp_chat(
    owner: Any,
    user_text: str,
    system_prompt: str,
    *,
    backend: str,
    model_override: Optional[str] = None,
) -> str:
    """Call a llama.cpp server (OpenAI-compatible) via local_client.local_chat().

    Args:
        backend: One of "llamacpp-gemma", "llamacpp-qwen3", "llamacpp-pepe".
        model_override: Optional model name override (ignored by llama.cpp server
                        since it uses whatever model was loaded at startup, but
                        recorded in metadata for logging).
    """
    from src.guppy.inference.local_client import local_chat as _local_chat, _BACKEND_DEFAULT_MODELS

    model = str(model_override or "").strip() or _BACKEND_DEFAULT_MODELS.get(backend, backend)
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_text})
    timeout = int(getattr(owner, "CHAT_TIMEOUT_SECONDS", 90))

    result = _local_chat(model, messages, backend=backend, timeout=timeout, num_predict=1024)
    if result is None:
        raise RuntimeError(f"{backend} returned no response (server may not be running).")
    content = str(result.get("response", "") or "").strip()
    if not content:
        raise RuntimeError(f"{backend} returned an empty response.")
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
    """Call the selected local runtime backend with automatic fallback to Ollama.

    If LM Studio times out or fails, automatically falls back to Ollama.
    """
    import logging
    import time
    from src.guppy.inference.local_client import _LLAMACPP_MODEL_ROUTE

    logger = logging.getLogger(__name__)
    backend = owner._selected_local_runtime_backend()
    warm_status = owner._local_runtime_warm_cached_or_unknown()

    # If the requested model name maps to a llama.cpp server, route there directly
    # without trying the active backend or falling back to Ollama.
    llamacpp_backend = _LLAMACPP_MODEL_ROUTE.get(model_override or "", "") if model_override else ""

    # Determine which backends to try (in order)
    if llamacpp_backend:
        backends_to_try = [llamacpp_backend]
    else:
        backends_to_try = []
        if backend:
            backends_to_try.append(backend)
        # Ollama fallback removed — all local routes now use llama.cpp servers directly
    
    last_error = None
    
    for attempt_backend in backends_to_try:
        try:
            logger.debug(f"[CHAT] Attempting {attempt_backend} (primary={backend})")
            
            if attempt_backend == "ollama":
                if backend != "ollama" and not bool(warm_status.get("chat_ready", False)):
                    owner._trigger_local_runtime_warm_refresh(force=True)
                return owner._call_ollama_with_tools(
                    user_text,
                    system_prompt,
                    instance_name=instance_name,
                    instance_type=instance_type,
                    model_override=model_override,
                )
            
            elif attempt_backend == "lemonade":
                return owner._call_lemonade_chat(user_text, system_prompt, model_override=model_override)
            
            elif attempt_backend == "vllm":
                return call_vllm_chat(owner, user_text, system_prompt, model_override=model_override)
            
            elif attempt_backend == "text-generation-webui":
                return call_textgen_webui_chat(owner, user_text, system_prompt, model_override=model_override)
            
            elif attempt_backend == "lmstudio":
                # Try LM Studio with timeout
                start_time = time.perf_counter()
                try:
                    result = call_lmstudio_chat(owner, user_text, system_prompt, model_override=model_override)
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    logger.debug(f"[CHAT] LM Studio responded in {elapsed_ms:.0f}ms")
                    return result
                except (TimeoutError, urllib.error.URLError) as e:
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    logger.warning(f"[CHAT] LM Studio timeout/error after {elapsed_ms:.0f}ms: {e}")
                    last_error = e
                    # Continue to next backend (Ollama fallback)
                    if attempt_backend == backends_to_try[-1]:
                        raise  # Re-raise if this was the last backend
                    continue

            elif attempt_backend in {"llamacpp-gemma", "llamacpp-qwen3", "llamacpp-pepe"}:
                return call_llamacpp_chat(owner, user_text, system_prompt,
                                          backend=attempt_backend, model_override=model_override)
        
        except Exception as e:
            logger.warning(f"[CHAT] {attempt_backend} failed: {e}")
            last_error = e
            if attempt_backend == backends_to_try[-1]:
                # Last backend, re-raise the error
                raise RuntimeError(f"All backends failed. Last error: {e}") from e
            # Try next backend
            continue
    
    # Should not reach here, but just in case
    raise RuntimeError(f"No backends available. Last error: {last_error}")
