"""Conversations Surface — dedicated chat with persistent sessions.

Routes:
  POST /api/conversations/chat          — non-streaming
  POST /api/conversations/chat/stream   — SSE streaming (primary)
  GET  /api/conversations/sessions      — list sessions
  POST /api/conversations/sessions      — create session
  GET  /api/conversations/sessions/{id}/messages
  DELETE /api/conversations/sessions/{id}
  GET  /api/conversations/search?q=...  — full-text search across messages

Conversations always use the active conversation partner model (operator-selectable).
Tool envelope: web_fetch, create_reminder, download_media, memory_write, memory_recall, workspace_task only.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.guppy.api.realtime_inference_support import (
    _REPLACE_SENTINEL,
    _SOURCE_SENTINEL,
    _repair_tool_json,
    sanitize_chat_history,
    stream_unified_inference,
)
from src.guppy.api.server_context import ServerContext
from src.guppy.model_roles import get_active_conversation_partner
from src.guppy.paths import MAIN_DB_PATH, ensure_user_data_dir

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# DB helpers
# ──────────────────────────────────────────────────────────────────────────────

_DB_PATH: str = ""

_CONVERSATIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversation_sessions (
    id                TEXT PRIMARY KEY,
    session_title     TEXT,
    model_backend     TEXT,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversation_session_messages (
    id                TEXT PRIMARY KEY,
    conversation_id   TEXT NOT NULL,
    role              TEXT NOT NULL,
    content           TEXT NOT NULL,
    image_url         TEXT,
    created_at        TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversation_sessions(id) ON DELETE CASCADE
);
"""


