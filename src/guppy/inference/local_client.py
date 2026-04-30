"""Unified local inference client — llama.cpp (ROCm/HIP) only.

All local inference routes through llama.cpp OpenAI-compatible servers.
Ollama, LM Studio, and Lemonade are not supported and not routed.

Circuit breaker: 3 consecutive failures → 30 s cooldown before retrying.
Retry: up to 2 retries with exponential backoff (0.5 s, 1.0 s).

Backend selection (GUPPY_LOCAL_RUNTIME_BACKEND env var):
  llamacpp-gemma      — Gemma 4 E4B Heretic ARA at 127.0.0.1:8080 (GUPPY_LLAMACPP_GEMMA_URL)
  llamacpp-pepe       — Assistant Pepe 8B at 127.0.0.1:8082 (GUPPY_LLAMACPP_PEPE_URL)
  llamacpp-qwen3      — Qwen3 35B-A3B MoE at 127.0.0.1:8083 (GUPPY_LLAMACPP_QWEN3_URL)
  llamacpp-minicpm    — MiniCPM-o 4.5 Omni at 127.0.0.1:8084 (GUPPY_LLAMACPP_MINICPM_URL)
  llamacpp-dispatch   — Qwen2.5-3B-Instruct dispatcher at 127.0.0.1:8085 (GUPPY_LLAMACPP_DISPATCH_URL)
  llamacpp-hermes4    — Hermes 4 14B at 127.0.0.1:8086 (GUPPY_LLAMACPP_HERMES4_URL)
  llamacpp-hermes3    — Hermes 3 8B Lorablated at 127.0.0.1:8087 (GUPPY_LLAMACPP_HERMES3_URL) [default]
  llamacpp-rocinante  — Rocinante X 12B at 127.0.0.1:8088 (GUPPY_LLAMACPP_ROCINANTE_URL)
  llamacpp-xlam       — xLAM-2-8B-fc-r at 127.0.0.1:8089  (GUPPY_LLAMACPP_XLAM_URL)
  llamacpp-chat       — Llama 3.3 70B CPU-only at 127.0.0.1:8090 (GUPPY_LLAMACPP_CHAT_URL)
  llamacpp-phi4-mini  — Phi-4-mini-instruct at 127.0.0.1:8091  (GUPPY_LLAMACPP_PHI4_MINI_URL)
  local_harness       — Generic OpenAI-compat harness at 127.0.0.1:8001 (GUPPY_LOCAL_HARNESS_BASE_URL)
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Strip text-embedded tool call markers that Qwen/Hermes-family models emit
# when structured tool_calls aren't supported by the local backend.
_TEXT_TOOL_CALL_RE = re.compile(
    r"<\|tool_call\|>.*?<\|tool_call\|>|<tool_call>.*?</tool_call>",
    re.DOTALL,
)

# ---------------------------------------------------------------------------
# Self-contained .env bootstrap for env vars this module needs.
# Runs once at import time so the module works correctly regardless of whether
# the parent process (launcher, API, test runner) has already called
# load_env_file().  Only fills vars that aren't already set.
# ---------------------------------------------------------------------------
def _bootstrap_env() -> None:
    env_file = Path(__file__).resolve().parents[3] / ".env"
    if not env_file.exists():
        return
    try:
        for raw in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and not os.environ.get(key):
                os.environ[key] = val
    except Exception:
        pass

_bootstrap_env()

_BACKENDS: Dict[str, Dict[str, Any]] = {
    # ── llama.cpp (ROCm/HIP) — one server per model, OpenAI-compatible ────────
    "llamacpp-gemma": {
        "default_url": "http://127.0.0.1:8080",
        "chat_path": "/v1/chat/completions",
        "tags_path": "/v1/models",
        "pull_path": None,
        "delete_path": None,
        "format": "openai",
    },
    "llamacpp-qwen3": {
        "default_url": "http://127.0.0.1:8083",
        "chat_path": "/v1/chat/completions",
        "tags_path": "/v1/models",
        "pull_path": None,
        "delete_path": None,
        "format": "openai",
    },
    "llamacpp-pepe": {
        "default_url": "http://127.0.0.1:8082",
        "chat_path": "/v1/chat/completions",
        "tags_path": "/v1/models",
        "pull_path": None,
        "delete_path": None,
        "format": "openai",
    },
    # ── MiniCPM-o 4.5 Omni (vision + speech, needs --mmproj) ────────────────
    "llamacpp-minicpm": {
        "default_url": "http://127.0.0.1:8084",
        "chat_path": "/v1/chat/completions",
        "tags_path": "/v1/models",
        "pull_path": None,
        "delete_path": None,
        "format": "openai",
    },
    # ── Qwen2.5-3B-Instruct dispatcher (tiny orchestrator, always-on Mode A) ──
    "llamacpp-dispatch": {
        "default_url": "http://127.0.0.1:8085",
        "chat_path": "/v1/chat/completions",
        "tags_path": "/v1/models",
        "pull_path": None,
        "delete_path": None,
        "format": "openai",
    },
    # ── Hermes 4 14B — tool-capable, uncensored, NousResearch ────────────────
    "llamacpp-hermes4": {
        "default_url": "http://127.0.0.1:8086",
        "chat_path": "/v1/chat/completions",
        "tags_path": "/v1/models",
        "pull_path": None,
        "delete_path": None,
        "format": "openai",
    },
    # ── Hermes 3 8B Lorablated — fast, uncensored, tool-capable ──────────────
    "llamacpp-hermes3": {
        "default_url": "http://127.0.0.1:8087",
        "chat_path": "/v1/chat/completions",
        "tags_path": "/v1/models",
        "pull_path": None,
        "delete_path": None,
        "format": "openai",
    },
    # ── Rocinante X 12B — creative writing / roleplay, Mistral-Nemo base ─────
    "llamacpp-rocinante": {
        "default_url": "http://127.0.0.1:8088",
        "chat_path": "/v1/chat/completions",
        "tags_path": "/v1/models",
        "pull_path": None,
        "delete_path": None,
        "format": "openai",
    },
    # ── xLAM-2-8B-fc-r — Salesforce, #1 BFCL V4 for size, pure tool-calling ──
    "llamacpp-xlam": {
        "default_url": "http://127.0.0.1:8089",
        "chat_path": "/v1/chat/completions",
        "tags_path": "/v1/models",
        "pull_path": None,
        "delete_path": None,
        "format": "openai",
    },
    # ── Llama 3.3 70B — CPU-only flagship chat (zero VRAM) ───────────────────
    "llamacpp-chat": {
        "default_url": "http://127.0.0.1:8090",
        "chat_path": "/v1/chat/completions",
        "tags_path": "/v1/models",
        "pull_path": None,
        "delete_path": None,
        "format": "openai",
    },
    # ── Phi-4-mini-instruct — true JSON tool_call dispatch orchestrator ───────
    "llamacpp-phi4-mini": {
        "default_url": "http://127.0.0.1:8091",
        "chat_path": "/v1/chat/completions",
        "tags_path": "/v1/models",
        "pull_path": None,
        "delete_path": None,
        "format": "openai",
    },
    # ── Generic local harness (any OpenAI-compat server) ─────────────────────
    "local_harness": {
        "default_url": "http://127.0.0.1:8001",
        "chat_path": "/v1/chat/completions",
        "tags_path": "/v1/models",
        "pull_path": None,
        "delete_path": None,
        "format": "openai",
    },
}

_ENV_URL_KEYS: Dict[str, str] = {
    "llamacpp-gemma":    "GUPPY_LLAMACPP_GEMMA_URL",
    "llamacpp-qwen3":    "GUPPY_LLAMACPP_QWEN3_URL",
    "llamacpp-pepe":     "GUPPY_LLAMACPP_PEPE_URL",
    "llamacpp-minicpm":    "GUPPY_LLAMACPP_MINICPM_URL",
    "llamacpp-dispatch":   "GUPPY_LLAMACPP_DISPATCH_URL",
    "llamacpp-hermes4":    "GUPPY_LLAMACPP_HERMES4_URL",
    "llamacpp-hermes3":    "GUPPY_LLAMACPP_HERMES3_URL",
    "llamacpp-rocinante":  "GUPPY_LLAMACPP_ROCINANTE_URL",
    "llamacpp-xlam":       "GUPPY_LLAMACPP_XLAM_URL",
    "llamacpp-chat":       "GUPPY_LLAMACPP_CHAT_URL",
    "llamacpp-phi4-mini":  "GUPPY_LLAMACPP_PHI4_MINI_URL",
    "local_harness":       "GUPPY_LOCAL_HARNESS_BASE_URL",
}

# Model-name → backend routing for llamacpp servers.
# Allows local_chat(model="gemma-4-heretic-ara") without specifying backend=.
_LLAMACPP_MODEL_ROUTE: Dict[str, str] = {
    "gemma-4-heretic-ara":      "llamacpp-gemma",
    "gemma-4-e4b-heretic":      "llamacpp-gemma",
    "qwen3-35b-uncensored":     "llamacpp-qwen3",
    "qwen3-35b":                "llamacpp-qwen3",
    "qwen3-moe":                "llamacpp-qwen3",
    "assistant-pepe-8b":        "llamacpp-pepe",
    "pepe-8b":                  "llamacpp-pepe",
    "pepe":                     "llamacpp-pepe",
    # MiniCPM-o 4.5 — omni vision+speech
    "minicpm-o-4.5":            "llamacpp-minicpm",
    "minicpm-o":                "llamacpp-minicpm",
    "minicpm":                  "llamacpp-minicpm",
    "minicpm-omni":             "llamacpp-minicpm",
    # Qwen2.5-3B-Instruct — lightweight orchestrator / dispatcher
    "qwen2.5-3b-instruct":      "llamacpp-dispatch",
    "qwen2.5-3b":               "llamacpp-dispatch",
    "qwen2.5-omni-3b":          "llamacpp-dispatch",  # legacy alias
    "qwen2.5-omni":             "llamacpp-dispatch",  # legacy alias
    "dispatch":                 "llamacpp-dispatch",
    "guppy-dispatch":           "llamacpp-dispatch",
    # Hermes 4 14B — tool-capable, uncensored
    "hermes-4-14b":             "llamacpp-hermes4",
    "hermes4":                  "llamacpp-hermes4",
    "hermes-4":                 "llamacpp-hermes4",
    # Hermes 3 8B Lorablated — fast, uncensored
    "hermes-3-8b-lorablated":   "llamacpp-hermes3",
    "hermes-3-8b":              "llamacpp-hermes3",
    "hermes3":                  "llamacpp-hermes3",
    "hermes-3":                 "llamacpp-hermes3",
    # Rocinante X 12B — creative writing / roleplay
    "rocinante-x-12b":          "llamacpp-rocinante",
    "rocinante-12b":            "llamacpp-rocinante",
    "rocinante":                "llamacpp-rocinante",
    # Llama-xLAM-2-8B-fc-r — Salesforce function-calling specialist (#1 BFCL V4 ≤8B)
    "llama-xlam-2-8b-fc-r":    "llamacpp-xlam",
    "llama-xlam-2-8b-fc-r-q4_k_m.gguf": "llamacpp-xlam",
    "xlam-2-8b":                "llamacpp-xlam",
    "xlam-2-8b-fc-r":          "llamacpp-xlam",
    "xlam-8b":                  "llamacpp-xlam",
    "xlam":                     "llamacpp-xlam",
    # Llama 3.3 70B Instruct -- CPU-only flagship chat (port 8090)
    "llama-3.3-70b-instruct":   "llamacpp-chat",
    "llama-3.3-70b":            "llamacpp-chat",
    "llama-70b":                "llamacpp-chat",
    "chat-70b":                 "llamacpp-chat",
    # Phi-4-mini-instruct -- true JSON tool_call dispatch orchestrator (port 8091)
    "phi-4-mini-instruct":      "llamacpp-phi4-mini",
    "phi-4-mini":               "llamacpp-phi4-mini",
    "phi4-mini":                "llamacpp-phi4-mini",
    "phi4":                     "llamacpp-phi4-mini",
    # Self-referential backend-key aliases so surface_config keys work as mode values
    "llamacpp-gemma":           "llamacpp-gemma",
    "llamacpp-qwen3":           "llamacpp-qwen3",
    "llamacpp-pepe":            "llamacpp-pepe",
    "llamacpp-minicpm":         "llamacpp-minicpm",
    "llamacpp-dispatch":        "llamacpp-dispatch",
    "llamacpp-hermes4":         "llamacpp-hermes4",
    "llamacpp-hermes3":         "llamacpp-hermes3",
    "llamacpp-rocinante":       "llamacpp-rocinante",
    "llamacpp-xlam":            "llamacpp-xlam",
    "llamacpp-chat":            "llamacpp-chat",
    "llamacpp-phi4-mini":       "llamacpp-phi4-mini",
}

# Canonical model name for each llamacpp backend (first/preferred alias).
# Used by the registry and router when they know the backend but not the model name.
_BACKEND_DEFAULT_MODELS: Dict[str, str] = {
    "llamacpp-gemma":      "gemma-4-heretic-ara",
    "llamacpp-qwen3":      "qwen3-35b-uncensored",
    "llamacpp-pepe":       "assistant-pepe-8b",
    "llamacpp-minicpm":    "minicpm-o-4.5",
    "llamacpp-dispatch":   "qwen2.5-3b-instruct",
    "llamacpp-hermes4":    "hermes-4-14b",
    "llamacpp-hermes3":    "hermes-3-8b-lorablated",
    "llamacpp-rocinante":  "rocinante-x-12b",
    "llamacpp-xlam":       "Llama-xLAM-2-8B-fc-r-Q4_K_M.gguf",
    "llamacpp-chat":       "Llama-3.3-70B-Instruct-Q4_K_M.gguf",
    "llamacpp-phi4-mini":  "Phi-4-mini-instruct-Q4_K_M.gguf",
    "local_harness":       "local-model",
}

_DEFAULT_BACKEND = "llamacpp-hermes3" if "llamacpp-hermes3" in _BACKENDS else "local_harness"
_AUTO_PROBE_PREFERENCE = (
    "llamacpp-hermes3",
    "local_harness",
    "llamacpp-dispatch",
    "llamacpp-hermes4",
    "llamacpp-qwen3",
    "llamacpp-gemma",
    "llamacpp-pepe",
    "llamacpp-minicpm",
    "llamacpp-rocinante",
    "llamacpp-xlam",
    "llamacpp-chat",
    "llamacpp-phi4-mini",
)

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
_AUTO_PROBE_ORDER = tuple(name for name in _AUTO_PROBE_PREFERENCE if name in _BACKENDS)


def _probe_headers(name: str) -> Dict[str, str]:
    """Build probe headers for OpenAI-compatible local servers."""
    return {"Accept": "application/json"}


def _probe_backends(timeout: float = 1.5) -> str:
    """Ping each backend in order; return the first that responds."""
    for name in _AUTO_PROBE_ORDER:
        cfg = _BACKENDS.get(name)
        if not cfg:
            continue
        url = f"{_resolve_url(name)}{cfg['tags_path']}"
        try:
            req = urllib.request.Request(url, headers=_probe_headers(name), method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                r.read()
            logger.info(f"[LOCAL/auto] detected backend: {name}")
            return name
        except Exception:
            continue
    logger.info("[LOCAL/auto] no backend detected, defaulting to %s", _DEFAULT_BACKEND)
    return _DEFAULT_BACKEND


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
    if raw in _BACKENDS:
        return raw
    logger.info("[LOCAL] unsupported backend '%s', defaulting to %s", raw, _DEFAULT_BACKEND)
    return _DEFAULT_BACKEND


_probe_cache: Dict[str, Any] = {}
_probe_cache_lock = threading.Lock()
_PROBE_TTL_UP   = 12.0   # cache "alive"  for 12 s
_PROBE_TTL_DOWN =  5.0   # cache "down"   for  5 s (detect startup faster)


def probe_backends(timeout: float = 1.5) -> Dict[str, bool]:
    """Return liveness dict for all backends — useful for status/debug endpoints.

    Results are cached per-backend with a short TTL so rapid consecutive calls
    (e.g. every /providers request) don't each incur a full connection timeout.
    """
    now = time.monotonic()
    result: Dict[str, bool] = {}
    for name, cfg in _BACKENDS.items():
        with _probe_cache_lock:
            cached = _probe_cache.get(name)
            if cached and now < cached[1]:
                result[name] = cached[0]
                continue

        url = f"{_resolve_url(name)}{cfg['tags_path']}"
        try:
            req = urllib.request.Request(url, headers=_probe_headers(name), method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                r.read()
            alive = True
        except Exception as e:
            logger.debug(f"[LOCAL/probe] {name} unreachable at {url}: {e}")
            alive = False

        ttl = _PROBE_TTL_UP if alive else _PROBE_TTL_DOWN
        with _probe_cache_lock:
            _probe_cache[name] = (alive, now + ttl)
        result[name] = alive
    return result


# ── LM Studio model resolution ────────────────────────────────────────────────

_lmstudio_model_cache: Dict[str, Any] = {"models": [], "expires_at": 0.0}
_lmstudio_cache_lock = threading.Lock()


def _get_lmstudio_models(timeout: float = 2.0) -> List[str]:
    """Return LM Studio model IDs.

    LM Studio is no longer a routed local backend. Keep this compatibility
    shim side-effect free so legacy callers do not fall into a removed backend.
    """
    return []


def _get_lmstudio_loaded_model() -> Optional[str]:
    """Return the loaded LM Studio model, if that backend is supported."""
    return None


def _resolve_lmstudio_model(requested: str) -> str:
    """Compatibility shim for legacy imports; LM Studio is not routed."""
    return requested


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


def _parse_openai(data: Dict[str, Any], model: str, backend: str) -> Optional[Dict[str, Any]]:
    choices = data.get("choices", []) if isinstance(data, dict) else []
    if not choices:
        return None
    msg = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
    content = str(msg.get("content") or "")
    # Reasoning models (e.g. gemma-4, nemotron) put chain-of-thought in reasoning_content;
    # visible answer goes in content. If content is empty the model ran out of tokens mid-think.
    if not content.strip():
        content = str(msg.get("reasoning_content") or "")
    # Strip text-embedded tool call markers (<|tool_call|>...<|tool_call|> or
    # <tool_call>...</tool_call>) that Qwen/Hermes-family models emit when they
    # can't use structured tool_calls.  These must never reach the UI as raw text.
    content = _TEXT_TOOL_CALL_RE.sub("", content).strip()
    return {
        "response": content,
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
    """
    resolved = (backend or _resolve_backend()).strip().lower()
    if resolved not in _BACKENDS:
        # Try routing by model name (covers llamacpp-* servers)
        resolved = _LLAMACPP_MODEL_ROUTE.get(model.strip().lower(), _DEFAULT_BACKEND)

    cb = _get_cb(resolved)
    if cb.is_open:
        logger.warning(f"[LOCAL/{resolved}] circuit breaker OPEN — skipping {model}")
        return None

    actual_model = model

    cfg = _BACKENDS[resolved]
    url = f"{_resolve_url(resolved)}{cfg['chat_path']}"
    payload = _build_openai_payload(actual_model, messages, tools, num_predict)

    def parse(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return _parse_openai(data, actual_model, resolved)

    last_error: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        if attempt > 0:
            backoff = 0.5 * (2 ** (attempt - 1))
            logger.info(f"[LOCAL/{resolved}] retry {attempt}/{max_retries} in {backoff:.1f}s model={actual_model}")
            time.sleep(backoff)
        try:
            headers: Dict[str, str] = {"Content-Type": "application/json"}
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode(),
                headers=headers,
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

        except urllib.error.HTTPError as e:
            last_error = e
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                body = ""
            if re.search(
                r"out of memory|cudaMalloc failed|hipMalloc failed|"
                r"CUDA error.*memory|HIP error.*memory|ggml_cuda_pool_alloc|"
                r"failed to allocate|memory.*exhausted",
                body,
                re.IGNORECASE,
            ):
                logger.error(
                    "[LOCAL/%s] OOM — model=%s. Restart server or reduce context. body=%s",
                    resolved, actual_model, body[:200],
                )
            else:
                logger.warning(
                    f"[LOCAL/{resolved}] HTTP {e.code} attempt={attempt + 1} model={actual_model}: {e}"
                )
            cb.record_failure()
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


_models_cache: Dict[str, Any] = {}
_models_cache_lock = threading.Lock()
_MODELS_TTL = 15.0   # cache model list for 15 s


def list_local_models(backend: Optional[str] = None, timeout: float = 4.0) -> List[str]:
    """Return available model names from the local backend.

    Results are cached for 15 s per backend so repeated /providers polls don't
    each incur a full round-trip to the local OpenAI-compatible server.
    """
    resolved = (backend or _resolve_backend()).strip().lower()
    if resolved not in _BACKENDS:
        resolved = _DEFAULT_BACKEND

    now = time.monotonic()
    with _models_cache_lock:
        cached = _models_cache.get(resolved)
        if cached and now < cached[1]:
            return list(cached[0])

    cfg = _BACKENDS[resolved]
    url = f"{_resolve_url(resolved)}{cfg['tags_path']}"
    models: List[str] = []
    try:
        headers = _probe_headers(resolved)
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
        if "models" in data:
            models = [m.get("key", m.get("id", "")) for m in data.get("models", []) if m.get("key") or m.get("id")]
        else:
            models = [m.get("id", "") for m in data.get("data", []) if m.get("id")]
    except Exception as e:
        logger.warning(f"[LOCAL/{resolved}] list_models failed: {e}")
        models = []

    with _models_cache_lock:
        _models_cache[resolved] = (models, now + _MODELS_TTL)
    return list(models)


def active_backend() -> str:
    """Return the currently resolved backend name (probes if auto)."""
    return _resolve_backend()
