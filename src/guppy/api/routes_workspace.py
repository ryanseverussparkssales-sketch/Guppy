"""Workspace task orchestration API.

Routes:
  POST /api/workspace/tasks              create task
  GET  /api/workspace/tasks              list tasks with optional state filter
  GET  /api/workspace/tasks/{id}         detail with steps and events
  POST /api/workspace/tasks/{id}/run     run the workspace orchestrator
  POST /api/workspace/tasks/{id}/confirm confirm a blocked step
  POST /api/workspace/tasks/{id}/cancel  cancel task
  GET  /api/workspace/tasks/{id}/stream  SSE updates
  POST /api/workspace/events             persist internal workspace event
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.guppy.api.server_context import ServerContext
from src.guppy.api.workspace_tools import execute_workspace_tool, planned_steps
from src.guppy.paths import MAIN_DB_PATH


class TaskState(str, Enum):
    """Task lifecycle states."""

    QUEUED = "queued"
    PLANNING = "planning"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATES = {
    TaskState.COMPLETE.value,
    TaskState.FAILED.value,
    TaskState.CANCELLED.value,
}

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
    requires_confirmation INTEGER NOT NULL DEFAULT 0,
    confirmation_given  INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL,
    completed_at        TEXT,
    FOREIGN KEY (task_id) REFERENCES workspace_tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS workspace_task_events (
    id                  TEXT PRIMARY KEY,
    task_id             TEXT,
    event_type          TEXT NOT NULL,
    payload             TEXT NOT NULL,
    created_at          TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES workspace_tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_workspace_tasks_state_created
    ON workspace_tasks(state, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_workspace_task_steps_task
    ON workspace_task_steps(task_id, step_number ASC);
CREATE INDEX IF NOT EXISTS idx_workspace_task_events_task
    ON workspace_task_events(task_id, created_at ASC);
"""


def _db() -> sqlite3.Connection:
    path = _DB_PATH or str(MAIN_DB_PATH)
    Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
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


class CreateTaskRequest(BaseModel):
    task_description: str
    source: str = "workspace"


class ConfirmTaskRequest(BaseModel):
    step_id: str


class TaskStepResponse(BaseModel):
    id: str
    step_number: int
    tool_name: str
    tool_args: dict[str, Any]
    result: dict[str, Any] | None = None
    requires_confirmation: bool = False
    confirmation_given: bool = False
    created_at: str
    completed_at: str | None = None


class TaskEventResponse(BaseModel):
    id: str
    task_id: str | None = None
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class TaskDetailResponse(BaseModel):
    id: str
    task_description: str
    source: str
    state: str
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    result: str | None = None
    error: str | None = None
    steps: list[TaskStepResponse] = Field(default_factory=list)
    events: list[TaskEventResponse] = Field(default_factory=list)


class TaskListItemResponse(BaseModel):
    id: str
    task_description: str
    source: str
    state: str
    created_at: str
    completed_at: str | None = None