def _db() -> sqlite3.Connection:
    ensure_user_data_dir()
    path = _DB_PATH or str(MAIN_DB_PATH)
    conn = sqlite3.connect(path, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_schema() -> None:
    with _db() as conn:
        conn.executescript(_CONVERSATIONS_SCHEMA)
        conn.commit()


_CONVERSATION_SYSTEM_PROMPT_BASE = """
You are Guppy in the dedicated Conversations surface: warm, direct, and useful.
Answer naturally and keep continuity with the provided session history.

RESPONSE LENGTH: Match complexity to the question. 1–2 sentences for simple or conversational messages. More detail only when the request is clearly technical or multi-part. No bullet lists for casual replies.

If a tool is truly needed, emit a raw tool block in this exact form:
<tool_call>{"name":"tool_name","arguments":{}}</tool_call>

AVAILABLE TOOLS — use them proactively when the request clearly calls for them:
• web_fetch(url, extract?)        — fetch live content from any URL
  USE WHEN: user asks to look something up, get live data, or check a site
• create_reminder(message, delay_minutes?) — schedule a reminder for Ryan
  USE WHEN: user says "remind me", "don't forget", or gives a time-based task
• memory_write(key, value)        — save a fact to long-term memory
  USE WHEN: user shares a preference, decision, or fact worth keeping
• memory_recall(query)            — retrieve stored facts from long-term memory
  USE WHEN: user references something that may have been discussed before
• workspace_task(task, description?) — hand off a multi-step task to Workspace
  USE WHEN: the request requires browsing, file work, or a multi-tool workflow
Do not call any other tool.
""".strip()


def _build_conversation_system_prompt(history: list[dict]) -> str:
    """Build the system prompt, injecting startup context on the first exchange."""
    base = _CONVERSATION_SYSTEM_PROMPT_BASE
    # Inject Ryan's persistent context (facts, tasks, session summaries) on
    # the first two turns of a new session so the model starts warm, not cold.
    if len(history) <= 2:
        try:
            from src.guppy.memory.memory import get_startup_context
            ctx = get_startup_context()
            if ctx and len(ctx.strip()) > 20:
                base = f"{base}\n\n{ctx.strip()}"
        except Exception:
            pass
    return base


async def _stream_conversation_inference(
    ctx: ServerContext,
    *,
    message: str,
    backend: str,
    history: list[dict],
    image_base64: str | None = None,
) -> AsyncGenerator[str, None]:
    """Adapt the conversations route shape to the shared realtime stream helper.

    Uses the active conversation-partner model (Rocinante by default) in local
    mode with tools disabled — the Conversations surface is pure dialogue.
    """
    active_partner = get_active_conversation_partner() or backend or None
    async for token in stream_unified_inference(
        ctx.owner,
        message,
        _build_conversation_system_prompt(history),
        mode="local" if active_partner else "auto",
        history=history,
        image_base64=image_base64 or None,
        active_local_model=active_partner,
        skip_tools=True,
        surface="conversations",
    ):
        if token.startswith(_SOURCE_SENTINEL):
            continue
        if token.startswith(_REPLACE_SENTINEL):
            yield token[len(_REPLACE_SENTINEL):]
            continue
        yield token


# ──────────────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ──────────────────────────────────────────────────────────────────────────────


class Message(BaseModel):
    role: str  # user | assistant
    content: str
    image_url: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    image_base64: Optional[str] = None


class SessionResponse(BaseModel):
    id: str
    session_title: str
    model_backend: str
    created_at: str
    updated_at: str
    message_count: int


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


# ──────────────────────────────────────────────────────────────────────────────
# Tool execution — conversation whitelist only
# ──────────────────────────────────────────────────────────────────────────────

async def _execute_conversation_tool(ctx: ServerContext, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Execute one conversation tool call. Returns a result dict.

    Whitelist: web_fetch, create_reminder, download_media, memory_write,
    memory_recall, workspace_task.
    """
    import httpx

    if name == "web_fetch":
        from src.guppy.api.web_fetch_safe import safe_web_fetch
        url = str(args.get("url", "")).strip()
        extract = str(args.get("extract", "")).strip().lower()
        return await safe_web_fetch(url, extract=extract)

    elif name == "create_reminder":
        text = str(args.get("text", "")).strip()
        due = str(args.get("due", "")).strip()
        if not text:
            return {"ok": False, "error": "text required"}
        try:
            from src.guppy.api.routes_reminders import create_reminder

            delay_minutes = args.get("delay_minutes")
            if not due and delay_minutes is None:
                delay_minutes = 30
            reminder = await asyncio.to_thread(
                create_reminder,
                text,
                due or None,
                float(delay_minutes) if delay_minutes is not None else None,
            )
            return {"ok": True, "reminder": reminder}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    elif name == "download_media":
        url = str(args.get("url", "")).strip()
        if not url:
            return {"ok": False, "error": "url required"}
        # Stub — full implementation in Tranche F
        return {"ok": True, "url": url, "note": "Download queued (Tranche F)"}

    elif name == "memory_write":
        key = str(args.get("query") or args.get("key") or "").strip()
        value = str(args.get("value", "")).strip()
        if not key or not value:
            return {"ok": False, "error": "key and value required"}
        # Stub — full implementation in Tranche F
        try:
            from src.guppy.memory.semantic import remember_semantic

            category = str(args.get("category", "conversation") or "conversation").strip()
            stored = await asyncio.to_thread(remember_semantic, key, value, category)
            return {"ok": True, "key": key, "stored": stored}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    elif name == "memory_recall":
        key = str(args.get("key", "")).strip()
        if not key:
            return {"ok": False, "error": "key required"}
        # Stub — full implementation in Tranche F
        query = key
        try:
            from src.guppy.memory.semantic import recall_semantic

            n = int(args.get("n", 5) or 5)
            category = str(args.get("category", "") or "").strip()
            value = await asyncio.to_thread(recall_semantic, query, n, category)
            return {"ok": True, "query": query, "value": value}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    elif name == "workspace_task":
        task_text = str(
            args.get("task") or args.get("title") or args.get("description") or ""
        ).strip()
        description_text = str(args.get("description", "")).strip()
        if not task_text:
            return {"ok": False, "error": "task/title required"}
        try:
            from src.guppy.api.routes_surface import _spawn_task_direct
            task = _spawn_task_direct(
                title=task_text,
                description=description_text or task_text,
                source="conversations",
            )
            return {
                "ok": True,
                "task_id": task["id"],
                "status": task.get("status", "queued"),
                "task_description": task_text,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    else:
        return {"ok": False, "error": f"Tool not whitelisted for conversations: {name}"}


# ──────────────────────────────────────────────────────────────────────────────
# Tool-call parser (same as companion)
# ──────────────────────────────────────────────────────────────────────────────

_TOOL_CALL_RE = re.compile(
    r"(?:<tool_call>|<\|tool_call\|>)\s*(\{.*?\})\s*(?:</tool_call>|<\|tool_call\|>)",
    re.DOTALL,
)
_TOOL_START_MARKERS = ("<tool_call>", "<|tool_call|>", "<think>")
_TOOL_END_MARKERS = {
    "<tool_call>": "</tool_call>",
    "<|tool_call|>": "<|tool_call|>",
    "<think>": "</think>",
}


def _strip_tool_blocks(text: str) -> str:
    import re as _re
    text = _TOOL_CALL_RE.sub("", text)
    text = _re.sub(r"<think>.*?</think>", "", text, flags=_re.DOTALL)
    return text.strip()


def _marker_suffix_len(buffer: str) -> int:
    keep = 0
    for marker in _TOOL_START_MARKERS:
        max_len = min(len(marker) - 1, len(buffer))
        for size in range(max_len, 0, -1):
            if marker.startswith(buffer[-size:]):
                keep = max(keep, size)
                break
    return keep


def _visible_stream_chunks(
    buffer: str,
    tool_marker: str | None,
) -> tuple[list[str], str, str | None]:
    visible: list[str] = []
    while buffer:
        if tool_marker:
            end_marker = _TOOL_END_MARKERS[tool_marker]
            end_idx = buffer.find(end_marker)
            if end_idx < 0:
                keep = min(len(end_marker) - 1, len(buffer))
                return visible, buffer[-keep:] if keep else "", tool_marker
            buffer = buffer[end_idx + len(end_marker) :]
            tool_marker = None
            continue

        starts = [
            (idx, marker)
            for marker in _TOOL_START_MARKERS
            if (idx := buffer.find(marker)) >= 0
        ]
        if starts:
            idx, marker = min(starts, key=lambda item: item[0])
            if idx:
                visible.append(buffer[:idx])
            buffer = buffer[idx + len(marker) :]
            tool_marker = marker
            continue

        keep = _marker_suffix_len(buffer)
        if keep:
            if len(buffer) > keep:
                visible.append(buffer[:-keep])
            return visible, buffer[-keep:], None

        visible.append(buffer)
        return visible, "", None

    return visible, "", tool_marker


async def _execute_and_format_conversation_tools(
    ctx: ServerContext,
    assistant_text: str,
    *,
    session_id: str | None = None,
) -> tuple[str, list[dict]]:
    """Parse tool calls from assistant response, execute, and format results."""
    tool_results = []
    results_markdown = ""

    for match in _TOOL_CALL_RE.finditer(assistant_text):
        json_str = match.group(1)
        try:
            call = _repair_tool_json(json_str)
            if not isinstance(call, dict):
                continue
            name = call.get("name")
            args = call.get("arguments", {})
            if not name:
                continue

            logger.debug(f"Executing tool: {name} args={args}")
            result = await _execute_conversation_tool(ctx, name, args)
            from src.guppy.api.tool_call_log import log_tool_call
            log_tool_call(
                surface="conversations",
                tool_name=name,
                tool_args=args,
                result=result,
                session_id=session_id,
                conversation_id=session_id,
            )
            tool_results.append({"name": name, "result": result})

            if result.get("ok"):
                if name == "web_fetch":
                    results_markdown += f"\n\n**{name}** ({result.get('url', '?')})\n{result.get('text', '')[:2000]}"
                elif name == "workspace_task":
                    results_markdown += f"\n\n**Task queued** — ID: `{result.get('task_id')}` — Check Workspace panel"
                else:
                    results_markdown += f"\n\n**{name}** — {json.dumps(result, indent=2)[:500]}"
            else:
                results_markdown += f"\n\n**{name}** — Error: {result.get('error', 'Unknown')}"
        except Exception as e:
            logger.exception(f"Tool parse/exec error: {e}")

    return results_markdown, tool_results


async def _auto_generate_title(session_id: str, user_message: str) -> None:
    """Generate a descriptive 4-7 word title using phi-4-mini (port 8091).

    Fires as a background task after the first assistant response is saved.
    Falls back to a truncated user message if phi-4-mini is unavailable.
    """
    try:
        from src.guppy.api.routes_backends import _port_alive
        title: str = ""
        if _port_alive(8091):
            import httpx
            prompt = (
                f"Write a short 4-7 word title for this conversation.\n"
                f"First message: {user_message[:300]}\n"
                f"Output ONLY the title text. No quotes, no punctuation at end."
            )
            payload = {
                "model": "phi-4-mini",
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "max_tokens": 24,
                "temperature": 0.3,
            }
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(
                    "http://127.0.0.1:8091/v1/chat/completions",
                    json=payload,
                )
                resp.raise_for_status()
                raw = (
                    resp.json()
                    .get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip()
                )
                title = raw.strip("\"'").split("\n")[0][:80].strip()

        if not title:
            title = user_message[:60].rstrip(" .,?!") or "Conversation"

        with _db() as conn:
            conn.execute(
                "UPDATE conversation_sessions SET session_title = ? WHERE id = ?",
                (title, session_id),
            )
            conn.commit()
        logger.debug("[conversations] Auto-titled session %s → %r", session_id, title)
    except Exception:
        logger.debug("[conversations] Auto-title failed for session %s", session_id, exc_info=True)


async def _with_keepalives(
    source: AsyncGenerator[str, None],
    *,
    interval_seconds: float = 15.0,
) -> AsyncGenerator[str, None]:
    """Wrap an SSE source with comment keepalives during long model waits."""
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def _produce() -> None:
        try:
            async for item in source:
                await queue.put(item)
        finally:
            await queue.put(None)

    task = asyncio.create_task(_produce())
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=interval_seconds)
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"
                continue

            if item is None:
                break
            yield item
    finally:
        task.cancel()


# ──────────────────────────────────────────────────────────────────────────────
# Router
# ──────────────────────────────────────────────────────────────────────────────


def build_conversations_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/conversations", tags=["conversations"])

    _ensure_schema()

    # ──────────────────────────────────────────────────────────────────────────
    # Session CRUD
    # ──────────────────────────────────────────────────────────────────────────

    @router.post("/sessions", response_model=SessionResponse)
    async def create_session(
        _user_id: str = Depends(ctx.require_rate_limit),
    ) -> SessionResponse:
        """Create a new conversation session."""
        session_id = str(uuid.uuid4())
        backend = get_active_conversation_partner()
        now = _now()

        with _db() as conn:
            conn.execute(
                """INSERT INTO conversation_sessions
                   (id, session_title, model_backend, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (session_id, f"Session {now[:10]}", backend, now, now),
            )
            conn.commit()

        return SessionResponse(
            id=session_id,
            session_title=f"Session {now[:10]}",
            model_backend=backend,
            created_at=now,
            updated_at=now,
            message_count=0,
        )

    @router.get("/sessions", response_model=list[SessionResponse])
    async def list_sessions(
        _user_id: str = Depends(ctx.require_rate_limit),
    ) -> list[SessionResponse]:
        """List all conversation sessions."""
        with _db() as conn:
            rows = conn.execute(
                """SELECT id, session_title, model_backend, created_at, updated_at
                   FROM conversation_sessions ORDER BY updated_at DESC"""
            ).fetchall()
            result = []
            for row in rows:
                msg_count = conn.execute(
                    "SELECT COUNT(*) FROM conversation_session_messages WHERE conversation_id = ?",
                    (row["id"],),
                ).fetchone()[0]
                result.append(
                    SessionResponse(
                        id=row["id"],
                        session_title=row["session_title"],
                        model_backend=row["model_backend"],
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                        message_count=msg_count,
                    )
                )
        return result

    @router.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
    async def get_session_messages(
        session_id: str,
        limit: int = 100,
        offset: int = 0,
        _user_id: str = Depends(ctx.require_rate_limit),
    ) -> list[MessageResponse]:
        """Get messages in a session with optional pagination."""
        with _db() as conn:
            if not conn.execute(
                "SELECT 1 FROM conversation_sessions WHERE id = ?", (session_id,)
            ).fetchone():
                raise HTTPException(status_code=404, detail="Session not found")
            rows = conn.execute(
                """SELECT id, role, content, created_at
                   FROM conversation_session_messages
                   WHERE conversation_id = ?
                   ORDER BY created_at ASC
                   LIMIT ? OFFSET ?""",
                (session_id, max(1, min(limit, 500)), max(0, offset)),
            ).fetchall()
            return [
                MessageResponse(
                    id=row["id"],
                    role=row["role"],
                    content=row["content"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]

    @router.delete("/sessions/{session_id}")
    async def delete_session(
        session_id: str,
        _user_id: str = Depends(ctx.require_rate_limit),
    ) -> dict:
        """Delete a session and all its messages."""
        with _db() as conn:
            conn.execute("DELETE FROM conversation_sessions WHERE id = ?", (session_id,))
            conn.commit()
        return {"ok": True}

    @router.patch("/sessions/{session_id}")
    async def update_session_title(
        session_id: str,
        body: dict,
        _user_id: str = Depends(ctx.require_rate_limit),
    ) -> dict:
        """Update session metadata (title)."""
        title = str(body.get("session_title", "")).strip()[:200]
        if title:
            with _db() as conn:
                conn.execute(
                    "UPDATE conversation_sessions SET session_title=?, updated_at=? WHERE id=?",
                    (title, _now(), session_id),
                )
                conn.commit()
        return {"ok": True}

    @router.get("/search")
    async def search_conversations(
        q: str,
        limit: int = 20,
        _user_id: str = Depends(ctx.require_rate_limit),
    ) -> dict:
        """Full-text search across conversation messages.

        Returns sessions with matching messages, ranked by recency.
        Each result includes the session metadata and up to 3 matching snippets.
        """
        if not q or len(q.strip()) < 2:
            raise HTTPException(400, "query must be at least 2 characters")
        q = q.strip()
        limit = max(1, min(limit, 100))

        pattern = f"%{q}%"
        with _db() as conn:
            rows = conn.execute(
                """
                SELECT
                    s.id          AS session_id,
                    s.session_title,
                    s.updated_at,
                    m.id          AS message_id,
                    m.role,
                    m.content,
                    m.created_at  AS message_at
                FROM conversation_session_messages m
                JOIN conversation_sessions s ON m.conversation_id = s.id
                WHERE m.content LIKE ? COLLATE NOCASE
                ORDER BY s.updated_at DESC, m.created_at ASC
                LIMIT ?
                """,
                (pattern, limit * 5),
            ).fetchall()

        # Group by session, collect up to 3 snippet per session
        seen_sessions: dict[str, dict] = {}
        for row in rows:
            sid = row["session_id"]
            if sid not in seen_sessions:
                seen_sessions[sid] = {
                    "session_id": sid,
                    "session_title": row["session_title"],
                    "updated_at": row["updated_at"],
                    "snippets": [],
                }
            if len(seen_sessions[sid]["snippets"]) < 3:
                content = row["content"]
                idx = content.lower().find(q.lower())
                snippet = content[max(0, idx - 60) : idx + 200].strip() if idx >= 0 else content[:200]
                seen_sessions[sid]["snippets"].append({
                    "message_id": row["message_id"],
                    "role": row["role"],
                    "snippet": snippet,
                    "message_at": row["message_at"],
                })

        results = list(seen_sessions.values())[:limit]
        return {"query": q, "total": len(results), "results": results}

    # ──────────────────────────────────────────────────────────────────────────
    # Chat (non-streaming)
    # ──────────────────────────────────────────────────────────────────────────

    @router.post("/chat")
    async def chat(
        req: ChatRequest,
        _user_id: str = Depends(ctx.require_rate_limit),
    ) -> dict:
        """Non-streaming chat endpoint."""
        # Get or create session
        session_id = req.session_id
        if not session_id:
            backend = get_active_conversation_partner()
            session_id = str(uuid.uuid4())
            now = _now()
            with _db() as conn:
                conn.execute(
                    """INSERT INTO conversation_sessions
                       (id, session_title, model_backend, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (session_id, f"Session {now[:10]}", backend, now, now),
                )
                conn.commit()
        else:
            with _db() as conn:
                c = conn.execute(
                    "SELECT model_backend FROM conversation_sessions WHERE id = ?", (session_id,)
                ).fetchone()
                if not c:
                    raise HTTPException(status_code=404, detail="Session not found")
                # Always use current active partner; fall back to stored backend
                backend = get_active_conversation_partner() or c["model_backend"]

        # Save user message
        user_msg_id = str(uuid.uuid4())
        with _db() as conn:
            conn.execute(
                """INSERT INTO conversation_session_messages
                   (id, conversation_id, role, content, image_url, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_msg_id, session_id, "user", req.message, req.image_base64, _now()),
            )
            conn.commit()

        # Get history (trim to context budget before inference)
        with _db() as conn:
            history_rows = conn.execute(
                """SELECT role, content FROM conversation_session_messages
                   WHERE conversation_id = ? ORDER BY created_at ASC""",
                (session_id,),
            ).fetchall()
            history = sanitize_chat_history(
                [{"role": row["role"], "content": row["content"]} for row in history_rows],
                backend=backend,
            )

        # Run inference
        full_response = ""
        try:
            async for token in _stream_conversation_inference(
                ctx,
                message=req.message,
                backend=backend,
                history=history,
                image_base64=req.image_base64,
            ):
                full_response += token
        except Exception as e:
            logger.exception("Inference failed")
            return {"ok": False, "error": str(e)}

        # Execute tools and format clean confirmation
        stripped_response = _strip_tool_blocks(full_response)
        try:
            tool_markdown, tool_results = await _execute_and_format_conversation_tools(
                ctx,
                full_response,
                session_id=session_id,
            )
        except Exception as e:
            logger.exception("Tool execution failed")
            tool_markdown, tool_results = "", []
        final_response = (stripped_response + tool_markdown).strip()

        # Save assistant message; auto-title on first exchange
        assistant_msg_id = str(uuid.uuid4())
        now = _now()
        _needs_title = False
        with _db() as conn:
            conn.execute(
                """INSERT INTO conversation_session_messages
                   (id, conversation_id, role, content, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (assistant_msg_id, session_id, "assistant", final_response, now),
            )
            conn.execute(
                "UPDATE conversation_sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )
            title_row = conn.execute(
                "SELECT session_title FROM conversation_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if title_row and title_row[0].startswith("Session "):
                _needs_title = True
            conn.commit()
        if _needs_title:
            asyncio.create_task(_auto_generate_title(session_id, req.message))

        return {
            "ok": True,
            "session_id": session_id,
            "response": final_response,
            "tool_results": tool_results,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Chat (streaming SSE)
    # ──────────────────────────────────────────────────────────────────────────

    @router.post("/chat/stream")
    async def chat_stream(
        req: ChatRequest,
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        """Streaming chat via SSE."""
        # Get or create session
        session_id = req.session_id
        if not session_id:
            backend = get_active_conversation_partner()
            session_id = str(uuid.uuid4())
            now = _now()
            with _db() as conn:
                conn.execute(
                    """INSERT INTO conversation_sessions
                       (id, session_title, model_backend, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (session_id, f"Session {now[:10]}", backend, now, now),
                )
                conn.commit()
        else:
            with _db() as conn:
                c = conn.execute(
                    "SELECT model_backend FROM conversation_sessions WHERE id = ?", (session_id,)
                ).fetchone()
                if not c:
                    raise HTTPException(status_code=404, detail="Session not found")
                # Always use current active partner; fall back to stored backend
                backend = get_active_conversation_partner() or c["model_backend"]

        # Save user message
        user_msg_id = str(uuid.uuid4())
        with _db() as conn:
            conn.execute(
                """INSERT INTO conversation_session_messages
                   (id, conversation_id, role, content, image_url, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_msg_id, session_id, "user", req.message, req.image_base64, _now()),
            )
            conn.commit()

        # Get history (trim to context budget before inference)
        with _db() as conn:
            history_rows = conn.execute(
                """SELECT role, content FROM conversation_session_messages
                   WHERE conversation_id = ? ORDER BY created_at ASC""",
                (session_id,),
            ).fetchall()
            history = sanitize_chat_history(
                [{"role": row["role"], "content": row["content"]} for row in history_rows],
                backend=backend,
            )

        async def _stream():
            """Stream tokens + execute tool calls + synthesize results + save."""
            full_response = ""
            visible_buffer = ""
            tool_marker: str | None = None
            try:
                yield f"data: {json.dumps({'session_id': session_id, 'status': 'started'})}\n\n"

                # Phase 1: stream initial model response (tool blocks hidden in visible output)
                try:
                    async with asyncio.timeout(120.0):
                        async for token in _stream_conversation_inference(
                            ctx,
                            message=req.message,
                            backend=backend,
                            history=history,
                            image_base64=req.image_base64,
                        ):
                            full_response += token
                            visible_buffer += token
                            chunks, visible_buffer, tool_marker = _visible_stream_chunks(
                                visible_buffer,
                                tool_marker,
                            )
                            for chunk in chunks:
                                if chunk:
                                    yield f"data: {json.dumps({'token': chunk})}\n\n"
                except asyncio.TimeoutError:
                    logger.warning("[conversations] Phase-1 inference timed out (session %s)", session_id)
                    yield f"data: {json.dumps({'error': 'Response timed out. Please try again.'})}\n\n"
                except asyncio.CancelledError:
                    logger.info("Client disconnected mid-stream — cancelling conversations phase-1 inference")
                    return

                # Flush remaining visible buffer (text after last tool block)
                if visible_buffer and tool_marker is None:
                    yield f"data: {json.dumps({'token': visible_buffer})}\n\n"

                # Phase 2: execute tool calls
                stripped_response = _strip_tool_blocks(full_response)
                final_response = stripped_response

                if _TOOL_CALL_RE.search(full_response):
                    try:
                        tool_markdown, tool_results = await _execute_and_format_conversation_tools(
                            ctx,
                            full_response,
                            session_id=session_id,
                        )
                    except Exception as tool_exc:
                        logger.exception("[conversations] Tool execution failed (session %s)", session_id)
                        yield f"data: {json.dumps({'error': f'Tool error: {tool_exc}'})}\n\n"
                        tool_markdown, tool_results = "", []

                    if tool_results:
                        # Phase 3: synthesis — model sees tool results and generates answer
                        synthesis_history = list(history)
                        synthesis_history.append({"role": "user", "content": req.message})
                        if stripped_response.strip():
                            synthesis_history.append(
                                {"role": "assistant", "content": stripped_response}
                            )
                        synthesis_prompt = (
                            f"[Tool Results]\n{tool_markdown}\n\n"
                            "Using the results above, answer the original question directly and concisely."
                        )
                        synthesis_text = ""
                        _synth_buf = ""
                        _synth_marker: str | None = None
                        try:
                            async with asyncio.timeout(90.0):
                                async for token in _stream_conversation_inference(
                                    ctx,
                                    message=synthesis_prompt,
                                    backend=backend,
                                    history=synthesis_history,
                                ):
                                    synthesis_text += token
                                    _synth_buf += token
                                    _chunks, _synth_buf, _synth_marker = _visible_stream_chunks(
                                        _synth_buf, _synth_marker
                                    )
                                    for _chunk in _chunks:
                                        if _chunk:
                                            yield f"data: {json.dumps({'token': _chunk})}\n\n"
                        except asyncio.TimeoutError:
                            logger.warning("[conversations] Synthesis inference timed out (session %s)", session_id)
                            yield f"data: {json.dumps({'error': 'Synthesis timed out.'})}\n\n"
                        except asyncio.CancelledError:
                            logger.info("Client disconnected mid-stream — cancelling conversations synthesis inference")
                            return
                        if _synth_buf and _synth_marker is None:
                            yield f"data: {json.dumps({'token': _synth_buf})}\n\n"

                        final_response = (
                            (stripped_response.strip() + "\n\n" if stripped_response.strip() else "")
                            + synthesis_text
                        ).strip()

                # Save assistant message; auto-title on first exchange
                assistant_msg_id = str(uuid.uuid4())
                save_now = _now()
                _needs_title = False
                with _db() as conn:
                    conn.execute(
                        """INSERT INTO conversation_session_messages
                           (id, conversation_id, role, content, created_at)
                           VALUES (?, ?, ?, ?, ?)""",
                        (assistant_msg_id, session_id, "assistant", final_response, save_now),
                    )
                    conn.execute(
                        "UPDATE conversation_sessions SET updated_at = ? WHERE id = ?",
                        (save_now, session_id),
                    )
                    title_row = conn.execute(
                        "SELECT session_title FROM conversation_sessions WHERE id = ?", (session_id,)
                    ).fetchone()
                    if title_row and title_row[0].startswith("Session "):
                        _needs_title = True
                    conn.commit()
                if _needs_title:
                    asyncio.create_task(_auto_generate_title(session_id, req.message))

                yield "data: [DONE]\n\n"
            except asyncio.CancelledError:
                logger.info("Client disconnected mid-stream — cancelling conversations stream")
                return
            except Exception as e:
                logger.exception("Stream error")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(_with_keepalives(_stream()), media_type="text/event-stream")

    return router
