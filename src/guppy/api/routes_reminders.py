"""
Reminder scheduling and delivery API.

POST /api/reminders          — create a reminder  { message, due_iso | delay_minutes }
GET  /api/reminders          — list all pending reminders
GET  /api/reminders/due      — return reminders that are due NOW and mark them delivered
DELETE /api/reminders/{id}   — cancel a reminder

The web UI polls /api/reminders/due every 30 s and fires browser Notification() toasts.
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from src.guppy.api.server_context import ServerContext


# ── storage ───────────────────────────────────────────────────────────────────

from src.guppy.paths import MAIN_DB_PATH
_DB_PATH = str(MAIN_DB_PATH)


def _get_conn() -> sqlite3.Connection:
    MAIN_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id          TEXT PRIMARY KEY,
            message     TEXT NOT NULL,
            due_at      TEXT NOT NULL,
            delivered   INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


# ── helpers ───────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id":         row["id"],
        "message":    row["message"],
        "due_at":     row["due_at"],
        "delivered":  bool(row["delivered"]),
        "created_at": row["created_at"],
    }


# ── public helper (called from tool_runner) ───────────────────────────────────

def create_reminder(message: str, due_iso: Optional[str] = None, delay_minutes: Optional[float] = None) -> Dict[str, Any]:
    """Create a reminder. Either due_iso (UTC ISO-8601) or delay_minutes must be supplied."""
    if due_iso is None and delay_minutes is None:
        raise ValueError("Provide due_iso or delay_minutes")
    if due_iso is None:
        due_dt = datetime.now(timezone.utc) + timedelta(minutes=float(delay_minutes or 30))
        due_iso = due_dt.isoformat()
    rid = str(uuid.uuid4())
    now = _now_iso()
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO reminders (id, message, due_at, delivered, created_at) VALUES (?,?,?,0,?)",
            (rid, message, due_iso, now),
        )
        conn.commit()
    return {"id": rid, "message": message, "due_at": due_iso, "created_at": now}


def get_due_reminders() -> List[Dict[str, Any]]:
    """Return all undelivered reminders whose due_at <= now, and mark them delivered."""
    now = _now_iso()
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM reminders WHERE delivered=0 AND due_at <= ? ORDER BY due_at",
            (now,),
        ).fetchall()
        if rows:
            ids = [r["id"] for r in rows]
            conn.execute(
                f"UPDATE reminders SET delivered=1 WHERE id IN ({','.join('?' * len(ids))})",
                ids,
            )
            conn.commit()
    return [_row_to_dict(r) for r in rows]


# ── router ────────────────────────────────────────────────────────────────────

def build_reminders_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/reminders")

    @router.post("")
    async def create(
        payload: Dict[str, Any],
        _u: str = Depends(ctx.require_rate_limit),
    ):
        """Schedule a reminder. Body: { message, due_iso? | delay_minutes? }"""
        message = str(payload.get("message", "")).strip()
        if not message:
            raise HTTPException(status_code=400, detail="message required")
        due_iso      = payload.get("due_iso")
        delay_minutes = payload.get("delay_minutes")
        if due_iso is None and delay_minutes is None:
            raise HTTPException(status_code=400, detail="due_iso or delay_minutes required")
        try:
            return create_reminder(message, due_iso=due_iso, delay_minutes=delay_minutes)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("")
    async def list_all(_u: str = Depends(ctx.require_rate_limit)):
        """Return all undelivered reminders."""
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM reminders WHERE delivered=0 ORDER BY due_at"
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    @router.get("/due")
    async def poll_due(_u: str = Depends(ctx.require_rate_limit)):
        """Return reminders due now and mark them as delivered. Web UI polls this."""
        return get_due_reminders()

    @router.delete("/{rid}")
    async def cancel(rid: str, _u: str = Depends(ctx.require_rate_limit)):
        """Cancel a reminder."""
        with _get_conn() as conn:
            result = conn.execute("DELETE FROM reminders WHERE id=?", (rid,))
            conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Reminder not found")
        return {"deleted": rid}

    return router
