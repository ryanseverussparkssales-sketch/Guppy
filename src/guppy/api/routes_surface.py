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
import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.guppy.api.server_context import ServerContext
from src.guppy.paths import MAIN_DB_PATH, ensure_user_data_dir, USER_DATA_DIR

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
        "backend":       "llamacpp",
        "model":         "llamacpp-hermes4",
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
    id               TEXT PRIMARY KEY,
    surface          TEXT NOT NULL,
    source           TEXT NOT NULL DEFAULT 'user',
    title            TEXT NOT NULL,
    description      TEXT NOT NULL DEFAULT '',
    status           TEXT NOT NULL DEFAULT 'queued',
    result           TEXT,
    parent_task_id   TEXT,
    callback_surface TEXT,
    result_summary   TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
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


def _ensure_new_columns() -> None:
    """Migrate existing DBs: add columns introduced after initial schema creation."""
    new_cols = [
        ("surface_tasks", "parent_task_id",  "TEXT"),
        ("surface_tasks", "callback_surface", "TEXT"),
        ("surface_tasks", "result_summary",   "TEXT"),
    ]
    with _db() as conn:
        for table, col, coltype in new_cols:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")
                conn.commit()
            except sqlite3.OperationalError:
                pass  # column already exists


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
    _ensure_new_columns()


# ── Internal task-spawn helper (called without HTTP context) ──────────────────

def _spawn_task_direct(
    *,
    title: str,
    description: str = "",
    source: str = "companion",
    surface: str = "workspace",
    parent_task_id: str | None = None,
    callback_surface: str | None = None,
) -> dict:
    """Spawn a task directly from internal code (e.g. companion tool executor).

    Identical to the /spawn endpoint but bypasses HTTP auth — only call from
    trusted internal paths.
    """
    if not _DB_PATH:
        raise RuntimeError("surface DB not initialised yet — router not built")
    task_id = str(uuid.uuid4())
    now = _now()
    with _db() as conn:
        conn.execute(
            """INSERT INTO surface_tasks
               (id, surface, source, title, description, status,
                parent_task_id, callback_surface, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'queued', ?, ?, ?, ?)""",
            (task_id, surface, source, title, description,
             parent_task_id, callback_surface, now, now),
        )
        conn.execute(
            """UPDATE surface_state
               SET agent_count = agent_count + 1,
                   status = 'agent_running',
                   current_task = ?,
                   updated_at = ?
               WHERE surface = ?""",
            (title, now, surface),
        )
        conn.commit()
    task = {
        "id": task_id,
        "surface": surface,
        "source": source,
        "title": title,
        "description": description,
        "status": "queued",
        "parent_task_id": parent_task_id,
        "callback_surface": callback_surface,
        "created_at": now,
    }
    _broadcast_event("task_spawned", task)
    return task


def _cancel_task_direct(task_id: str) -> dict:
    """Cancel a queued task from internal code (e.g. companion cancel_workspace_task tool).

    Only queued tasks can be cancelled — in-progress tasks are not interrupted.
    """
    if not _DB_PATH:
        raise RuntimeError("surface DB not initialised yet — router not built")
    task_id = (task_id or "").strip()
    if not task_id:
        return {"ok": False, "error": "task_id required"}
    with _db() as conn:
        row = conn.execute(
            "SELECT title, status FROM surface_tasks WHERE id=?", (task_id,)
        ).fetchone()
        if not row:
            return {"ok": False, "error": f"task {task_id!r} not found"}
        title, status = row
        if status != "queued":
            return {"ok": False, "error": f"task is {status!r}, can only cancel queued tasks"}
        now = _now()
        conn.execute(
            "UPDATE surface_tasks SET status='cancelled', updated_at=? WHERE id=?",
            (now, task_id),
        )
        conn.commit()
    _broadcast_event("task_cancelled", {"id": task_id, "title": title})
    return {"ok": True, "cancelled_id": task_id, "title": title}


# ── SSE event bus ──────────────────────────────────────────────────────────────

