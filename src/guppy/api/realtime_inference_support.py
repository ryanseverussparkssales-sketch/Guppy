from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any, AsyncGenerator, Optional

_log = logging.getLogger(__name__)

_CHAT_CONTENT_MAX_CHARS = 2000
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


def call_unified_inference(
    owner: Any,
    user_text: str,
    system_prompt: str,
    mode: Optional[str] = None,
    history: Optional[list[dict[str, str]]] = None,
    instance_name: Optional[str] = None,
    instance_type: Optional[str] = None,
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
    router_messages = build_router_messages(augmented_system_prompt, user_text, clean_history)
    requested_mode = (
        mode or owner.os.environ.get("GUPPY_DEFAULT_MODE", "auto") or "auto"
    ).strip().lower()

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
            )

        owner.logger.info(
            "Inference completed via %s. Tokens: %s",
            source,
            metadata.get("usage", {}).get("output_tokens", "?"),
        )
        return response

    except Exception as exc:
        if requested_mode in {"local", "code", "claude", "ollama"}:
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
) -> tuple[str, str, dict[str, Any]]:
    task_type = router._classify_task(user_text, augmented_system_prompt)
    model_name = router.LOCAL_TIER_MAP.get(task_type, router.LOCAL_MODEL)
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
            preferred_model=target_model or None,
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
            model_override=target_model or None,
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
                    "num_predict": 512,
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
        content = (msg.get("content") or "").strip()
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
        "options": {"temperature": 0.8, "top_p": 0.95, "top_k": 40, "num_predict": 512},
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
) -> AsyncGenerator[str, None]:
    """
    Async generator yielding content tokens for the chat response.

    For Ollama backends: true token-level streaming via httpx.
    For Claude / fallbacks: yields the full response as a single chunk.
    """
    clean_history = sanitize_chat_history(history)
    augmented_system = augment_system_with_history(system_prompt, clean_history)
    augmented_system = await _inject_semantic_context_async(augmented_system, user_text, owner)
    requested_mode = (mode or owner.os.environ.get("GUPPY_DEFAULT_MODE", "auto") or "auto").strip().lower()

    can_stream_ollama = (
        owner.GUPPY_CORE_AVAILABLE
        and owner.INFERENCE_ROUTER_AVAILABLE
        and requested_mode in {"local", "auto", ""}
    )

    if can_stream_ollama:
        try:
            router = owner.get_router()
            task_type = router._classify_task(user_text, augmented_system)
            model_name = router.LOCAL_TIER_MAP.get(task_type, router.LOCAL_MODEL)
            messages = build_router_messages(augmented_system, user_text, clean_history)
            tools = owner.core.to_ollama_tools(owner.core.TOOLS) if owner.GUPPY_CORE_AVAILABLE else None

            tool_calls_accumulated: list = []
            all_messages = list(messages)
            assistant_content = ""

            async for token in _stream_ollama_tokens(
                model=model_name,
                messages=all_messages,
                tools=tools,
            ):
                if token.startswith(_TOOL_CALL_SENTINEL):
                    tool_calls_accumulated = json.loads(token[len(_TOOL_CALL_SENTINEL):])
                else:
                    assistant_content += token
                    yield token

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
            return

        except RuntimeError:
            pass  # fall through to non-streaming fallback

    # Non-streaming fallback (Claude / no router / explicit code mode)
    response = call_unified_inference(
        owner=owner,
        user_text=user_text,
        system_prompt=system_prompt,
        mode=mode,
        history=history,
        instance_name=instance_name,
        instance_type=instance_type,
    )
    yield response
