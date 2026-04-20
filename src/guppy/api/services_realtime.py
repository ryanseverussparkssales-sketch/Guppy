from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
import urllib.request
from functools import partial
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

from fastapi import HTTPException, UploadFile

from src.guppy.api import services_briefing
from src.guppy.api.chat_idempotency import (
    _prune_chat_idempotency_records,
    build_chat_request_fingerprint as _build_chat_request_fingerprint_impl,
    clear_chat_idempotency_key,
    complete_chat_idempotency_key,
    register_chat_idempotency_key,
    resolve_chat_idempotency_key,
    takeover_chat_idempotency_key,
)

_RICH_PROMPT_DIRECT_CUES = (
    "remember",
    "recall",
    "earlier",
    "previous",
    "follow up",
    "continue",
    "same as",
    "project",
    "task",
    "todo",
    "debug",
    "refactor",
    "design",
    "compare",
    "tradeoff",
    "teach",
    "explain",
    "why",
    "how",
)


def prune_chat_idempotency_records(now: float | None = None) -> None:
    _prune_chat_idempotency_records(now)


def build_chat_request_fingerprint(request: Any) -> str:
    return _build_chat_request_fingerprint_impl(
        message=str(getattr(request, "message", "") or ""),
        session_id=getattr(request, "session_id", None),
        mode=getattr(request, "mode", None),
        persona=getattr(request, "persona", None),
        history=getattr(request, "history", None),
    )


def sanitize_chat_history(history: Any, limit: int = 12) -> list[dict[str, str]]:
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
        out.append({"role": role, "content": content[:2000]})
    return out


def should_use_rich_chat_prompt_context(request: Any) -> bool:
    return should_use_rich_prompt_context(
        message=request.message,
        mode=request.mode,
        history=request.history,
    )


def should_use_rich_prompt_context(
    *,
    message: str,
    mode: str | None = None,
    history: Any = None,
) -> bool:
    if sanitize_chat_history(history):
        return True

    normalized_mode = str(mode or "auto").strip().lower()
    if normalized_mode in {"teaching", "code", "vault"}:
        return True

    normalized_message = str(message or "").strip()
    if not normalized_message:
        return False
    if len(normalized_message) >= 80:
        return True

    normalized = re.sub(r"\s+", " ", normalized_message.lower())
    if any(cue in normalized for cue in _RICH_PROMPT_DIRECT_CUES):
        return True
    if "?" in normalized_message and len(normalized.split()) >= 10:
        return True
    return False


def build_chat_system_prompt(
    owner: Any,
    *,
    message: str,
    session_id: str | None = None,
    mode: str | None = None,
    persona: str | None = None,
    model_id: str | None = None,
    history: Any = None,
) -> str:
    use_rich_prompt_context = should_use_rich_prompt_context(
        message=message,
        mode=mode,
        history=history,
    )
    system_prompt = owner.core.get_startup_system(
        session_id=session_id,
        query_context=message,
        include_memory_context=use_rich_prompt_context,
        include_semantic_context=use_rich_prompt_context,
    )
    try:
        _persona_payload, overlay = owner.build_persona_prompt_overlay(
            requested_persona=str(persona or "").strip(),
            model_id=str(model_id or "").strip(),
        )
        if overlay:
            system_prompt += "\n\n" + overlay
    except Exception:
        pass
    return system_prompt


async def save_voice_upload_tempfile(owner: Any, file: UploadFile) -> str:
    filename = str(getattr(file, "filename", "") or "").strip()
    content_type = str(getattr(file, "content_type", "") or "").strip().lower()
    if not filename:
        raise HTTPException(status_code=400, detail="Audio file is required")
    if content_type and not (
        content_type.startswith("audio/") or content_type == "application/octet-stream"
    ):
        raise HTTPException(status_code=400, detail="Unsupported audio upload type")

    suffix = Path(filename).suffix or ".wav"
    bytes_written = 0
    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = temp_file.name
            while True:
                chunk = await file.read(owner.VOICE_UPLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > owner.VOICE_UPLOAD_MAX_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Audio upload exceeds {owner.VOICE_UPLOAD_MAX_BYTES} bytes",
                    )
                temp_file.write(chunk)
        if bytes_written <= 0:
            raise HTTPException(status_code=400, detail="Audio file was empty")
        return temp_path
    except HTTPException:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)
        raise
    except Exception:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)
        raise
    finally:
        await file.close()


