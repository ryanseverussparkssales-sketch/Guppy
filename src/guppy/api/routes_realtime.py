from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from src.guppy.api._server_fragment_models import ChatRequest
from src.guppy.api.server_context import ServerContext
from src.guppy.api.realtime_inference_support import (
    stream_unified_inference,
    _REPLACE_SENTINEL,
    _SOURCE_SENTINEL,
    _repair_tool_json,
    _bg_store_tool_outcome,
)
from src.guppy.voice import voice as _voice

# ── Companion tool-call parser ─────────────────────────────────────────────────
# JSON format: <tool_call>{"name": "...", "arguments": {...}}</tool_call>
_TOOL_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)

# XML format: <tool_call><name>...</name><arguments>JSON</arguments></tool_call>
# Some Hermes4 generations use this format instead of JSON-in-tags.
_TOOL_CALL_XML_RE = re.compile(
    r"<tool_call>\s*<name>(.*?)</name>\s*<arguments>\s*(.*?)\s*</arguments>\s*</tool_call>",
    re.DOTALL,
)


def _normalize_tool_calls(text: str) -> str:
    """Convert XML-style tool calls to JSON-style so _TOOL_CALL_RE can parse them."""
    def _to_json(m: re.Match) -> str:
        name = m.group(1).strip()
        args_raw = m.group(2).strip()
        try:
            args = json.loads(args_raw)
        except Exception:
            args = {}
        return f'<tool_call>{{"name": "{name}", "arguments": {json.dumps(args)}}}</tool_call>'
    return _TOOL_CALL_XML_RE.sub(_to_json, text)


async def _think_filter(source):
    """Strip <think>...</think> reasoning blocks from a token SSE stream.

    Hermes 4.3 36B has a hybrid thinking mode that leaks <think> blocks
    even when the system prompt says not to. This filter removes them from
    every token event before they reach the client, handling cases where
    the opening/closing tags are split across multiple streaming tokens.
    Non-token events (replace, error, done, tool_exec, heartbeats) pass through unchanged.
    """
    _buf = ""
    _in_think = False
    _OPEN = "<think>"
    _CLOSE = "</think>"
    _SAFE = len(_OPEN) - 1  # chars to keep buffered to avoid missing a split tag

    async for event in source:
        if not event.startswith("data: "):
            yield event
            continue
        raw = event[5:].strip()
        if not raw or raw == "[DONE]":
            # Flush buffered content before forwarding the done signal.
            # Without this, the last ≤6 chars in _buf would be emitted AFTER [DONE],
            # which SSE clients break on — causing truncated responses like "was A" for "was AURORA".
            if _buf and not _in_think:
                yield f"data: {json.dumps({'token': _buf})}\n\n"
                _buf = ""
            yield event
            continue
        try:
            obj = json.loads(raw)
        except Exception:
            yield event
            continue

        tok = obj.get("token")
        if tok is None:
            # replace, error, done, tool_exec — pass through unchanged
            yield event
            continue

        _buf += tok
        out = ""

        while _buf:
            if _in_think:
                end = _buf.find(_CLOSE)
                if end == -1:
                    keep = min(len(_buf), len(_CLOSE) - 1)
                    _buf = _buf[-keep:] if keep else ""
                    break
                _buf = _buf[end + len(_CLOSE):]
                _in_think = False
            else:
                start = _buf.find(_OPEN)
                if start == -1:
                    safe_end = max(0, len(_buf) - _SAFE)
                    out += _buf[:safe_end]
                    _buf = _buf[safe_end:]
                    break
                out += _buf[:start]
                _buf = _buf[start + len(_OPEN):]
                _in_think = True

        if out:
            yield f"data: {json.dumps({**obj, 'token': out})}\n\n"

    # Flush remaining buffer (only if not inside an unclosed think block)
    if _buf and not _in_think:
        yield f"data: {json.dumps({'token': _buf})}\n\n"


