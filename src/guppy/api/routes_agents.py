"""Custom agents registry API.

GET    /api/agents           — list all agents
POST   /api/agents           — create a new agent
GET    /api/agents/{id}      — get one agent
PUT    /api/agents/{id}      — update an agent
DELETE /api/agents/{id}      — delete an agent
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.guppy.api.server_context import ServerContext
from src.guppy.paths import MAIN_DB_PATH, ensure_user_data_dir


_SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    model         TEXT NOT NULL DEFAULT 'guppy',
    system_prompt TEXT NOT NULL DEFAULT '',
    tools_json    TEXT NOT NULL DEFAULT '[]',
    color         TEXT NOT NULL DEFAULT 'bg-primary/10 text-primary',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
"""

_SEED_AGENTS = [
    (
        "builtin-fast",
        "Guppy Fast",
        "guppy-fast",
        "You are a fast, concise butler. Answer directly and briefly. No padding.",
        "[]",
        "bg-success/10 text-success",
    ),
    (
        "builtin-code",
        "Guppy Code",
        "guppy-code",
        "You are an expert software engineer. Write clean, idiomatic code with minimal but precise comments. Always include a usage example.",
        "[]",
        "bg-info/10 text-info",
    ),
    (
        "builtin-deep",
        "Guppy",
        "guppy",
        "You are a thorough analyst and problem-solver. Explore topics deeply, surface tradeoffs, and reason step-by-step.",
        "[]",
        "bg-primary/10 text-primary",
    ),
    (
        "builtin-teach",
        "Guppy Teach",
        "guppy-teach",
        "You are a Socratic teacher. Never just give answers — guide understanding through analogies, questions, and examples.",
        "[]",
        "bg-secondary/10 text-secondary",
    ),
    (
        "builtin-vault",
        "Vault Scraper",
        "vault-scraper",
        "You are a structured metadata extraction agent. Extract and output data as clean JSON matching the requested schema. No prose.",
        "[]",
        "bg-warning/10 text-warning",
    ),
]


def _db_path() -> str:
    return str(MAIN_DB_PATH)


def _init_db() -> None:
    with sqlite3.connect(_db_path()) as conn:
        conn.executescript(_SCHEMA)
        existing = {r[0] for r in conn.execute("SELECT id FROM agents").fetchall()}
        now = datetime.now(timezone.utc).isoformat()
        for row in _SEED_AGENTS:
            if row[0] not in existing:
                conn.execute(
                    "INSERT INTO agents (id, name, model, system_prompt, tools_json, color, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                    (*row, now, now),
                )
        conn.commit()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "model": row["model"],
        "system_prompt": row["system_prompt"],
        "tools": json.loads(row["tools_json"] or "[]"),
        "color": row["color"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "builtin": row["id"].startswith("builtin-"),
    }


def _get_all_agents() -> list[dict]:
    with sqlite3.connect(_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        return [_row_to_dict(r) for r in conn.execute("SELECT * FROM agents ORDER BY created_at").fetchall()]


def _get_agent(agent_id: str) -> dict | None:
    with sqlite3.connect(_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        r = conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
        return _row_to_dict(r) if r else None


def _create_agent(
    name: str,
    model: str,
    system_prompt: str,
    tools: list,
    color: str,
) -> dict:
    agent_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(_db_path()) as conn:
        conn.execute(
            "INSERT INTO agents (id, name, model, system_prompt, tools_json, color, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (agent_id, name, model, system_prompt, json.dumps(tools), color, now, now),
        )
        conn.commit()
    return _get_agent(agent_id)  # type: ignore[return-value]


def _update_agent(agent_id: str, fields: dict) -> dict:
    allowed = {"name", "model", "system_prompt", "tools", "color"}
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(_db_path()) as conn:
        for key, val in fields.items():
            if key not in allowed:
                continue
            col = "tools_json" if key == "tools" else key
            db_val = json.dumps(val) if key == "tools" else val
            conn.execute(f"UPDATE agents SET {col}=?, updated_at=? WHERE id=?", (db_val, now, agent_id))
        conn.commit()
    agent = _get_agent(agent_id)
    if not agent:
        raise KeyError(agent_id)
    return agent


def _delete_agent(agent_id: str) -> None:
    with sqlite3.connect(_db_path()) as conn:
        conn.execute("DELETE FROM agents WHERE id=?", (agent_id,))
        conn.commit()


def build_agents_router(ctx: ServerContext) -> APIRouter:
    _init_db()
    router = APIRouter(prefix="/api/agents")

    @router.get("")
    async def list_agents(_user_id: str = Depends(ctx.require_rate_limit)):
        return await asyncio.to_thread(_get_all_agents)

    @router.post("")
    async def create_agent(
        payload: dict,
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        name = str(payload.get("name", "")).strip()
        model = str(payload.get("model", "guppy")).strip()
        system_prompt = str(payload.get("system_prompt", "")).strip()
        tools = payload.get("tools", []) if isinstance(payload.get("tools"), list) else []
        color = str(payload.get("color", "bg-primary/10 text-primary")).strip()

        if not name:
            raise HTTPException(status_code=400, detail="name required")
        if not model:
            raise HTTPException(status_code=400, detail="model required")

        return await asyncio.to_thread(_create_agent, name, model, system_prompt, tools, color)

    @router.get("/{agent_id}")
    async def get_agent(agent_id: str, _user_id: str = Depends(ctx.require_rate_limit)):
        agent = await asyncio.to_thread(_get_agent, agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="agent not found")
        return agent

    @router.put("/{agent_id}")
    async def update_agent(
        agent_id: str,
        payload: dict,
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        # Builtin agents: allow system_prompt and color updates, but not model/name changes
        agent = await asyncio.to_thread(_get_agent, agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="agent not found")

        try:
            return await asyncio.to_thread(_update_agent, agent_id, payload)
        except KeyError:
            raise HTTPException(status_code=404, detail="agent not found")

    @router.delete("/{agent_id}")
    async def delete_agent(agent_id: str, _user_id: str = Depends(ctx.require_rate_limit)):
        agent = await asyncio.to_thread(_get_agent, agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="agent not found")
        if agent.get("builtin"):
            raise HTTPException(status_code=400, detail="built-in agents cannot be deleted")
        await asyncio.to_thread(_delete_agent, agent_id)
        return {"deleted": agent_id}

    return router
