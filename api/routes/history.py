"""Cloud-safe chat history routes.

Stores conversations and messages in-process (ephemeral per deployment).
A persistent store can replace the dicts when a database is wired in.
"""
from __future__ import annotations

import time
import uuid
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["history"])

# conversation_id → {id, workspace_id, title, message_count, created_at, updated_at}
_conversations: dict[str, dict[str, Any]] = {}

# conversation_id → list of {id, conversation_id, role, content, model, created_at}
_messages: dict[str, list[dict[str, Any]]] = defaultdict(list)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class ConversationCreate(BaseModel):
    workspace_id: str = ""
    title: str = ""


class ConversationUpdate(BaseModel):
    title: str


class MessageCreate(BaseModel):
    role: str
    content: str
    model: str = ""


@router.get("/api/chat/history")
async def list_conversations(workspace_id: str = "", limit: int = 50) -> dict[str, Any]:
    convs = list(_conversations.values())
    if workspace_id:
        convs = [c for c in convs if c.get("workspace_id") == workspace_id]
    convs = sorted(convs, key=lambda c: c.get("updated_at", ""), reverse=True)[:limit]
    return {"conversations": convs, "total": len(convs)}


@router.post("/api/chat/history")
async def create_conversation(body: ConversationCreate) -> dict[str, Any]:
    conv_id = str(uuid.uuid4())
    now = _now()
    title = body.title or f"Conversation {len(_conversations) + 1}"
    conv: dict[str, Any] = {
        "id": conv_id,
        "workspace_id": body.workspace_id or "default",
        "title": title,
        "message_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    _conversations[conv_id] = conv
    return conv


@router.get("/api/chat/history/{conversation_id}")
async def get_conversation(conversation_id: str) -> dict[str, Any]:
    conv = _conversations.get(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {**conv, "messages": _messages.get(conversation_id, [])}


@router.put("/api/chat/history/{conversation_id}")
async def update_conversation(conversation_id: str, body: ConversationUpdate) -> dict[str, Any]:
    conv = _conversations.get(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv["title"] = body.title
    conv["updated_at"] = _now()
    return conv


@router.delete("/api/chat/history/{conversation_id}")
async def delete_conversation(conversation_id: str) -> dict[str, Any]:
    if conversation_id not in _conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")
    _conversations.pop(conversation_id)
    _messages.pop(conversation_id, None)
    return {"ok": True}


@router.get("/api/chat/history/{conversation_id}/messages")
async def list_messages(conversation_id: str) -> dict[str, Any]:
    if conversation_id not in _conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")
    msgs = _messages.get(conversation_id, [])
    return {"messages": msgs, "total": len(msgs)}


@router.post("/api/chat/history/{conversation_id}/messages")
async def add_message(conversation_id: str, body: MessageCreate) -> dict[str, Any]:
    if conversation_id not in _conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")
    msg: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "role": body.role,
        "content": body.content,
        "model": body.model or None,
        "created_at": _now(),
    }
    _messages[conversation_id].append(msg)
    _conversations[conversation_id]["message_count"] = len(_messages[conversation_id])
    _conversations[conversation_id]["updated_at"] = _now()
    return msg


@router.get("/api/chat/history/{conversation_id}/search")
async def search_messages(conversation_id: str, q: str = "") -> dict[str, Any]:
    msgs = _messages.get(conversation_id, [])
    if q:
        q_lower = q.lower()
        msgs = [m for m in msgs if q_lower in m.get("content", "").lower()]
    return {"messages": msgs, "total": len(msgs)}
