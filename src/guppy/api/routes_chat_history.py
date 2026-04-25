"""Chat history persistence API — save, retrieve, and manage conversations.

GET  /api/chat/history              — list all conversations
GET  /api/chat/history/{conv_id}    — get conversation with all messages
POST /api/chat/history              — create new conversation { workspace_id: string, title?: string }
PUT  /api/chat/history/{conv_id}    — update conversation metadata
DELETE /api/chat/history/{conv_id}  — delete conversation
POST /api/chat/history/{conv_id}/messages — add message to conversation
GET  /api/chat/history/search       — search conversations by keyword
"""
from __future__ import annotations

import asyncio
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from src.guppy.api.server_context import ServerContext
from src.guppy.paths import ensure_user_data_dir


def _default_chat_history_db_path() -> str:
    return str(ensure_user_data_dir() / "chat_history.db")


class ChatHistoryDB:
    """SQLite-based chat history storage."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or _default_chat_history_db_path()
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema if not exists."""
        with sqlite3.connect(self.db_path) as conn:
            # Conversations table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    message_count INTEGER DEFAULT 0
                )
                """
            )

            # Messages table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    model TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                )
                """
            )

            # Create index for faster lookups
            conn.execute("CREATE INDEX IF NOT EXISTS idx_conv_workspace ON conversations(workspace_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id)")

            conn.commit()

    def create_conversation(self, workspace_id: str, title: Optional[str] = None) -> Dict[str, Any]:
        """Create a new conversation."""
        conv_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        final_title = title or f"Conversation {now[:10]}"

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO conversations (id, workspace_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (conv_id, workspace_id, final_title, now, now),
            )
            conn.commit()

        return {
            "id": conv_id,
            "workspace_id": workspace_id,
            "title": final_title,
            "created_at": now,
            "updated_at": now,
            "message_count": 0,
        }

    def list_conversations(self, workspace_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """List conversations in a workspace."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM conversations
                WHERE workspace_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (workspace_id, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_conversation(self, conv_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation metadata."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()
            return dict(row) if row else None

    def get_conversation_with_messages(self, conv_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation with all messages."""
        conv = self.get_conversation(conv_id)
        if not conv:
            return None

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            msg_rows = conn.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
                (conv_id,),
            ).fetchall()

        conv["messages"] = [dict(row) for row in msg_rows]
        return conv

    def add_message(self, conv_id: str, role: str, content: str, model: Optional[str] = None) -> Dict[str, Any]:
        """Add a message to a conversation."""
        msg_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            # Add message
            conn.execute(
                """
                INSERT INTO messages (id, conversation_id, role, content, model, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (msg_id, conv_id, role, content, model, now),
            )

            # Update conversation updated_at and message_count
            conn.execute(
                """
                UPDATE conversations
                SET updated_at = ?, message_count = (SELECT COUNT(*) FROM messages WHERE conversation_id = ?)
                WHERE id = ?
                """,
                (now, conv_id, conv_id),
            )
            conn.commit()

        return {
            "id": msg_id,
            "conversation_id": conv_id,
            "role": role,
            "content": content,
            "model": model,
            "created_at": now,
        }

    def update_conversation_title(self, conv_id: str, title: str) -> Dict[str, Any]:
        """Update conversation title."""
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                (title, now, conv_id),
            )
            conn.commit()
        return self.get_conversation(conv_id)

    def delete_conversation(self, conv_id: str) -> bool:
        """Delete a conversation and all its messages."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
            conn.commit()
        return True

    def search_conversations(self, workspace_id: str, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search conversations by title and content."""
        search_term = f"%{query}%"
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT DISTINCT c.* FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                WHERE c.workspace_id = ? AND (c.title LIKE ? OR m.content LIKE ?)
                ORDER BY c.updated_at DESC
                LIMIT ?
                """,
                (workspace_id, search_term, search_term, limit),
            ).fetchall()
            return [dict(row) for row in rows]


# Global DB instance
_chat_history_db = ChatHistoryDB()


def build_chat_history_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/chat/history")

    @router.get("")
    async def list_conversations(
        workspace_id: str,
        limit: int = 50,
        user_id: str = Depends(ctx.require_rate_limit),
    ):
        """List conversations in a workspace."""
        del user_id
        conversations = await asyncio.to_thread(_chat_history_db.list_conversations, workspace_id, limit)
        return {"conversations": conversations, "count": len(conversations)}

    @router.post("")
    async def create_conversation(
        payload: Dict[str, str],
        user_id: str = Depends(ctx.require_rate_limit),
    ):
        """Create a new conversation."""
        del user_id
        workspace_id = payload.get("workspace_id", "").strip()
        if not workspace_id:
            raise HTTPException(status_code=400, detail="workspace_id required")

        title = payload.get("title", "").strip() or None
        conv = await asyncio.to_thread(_chat_history_db.create_conversation, workspace_id, title)
        return conv

    @router.get("/{conv_id}")
    async def get_conversation(conv_id: str, user_id: str = Depends(ctx.require_rate_limit)):
        """Get conversation with messages."""
        del user_id
        conv = await asyncio.to_thread(_chat_history_db.get_conversation_with_messages, conv_id)
        if not conv:
            raise HTTPException(status_code=404, detail="conversation not found")
        return conv

    @router.put("/{conv_id}")
    async def update_conversation(
        conv_id: str,
        payload: Dict[str, str],
        user_id: str = Depends(ctx.require_rate_limit),
    ):
        """Update conversation metadata."""
        del user_id
        title = payload.get("title", "").strip()
        if not title:
            raise HTTPException(status_code=400, detail="title required")

        conv = await asyncio.to_thread(_chat_history_db.update_conversation_title, conv_id, title)
        if not conv:
            raise HTTPException(status_code=404, detail="conversation not found")
        return conv

    @router.delete("/{conv_id}")
    async def delete_conversation(conv_id: str, user_id: str = Depends(ctx.require_rate_limit)):
        """Delete a conversation."""
        del user_id
        await asyncio.to_thread(_chat_history_db.delete_conversation, conv_id)
        return {"deleted": conv_id}

    @router.post("/{conv_id}/messages")
    async def add_message(
        conv_id: str,
        payload: Dict[str, str],
        user_id: str = Depends(ctx.require_rate_limit),
    ):
        """Add a message to a conversation."""
        del user_id
        role = payload.get("role", "").strip()
        content = payload.get("content", "").strip()
        model = payload.get("model", "").strip() or None

        if not role or not content:
            raise HTTPException(status_code=400, detail="role and content required")

        message = await asyncio.to_thread(_chat_history_db.add_message, conv_id, role, content, model)
        return message

    @router.get("/search/{workspace_id}")
    async def search_conversations(
        workspace_id: str,
        q: str,
        limit: int = 20,
        user_id: str = Depends(ctx.require_rate_limit),
    ):
        """Search conversations."""
        del user_id
        if not q.strip():
            raise HTTPException(status_code=400, detail="search query required")

        results = await asyncio.to_thread(_chat_history_db.search_conversations, workspace_id, q, limit)
        return {"results": results, "count": len(results), "query": q}

    return router
