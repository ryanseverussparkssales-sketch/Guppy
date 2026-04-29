from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any, AsyncGenerator, Optional

import re as _re

from src.guppy.inference.local_client import (
    _LLAMACPP_MODEL_ROUTE as _LOCAL_LLAMACPP_ROUTES,
    _BACKENDS as _LOCAL_BACKENDS,
    _BACKEND_DEFAULT_MODELS as _LOCAL_BACKEND_DEFAULT_MODELS,
    _resolve_url as _local_resolve_url,
)

# Strip raw text-embedded tool call blocks that some local models emit when they
# can't use (or don't parse) structured tool_calls.  Two common formats:
#
#   Hermes / Gemma:   <tool_call>call:name{args}</tool_call>
#   Qwen / Pepe:      <|tool_call|>call:name{args}<|tool_call|>
#
# The pipe-delimited variant uses special tokenizer boundary tokens that look
# like angle-bracket tags but aren't HTML.  Both must be stripped so they
# never reach the user as visible response text.
_TOOL_CALL_TAG_RE = _re.compile(
    r"<\|tool_call\|>.*?<\|tool_call\|>"   # Qwen3 / Pepe pipe-variant
    r"|<tool_call>.*?</tool_call>",          # Hermes / Gemma tag-variant
    _re.DOTALL,
)

_TOOL_CALLS_ONLY_RE = _re.compile(
    r"^\s*(<\|tool_call\|>.*?<\|tool_call\|>\s*|<tool_call>.*?</tool_call>\s*)+$",
    _re.DOTALL,
)

_NO_TOOLS_FALLBACK = (
    "I don't have access to live tools in local mode. "
    "Ask me to answer from my training knowledge, or switch to a cloud model "
    "(Anthropic / OpenAI) for tool-enabled responses."
)


def _strip_tool_call_markers(text: str) -> str:
    """Remove raw text-embedded tool call blocks from a model response.

    Returns the cleaned text (may be empty string if the whole response was
    a tool call block).
    """
    return _TOOL_CALL_TAG_RE.sub("", text).strip()


def _clean_local_response(text: str) -> str:
    """Strip tool call markup and return a user-friendly string.

    Applied to non-streaming local model (llamacpp and Ollama) responses when
    the model tries to invoke tools via text delimiters instead of the
    structured tool_calls field.
    """
    cleaned = _strip_tool_call_markers(text)
    if cleaned == text.strip():
        return text  # nothing was stripped — return unchanged
    if not cleaned:
        return _NO_TOOLS_FALLBACK
    return (
        cleaned
        + "\n\n_(Note: tool calls are not supported in local mode — "
        "this answer is based on the model's training knowledge only.)_"
    )


# Keep the old name as an alias so existing call-sites don't break.
_clean_llamacpp_response = _clean_local_response


def _to_openai_tools(anthropic_tools: Any) -> list[dict]:
    """Convert Anthropic-format tool definitions to OpenAI/llamacpp JSON format.

    Anthropic uses ``input_schema``; OpenAI/llamacpp uses ``parameters`` inside
    ``{"type": "function", "function": {...}}``.  Handles both plain dicts and
    Anthropic SDK ``ToolParam`` objects.
    """
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
            # Coerce SDK model objects to plain dicts
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

_log = logging.getLogger(__name__)

_CHAT_CONTENT_MAX_CHARS = 2000


def _get_db_tools_openai() -> list[dict]:
    """Load enabled tools from tools.db and return them in OpenAI function-call format.

    Used as a fallback/supplement when owner.core.TOOLS is empty or unavailable.
    """
    try:
        import sqlite3
        import json as _json
        from src.guppy.paths import ensure_user_data_dir
        db_path = str(ensure_user_data_dir() / "tools.db")
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
    """Merge guppy_core.TOOLS + all enabled db tools, deduplicated by function name.

    core.TOOLS only contains tools the C++ core was compiled with or auto-discovered
    at startup.  The tools.db may have additional enabled tools (calibre, gutenberg,
    screenpipe, etc.) that the core can execute but didn't register in its catalog.
    Merging both sources ensures the model sees and can call ALL available tools.
    """
    core = _to_openai_tools(getattr(getattr(owner, "core", None), "TOOLS", None) or []) \
        if getattr(owner, "GUPPY_CORE_AVAILABLE", False) else []
    db = _get_db_tools_openai()
    if not core and not db:
        return None
    core_names = {t["function"]["name"] for t in core}
    merged = core + [t for t in db if t["function"]["name"] not in core_names]
    return merged or None


_HISTORY_SNIPPET_MAX_CHARS = 240
_HISTORY_TURNS_SHOWN = 8
_CHAT_HISTORY_LIMIT = 12


def sanitize_chat_history(history: Any, limit: int = _CHAT_HISTORY_LIMIT) -> list[dict[str, str]]:
    if not isinstance(history, list):
        return []
    out: list[dict[str, str]] = []
    for item in history[-max(1, limit):]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if role not in {"user", "assistant"} or not content:
            continue
        out.append({"role": role, "content": content[:_CHAT_CONTENT_MAX_CHARS]})
    return out


def extract_text_from_anthropic_blocks(blocks) -> str:
    parts = []
    for block in blocks:
        if getattr(block, "type", None) == "text" and getattr(block, "text", "").strip():
            parts.append(block.text.strip())
    return "\n".join(parts).strip()


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


def augment_system_with_history(system_prompt: str, history: list[dict[str, str]]) -> str:
    if not history:
        return system_prompt
    lines = ["LIVE SESSION HISTORY (RECENT TURNS):"]
    for item in history[-_HISTORY_TURNS_SHOWN:]:
        speaker = "Ryan" if item.get("role") == "user" else "Guppy"
        snippet = item.get("content", "").replace("\n", " ").strip()
        if len(snippet) > _HISTORY_SNIPPET_MAX_CHARS:
            snippet = snippet[:_HISTORY_SNIPPET_MAX_CHARS] + "..."
        lines.append(f"- {speaker}: {snippet}")
    return f"{system_prompt}\n\n" + "\n".join(lines)


def is_rate_limited_error(error: Exception | str) -> bool:
    txt = str(error or "").lower()
    return "429" in txt or "rate limit" in txt or "too many requests" in txt


def _is_transient_inference_error(exc: Exception) -> bool:
    txt = str(exc).lower()
    return any(k in txt for k in ("timeout", "timed out", "connection reset", "temporarily unavailable", "503", "busy"))


