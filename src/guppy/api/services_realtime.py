from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import tempfile
import threading
import time
import urllib.request
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

from fastapi import HTTPException, UploadFile


_CHAT_IDEMPOTENCY_TTL_SECONDS = max(
    60.0,
    float(os.environ.get("GUPPY_CHAT_IDEMPOTENCY_TTL_SECONDS", "300") or "300"),
)
_chat_idempotency_lock = threading.Lock()
_chat_idempotency_records: dict[str, dict[str, Any]] = {}

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

_MORNING_BRIEF_DIRECT_PHRASES = (
    "morning brief",
    "daily brief",
    "brief the day",
    "start my day",
    "what's on deck",
    "whats on deck",
)
_MORNING_BRIEF_AFFIRMATIONS = {
    "yes",
    "yes please",
    "sure",
    "sure please",
    "do it",
    "go ahead",
    "lets do it",
    "let's do it",
    "please do",
}


def prune_chat_idempotency_records(now: float | None = None) -> None:
    cutoff = (time.monotonic() if now is None else now) - _CHAT_IDEMPOTENCY_TTL_SECONDS
    stale_keys = [
        key
        for key, record in _chat_idempotency_records.items()
        if float(record.get("created_at", 0.0) or 0.0) < cutoff
    ]
    for key in stale_keys:
        _chat_idempotency_records.pop(key, None)