async def _execute_companion_tool(name: str, args: dict) -> dict:
    """Execute one companion tool call. Returns a result dict."""
    import httpx

    if name == "web_fetch":
        url     = str(args.get("url", "")).strip()
        extract = str(args.get("extract", "")).strip().lower()
        if not url:
            return {"ok": False, "error": "url required"}
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 Guppy/1.0"})
                text = resp.text
            if "<html" in text.lower()[:500]:
                text = re.sub(r"<[^>]+>", " ", text)
                text = re.sub(r"[ \t]{3,}", " ", text)
                text = re.sub(r"\n{4,}", "\n\n", text)
            text = text[:20000]
            if extract:
                idx = text.lower().find(extract)
                if idx >= 0:
                    text = text[max(0, idx - 100): idx + 6000]
            return {"ok": True, "text": text[:8000], "url": url}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if name == "create_reminder":
        from src.guppy.api.routes_reminders import create_reminder
        message       = str(args.get("message", "")).strip()
        delay_minutes = args.get("delay_minutes")
        due_iso       = args.get("due_iso")
        if not message:
            return {"ok": False, "error": "message required"}
        if delay_minutes is None and due_iso is None:
            delay_minutes = 30
        try:
            return {"ok": True, **create_reminder(message, due_iso=due_iso, delay_minutes=delay_minutes)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if name == "download_media":
        url      = str(args.get("url", "")).strip()
        category = str(args.get("category", "general")).strip()
        if not url:
            return {"ok": False, "error": "url required"}

        policy = os.environ.get("LIBRARY_ACQUISITION_POLICY", "user_approved").strip().lower()
        if policy == "open_content_only":
            return {
                "ok": False,
                "error": "download_media disabled by LIBRARY_ACQUISITION_POLICY=open_content_only",
            }

        try:
            # Call qBittorrent Web API directly (bypasses Guppy auth)
            qb_base = os.environ.get("QBITTORRENT_URL", "http://localhost:8080").rstrip("/")
            payload: dict = {"urls": url}
            if category:
                payload["category"] = category
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(f"{qb_base}/api/v2/torrents/add", data=payload)
            return {"ok": resp.status_code < 300, "status": resp.status_code, "url": url}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if name == "memory_write":
        from src.guppy.memory.semantic import remember_semantic
        key      = str(args.get("key", "note")).strip()
        value    = str(args.get("value", "")).strip()
        category = str(args.get("category", "general")).strip()
        if not value:
            return {"ok": False, "error": "value required"}
        try:
            return {"ok": True, "stored": remember_semantic(key, value, category)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if name == "memory_recall":
        from src.guppy.memory.semantic import recall_semantic
        query = str(args.get("query", "")).strip()
        if not query:
            return {"ok": False, "error": "query required"}
        try:
            return {"ok": True, "recalled": recall_semantic(query)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if name == "workspace_task":
        title       = str(args.get("title", "Task")).strip()
        description = str(args.get("description", "")).strip()
        if not title:
            return {"ok": False, "error": "title required"}
        try:
            from src.guppy.api.routes_surface import _spawn_task_direct
            task = _spawn_task_direct(title=title, description=description, source="companion")
            return {"ok": True, "task_id": task["id"], "surface": "workspace"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # MCP tool dispatch — mcp__<server_id>__<tool_name>
    if name.startswith("mcp__"):
        try:
            from src.guppy.mcp.manager import get_mcp_manager
            result_text = await get_mcp_manager().call_tool_by_guppy_id(name, args)
            return {"ok": True, "result": result_text}
        except Exception as e:
            return {"ok": False, "error": f"MCP tool error: {e}"}

    return {"ok": False, "error": f"Unknown tool: {name}"}


# ── Workspace tool executor ────────────────────────────────────────────────────
# Workspace has the full tool policy: web, filesystem, shell (read-only),
# CRM, memory, reminders, media, and task spawning.

_WORKSPACE_TOOL_SCHEMA = """
## Tools — Workspace Agent (Hermes 4)
You are an autonomous workspace agent. Use <tool_call> blocks to invoke tools.
Chain multiple calls to complete tasks. Use tools when they would help — don't just describe.

WHEN TO USE TOOLS (must satisfy at least one):
- User asks to fetch, search, read, list, run, or download something external
- User says "remember" or "store" something (memory_write)
- User asks about a CRM contact or screenpipe event

DO NOT use tools for:
- Conversational questions ("what model are you", "what surface is this")
- Simple math or factual questions answerable from training
- Questions whose answer is visible in the conversation history above
- Greetings, acknowledgements, or clarifying questions

web_fetch(url, extract="")   — fetch any URL as plain text
  <tool_call>{"name": "web_fetch", "arguments": {"url": "https://www.gutenberg.org/files/1533/1533-0.txt", "extract": "witches"}}</tool_call>

web_search(query, num_results=5)   — search the web via DuckDuckGo
  <tool_call>{"name": "web_search", "arguments": {"query": "Project Gutenberg Macbeth plain text", "num_results": 5}}</tool_call>

file_read(path)   — read a local file
  <tool_call>{"name": "file_read", "arguments": {"path": "C:/Users/Ryan/Documents/notes.txt"}}</tool_call>

file_list(path=".")   — list files in a directory
  <tool_call>{"name": "file_list", "arguments": {"path": "C:/Users/Ryan/Downloads"}}</tool_call>

shell_run(command)   — read-only shell commands: dir, ls, git status/log/diff, python, type, cat
  <tool_call>{"name": "shell_run", "arguments": {"command": "dir C:/Users/Ryan/Downloads"}}</tool_call>

contacts_search(query)   — search CRM contacts by name/company/email
  <tool_call>{"name": "contacts_search", "arguments": {"query": "Smith"}}</tool_call>

screenpipe_search(query, limit=5)   — search recent screen/audio context via Screenpipe
    <tool_call>{"name": "screenpipe_search", "arguments": {"query": "invoice draft", "limit": 5}}</tool_call>

memory_write(key, value, category="general")   — store a fact permanently
  <tool_call>{"name": "memory_write", "arguments": {"key": "macbeth_location", "value": "Saved to C:/Users/Ryan/Downloads/macbeth.txt", "category": "completed"}}</tool_call>

memory_recall(query)   — recall facts from persistent memory
  <tool_call>{"name": "memory_recall", "arguments": {"query": "where is Macbeth saved"}}</tool_call>

create_reminder(message, delay_minutes=30)   — schedule a reminder for Ryan
  <tool_call>{"name": "create_reminder", "arguments": {"message": "Read the Macbeth witches scene", "delay_minutes": 60}}</tool_call>

download_media(url, category="general")   — queue a download in qBittorrent
  <tool_call>{"name": "download_media", "arguments": {"url": "magnet:?xt=urn:btih:...", "category": "books"}}</tool_call>
"""

_SHELL_SAFE_PREFIXES = (
    "dir", "ls", "echo", "git status", "git log", "git diff", "git branch",
    "python --version", "python -c", "python -m", "type ", "cat ", "head ",
    "tail ", "where ", "which ", "pip list", "pip show",
)


async def _execute_workspace_tool(name: str, args: dict) -> dict:
    """Execute one workspace tool call. Delegates shared tools to companion executor."""
    import httpx

    # Shared tools — delegate to companion executor
    if name in (
        "web_fetch", "create_reminder", "download_media",
        "memory_write", "memory_recall", "workspace_task",
    ):
        return await _execute_companion_tool(name, args)

    if name == "web_search":
        query = str(args.get("query", "")).strip()
        num_results = min(int(args.get("num_results", 5)), 10)
        if not query:
            return {"ok": False, "error": "query required"}
        try:
            async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": "Mozilla/5.0 Guppy/1.0"},
                )
            # Extract result snippets from DDG HTML response
            anchors = re.findall(
                r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a',
                resp.text, re.DOTALL,
            )
            results = [
                {"url": u, "title": re.sub(r"<[^>]+>", "", t).strip()}
                for u, t in anchors[:num_results]
            ]
            return {"ok": True, "results": results, "query": query}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if name == "file_read":
        from pathlib import Path
        path = str(args.get("path", "")).strip()
        if not path:
            return {"ok": False, "error": "path required"}
        try:
            content = Path(path).read_text(encoding="utf-8", errors="replace")
            return {"ok": True, "path": path, "content": content[:20000]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if name == "file_list":
        from pathlib import Path
        path = str(args.get("path", ".")).strip() or "."
        try:
            p = Path(path)
            entries = [
                {
                    "name": x.name,
                    "type": "dir" if x.is_dir() else "file",
                    "size": x.stat().st_size if x.is_file() else 0,
                }
                for x in sorted(p.iterdir())
            ]
            return {"ok": True, "path": str(p.resolve()), "entries": entries[:200]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if name == "shell_run":
        import subprocess, shlex
        command = str(args.get("command", "")).strip()
        if not command:
            return {"ok": False, "error": "command required"}
        cmd_lower = command.lower()
        if not any(cmd_lower.startswith(p.lower()) for p in _SHELL_SAFE_PREFIXES):
            return {
                "ok": False,
                "error": f"Not in safe-command whitelist (read-only only): {command[:80]}",
            }
        try:
            cmd_parts = shlex.split(command, posix=False)
            result = subprocess.run(
                cmd_parts, shell=False, capture_output=True, text=True, timeout=15,
            )
            return {
                "ok": True,
                "stdout": result.stdout[:8000],
                "stderr": result.stderr[:2000],
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "command timed out (15 s)"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if name == "contacts_search":
        query = str(args.get("query", "")).strip()
        try:
            from src.guppy.api.routes_workspace_data import _contacts_json
            contacts = _contacts_json(search=query)
            return {"ok": True, "contacts": contacts[:20]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if name == "screenpipe_search":
        query = str(args.get("query", "")).strip()
        limit = min(max(int(args.get("limit", 5)), 1), 20)
        if not query:
            return {"ok": False, "error": "query required"}
        try:
            from src.guppy.api.routes_screenpipe import _search

            results = await asyncio.to_thread(
                _search,
                query,
                limit,
                "all",
                None,
                None,
                None,
            )
            formatted = [
                {
                    "timestamp": r.get("timestamp", ""),
                    "app": r.get("app_name", "Unknown"),
                    "content": (r.get("content", "") or "")[:240],
                    "type": r.get("type", "unknown"),
                }
                for r in results[:limit]
            ]
            return {
                "ok": True,
                "query": query,
                "count": len(formatted),
                "results": formatted,
            }
        except Exception as e:
            return {"ok": False, "error": f"screenpipe_search failed: {e}"}

    # MCP tool dispatch — mcp__<server_id>__<tool_name>
    if name.startswith("mcp__"):
        try:
            from src.guppy.mcp.manager import get_mcp_manager
            result_text = await get_mcp_manager().call_tool_by_guppy_id(name, args)
            return {"ok": True, "result": result_text}
        except Exception as e:
            return {"ok": False, "error": f"MCP tool error: {e}"}

    return {"ok": False, "error": f"Unknown workspace tool: {name}"}


async def _generate_conversation_title(user_message: str, conv_id: str) -> None:
    """Fire-and-forget: generate a short title for a new conversation.

    Uses the dispatch llamacpp server (Qwen2.5-3B-Instruct) via OpenAI-compatible API.
    Updates the DB on success, silently no-ops on any failure.
    """
    import httpx
    from src.guppy.api.routes_chat_history import _chat_history_db

    snippet = user_message.strip()[:120]
    payload = {
        "model": "qwen2.5-3b-instruct",
        "messages": [
            {
                "role": "user",
                "content": (
                    f"Write a chat title of 5 words or fewer for this message. "
                    f"Reply with ONLY the title, no punctuation, no quotes:\n{snippet}"
                ),
            }
        ],
        "stream": False,
        "temperature": 0.3,
        "max_tokens": 16,
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post("http://localhost:8085/v1/chat/completions", json=payload)
            resp.raise_for_status()
            title = resp.json()["choices"][0]["message"]["content"].strip()
            title = title.strip('"\'').strip()
            if title:
                await asyncio.to_thread(_chat_history_db.update_conversation_title, conv_id, title)
    except Exception:
        pass  # title gen is best-effort — never surface errors to the user


def _get_active_local_model() -> Optional[str]:
    """Read the user-selected local model from the settings DB."""
    try:
        from src.guppy.api.routes_settings import _settings_db
        val = _settings_db.get_setting("local_active_model")
        return val.strip() if val and val.strip() else None
    except Exception:
        return None


def _get_active_cloud_model(provider: str = "") -> Optional[str]:
    """Read the user-selected cloud model for the active provider from the settings DB.

    When *provider* is empty, the function reads the active provider from settings
    first.  This ensures that when the user has selected Mistral, Cohere, etc. as
    their active provider, the correct model ID is returned for routing.
    """
    try:
        from src.guppy.api.routes_settings import _settings_db
        resolved = provider or _settings_db.get_active_provider() or "anthropic"
        val = _settings_db.get_setting(f"{resolved}_active_model")
        return val.strip() if val and val.strip() else None
    except Exception:
        return None


# ── Surface-aware model selection ──────────────────────────────────────────────
# Each surface has a dedicated always-on local model and a preferred cloud fallback.
# Single primary model: Hermes 4.3 36B Heretic (port 8086) handles all surfaces.
# Replaces Rocinante (companion) + Hermes 4 14B (workspace) with one 36B model.
# Cloud fallbacks remain surface-appropriate: Haiku for companion, Sonnet for workspace/codespace.

_SURFACE_LOCAL_DEFAULTS: dict[str, str] = {
    "companion": "llamacpp-hermes4",
    "workspace": "llamacpp-hermes4",
    "codespace": "llamacpp-hermes4",
}

_SURFACE_CLOUD_DEFAULTS: dict[str, str] = {
    "companion": "claude-haiku-4-5-20251001",
    "workspace": "claude-sonnet-4-6",
    "codespace": "claude-sonnet-4-6",
}


def _get_surface_local_model(surface: Optional[str]) -> Optional[str]:
    """Return the local model configured for *surface*, with hardcoded per-surface defaults.

    Priority: surface_config DB value → per-surface hardcoded default → global setting.
    The DB value is written by BackendSelector when the user picks a model for a surface.
    """
    default = _SURFACE_LOCAL_DEFAULTS.get(surface or "")
    if not surface:
        return _get_active_local_model() or default
    try:
        import sqlite3
        from src.guppy.paths import MAIN_DB_PATH
        db_path = str(MAIN_DB_PATH)
        conn = sqlite3.connect(db_path, check_same_thread=False, timeout=3)
        row = conn.execute(
            "SELECT model FROM surface_config WHERE surface = ?", (surface,)
        ).fetchone()
        conn.close()
        if row:
            model = str(row[0] or "").strip()
            if model and model not in ("auto", ""):
                return model
    except Exception:
        pass
    return default


def _get_surface_cloud_model(surface: Optional[str]) -> Optional[str]:
    """Return the cloud fallback model for *surface*.

    User's explicit provider selection wins if set; otherwise use the surface default.
    companion → claude-haiku-4-5-20251001 (fast, cheap)
    workspace/codespace → claude-sonnet-4-6 (capable)
    """
    user_model = _get_active_cloud_model()
    return user_model or _SURFACE_CLOUD_DEFAULTS.get(surface or "", "claude-sonnet-4-6")


def build_realtime_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter()
    owner = ctx.owner

    def _strip_think_from_text(text: str) -> str:
        """Remove <think>...</think> blocks from a completed assistant response."""
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    def _persist_chat_memory(
        *,
        session_id: str | None,
        user_text: str,
        assistant_text: str,
        persona_id: str = "",
        workspace_name: str = "",
    ) -> None:
        if not session_id or not owner.GUPPY_MEMORY_AVAILABLE:
            return
        assistant_text = _strip_think_from_text(assistant_text)
        try:
            owner.memory.save_message(
                session_id,
                "user",
                user_text,
                workspace_name=workspace_name,
            )
            owner.memory.save_message(
                session_id,
                "assistant",
                assistant_text,
                workspace_name=workspace_name,
            )
            if hasattr(owner.memory, "promote_durable_chat_memory"):
                owner.memory.promote_durable_chat_memory(
                    user_text,
                    assistant_text,
                    session_id=session_id,
                    persona_id=persona_id,
                )
        except Exception as exc:
            owner.logger.error(
                "chat memory persistence failed session_id=%r persona_id=%r error=%s",
                session_id,
                persona_id,
                exc,
            )

    @router.post("/chat")
    async def chat(request: ChatRequest, _user_id: str = Depends(ctx.require_rate_limit)):

        if not owner.GUPPY_CORE_AVAILABLE:
            raise HTTPException(status_code=503, detail="Guppy core not available")

        idempotency_key = str(request.idempotency_key or "").strip()
        request_fingerprint = ctx.build_chat_request_fingerprint(request) if idempotency_key else ""
        idempotency_owner = False
        if idempotency_key:
            while True:
                idempotency_owner, idempotency_event = ctx.register_chat_idempotency_key(
                    idempotency_key, request_fingerprint
                )
                if idempotency_owner:
                    break
                await ctx.run_blocking(
                    idempotency_event.wait,
                    timeout_seconds=max(owner.CHAT_TIMEOUT_SECONDS, 120.0),
                )
                idempotent_result = ctx.resolve_chat_idempotency_key(
                    idempotency_key, request_fingerprint
                )
                if isinstance(idempotent_result, dict):
                    response_payload = idempotent_result.get("response")
                    if isinstance(response_payload, dict):
                        return response_payload
                    if "error" in idempotent_result:
                        raise HTTPException(
                            status_code=int(idempotent_result.get("status", 500) or 500),
                            detail=idempotent_result.get("error"),
                            headers=idempotent_result.get("headers")
                            if isinstance(idempotent_result.get("headers"), dict)
                            else None,
                        )
                (
                    idempotency_owner,
                    idempotency_event,
                    took_ownership,
                ) = ctx.takeover_chat_idempotency_key(idempotency_key, request_fingerprint)
                if idempotency_owner and took_ownership:
                    break

        try:
            (
                active_instance_name,
                active_instance_type,
                active_instance_persona,
                _active_instance_voice,
            ) = ctx.get_active_instance_context()
            if ctx.request_is_morning_brief(request):
                response = ctx.build_morning_brief_response()
                owner.log_session_event(
                    "api",
                    "morning_brief_served",
                    level="info",
                    session_id=request.session_id or "",
                    instance_name=active_instance_name,
                    used_saved_report=bool(ctx.latest_daily_report_path()),
                )
                if request.session_id and owner.GUPPY_MEMORY_AVAILABLE:
                    for role, content in (("user", request.message), ("assistant", response)):
                        try:
                            owner.memory.save_message(
                                request.session_id,
                                role,
                                content,
                                workspace_name=str(active_instance_name or "").strip(),
                            )
                        except Exception as exc:
                            owner.logger.error(
                                "morning brief memory.save_message failed session_id=%r role=%s error=%s",
                                request.session_id,
                                role,
                                exc,
                            )
                payload = {"response": response, "session_id": request.session_id, "brief": True}
                if idempotency_owner and idempotency_key:
                    ctx.complete_chat_idempotency_key(
                        idempotency_key, response=payload, status_code=200
                    )
                return payload

            system_prompt = ctx.build_chat_system_prompt(
                session_id=request.session_id,
                message=request.message,
                mode=request.mode,
                persona=request.persona or active_instance_persona,
                model_id=request.mode,
                history=request.history,
                surface=request.surface,
            )

            cache_key = None
            if owner.INFERENCE_ROUTER_AVAILABLE and ctx.request_is_cacheable(request):
                try:
                    router_impl = owner.get_router()
                    task_type = router_impl._classify_task(request.message, system_prompt)
                    if task_type == "simple":
                        cache_key = owner.build_response_cache_key(
                            message=request.message,
                            system_prompt=system_prompt,
                            mode=request.mode or "auto",
                            instance_name=active_instance_name,
                            instance_type=active_instance_type,
                        )
                        cached_response = owner.get_cached_response(cache_key)
                        if cached_response:
                            payload = {
                                "response": cached_response,
                                "session_id": request.session_id,
                                "cached": True,
                            }
                            if idempotency_owner and idempotency_key:
                                ctx.complete_chat_idempotency_key(
                                    idempotency_key, response=payload, status_code=200
                                )
                            return payload
                except Exception as e:
                    owner.logger.debug("Response cache lookup skipped: %s", e)

            _active_local = _get_surface_local_model(request.surface)

            response = await ctx.run_blocking(
                ctx.call_unified_inference,
                request.message,
                system_prompt,
                request.mode,
                request.history,
                instance_name=active_instance_name,
                instance_type=active_instance_type,
                active_local_model=_active_local,
                active_cloud_model=_get_surface_cloud_model(request.surface),
                timeout_seconds=owner.CHAT_TIMEOUT_SECONDS,
            )

            if cache_key and response.strip():
                try:
                    owner.set_cached_response(cache_key, response)
                except Exception as e:
                    owner.logger.debug("Response cache store skipped: %s", e)

            _persist_chat_memory(
                session_id=request.session_id,
                user_text=request.message,
                assistant_text=response,
                persona_id=str(request.persona or active_instance_persona or "").strip(),
                workspace_name=str(active_instance_name or "").strip(),
            )

            payload = {"response": response, "session_id": request.session_id}
            if idempotency_owner and idempotency_key:
                ctx.complete_chat_idempotency_key(
                    idempotency_key, response=payload, status_code=200
                )
            return payload

        except HTTPException as exc:
            if idempotency_owner and idempotency_key:
                ctx.complete_chat_idempotency_key(
                    idempotency_key,
                    error=getattr(exc, "detail", "chat request failed"),
                    status_code=int(getattr(exc, "status_code", 500) or 500),
                    headers=getattr(exc, "headers", None),
                )
            raise
        except Exception as e:
            owner.logger.error(f"Chat request failed: {e}")
            owner.log_session_event(
                "api",
                "chat_failed",
                level="error",
                session_id=request.session_id or "",
                use_claude=bool(request.use_claude),
                error=str(e),
            )
            if idempotency_owner and idempotency_key:
                ctx.complete_chat_idempotency_key(
                    idempotency_key, error=str(e), status_code=500
                )
            user_msg = str(e)
            if "llamacpp" in user_msg.lower() or "8086" in user_msg or "connect" in user_msg.lower():
                user_msg = f"Cannot reach local inference backend (port 8086 — Hermes 4.3 36B). Ensure the backend is running and try again. ({e})"
            raise HTTPException(status_code=500, detail=user_msg)

    @router.post("/chat/stream")
    async def chat_stream(
        request: ChatRequest,
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        """
        SSE streaming chat endpoint. Yields tokens as they are produced by the
        inference backend.  Each event is ``data: {"token": "..."}\\n\\n``.
        The stream ends with ``data: [DONE]\\n\\n``.
        On error: ``data: {"error": "..."}\\n\\n``.
        """

        (
            active_instance_name,
            active_instance_type,
            active_instance_persona,
            _active_instance_voice,
        ) = ctx.get_active_instance_context()
        system_prompt = ctx.build_chat_system_prompt(
            session_id=request.session_id,
            message=request.message,
            mode=request.mode,
            persona=request.persona or active_instance_persona,
            model_id=request.mode,
            history=request.history,
            surface=request.surface,
        )

        _active_local_model = _get_surface_local_model(request.surface)
        _active_cloud_model = _get_surface_cloud_model(request.surface)

        # Voice brevity injection: TTS responses must be 1-2 sentences, no markdown.
        # Single model (Hermes 4.3 36B) handles voice — no routing change needed.
        if request.is_voice and request.surface == "companion":
            system_prompt = (
                "VOICE MODE: You are responding via text-to-speech. "
                "Reply in ONE or TWO sentences only. "
                "No bullet points, no markdown, no lists. "
                "Be direct and conversational — your response will be read aloud.\n\n"
            ) + system_prompt

        # ── Local-model check — prefer local, fall back to cloud transparently ──
        # If the companion's local model port is down, announce it in-stream and
        # route to the cloud fallback rather than hard-failing. This keeps the
        # conversation alive. The watchdog will restart the local model in <60 s.
        _local_offline_notice: str | None = None
        if request.surface == "companion" and _active_local_model:
            try:
                from src.guppy.api.routes_backends import _LLAMACPP_CONFIG, _port_alive
                from src.guppy.inference.local_client import _LLAMACPP_MODEL_ROUTE as _ROUTE_MAP
                _canonical = _ROUTE_MAP.get(_active_local_model, _active_local_model)
                _cfg_entry = _LLAMACPP_CONFIG.get(_canonical, {})
                _model_port = _cfg_entry.get("port")
                if _model_port and not _port_alive(_model_port):
                    _model_label = _cfg_entry.get("label", _active_local_model)
                    _local_offline_notice = (
                        f"[Local model offline — routing to cloud. "
                        f"{_model_label} will restart automatically.] "
                    )
                    _active_local_model = None  # force cloud path
            except Exception:
                pass

        # Inject workspace tool schema — local models need the XML <tool_call> schema;
        # cloud models (Anthropic etc.) use native tool_use and don't need it.
        _is_cloud_only = (
            not _active_local_model
            or (request.use_claude and not _active_local_model)
        )
        if request.surface == "workspace" and _WORKSPACE_TOOL_SCHEMA not in system_prompt and not _is_cloud_only:
            _tool_schema = _WORKSPACE_TOOL_SCHEMA
            # Append any enabled MCP server tools so the model knows they exist
            try:
                from src.guppy.mcp.manager import get_mcp_manager
                _mcp_tools = await get_mcp_manager().get_tools_for_llm()
                if _mcp_tools:
                    _mcp_lines = ["\n\n## MCP Tools (external servers)\nUse the same <tool_call> format.\n"]
                    for _t in _mcp_tools:
                        _params = _t.get("parameters", {})
                        _props = _params.get("properties", {})
                        _param_str = ", ".join(
                            f"{k}{'?' if k not in _params.get('required', []) else ''}"
                            for k in _props
                        ) if _props else ""
                        _mcp_lines.append(
                            f"{_t['id']}({_param_str})   — {_t.get('description', '')}\n"
                            f"  <tool_call>{{\"name\": \"{_t['id']}\", \"arguments\": {{{', '.join(f'\"{k}\": ...' for k in list(_props)[:3])}}}}}</tool_call>"
                        )
                    _tool_schema = _tool_schema + "\n".join(_mcp_lines)
            except Exception:
                pass  # MCP tools are optional; never break chat if they fail
            system_prompt = system_prompt + _tool_schema

        async def _generate():
            full_response = ""
            last_source: str = ""

            # Emit offline notice as first token so TTS picks it up immediately
            if _local_offline_notice:
                yield f"data: {json.dumps({'token': _local_offline_notice})}\n\n"
                full_response += _local_offline_notice

            # ── Workspace surface: two-pass with full tool-call execution ─────
            if request.surface == "workspace":
                first_response = ""
                _p1_tool_signal = False   # True once "Calling tools…" replace is sent
                try:
                    async for token in stream_unified_inference(
                        owner,
                        request.message,
                        system_prompt,
                        mode=request.mode,
                        history=request.history,
                        instance_name=active_instance_name,
                        instance_type=active_instance_type,
                        active_local_model=_active_local_model,
                        active_cloud_model=_active_cloud_model,
                        image_base64=request.image_base64 or None,
                        skip_tools=True,
                        surface=request.surface,
                    ):
                        if token.startswith(_SOURCE_SENTINEL):
                            continue
                        if token.startswith(_REPLACE_SENTINEL):
                            # Cache hit / atomic replace — relay to client and stop streaming
                            first_response = token[len(_REPLACE_SENTINEL):]
                            yield f"data: {json.dumps({'replace': first_response})}\n\n"
                            _p1_tool_signal = True
                            continue
                        first_response += token
                        if not _p1_tool_signal:
                            if "<tool_call>" not in first_response:
                                yield f"data: {json.dumps({'token': token})}\n\n"
                            else:
                                # Tool call starting — replace partial text with status
                                yield f"data: {json.dumps({'replace': '⚙️ Calling tools…'})}\n\n"
                                _p1_tool_signal = True
                except Exception as exc:
                    owner.logger.error("Workspace pass-1 streaming failed: %s", exc)
                    yield f"data: {json.dumps({'error': str(exc)})}\n\n"
                    return

                first_response_clean = _strip_think_from_text(first_response)
                if not first_response_clean.strip():
                    first_response_clean = "Ready — what do you need?"
                    yield f"data: {json.dumps({'token': first_response_clean})}\n\n"

                tool_blocks = _TOOL_CALL_RE.findall(_normalize_tool_calls(first_response_clean))

                if not tool_blocks:
                    full_response = first_response_clean
                    if _p1_tool_signal:
                        # A replace was sent (cache hit or false tool_call signal) —
                        # ensure the client has the correct final text.
                        yield f"data: {json.dumps({'replace': first_response_clean})}\n\n"
                    # Tokens already streamed for normal case — just signal done below.
                else:
                    tool_results: list[dict] = []
                    for tc_json in tool_blocks:
                        try:
                            tc = _repair_tool_json(tc_json)
                            if tc is None:
                                # One-shot correction: ask the model to fix its malformed JSON
                                try:
                                    import httpx as _httpx
                                    _correction_payload = {
                                        "model": "hermes-4-3-36b-heretic",
                                        "messages": [
                                            {"role": "user", "content": (
                                                f"You emitted an invalid tool call. Raw output:\n\n{tc_json}\n\n"
                                                "Rewrite it as valid JSON inside <tool_call>...</tool_call> tags. "
                                                "Output ONLY the corrected tool call, nothing else."
                                            )}
                                        ],
                                        "stream": False,
                                        "max_tokens": 256,
                                        "temperature": 0.0,
                                    }
                                    async with _httpx.AsyncClient(timeout=10.0) as _c:
                                        _cr = await _c.post("http://localhost:8086/v1/chat/completions", json=_correction_payload)
                                        _cr.raise_for_status()
                                    _corrected_text = _cr.json()["choices"][0]["message"]["content"]
                                    _corrected_blocks = _TOOL_CALL_RE.findall(_corrected_text)
                                    tc = _repair_tool_json(_corrected_blocks[0]) if _corrected_blocks else None
                                except Exception as _retry_exc:
                                    owner.logger.warning("Workspace tool-call correction failed: %s", _retry_exc)
                                    tc = None
                                if tc is None:
                                    tool_results.append({"tool": "?", "error": "malformed tool JSON"})
                                    continue
                            tool_name = tc.get("name", "")
                            if not tool_name:
                                owner.logger.warning("Workspace tool call missing name, skipping: %s", tc)
                                continue
                            tool_args = tc.get("arguments", {})
                            if not isinstance(tool_args, dict):
                                owner.logger.warning("Workspace tool_args not a dict, coercing to {}: %s", tool_args)
                                tool_args = {}
                            yield f"data: {json.dumps({'tool_exec': tool_name})}\n\n"
                            result = await _execute_workspace_tool(tool_name, tool_args)
                            tool_results.append({"tool": tool_name, "result": result})
                        except Exception as exc:
                            tool_results.append({"tool": "?", "error": str(exc)})

                    def _fmt_ws_result(r: dict) -> str:
                        if "error" in r:
                            return f"[{r['tool']}] Error: {r['error']}"
                        result = r.get("result", "")
                        if isinstance(result, dict):
                            flat = "\n".join(f"  {k}: {v}" for k, v in result.items() if k != "ok")
                            return f"[{r['tool']}]\n{flat}" if flat else f"[{r['tool']}] done"
                        text = str(result)[:6000]
                        return f"[{r['tool']}]\n{text}"

                    tool_result_text = "\n\n".join(_fmt_ws_result(r) for r in tool_results)
                    follow_up_history = list(request.history or []) + [
                        {"role": "assistant", "content": first_response_clean},
                        {
                            "role": "user",
                            "content": (
                                f"Results:\n\n{tool_result_text}\n\n"
                                "Give a clear, direct response. Continue with more tool calls if the task needs them."
                            ),
                        },
                    ]

                    # Clear the "Calling tools…" status before streaming pass 2
                    yield f"data: {json.dumps({'replace': ''})}\n\n"

                    # Strip the heavy tool schema + file tree from pass-2 system prompt.
                    # By this point the tool schema is in conversation history; re-injecting
                    # it doubles context usage and pushes the 32K context over the limit.
                    _p2_system = system_prompt.replace(_WORKSPACE_TOOL_SCHEMA, "").strip()
                    _p2_system += (
                        "\n\nYou have the tool results above. Give a clear, direct response. "
                        "State findings and conclusions without narrating what commands you ran. "
                        "Do NOT emit any <tool_call> blocks. Do NOT use <think> blocks."
                    )

                    try:
                        async for token in stream_unified_inference(
                            owner,
                            "Respond based on the tool results.",
                            _p2_system,
                            mode=request.mode,
                            history=follow_up_history,
                            instance_name=active_instance_name,
                            instance_type=active_instance_type,
                            active_local_model=_active_local_model,
                            active_cloud_model=_active_cloud_model,
                            image_base64=None,
                            skip_tools=True,
                            surface=request.surface,
                        ):
                            if token.startswith(_SOURCE_SENTINEL):
                                last_source = token[len(_SOURCE_SENTINEL):]
                                continue
                            if token.startswith(_REPLACE_SENTINEL):
                                replaced = token[len(_REPLACE_SENTINEL):]
                                full_response = replaced
                                yield f"data: {json.dumps({'replace': replaced})}\n\n"
                                continue
                            full_response += token
                            yield f"data: {json.dumps({'token': token})}\n\n"
                    except Exception as exc:
                        owner.logger.error("Workspace pass-2 streaming failed: %s", exc)
                        yield f"data: {json.dumps({'error': str(exc)})}\n\n"
                        return

                done_payload: dict = {}
                if last_source:
                    done_payload["source"] = last_source
                yield f"data: {json.dumps({**done_payload, 'done': True})}\n\n" if done_payload else "data: [DONE]\n\n"

                _persist_chat_memory(
                    session_id=request.session_id,
                    user_text=request.message,
                    assistant_text=full_response,
                    persona_id=str(request.persona or active_instance_persona or "").strip(),
                    workspace_name=str(active_instance_name or "").strip(),
                )
                if request.session_id and full_response:
                    try:
                        from src.guppy.api.routes_chat_history import _chat_history_db
                        conv = _chat_history_db.get_conversation(request.session_id)
                        if conv and conv.get("message_count", 0) <= 2 and str(conv.get("title", "")).startswith("Conversation "):
                            asyncio.ensure_future(_generate_conversation_title(request.message, request.session_id))
                    except Exception:
                        pass
                return

            # ── Companion surface: two-pass with tool-call detection ───────────
            if request.surface == "companion":
                # Pass 1: stream tokens to client while detecting <tool_call> blocks.
                # When a tool_call appears mid-stream, replace the partial display
                # with a status message and proceed to tool execution.
                # MUST use stream_unified_inference (not call_unified_inference) so
                # <tool_call> markup is preserved in the raw token stream.
                first_response = ""
                _p1_tool_signal = False
                try:
                    async for token in stream_unified_inference(
                        owner,
                        request.message,
                        system_prompt,
                        mode=request.mode,
                        history=request.history,
                        instance_name=active_instance_name,
                        instance_type=active_instance_type,
                        active_local_model=_active_local_model,
                        active_cloud_model=_active_cloud_model,
                        image_base64=request.image_base64 or None,
                        skip_tools=True,
                        surface=request.surface,
                    ):
                        if token.startswith(_SOURCE_SENTINEL):
                            continue
                        if token.startswith(_REPLACE_SENTINEL):
                            first_response = token[len(_REPLACE_SENTINEL):]
                            yield f"data: {json.dumps({'replace': first_response})}\n\n"
                            _p1_tool_signal = True
                            continue
                        first_response += token
                        if not _p1_tool_signal:
                            if "<tool_call>" not in first_response:
                                yield f"data: {json.dumps({'token': token})}\n\n"
                            else:
                                yield f"data: {json.dumps({'replace': '⚙️ Calling tools…'})}\n\n"
                                _p1_tool_signal = True
                except Exception as exc:
                    owner.logger.error("Companion pass-1 streaming failed: %s", exc)
                    yield f"data: {json.dumps({'error': str(exc)})}\n\n"
                    return

                # Strip think blocks from first_response before tool detection.
                # first_response accumulates raw tokens; _think_filter only strips
                # them from the SSE stream (what the client sees), not from this variable.
                # If the entire response was think content, the client already saw nothing —
                # we need the fallback to fire correctly here too.
                first_response_clean = _strip_think_from_text(first_response)

                # If the model generated nothing visible (all think content or empty),
                # substitute a polite fallback so the frontend never receives an empty display.
                if not first_response_clean.strip():
                    first_response_clean = "I'm here — could you rephrase that?"
                    yield f"data: {json.dumps({'token': first_response_clean})}\n\n"

                tool_blocks = _TOOL_CALL_RE.findall(_normalize_tool_calls(first_response_clean))

                if not tool_blocks:
                    full_response = first_response_clean
                    if _p1_tool_signal:
                        # Replace sent earlier (cache hit or false tool signal)
                        yield f"data: {json.dumps({'replace': first_response_clean})}\n\n"
                    # Normal case: tokens already streamed — done signal sent below
                else:
                    # Execute each tool in sequence, emitting tool_exec status events
                    tool_results: list[dict] = []
                    for tc_json in tool_blocks:
                        try:
                            tc = _repair_tool_json(tc_json)
                            if tc is None:
                                # One-shot correction: ask the model to fix its malformed JSON
                                try:
                                    import httpx as _httpx
                                    _correction_payload = {
                                        "model": "hermes-4-3-36b-heretic",
                                        "messages": [
                                            {"role": "user", "content": (
                                                f"You emitted an invalid tool call. Raw output:\n\n{tc_json}\n\n"
                                                "Rewrite it as valid JSON inside <tool_call>...</tool_call> tags. "
                                                "Output ONLY the corrected tool call, nothing else."
                                            )}
                                        ],
                                        "stream": False,
                                        "max_tokens": 256,
                                        "temperature": 0.0,
                                    }
                                    async with _httpx.AsyncClient(timeout=10.0) as _c:
                                        _cr = await _c.post("http://localhost:8086/v1/chat/completions", json=_correction_payload)
                                        _cr.raise_for_status()
                                    _corrected_text = _cr.json()["choices"][0]["message"]["content"]
                                    _corrected_blocks = _TOOL_CALL_RE.findall(_corrected_text)
                                    tc = _repair_tool_json(_corrected_blocks[0]) if _corrected_blocks else None
                                except Exception as _retry_exc:
                                    owner.logger.warning("Companion tool-call correction failed: %s", _retry_exc)
                                    tc = None
                                if tc is None:
                                    tool_results.append({"tool": "?", "error": "malformed tool JSON"})
                                    continue
                            tool_name = tc.get("name", "")
                            if not tool_name:
                                owner.logger.warning("Companion tool call missing name, skipping: %s", tc)
                                continue
                            tool_args = tc.get("arguments", {})
                            if not isinstance(tool_args, dict):
                                owner.logger.warning("Companion tool_args not a dict, coercing to {}: %s", tool_args)
                                tool_args = {}
                            yield f"data: {json.dumps({'tool_exec': tool_name})}\n\n"
                            result = await _execute_companion_tool(tool_name, tool_args)
                            tool_results.append({"tool": tool_name, "result": result})
                        except Exception as exc:
                            tool_results.append({"tool": "?", "error": str(exc)})

                    # Build tool-result injection for pass 2.
                    # Format results as readable text, not raw JSON dumps.
                    def _fmt_result(r: dict) -> str:
                        if "error" in r:
                            return f"[{r['tool']}] Error: {r['error']}"
                        result = r.get("result", "")
                        if isinstance(result, dict):
                            # Flatten simple dicts (e.g. get_time) to readable k: v lines
                            flat = "\n".join(f"  {k}: {v}" for k, v in result.items() if k != "ok")
                            return f"[{r['tool']}]\n{flat}" if flat else f"[{r['tool']}] done"
                        text = str(result)[:4000]
                        return f"[{r['tool']}]\n{text}"

                    tool_result_text = "\n\n".join(_fmt_result(r) for r in tool_results)
                    follow_up_history = list(request.history or []) + [
                        {"role": "assistant", "content": first_response_clean},
                        {
                            "role": "user",
                            "content": f"Here are the results:\n\n{tool_result_text}",
                        },
                    ]

                    # Clear the "Calling tools…" status before streaming pass 2
                    yield f"data: {json.dumps({'replace': ''})}\n\n"

                    # Pass 2: synthesize tool results into a natural reply.
                    # skip_tools=True prevents the tool primer from re-entering the prompt
                    # and stops the model from emitting another tool-call loop.
                    _p2_system = (
                        system_prompt
                        + "\n\nAnswer Ryan naturally based on the information above. "
                        "Respond as if you simply know the answer — don't say 'the tool returned' "
                        "or 'I executed get_time'. Just give Ryan the answer directly. "
                        "One to three sentences unless the task needs more. "
                        "Do NOT emit any <tool_call> blocks. Do NOT use <think> blocks."
                    )
                    try:
                        async for token in stream_unified_inference(
                            owner,
                            "Respond naturally based on the tool results.",
                            _p2_system,
                            mode=request.mode,
                            history=follow_up_history,
                            instance_name=active_instance_name,
                            instance_type=active_instance_type,
                            active_local_model=_active_local_model,
                            active_cloud_model=_active_cloud_model,
                            image_base64=None,
                            skip_tools=True,
                            surface=request.surface,
                        ):
                            if token.startswith(_SOURCE_SENTINEL):
                                last_source = token[len(_SOURCE_SENTINEL):]
                                continue
                            if token.startswith(_REPLACE_SENTINEL):
                                replaced = token[len(_REPLACE_SENTINEL):]
                                full_response = replaced
                                yield f"data: {json.dumps({'replace': replaced})}\n\n"
                                continue
                            full_response += token
                            yield f"data: {json.dumps({'token': token})}\n\n"
                    except Exception as exc:
                        owner.logger.error("Companion pass-2 streaming failed: %s", exc)
                        yield f"data: {json.dumps({'error': str(exc)})}\n\n"
                        return

                done_payload: dict = {}
                if last_source:
                    done_payload["source"] = last_source
                yield f"data: {json.dumps({**done_payload, 'done': True})}\n\n" if done_payload else "data: [DONE]\n\n"

                _persist_chat_memory(
                    session_id=request.session_id,
                    user_text=request.message,
                    assistant_text=full_response,
                    persona_id=str(request.persona or active_instance_persona or "").strip(),
                    workspace_name=str(active_instance_name or "").strip(),
                )
                if request.session_id and full_response:
                    try:
                        from src.guppy.api.routes_chat_history import _chat_history_db
                        conv = _chat_history_db.get_conversation(request.session_id)
                        if conv and conv.get("message_count", 0) <= 2 and str(conv.get("title", "")).startswith("Conversation "):
                            asyncio.ensure_future(_generate_conversation_title(request.message, request.session_id))
                    except Exception:
                        pass
                return

            # ── Standard streaming for all other surfaces ─────────────────────
            try:
                async for token in stream_unified_inference(
                    owner,
                    request.message,
                    system_prompt,
                    mode=request.mode,
                    history=request.history,
                    instance_name=active_instance_name,
                    instance_type=active_instance_type,
                    active_local_model=_active_local_model,
                    active_cloud_model=_active_cloud_model,
                    image_base64=request.image_base64 or None,
                    surface=request.surface,
                ):
                    if token.startswith(_SOURCE_SENTINEL):
                        last_source = token[len(_SOURCE_SENTINEL):]
                        continue
                    if token.startswith(_REPLACE_SENTINEL):
                        replaced = token[len(_REPLACE_SENTINEL):]
                        full_response = replaced
                        yield f"data: {json.dumps({'replace': replaced})}\n\n"
                        continue
                    full_response += token
                    yield f"data: {json.dumps({'token': token})}\n\n"

                done_payload: dict = {}
                if last_source:
                    done_payload["source"] = last_source
                yield f"data: {json.dumps({**done_payload, 'done': True})}\n\n" if done_payload else "data: [DONE]\n\n"

            except Exception as exc:
                owner.logger.error("Streaming chat error: %s", exc)
                yield f"data: {json.dumps({'error': str(exc)})}\n\n"
                return

            _persist_chat_memory(
                session_id=request.session_id,
                user_text=request.message,
                assistant_text=full_response,
                persona_id=str(request.persona or active_instance_persona or "").strip(),
                workspace_name=str(active_instance_name or "").strip(),
            )

            # Auto-title: fire-and-forget on the first assistant turn only.
            if request.session_id and full_response:
                try:
                    from src.guppy.api.routes_chat_history import _chat_history_db
                    conv = _chat_history_db.get_conversation(request.session_id)
                    if conv and conv.get("message_count", 0) <= 2 and str(conv.get("title", "")).startswith("Conversation "):
                        asyncio.ensure_future(
                            _generate_conversation_title(request.message, request.session_id)
                        )
                except Exception:
                    pass  # best-effort, never block the response

        async def _generate_with_heartbeat():
            """Wrap _generate() with SSE keepalives and an inactivity timeout.

            Uses a queue to decouple the generator from the heartbeat loop —
            asyncio.shield on __anext__() is unsafe because calling __anext__()
            while the previous shielded call is still running raises ValueError.
            The queue approach runs the generator in a background task, feeding
            chunks to the consumer; the consumer blocks on queue.get() with a
            30 s timeout and emits a heartbeat comment when the queue is empty.
            The heartbeat is a bare SSE comment (': heartbeat') which browsers
            and proxies ignore but which keeps the TCP connection alive.
            """
            import asyncio as _aio
            _stream_timeout = float(os.environ.get("GUPPY_STREAM_TIMEOUT_SECONDS", "300"))
            _heartbeat_s = 30.0
            _sentinel = object()

            q: _aio.Queue = _aio.Queue()

            async def _drain() -> None:
                try:
                    async for chunk in _think_filter(_generate()):
                        await q.put(chunk)
                except Exception as exc:
                    await q.put(exc)
                finally:
                    await q.put(_sentinel)

            drain_task = _aio.ensure_future(_drain())
            last_yield = _aio.get_event_loop().time()

            try:
                while True:
                    try:
                        item = await _aio.wait_for(q.get(), timeout=_heartbeat_s)
                    except _aio.TimeoutError:
                        if _aio.get_event_loop().time() - last_yield > _stream_timeout:
                            yield 'event: error\ndata: {"error": "Stream timeout — inference stalled"}\n\n'
                            drain_task.cancel()
                            break
                        yield ": heartbeat\n\n"
                        continue

                    if item is _sentinel:
                        break
                    if isinstance(item, BaseException):
                        yield f'event: error\ndata: {{"error": {json.dumps(str(item))}}}\n\n'
                        break
                    last_yield = _aio.get_event_loop().time()
                    yield item
            finally:
                if not drain_task.done():
                    drain_task.cancel()

        return StreamingResponse(
            _generate_with_heartbeat(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    @router.post("/chat/voice")
    async def chat_voice(
        file: UploadFile = File(...),
        session_id: Optional[str] = None,
        use_claude: Optional[bool] = True,
        _user_id: str = Depends(ctx.require_rate_limit),
    ):

        if not owner.GUPPY_CORE_AVAILABLE:
            raise HTTPException(status_code=503, detail="Guppy core not available")

        if not owner.GUPPY_VOICE_AVAILABLE:
            raise HTTPException(status_code=503, detail="Voice processing not available")

        try:
            (
                active_instance_name,
                active_instance_type,
                active_instance_persona,
                _active_instance_voice,
            ) = ctx.get_active_instance_context()
            temp_path = await ctx.save_voice_upload_tempfile(file)

            try:
                # Transcribe via Stack C facade
                audio_bytes = Path(temp_path).read_bytes()
                stt_result = await _voice.transcribe(audio_bytes)
                if stt_result.error:
                    raise HTTPException(status_code=503, detail=stt_result.error or "STT failed")
                transcription = stt_result.text

                if not transcription:
                    raise HTTPException(status_code=400, detail="Could not transcribe audio")

                system_prompt = ctx.build_chat_system_prompt(
                    session_id=session_id,
                    message=transcription,
                    persona=active_instance_persona,
                    model_id="",
                )

                response = await ctx.run_blocking(
                    ctx.call_unified_inference,
                    transcription,
                    system_prompt,
                    instance_name=active_instance_name,
                    instance_type=active_instance_type,
                    active_local_model=_get_active_local_model(),
                    active_cloud_model=_get_active_cloud_model(),
                    timeout_seconds=owner.CHAT_TIMEOUT_SECONDS,
                )

                _persist_chat_memory(
                    session_id=session_id,
                    user_text=f"[Voice] {transcription}",
                    assistant_text=response,
                    persona_id=str(active_instance_persona or "").strip(),
                    workspace_name=str(active_instance_name or "").strip(),
                )

                return {
                    "transcription": transcription,
                    "response": response,
                    "session_id": session_id,
                }
            finally:
                Path(temp_path).unlink(missing_ok=True)
        except HTTPException:
            raise
        except Exception as e:
            owner.logger.error(f"Voice chat request failed: {e}")
            owner.log_session_event(
                "api",
                "voice_chat_failed",
                level="error",
                session_id=session_id or "",
                use_claude=bool(use_claude),
                error=str(e),
            )
            raise HTTPException(status_code=500, detail=str(e))

    @router.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()

        try:
            auth_data = await websocket.receive_json()
            token = auth_data.get("token")

            if not token:
                await websocket.send_json({"error": "Authentication required"})
                await websocket.close()
                return

            try:
                payload = owner.jwt.decode(
                    token, owner.SECRET_KEY, algorithms=[owner.ALGORITHM]
                )
                _ = payload.get("sub")
            except owner.JWTError:
                await websocket.send_json({"error": "Invalid token"})
                await websocket.close()
                return

            await websocket.send_json({"status": "authenticated"})

            while True:
                try:
                    data = await websocket.receive_json()
                    message = data.get("message")
                    session_id = data.get("session_id")
                    mode = data.get("mode")
                    use_claude = data.get("use_claude", True)

                    if not message:
                        continue

                    if not owner.GUPPY_CORE_AVAILABLE:
                        await websocket.send_json({"error": "Guppy core not available"})
                        continue

                    (
                        active_instance_name,
                        active_instance_type,
                        active_instance_persona,
                        _active_instance_voice,
                    ) = ctx.get_active_instance_context()
                    system_prompt = ctx.build_chat_system_prompt(
                        session_id=session_id,
                        message=message,
                        mode=mode,
                        persona=data.get("persona") or active_instance_persona,
                        model_id=mode or "",
                    )

                    text = await ctx.run_blocking(
                        ctx.call_unified_inference,
                        message,
                        system_prompt,
                        instance_name=active_instance_name,
                        instance_type=active_instance_type,
                        active_local_model=_get_active_local_model(),
                        active_cloud_model=_get_active_cloud_model(),
                        timeout_seconds=owner.CHAT_TIMEOUT_SECONDS,
                    )
                    async for chunk in ctx.stream_chunks(text):
                        await websocket.send_json({"chunk": chunk})

                    await websocket.send_json({"done": True})
                    _persist_chat_memory(
                        session_id=session_id,
                        user_text=message,
                        assistant_text=text,
                        persona_id=str(data.get("persona") or active_instance_persona or "").strip(),
                        workspace_name=str(active_instance_name or "").strip(),
                    )

                except WebSocketDisconnect:
                    break
                except Exception as e:
                    owner.logger.error(f"WebSocket error: {e}")
                    owner.log_session_event("api", "ws_error", level="error", error=str(e))
                    await websocket.send_json({"error": str(e)})
        except Exception as e:
            owner.logger.error(f"WebSocket connection failed: {e}")
            owner.log_session_event(
                "api", "ws_connection_failed", level="error", error=str(e)
            )

    return router
