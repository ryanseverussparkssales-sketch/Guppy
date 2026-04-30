"""Conversations Surface — dedicated chat with persistent sessions.

Routes:
  POST /api/conversations/chat          — non-streaming
  POST /api/conversations/chat/stream   — SSE streaming (primary)
  GET  /api/conversations/sessions      — list sessions
  POST /api/conversations/sessions      — create session
  GET  /api/conversations/sessions/{id}/messages
  DELETE /api/conversations/sessions/{id}

Conversations always use the active conversation partner model (operator-selectable).
Tool envelope: web_fetch, create_reminder, download_media, memory_write, memory_recall, workspace_task only.
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.guppy.api.realtime_inference_support import stream_unified_inference, _repair_tool_json
from src.guppy.api.server_context import ServerContext
from src.guppy.model_roles import get_active_conversation_partner, resolve_role
from src.guppy.paths import USER_DATA_DIR

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# DB helpers
# ──────────────────────────────────────────────────────────────────────────────

_DB_PATH: str = ""

_CONVERSATIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id                TEXT PRIMARY KEY,
    session_title     TEXT,
    model_backend     TEXT,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversation_messages (
    id                TEXT PRIMARY KEY,
    conversation_id   TEXT NOT NULL,
    role              TEXT NOT NULL,
    content           TEXT NOT NULL,
    image_url         TEXT,
    created_at        TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);
"""


def _db() -> sqlite3.Connection:
    path = _DB_PATH or str(USER_DATA_DIR / "guppy_main.db")
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

async def _execute_conversation_tool(name: str, args: dict) -> dict:
    """Execute one conversation tool call. Returns a result dict.
    
    Whitelist: web_fetch, create_reminder, download_media, memory_write,
    memory_recall, workspace_task.
    """
    import httpx

    if name == "web_fetch":
        url = str(args.get("url", "")).strip()
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
                    text = text[max(0, idx - 100) : idx + 6000]
            return {"ok": True, "text": text[:8000], "url": url}
        except Exception as e:
            return {"ok": False, "error": str(e), "url": url}

    elif name == "create_reminder":
        text = str(args.get("text", "")).strip()
        due = str(args.get("due", "")).strip()
        if not text:
            return {"ok": False, "error": "text required"}
        try:
            with _db() as conn:
                reminder_id = str(uuid.uuid4())
                conn.execute(
                    """INSERT INTO reminders (id, text, due, created_at, status)
                       VALUES (?, ?, ?, ?, 'pending')""",
                    (reminder_id, text, due, _now()),
                )
                conn.commit()
            return {"ok": True, "reminder_id": reminder_id, "text": text[:100], "due": due}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    elif name == "download_media":
        url = str(args.get("url", "")).strip()
        if not url:
            return {"ok": False, "error": "url required"}
        # Stub — full implementation in Tranche F
        return {"ok": True, "url": url, "note": "Download queued (Tranche F)"}

    elif name == "memory_write":
        key = str(args.get("key", "")).strip()
        value = str(args.get("value", "")).strip()
        if not key or not value:
            return {"ok": False, "error": "key and value required"}
        # Stub — full implementation in Tranche F
        return {"ok": True, "key": key, "note": "Memory write pending (Tranche F)"}

    elif name == "memory_recall":
        key = str(args.get("key", "")).strip()
        if not key:
            return {"ok": False, "error": "key required"}
        # Stub — full implementation in Tranche F
        return {"ok": True, "key": key, "value": None, "note": "Memory recall pending (Tranche F)"}

    elif name == "workspace_task":
        task_text = str(args.get("task", "")).strip()
        if not task_text:
            return {"ok": False, "error": "task required"}
        # Create task in workspace via internal API
        try:
            import httpx

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "http://127.0.0.1:8000/api/workspace/tasks",
                    json={"task_description": task_text, "source": "conversations"},
                    headers={"Authorization": "Bearer internal"},
                )
                if resp.status_code == 201:
                    data = resp.json()
                    return {"ok": True, "task_id": data.get("id"), "status": "queued"}
                else:
                    return {"ok": False, "error": f"Workspace API returned {resp.status_code}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    else:
        return {"ok": False, "error": f"Tool not whitelisted for conversations: {name}"}


# ──────────────────────────────────────────────────────────────────────────────
# Tool-call parser (same as companion)
# ──────────────────────────────────────────────────────────────────────────────

_TOOL_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)


