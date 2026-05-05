"""Shared routing utilities and constants for surface/task-type routers.

Imported by router_surface and router_task_types to avoid circular imports
with realtime_inference_support (which also imports those router modules).
The definitions here are intentional copies of the equivalents in
realtime_inference_support; the originals remain there for backward compat.
"""
from __future__ import annotations

import json as _json
import logging
import sqlite3
from typing import Any

_log = logging.getLogger(__name__)

# ── Streaming sentinels ───────────────────────────────────────────────────────
_TOOL_CALL_SENTINEL = "\x00TOOL_CALLS:"
_REPLACE_SENTINEL = "\x00REPLACE:"
_SOURCE_SENTINEL = "\x00SOURCE:"

# ── Free-tier cloud provider constants ────────────────────────────────────────
_MISTRAL_MODEL_IDS: frozenset = frozenset({
    "mistral-large-latest", "mistral-medium-latest", "mistral-small-latest",
    "codestral-latest", "ministral-8b-latest", "ministral-3b-latest",
    "open-mistral-nemo", "pixtral-large-latest", "pixtral-12b-2409",
    "open-mixtral-8x22b",
})
_COHERE_MODEL_IDS: frozenset = frozenset({
    "command-a-03-2025", "command-r-plus-08-2024", "command-r-08-2024",
    "command-r7b-12-2024", "command-light", "aya-23-35b", "aya-23-8b",
})
_FREE_MISTRAL_MODEL = "ministral-8b-latest"
_FREE_COHERE_MODEL  = "command-r7b-12-2024"

# ── History / chat constants ──────────────────────────────────────────────────
_CHAT_CONTENT_MAX_CHARS = 2000
_CHAT_HISTORY_LIMIT = 12
_BACKEND_CONTEXT_TOKENS: dict[str, int] = {
    "llamacpp-hermes3":    8192,
    "llamacpp-hermes4":   49152,
    "llamacpp-dispatch":   4096,
    "llamacpp-phi4-mini": 131072,
    "llamacpp-pepe":       8192,
    "llamacpp-rocinante": 16384,
    "llamacpp-xlam":       8192,
    "llamacpp-minicpm":    8192,
    "llamacpp-qwen3":     40960,
    "llamacpp-chat":      32768,
    "llamacpp-gemma":      8192,
}
_DEFAULT_CONTEXT_TOKENS = 8192
_CONTEXT_RESERVE_TOKENS = 1024
_CHARS_PER_TOKEN = 4


def _trim_history_to_tokens(
    history: list[dict[str, str]],
    backend: str | None,
    limit: int = _CHAT_HISTORY_LIMIT,
) -> list[dict[str, str]]:
    max_tokens = _BACKEND_CONTEXT_TOKENS.get(backend or "", _DEFAULT_CONTEXT_TOKENS)
    budget_chars = (max_tokens - _CONTEXT_RESERVE_TOKENS) * _CHARS_PER_TOKEN
    capped = history[-max(1, limit):]
    while capped:
        total = sum(len(m.get("content", "")) for m in capped)
        if total <= budget_chars:
            break
        capped = capped[1:]
    return capped


def sanitize_chat_history(
    history: Any,
    limit: int = _CHAT_HISTORY_LIMIT,
    backend: str | None = None,
) -> list[dict[str, str]]:
    if not isinstance(history, list):
        return []
    out: list[dict[str, str]] = []
    for item in history:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if role not in {"user", "assistant"} or not content:
            continue
        out.append({"role": role, "content": content[:_CHAT_CONTENT_MAX_CHARS]})
    return _trim_history_to_tokens(out, backend=backend, limit=limit)


def build_router_messages(
    system_prompt: str, user_text: str, history: list[dict[str, str]]
) -> list[dict[str, str]]:
    trimmed = list(history)
    if (
        trimmed
        and trimmed[-1].get("role") == "user"
        and trimmed[-1].get("content", "").strip() == user_text.strip()
    ):
        trimmed = trimmed[:-1]
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(trimmed)
    messages.append({"role": "user", "content": user_text})
    return messages


def _to_openai_tools(anthropic_tools: Any) -> list[dict]:
    result = []
    for tool in (anthropic_tools or []):
        if isinstance(tool, dict):
            name = str(tool.get("name") or "")
            desc = str(tool.get("description") or "")
            params = tool.get("input_schema", {})
        else:
            name = str(getattr(tool, "name", "") or "")
            desc = str(getattr(tool, "description", "") or "")
            params = getattr(tool, "input_schema", {})
            if not isinstance(params, dict):
                try:
                    params = dict(params)
                except Exception:
                    params = {}
        if not name:
            continue
        result.append({
            "type": "function",
            "function": {
                "name": name,
                "description": desc,
                "parameters": params if isinstance(params, dict) else {},
            },
        })
    return result


def _get_db_tools_openai() -> list[dict]:
    try:
        from src.guppy.paths import MAIN_DB_PATH
        db_path = str(MAIN_DB_PATH)
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, name, description, parameters FROM tools WHERE is_enabled = 1"
            ).fetchall()
        result = []
        for row in rows:
            try:
                params = _json.loads(row["parameters"] or "{}")
            except Exception:
                params = {}
            result.append({
                "type": "function",
                "function": {
                    "name": row["id"],
                    "description": row["description"],
                    "parameters": params,
                },
            })
        return result
    except Exception as exc:
        _log.debug("_get_db_tools_openai failed: %s", exc)
        return []


def _merged_openai_tools(owner: Any) -> list[dict] | None:
    core = _to_openai_tools(getattr(getattr(owner, "core", None), "TOOLS", None) or []) \
        if getattr(owner, "GUPPY_CORE_AVAILABLE", False) else []
    db = _get_db_tools_openai()
    if not core and not db:
        return None
    core_names = {t["function"]["name"] for t in core}
    merged = core + [t for t in db if t["function"]["name"] not in core_names]
    return merged or None


def _get_cloud_api_key(provider: str, owner: Any) -> str:
    """Return API key for provider: env var first, then settings DB."""
    _env_map = {
        "mistral":   "MISTRAL_API_KEY",
        "cohere":    "COHERE_API_KEY",
        "google":    "GOOGLE_API_KEY",
        "openai":    "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }
    key = owner.os.environ.get(_env_map.get(provider, ""), "").strip()
    if key:
        return key
    try:
        from src.guppy.api.routes_settings import _settings_db
        return _settings_db.get_credential(provider) or ""
    except Exception:
        return ""