def _with_single_retry(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Call fn(*args, **kwargs), retry once after 1s on transient errors."""
    import time as _time
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        if _is_transient_inference_error(exc):
            _time.sleep(1.0)
            return fn(*args, **kwargs)
        raise


def _inject_semantic_context(system_prompt: str, user_text: str, owner: Any) -> str:
    """Append relevant ChromaDB/SQLite semantic memory to the system prompt."""
    if not (owner.os.environ.get("GUPPY_SEMANTIC_RAG", "1").strip().lower() in {"1", "true", "yes", "on"}):
        return system_prompt
    try:
        from src.guppy.memory.semantic import build_semantic_prompt_context
        ctx = build_semantic_prompt_context(user_text, n=4)
        if ctx:
            return f"{system_prompt}\n\n{ctx}"
    except Exception as exc:
        _log.debug("Semantic context injection failed: %s", exc)
    return system_prompt


async def _inject_semantic_context_async(system_prompt: str, user_text: str, owner: Any) -> str:
    """Async wrapper — runs the synchronous ChromaDB/SQLite read in a thread pool."""
    import asyncio
    return await asyncio.to_thread(_inject_semantic_context, system_prompt, user_text, owner)


# ── Tool-list injection ────────────────────────────────────────────────────────

def _build_tool_context(owner: Any) -> str:
    """Return a compact AVAILABLE TOOLS block from the owner's tool catalog.

    Only the first sentence of each description is included to keep the prompt
    token-efficient. Returns an empty string when tools are unavailable.
    """
    if not getattr(owner, "GUPPY_CORE_AVAILABLE", False):
        return ""
    tools = getattr(getattr(owner, "core", None), "TOOLS", None)
    if not tools:
        return ""
    lines = [
        "AVAILABLE TOOLS:",
        "Only call a tool when the user's request explicitly requires it.",
        "For general knowledge, news, or conversational questions, answer directly — do NOT call any tool.",
    ]
    for tool in tools:
        if isinstance(tool, dict):
            name = str(tool.get("name") or "").strip()
            desc = str(tool.get("description") or "").strip()
        else:
            name = str(getattr(tool, "name", "") or "").strip()
            desc = str(getattr(tool, "description", "") or "").strip()
        if not name:
            continue
        first_sentence = desc.split(".")[0].strip() if desc else ""
        lines.append(f"- {name}: {first_sentence}" if first_sentence else f"- {name}")
    return "\n".join(lines) if len(lines) > 1 else ""


# ── Workspace filesystem snapshot ─────────────────────────────────────────────

import os as _os
import time as _time
from pathlib import Path as _Path

_FS_SNAPSHOT_CACHE: dict[str, tuple[float, str]] = {}
_FS_SNAPSHOT_TTL = 30.0  # seconds
_FS_MAX_ENTRIES = 60
_FS_MAX_DEPTH = 2
_FS_SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build",
    ".tmp", "static", "coverage", ".eggs",
}
_FS_CODE_EXTS = {
    ".py", ".ts", ".tsx", ".js", ".jsx",
    ".json", ".yaml", ".yml", ".toml",
    ".md", ".txt", ".bat", ".ps1", ".sh",
    ".cfg", ".ini", ".env", ".sql",
}


def _scan_workspace_sync(directory: str) -> str:
    """Return a compact depth-limited file tree of *directory*, cached by TTL.

    Skips non-code files and common build/cache directories to keep the
    injected context token-efficient.
    """
    now = _time.monotonic()
    cached = _FS_SNAPSHOT_CACHE.get(directory)
    if cached and (now - cached[0]) < _FS_SNAPSHOT_TTL:
        return cached[1]

    root = _Path(directory)
    if not root.is_dir():
        _FS_SNAPSHOT_CACHE[directory] = (now, "")
        return ""

    entries: list[str] = []
    try:
        for dirpath, dirnames, filenames in _os.walk(root, topdown=True):
            depth = len(_Path(dirpath).relative_to(root).parts)
            if depth >= _FS_MAX_DEPTH:
                dirnames.clear()
                continue
            dirnames[:] = sorted(
                d for d in dirnames
                if d not in _FS_SKIP_DIRS and not d.startswith(".")
            )
            indent = "  " * depth
            rel = _Path(dirpath).relative_to(root)
            if depth > 0:
                entries.append(f"{indent}{rel.name}/")
            child_indent = "  " * (depth + 1)
            for fname in sorted(filenames):
                if _Path(fname).suffix.lower() in _FS_CODE_EXTS:
                    entries.append(f"{child_indent}{fname}")
            if len(entries) >= _FS_MAX_ENTRIES:
                entries.append("  ... (truncated)")
                break
    except (PermissionError, OSError):
        pass

    if not entries:
        _FS_SNAPSHOT_CACHE[directory] = (now, "")
        return ""

    result = (
        f"WORKSPACE FILE TREE ({directory}) — background context only.\n"
        "Reference this only when the user's request involves specific files or code.\n"
        "Do NOT explore or list these files unless explicitly asked to.\n"
        + "\n".join(entries[:_FS_MAX_ENTRIES])
    )
    _FS_SNAPSHOT_CACHE[directory] = (now, result)
    return result


def _inject_workspace_context_sync(system_prompt: str, owner: Any) -> str:
    """Inject tool list + filesystem snapshot into the system prompt.

    Workspace directory priority:
      1. GUPPY_WORKSPACE_DIR env var
      2. Current working directory (where Guppy was launched)
    """
    parts = [system_prompt]

    tool_ctx = _build_tool_context(owner)
    if tool_ctx:
        parts.append(tool_ctx)

    workspace_dir = (
        owner.os.environ.get("GUPPY_WORKSPACE_DIR", "").strip()
        or str(_Path.home())
    )
    fs_ctx = _scan_workspace_sync(workspace_dir)
    if fs_ctx:
        parts.append(fs_ctx)

    return "\n\n".join(parts)


async def _inject_workspace_context_async(system_prompt: str, owner: Any) -> str:
    """Async wrapper — filesystem walk runs in a thread pool."""
    import asyncio
    return await asyncio.to_thread(_inject_workspace_context_sync, system_prompt, owner)


def call_unified_inference(
    owner: Any,
    user_text: str,
    system_prompt: str,
    mode: Optional[str] = None,
    history: Optional[list[dict[str, str]]] = None,
    instance_name: Optional[str] = None,
    instance_type: Optional[str] = None,
    active_local_model: Optional[str] = None,
    active_cloud_model: Optional[str] = None,
) -> str:
    if not owner.GUPPY_CORE_AVAILABLE:
        raise RuntimeError("Guppy core not available.")

    if not owner.INFERENCE_ROUTER_AVAILABLE:
        if owner.os.environ.get("ANTHROPIC_API_KEY"):
            owner.logger.warning("Router unavailable, falling back to Claude")
            return owner._call_claude_with_tools(
                user_text,
                system_prompt,
                instance_name=instance_name,
                instance_type=instance_type,
            )
        raise RuntimeError(
            "Inference router unavailable and no ANTHROPIC_API_KEY set. "
            "Start Ollama (port 11434) or LM Studio (port 1234) first."
        )

    router = owner.get_router()
    clean_history = sanitize_chat_history(history)
    augmented_system_prompt = augment_system_with_history(system_prompt, clean_history)
    augmented_system_prompt = _inject_semantic_context(augmented_system_prompt, user_text, owner)
    augmented_system_prompt = _inject_workspace_context_sync(augmented_system_prompt, owner)
    router_messages = build_router_messages(augmented_system_prompt, user_text, clean_history)
    requested_mode = (
        mode or owner.os.environ.get("GUPPY_DEFAULT_MODE", "auto") or "auto"
    ).strip().lower()

    # Steer mode: user is correcting or redirecting — surface that context, then
    # route normally so the best available model responds.
    if requested_mode == "steer":
        augmented_system_prompt = (
            "The user's next message is a steering directive or correction. "
            "Adjust your approach and direction accordingly, "
            "then continue helpfully from where you left off.\n\n"
        ) + augmented_system_prompt
        requested_mode = "auto"

    # If the user explicitly selected a llama.cpp model AND it's reachable, force
    # local routing so the router doesn't escalate to cloud in "auto" mode.
    # If the backend isn't running, keep "auto" so Ollama is tried instead —
    # this prevents a hard 500 when the saved model selection is stale.
    if active_local_model and active_local_model in _LOCAL_LLAMACPP_ROUTES and requested_mode in {"auto", ""}:
        from src.guppy.api.routes_backends import _port_alive as _llc_port_alive
        _backend_name = _LOCAL_LLAMACPP_ROUTES.get(active_local_model, "")
        _backend_url  = (_LOCAL_BACKENDS.get(_backend_name) or {}).get("default_url", "")
        _backend_port = int(_backend_url.rsplit(":", 1)[-1]) if ":" in _backend_url else 0
        if _backend_port and _llc_port_alive(_backend_port):
            requested_mode = "local"
        # else: backend offline — fall through as "auto" so Ollama is used

    # Track whether the active model is a llamacpp-backed key (used in the except block)
    is_llamacpp = bool(active_local_model and active_local_model in _LOCAL_LLAMACPP_ROUTES)

    try:
        if requested_mode == "local":
            response, source, metadata = _with_single_retry(
                _run_local_mode,
                owner=owner,
                router=router,
                user_text=user_text,
                augmented_system_prompt=augmented_system_prompt,
                router_messages=router_messages,
                instance_name=instance_name,
                instance_type=instance_type,
                active_local_model=active_local_model,
            )
        elif requested_mode == "code":
            response, source, metadata = _with_single_retry(
                _run_code_mode,
                owner=owner,
                router=router,
                user_text=user_text,
                augmented_system_prompt=augmented_system_prompt,
                router_messages=router_messages,
            )
        else:
            response, source, metadata = _run_routed_mode(
                owner=owner,
                router=router,
                user_text=user_text,
                requested_mode=requested_mode,
                augmented_system_prompt=augmented_system_prompt,
                router_messages=router_messages,
                instance_name=instance_name,
                instance_type=instance_type,
                active_local_model=active_local_model,
                active_cloud_model=active_cloud_model,
            )

        owner.logger.info(
            "Inference completed via %s. Tokens: %s",
            source,
            metadata.get("usage", {}).get("output_tokens", "?"),
        )
        return response

    except Exception as exc:
        if requested_mode in {"local", "code", "claude", "ollama"}:
            # For local mode: if the failure came from a specific llamacpp backend that's
            # offline, try Ollama before hard-failing.  This avoids a 500 just because
            # the user's saved active_local_model points to an offline backend.
            if requested_mode == "local" and is_llamacpp:
                owner.logger.warning(
                    "llamacpp backend offline for '%s'; falling back to Ollama. Error: %s",
                    active_local_model, exc,
                )
                try:
                    return owner._call_selected_local_runtime(
                        user_text,
                        augmented_system_prompt,
                        instance_name=instance_name,
                        instance_type=instance_type,
                        model_override=None,  # let Ollama pick its default model
                    )
                except Exception as _oll_exc:
                    owner.logger.error(
                        "Ollama fallback also failed after llamacpp offline: %s", _oll_exc
                    )
                    # fall through to the hard raise below
            owner.logger.error("Inference failed in explicit mode '%s': %s", requested_mode, exc)
            raise
        if not owner.os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                f"Local inference failed ({exc}). "
                "Start Ollama (port 11434) or LM Studio (port 1234) and try again."
            ) from exc
        owner.logger.error("Unified inference failed: %s. Escalating to Claude Sonnet.", exc)
        try:
            return owner._call_claude_with_tools(
                user_text,
                augmented_system_prompt,
                instance_name=instance_name,
                instance_type=instance_type,
            )
        except Exception as cloud_error:
            if is_rate_limited_error(cloud_error):
                owner.logger.warning(
                    "Claude fallback hit rate limits; trying local Ollama fallback"
                )
                return owner._call_ollama_with_tools(
                    user_text,
                    augmented_system_prompt,
                    instance_name=instance_name,
                    instance_type=instance_type,
                )
            raise


def _run_local_mode(
    *,
    owner: Any,
    router: Any,
    user_text: str,
    augmented_system_prompt: str,
    router_messages: list[dict[str, str]],
    instance_name: str | None,
    instance_type: str | None,
    active_local_model: str | None = None,
) -> tuple[str, str, dict[str, Any]]:
    task_type = router._classify_task(user_text, augmented_system_prompt)
    # Ignore active_local_model if it's a llamacpp key — those are handled upstream
    _ollama_model = (
        active_local_model
        if (active_local_model and active_local_model not in _LOCAL_LLAMACPP_ROUTES)
        else None
    )
    model_name = _ollama_model or router.LOCAL_TIER_MAP.get(task_type, router.LOCAL_MODEL)
    paired = owner.os.environ.get("GUPPY_LOCAL_PAIRED", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if paired and task_type != "simple":
        result = router.query_local_paired(
            augmented_system_prompt,
            user_text,
            task_type,
            owner.core.TOOLS,
            router_messages,
        )
        if not result:
            raise RuntimeError("Local-only paired mode failed (Ollama/model unavailable)")
        response = str(result.get("response", "")).strip()
        if not response:
            raise RuntimeError("Local-only paired mode returned empty response")
        return (
            response,
            str(result.get("source", "local")),
            dict(result.get("metadata", {})),
        )

    response = owner._call_selected_local_runtime(
        user_text,
        augmented_system_prompt,
        instance_name=instance_name,
        instance_type=instance_type,
        model_override=model_name,
    )
    return response, "local", {"route_mode": "local", "model": model_name}


def _run_code_mode(
    *,
    owner: Any,
    router: Any,
    user_text: str,
    augmented_system_prompt: str,
    router_messages: list[dict[str, str]],
) -> tuple[str, str, dict[str, Any]]:
    result = router.query_with_boost(
        system_prompt=augmented_system_prompt,
        user_text=user_text,
        model=router.LOCAL_CODE_MODEL,
        boost_mode=router.HAIKU_BOOST_CODE_REVIEW,
        tools=None,
        messages=router_messages,
    )
    if not result:
        raise RuntimeError("Code mode local model unavailable")
    return (
        str(result.get("response", "")),
        str(result.get("source", "local")),
        dict(result.get("metadata", {})),
    )


def _run_routed_mode(
    *,
    owner: Any,
    router: Any,
    user_text: str,
    requested_mode: str,
    augmented_system_prompt: str,
    router_messages: list[dict[str, str]],
    instance_name: str | None,
    instance_type: str | None,
    active_local_model: str | None = None,
    active_cloud_model: str | None = None,
) -> tuple[str, str, dict[str, Any]]:
    route_decision = router.resolve_ui_route(
        user_text=user_text,
        system_prompt=augmented_system_prompt,
        mode=requested_mode,
        api_key_available=bool(getattr(router, "anthropic_available", False)),
    )
    executor = str(route_decision.get("executor", "") or "").strip().lower()
    target_model = str(route_decision.get("model", "") or "").strip()
    backup_model = str(route_decision.get("backup_model", "") or "").strip()

    if executor == "error":
        raise RuntimeError(
            str(
                route_decision.get("error")
                or route_decision.get("route_reason")
                or "Requested route unavailable"
            )
        )

    if executor == "claude":
        response = owner._call_claude_with_tools(
            user_text,
            augmented_system_prompt,
            instance_name=instance_name,
            instance_type=instance_type,
            preferred_model=active_cloud_model or target_model or None,
            backup_model=backup_model or None,
        )
        source = "haiku" if "haiku" in (target_model or "").lower() else "sonnet"
        return response, source, {"route_decision": route_decision}

    if executor in {"ollama", "ollama_paired"}:
        if executor == "ollama_paired":
            result = router.query_local_paired(
                augmented_system_prompt,
                user_text,
                str(route_decision.get("task_type", "complex") or "complex"),
                owner.core.TOOLS,
                router_messages,
            )
            if not result:
                raise RuntimeError("Local paired route failed")
            response = str(result.get("response", "")).strip()
            if not response:
                raise RuntimeError("Local paired route returned empty response")
            return (
                response,
                str(result.get("source", "local")),
                dict(result.get("metadata", {})),
            )

        response = owner._call_selected_local_runtime(
            user_text,
            augmented_system_prompt,
            instance_name=instance_name,
            instance_type=instance_type,
            model_override=active_local_model or target_model or None,
        )
        return response, "local", {"route_decision": route_decision}

    response, source, metadata = router.query_smart(
        system_prompt=augmented_system_prompt,
        user_text=user_text,
        tools=owner.core.TOOLS,
        messages=router_messages,
    )
    return response, source, metadata


def call_claude_with_tools(
    owner: Any,
    user_text: str,
    system_prompt: str,
    *,
    instance_name: Optional[str] = None,
    instance_type: Optional[str] = None,
    preferred_model: Optional[str] = None,
    backup_model: Optional[str] = None,
) -> str:
    if not owner.ANTHROPIC_AVAILABLE:
        raise RuntimeError("Anthropic SDK is not installed.")
    api_key = owner.os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")

    primary_model = (
        str(preferred_model or owner.os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"))
        .strip()
        or "claude-sonnet-4-6"
    )
    backup_model_name = str(
        backup_model or owner.os.environ.get("ANTHROPIC_BACKUP_MODEL", "claude-haiku-4-5-20251001")
    ).strip()
    model_chain = [primary_model] + (
        [backup_model_name] if backup_model_name and backup_model_name != primary_model else []
    )

    client = owner.anthropic.Anthropic(api_key=api_key)
    msgs = [{"role": "user", "content": user_text}]
    final_text = ""

    while True:
        resp = None
        last_err = None
        for model_name in model_chain:
            try:
                resp = client.messages.create(
                    model=model_name,
                    max_tokens=4096,
                    system=system_prompt,
                    tools=owner.core.TOOLS,
                    messages=msgs,
                )
                break
            except Exception as exc:
                last_err = exc
        if resp is None:
            raise RuntimeError(f"Claude request failed on all configured models: {last_err}")

        msgs.append({"role": "assistant", "content": resp.content})
        block_text = extract_text_from_anthropic_blocks(resp.content)
        if block_text:
            final_text = block_text

        tool_uses = [b for b in resp.content if getattr(b, "type", None) == "tool_use"]
        if not tool_uses or getattr(resp, "stop_reason", "") == "end_turn":
            break

        results = []
        for tool_use in tool_uses:
            result = owner.core.run_tool(
                tool_use.name,
                tool_use.input,
                instance_name=instance_name,
                instance_type=instance_type,
            )
            results.append(
                {"type": "tool_result", "tool_use_id": tool_use.id, "content": str(result)}
            )
        msgs.append({"role": "user", "content": results})

    return final_text or "No response produced."


def call_ollama_with_tools(
    owner: Any,
    user_text: str,
    system_prompt: str,
    *,
    instance_name: Optional[str] = None,
    instance_type: Optional[str] = None,
    model_override: Optional[str] = None,
) -> str:
    model = str(model_override or owner.os.environ.get("OLLAMA_MODEL", "guppy")).strip() or "guppy"
    ok, err = owner.core.check_ollama(model)
    if not ok:
        raise RuntimeError(err)

    all_msgs = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]
    ollama_tools = owner.core.to_ollama_tools(owner.core.TOOLS)
    final_text = ""

    while True:
        payload = json.dumps(
            {
                "model": model,
                "messages": all_msgs,
                "tools": ollama_tools,
                "stream": False,
                "keep_alive": "10m",
                "options": {
                    "temperature": 0.8,
                    "top_p": 0.95,
                    "top_k": 40,
                    "num_predict": 4096,
                },
            }
        ).encode()
        req = urllib.request.Request(
            "http://localhost:11434/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=180) as response:
            data = json.loads(response.read().decode())

        msg = data.get("message", {})
        content = _strip_tool_call_markers((msg.get("content") or "").strip())
        if content:
            final_text = content

        tool_calls = msg.get("tool_calls") or []
        clean_assistant = {"role": "assistant", "content": content}
        if tool_calls:
            clean_assistant["tool_calls"] = tool_calls
        all_msgs.append(clean_assistant)

        if not tool_calls:
            break

        for tool_call in tool_calls:
            fn = tool_call.get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            result = owner.core.run_tool(
                name,
                args if isinstance(args, dict) else {},
                instance_name=instance_name,
                instance_type=instance_type,
            )
            all_msgs.append({"role": "tool", "content": str(result)})

    return final_text or "No response produced."


# ── Streaming support ─────────────────────────────────────────────────────────

_OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"
_TOOL_CALL_SENTINEL = "\x00TOOL_CALLS:"
# Sent as the final token when streamed content needs to be replaced by the UI
# (e.g. post-stream tool-marker cleanup). Frontend checks for this prefix.
_REPLACE_SENTINEL = "\x00REPLACE:"
# Emitted as the last token before [DONE] so the UI knows which backend served the response.
_SOURCE_SENTINEL = "\x00SOURCE:"

# ── Free-tier cloud provider constants ────────────────────────────────────────
# Must be kept in sync with routes_providers.py model catalogs.
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
# Best free-tier models to try when auto-routing without local resources
_FREE_MISTRAL_MODEL = "ministral-8b-latest"
_FREE_COHERE_MODEL  = "command-r7b-12-2024"


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


async def _stream_openai_compat_tokens(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    timeout: float = 120.0,
) -> AsyncGenerator[str, None]:
    """Yield content from any OpenAI-compatible SSE streaming endpoint.

    Used for Mistral (native OpenAI-compat API) and Cohere (via their
    /compatibility endpoint).  No tool-call loop — text streaming only.
    """
    import httpx

    url = f"{base_url.rstrip('/')}/chat/completions"
    payload: dict = {
        "model": model,
        "messages": messages,
        "stream": True,
        "max_tokens": 2048,
        "temperature": 0.7,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                response.raise_for_status()
                async for raw_line in response.aiter_lines():
                    line = raw_line.strip()
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    content = (choices[0].get("delta") or {}).get("content") or ""
                    if content:
                        yield content
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Cloud API returned HTTP {exc.response.status_code}"
        ) from exc
    except httpx.ConnectError as exc:
        raise RuntimeError("Cannot reach cloud provider API") from exc


async def _stream_mistral_tokens(
    *,
    api_key: str,
    model: str,
    messages: list[dict],
    timeout: float = 120.0,
) -> AsyncGenerator[str, None]:
    """Yield content tokens from Mistral's OpenAI-compatible streaming API."""
    async for token in _stream_openai_compat_tokens(
        base_url="https://api.mistral.ai/v1",
        api_key=api_key,
        model=model,
        messages=messages,
        timeout=timeout,
    ):
        yield token


async def _stream_cohere_tokens(
    *,
    api_key: str,
    model: str,
    messages: list[dict],
    timeout: float = 120.0,
) -> AsyncGenerator[str, None]:
    """Yield content tokens from Cohere's OpenAI-compatible streaming endpoint."""
    async for token in _stream_openai_compat_tokens(
        base_url="https://api.cohere.com/compatibility/v1",
        api_key=api_key,
        model=model,
        messages=messages,
        timeout=timeout,
    ):
        yield token


async def _stream_claude_with_tools(
    *,
    api_key: str,
    model: str,
    system_prompt: str,
    messages: list[dict],
    tools: list | None = None,
    tool_runner: Any | None = None,
    max_tokens: int = 4096,
    max_tool_rounds: int = 6,
) -> AsyncGenerator[str, None]:
    """Yield content tokens from Anthropic Claude using the async streaming SDK.

    Handles multi-round tool-call loops: each round's text streams token-by-token
    to the UI; tool execution happens between rounds in a thread pool.
    """
    import asyncio

    try:
        import anthropic as _ant
        client = _ant.AsyncAnthropic(api_key=api_key)
    except ImportError:
        raise RuntimeError("anthropic SDK not installed or too old — pip install anthropic>=0.21")

    msgs: list[dict] = list(messages)
    for _round in range(max_tool_rounds + 1):
        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": msgs,
        }
        if tools:
            kwargs["tools"] = tools

        tool_use_blocks: list = []
        try:
            async with client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text
                final = await stream.get_final_message()

            tool_use_blocks = [b for b in final.content if getattr(b, "type", None) == "tool_use"]

            if not tool_use_blocks or getattr(final, "stop_reason", "") == "end_turn":
                return

        except Exception as exc:
            raise RuntimeError(f"Claude streaming error: {exc}") from exc

        if _round >= max_tool_rounds:
            _log.warning("Claude streaming tool loop hit max_tool_rounds=%d — stopping", max_tool_rounds)
            return

        if not tool_runner:
            return

        msgs.append({"role": "assistant", "content": final.content})
        results = []
        for tu in tool_use_blocks:
            try:
                result = await asyncio.to_thread(
                    tool_runner, tu.name, dict(tu.input) if tu.input else {}
                )
                result_str = str(result)
            except Exception as exc:
                result_str = f"[tool error: {exc}]"
                _log.warning("Claude streaming tool_runner(%r) error: %s", tu.name, exc)
            results.append({"type": "tool_result", "tool_use_id": tu.id, "content": result_str})
        msgs.append({"role": "user", "content": results})


