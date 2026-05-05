from __future__ import annotations

import asyncio
import re
import tempfile
import time
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


# ── System prompt cache — avoids rebuilding identical prompts within 60 s ─────
# Key: (surface, persona, mode) — message/history intentionally excluded since
# they don't affect the static parts of the system prompt.
_SYSTEM_PROMPT_CACHE: dict[tuple, tuple[str, float]] = {}
_SYSTEM_PROMPT_TTL = 60.0  # seconds


def _get_cached_system_prompt(cache_key: tuple) -> str | None:
    entry = _SYSTEM_PROMPT_CACHE.get(cache_key)
    if entry:
        prompt, ts = entry
        if time.monotonic() - ts < _SYSTEM_PROMPT_TTL:
            return prompt
        del _SYSTEM_PROMPT_CACHE[cache_key]
    return None


def _cache_system_prompt(cache_key: tuple, prompt: str) -> None:
    # Keep cache small — evict oldest if over 20 entries
    if len(_SYSTEM_PROMPT_CACHE) >= 20:
        oldest = min(_SYSTEM_PROMPT_CACHE, key=lambda k: _SYSTEM_PROMPT_CACHE[k][1])
        _SYSTEM_PROMPT_CACHE.pop(oldest, None)
    _SYSTEM_PROMPT_CACHE[cache_key] = (prompt, time.monotonic())


def build_chat_system_prompt(
    owner: Any,
    *,
    message: str,
    session_id: str | None = None,
    mode: str | None = None,
    persona: str | None = None,
    model_id: str | None = None,
    history: Any = None,
    surface: str | None = None,
) -> str:
    # Check cache first — static portions don't depend on message/history
    _cache_key = (str(surface or ""), str(persona or ""), str(mode or ""))
    _cached = _get_cached_system_prompt(_cache_key)
    if _cached is not None:
        return _cached
    from datetime import datetime as _dt
    from src.guppy.api._server_fragment_bootstrap import _WORKSPACE_TOOL_BLOCK
    _now = _dt.now()
    _date_line = (
        f"Current date and time: {_now.strftime('%A, %B %d, %Y')} at {_now.strftime('%I:%M %p')}. "
        f"User's name: Ryan Sparks."
    )
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
    system_prompt = _date_line + "\n\n" + system_prompt
    # Inject user-authored instructions (booklet sections with mode="always")
    try:
        from src.guppy.api.routes_booklet import compile_booklet
        booklet_text = compile_booklet()
        if booklet_text:
            system_prompt += "\n\n" + booklet_text
    except Exception:
        pass
    resolved_surface = str(surface or "").strip().lower()
    if resolved_surface == "companion":
        try:
            import sqlite3
            from src.guppy.paths import USER_DATA_DIR
            db_path = str(USER_DATA_DIR / "surface.db")
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT system_prompt FROM surface_config WHERE surface = 'companion'"
                ).fetchone()
            if row and row["system_prompt"]:
                system_prompt += "\n\n" + str(row["system_prompt"]).strip()
        except Exception:
            pass
    # workspace surface uses _WORKSPACE_TOOL_SCHEMA (routes_realtime) + _WORKSPACE_TOOL_PRIMER
    # (context_injection) — skip the legacy bootstrap block to avoid triple tool-list bloat
    if resolved_surface in ("chat", "") or (not resolved_surface):
        system_prompt += "\n\n" + _WORKSPACE_TOOL_BLOCK
    try:
        _persona_payload, overlay = owner.build_persona_prompt_overlay(
            requested_persona=str(persona or "").strip(),
            model_id=str(model_id or "").strip(),
        )
        if overlay:
            system_prompt += "\n\n" + overlay
    except Exception:
        pass
    _cache_system_prompt(_cache_key, system_prompt)
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