normalize_brief_text = services_briefing.normalize_brief_text
looks_like_brief_affirmation = services_briefing.looks_like_brief_affirmation
history_offered_morning_brief = services_briefing.history_offered_morning_brief
request_is_morning_brief = services_briefing.request_is_morning_brief
latest_daily_report_path = services_briefing.latest_daily_report_path
strip_markdown_prefix = services_briefing.strip_markdown_prefix
parse_markdown_sections = services_briefing.parse_markdown_sections
preview_markdown_section = services_briefing.preview_markdown_section
preview_plain_block = services_briefing.preview_plain_block
build_morning_brief_response = services_briefing.build_morning_brief_response


async def run_blocking(func, *args, timeout_seconds: float, **kwargs):
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(partial(func, *args, **kwargs)),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Request timed out") from exc


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


def request_is_cacheable(owner: Any, request: Any) -> bool:
    if not owner.response_cache_enabled():
        return False
    if request.session_id:
        return False
    if sanitize_chat_history(request.history):
        return False
    mode = (request.mode or "auto").strip().lower()
    if mode in {"teaching", "vault"}:
        return False
    return bool((request.message or "").strip())


def augment_system_with_history(system_prompt: str, history: list[dict[str, str]]) -> str:
    if not history:
        return system_prompt
    lines = ["LIVE SESSION HISTORY (RECENT TURNS):"]
    for item in history[-8:]:
        speaker = "Ryan" if item.get("role") == "user" else "Guppy"
        snippet = item.get("content", "").replace("\n", " ").strip()
        if len(snippet) > 240:
            snippet = snippet[:240] + "..."
        lines.append(f"- {speaker}: {snippet}")
    return f"{system_prompt}\n\n" + "\n".join(lines)


def is_rate_limited_error(error: Exception | str) -> bool:
    txt = str(error or "").lower()
    return "429" in txt or "rate limit" in txt or "too many requests" in txt


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
        owner.logger.warning("Router unavailable, falling back to Claude")
        return owner._call_claude_with_tools(
            user_text,
            system_prompt,
            instance_name=instance_name,
            instance_type=instance_type,
        )

    router = owner.get_router()
    clean_history = sanitize_chat_history(history)
    augmented_system_prompt = augment_system_with_history(system_prompt, clean_history)
    router_messages = build_router_messages(augmented_system_prompt, user_text, clean_history)
    requested_mode = (
        mode or owner.os.environ.get("GUPPY_DEFAULT_MODE", "auto") or "auto"
    ).strip().lower()

    try:
        if requested_mode == "local":
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
                source = str(result.get("source", "local"))
                metadata = dict(result.get("metadata", {}))
            else:
                response = owner._call_selected_local_runtime(
                    user_text,
                    augmented_system_prompt,
                    instance_name=instance_name,
                    instance_type=instance_type,
                    model_override=model_name,
                )
                source = "local"
                metadata = {"route_mode": "local", "model": model_name}
        elif requested_mode == "code":
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
            response = str(result.get("response", ""))
            source = str(result.get("source", "local"))
            metadata = dict(result.get("metadata", {}))
        else:
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
                metadata = {"route_decision": route_decision}
            elif executor in {"ollama", "ollama_paired"}:
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
                    source = str(result.get("source", "local"))
                    metadata = dict(result.get("metadata", {}))
                else:
                    response = owner._call_selected_local_runtime(
                        user_text,
                        augmented_system_prompt,
                        instance_name=instance_name,
                        instance_type=instance_type,
                        model_override=target_model or None,
                    )
                    source = "local"
                    metadata = {"route_decision": route_decision}
            else:
                response, source, metadata = router.query_smart(
                    system_prompt=augmented_system_prompt,
                    user_text=user_text,
                    tools=owner.core.TOOLS,
                    messages=router_messages,
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


async def stream_chunks(text: str) -> AsyncGenerator[str, None]:
    for chunk in text.split():
        yield chunk + " "