def _json_dict(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {"raw": value}
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def _emit_event(
    conn: sqlite3.Connection,
    task_id: str | None,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> TaskEventResponse:
    event_id = str(uuid.uuid4())
    created_at = _now()
    safe_payload = payload or {}
    conn.execute(
        """INSERT INTO workspace_task_events
           (id, task_id, event_type, payload, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (event_id, task_id, event_type, json.dumps(safe_payload, ensure_ascii=True), created_at),
    )
    return TaskEventResponse(
        id=event_id,
        task_id=task_id,
        event_type=event_type,
        payload=safe_payload,
        created_at=created_at,
    )


def _task_steps(conn: sqlite3.Connection, task_id: str) -> list[TaskStepResponse]:
    rows = conn.execute(
        """SELECT id, step_number, tool_name, tool_args, result,
                  requires_confirmation, confirmation_given, created_at, completed_at
           FROM workspace_task_steps
           WHERE task_id = ?
           ORDER BY step_number ASC""",
        (task_id,),
    ).fetchall()
    return [
        TaskStepResponse(
            id=row["id"],
            step_number=row["step_number"],
            tool_name=row["tool_name"],
            tool_args=_json_dict(row["tool_args"]) or {},
            result=_json_dict(row["result"]),
            requires_confirmation=bool(row["requires_confirmation"]),
            confirmation_given=bool(row["confirmation_given"]),
            created_at=row["created_at"],
            completed_at=row["completed_at"],
        )
        for row in rows
    ]


def _task_events(conn: sqlite3.Connection, task_id: str) -> list[TaskEventResponse]:
    rows = conn.execute(
        """SELECT id, task_id, event_type, payload, created_at
           FROM workspace_task_events
           WHERE task_id = ?
           ORDER BY created_at ASC""",
        (task_id,),
    ).fetchall()
    return [
        TaskEventResponse(
            id=row["id"],
            task_id=row["task_id"],
            event_type=row["event_type"],
            payload=_json_dict(row["payload"]) or {},
            created_at=row["created_at"],
        )
        for row in rows
    ]


def _detail_from_row(conn: sqlite3.Connection, row: sqlite3.Row) -> TaskDetailResponse:
    return TaskDetailResponse(
        id=row["id"],
        task_description=row["task_description"],
        source=row["source"],
        state=row["state"],
        created_at=row["created_at"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        result=row["result"],
        error=row["error"],
        steps=_task_steps(conn, row["id"]),
        events=_task_events(conn, row["id"]),
    )


def _task_row(conn: sqlite3.Connection, task_id: str) -> sqlite3.Row:
    row = conn.execute(
        """SELECT id, task_description, source, state, created_at, started_at,
                  completed_at, result, error
           FROM workspace_tasks
           WHERE id = ?""",
        (task_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    return row


def create_workspace_task_record(req: CreateTaskRequest) -> TaskDetailResponse:
    _ensure_schema()
    description = req.task_description.strip()
    if not description:
        raise HTTPException(status_code=422, detail="task_description is required")

    task_id = str(uuid.uuid4())
    now = _now()
    source = req.source.strip() or "workspace"
    with _db() as conn:
        conn.execute(
            """INSERT INTO workspace_tasks
               (id, task_description, source, state, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (task_id, description, source, TaskState.QUEUED.value, now),
        )
        _emit_event(conn, task_id, "created", {"state": TaskState.QUEUED.value, "source": source})
        conn.commit()
        return _detail_from_row(conn, _task_row(conn, task_id))


def list_workspace_task_records(state: str | None = None) -> list[TaskListItemResponse]:
    _ensure_schema()
    if state and state not in {item.value for item in TaskState}:
        raise HTTPException(status_code=400, detail=f"Unknown workspace task state: {state}")

    with _db() as conn:
        if state:
            rows = conn.execute(
                """SELECT id, task_description, source, state, created_at, completed_at
                   FROM workspace_tasks
                   WHERE state = ?
                   ORDER BY created_at DESC""",
                (state,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT id, task_description, source, state, created_at, completed_at
                   FROM workspace_tasks
                   ORDER BY created_at DESC"""
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


def _list_crm_task_records(status: str) -> list[dict[str, Any]]:
    from src.guppy.api.routes_workspace_data import list_crm_task_records

    return list_crm_task_records(status=status)


def _create_crm_task_record(body: dict[str, Any]) -> dict[str, Any]:
    from src.guppy.api.routes_workspace_data import TaskCreate, create_crm_task_record

    task = str(body.get("task") or "").strip()
    if not task:
        raise HTTPException(status_code=422, detail="task_description or task is required")
    return create_crm_task_record(
        TaskCreate(
            task=task,
            due_date=str(body.get("due_date") or ""),
        )
    )


def get_workspace_task_record(task_id: str) -> TaskDetailResponse:
    _ensure_schema()
    with _db() as conn:
        return _detail_from_row(conn, _task_row(conn, task_id))


def _insert_step(
    conn: sqlite3.Connection,
    task_id: str,
    step_number: int,
    tool_name: str,
    tool_args: dict[str, Any],
) -> str:
    step_id = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO workspace_task_steps
           (id, task_id, step_number, tool_name, tool_args, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            step_id,
            task_id,
            step_number,
            tool_name,
            json.dumps(tool_args, ensure_ascii=True),
            _now(),
        ),
    )
    return step_id


async def run_workspace_task_record(task_id: str) -> dict[str, Any]:
    _ensure_schema()
    with _db() as conn:
        task = _task_row(conn, task_id)
        current_state = task["state"]
        if current_state in {TaskState.PLANNING.value, TaskState.RUNNING.value, TaskState.BLOCKED.value}:
            return {"ok": True, "task_id": task_id, "state": current_state}
        if current_state in TERMINAL_STATES:
            raise HTTPException(status_code=409, detail=f"Task is already {current_state}")

        started_at = task["started_at"] or _now()
        conn.execute(
            "UPDATE workspace_tasks SET state = ?, started_at = ? WHERE id = ?",
            (TaskState.PLANNING.value, started_at, task_id),
        )
        _emit_event(conn, task_id, "state_changed", {"state": TaskState.PLANNING.value})
        conn.commit()

        conn.execute(
            "UPDATE workspace_tasks SET state = ? WHERE id = ?",
            (TaskState.RUNNING.value, task_id),
        )
        _emit_event(conn, task_id, "state_changed", {"state": TaskState.RUNNING.value})
        conn.commit()

        for step_number, (tool_name, tool_args) in enumerate(
            planned_steps(task["task_description"]),
            start=1,
        ):
            step_id = _insert_step(conn, task_id, step_number, tool_name, tool_args)
            _emit_event(
                conn,
                task_id,
                "step_started",
                {"step_id": step_id, "step_number": step_number, "tool_name": tool_name},
            )
            conn.commit()

            result = await execute_workspace_tool(tool_name, tool_args)
            now = _now()

            if result.get("requires_confirmation"):
                conn.execute(
                    """UPDATE workspace_task_steps
                       SET result = ?, requires_confirmation = 1
                       WHERE id = ?""",
                    (json.dumps(result, ensure_ascii=True), step_id),
                )
                conn.execute(
                    "UPDATE workspace_tasks SET state = ? WHERE id = ?",
                    (TaskState.BLOCKED.value, task_id),
                )
                _emit_event(
                    conn,
                    task_id,
                    "step_blocked",
                    {"step_id": step_id, "step_number": step_number, "tool_name": tool_name},
                )
                _emit_event(conn, task_id, "state_changed", {"state": TaskState.BLOCKED.value})
                conn.commit()
                return {"ok": True, "task_id": task_id, "state": TaskState.BLOCKED.value}

            conn.execute(
                """UPDATE workspace_task_steps
                   SET result = ?, completed_at = ?
                   WHERE id = ?""",
                (json.dumps(result, ensure_ascii=True), now, step_id),
            )
            _emit_event(
                conn,
                task_id,
                "step_completed",
                {"step_id": step_id, "step_number": step_number, "tool_name": tool_name},
            )
            conn.commit()

            if not result.get("ok", False):
                error = str(result.get("error") or f"{tool_name} failed")
                conn.execute(
                    """UPDATE workspace_tasks
                       SET state = ?, error = ?, completed_at = ?
                       WHERE id = ?""",
                    (TaskState.FAILED.value, error, _now(), task_id),
                )
                _emit_event(conn, task_id, "state_changed", {"state": TaskState.FAILED.value})
                conn.commit()
                return {
                    "ok": False,
                    "task_id": task_id,
                    "state": TaskState.FAILED.value,
                    "error": error,
                }

        result_text = "Workspace task run complete."
        conn.execute(
            """UPDATE workspace_tasks
               SET state = ?, completed_at = ?, result = ?
               WHERE id = ?""",
            (TaskState.COMPLETE.value, _now(), result_text, task_id),
        )
        _emit_event(conn, task_id, "state_changed", {"state": TaskState.COMPLETE.value})
        conn.commit()
        return {"ok": True, "task_id": task_id, "state": TaskState.COMPLETE.value}


def confirm_workspace_task_record(task_id: str, step_id: str) -> dict[str, Any]:
    _ensure_schema()
    with _db() as conn:
        _task_row(conn, task_id)
        step = conn.execute(
            """SELECT id, task_id, result, requires_confirmation
               FROM workspace_task_steps
               WHERE id = ?""",
            (step_id,),
        ).fetchone()
        if not step or step["task_id"] != task_id:
            raise HTTPException(status_code=404, detail="Step not found")

        result = _json_dict(step["result"]) or {}
        result["confirmed"] = True
        result["note"] = "Confirmed by user; workspace task marked complete."
        now = _now()
        conn.execute(
            """UPDATE workspace_task_steps
               SET confirmation_given = 1, result = ?, completed_at = COALESCE(completed_at, ?)
               WHERE id = ?""",
            (json.dumps(result, ensure_ascii=True), now, step_id),
        )
        conn.execute(
            """UPDATE workspace_tasks
               SET state = ?, completed_at = ?, result = ?
               WHERE id = ?""",
            (
                TaskState.COMPLETE.value,
                now,
                "Confirmed action recorded; workspace task complete.",
                task_id,
            ),
        )
        _emit_event(conn, task_id, "step_confirmed", {"step_id": step_id})
        _emit_event(conn, task_id, "state_changed", {"state": TaskState.COMPLETE.value})
        conn.commit()
        return {
            "ok": True,
            "task_id": task_id,
            "step_id": step_id,
            "confirmed": True,
            "state": TaskState.COMPLETE.value,
        }


def cancel_workspace_task_record(task_id: str) -> dict[str, Any]:
    _ensure_schema()
    with _db() as conn:
        _task_row(conn, task_id)
        now = _now()
        conn.execute(
            "UPDATE workspace_tasks SET state = ?, completed_at = ? WHERE id = ?",
            (TaskState.CANCELLED.value, now, task_id),
        )
        _emit_event(conn, task_id, "state_changed", {"state": TaskState.CANCELLED.value})
        conn.commit()
        return {"ok": True, "task_id": task_id, "state": TaskState.CANCELLED.value}


def build_workspace_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/workspace", tags=["workspace"])
    _ensure_schema()

    @router.post("/tasks")
    async def create_task(
        body: dict[str, Any],
        response: Response,
        _uid: str = Depends(ctx.require_rate_limit),
    ) -> Any:
        if "task_description" not in body:
            return _create_crm_task_record(body)

        detail = create_workspace_task_record(
            CreateTaskRequest(
                task_description=str(body.get("task_description") or ""),
                source=str(body.get("source") or "workspace"),
            )
        )
        response.status_code = 201
        return detail

    @router.get("/tasks")
    async def list_tasks(
        state: str | None = None,
        status: str | None = None,
        _uid: str = Depends(ctx.require_rate_limit),
    ) -> Any:
        if status is not None and state is None:
            return _list_crm_task_records(status=status)
        return list_workspace_task_records(state=state)

    @router.get("/tasks/{task_id}", response_model=TaskDetailResponse)
    async def get_task(
        task_id: str,
        _uid: str = Depends(ctx.require_rate_limit),
    ) -> TaskDetailResponse:
        return get_workspace_task_record(task_id)

    @router.post("/tasks/{task_id}/run")
    async def run_task(
        task_id: str,
        _uid: str = Depends(ctx.require_rate_limit),
    ) -> dict[str, Any]:
        return await run_workspace_task_record(task_id)

    @router.post("/tasks/{task_id}/confirm")
    async def confirm_task_action(
        task_id: str,
        req: ConfirmTaskRequest,
        _uid: str = Depends(ctx.require_rate_limit),
    ) -> dict[str, Any]:
        return confirm_workspace_task_record(task_id, req.step_id)

    @router.post("/tasks/{task_id}/cancel")
    async def cancel_task(
        task_id: str,
        _uid: str = Depends(ctx.require_rate_limit),
    ) -> dict[str, Any]:
        return cancel_workspace_task_record(task_id)

    @router.get("/tasks/{task_id}/stream")
    async def stream_task(
        task_id: str,
        _uid: str = Depends(ctx.require_rate_limit),
    ) -> StreamingResponse:
        async def _stream():
            last_state: str | None = None
            last_step_count = -1
            last_event_count = -1

            with _db() as conn:
                _task_row(conn, task_id)

            while True:
                with _db() as conn:
                    task = _task_row(conn, task_id)
                    steps = _task_steps(conn, task_id)
                    events = _task_events(conn, task_id)

                state = task["state"]
                if state != last_state:
                    yield "data: " + json.dumps(
                        {
                            "event": "state",
                            "task_id": task_id,
                            "state": state,
                            "error": task["error"],
                        }
                    ) + "\n\n"
                    last_state = state

                if len(steps) != last_step_count:
                    yield "data: " + json.dumps(
                        {
                            "event": "steps",
                            "task_id": task_id,
                            "steps": [step.model_dump() for step in steps],
                        }
                    ) + "\n\n"
                    last_step_count = len(steps)

                if len(events) != last_event_count:
                    yield "data: " + json.dumps(
                        {
                            "event": "events",
                            "task_id": task_id,
                            "events": [event.model_dump() for event in events],
                        }
                    ) + "\n\n"
                    last_event_count = len(events)

                if state in TERMINAL_STATES:
                    yield "data: " + json.dumps(
                        {
                            "event": "done",
                            "task_id": task_id,
                            "state": state,
                            "result": task["result"],
                            "error": task["error"],
                        }
                    ) + "\n\n"
                    yield "data: [DONE]\n\n"
                    return

                await asyncio.sleep(1)

        return StreamingResponse(_stream(), media_type="text/event-stream")

    @router.post("/events")
    async def post_event(
        event: dict[str, Any],
        _uid: str = Depends(ctx.require_rate_limit),
    ) -> dict[str, Any]:
        _ensure_schema()
        event_type = str(event.get("event") or event.get("type") or "workspace_event")
        raw_task_id = event.get("task_id")
        task_id = str(raw_task_id) if raw_task_id else None
        with _db() as conn:
            stored = _emit_event(conn, task_id, event_type, event)
            conn.commit()
        return {"ok": True, "event": stored.model_dump()}

    return router