_sse_clients: set[asyncio.Queue] = set()
_sse_clients_lock = threading.Lock()
_sse_loop: asyncio.AbstractEventLoop | None = None


def _capture_loop() -> None:
    global _sse_loop
    if _sse_loop is None:
        try:
            _sse_loop = asyncio.get_event_loop()
        except RuntimeError:
            pass


def _broadcast_event(event_type: str, data: dict[str, Any]) -> None:
    """Thread-safe broadcast to all connected SSE clients.

    Each client has a bounded asyncio.Queue(maxsize=200).  If a client's queue
    is full (slow/stale connection) its event is silently dropped with a warning
    rather than blocking or growing unbounded.
    """
    payload = {"type": event_type, "data": data, "ts": _now()}
    msg = f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"
    if not _sse_loop:
        return
    with _sse_clients_lock:
        snapshot = list(_sse_clients)
    for q in snapshot:
        def _try_put(_q=q, _m=msg, _et=event_type) -> None:
            try:
                _q.put_nowait(_m)
            except asyncio.QueueFull:
                _log.warning("[surface.sse] slow client evicted (queue full): event=%s qid=%s", _et, id(_q))
        try:
            _sse_loop.call_soon_threadsafe(_try_put)
        except Exception:
            _log.debug("[surface.sse] broadcast schedule failed: event=%s", event_type)


async def _sse_generator() -> AsyncGenerator[str, None]:
    _capture_loop()
    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    with _sse_clients_lock:
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
        with _sse_clients_lock:
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
    surface:          str
    title:            str
    description:      str = ""
    source:           str = "user"     # 'user' | 'companion' | 'workspace' | 'codespace'
    parent_task_id:   str | None = None
    callback_surface: str | None = None


class TaskCallbackRequest(BaseModel):
    result_summary:  str
    source_task_id:  str | None = None


# ── 24/7 background loop ───────────────────────────────────────────────────────
_bg_log = logging.getLogger(__name__ + ".bg")


_task_executor_running = False   # simple flag — only one task runs at a time


