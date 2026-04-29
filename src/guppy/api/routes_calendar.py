"""Calendar API — local event store with Google Calendar sync stub.

Local events stored in SQLite (runtime/calendar.db).
When GOOGLE_CALENDAR_CREDENTIALS env var points to a valid OAuth token
file the sync endpoint will pull events from Google Calendar. Until then
all CRUD is fully local and sync is a documented no-op.

GET    /api/calendar/events          — list events (start/end ISO, limit)
GET    /api/calendar/today           — today's agenda (sorted by start)
GET    /api/calendar/upcoming        — next 7 days
POST   /api/calendar/events          — create local event
PATCH  /api/calendar/events/{id}     — update event
DELETE /api/calendar/events/{id}     — delete event
GET    /api/calendar/status          — Google Calendar connection status
POST   /api/calendar/sync            — trigger Google Calendar sync (stub)
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.guppy.api.server_context import ServerContext

logger = logging.getLogger(__name__)

_DB_PATH = "runtime/calendar.db"

# ── DB ────────────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    os.makedirs("runtime", exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS calendar_events (
            id              TEXT PRIMARY KEY,
            title           TEXT NOT NULL,
            description     TEXT NOT NULL DEFAULT '',
            location        TEXT NOT NULL DEFAULT '',
            start_time      TEXT NOT NULL,
            end_time        TEXT NOT NULL,
            all_day         INTEGER NOT NULL DEFAULT 0,
            color           TEXT NOT NULL DEFAULT 'primary',
            google_event_id TEXT,
            calendar_id     TEXT NOT NULL DEFAULT 'local',
            recurrence      TEXT NOT NULL DEFAULT '',
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def _row(r: sqlite3.Row) -> dict[str, Any]:
    return {
        "id":              r["id"],
        "title":           r["title"],
        "description":     r["description"],
        "location":        r["location"],
        "start_time":      r["start_time"],
        "end_time":        r["end_time"],
        "all_day":         bool(r["all_day"]),
        "color":           r["color"],
        "google_event_id": r["google_event_id"],
        "calendar_id":     r["calendar_id"],
        "recurrence":      r["recurrence"],
        "created_at":      r["created_at"],
        "updated_at":      r["updated_at"],
    }


# ── Google Calendar stub ──────────────────────────────────────────────────────

def _google_connected() -> bool:
    creds_path = os.environ.get("GOOGLE_CALENDAR_CREDENTIALS", "")
    return bool(creds_path and os.path.exists(creds_path))


def _sync_google_calendar() -> dict[str, Any]:
    """Attempt Google Calendar sync. Returns result dict."""
    if not _google_connected():
        return {"ok": False, "error": "GOOGLE_CALENDAR_CREDENTIALS not set or file not found"}
    try:
        # Real implementation would use google-api-python-client:
        #   service = build('calendar', 'v3', credentials=creds)
        #   events = service.events().list(calendarId='primary', ...).execute()
        # For now: no-op stub that signals "configured but not yet implemented"
        return {"ok": False, "error": "Google Calendar sync not yet implemented — set GOOGLE_CALENDAR_CREDENTIALS"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ── Pydantic ──────────────────────────────────────────────────────────────────

class EventCreate(BaseModel):
    title:       str
    description: str = ""
    location:    str = ""
    start_time:  str          # ISO 8601
    end_time:    str          # ISO 8601
    all_day:     bool = False
    color:       str = "primary"  # primary | secondary | tertiary | error | success | warning
    recurrence:  str = ""


class EventUpdate(BaseModel):
    title:       Optional[str] = None
    description: Optional[str] = None
    location:    Optional[str] = None
    start_time:  Optional[str] = None
    end_time:    Optional[str] = None
    all_day:     Optional[bool] = None
    color:       Optional[str] = None
    recurrence:  Optional[str] = None


# ── Router ────────────────────────────────────────────────────────────────────

def build_calendar_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/calendar", tags=["calendar"])

    @router.get("/status")
    def calendar_status(_uid: str = Depends(ctx.require_rate_limit)):
        connected = _google_connected()
        with _conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM calendar_events").fetchone()[0]
        return {
            "google_connected":    connected,
            "google_creds_env":    bool(os.environ.get("GOOGLE_CALENDAR_CREDENTIALS")),
            "local_event_count":   total,
            "sync_hint": (
                "Set GOOGLE_CALENDAR_CREDENTIALS to a Google OAuth token file "
                "and restart the server to enable sync."
                if not connected else "Google Calendar credentials found"
            ),
        }

    @router.get("/events")
    def list_events(
        start:  str = "",
        end:    str = "",
        limit:  int = 200,
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        with _conn() as conn:
            if start and end:
                rows = conn.execute(
                    "SELECT * FROM calendar_events "
                    "WHERE start_time >= ? AND start_time <= ? "
                    "ORDER BY start_time ASC LIMIT ?",
                    (start, end, min(limit, 500)),
                ).fetchall()
            elif start:
                rows = conn.execute(
                    "SELECT * FROM calendar_events WHERE start_time >= ? "
                    "ORDER BY start_time ASC LIMIT ?",
                    (start, min(limit, 500)),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM calendar_events ORDER BY start_time ASC LIMIT ?",
                    (min(limit, 500),),
                ).fetchall()
        return [_row(r) for r in rows]

    @router.get("/today")
    def today_events(_uid: str = Depends(ctx.require_rate_limit)):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
        with _conn() as conn:
            rows = conn.execute(
                "SELECT * FROM calendar_events "
                "WHERE start_time >= ? AND start_time < ? "
                "ORDER BY start_time ASC",
                (today, tomorrow),
            ).fetchall()
        return [_row(r) for r in rows]

    @router.get("/upcoming")
    def upcoming_events(days: int = 7, _uid: str = Depends(ctx.require_rate_limit)):
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=min(days, 90))
        with _conn() as conn:
            rows = conn.execute(
                "SELECT * FROM calendar_events "
                "WHERE start_time >= ? AND start_time <= ? "
                "ORDER BY start_time ASC LIMIT 100",
                (now.isoformat(), end.isoformat()),
            ).fetchall()
        return [_row(r) for r in rows]

    @router.post("/events")
    def create_event(body: EventCreate, _uid: str = Depends(ctx.require_rate_limit)):
        eid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with _conn() as conn:
            conn.execute(
                "INSERT INTO calendar_events "
                "(id, title, description, location, start_time, end_time, all_day, color, recurrence, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (eid, body.title, body.description, body.location,
                 body.start_time, body.end_time, int(body.all_day),
                 body.color, body.recurrence, now, now),
            )
            conn.commit()
        return {"ok": True, "id": eid}

    @router.patch("/events/{event_id}")
    def update_event(event_id: str, body: EventUpdate, _uid: str = Depends(ctx.require_rate_limit)):
        updates: dict[str, Any] = {}
        if body.title       is not None: updates["title"]       = body.title
        if body.description is not None: updates["description"] = body.description
        if body.location    is not None: updates["location"]    = body.location
        if body.start_time  is not None: updates["start_time"]  = body.start_time
        if body.end_time    is not None: updates["end_time"]    = body.end_time
        if body.all_day     is not None: updates["all_day"]     = int(body.all_day)
        if body.color       is not None: updates["color"]       = body.color
        if body.recurrence  is not None: updates["recurrence"]  = body.recurrence
        if not updates:
            raise HTTPException(400, "Nothing to update")
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [event_id]
        with _conn() as conn:
            conn.execute(f"UPDATE calendar_events SET {set_clause} WHERE id=?", values)
            conn.commit()
        return {"ok": True}

    @router.delete("/events/{event_id}")
    def delete_event(event_id: str, _uid: str = Depends(ctx.require_rate_limit)):
        with _conn() as conn:
            conn.execute("DELETE FROM calendar_events WHERE id=?", (event_id,))
            conn.commit()
        return {"ok": True}

    @router.post("/sync")
    def sync_calendar(_uid: str = Depends(ctx.require_rate_limit)):
        result = _sync_google_calendar()
        return result

    return router
