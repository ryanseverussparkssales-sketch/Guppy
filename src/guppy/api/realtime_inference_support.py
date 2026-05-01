from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any, AsyncGenerator, Optional

import re as _re

from src.guppy.inference.streaming_backends import (
    _parse_oom_error,
    _repair_tool_json,
    _stream_openai_compat_tokens,
    _stream_mistral_tokens,
    _stream_cohere_tokens,
    _stream_claude_with_tools,
    _stream_llamacpp_tokens,
    _TOOL_CALL_GBNF,
)
from src.guppy.inference.context_injection import (
    augment_system_with_history,
    _bg_store_tool_outcome,
    _bg_summarize_session,
    _inject_semantic_context,
    _inject_semantic_context_async,
    _build_tool_context,
    _inject_tool_primer,
    _scan_workspace_sync,
    _inject_workspace_context_sync,
    _inject_workspace_context_async,
)

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
_TOOL_CALL_TAG_RE = _re.compile(  # noqa: F841 — used by _strip_tool_call_markers
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

# OOM error detection is now in src.guppy.inference.streaming_backends.
# _parse_oom_error, _repair_tool_json, _TOOL_CALL_GBNF are imported above and
# re-exported from here for backward compatibility.


def _strip_tool_call_markers(text: str) -> str:
    """Remove raw text-embedded tool call blocks from a model response.

    Returns the cleaned text (may be empty string if the whole response was
    a tool call block).
    """
    return _TOOL_CALL_TAG_RE.sub("", text).strip()


def _clean_local_response(text: str) -> str:
    """Strip tool call markup and return a user-friendly string.

    Applied to non-streaming local llama.cpp responses when
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


# _HISTORY_SNIPPET_MAX_CHARS and _HISTORY_TURNS_SHOWN moved to context_injection.
_CHAT_HISTORY_LIMIT = 12

# Context window in tokens for each backend.  Used by _trim_history_to_tokens()
# to dynamically cap history rather than using the fixed 12-turn limit.
# Rough estimate: 1 token ≈ 4 chars.  Reserve 1024 tokens for system prompt +
# current user message + model response headroom.
_BACKEND_CONTEXT_TOKENS: dict[str, int] = {
    "llamacpp-hermes3":    8192,    # Hermes 3 8B — 8K context
    "llamacpp-hermes4":   32768,    # Hermes 4 14B — 32K context
    "llamacpp-dispatch":   4096,    # Qwen2.5-3B — 4K context
    "llamacpp-phi4-mini": 131072,   # Phi-4-mini — 128K context
    "llamacpp-pepe":       8192,    # Assistant Pepe 8B
    "llamacpp-rocinante": 16384,    # Rocinante 12B
    "llamacpp-xlam":       8192,    # xLAM-2-8B
    "llamacpp-minicpm":    8192,    # MiniCPM-o
    "llamacpp-qwen3":     40960,    # Qwen3 35B MoE
    "llamacpp-chat":      32768,    # Llama 3.3 70B
    "llamacpp-gemma":      8192,    # Gemma 4 E4B
}
_DEFAULT_CONTEXT_TOKENS = 8192
_CONTEXT_RESERVE_TOKENS = 1024
_CHARS_PER_TOKEN = 4  # conservative estimate


def _trim_history_to_tokens(
    history: list[dict[str, str]],
    backend: str | None,
    limit: int = _CHAT_HISTORY_LIMIT,
) -> list[dict[str, str]]:
    """Return a token-budget-aware slice of chat history.

    Uses a rough chars-per-token estimate.  Never returns more than ``limit``
    turns.  Preserves the most *recent* turns when trimming.
    """
    max_tokens = _BACKEND_CONTEXT_TOKENS.get(backend or "", _DEFAULT_CONTEXT_TOKENS)
    budget_chars = (max_tokens - _CONTEXT_RESERVE_TOKENS) * _CHARS_PER_TOKEN
    # Apply fixed turn cap first (most-recent N turns)
    capped = history[-max(1, limit):]
    # Then trim from the front until the total char count fits in the budget
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
    # Apply token-aware trimming (respects both hard turn limit and context budget)
    return _trim_history_to_tokens(out, backend=backend, limit=limit)


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


# augment_system_with_history is now imported from context_injection above.
# It remains importable from this module for backward compatibility.

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



# All context-injection functions (_bg_store_tool_outcome, _bg_summarize_session,
# _inject_semantic_context, _inject_semantic_context_async, _build_tool_context,
# _inject_tool_primer, _scan_workspace_sync, _inject_workspace_context_sync,
# _inject_workspace_context_async) and their associated constants and primer
# strings are now in src.guppy.inference.context_injection and imported above.
# They remain importable from this module for backward compatibility.

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
            "Start a llamacpp backend (e.g. hermes3 on port 8087) first."
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
    # If the backend is not running, keep "auto" so the llama.cpp fallback chain
    # can try any reachable local backend instead of hard-failing stale selection.
    if active_local_model and active_local_model in _LOCAL_LLAMACPP_ROUTES and requested_mode in {"auto", ""}:
        from src.guppy.api.routes_backends import _port_alive as _llc_port_alive
        _backend_name = _LOCAL_LLAMACPP_ROUTES.get(active_local_model, "")
        _backend_url  = (_LOCAL_BACKENDS.get(_backend_name) or {}).get("default_url", "")
        _backend_port = int(_backend_url.rsplit(":", 1)[-1]) if ":" in _backend_url else 0
        if _backend_port and _llc_port_alive(_backend_port):
            requested_mode = "local"
        # else: backend offline — fall through as "auto"; cloud escalation may occur

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
        if requested_mode in {"local", "code", "claude"}:
            owner.logger.error("Inference failed in explicit mode '%s': %s", requested_mode, exc)
            raise
        if not owner.os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                f"Local inference failed ({exc}). "
                "Ensure at least one llama.cpp workspace agent (hermes4/hermes3) is running."
            ) from exc
        owner.logger.error("Unified inference failed: %s. Escalating to Claude Sonnet.", exc)
        return owner._call_claude_with_tools(
            user_text,
            augmented_system_prompt,
            instance_name=instance_name,
            instance_type=instance_type,
        )


def _call_llamacpp_sync(
    *,
    active_local_model: str,
    messages: list[dict],
    timeout: float = 90.0,
) -> str:
    """Synchronous non-streaming call to a llama.cpp OpenAI-compat endpoint."""
    import httpx
    backend = _LOCAL_LLAMACPP_ROUTES.get(active_local_model, "")
    cfg = _LOCAL_BACKENDS.get(backend, {})
    base = cfg.get("default_url", "").rstrip("/")
    if not base:
        raise RuntimeError(f"No URL configured for llamacpp backend {backend!r}")
    url = f"{base}/v1/chat/completions"
    payload = {
        "model": active_local_model,
        "messages": messages,
        "stream": False,
        "temperature": 0.7,
        "max_tokens": 2048,
    }
    resp = httpx.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return str((data.get("choices") or [{}])[0].get("message", {}).get("content", "")).strip()


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

    # If the surface has a llamacpp model selected, call it directly.
    if active_local_model and active_local_model in _LOCAL_LLAMACPP_ROUTES:
        from src.guppy.api.routes_backends import _port_alive as _llc_port_alive
        _backend = _LOCAL_LLAMACPP_ROUTES.get(active_local_model, "")
        _backend_url = (_LOCAL_BACKENDS.get(_backend) or {}).get("default_url", "")
        _backend_port = int(_backend_url.rsplit(":", 1)[-1]) if ":" in _backend_url else 0
        if _backend_port and _llc_port_alive(_backend_port):
            messages = build_router_messages(augmented_system_prompt, user_text, sanitize_chat_history(None))
            response = _call_llamacpp_sync(active_local_model=active_local_model, messages=messages)
            return response, "llamacpp", {"route_mode": "local", "model": active_local_model}

    # Use active_local_model only if it is NOT already a llamacpp-routed key.
    _local_model = (
        active_local_model
        if (active_local_model and active_local_model not in _LOCAL_LLAMACPP_ROUTES)
        else None
    )
    model_name = _local_model or router.LOCAL_TIER_MAP.get(task_type, router.LOCAL_MODEL)
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
            raise RuntimeError("Local-only paired mode failed (model unavailable)")
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

    if executor in {"llamacpp", "ollama", "ollama_paired"}:
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
    """Compatibility shim for legacy call sites.

    The runtime still exposes `_call_ollama_with_tools`, but local inference now
    goes through the selected llama.cpp/local runtime instead of direct Ollama.
    """
    return owner._call_selected_local_runtime(
        user_text,
        system_prompt,
        instance_name=instance_name,
        instance_type=instance_type,
        model_override=model_override,
    )


# ── Streaming support ─────────────────────────────────────────────────────────

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
    skip_tools: bool = False,
    surface: str = "",
) -> AsyncGenerator[str, None]:
    """
    Async generator yielding content tokens for the chat response.

    For llama.cpp backends: true token-level streaming via httpx.
    For Claude / fallbacks: yields the full response as a single chunk.
    """
    clean_history = sanitize_chat_history(history)

    # Auto-summarize long sessions every 10 turns so context accumulates in
    # semantic memory and gets injected into future prompts via RAG.
    if len(clean_history) >= 10 and len(clean_history) % 10 == 0:
        _bg_summarize_session(clean_history)

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

    # Classify task type early so agentic routing can intercept before general llama.cpp fallback.
    # Only meaningful for auto mode — explicit mode selections bypass this.
    _early_task_type: str = ""
    if requested_mode in {"auto", ""} and owner.GUPPY_CORE_AVAILABLE and owner.INFERENCE_ROUTER_AVAILABLE:
        try:
            _early_task_type = owner.get_router()._classify_task(user_text, augmented_system)
        except Exception:
            _early_task_type = ""

    # ─────────────────────────────────────────────────────────────────────────
    # SURFACE-PINNED ROUTING
    # Each surface has a fixed local preference order and specific cloud
    # fallback tiers (free Mistral/Cohere first, then paid Haiku or Sonnet).
    # This block runs for requests tagged with a surface= value and short-
    # circuits the generic classification routing below.
    # ─────────────────────────────────────────────────────────────────────────
    if surface in {"companion", "workspace", "codespace"} and requested_mode in {"auto", ""}:
        # Inject surface-specific tool primer + few-shot examples so local models
        # know exactly what tools exist here and when/how to invoke them.
        if not skip_tools:
            augmented_system = _inject_tool_primer(augmented_system, surface)

        from src.guppy.api.routes_backends import _port_alive as _sp_port_alive

        def _sp_backend_alive(key: str) -> str:
            """Return model name if backend is alive, else empty string."""
            _cfg = _LOCAL_BACKENDS.get(key, {})
            _url = _cfg.get("default_url", "")
            _port = int(_url.rsplit(":", 1)[-1]) if ":" in _url else 0
            _model = _LOCAL_BACKEND_DEFAULT_MODELS.get(key, "")
            return _model if (_port and _sp_port_alive(_port) and _model) else ""

        def _sp_make_messages(backend: str | None = None) -> list[dict]:
            return build_router_messages(augmented_system, user_text, sanitize_chat_history(history, backend=backend))

        def _sp_tool_runner(name: str, args: dict) -> str:
            return str(owner.core.run_tool(name, args,
                instance_name=instance_name, instance_type=instance_type))

        # Tools passed to companion are stripped to the basics (read/write memory,
        # create_reminder, web_fetch, workspace_task) — heavy agentic tools stay with workspace.
        _COMPANION_BASIC_TOOLS = [
            "memory_write", "memory_recall", "create_reminder",
            "web_fetch", "get_time", "workspace_task", "download_media",
        ]

        def _sp_companion_tools() -> list[dict] | None:
            if not owner.GUPPY_CORE_AVAILABLE:
                return None
            all_tools = _merged_openai_tools(owner) or []
            basic = [t for t in all_tools
                     if (t.get("function", {}).get("name") or t.get("name", "")) in _COMPANION_BASIC_TOOLS]
            return basic or None

        def _sp_full_tools() -> list[dict] | None:
            return _merged_openai_tools(owner) if owner.GUPPY_CORE_AVAILABLE else None

        # ── free cloud helpers ──
        def _sp_free_cloud_key() -> tuple[str, str]:
            """Return (provider, api_key) for first available free cloud provider."""
            _mk = _get_cloud_api_key("mistral", owner)
            if _mk:
                return ("mistral", _mk)
            _ck = _get_cloud_api_key("cohere", owner)
            if _ck:
                return ("cohere", _ck)
            return ("", "")

        async def _sp_stream_free_cloud(msgs: list[dict], tools, tr, label: str):
            _prov, _key = _sp_free_cloud_key()
            if not _key:
                return
            try:
                if _prov == "mistral":
                    async for tok in _stream_mistral_tokens(_key, "mistral-small-latest", msgs):
                        yield tok
                else:
                    async for tok in _stream_cohere_tokens(_key, "command-r-plus", msgs):
                        yield tok
                yield _SOURCE_SENTINEL + _prov
            except Exception as _fc_err:
                _log.warning("Surface %s free cloud (%s) failed: %s", surface, _prov, _fc_err)

        if surface == "companion":
            # Pass-1: Hermes3 (fast 8B, basic tools only)
            _h3m = _sp_backend_alive("llamacpp-hermes3")
            if _h3m:
                _msgs = _sp_make_messages("llamacpp-hermes3")
                _tools = _sp_companion_tools() if not skip_tools else None
                try:
                    async for tok in _stream_llamacpp_tokens(
                        model=_h3m, backend="llamacpp-hermes3",
                        messages=_msgs, tools=_tools, tool_runner=_sp_tool_runner,
                        max_tool_rounds=2,
                    ):
                        yield tok
                    yield _SOURCE_SENTINEL + f"llamacpp-hermes3:{_h3m}"
                    return
                except RuntimeError as _e:
                    _log.warning("Companion Hermes3 failed: %s — trying orchestrator", _e)

            # Pass-2: Phi-4-mini dispatch as orchestrator (complex escalation)
            for _orch_key in ("llamacpp-phi4-mini", "llamacpp-dispatch"):
                _om = _sp_backend_alive(_orch_key)
                if _om:
                    _msgs = _sp_make_messages(_orch_key)
                    try:
                        async for tok in _stream_llamacpp_tokens(
                            model=_om, backend=_orch_key,
                            messages=_msgs, tools=_sp_full_tools(), tool_runner=_sp_tool_runner,
                            max_tool_rounds=6,
                        ):
                            yield tok
                        yield _SOURCE_SENTINEL + f"{_orch_key}:{_om}"
                        return
                    except RuntimeError as _e:
                        _log.warning("Companion orchestrator %s failed: %s", _orch_key, _e)

            # Pass-3: free cloud (Mistral or Cohere)
            _prov, _fck = _sp_free_cloud_key()
            if _fck:
                _msgs = _sp_make_messages()
                try:
                    _free_model = "mistral-small-latest" if _prov == "mistral" else "command-r-plus"
                    _stream_fn = _stream_mistral_tokens if _prov == "mistral" else _stream_cohere_tokens
                    async for tok in _stream_fn(_fck, _free_model, _msgs):
                        yield tok
                    yield _SOURCE_SENTINEL + _prov
                    return
                except Exception as _fe:
                    _log.warning("Companion free cloud (%s) failed: %s", _prov, _fe)

            # Pass-4: paid Haiku (cheap/fast companion fallback)
            _ak = _get_cloud_api_key("anthropic", owner)
            if _ak:
                _msgs = _sp_make_messages()
                try:
                    async for tok in _stream_claude_with_tools(
                        api_key=_ak, model="claude-haiku-4-5-20251001",
                        system_prompt=augmented_system, messages=_msgs,
                        tools=None, tool_runner=_sp_tool_runner,
                    ):
                        yield tok
                    yield _SOURCE_SENTINEL + "claude-haiku-4-5-20251001"
                    return
                except Exception as _pe:
                    _log.warning("Companion paid Haiku failed: %s", _pe)

            yield "⚠️ No backend available for companion surface."
            return

        elif surface == "workspace":
            # Pass-1: Phi-4-mini or dispatch as orchestrator
            for _orch_key in ("llamacpp-phi4-mini", "llamacpp-dispatch"):
                _om = _sp_backend_alive(_orch_key)
                if _om:
                    _msgs = _sp_make_messages(_orch_key)
                    try:
                        async for tok in _stream_llamacpp_tokens(
                            model=_om, backend=_orch_key,
                            messages=_msgs, tools=_sp_full_tools(), tool_runner=_sp_tool_runner,
                            max_tool_rounds=8,
                        ):
                            yield tok
                        yield _SOURCE_SENTINEL + f"{_orch_key}:{_om}"
                        return
                    except RuntimeError as _e:
                        _log.warning("Workspace orchestrator %s failed: %s", _orch_key, _e)

            # Pass-2: workers — Hermes4 then Hermes3
            for _w_key in ("llamacpp-hermes4", "llamacpp-hermes3"):
                _wm = _sp_backend_alive(_w_key)
                if _wm:
                    _msgs = _sp_make_messages(_w_key)
                    try:
                        async for tok in _stream_llamacpp_tokens(
                            model=_wm, backend=_w_key,
                            messages=_msgs, tools=_sp_full_tools(), tool_runner=_sp_tool_runner,
                            max_tool_rounds=6,
                        ):
                            yield tok
                        yield _SOURCE_SENTINEL + f"{_w_key}:{_wm}"
                        return
                    except RuntimeError as _e:
                        _log.warning("Workspace worker %s failed: %s", _w_key, _e)

            # Pass-3: free cloud
            _prov, _fck = _sp_free_cloud_key()
            if _fck:
                _msgs = _sp_make_messages()
                try:
                    _free_model = "mistral-small-latest" if _prov == "mistral" else "command-r-plus"
                    _stream_fn = _stream_mistral_tokens if _prov == "mistral" else _stream_cohere_tokens
                    async for tok in _stream_fn(_fck, _free_model, _msgs):
                        yield tok
                    yield _SOURCE_SENTINEL + _prov
                    return
                except Exception as _fe:
                    _log.warning("Workspace free cloud (%s) failed: %s", _prov, _fe)

            # Pass-4: paid Sonnet (capable workspace fallback)
            _ak = _get_cloud_api_key("anthropic", owner)
            if _ak:
                _msgs = _sp_make_messages()
                try:
                    async for tok in _stream_claude_with_tools(
                        api_key=_ak, model="claude-sonnet-4-6",
                        system_prompt=augmented_system, messages=_msgs,
                        tools=_sp_full_tools(), tool_runner=_sp_tool_runner,
                    ):
                        yield tok
                    yield _SOURCE_SENTINEL + "claude-sonnet-4-6"
                    return
                except Exception as _pe:
                    _log.warning("Workspace paid Sonnet failed: %s", _pe)

            yield "⚠️ No backend available for workspace surface."
            return

        elif surface == "codespace":
            # No dedicated orchestrator — direct to workers
            for _w_key in ("llamacpp-hermes4", "llamacpp-hermes3"):
                _wm = _sp_backend_alive(_w_key)
                if _wm:
                    _msgs = _sp_make_messages(_w_key)
                    try:
                        async for tok in _stream_llamacpp_tokens(
                            model=_wm, backend=_w_key,
                            messages=_msgs, tools=_sp_full_tools(), tool_runner=_sp_tool_runner,
                            max_tool_rounds=6,
                        ):
                            yield tok
                        yield _SOURCE_SENTINEL + f"{_w_key}:{_wm}"
                        return
                    except RuntimeError as _e:
                        _log.warning("Codespace worker %s failed: %s", _w_key, _e)

            # Free cloud fallback
            _prov, _fck = _sp_free_cloud_key()
            if _fck:
                _msgs = _sp_make_messages()
                try:
                    _free_model = "mistral-small-latest" if _prov == "mistral" else "command-r-plus"
                    _stream_fn = _stream_mistral_tokens if _prov == "mistral" else _stream_cohere_tokens
                    async for tok in _stream_fn(_fck, _free_model, _msgs):
                        yield tok
                    yield _SOURCE_SENTINEL + _prov
                    return
                except Exception as _fe:
                    _log.warning("Codespace free cloud (%s) failed: %s", _prov, _fe)

            # Paid Sonnet
            _ak = _get_cloud_api_key("anthropic", owner)
            if _ak:
                _msgs = _sp_make_messages()
                try:
                    async for tok in _stream_claude_with_tools(
                        api_key=_ak, model="claude-sonnet-4-6",
                        system_prompt=augmented_system, messages=_msgs,
                        tools=_sp_full_tools(), tool_runner=_sp_tool_runner,
                    ):
                        yield tok
                    yield _SOURCE_SENTINEL + "claude-sonnet-4-6"
                    return
                except Exception as _pe:
                    _log.warning("Codespace paid Sonnet failed: %s", _pe)

            yield "⚠️ No backend available for codespace surface."
            return

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
        if _xlam_port and not _llc_port_alive(_xlam_port):
            try:
                from src.guppy.api.routes_backends import ensure_backend_started
                ensure_backend_started(_XLAM_BACKEND)
            except Exception as exc:
                _log.warning("xLAM auto-start failed: %s", exc)

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
                        escalate_on_all_tool_errors=True,
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

        # Qwen3 offline (or failed) — try Hermes 4 (always-on workspace agent) before cloud.
        # Never fall through to Pepe for agentic tasks.
        _H4_AGENTIC = "llamacpp-hermes4"
        _h4a_cfg = _LOCAL_BACKENDS.get(_H4_AGENTIC, {})
        _h4a_url = _h4a_cfg.get("default_url", "")
        _h4a_port = int(_h4a_url.rsplit(":", 1)[-1]) if ":" in _h4a_url else 0
        if _h4a_port and _llc_port_alive(_h4a_port):
            _h4a_model = _LOCAL_BACKEND_DEFAULT_MODELS.get(_H4_AGENTIC, "")
            if _h4a_model:
                _log.info("Agentic task: Qwen3 offline → Hermes 4 (port %d)", _h4a_port)
                _h4a_messages = build_router_messages(augmented_system, user_text, sanitize_chat_history(history))
                _h4a_tools = _merged_openai_tools(owner)
                def _h4a_tool_runner(name: str, args: dict) -> str:
                    return str(owner.core.run_tool(name, args,
                        instance_name=instance_name, instance_type=instance_type))
                try:
                    async for token in _stream_llamacpp_tokens(
                        model=_h4a_model,
                        backend=_H4_AGENTIC,
                        messages=_h4a_messages,
                        tools=_h4a_tools,
                        tool_runner=_h4a_tool_runner,
                        max_tool_rounds=8,
                    ):
                        yield token
                    yield _SOURCE_SENTINEL + f"{_H4_AGENTIC}:{_h4a_model}"
                    return
                except RuntimeError as _h4a_err:
                    _log.warning("Hermes 4 agentic fallback failed: %s — escalating to Claude Sonnet", _h4a_err)

        _ak = _get_cloud_api_key("anthropic", owner)
        if _ak:
            _log.info("Agentic task: local agents offline, routing to Claude Sonnet (streaming)")
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

    # ── Complex routing: Hermes 4 (always-on) → Claude Sonnet ────────────────────
    # For complex tasks in auto mode, try the always-on Hermes 4 workspace agent
    # before touching the cloud or the general local pool. Hermes 4 at 14B handles
    # multi-step reasoning and tool chains well; Sonnet is the cloud safety net.
    if _early_task_type == "complex" and requested_mode in {"auto", ""} and owner.GUPPY_CORE_AVAILABLE:
        from src.guppy.api.routes_backends import _port_alive as _llc_port_alive
        _H4_COMPLEX = "llamacpp-hermes4"
        _h4c_cfg = _LOCAL_BACKENDS.get(_H4_COMPLEX, {})
        _h4c_url = _h4c_cfg.get("default_url", "")
        _h4c_port = int(_h4c_url.rsplit(":", 1)[-1]) if ":" in _h4c_url else 0
        if _h4c_port and _llc_port_alive(_h4c_port):
            _h4c_model = _LOCAL_BACKEND_DEFAULT_MODELS.get(_H4_COMPLEX, "")
            if _h4c_model:
                _log.info("Complex task → Hermes 4 workspace agent (port %d)", _h4c_port)
                _h4c_messages = build_router_messages(augmented_system, user_text, sanitize_chat_history(history))
                _h4c_tools = _merged_openai_tools(owner)
                def _h4c_tool_runner(name: str, args: dict) -> str:
                    return str(owner.core.run_tool(name, args,
                        instance_name=instance_name, instance_type=instance_type))
                try:
                    async for token in _stream_llamacpp_tokens(
                        model=_h4c_model,
                        backend=_H4_COMPLEX,
                        messages=_h4c_messages,
                        tools=_h4c_tools,
                        tool_runner=_h4c_tool_runner,
                        max_tool_rounds=6,
                    ):
                        yield token
                    yield _SOURCE_SENTINEL + f"{_H4_COMPLEX}:{_h4c_model}"
                    return
                except RuntimeError as _h4c_err:
                    _log.warning("Hermes 4 complex route failed: %s — escalating to Sonnet", _h4c_err)

        _ak = _get_cloud_api_key("anthropic", owner)
        if _ak:
            _log.info("Complex task: Hermes 4 offline, routing to Claude Sonnet")
            _complex_msgs = build_router_messages(augmented_system, user_text, clean_history)
            _complex_tools = owner.core.TOOLS if owner.GUPPY_CORE_AVAILABLE else None
            def _complex_tool_runner(name: str, args: dict) -> str:
                return str(owner.core.run_tool(name, args,
                    instance_name=instance_name, instance_type=instance_type))
            try:
                async for token in _stream_claude_with_tools(
                    api_key=_ak,
                    model="claude-sonnet-4-6",
                    system_prompt=augmented_system,
                    messages=_complex_msgs,
                    tools=_complex_tools,
                    tool_runner=_complex_tool_runner,
                ):
                    yield token
                yield _SOURCE_SENTINEL + "claude-sonnet-4-6"
                return
            except Exception as _cplx_err:
                _log.warning("Claude Sonnet complex fallback failed: %s — continuing to local", _cplx_err)
        # else: fall through to general llama.cpp path

    # ── simple → Hermes 3 (fast 8B, uncensored) → Hermes 4 fallback ─────────────
    if _early_task_type == "simple" and requested_mode in {"auto", ""} and owner.GUPPY_CORE_AVAILABLE:
        from src.guppy.api.routes_backends import _port_alive as _llc_port_alive
        _SIMPLE_ORDER = [
            ("llamacpp-hermes3", _LOCAL_BACKEND_DEFAULT_MODELS.get("llamacpp-hermes3", "")),
            ("llamacpp-hermes4", _LOCAL_BACKEND_DEFAULT_MODELS.get("llamacpp-hermes4", "")),
        ]
        for _sb, _sm in _SIMPLE_ORDER:
            _sc = _LOCAL_BACKENDS.get(_sb, {})
            _su = _sc.get("default_url", "")
            _sp = int(_su.rsplit(":", 1)[-1]) if ":" in _su else 0
            if not _sp or not _llc_port_alive(_sp) or not _sm:
                continue
            _s_msgs = build_router_messages(augmented_system, user_text, sanitize_chat_history(history))
            _s_tools = _merged_openai_tools(owner)
            def _s_tr(name: str, args: dict, _i=instance_name, _t=instance_type) -> str:
                return str(owner.core.run_tool(name, args, instance_name=_i, instance_type=_t))
            try:
                async for token in _stream_llamacpp_tokens(
                    model=_sm, backend=_sb, messages=_s_msgs, tools=_s_tools, tool_runner=_s_tr,
                ):
                    yield token
                yield _SOURCE_SENTINEL + f"{_sb}:{_sm}"
                return
            except RuntimeError:
                continue

    # ── teaching → Hermes 4 (quality 14B, always-on) → Hermes 3 fallback ────────
    if _early_task_type == "teaching" and requested_mode in {"auto", ""} and owner.GUPPY_CORE_AVAILABLE:
        from src.guppy.api.routes_backends import _port_alive as _llc_port_alive
        _TEACH_ORDER = [
            ("llamacpp-hermes4", _LOCAL_BACKEND_DEFAULT_MODELS.get("llamacpp-hermes4", "")),
            ("llamacpp-hermes3", _LOCAL_BACKEND_DEFAULT_MODELS.get("llamacpp-hermes3", "")),
        ]
        for _tb, _tm in _TEACH_ORDER:
            _tc = _LOCAL_BACKENDS.get(_tb, {})
            _tu = _tc.get("default_url", "")
            _tp = int(_tu.rsplit(":", 1)[-1]) if ":" in _tu else 0
            if not _tp or not _llc_port_alive(_tp) or not _tm:
                continue
            _t_msgs = build_router_messages(augmented_system, user_text, sanitize_chat_history(history))
            _t_tools = _merged_openai_tools(owner)
            def _t_tr(name: str, args: dict, _i=instance_name, _t=instance_type) -> str:
                return str(owner.core.run_tool(name, args, instance_name=_i, instance_type=_t))
            try:
                async for token in _stream_llamacpp_tokens(
                    model=_tm, backend=_tb, messages=_t_msgs, tools=_t_tools, tool_runner=_t_tr,
                ):
                    yield token
                yield _SOURCE_SENTINEL + f"{_tb}:{_tm}"
                return
            except RuntimeError:
                continue

    is_llamacpp = bool(active_local_model and active_local_model in _LOCAL_LLAMACPP_ROUTES)
    # Tracks whether llamacpp was attempted but the backend was not reachable.
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
                # skip_tools=True: caller (e.g. workspace two-pass buffering) handles
                # tool execution itself via <tool_call> markup detection; passing
                # OpenAI function-calling tools here causes hermes4 to loop.
                _openai_tools = None if skip_tools else _merged_openai_tools(owner)

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
                # Backend not running — fall through to Mode-A opportunistic chain.
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
        from src.guppy.api.routes_backends import ensure_backend_started
        _MODE_A_FALLBACK_ORDER = [
            "llamacpp-hermes4", "llamacpp-hermes3",
            "llamacpp-chat",    # 70B CPU -- zero VRAM, high quality
            "llamacpp-pepe", "llamacpp-rocinante",
            "llamacpp-minicpm", "llamacpp-dispatch",
        ]
        for _fb_backend in _MODE_A_FALLBACK_ORDER:
            _fb_cfg = _LOCAL_BACKENDS.get(_fb_backend, {})
            _fb_url = _fb_cfg.get("default_url", "")
            _fb_port = int(_fb_url.rsplit(":", 1)[-1]) if ":" in _fb_url else 0
            if _fb_backend == "llamacpp-chat" and _fb_port and not _llc_port_alive(_fb_port):
                try:
                    ensure_backend_started(_fb_backend)
                except Exception as exc:
                    _log.warning("70B auto-start failed: %s", exc)
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

    # Free-tier cloud: prefer Mistral -> Cohere before paying for Claude.
    # Reached only when all local llama.cpp/OpenAI-compatible paths failed or are unavailable.
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