async def _run_workspace_task(
    task_id: str,
    title: str,
    description: str,
    parent_task_id: str | None = None,
    callback_surface: str | None = None,
) -> None:
    """Run one queued workspace task through Hermes4 (port 8086).

    Marks the task in_progress → completed/failed, broadcasts SSE events
    throughout so the Workspace surface can show live progress.
    The executor calls Hermes4 directly (OpenAI-compat) to avoid circular
    HTTP auth — the background loop has no JWT token.
    """
    import httpx, json as _json

    _bg_log.info("[task_exec] starting task %s: %s", task_id, title)

    def _update(status: str, result: str | None = None) -> None:
        if not _DB_PATH:
            return
        try:
            with _db() as conn:
                if result is not None:
                    conn.execute(
                        "UPDATE surface_tasks SET status=?, result=?, updated_at=? WHERE id=?",
                        (status, result, _now(), task_id),
                    )
                else:
                    conn.execute(
                        "UPDATE surface_tasks SET status=?, updated_at=? WHERE id=?",
                        (status, _now(), task_id),
                    )
                conn.commit()
        except Exception as _e:
            _bg_log.error("[task_exec] DB update failed: %s", _e)

    _update("in_progress")
    _broadcast_event("task_progress", {"id": task_id, "status": "in_progress", "step": "Starting"})

    # Build the task message for Hermes4
    from src.guppy.api.routes_realtime import _WORKSPACE_TOOL_SCHEMA, _TOOL_CALL_RE, _execute_workspace_tool
    from src.guppy.api.realtime_inference_support import _repair_tool_json

    # Inject relevant semantic context so the agent benefits from past task outcomes,
    # user preferences, and prior workspace results before the first LLM call.
    _semantic_suffix = ""
    try:
        from src.guppy.memory.semantic import recall_semantic
        _mem = await asyncio.to_thread(
            recall_semantic,
            f"{title} {description}"[:400],
            5,
            "",  # all categories
        )
        if _mem and not _mem.startswith("Error:") and "nothing found" not in _mem.lower():
            _semantic_suffix = f"\n\n[Relevant memory context]\n{_mem[:1200]}"
    except Exception as _me:
        _bg_log.debug("[task_exec] memory recall skipped: %s", _me)

    system_prompt = (
        "You are the Guppy Workspace agent — an autonomous operator running a background task.\n"
        "Complete the task fully. Use tools as needed. Report what you did concisely."
        + _semantic_suffix
        + _WORKSPACE_TOOL_SCHEMA
    )

    context_text = ""
    try:
        _broadcast_event("task_progress", {"id": task_id, "status": "in_progress", "step": "Gathering screen context"})
        from src.guppy.api.routes_screenpipe import _search as _screenpipe_search

        ctx_rows = await asyncio.to_thread(
            _screenpipe_search,
            description or title,
            3,
            "all",
            None,
            None,
            None,
        )
        if ctx_rows:
            lines = []
            for row in ctx_rows[:3]:
                app = row.get("app_name", "Unknown")
                ts = row.get("timestamp", "")
                content = (row.get("content", "") or "")[:180].replace("\n", " ").strip()
                lines.append(f"- [{ts}] ({app}) {content}")
            context_text = "\nRecent screen context:\n" + "\n".join(lines)
    except Exception as _ctx_exc:
        _bg_log.debug("[task_exec] screen context unavailable for %s: %s", task_id, _ctx_exc)

    user_message = f"Task: {title}\n\n{description}{context_text}".strip()

    try:
        # Call Hermes4 directly (port 8086, OpenAI-compat)
        payload = {
            "model": "hermes-4-14b",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message},
            ],
            "stream": False,
            "temperature": 0.3,
            "max_tokens": 2048,
        }
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post("http://localhost:8086/v1/chat/completions", json=payload)
            resp.raise_for_status()

        first_response = resp.json()["choices"][0]["message"]["content"]
        _broadcast_event("task_progress", {"id": task_id, "status": "in_progress", "step": "Executing tools"})

        # Execute any tool calls in the response
        tool_blocks = _TOOL_CALL_RE.findall(first_response)
        tool_results: list[dict] = []
        for tc_json in tool_blocks:
            try:
                tc = _repair_tool_json(tc_json)
                if tc is None:
                    # One-shot correction: ask the model to fix its malformed JSON
                    try:
                        _correction_payload = {
                            "model": "hermes-4-14b",
                            "messages": [
                                {"role": "user", "content": (
                                    f"You emitted an invalid tool call. Raw output:\n\n{tc_json}\n\n"
                                    "Rewrite it as valid JSON inside <tool_call>...</tool_call> tags. "
                                    "Output ONLY the corrected tool call, nothing else."
                                )}
                            ],
                            "stream": False,
                            "max_tokens": 256,
                            "temperature": 0.0,
                        }
                        async with httpx.AsyncClient(timeout=10.0) as _c:
                            _cr = await _c.post("http://localhost:8086/v1/chat/completions", json=_correction_payload)
                            _cr.raise_for_status()
                        _corrected_text = _cr.json()["choices"][0]["message"]["content"]
                        _corrected_blocks = _TOOL_CALL_RE.findall(_corrected_text)
                        tc = _repair_tool_json(_corrected_blocks[0]) if _corrected_blocks else None
                    except Exception as _retry_exc:
                        _bg_log.warning("[task_exec] Tool-call correction failed: %s", _retry_exc)
                        tc = None
                    if tc is None:
                        tool_results.append({"tool": "?", "error": "malformed tool JSON"})
                        continue
                tool_name = tc.get("name", "")
                if not tool_name:
                    _bg_log.warning("[task_exec] Tool call missing name, skipping: %s", tc)
                    continue
                tool_args = tc.get("arguments", {})
                if not isinstance(tool_args, dict):
                    _bg_log.warning("[task_exec] tool_args not a dict, coercing to {}: %s", tool_args)
                    tool_args = {}
                _broadcast_event("task_progress", {"id": task_id, "status": "in_progress", "step": f"Tool: {tool_name}"})
                result = await _execute_workspace_tool(tool_name, tool_args)
                tool_results.append({"tool": tool_name, "result": result})
            except Exception as exc:
                tool_results.append({"tool": "?", "error": str(exc)})

        # If tools were called, get a follow-up summary
        final_result = first_response
        if tool_results:
            tool_result_text = "\n\n".join(
                f"[{r['tool']}]\n{_json.dumps(r.get('result', r.get('error', '')), ensure_ascii=False)[:3000]}"
                for r in tool_results
            )
            summary_payload = {
                "model": "hermes-4-14b",
                "messages": [
                    {"role": "system",    "content": system_prompt},
                    {"role": "user",      "content": user_message},
                    {"role": "assistant", "content": first_response},
                    {"role": "user",      "content": (
                        f"Tool results:\n\n{tool_result_text}\n\n"
                        "Summarize what was completed in 2-3 sentences."
                    )},
                ],
                "stream": False,
                "temperature": 0.3,
                "max_tokens": 512,
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp2 = await client.post("http://localhost:8086/v1/chat/completions", json=summary_payload)
                if resp2.status_code < 300:
                    final_result = resp2.json()["choices"][0]["message"]["content"]

        _update("completed", final_result[:4000])
        _broadcast_event("task_completed", {
            "id": task_id, "title": title, "result": final_result[:500],
        })
        _bg_log.info("[task_exec] task %s completed", task_id)

        # Fire callback to parent task if this was spawned as a child task
        if parent_task_id:
            try:
                _cb_surface = callback_surface or "workspace"
                with _db() as conn:
                    conn.execute(
                        "UPDATE surface_tasks SET result_summary=?, updated_at=? WHERE id=?",
                        (final_result[:4000], _now(), parent_task_id),
                    )
                    conn.commit()
                _broadcast_event("task_callback", {
                    "parent_task_id": parent_task_id,
                    "child_task_id": task_id,
                    "child_title": title,
                    "surface": _cb_surface,
                    "result_summary": final_result[:500],
                })
                _bg_log.info("[task_exec] callback fired for parent=%s from child=%s", parent_task_id, task_id)
            except Exception as _cb_exc:
                _bg_log.warning("[task_exec] callback failed for parent=%s: %s", parent_task_id, _cb_exc)

    except Exception as exc:
        _bg_log.error("[task_exec] task %s failed: %s", task_id, exc)
        _update("failed", str(exc)[:1000])
        _broadcast_event("task_failed", {"id": task_id, "title": title, "error": str(exc)[:200]})


async def _background_loop() -> None:
    """24/7 async background task: reminder delivery + workspace task execution.

    Runs every 30 s. Delivers due reminders as SSE events, processes one queued
    workspace task per cycle through Hermes4, ages stale tasks after 6 h, and
    tombstone-deletes terminal tasks older than 30 days once per 24 h.
    """
    global _task_executor_running
    _bg_log.info("[surface.bg] background loop started")
    _last_tombstone = 0.0  # epoch seconds — tracks last daily cleanup

    while True:
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            _bg_log.info("[surface.bg] background loop cancelled")
            return

        # ── Reminder delivery ─────────────────────────────────────────────────
        try:
            from src.guppy.api.routes_reminders import get_due_reminders
            due = get_due_reminders()
            for reminder in due:
                _broadcast_event("reminder_due", reminder)
                _bg_log.info(
                    "[surface.bg] reminder delivered: %s (id=%s)",
                    reminder.get("message", ""), reminder.get("id", ""),
                )
        except Exception as exc:
            _bg_log.error("[surface.bg] reminder delivery error: %s", exc)

        # ── Workspace task execution ───────────────────────────────────────────
        # Process one queued workspace task per cycle to keep VRAM pressure low.
        if not _task_executor_running and _DB_PATH:
            try:
                with _db() as conn:
                    row = conn.execute(
                        "SELECT id, title, description, parent_task_id, callback_surface "
                        "FROM surface_tasks "
                        "WHERE surface='workspace' AND status='queued' "
                        "ORDER BY created_at ASC LIMIT 1"
                    ).fetchone()
                if row:
                    _task_executor_running = True
                    task_id    = row["id"]
                    title      = row["title"]
                    description = row["description"]
                    _ptid      = row["parent_task_id"]
                    _cbsurf    = row["callback_surface"]

                    async def _run_and_clear(
                        tid: str, ttl: str, desc: str,
                        ptid: str | None, cbsurf: str | None,
                    ) -> None:
                        global _task_executor_running
                        try:
                            await asyncio.wait_for(
                                _run_workspace_task(tid, ttl, desc, ptid, cbsurf),
                                timeout=600,
                            )
                        except asyncio.TimeoutError:
                            _bg_log.error(
                                "[surface.bg] task %s timed out after 600s — marking failed", tid
                            )
                            try:
                                if _DB_PATH:
                                    with _db() as conn:
                                        conn.execute(
                                            "UPDATE tasks SET status='failed', updated_at=? WHERE id=?",
                                            (datetime.now(timezone.utc).isoformat(), tid),
                                        )
                            except Exception:
                                pass
                        finally:
                            _task_executor_running = False

                    asyncio.create_task(_run_and_clear(task_id, title, description, _ptid, _cbsurf))
            except Exception as exc:
                _task_executor_running = False
                _bg_log.error("[surface.bg] task dispatch error: %s", exc)

        # ── Stale task cleanup (tasks queued for >6 h become stale) ──────────
        try:
            from datetime import timedelta
            stale_cutoff = (
                datetime.now(timezone.utc) - timedelta(hours=6)
            ).isoformat()
            if _DB_PATH:
                with _db() as conn:
                    # Fetch affected tasks so we can decrement agent_count per surface.
                    stale_rows = conn.execute(
                        """SELECT id, surface FROM surface_tasks
                           WHERE status = 'queued' AND created_at < ?""",
                        (stale_cutoff,),
                    ).fetchall()
                    if stale_rows:
                        ids = [r[0] for r in stale_rows]
                        conn.execute(
                            f"UPDATE surface_tasks SET status = 'stale', updated_at = ? "
                            f"WHERE id IN ({','.join('?' * len(ids))})",
                            (_now(), *ids),
                        )
                        # Decrement agent_count for each affected surface.
                        surfaces_affected: set[str] = {r[1] for r in stale_rows if r[1]}
                        for surf in surfaces_affected:
                            count = sum(1 for r in stale_rows if r[1] == surf)
                            conn.execute(
                                """UPDATE surface_state
                                   SET agent_count = MAX(0, agent_count - ?),
                                       updated_at  = ?
                                   WHERE surface = ?""",
                                (count, _now(), surf),
                            )
                        conn.commit()
        except Exception as exc:
            _bg_log.error("[surface.bg] stale task cleanup error: %s", exc)

        # ── Proactive companion nudges (every 5 min) ─────────────────────────
        # Surface upcoming calendar events and unread email counts as ambient
        # SSE events so CompanionView can speak them without the user asking.
        try:
            import time as _time
            _now_epoch = _time.monotonic()
            if not hasattr(_background_loop, "_last_proactive"):
                _background_loop._last_proactive = 0.0  # type: ignore[attr-defined]
            if _now_epoch - _background_loop._last_proactive > 300:  # type: ignore[attr-defined]
                _background_loop._last_proactive = _now_epoch  # type: ignore[attr-defined]
                nudges: list[dict] = []

                # Check for calendar events starting in the next 60 minutes
                try:
                    from src.guppy.api.routes_calendar import _get_upcoming_events
                    upcoming = _get_upcoming_events(horizon_minutes=60)
                    for ev in upcoming[:2]:
                        nudges.append({
                            "type": "calendar_reminder",
                            "title": ev.get("title", "Event"),
                            "starts_in_minutes": ev.get("starts_in_minutes", 0),
                            "location": ev.get("location", ""),
                        })
                except Exception:
                    pass

                # Broadcast each nudge so CompanionView can voice it
                for nudge in nudges:
                    _broadcast_event("proactive_nudge", nudge)
                    _bg_log.debug("[surface.bg] proactive nudge: %s", nudge.get("type"))
        except Exception as exc:
            _bg_log.error("[surface.bg] proactive nudge error: %s", exc)

        # ── Tombstone deletion (once per 24 h) ───────────────────────────────
        # Delete terminal tasks older than 30 days to prevent unbounded table growth.
        try:
            import time as _time
            now_epoch = _time.monotonic()
            if now_epoch - _last_tombstone > 86_400 and _DB_PATH:
                from datetime import timedelta
                cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
                with _db() as conn:
                    deleted = conn.execute(
                        """DELETE FROM surface_tasks
                           WHERE status IN ('completed','failed','stale','cancelled')
                             AND updated_at < ?""",
                        (cutoff,),
                    ).rowcount
                    conn.commit()
                if deleted:
                    _bg_log.info("[surface.bg] tombstone: deleted %d old terminal tasks", deleted)
                _last_tombstone = now_epoch
        except Exception as exc:
            _bg_log.error("[surface.bg] tombstone cleanup error: %s", exc)


# ── Router ─────────────────────────────────────────────────────────────────────

def build_surface_router(ctx: ServerContext) -> APIRouter:
    global _DB_PATH

    ensure_user_data_dir()
    _DB_PATH = str(MAIN_DB_PATH)
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

        # When companion model is switched without an explicit system_prompt, auto-apply
        # the matching personality preset so Pepe doesn't respond like Hermes3, etc.
        if surface == "companion" and "model" in updates and "system_prompt" not in updates:
            try:
                from src.guppy.api.routes_companion import PERSONALITY_PRESETS
                preset = next(
                    (p for p in PERSONALITY_PRESETS.values() if p["model"] == updates["model"]),
                    None,
                )
                if preset:
                    updates["system_prompt"] = preset["system_prompt"]
            except Exception:
                pass

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
                   (id, surface, source, title, description, status,
                    parent_task_id, callback_surface, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, 'queued', ?, ?, ?, ?)""",
                (task_id, body.surface, body.source, body.title, body.description,
                 body.parent_task_id, body.callback_surface, now, now),
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
            "parent_task_id": body.parent_task_id,
            "callback_surface": body.callback_surface,
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
            # If task is terminal, decrement agent_count
            if updates.get("status") in ("completed", "failed", "cancelled", "stale"):
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

    # ── Task callback (child → parent result notification) ─────────────────────

    @router.post("/tasks/{task_id}/callback")
    def task_callback(
        task_id: str,
        body: TaskCallbackRequest,
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        """Attach a result from a child task back to a parent task.

        Called by Codespace triage (or any child process) when it finishes work
        spawned on behalf of a Workspace task.  Updates `result_summary` on the
        target task and broadcasts a `task_callback` SSE event so WorkspaceView
        can show a "Fix ready" chip in the Agents tab.
        """
        with _db() as conn:
            row = conn.execute("SELECT * FROM surface_tasks WHERE id=?", (task_id,)).fetchone()
            if not row:
                raise HTTPException(404, "Task not found")
            conn.execute(
                "UPDATE surface_tasks SET result_summary=?, updated_at=? WHERE id=?",
                (body.result_summary[:4000], _now(), task_id),
            )
            conn.commit()
        _broadcast_event("task_callback", {
            "task_id": task_id,
            "surface": row["surface"],
            "title": row["title"],
            "result_summary": body.result_summary[:500],
            "source_task_id": body.source_task_id,
        })
        return {"ok": True, "task_id": task_id}

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