async def _stream_llamacpp_tokens(
    *,
    model: str,
    backend: str,
    messages: list[dict],
    timeout: float = 180.0,
    tools: list[dict] | None = None,
    tool_runner: Any | None = None,
    max_tool_rounds: int = 6,
    _loop_history: list[str] | None = None,
) -> AsyncGenerator[str, None]:
    """Yield content tokens from a llama.cpp OpenAI-compatible SSE stream.

    Tokens are yielded eagerly as they arrive so the UI updates in real time.
    Tool-call rounds are handled transparently: the model's pre-tool text (if
    any) streams immediately, tools execute, then the follow-up answer also
    streams token by token.

    Requires ``--jinja`` on llama-server (default since llama.cpp b5000+) for
    structured tool_calls.  On older GGUFs without a Jinja template the model
    may emit text-embedded markup (``<tool_call>…</tool_call>``) which will
    reach the UI as-is; that trade-off is acceptable given the eager-yield
    goal.
    """
    import httpx

    cfg = _LOCAL_BACKENDS.get(backend, {})
    url = f"{_local_resolve_url(backend)}{cfg.get('chat_path', '/v1/chat/completions')}"

    current_messages = list(messages)
    # Loop detection: track (name, args_fingerprint) per round.
    # Two identical consecutive call-sets = model is stuck; break early.
    _loop_history = _loop_history if _loop_history is not None else []

    for _round in range(max_tool_rounds + 1):
        payload: dict = {
            "model": model,
            "messages": current_messages,
            "stream": True,
            "max_tokens": 2048,
            "temperature": 0.8,
            "top_p": 0.95,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        full_content = ""
        tool_calls_acc: dict[int, dict] = {}   # delta index → accumulated call
        finish_reason: str | None = None

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", url, json=payload) as response:
                    response.raise_for_status()
                    async for raw_line in response.aiter_lines():
                        line = raw_line.strip()
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        choices = chunk.get("choices", [])
                        if not choices:
                            continue
                        choice = choices[0]
                        if choice.get("finish_reason"):
                            finish_reason = choice["finish_reason"]
                        delta = choice.get("delta", {})

                        # Accumulate and immediately yield text content
                        content = delta.get("content") or ""
                        if content:
                            full_content += content
                            yield content

                        # Accumulate tool_call deltas (OpenAI streaming format)
                        for tc_delta in (delta.get("tool_calls") or []):
                            idx = tc_delta.get("index", 0)
                            if idx not in tool_calls_acc:
                                tool_calls_acc[idx] = {
                                    "id": tc_delta.get("id", f"call_{_round}_{idx}"),
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                }
                            tc = tool_calls_acc[idx]
                            fn_delta = tc_delta.get("function", {})
                            if fn_delta.get("name"):
                                tc["function"]["name"] += fn_delta["name"]
                            if fn_delta.get("arguments"):
                                tc["function"]["arguments"] += fn_delta["arguments"]
                            if tc_delta.get("id"):
                                tc["id"] = tc_delta["id"]

        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"llama.cpp backend '{backend}' returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"Cannot reach llama.cpp backend '{backend}'. Is the server running?"
            ) from exc

        tool_calls_list = [tool_calls_acc[i] for i in sorted(tool_calls_acc)]

        # ── Structured tool call detected ─────────────────────────────────────
        # Execute tool calls whenever the model emits them, regardless of
        # finish_reason. Some llamacpp builds report "stop" even when tool_calls
        # are present; silently dropping them causes the "I'm downloading it now"
        # hallucination where the model claims to act but no tool was called.
        _is_tool_turn = bool(tool_calls_list)
        if _is_tool_turn and tool_runner:
            if _round >= max_tool_rounds:
                _log.warning(
                    "llama.cpp tool loop hit max_tool_rounds=%d — stopping", max_tool_rounds
                )
                break

            # Append the assistant turn (may carry partial text + tool_calls)
            asst_msg: dict = {
                "role": "assistant",
                "content": full_content if full_content else None,
                "tool_calls": tool_calls_list,
            }
            current_messages.append(asst_msg)

            # Execute each requested tool and collect results
            for tc in tool_calls_list:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                args_raw = fn.get("arguments", "{}")
                try:
                    args = json.loads(args_raw) if isinstance(args_raw, str) else (args_raw or {})
                except Exception:
                    args = {}

                try:
                    result = tool_runner(name, args if isinstance(args, dict) else {})
                    result_str = str(result)
                except Exception as exc:
                    result_str = f"[tool error: {exc}]"
                    _log.warning("llamacpp tool_runner(%r) error: %s", name, exc)

                # Truncate very large results (screenshots, file dumps) so the
                # model's context window isn't blown out.
                if len(result_str) > 6000:
                    result_str = result_str[:6000] + "\n...[truncated for context]"

                _log.info(
                    "llamacpp tool call round=%d: %s → %d chars", _round, name, len(result_str)
                )
                current_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": result_str,
                })

            # Loop detection: fingerprint this round's calls.
            # If the model issues the exact same set of calls twice in a row it's
            # stuck — break rather than burning all remaining rounds.
            _round_fp = "|".join(
                f"{tc['function']['name']}:{tc['function']['arguments'][:120]}"
                for tc in tool_calls_list
            )
            if _loop_history and _loop_history[-1] == _round_fp:
                _log.warning(
                    "llamacpp tool loop detected: round %d repeated identical calls (%s) — stopping",
                    _round, tool_calls_list[0]["function"]["name"] if tool_calls_list else "?",
                )
                yield "\n\n_(Loop detected: the model repeated the same tool call. Stopping to avoid cycling.)_"
                return
            _loop_history.append(_round_fp)

            continue  # send tool results back to the model

        # ── No tool calls — content already yielded token by token above ────
        return

    # Hit max_tool_rounds — final round's tokens were already yielded eagerly
    _log.warning("llamacpp tool loop exhausted after %d rounds", max_tool_rounds)


