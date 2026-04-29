"""Task Manager API — rich task board with priority, project, and status workflow.

This is the UI-first task board (TaskManagerPanel). It is separate from the
lighter /api/workspace/tasks endpoint which tracks agent-originated CRM tasks.

Schema: id, title, description, status (todo|inprogress|done),
         priority (low|medium|high|urgent), project, due_date, created_at, updated_at.

GET    /api/tasks              — list tasks (optional status/priority/project filter)
POST   /api/tasks              — create task
PATCH  /api/tasks/{id}         — update any fields
DELETE /api/tasks/{id}         — delete task
"""
from __future__ import annotations

import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.guppy.api.server_context import ServerContext

logger = logging.getLogger(__name__)

_DB_PATH = "runtime/tasks.db"


# ── DB ─────────────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    os.makedirs("runtime", exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id          TEXT PRIMARY KEY,
            title       TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status      TEXT NOT NULL DEFAULT 'todo',
            priority    TEXT NOT NULL DEFAULT 'medium',
            project     TEXT NOT NULL DEFAULT '',
            due_date    TEXT NOT NULL DEFAULT '',
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def _row(r: sqlite3.Row) -> dict[str, Any]:
    return {
        "id":          r["id"],
        "title":       r["title"],
        "description": r["description"],
        "status":      r["status"],
        "priority":    r["priority"],
        "project":     r["project"],
        "due_date":    r["due_date"],
        "created_at":  r["created_at"],
        "updated_at":  r["updated_at"],
    }


# ── Pydantic ───────────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    title:       str
    description: str = ""
    status:      str = "todo"    # todo | doing | done
    priority:    str = "medium"  # low | medium | high | urgent
    project:     str = ""
    due_date:    str = ""        # ISO date string, e.g. "2026-05-01"


class TaskUpdate(BaseModel):
    title:       Optional[str] = None
    description: Optional[str] = None
    status:      Optional[str] = None
    priority:    Optional[str] = None
    project:     Optional[str] = None
    due_date:    Optional[str] = None


# ── Router ─────────────────────────────────────────────────────────────────────

def build_tasks_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/tasks", tags=["tasks"])

    @router.get("")
    def list_tasks(
        status:   str = "",
        priority: str = "",
        project:  str = "",
        limit:    int = 200,
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        clauses: list[str] = []
        params:  list[Any] = []
        if status:
            clauses.append("status=?");   params.append(status)
        if priority:
            clauses.append("priority=?"); params.append(priority)
        if project:
            clauses.append("project=?");  params.append(project)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with _conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM tasks {where} ORDER BY created_at DESC LIMIT ?",
                params + [min(limit, 500)],
            ).fetchall()
        return [_row(r) for r in rows]

    @router.post("")
    def create_task(body: TaskCreate, _uid: str = Depends(ctx.require_rate_limit)):
        valid_statuses  = {"todo", "doing", "done"}
        valid_priorities = {"low", "medium", "high", "urgent"}
        if body.status not in valid_statuses:
            raise HTTPException(400, f"status must be one of {sorted(valid_statuses)}")
        if body.priority not in valid_priorities:
            raise HTTPException(400, f"priority must be one of {sorted(valid_priorities)}")
        tid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with _conn() as conn:
            conn.execute(
                "INSERT INTO tasks (id, title, description, status, priority, project, due_date, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (tid, body.title.strip(), body.description, body.status,
                 body.priority, body.project, body.due_date, now, now),
            )
            conn.commit()
        return {"ok": True, "id": tid}

    @router.patch("/{task_id}")
    def update_task(task_id: str, body: TaskUpdate, _uid: str = Depends(ctx.require_rate_limit)):
        updates: dict[str, Any] = {}
        if body.title       is not None: updates["title"]       = body.title.strip()
        if body.description is not None: updates["description"] = body.description
        if body.status      is not None: updates["status"]      = body.status
        if body.priority    is not None: updates["priority"]    = body.priority
        if body.project     is not None: updates["project"]     = body.project
        if body.due_date    is not None: updates["due_date"]    = body.due_date
        if not updates:
            raise HTTPException(400, "Nothing to update")
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [task_id]
        with _conn() as conn:
            cur = conn.execute(f"UPDATE tasks SET {set_clause} WHERE id=?", values)
            conn.commit()
            if cur.rowcount == 0:
                raise HTTPException(404, "Task not found")
        return {"ok": True}

    @router.delete("/{task_id}")
    def delete_task(task_id: str, _uid: str = Depends(ctx.require_rate_limit)):
        with _conn() as conn:
            conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
            conn.commit()
        return {"ok": True}

    return router
