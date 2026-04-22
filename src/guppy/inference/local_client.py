"""Unified local inference client: Ollama, LM Studio, Lemonade.

Circuit breaker: 3 consecutive failures → 30 s cooldown before retrying.
Retry: up to 2 retries with exponential backoff (0.5 s, 1.0 s).

Backend selection (GUPPY_LOCAL_RUNTIME_BACKEND env var):
  auto      — probe Ollama (11434) then LM Studio (1234), use whichever answers (default)
  ollama    — Ollama at 127.0.0.1:11434 (override with GUPPY_OLLAMA_BASE_URL)
  lmstudio  — LM Studio at 127.0.0.1:1234 (override with GUPPY_LMSTUDIO_BASE_URL)
  lemonade  — Lemonade at 127.0.0.1:8000 (override with GUPPY_LEMONADE_BASE_URL)

LM Studio model resolution:
  LM Studio exposes long model IDs (e.g. "org/model-GGUF/file.gguf").
  When the requested model name isn't found verbatim, the client automatically
  falls back to the first loaded model so callers never need to configure
  LM Studio model names explicitly.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_BACKENDS: Dict[str, Dict[str, Any]] = {
    "ollama": {
        "default_url": "http://127.0.0.1:11434",
        "chat_path": "/api/chat",
        "tags_path": "/api/tags",
        "pull_path": "/api/pull",
        "delete_path": "/api/delete",
        "format": "ollama",
    },
    "lmstudio": {
        "default_url": "http://127.0.0.1:1234",
        "chat_path": "/v1/chat/completions",
        "tags_path": "/v1/models",
        "pull_path": None,
        "delete_path": None,
        "format": "openai",
    },
    "lemonade": {
        "default_url": "http://127.0.0.1:8000",
        "chat_path": "/chat/completions",
        "tags_path": "/models",
        "pull_path": None,
        "delete_path": None,
        "format": "openai",
    },
}

_ENV_URL_KEYS: Dict[str, str] = {
    "ollama": "GUPPY_OLLAMA_BASE_URL",
    "lmstudio": "GUPPY_LMSTUDIO_BASE_URL",
    "lemonade": "GUPPY_LEMONADE_BASE_URL",
}

# ── circuit breakers ──────────────────────────────────────────────────────────

class _CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, reset_timeout: float = 30.0) -> None:
        self._threshold = failure_threshold
        self._reset_timeout = reset_timeout
        self._failures = 0
        self._opened_at: Optional[float] = None
        self._lock = threading.Lock()

    @property
    def is_open(self) -> bool:
        with self._lock:
            if self._opened_at is None:
                return False
            if time.monotonic() - self._opened_at > self._reset_timeout:
                self._failures = 0
                self._opened_at = None
                return False
            return True

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self._threshold and self._opened_at is None:
                self._opened_at = time.monotonic()
                logger.warning(
                    f"[LOCAL] circuit breaker opened after {self._failures} failures"
                    f" — cooling down {self._reset_timeout:.0f}s"
                )


_circuit_breakers: Dict[str, _CircuitBreaker] = {}
_cb_lock = threading.Lock()


def _get_cb(backend: str) -> _CircuitBreaker:
    with _cb_lock:
        if backend not in _circuit_breakers:
            _circuit_breakers[backend] = _CircuitBreaker()
        return _circuit_breakers[backend]


# ── URL helpers ───────────────────────────────────────────────────────────────

def _resolve_url(backend: str) -> str:
    env_key = _ENV_URL_KEYS.get(backend, "")
    env_val = (os.environ.get(env_key, "") or "").strip()
    return (env_val or _BACKENDS[backend]["default_url"]).rstrip("/")


# ── auto-backend detection ────────────────────────────────────────────────────

_auto_cache: Dict[str, Any] = {"backend": None, "expires_at": 0.0}
_auto_lock = threading.Lock()
# Probe order: Ollama first (most common), then LM Studio
_AUTO_PROBE_ORDER = ("ollama", "lmstudio")


def _probe_backends(timeout: float = 1.5) -> str:
    """Ping each backend in order; return the first that responds."""
    for name in _AUTO_PROBE_ORDER:
        cfg = _BACKENDS[name]
        url = f"{_resolve_url(name)}{cfg['tags_path']}"
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                r.read()
            logger.info(f"[LOCAL/auto] detected backend: {name}")
            return name
        except Exception:
            continue
    logger.info("[LOCAL/auto] no backend detected, defaulting to ollama")
    return "ollama"


def _resolve_backend() -> str:
    raw = (os.environ.get("GUPPY_LOCAL_RUNTIME_BACKEND", "auto") or "auto").strip().lower()
    if raw == "auto":
        now = time.monotonic()
        with _auto_lock:
            cached = _auto_cache.get("backend")
            if cached and _auto_cache.get("expires_at", 0.0) > now:
                return cached
        detected = _probe_backends()
        with _auto_lock:
            _auto_cache["backend"] = detected
            _auto_cache["expires_at"] = now + 30.0
        return detected
    return raw if raw in _BACKENDS else "ollama"


def probe_backends(timeout: float = 1.5) -> Dict[str, bool]:
    """Return liveness dict for all backends — useful for status/debug endpoints."""
    result: Dict[str, bool] = {}
    for name, cfg in _BACKENDS.items():
        url = f"{_resolve_url(name)}{cfg['tags_path']}"
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                r.read()
            result[name] = True
        except Exception:
            result[name] = False
    return result


# ── LM Studio model resolution ────────────────────────────────────────────────

_lmstudio_model_cache: Dict[str, Any] = {"models": [], "expires_at": 0.0}
_lmstudio_cache_lock = threading.Lock()


def _get_lmstudio_models(timeout: float = 2.0) -> List[str]:
    """Return LM Studio model IDs, cached for 15 s."""
    now = time.monotonic()
    with _lmstudio_cache_lock:
        if _lmstudio_model_cache["expires_at"] > now:
            return list(_lmstudio_model_cache["models"])

    models = list_local_models("lmstudio", timeout=timeout)
    with _lmstudio_cache_lock:
        _lmstudio_model_cache["models"] = models
        _lmstudio_model_cache["expires_at"] = now + 15.0
    return models


def _resolve_lmstudio_model(requested: str) -> str:
    """Map a Guppy logical model name to an LM Studio model ID.

    If the requested name exists verbatim in LM Studio, use it.
    Otherwise fall back to the first loaded model — LM Studio users
    never need to configure model names explicitly.
    """
    available = _get_lmstudio_models()
    if not available:
        return requested  # nothing loaded; attempt will fail gracefully
    if requested in available:
        return requested
    # Use whatever is currently loaded
    resolved = available[0]
    if requested != resolved:
        logger.info(f"[LOCAL/lmstudio] '{requested}' not found — using loaded model '{resolved}'")
    return resolved


# ── payload builders ──────────────────────────────────────────────────────────

def _build_ollama_payload(
    model: str,
    messages: List[Dict[str, Any]],
    tools: Optional[list],
    num_predict: int,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "keep_alive": "10m",
        "options": {"temperature": 0.8, "top_p": 0.95, "top_k": 40, "num_predict": num_predict},
    }
    if tools:
        payload["tools"] = tools
    return payload


def _build_openai_payload(
    model: str,
    messages: List[Dict[str, Any]],
    tools: Optional[list],
    num_predict: int,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "max_tokens": num_predict,
        "temperature": 0.8,
        "top_p": 0.95,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    return payload


# ── response parsers ──────────────────────────────────────────────────────────

def _parse_ollama(data: Dict[str, Any], model: str, backend: str) -> Dict[str, Any]:
    return {
        "response": data.get("message", {}).get("content", ""),
        "model": model,
        "source": "local",
        "tool_calls": data.get("message", {}).get("tool_calls", []),
        "metadata": {"timestamp": datetime.now().isoformat(), "backend": backend},
    }


def _parse_openai(data: Dict[str, Any], model: str, backend: str) -> Optional[Dict[str, Any]]:
    choices = data.get("choices", []) if isinstance(data, dict) else []
    if not choices:
        return None
    msg = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
    return {
        "response": str(msg.get("content") or ""),
        "model": model,
        "source": "local",
        "tool_calls": msg.get("tool_calls", []),
        "metadata": {"timestamp": datetime.now().isoformat(), "backend": backend},
    }


# ── public API ────────────────────────────────────────────────────────────────

def local_chat(
    model: str,
    messages: List[Dict[str, Any]],
    *,
    tools: Optional[list] = None,
    timeout: int = 60,
    num_predict: int = 512,
    max_retries: int = 2,
    backend: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Send a chat request to the configured local backend.

    Returns a response dict or None on failure. Respects the circuit breaker.
    For LM Studio, automatically maps to the currently loaded model.
    """
    resolved = (backend or _resolve_backend()).strip().lower()
    if resolved not in _BACKENDS:
        resolved = "ollama"

    cb = _get_cb(resolved)
    if cb.is_open:
        logger.warning(f"[LOCAL/{resolved}] circuit breaker OPEN — skipping {model}")
        return None

    # LM Studio: resolve logical name → actual loaded model ID
    actual_model = _resolve_lmstudio_model(model) if resolved == "lmstudio" else model

    cfg = _BACKENDS[resolved]
    url = f"{_resolve_url(resolved)}{cfg['chat_path']}"
    if cfg["format"] == "ollama":
        payload = _build_ollama_payload(actual_model, messages, tools, num_predict)
        parse = lambda d: _parse_ollama(d, actual_model, resolved)
    else:
        payload = _build_openai_payload(actual_model, messages, tools, num_predict)
        parse = lambda d: _parse_openai(d, actual_model, resolved)

    last_error: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        if attempt > 0:
            backoff = 0.5 * (2 ** (attempt - 1))
            logger.info(f"[LOCAL/{resolved}] retry {attempt}/{max_retries} in {backoff:.1f}s model={actual_model}")
            time.sleep(backoff)
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode())

            result = parse(data)
            if result is not None:
                cb.record_success()
                logger.info(f"[LOCAL/{resolved}] ok model={actual_model}")
                return result
            break  # empty parse — don't retry

        except (urllib.error.URLError, OSError, TimeoutError) as e:
            last_error = e
            logger.warning(
                f"[LOCAL/{resolved}] connection error attempt={attempt + 1} model={actual_model}: {e}"
            )
            cb.record_failure()
        except Exception as e:
            last_error = e
            logger.warning(f"[LOCAL/{resolved}] unexpected error attempt={attempt + 1} model={actual_model}: {e}")
            cb.record_failure()
            break

    logger.warning(f"[LOCAL/{resolved}] all attempts failed model={actual_model}: {last_error}")
    return None


def list_local_models(backend: Optional[str] = None, timeout: float = 4.0) -> List[str]:
    """Return available model names from the local backend."""
    resolved = (backend or _resolve_backend()).strip().lower()
    if resolved not in _BACKENDS:
        resolved = "ollama"
    cfg = _BACKENDS[resolved]
    url = f"{_resolve_url(resolved)}{cfg['tags_path']}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
        if cfg["format"] == "ollama":
            return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        return [m.get("id", "") for m in data.get("data", []) if m.get("id")]
    except Exception as e:
        logger.warning(f"[LOCAL/{resolved}] list_models failed: {e}")
        return []


def active_backend() -> str:
    """Return the currently resolved backend name (probes if auto)."""
    return _resolve_backend()