async def _stream_ollama_tokens(
    *,
    model: str,
    messages: list[dict],
    tools: list | None = None,
    timeout: float = 180.0,
) -> AsyncGenerator[str, None]:
    """
    Yield content token strings from Ollama's streaming chat API.

    If the model produces tool calls, the final yielded value is a sentinel
    string ``"\\x00TOOL_CALLS:<json>"`` so the caller can detect and handle
    them without breaking the token stream.
    """
    import httpx

    payload: dict = {
        "model": model,
        "messages": messages,
        "stream": True,
        "keep_alive": "10m",
        "options": {"temperature": 0.8, "top_p": 0.95, "top_k": 40, "num_predict": 4096},
    }
    if tools:
        payload["tools"] = tools

    tool_calls_buffer: list = []

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", _OLLAMA_CHAT_URL, json=payload) as response:
                response.raise_for_status()
                async for raw_line in response.aiter_lines():
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    msg = chunk.get("message", {})
                    content = msg.get("content") or ""
                    if content:
                        yield content

                    calls = msg.get("tool_calls")
                    if calls:
                        tool_calls_buffer.extend(calls)

                    if chunk.get("done"):
                        break
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"Ollama returned {exc.response.status_code}") from exc
    except httpx.ConnectError as exc:
        raise RuntimeError(
            "Cannot reach Ollama on port 11434. Start Ollama and try again."
        ) from exc

    if tool_calls_buffer:
        yield _TOOL_CALL_SENTINEL + json.dumps(tool_calls_buffer)


