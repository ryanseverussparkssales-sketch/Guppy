"""Surface coordination API.

Manages cross-surface state, per-surface backend config, task spawning,
and an SSE event bus shared across all three surfaces (companion / workspace / codespace).

GET  /api/surface/state              — all three surfaces' current status
PUT  /api/surface/state/{surface}    — update a surface's status
GET  /api/surface/config             — per-surface backend config
PUT  /api/surface/config/{surface}   — save per-surface backend config
POST /api/surface/spawn              — spawn a task to a target surface
GET  /api/surface/events             — SSE stream of cross-surface events
DELETE /api/surface/tasks/{task_id}  — cancel / dismiss a spawned task
GET  /api/surface/tasks              — list active spawned tasks
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.guppy.api.server_context import ServerContext
from src.guppy.paths import ensure_user_data_dir, USER_DATA_DIR

# ── Constants ──────────────────────────────────────────────────────────────────

SURFACES = ("companion", "workspace", "codespace")

SURFACE_DEFAULTS: dict[str, dict[str, str]] = {
    "companion": {
        "backend":       "llamacpp",
        "model":         "llamacpp-minicpm",
        "fallback_model": "llamacpp-rocinante",
        "mode":          "local",
        "system_prompt": (
            "You are Guppy — a sharp, warm, uncensored personal assistant. "
            "You are voice-first, conversational, and direct. You never lecture. "
            "Keep answers tight unless asked to expand. You can hand off complex "
            "tasks to the Workspace when needed."
        ),
        "tool_policy":   "minimal",   # web_search, memory only
    },
    "workspace": {
        "backend":       "llamacpp",
        "model":         "llamacpp-hermes4",
        "fallback_model": "llamacpp-xlam",
        "mode":          "local",
        "system_prompt": (
            "You are the Workspace agent — a capable, methodical operator. "
            "You have access to full tools: file system, CRM, system monitoring, "
            "web search, code execution, and automation. Work step-by-step, "
            "report progress, and ask for clarification only when genuinely stuck."
        ),
        "tool_policy":   "full",
    },
    "codespace": {
        "backend":       "ollama",
        "model":         "guppy-code",
        "fallback_model": "llamacpp-hermes4",
        "mode":          "code",
        "system_prompt": (
            "You are the Codespace assistant — a senior software engineer. "
            "Write clean, idiomatic code with minimal but precise comments. "
            "Always include usage examples. Prefer correctness over brevity. "
            "You can run code in Docker sandboxes and read the Guppy codebase."
        ),
        "tool_policy":   "code",      # file read/write, docker exec, system
    },
}

# ── Database ───────────────────────────────────────────────────────────────────

_DB_PATH: str = ""

_SCHEMA = """
CREATE TABLE IF NOT EXISTS surface_state (
    surface      TEXT PRIMARY KEY,
    status       TEXT NOT NULL DEFAULT 'idle',
    current_task TEXT,
    agent_count  INTEGER NOT NULL DEFAULT 0,
    last_context TEXT,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS surface_config (
    surface       TEXT PRIMARY KEY,
    backend       TEXT NOT NULL DEFAULT 'auto',
    model         TEXT NOT NULL DEFAULT 'auto',
    fallback_model TEXT,
    mode          TEXT NOT NULL DEFAULT 'auto',
    system_prompt TEXT NOT NULL DEFAULT '',
    tool_policy   TEXT NOT NULL DEFAULT 'auto',
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS surface_tasks (
    id           TEXT PRIMARY KEY,
    surface      TEXT NOT NULL,
    source       TEXT NOT NULL DEFAULT 'user',
    title        TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'queued',
    result       TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
"""


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _init_db() -> None:
    with _db() as conn:
        conn.executescript(_SCHEMA)
        # Seed default state + config for each surface
        for surface in SURFACES:
            conn.execute(
                """INSERT OR IGNORE INTO surface_state
                   (surface, status, agent_count, updated_at)
                   VALUES (?, 'idle', 0, ?)""",
                (surface, _now()),
            )
            cfg = SURFACE_DEFAULTS[surface]
            conn.execute(
                """INSERT OR IGNORE INTO surface_config
                   (surface, backend, model, fallback_model, mode, system_prompt, tool_policy, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    surface,
                    cfg["backend"],
                    cfg["model"],
                    cfg.get("fallback_model", ""),
                    cfg["mode"],
                    cfg["system_prompt"],
                    cfg["tool_policy"],
                    _now(),
                ),
            )
        conn.commit()


# ── SSE event bus ──────────────────────────────────────────────────────────────

_sse_clients: set[asyncio.Queue] = set()
_sse_loop: asyncio.AbstractEventLoop | None = None


def _capture_loop() -> None:
    global _sse_loop
    if _sse_loop is None:
        try:
            _sse_loop = asyncio.get_event_loop()
        except RuntimeError:
            pass


def _broadcast_event(event_type: str, data: dict[str, Any]) -> None:
    """Thread-safe broadcast to all connected SSE clients."""
    payload = {"type": event_type, "data": data, "ts": _now()}
    msg = f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"
    if _sse_loop:
        for q in list(_sse_clients):
            try:
                _sse_loop.call_soon_threadsafe(q.put_nowait, msg)
            except Exception:
                pass


async def _sse_generator() -> AsyncGenerator[str, None]:
    _capture_loop()
    q: asyncio.Queue = asyncio.Queue()
    _sse_clients.add(q)
    try:
        # Send current state snapshot on connect
        with _db() as conn:
            rows = conn.execute("SELECT * FROM surface_state").fetchall()
        snapshot = {r["surface"]: dict(r) for r in rows}
        yield f"event: snapshot\ndata: {json.dumps(snapshot)}\n\n"

        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=25.0)
                yield msg
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
    finally:
        _sse_clients.discard(q)


# ── Pydantic models ────────────────────────────────────────────────────────────

class SurfaceStateUpdate(BaseModel):
    status:       str | None = None
    current_task: str | None = None
    agent_count:  int | None = None
    last_context: str | None = None


class SurfaceConfigUpdate(BaseModel):
    backend:        str | None = None
    model:          str | None = None
    fallback_model: str | None = None
    mode:           str | None = None
    system_prompt:  str | None = None
    tool_policy:    str | None = None


class SpawnTaskRequest(BaseModel):
    surface:     str
    title:       str
    description: str = ""
    source:      str = "user"     # 'user' | 'companion' | 'workspace' | 'codespace'


# ── Router ─────────────────────────────────────────────────────────────────────

def build_surface_router(ctx: ServerContext) -> APIRouter:
    global _DB_PATH

    ensure_user_data_dir()
    _DB_PATH = str(USER_DATA_DIR / "surface.db")
    _init_db()

    router = APIRouter(prefix="/api/surface", tags=["surface"])

    # ── State ──────────────────────────────────────────────────────────────────

    @router.get("/state")
    def get_all_state(_uid: str = Depends(ctx.require_rate_limit)):
        with _db() as conn:
            rows = conn.execute("SELECT * FROM surface_state ORDER BY surface").fetchall()
        return {r["surface"]: dict(r) for r in rows}

    @router.get("/state/{surface}")
    def get_surface_state(surface: str, _uid: str = Depends(ctx.require_rate_limit)):
        if surface not in SURFACES:
            raise HTTPException(400, f"Unknown surface: {surface}")
        with _db() as conn:
            row = conn.execute(
                "SELECT * FROM surface_state WHERE surface = ?", (surface,)
            ).fetchone()
        return dict(row) if row else {}

    @router.put("/state/{surface}")
    def update_surface_state(
        surface: str,
        body: SurfaceStateUpdate,
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        if surface not in SURFACES:
            raise HTTPException(400, f"Unknown surface: {surface}")
        updates: dict[str, Any] = {k: v for k, v in body.model_dump().items() if v is not None}
        updates["updated_at"] = _now()
        if not updates:
            return {"ok": True}
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        with _db() as conn:
            conn.execute(
                f"UPDATE surface_state SET {set_clause} WHERE surface = ?",
                (*updates.values(), surface),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM surface_state WHERE surface = ?", (surface,)
            ).fetchone()
        state = dict(row) if row else {}
        _broadcast_event("state_update", {"surface": surface, **state})
        return state

    # ── Config ─────────────────────────────────────────────────────────────────

    @router.get("/config")
    def get_all_config(_uid: str = Depends(ctx.require_rate_limit)):
        with _db() as conn:
            rows = conn.execute("SELECT * FROM surface_config ORDER BY surface").fetchall()
        return {r["surface"]: dict(r) for r in rows}

    @router.get("/config/{surface}")
    def get_surface_config(surface: str, _uid: str = Depends(ctx.require_rate_limit)):
        if surface not in SURFACES:
            raise HTTPException(400, f"Unknown surface: {surface}")
        with _db() as conn:
            row = conn.execute(
                "SELECT * FROM surface_config WHERE surface = ?", (surface,)
            ).fetchone()
        return dict(row) if row else SURFACE_DEFAULTS.get(surface, {})

    @router.put("/config/{surface}")
    def update_surface_config(
        surface: str,
        body: SurfaceConfigUpdate,
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        if surface not in SURFACES:
            raise HTTPException(400, f"Unknown surface: {surface}")
        updates: dict[str, Any] = {k: v for k, v in body.model_dump().items() if v is not None}
        updates["updated_at"] = _now()
        if not updates:
            return {"ok": True}
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        with _db() as conn:
            conn.execute(
                f"UPDATE surface_config SET {set_clause} WHERE surface = ?",
                (*updates.values(), surface),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM surface_config WHERE surface = ?", (surface,)
            ).fetchone()
        cfg = dict(row) if row else {}

        # Sync local model selection to the settings DB key that chat routing reads
        selected_model   = updates.get("model", "")
        selected_backend = updates.get("backend", cfg.get("backend", ""))
        if selected_model and selected_backend in ("llamacpp", "ollama"):
            try:
                from src.guppy.api.routes_settings import _settings_db
                _settings_db.set_setting("local_active_model", selected_model)
            except Exception:
                pass

        _broadcast_event("config_update", {"surface": surface, **cfg})
        return cfg

    @router.post("/config/{surface}/reset")
    def reset_surface_config(surface: str, _uid: str = Depends(ctx.require_rate_limit)):
        """Reset a surface's backend config to its defaults."""
        if surface not in SURFACES:
            raise HTTPException(400, f"Unknown surface: {surface}")
        cfg = SURFACE_DEFAULTS[surface]
        with _db() as conn:
            conn.execute(
                """UPDATE surface_config
                   SET backend=?, model=?, fallback_model=?, mode=?, system_prompt=?, tool_policy=?, updated_at=?
                   WHERE surface=?""",
                (
                    cfg["backend"], cfg["model"], cfg.get("fallback_model", ""),
                    cfg["mode"], cfg["system_prompt"], cfg["tool_policy"],
                    _now(), surface,
                ),
            )
            conn.commit()
        _broadcast_event("config_reset", {"surface": surface})
        return {"ok": True, "surface": surface, "config": cfg}

    # ── Task spawn ─────────────────────────────────────────────────────────────

    @router.post("/spawn")
    def spawn_task(body: SpawnTaskRequest, _uid: str = Depends(ctx.require_rate_limit)):
        if body.surface not in SURFACES:
            raise HTTPException(400, f"Unknown target surface: {body.surface}")
        task_id = str(uuid.uuid4())
        now = _now()
        with _db() as conn:
            conn.execute(
                """INSERT INTO surface_tasks
                   (id, surface, source, title, description, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, 'queued', ?, ?)""",
                (task_id, body.surface, body.source, body.title, body.description, now, now),
            )
            # Increment agent_count on the target surface
            conn.execute(
                """UPDATE surface_state
                   SET agent_count = agent_count + 1,
                       status = 'agent_running',
                       current_task = ?,
                       updated_at = ?
                   WHERE surface = ?""",
                (body.title, now, body.surface),
            )
            conn.commit()
        task = {
            "id": task_id,
            "surface": body.surface,
            "source": body.source,
            "title": body.title,
            "description": body.description,
            "status": "queued",
            "created_at": now,
        }
        _broadcast_event("task_spawned", task)
        return task

    @router.get("/tasks")
    def list_tasks(
        surface: str | None = None,
        status: str | None = None,
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        sql = "SELECT * FROM surface_tasks WHERE 1=1"
        params: list[Any] = []
        if surface:
            sql += " AND surface = ?"
            params.append(surface)
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY created_at DESC LIMIT 100"
        with _db() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    @router.put("/tasks/{task_id}")
    def update_task(
        task_id: str,
        body: dict,
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        allowed = {"status", "result", "current_task"}
        updates = {k: v for k, v in body.items() if k in allowed}
        if not updates:
            raise HTTPException(400, "No valid fields to update")
        updates["updated_at"] = _now()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        with _db() as conn:
            conn.execute(
                f"UPDATE surface_tasks SET {set_clause} WHERE id = ?",
                (*updates.values(), task_id),
            )
            # If task is complete/failed, decrement agent_count
            if updates.get("status") in ("complete", "failed", "cancelled"):
                row = conn.execute(
                    "SELECT surface FROM surface_tasks WHERE id = ?", (task_id,)
                ).fetchone()
                if row:
                    conn.execute(
                        """UPDATE surface_state
                           SET agent_count = MAX(0, agent_count - 1),
                               updated_at = ?
                           WHERE surface = ?""",
                        (_now(), row["surface"]),
                    )
                    # Clear status if no tasks remain
                    conn.execute(
                        """UPDATE surface_state
                           SET status = CASE WHEN agent_count <= 0 THEN 'idle' ELSE status END,
                               current_task = CASE WHEN agent_count <= 0 THEN NULL ELSE current_task END,
                               updated_at = ?
                           WHERE surface = ?""",
                        (_now(), row["surface"]),
                    )
            conn.commit()
            task_row = conn.execute(
                "SELECT * FROM surface_tasks WHERE id = ?", (task_id,)
            ).fetchone()
        task = dict(task_row) if task_row else {}
        _broadcast_event("task_updated", task)
        return task

    @router.delete("/tasks/{task_id}", status_code=204)
    def cancel_task(task_id: str, _uid: str = Depends(ctx.require_rate_limit)):
        with _db() as conn:
            row = conn.execute(
                "SELECT surface FROM surface_tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if not row:
                raise HTTPException(404, "Task not found")
            conn.execute(
                "UPDATE surface_tasks SET status='cancelled', updated_at=? WHERE id=?",
                (_now(), task_id),
            )
            conn.execute(
                """UPDATE surface_state
                   SET agent_count = MAX(0, agent_count - 1),
                       updated_at = ?
                   WHERE surface = ?""",
                (_now(), row["surface"]),
            )
            conn.execute(
                """UPDATE surface_state
                   SET status = CASE WHEN agent_count <= 0 THEN 'idle' ELSE status END,
                       current_task = CASE WHEN agent_count <= 0 THEN NULL ELSE current_task END,
                       updated_at = ?
                   WHERE surface = ?""",
                (_now(), row["surface"]),
            )
            conn.commit()
        _broadcast_event("task_cancelled", {"id": task_id})

    # ── SSE events ─────────────────────────────────────────────────────────────

    @router.get("/events")
    async def surface_events(_uid: str = Depends(ctx.require_rate_limit)):
        _capture_loop()
        return StreamingResponse(
            _sse_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    return router
