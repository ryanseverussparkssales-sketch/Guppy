"""Workspace Tasks and Orchestration API.

Routes:
  POST /api/workspace/tasks             — create task
  GET  /api/workspace/tasks             — list with state filter
  GET  /api/workspace/tasks/{id}        — detail + step trace
  POST /api/workspace/tasks/{id}/run    — trigger orchestrator
  POST /api/workspace/tasks/{id}/confirm — user confirms blocked action
  POST /api/workspace/tasks/{id}/cancel  — cancel task
  GET  /api/workspace/tasks/{id}/stream — SSE: live output
  POST /api/workspace/events            — internal event bus

Task state machine: queued → planning → running → blocked → complete | failed
"""
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.guppy.api.server_context import ServerContext
from src.guppy.model_roles import resolve_role
from src.guppy.paths import USER_DATA_DIR

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Types
# ──────────────────────────────────────────────────────────────────────────────


class TaskState(str, Enum):
    """Task lifecycle states."""
    QUEUED = "queued"        # Accepted, waiting for execution
    PLANNING = "planning"    # Phi controller planning steps
    RUNNING = "running"      # Hermes4 executing steps
    BLOCKED = "blocked"      # Waiting for user confirmation on destructive action
    COMPLETE = "complete"    # Finished successfully
    FAILED = "failed"        # Error during execution
    CANCELLED = "cancelled"  # User cancelled


# ──────────────────────────────────────────────────────────────────────────────
# DB helpers
# ──────────────────────────────────────────────────────────────────────────────

_DB_PATH: str = ""