async def stream_unified_inference(
    owner: Any,
    user_text: str,
    system_prompt: str,
    mode: Optional[str] = None,
    history: Optional[list[dict]] = None,
    instance_name: Optional[str] = None,
    instance_type: Optional[str] = None,
    active_local_model: Optional[str] = None,
    active_cloud_model: Optional[str] = None,
    image_base64: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Async generator yielding content tokens for the chat response.

    For Ollama backends: true token-level streaming via httpx.
    For Claude / fallbacks: yields the full response as a single chunk.
    """
    clean_history = sanitize_chat_history(history)
    augmented_system = augment_system_with_history(system_prompt, clean_history)
    augmented_system = await _inject_semantic_context_async(augmented_system, user_text, owner)
    augmented_system = await _inject_workspace_context_async(augmented_system, owner)
    requested_mode = (mode or owner.os.environ.get("GUPPY_DEFAULT_MODE", "auto") or "auto").strip().lower()

    # Steer mode: prepend a redirection directive then route normally so
    # streaming paths work without a special code path.
    if requested_mode == "steer":
        augmented_system = (
            "The user's next message is a steering directive or correction. "
            "Adjust your approach and direction accordingly, "
            "then continue helpfully from where you left off.\n\n"
        ) + augmented_system
        requested_mode = "auto"

    # Classify task type early so agentic routing can intercept before llamacpp/Ollama.
    # Only meaningful for auto mode — explicit mode selections bypass this.
    _early_task_type: str = ""
    if requested_mode in {"auto", ""} and owner.GUPPY_CORE_AVAILABLE and owner.INFERENCE_ROUTER_AVAILABLE:
        try:
            _early_task_type = owner.get_router()._classify_task(user_text, augmented_system)
        except Exception:
            _early_task_type = ""

    # ── Explicit Mistral / Cohere cloud routing ────────────────────────────────
    # When the user has picked a Mistral or Cohere model in the model picker,
    # skip local models entirely and stream from that provider's API.
    # Only active for explicit cloud modes — not "auto", which should prefer local.
    if active_cloud_model and requested_mode not in {"local", "code", "auto", ""}:
        if active_cloud_model in _MISTRAL_MODEL_IDS:
            _mk = _get_cloud_api_key("mistral", owner)
            if _mk:
                _log.info("Explicit cloud: streaming from Mistral model %s", active_cloud_model)
                _msgs = build_router_messages(augmented_system, user_text, clean_history)
                try:
                    async for token in _stream_mistral_tokens(
                        api_key=_mk, model=active_cloud_model, messages=_msgs
                    ):
                        yield token
                    yield _SOURCE_SENTINEL + f"mistral:{active_cloud_model}"
                    return
                except Exception as _merr:
                    _log.warning(
                        "Mistral explicit model %s failed: %s — falling back",
                        active_cloud_model, _merr,
                    )
        elif active_cloud_model in _COHERE_MODEL_IDS:
            _ck = _get_cloud_api_key("cohere", owner)
            if _ck:
                _log.info("Explicit cloud: streaming from Cohere model %s", active_cloud_model)
                _msgs = build_router_messages(augmented_system, user_text, clean_history)
                try:
                    async for token in _stream_cohere_tokens(
                        api_key=_ck, model=active_cloud_model, messages=_msgs
                    ):
                        yield token
                    yield _SOURCE_SENTINEL + f"cohere:{active_cloud_model}"
                    return
                except Exception as _cerr:
                    _log.warning(
                        "Cohere explicit model %s failed: %s — falling back",
                        active_cloud_model, _cerr,
                    )

    # ── Tool-call routing: xLAM-2-8B → Hermes 4 (fallback) ─────────────────────
    # Single-tool invocation tasks where structured function-calling accuracy
    # matters. xLAM-2-8B-fc-r is #1 on BFCL V4 for its size class (~5 GB Q4).
    # Falls back to hermes4 if xLAM is offline.
    if _early_task_type == "tool_call" and requested_mode in {"auto", ""}:
        from src.guppy.api.routes_backends import _port_alive as _llc_port_alive
        _XLAM_BACKEND = "llamacpp-xlam"
        _xlam_cfg = _LOCAL_BACKENDS.get(_XLAM_BACKEND, {})
        _xlam_url = _xlam_cfg.get("default_url", "")
        _xlam_port = int(_xlam_url.rsplit(":", 1)[-1]) if ":" in _xlam_url else 0
        if _xlam_port and _llc_port_alive(_xlam_port):
            _xlam_model = _LOCAL_BACKEND_DEFAULT_MODELS.get(_XLAM_BACKEND, "")
            if _xlam_model:
                _log.info("Tool-call task → routing to xLAM-2-8B (port %d)", _xlam_port)
                _xlam_messages = build_router_messages(
                    augmented_system, user_text, sanitize_chat_history(history)
                )
                _xlam_tools = _merged_openai_tools(owner)
                def _xlam_tool_runner(name: str, args: dict) -> str:
                    return str(owner.core.run_tool(
                        name, args,
                        instance_name=instance_name,
                        instance_type=instance_type,
                    ))
                try:
                    async for token in _stream_llamacpp_tokens(
                        model=_xlam_model,
                        backend=_XLAM_BACKEND,
                        messages=_xlam_messages,
                        tools=_xlam_tools,
                        tool_runner=_xlam_tool_runner,
                        max_tool_rounds=4,
                    ):
                        yield token
                    yield _SOURCE_SENTINEL + f"{_XLAM_BACKEND}:{_xlam_model}"
                    return
                except RuntimeError as _xlam_err:
                    _log.warning(
                        "xLAM tool-call route failed: %s — falling back to Hermes 4",
                        _xlam_err,
                    )
        # xLAM offline or failed — try hermes4 as tool-call fallback
        _H4_BACKEND = "llamacpp-hermes4"
        _h4_cfg = _LOCAL_BACKENDS.get(_H4_BACKEND, {})
        _h4_url = _h4_cfg.get("default_url", "")
        _h4_port = int(_h4_url.rsplit(":", 1)[-1]) if ":" in _h4_url else 0
        if _h4_port and _llc_port_alive(_h4_port):
            _h4_model = _LOCAL_BACKEND_DEFAULT_MODELS.get(_H4_BACKEND, "")
            if _h4_model:
                _log.info("Tool-call fallback → Hermes 4 (port %d)", _h4_port)
                _h4_messages = build_router_messages(
                    augmented_system, user_text, sanitize_chat_history(history)
                )
                _h4_tools = _merged_openai_tools(owner)
                def _h4_tool_runner(name: str, args: dict) -> str:
                    return str(owner.core.run_tool(
                        name, args,
                        instance_name=instance_name,
                        instance_type=instance_type,
                    ))
                try:
                    async for token in _stream_llamacpp_tokens(
                        model=_h4_model,
                        backend=_H4_BACKEND,
                        messages=_h4_messages,
                        tools=_h4_tools,
                        tool_runner=_h4_tool_runner,
                        max_tool_rounds=4,
                    ):
                        yield token
                    yield _SOURCE_SENTINEL + f"{_H4_BACKEND}:{_h4_model}"
                    return
                except RuntimeError as _h4_err:
                    _log.warning(
                        "Hermes 4 tool-call fallback failed: %s — continuing to local models",
                        _h4_err,
                    )

    # ── Agentic routing: Qwen3 35B → Claude Sonnet ────────────────────────────
    # Multi-step tool-loop tasks (read all files, collect data, iterate over sets)
    # need a capable model. 8B models hallucinate fake results instead of calling
    # tools. Qwen3 35B-A3B MoE is the strongest local option (port 8083); Claude
    # Sonnet is the cloud fallback when Qwen3 is offline. Pepe is never tried
    # for agentic tasks.
    if _early_task_type == "agentic" and requested_mode in {"auto", ""} and owner.GUPPY_CORE_AVAILABLE:
        from src.guppy.api.routes_backends import _port_alive as _llc_port_alive
        _QWEN3_BACKEND = "llamacpp-qwen3"
        _qwen3_cfg = _LOCAL_BACKENDS.get(_QWEN3_BACKEND, {})
        _qwen3_url = _qwen3_cfg.get("default_url", "")
        _qwen3_port = int(_qwen3_url.rsplit(":", 1)[-1]) if ":" in _qwen3_url else 0
        if _qwen3_port and _llc_port_alive(_qwen3_port):
            _qwen3_model = _LOCAL_BACKEND_DEFAULT_MODELS.get(_QWEN3_BACKEND, "")
            if _qwen3_model:
                _log.info("Agentic task → routing to Qwen3 35B (port %d)", _qwen3_port)
                _agentic_messages = build_router_messages(
                    augmented_system, user_text, sanitize_chat_history(history)
                )
                _agentic_tools = _merged_openai_tools(owner)
                def _qwen3_tool_runner(name: str, args: dict) -> str:
                    return str(owner.core.run_tool(
                        name, args,
                        instance_name=instance_name,
                        instance_type=instance_type,
                    ))
                try:
                    async for token in _stream_llamacpp_tokens(
                        model=_qwen3_model,
                        backend=_QWEN3_BACKEND,
                        messages=_agentic_messages,
                        tools=_agentic_tools,
                        tool_runner=_qwen3_tool_runner,
                        max_tool_rounds=10,  # agentic tasks may need more rounds
                    ):
                        yield token
                    yield _SOURCE_SENTINEL + f"{_QWEN3_BACKEND}:{_qwen3_model}"
                    return
                except RuntimeError as _qwen3_err:
                    _log.warning(
                        "Qwen3 agentic route failed: %s — escalating to Claude Sonnet",
                        _qwen3_err,
                    )

        # Qwen3 offline (or failed) — escalate directly to Claude Sonnet (streaming).
        # Never fall through to Pepe for agentic tasks.
        _ak = _get_cloud_api_key("anthropic", owner)
        if _ak:
            _log.info("Agentic task: Qwen3 offline, routing to Claude Sonnet (streaming)")
            _agentic_msgs = build_router_messages(augmented_system, user_text, clean_history)
            _claude_tools = owner.core.TOOLS if owner.GUPPY_CORE_AVAILABLE else None
            def _claude_tool_runner(name: str, args: dict) -> str:
                return str(owner.core.run_tool(name, args,
                    instance_name=instance_name, instance_type=instance_type))
            try:
                async for token in _stream_claude_with_tools(
                    api_key=_ak,
                    model="claude-sonnet-4-6",
                    system_prompt=augmented_system,
                    messages=_agentic_msgs,
                    tools=_claude_tools,
                    tool_runner=_claude_tool_runner,
                ):
                    yield token
                yield _SOURCE_SENTINEL + "claude-sonnet-4-6"
                return
            except Exception as _cloud_err:
                _log.warning(
                    "Claude Sonnet agentic fallback failed: %s — continuing to local models",
                    _cloud_err,
                )
        # else: no API key or cloud failed — fall through to best available local

    is_llamacpp = bool(active_local_model and active_local_model in _LOCAL_LLAMACPP_ROUTES)
    # Tracks whether llamacpp was attempted but the backend was not reachable,
    # so we can gracefully fall through to Ollama instead of hard-failing.
    llamacpp_failed = False

    # llama.cpp: stream via OpenAI-compat SSE with full tool-call loop.
    # Requires --jinja on the server (default since llama.cpp b5000).
    # Falls back gracefully when the model has no tool-use template.
    if is_llamacpp and owner.GUPPY_CORE_AVAILABLE:
        llamacpp_backend = _LOCAL_LLAMACPP_ROUTES.get(active_local_model or "")
        if llamacpp_backend and _LOCAL_BACKENDS.get(llamacpp_backend):
            # Quick liveness check before attempting — avoids a slow timeout when
            # the selected llamacpp model isn't running.
            from src.guppy.api.routes_backends import _port_alive as _llc_port_alive
            backend_cfg = _LOCAL_BACKENDS.get(llamacpp_backend, {})
            backend_port = int(
                (backend_cfg.get("default_url", "") or "").rsplit(":", 1)[-1]
            ) if ":" in (backend_cfg.get("default_url", "") or "") else 0
            backend_alive = _llc_port_alive(backend_port) if backend_port else False

            if backend_alive:
                messages = build_router_messages(
                    augmented_system, user_text, sanitize_chat_history(history)
                )
                # For multimodal backends (MiniCPM-o), replace the last user message
                # with an OpenAI vision content array when an image is attached.
                if image_base64 and llamacpp_backend == "llamacpp-minicpm" and messages:
                    last = messages[-1]
                    if last.get("role") == "user":
                        messages[-1] = {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": last["content"]},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
                            ],
                        }
                # Merge core.TOOLS + all enabled db tools so the model can call
                # calibre, gutenberg, screenpipe, etc. even when they're not in
                # the C++ core's auto-discovered catalog.
                _openai_tools = _merged_openai_tools(owner)

                def _llamacpp_tool_runner(name: str, args: dict) -> str:
                    return str(
                        owner.core.run_tool(
                            name,
                            args,
                            instance_name=instance_name,
                            instance_type=instance_type,
                        )
                    )

                try:
                    async for token in _stream_llamacpp_tokens(
                        model=active_local_model,
                        backend=llamacpp_backend,
                        messages=messages,
                        tools=_openai_tools,
                        tool_runner=_llamacpp_tool_runner,
                    ):
                        yield token
                    yield _SOURCE_SENTINEL + f"{llamacpp_backend}:{active_local_model}"
                    return
                except RuntimeError:
                    llamacpp_failed = True  # backend died mid-stream — fall through
            else:
                # Backend not running — silently fall through to Ollama/cloud.
                llamacpp_failed = True

    # ── llamacpp opportunistic routing ───────────────────────────────────────────
    # Try alive Mode-A llamacpp backends when:
    #   (a) the saved model's backend was offline (llamacpp_failed), OR
    #   (b) no llamacpp model is saved at all (is_llamacpp=False) and mode allows local.
    # Priority: pepe (fast general) → minicpm (vision/speech) → dispatch (lightweight).
    # Dispatcher is intentionally last — it's an orchestrator, not a primary chat model.
    _should_try_llamacpp_auto = (
        owner.GUPPY_CORE_AVAILABLE
        and requested_mode in {"local", "auto", ""}
        and (llamacpp_failed or not is_llamacpp)
    )
    if _should_try_llamacpp_auto:
        from src.guppy.api.routes_backends import _port_alive as _llc_port_alive
        _MODE_A_FALLBACK_ORDER = [
            "llamacpp-hermes4", "llamacpp-hermes3",
            "llamacpp-pepe", "llamacpp-rocinante",
            "llamacpp-minicpm", "llamacpp-dispatch",
        ]
        for _fb_backend in _MODE_A_FALLBACK_ORDER:
            _fb_cfg = _LOCAL_BACKENDS.get(_fb_backend, {})
            _fb_url = _fb_cfg.get("default_url", "")
            _fb_port = int(_fb_url.rsplit(":", 1)[-1]) if ":" in _fb_url else 0
            if not _fb_port or not _llc_port_alive(_fb_port):
                continue
            _fb_model = _LOCAL_BACKEND_DEFAULT_MODELS.get(_fb_backend, "")
            if not _fb_model:
                continue
            messages = build_router_messages(
                augmented_system, user_text, sanitize_chat_history(history)
            )
            _openai_tools = _merged_openai_tools(owner)
            def _fb_tool_runner(name: str, args: dict) -> str:
                return str(owner.core.run_tool(name, args,
                    instance_name=instance_name, instance_type=instance_type))
            try:
                async for token in _stream_llamacpp_tokens(
                    model=_fb_model,
                    backend=_fb_backend,
                    messages=messages,
                    tools=_openai_tools,
                    tool_runner=_fb_tool_runner,
                ):
                    yield token
                yield _SOURCE_SENTINEL + f"{_fb_backend}:{_fb_model}"
                return
            except RuntimeError:
                continue  # try next fallback

    # Allow Ollama streaming when: llamacpp was never attempted OR it failed.
    # Previously "not is_llamacpp" blocked Ollama fallback when a llamacpp model
    # was selected but not running — now we always fall through gracefully.
    can_stream_ollama = (
        owner.GUPPY_CORE_AVAILABLE
        and owner.INFERENCE_ROUTER_AVAILABLE
        and requested_mode in {"local", "auto", ""}
        and (not is_llamacpp or llamacpp_failed)
    )

    if can_stream_ollama:
        try:
            router = owner.get_router()
            task_type = router._classify_task(user_text, augmented_system)
            # Only use active_local_model if it's an Ollama model — not a llamacpp route key.
            # If llamacpp_failed, active_local_model is the llamacpp key (e.g. "gemma-4-heretic-ara")
            # which Ollama doesn't know about, causing a 404.
            _ollama_active = (
                active_local_model
                if (active_local_model and active_local_model not in _LOCAL_LLAMACPP_ROUTES)
                else None
            )
            model_name = _ollama_active or router.LOCAL_TIER_MAP.get(task_type, router.LOCAL_MODEL)
            messages = build_router_messages(augmented_system, user_text, clean_history)
            tools = owner.core.to_ollama_tools(owner.core.TOOLS) if owner.GUPPY_CORE_AVAILABLE else None

            tool_calls_accumulated: list = []
            all_messages = list(messages)
            full_content_parts: list[str] = []

            # Stream tokens eagerly — no buffering. We track full_content
            # in parallel so we can detect text-embedded tool markers after
            # the stream ends and issue a REPLACE correction if needed.
            async for token in _stream_ollama_tokens(
                model=model_name,
                messages=all_messages,
                tools=tools,
            ):
                if token.startswith(_TOOL_CALL_SENTINEL):
                    tool_calls_accumulated = json.loads(token[len(_TOOL_CALL_SENTINEL):])
                else:
                    full_content_parts.append(token)
                    yield token

            assistant_content = "".join(full_content_parts)

            # Post-stream: check for text-embedded tool call markers (edge case —
            # some GGUF models emit <tool_call>…</tool_call> as plain text).
            # Since tokens were already sent, signal the UI to replace the content.
            if _TOOL_CALL_TAG_RE.search(assistant_content):
                cleaned = _clean_local_response(assistant_content)
                if cleaned != assistant_content:
                    yield _REPLACE_SENTINEL + cleaned
                yield _SOURCE_SENTINEL + f"ollama:{model_name}"
                return

            if tool_calls_accumulated:
                clean_assistant: dict = {"role": "assistant", "content": assistant_content}
                clean_assistant["tool_calls"] = tool_calls_accumulated
                all_messages.append(clean_assistant)

                for tool_call in tool_calls_accumulated:
                    fn = tool_call.get("function", {})
                    name = fn.get("name", "")
                    args = fn.get("arguments", {})
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            args = {}
                    result = owner.core.run_tool(
                        name,
                        args if isinstance(args, dict) else {},
                        instance_name=instance_name,
                        instance_type=instance_type,
                    )
                    all_messages.append({"role": "tool", "content": str(result)})

                async for token in _stream_ollama_tokens(
                    model=model_name,
                    messages=all_messages,
                    tools=tools,
                ):
                    if not token.startswith(_TOOL_CALL_SENTINEL):
                        yield token
            yield _SOURCE_SENTINEL + f"ollama:{model_name}"
            return

        except RuntimeError as _oll_err:
            _log.warning("Ollama streaming failed (%s) — falling back to non-streaming", _oll_err)

    # ── Free-tier cloud: prefer Mistral → Cohere before paying for Claude ───────
    # Reached only when local/llamacpp/Ollama all failed or aren't available.
    # In auto mode, try free-tier cloud providers before escalating to paid
    # Anthropic Claude.  Explicit local/code/claude modes bypass this entirely.
    if requested_mode in {"auto", ""}:
        _mk = _get_cloud_api_key("mistral", owner)
        if _mk:
            _log.info("Free cloud: routing to Mistral %s", _FREE_MISTRAL_MODEL)
            _msgs = build_router_messages(augmented_system, user_text, clean_history)
            try:
                async for token in _stream_mistral_tokens(
                    api_key=_mk, model=_FREE_MISTRAL_MODEL, messages=_msgs
                ):
                    yield token
                yield _SOURCE_SENTINEL + f"mistral:{_FREE_MISTRAL_MODEL}"
                return
            except Exception as _merr:
                _log.warning("Mistral free-tier (%s) failed: %s — trying Cohere", _FREE_MISTRAL_MODEL, _merr)

        _ck = _get_cloud_api_key("cohere", owner)
        if _ck:
            _log.info("Free cloud: routing to Cohere %s", _FREE_COHERE_MODEL)
            _msgs = build_router_messages(augmented_system, user_text, clean_history)
            try:
                async for token in _stream_cohere_tokens(
                    api_key=_ck, model=_FREE_COHERE_MODEL, messages=_msgs
                ):
                    yield token
                yield _SOURCE_SENTINEL + f"cohere:{_FREE_COHERE_MODEL}"
                return
            except Exception as _cerr:
                _log.warning("Cohere free-tier (%s) failed: %s — escalating to Claude", _FREE_COHERE_MODEL, _cerr)

    # ── Explicit Claude mode: stream instead of blocking ─────────────────────────
    if requested_mode == "claude":
        _ak = _get_cloud_api_key("anthropic", owner)
        if _ak:
            _log.info("Explicit claude mode: streaming via Claude SDK")
            _claude_msgs = build_router_messages(augmented_system, user_text, clean_history)
            _pref_model = str(active_cloud_model or owner.os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")).strip() or "claude-sonnet-4-6"
            _claude_tools = owner.core.TOOLS if owner.GUPPY_CORE_AVAILABLE else None
            def _explicit_claude_runner(name: str, args: dict) -> str:
                return str(owner.core.run_tool(name, args,
                    instance_name=instance_name, instance_type=instance_type))
            try:
                async for token in _stream_claude_with_tools(
                    api_key=_ak,
                    model=_pref_model,
                    system_prompt=augmented_system,
                    messages=_claude_msgs,
                    tools=_claude_tools,
                    tool_runner=_explicit_claude_runner,
                ):
                    yield token
                yield _SOURCE_SENTINEL + _pref_model
                return
            except Exception as _exc:
                _log.warning("Claude streaming failed (%s), falling back to non-streaming", _exc)

    # Non-streaming fallback (code mode / no router / last resort)
    response = call_unified_inference(
        owner=owner,
        user_text=user_text,
        system_prompt=system_prompt,
        mode=mode,
        history=history,
        instance_name=instance_name,
        instance_type=instance_type,
        active_local_model=active_local_model,
        active_cloud_model=active_cloud_model,
    )
    yield response