async def _execute_and_format_conversation_tools(
    assistant_text: str,
) -> tuple[str, list[dict]]:
    """Parse tool calls from assistant response, execute, and format results."""
    tool_results = []
    results_markdown = ""

    for match in _TOOL_CALL_RE.finditer(assistant_text):
        json_str = match.group(1)
        try:
            call = json.loads(_repair_tool_json(json_str))
            name = call.get("name")
            args = call.get("arguments", {})
            if not name:
                continue

            logger.debug(f"Executing tool: {name} args={args}")
            result = await _execute_conversation_tool(name, args)
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
    async def create_session() -> SessionResponse:
        """Create a new conversation session."""
        session_id = str(uuid.uuid4())
        backend = resolve_role(get_active_conversation_partner())
        now = _now()

        with _db() as conn:
            conn.execute(
                """INSERT INTO conversations
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
    async def list_sessions() -> list[SessionResponse]:
        """List all conversation sessions."""
        with _db() as conn:
            rows = conn.execute(
                """SELECT id, session_title, model_backend, created_at, updated_at
                   FROM conversations ORDER BY updated_at DESC"""
            ).fetchall()
            result = []
            for row in rows:
                msg_count = conn.execute(
                    "SELECT COUNT(*) FROM conversation_messages WHERE conversation_id = ?",
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
    async def get_session_messages(session_id: str) -> list[MessageResponse]:
        """Get all messages in a session."""
        with _db() as conn:
            rows = conn.execute(
                """SELECT id, role, content, created_at
                   FROM conversation_messages
                   WHERE conversation_id = ?
                   ORDER BY created_at ASC""",
                (session_id,),
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
    async def delete_session(session_id: str) -> dict:
        """Delete a session and all its messages."""
        with _db() as conn:
            conn.execute("DELETE FROM conversations WHERE id = ?", (session_id,))
            conn.commit()
        return {"ok": True}

    # ──────────────────────────────────────────────────────────────────────────
    # Chat (non-streaming)
    # ──────────────────────────────────────────────────────────────────────────

    @router.post("/chat")
    async def chat(req: ChatRequest) -> dict:
        """Non-streaming chat endpoint."""
        # Get or create session
        session_id = req.session_id
        if not session_id:
            backend = resolve_role(get_active_conversation_partner())
            session_id = str(uuid.uuid4())
            now = _now()
            with _db() as conn:
                conn.execute(
                    """INSERT INTO conversations
                       (id, session_title, model_backend, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (session_id, f"Session {now[:10]}", backend, now, now),
                )
                conn.commit()
        else:
            with _db() as conn:
                c = conn.execute(
                    "SELECT model_backend FROM conversations WHERE id = ?", (session_id,)
                ).fetchone()
                if not c:
                    raise HTTPException(status_code=404, detail="Session not found")
                backend = c["model_backend"]

        # Save user message
        user_msg_id = str(uuid.uuid4())
        with _db() as conn:
            conn.execute(
                """INSERT INTO conversation_messages
                   (id, conversation_id, role, content, image_url, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_msg_id, session_id, "user", req.message, req.image_base64, _now()),
            )
            conn.commit()

        # Get history
        with _db() as conn:
            history_rows = conn.execute(
                """SELECT role, content FROM conversation_messages
                   WHERE conversation_id = ? ORDER BY created_at ASC""",
                (session_id,),
            ).fetchall()
            history = [{"role": row["role"], "content": row["content"]} for row in history_rows]

        # Run inference
        full_response = ""
        try:
            async for token in stream_unified_inference(
                surface="conversations",
                model_backend=backend,
                history=history,
                is_voice=False,
                system_prompt=None,
            ):
                full_response += token
        except Exception as e:
            logger.exception("Inference failed")
            return {"ok": False, "error": str(e)}

        # Execute tools and format
        tool_markdown, tool_results = await _execute_and_format_conversation_tools(full_response)
        full_response += tool_markdown

        # Save assistant message
        assistant_msg_id = str(uuid.uuid4())
        with _db() as conn:
            conn.execute(
                """INSERT INTO conversation_messages
                   (id, conversation_id, role, content, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (assistant_msg_id, session_id, "assistant", full_response, _now()),
            )
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (_now(), session_id),
            )
            conn.commit()

        return {
            "ok": True,
            "session_id": session_id,
            "response": full_response,
            "tool_results": tool_results,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Chat (streaming SSE)
    # ──────────────────────────────────────────────────────────────────────────

    @router.post("/chat/stream")
    async def chat_stream(req: ChatRequest):
        """Streaming chat via SSE."""
        # Get or create session
        session_id = req.session_id
        if not session_id:
            backend = resolve_role(get_active_conversation_partner())
            session_id = str(uuid.uuid4())
            now = _now()
            with _db() as conn:
                conn.execute(
                    """INSERT INTO conversations
                       (id, session_title, model_backend, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (session_id, f"Session {now[:10]}", backend, now, now),
                )
                conn.commit()
        else:
            with _db() as conn:
                c = conn.execute(
                    "SELECT model_backend FROM conversations WHERE id = ?", (session_id,)
                ).fetchone()
                if not c:
                    raise HTTPException(status_code=404, detail="Session not found")
                backend = c["model_backend"]

        # Save user message
        user_msg_id = str(uuid.uuid4())
        with _db() as conn:
            conn.execute(
                """INSERT INTO conversation_messages
                   (id, conversation_id, role, content, image_url, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_msg_id, session_id, "user", req.message, req.image_base64, _now()),
            )
            conn.commit()

        # Get history
        with _db() as conn:
            history_rows = conn.execute(
                """SELECT role, content FROM conversation_messages
                   WHERE conversation_id = ? ORDER BY created_at ASC""",
                (session_id,),
            ).fetchall()
            history = [{"role": row["role"], "content": row["content"]} for row in history_rows]

        async def _stream():
            """Stream tokens + handle tool calls + save final response."""
            full_response = ""
            try:
                async for token in stream_unified_inference(
                    surface="conversations",
                    model_backend=backend,
                    history=history,
                    is_voice=False,
                    system_prompt=None,
                ):
                    full_response += token
                    yield f"data: {json.dumps({'token': token, 'session_id': session_id})}\n\n"

                # Execute tools
                tool_markdown, tool_results = await _execute_and_format_conversation_tools(
                    full_response
                )
                full_response += tool_markdown

                # Emit tool results
                for tr in tool_results:
                    yield f"data: {json.dumps({'tool': tr['name'], 'result': tr['result']})}\n\n"

                # Save assistant message
                assistant_msg_id = str(uuid.uuid4())
                with _db() as conn:
                    conn.execute(
                        """INSERT INTO conversation_messages
                           (id, conversation_id, role, content, created_at)
                           VALUES (?, ?, ?, ?, ?)""",
                        (assistant_msg_id, session_id, "assistant", full_response, _now()),
                    )
                    conn.execute(
                        "UPDATE conversations SET updated_at = ? WHERE id = ?",
                        (_now(), session_id),
                    )
                    conn.commit()

                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.exception("Stream error")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(_stream(), media_type="text/event-stream")

    return router