_WORKSPACE_SCHEMA = """
CREATE TABLE IF NOT EXISTS workspace_tasks (
    id                  TEXT PRIMARY KEY,
    task_description    TEXT NOT NULL,
    source              TEXT NOT NULL DEFAULT 'workspace',
    state               TEXT NOT NULL DEFAULT 'queued',
    created_at          TEXT NOT NULL,
    started_at          TEXT,
    completed_at        TEXT,
    result              TEXT,
    error               TEXT
);

CREATE TABLE IF NOT EXISTS workspace_task_steps (
    id                  TEXT PRIMARY KEY,
    task_id             TEXT NOT NULL,
    step_number         INTEGER NOT NULL,
    tool_name           TEXT NOT NULL,
    tool_args           TEXT NOT NULL,
    result              TEXT,
    requires_confirmation BOOLEAN DEFAULT 0,
    confirmation_given  BOOLEAN DEFAULT 0,
    created_at          TEXT NOT NULL,
    completed_at        TEXT,
    FOREIGN KEY (task_id) REFERENCES workspace_tasks(id) ON DELETE CASCADE
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
        conn.executescript(_WORKSPACE_SCHEMA)
        conn.commit()


# ──────────────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ──────────────────────────────────────────────────────────────────────────────


class CreateTaskRequest(BaseModel):
    task_description: str
    source: str = "workspace"  # workspace | conversations


class TaskStepResponse(BaseModel):
    id: str
    step_number: int
    tool_name: str
    tool_args: dict
    result: Optional[dict] = None
    requires_confirmation: bool = False
    confirmation_given: bool = False
    created_at: str
    completed_at: Optional[str] = None


class TaskDetailResponse(BaseModel):
    id: str
    task_description: str
    source: str
    state: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    steps: list[TaskStepResponse] = []


class TaskListItemResponse(BaseModel):
    id: str
    task_description: str
    source: str
    state: str
    created_at: str
    completed_at: Optional[str] = None


# ──────────────────────────────────────────────────────────────────────────────
# Tool executor (stub — full implementation in Tranche F)
# ──────────────────────────────────────────────────────────────────────────────


async def _execute_workspace_tool(tool_name: str, tool_args: dict) -> dict:
    """Execute one workspace tool. Returns a result dict.

    Whitelist: web_search, file_read, file_list, shell_run, contacts_search,
    calendar_read, email_read, screenpipe_search, pc_screenshot, pc_click,
    pc_type, pc_scroll.
    """
    # Stub implementations — Tranche F will add full logic

    if tool_name == "web_search":
        query = str(tool_args.get("query", "")).strip()
        return {"ok": True, "query": query, "results": []}

    elif tool_name == "file_read":
        path = str(tool_args.get("path", "")).strip()
        return {"ok": True, "path": path, "content": "(file read stub)"}

    elif tool_name == "file_list":
        path = str(tool_args.get("path", "")).strip()
        return {"ok": True, "path": path, "files": []}

    elif tool_name == "shell_run":
        command = str(tool_args.get("command", "")).strip()
        is_mutating = "delete" in command.lower() or "rm" in command.lower()
        if is_mutating:
            # Requires confirmation for destructive commands
            return {
                "ok": False,
                "requires_confirmation": True,
                "command": command,
                "note": "Destructive command — requires user confirmation",
            }
        return {"ok": True, "command": command, "stdout": "(output stub)"}

    elif tool_name == "contacts_search":
        query = str(tool_args.get("query", "")).strip()
        return {"ok": True, "query": query, "contacts": []}

    elif tool_name == "calendar_read":
        days = int(tool_args.get("days", 7))
        return {"ok": True, "days": days, "events": []}

    elif tool_name == "email_read":
        limit = int(tool_args.get("limit", 10))
        return {"ok": True, "limit": limit, "messages": []}

    elif tool_name == "screenpipe_search":
        query = str(tool_args.get("query", "")).strip()
        # Legacy workspace endpoint remains a lightweight passthrough.
        # Full task executor tool logic lives in routes_realtime.py.
        return {"ok": True, "query": query, "results": []}

    elif tool_name == "pc_screenshot":
        return {"ok": True, "image_url": "data:image/png;base64,(stub)"}

    elif tool_name == "pc_click":
        x = int(tool_args.get("x", 0))
        y = int(tool_args.get("y", 0))
        return {"ok": True, "x": x, "y": y}

    elif tool_name == "pc_type":
        text = str(tool_args.get("text", "")).strip()
        return {"ok": True, "text": text}

    elif tool_name == "pc_scroll":
        direction = str(tool_args.get("direction", "down")).strip()
        return {"ok": True, "direction": direction}

    else:
        return {"ok": False, "error": f"Unknown tool: {tool_name}"}


# ──────────────────────────────────────────────────────────────────────────────
# Router
# ──────────────────────────────────────────────────────────────────────────────


def build_workspace_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/workspace", tags=["workspace"])

    _ensure_schema()

    # ──────────────────────────────────────────────────────────────────────────
    # Task CRUD
    # ──────────────────────────────────────────────────────────────────────────

    @router.post("/tasks", response_model=TaskDetailResponse, status_code=201)
    async def create_task(req: CreateTaskRequest) -> TaskDetailResponse:
        """Create a new workspace task."""
        task_id = str(uuid.uuid4())
        now = _now()

        with _db() as conn:
            conn.execute(
                """INSERT INTO workspace_tasks
                   (id, task_description, source, state, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (task_id, req.task_description, req.source, TaskState.QUEUED.value, now),
            )
            conn.commit()

        return TaskDetailResponse(
            id=task_id,
            task_description=req.task_description,
            source=req.source,
            state=TaskState.QUEUED.value,
            created_at=now,
            steps=[],
        )

    @router.get("/tasks", response_model=list[TaskListItemResponse])
    async def list_tasks(state: Optional[str] = None) -> list[TaskListItemResponse]:
        """List workspace tasks, optionally filtered by state."""
        with _db() as conn:
            if state:
                rows = conn.execute(
                    """SELECT id, task_description, source, state, created_at, completed_at
                       FROM workspace_tasks WHERE state = ? ORDER BY created_at DESC""",
                    (state,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT id, task_description, source, state, created_at, completed_at
                       FROM workspace_tasks ORDER BY created_at DESC"""
                ).fetchall()

            return [
                TaskListItemResponse(
                    id=row["id"],
                    task_description=row["task_description"],
                    source=row["source"],
                    state=row["state"],
                    created_at=row["created_at"],
                    completed_at=row["completed_at"],
                )
                for row in rows
            ]

    @router.get("/tasks/{task_id}", response_model=TaskDetailResponse)
    async def get_task(task_id: str) -> TaskDetailResponse:
        """Get task detail + step trace."""
        with _db() as conn:
            task_row = conn.execute(
                """SELECT id, task_description, source, state, created_at, started_at,
                         completed_at, result, error
                   FROM workspace_tasks WHERE id = ?""",
                (task_id,),
            ).fetchone()

            if not task_row:
                raise HTTPException(status_code=404, detail="Task not found")

            step_rows = conn.execute(
                """SELECT id, step_number, tool_name, tool_args, result,
                         requires_confirmation, confirmation_given, created_at, completed_at
                   FROM workspace_task_steps WHERE task_id = ? ORDER BY step_number ASC""",
                (task_id,),
            ).fetchall()

            steps = [
                TaskStepResponse(
                    id=row["id"],
                    step_number=row["step_number"],
                    tool_name=row["tool_name"],
                    tool_args=json.loads(row["tool_args"]),
                    result=json.loads(row["result"]) if row["result"] else None,
                    requires_confirmation=bool(row["requires_confirmation"]),
                    confirmation_given=bool(row["confirmation_given"]),
                    created_at=row["created_at"],
                    completed_at=row["completed_at"],
                )
                for row in step_rows
            ]

            return TaskDetailResponse(
                id=task_row["id"],
                task_description=task_row["task_description"],
                source=task_row["source"],
                state=task_row["state"],
                created_at=task_row["created_at"],
                started_at=task_row["started_at"],
                completed_at=task_row["completed_at"],
                result=task_row["result"],
                error=task_row["error"],
                steps=steps,
            )

    # ──────────────────────────────────────────────────────────────────────────
    # Task lifecycle
    # ──────────────────────────────────────────────────────────────────────────

    @router.post("/tasks/{task_id}/run")
    async def run_task(task_id: str) -> dict:
        """Trigger orchestrator for a task. Stub — full implementation in Tranche F."""
        with _db() as conn:
            task = conn.execute(
                "SELECT state FROM workspace_tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")

            # Transition: queued → planning
            conn.execute(
                "UPDATE workspace_tasks SET state = ?, started_at = ? WHERE id = ?",
                (TaskState.PLANNING.value, _now(), task_id),
            )
            conn.commit()

        return {"ok": True, "task_id": task_id, "state": TaskState.PLANNING.value}

    @router.post("/tasks/{task_id}/confirm")
    async def confirm_task_action(task_id: str, step_id: str) -> dict:
        """User confirms a blocked (destructive) action. Stub."""
        with _db() as conn:
            step = conn.execute(
                "SELECT task_id FROM workspace_task_steps WHERE id = ?", (step_id,)
            ).fetchone()
            if not step or step["task_id"] != task_id:
                raise HTTPException(status_code=404, detail="Step not found")

            conn.execute(
                "UPDATE workspace_task_steps SET confirmation_given = 1 WHERE id = ?",
                (step_id,),
            )
            conn.commit()

        return {"ok": True, "step_id": step_id, "confirmed": True}

    @router.post("/tasks/{task_id}/cancel")
    async def cancel_task(task_id: str) -> dict:
        """Cancel a task."""
        with _db() as conn:
            conn.execute(
                "UPDATE workspace_tasks SET state = ?, completed_at = ? WHERE id = ?",
                (TaskState.CANCELLED.value, _now(), task_id),
            )
            conn.commit()

        return {"ok": True, "task_id": task_id, "state": TaskState.CANCELLED.value}

    # ──────────────────────────────────────────────────────────────────────────
    # Streaming
    # ──────────────────────────────────────────────────────────────────────────

    @router.get("/tasks/{task_id}/stream")
    async def stream_task(task_id: str):
        """Stream live task output via SSE.

        Emits state and step updates until the task reaches a terminal state.
        """

        terminal_states = {
            TaskState.COMPLETE.value,
            TaskState.FAILED.value,
            TaskState.CANCELLED.value,
        }

        async def _stream():
            last_state = None
            last_step_count = -1

            with _db() as conn:
                task = conn.execute(
                    "SELECT state FROM workspace_tasks WHERE id = ?", (task_id,)
                ).fetchone()
                if not task:
                    yield f"data: {json.dumps({'error': 'Task not found'})}\n\n"
                    return

            while True:
                with _db() as conn:
                    task = conn.execute(
                        "SELECT state, error, result FROM workspace_tasks WHERE id = ?",
                        (task_id,),
                    ).fetchone()

                    if not task:
                        yield f"data: {json.dumps({'error': 'Task not found'})}\n\n"
                        return

                    steps = conn.execute(
                        """SELECT step_number, tool_name, result, requires_confirmation,
                                  confirmation_given, completed_at
                           FROM workspace_task_steps
                           WHERE task_id = ? ORDER BY step_number ASC""",
                        (task_id,),
                    ).fetchall()

                state = task["state"]
                if state != last_state:
                    payload = {
                        "event": "state",
                        "task_id": task_id,
                        "state": state,
                        "error": task["error"],
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
                    last_state = state

                if len(steps) != last_step_count:
                    serialized_steps = []
                    for row in steps:
                        serialized_steps.append(
                            {
                                "step_number": row["step_number"],
                                "tool_name": row["tool_name"],
                                "result": json.loads(row["result"]) if row["result"] else None,
                                "requires_confirmation": bool(row["requires_confirmation"]),
                                "confirmation_given": bool(row["confirmation_given"]),
                                "completed_at": row["completed_at"],
                            }
                        )

                    payload = {
                        "event": "steps",
                        "task_id": task_id,
                        "steps": serialized_steps,
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
                    last_step_count = len(steps)

                if state in terminal_states:
                    done_payload = {
                        "event": "done",
                        "task_id": task_id,
                        "state": state,
                        "result": task["result"],
                        "error": task["error"],
                    }
                    yield f"data: {json.dumps(done_payload)}\n\n"
                    yield "data: [DONE]\n\n"
                    return

                await asyncio.sleep(1)

        return StreamingResponse(_stream(), media_type="text/event-stream")

    # ──────────────────────────────────────────────────────────────────────────
    # Internal event bus (for cross-surface communication)
    # ──────────────────────────────────────────────────────────────────────────

    @router.post("/events")
    async def post_event(event: dict) -> dict:
        """Post an internal workspace event (task_spawned, task_progress, etc.)."""
        # Stub — SSE broadcast logic in Tranche F
        return {"ok": True, "event": event}

    return router
