from __future__ import annotations

import asyncio
import re
import tempfile
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
from src.guppy.api.realtime_inference_support import (
    augment_system_with_history,
    build_router_messages,
    call_claude_with_tools,
    call_ollama_with_tools,
    call_unified_inference,
    extract_text_from_anthropic_blocks,
    is_rate_limited_error,
    sanitize_chat_history,
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


async def stream_chunks(text: str) -> AsyncGenerator[str, None]:
    for chunk in text.split():
        yield chunk + " "