def build_chat_request_fingerprint(request: Any) -> str:
    payload = {
        "message": request.message,
        "session_id": request.session_id or "",
        "mode": request.mode or "",
        "persona": request.persona or "",
        "history": request.history or [],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def register_chat_idempotency_key(key: str, fingerprint: str) -> tuple[bool, threading.Event]:
    now = time.monotonic()
    with _chat_idempotency_lock:
        prune_chat_idempotency_records(now)
        record = _chat_idempotency_records.get(key)
        if isinstance(record, dict):
            return False, record["event"]
        event = threading.Event()
        _chat_idempotency_records[key] = {
            "created_at": now,
            "event": event,
            "fingerprint": fingerprint,
            "response": None,
            "error": None,
            "status": None,
            "headers": None,
        }
        return True, event


def resolve_chat_idempotency_key(key: str, fingerprint: str) -> dict[str, Any] | None:
    with _chat_idempotency_lock:
        record = _chat_idempotency_records.get(key)
        if not isinstance(record, dict):
            return None
        if str(record.get("fingerprint", "") or "") != fingerprint:
            return None
        event = record.get("event")
        if not isinstance(event, threading.Event) or not event.is_set():
            return None
        response = record.get("response")
        payload: dict[str, Any] = {
            "status": int(record.get("status", 500) or 500),
            "headers": dict(record.get("headers", {}))
            if isinstance(record.get("headers"), dict)
            else None,
        }
        if isinstance(response, dict):
            payload["response"] = dict(response)
            return payload
        error = record.get("error")
        if error:
            payload["error"] = error
            return payload
        return None


def takeover_chat_idempotency_key(
    key: str, fingerprint: str
) -> tuple[bool, threading.Event, bool]:
    now = time.monotonic()
    with _chat_idempotency_lock:
        prune_chat_idempotency_records(now)
        record = _chat_idempotency_records.get(key)
        if isinstance(record, dict):
            event = record.get("event")
            if not isinstance(event, threading.Event):
                event = threading.Event()
            stored_fingerprint = str(record.get("fingerprint", "") or "")
            if stored_fingerprint == fingerprint:
                return False, event, False
            if not event.is_set():
                return False, event, False
            _chat_idempotency_records.pop(key, None)
        event = threading.Event()
        _chat_idempotency_records[key] = {
            "created_at": now,
            "event": event,
            "fingerprint": fingerprint,
            "response": None,
            "error": None,
            "status": None,
            "headers": None,
        }
        return True, event, True


def complete_chat_idempotency_key(
    key: str,
    *,
    response: dict[str, Any] | None = None,
    error: Any = None,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> None:
    with _chat_idempotency_lock:
        record = _chat_idempotency_records.get(key)
        if not isinstance(record, dict):
            return
        record["created_at"] = time.monotonic()
        record["response"] = dict(response) if isinstance(response, dict) else None
        record["error"] = error
        record["status"] = int(status_code or 500)
        record["headers"] = dict(headers) if isinstance(headers, dict) else None
        event = record.get("event")
        if isinstance(event, threading.Event):
            event.set()


def clear_chat_idempotency_key(key: str) -> None:
    with _chat_idempotency_lock:
        _chat_idempotency_records.pop(key, None)


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


def normalize_brief_text(text: Any) -> str:
    raw = str(text or "").strip().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9']+", " ", raw)).strip()


def looks_like_brief_affirmation(text: Any) -> bool:
    compact = normalize_brief_text(text)
    if not compact:
        return False
    if compact in _MORNING_BRIEF_AFFIRMATIONS:
        return True
    return any(compact.startswith(f"{phrase} ") for phrase in _MORNING_BRIEF_AFFIRMATIONS)


def history_offered_morning_brief(history: Any) -> bool:
    if not isinstance(history, list):
        return False
    for item in reversed(history[-6:]):
        if not isinstance(item, dict):
            continue
        if str(item.get("role", "")).strip().lower() != "assistant":
            continue
        content = normalize_brief_text(item.get("content", ""))
        if "morning brief" not in content:
            continue
        if any(
            phrase in content
            for phrase in ("shall i", "i can", "prepare", "proceed", "give you")
        ):
            return True
    return False


def request_is_morning_brief(request: Any) -> bool:
    message = normalize_brief_text(request.message)
    if any(phrase in message for phrase in _MORNING_BRIEF_DIRECT_PHRASES):
        return True
    return looks_like_brief_affirmation(message) and history_offered_morning_brief(
        request.history
    )


def latest_daily_report_path(owner: Any) -> Path | None:
    reports_dir = owner._path_config.runtime_dir / "daily_reports"
    if not reports_dir.exists():
        return None
    today_name = f"{datetime.now().strftime('%Y-%m-%d')}.md"
    today_path = reports_dir / today_name
    if today_path.exists():
        return today_path
    reports = sorted(reports_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return reports[0] if reports else None


def strip_markdown_prefix(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^\s*(?:[-*]|\d+\.)\s*", "", cleaned)
    cleaned = cleaned.replace("**", "").replace("`", "")
    return cleaned.strip()


def parse_markdown_sections(markdown_text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = ""
    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("## "):
            current = line[3:].strip().lower()
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(line)
    return sections


def preview_markdown_section(lines: list[str], limit: int = 3) -> list[str]:
    preview: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("|"):
            if line.startswith("|-"):
                continue
            cols = [part.strip() for part in line.strip("|").split("|")]
            if len(cols) >= 2 and cols[0].lower() != "topic":
                preview.append(strip_markdown_prefix(f"{cols[0]}: {cols[1]}"))
            continue
        preview.append(strip_markdown_prefix(line))
        if len(preview) >= limit:
            break
    return preview[:limit]


def preview_plain_block(text: str, limit: int = 3) -> list[str]:
    lines = [
        strip_markdown_prefix(line)
        for line in str(text or "").splitlines()
        if str(line).strip()
    ]
    return [line for line in lines if line][:limit]


def build_morning_brief_response(owner: Any) -> str:
    now_local = datetime.now().astimezone()
    lines = [f"Morning brief for {now_local.strftime('%A, %B %d, %Y')}."]

    report_path = latest_daily_report_path(owner)
    report_sections: dict[str, list[str]] = {}
    if report_path is not None:
        try:
            report_sections = parse_markdown_sections(
                report_path.read_text(encoding="utf-8", errors="ignore")
            )
        except Exception:
            report_sections = {}

    key_actions = preview_markdown_section(report_sections.get("key actions", []), limit=3)
    carry_forward = preview_markdown_section(
        report_sections.get("carry-forward items", []), limit=3
    )
    world_news = preview_markdown_section(report_sections.get("world news", []), limit=3)

    if key_actions:
        lines.append("")
        lines.append("Top priorities:")
        lines.extend(f"- {item}" for item in key_actions)

    pending_tasks = ""
    if owner.GUPPY_MEMORY_AVAILABLE and hasattr(owner.memory, "get_tasks"):
        try:
            pending_tasks = str(owner.memory.get_tasks("pending") or "").strip()
        except Exception:
            pending_tasks = ""
    task_preview = []
    if pending_tasks and not pending_tasks.lower().startswith("no pending tasks"):
        task_preview = preview_plain_block(pending_tasks, limit=3)
    if task_preview:
        lines.append("")
        lines.append("Pending tasks:")
        lines.extend(f"- {item}" for item in task_preview)

    if world_news:
        lines.append("")
        lines.append("World watch:")
        lines.extend(f"- {item}" for item in world_news)

    if carry_forward:
        lines.append("")
        lines.append("Carry-forward:")
        lines.extend(f"- {item}" for item in carry_forward)

    resource = owner._read_resource_envelope_status()
    startup = owner._startup_readiness_cached_or_unknown()
    resource_state = str(resource.get("state", "unknown")).strip().lower() or "unknown"
    resource_message = str(resource.get("message", "resource envelope status unavailable")).strip()
    startup_state = str(startup.get("overall", "UNKNOWN")).strip().lower() or "unknown"
    lines.append("")
    lines.append(
        f"System status: resource envelope {resource_state}; startup readiness {startup_state}."
    )
    if resource_message:
        lines.append(f"Runtime note: {resource_message.rstrip('.')}.")

    if report_path is not None:
        report_label = (
            "today's report"
            if report_path.name == f"{now_local.strftime('%Y-%m-%d')}.md"
            else "latest report"
        )
        lines.append(
            f"Full details are in {report_label}: runtime/daily_reports/{report_path.name}."
        )
    elif len(lines) == 3:
        lines.append(
            "No saved daily report is available yet, so this brief is using live runtime context only."
        )

    return "\n".join(lines)


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
