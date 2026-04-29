"""Workspace data API — structured JSON access to memory module CRM data.

GET  /api/workspace/contacts         — list contacts
POST /api/workspace/contacts         — add/update contact
GET  /api/workspace/tasks            — list tasks (by status)
POST /api/workspace/tasks            — add task
PUT  /api/workspace/tasks/{id}/complete — mark task complete
GET  /api/workspace/pipeline/history — recent pipeline runs
GET  /api/workspace/pipeline/templates — available pipeline templates
"""
from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.guppy.api.server_context import ServerContext
from src.guppy.paths import MEMORY_DB_PATH


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _mem_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(MEMORY_DB_PATH), check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _contacts_json(search: str = "") -> list[dict[str, Any]]:
    with _mem_conn() as conn:
        if search:
            rows = conn.execute(
                "SELECT * FROM contacts WHERE name LIKE ? OR company LIKE ? OR email LIKE ? ORDER BY last_contact DESC",
                (f"%{search}%", f"%{search}%", f"%{search}%"),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM contacts ORDER BY last_contact DESC LIMIT 200"
            ).fetchall()
    return [dict(r) for r in rows]


def _tasks_json(status: str = "pending") -> list[dict[str, Any]]:
    with _mem_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE status=? ORDER BY created DESC LIMIT 200",
            (status,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Pydantic ───────────────────────────────────────────────────────────────────

class ContactCreate(BaseModel):
    name:    str
    company: str = ""
    email:   str = ""
    phone:   str = ""
    notes:   str = ""


class TaskCreate(BaseModel):
    task:     str
    due_date: str = ""


# ── Router ─────────────────────────────────────────────────────────────────────

def build_workspace_data_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/workspace", tags=["workspace-data"])

    # ── Contacts ───────────────────────────────────────────────────────────────

    @router.get("/contacts")
    def list_contacts(
        q: str = "",
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        try:
            return _contacts_json(search=q)
        except Exception as e:
            raise HTTPException(500, f"Could not read contacts: {e}")

    @router.post("/contacts")
    def upsert_contact(
        body: ContactCreate,
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        try:
            from src.guppy.memory import memory_store
            result = memory_store.upsert_contact(
                MEMORY_DB_PATH,
                name=body.name,
                company=body.company,
                email=body.email,
                phone=body.phone,
                notes=body.notes,
            )
            return {"ok": True, "message": result}
        except Exception as e:
            raise HTTPException(500, f"Could not save contact: {e}")

    @router.delete("/contacts/{name}")
    def delete_contact(name: str, _uid: str = Depends(ctx.require_rate_limit)):
        try:
            with _mem_conn() as conn:
                conn.execute("DELETE FROM contacts WHERE name = ?", (name,))
                conn.commit()
            return {"ok": True}
        except Exception as e:
            raise HTTPException(500, f"Could not delete contact: {e}")

    # ── Tasks ──────────────────────────────────────────────────────────────────

    @router.get("/tasks")
    def list_tasks(
        status: str = "pending",
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        try:
            return _tasks_json(status=status)
        except Exception as e:
            raise HTTPException(500, f"Could not read tasks: {e}")

    @router.post("/tasks")
    def add_task(
        body: TaskCreate,
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        try:
            from src.guppy.memory import memory_store
            result = memory_store.add_task_record(
                MEMORY_DB_PATH,
                task=body.task,
                due_date=body.due_date,
            )
            return {"ok": True, "message": result}
        except Exception as e:
            raise HTTPException(500, f"Could not add task: {e}")

    @router.put("/tasks/{task_id}/complete")
    def complete_task(task_id: int, _uid: str = Depends(ctx.require_rate_limit)):
        try:
            from src.guppy.memory import memory_store
            result = memory_store.complete_task_record(MEMORY_DB_PATH, task_id)
            return {"ok": True, "message": result}
        except Exception as e:
            raise HTTPException(500, f"Could not complete task: {e}")

    @router.delete("/tasks/{task_id}")
    def delete_task(task_id: int, _uid: str = Depends(ctx.require_rate_limit)):
        try:
            with _mem_conn() as conn:
                conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                conn.commit()
            return {"ok": True}
        except Exception as e:
            raise HTTPException(500, f"Could not delete task: {e}")

    # ── Pipeline pass-through ──────────────────────────────────────────────────

    @router.get("/pipeline/history")
    async def pipeline_history(_uid: str = Depends(ctx.require_rate_limit)):
        """Proxy to /api/pipeline/history for workspace panel convenience."""
        try:
            import httpx, os
            port = int(os.environ.get("GUPPY_API_PORT", "8081"))
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"http://127.0.0.1:{port}/api/pipeline/history?limit=20",
                    headers={"Authorization": f"Bearer {_uid}"},
                )
                return resp.json()
        except Exception:
            return []

    @router.get("/pipeline/templates")
    async def pipeline_templates(_uid: str = Depends(ctx.require_rate_limit)):
        try:
            import httpx, os
            port = int(os.environ.get("GUPPY_API_PORT", "8081"))
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"http://127.0.0.1:{port}/api/pipeline/templates",
                    headers={"Authorization": f"Bearer {_uid}"},
                )
                return resp.json()
        except Exception:
            return []

    return router
