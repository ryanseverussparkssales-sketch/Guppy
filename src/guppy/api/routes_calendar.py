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
from src.guppy.paths import MAIN_DB_PATH

logger = logging.getLogger(__name__)

_DB_PATH = str(MAIN_DB_PATH)

# ── DB ────────────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    MAIN_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
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


# ── Google Calendar ───────────────────────────────────────────────────────────

def _google_connected() -> bool:
    creds_path = os.environ.get("GOOGLE_CALENDAR_CREDENTIALS", "")
    has_file = bool(creds_path and os.path.exists(creds_path))
    has_env = bool(
        os.environ.get("GOOGLE_CLIENT_ID") and
        os.environ.get("GOOGLE_CLIENT_SECRET") and
        os.environ.get("GOOGLE_REFRESH_TOKEN")
    )
    return has_file or has_env


def _get_calendar_service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds_path = os.environ.get("GOOGLE_CALENDAR_CREDENTIALS", "")
    if creds_path and os.path.exists(creds_path):
        import json as _json
        with open(creds_path) as f:
            creds_data = _json.load(f)
        creds = Credentials.from_authorized_user_info(creds_data)
    else:
        creds = Credentials(
            token=None,
            refresh_token=os.environ.get("GOOGLE_REFRESH_TOKEN"),
            client_id=os.environ.get("GOOGLE_CLIENT_ID"),
            client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
            token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
        )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _sync_google_calendar() -> dict[str, Any]:
    if not _google_connected():
        return {
            "ok": False,
            "error": (
                "No Google credentials found. Set GOOGLE_CALENDAR_CREDENTIALS (path to token "
                "JSON file) or GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET + GOOGLE_REFRESH_TOKEN."
            ),
        }
    try:
        service = _get_calendar_service()
        now = datetime.now(timezone.utc)
        db_now = now.isoformat()
        time_max = (now + timedelta(days=90)).isoformat()

        events_result = service.events().list(
            calendarId="primary",
            timeMin=db_now,
            timeMax=time_max,
            maxResults=250,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        events = events_result.get("items", [])

        synced = 0
        with _conn() as conn:
            for event in events:
                geid = event["id"]
                title = event.get("summary", "(no title)")
                description = event.get("description", "")
                location = event.get("location", "")
                start = event["start"].get("dateTime", event["start"].get("date", ""))
                end = event["end"].get("dateTime", event["end"].get("date", ""))
                all_day = "date" in event["start"]

                existing = conn.execute(
                    "SELECT id FROM calendar_events WHERE google_event_id=?", (geid,)
                ).fetchone()
                if existing:
                    conn.execute(
                        "UPDATE calendar_events SET title=?, description=?, location=?, "
                        "start_time=?, end_time=?, all_day=?, updated_at=? "
                        "WHERE google_event_id=?",
                        (title, description, location, start, end, int(all_day), db_now, geid),
                    )
                else:
                    eid = str(uuid.uuid4())
                    conn.execute(
                        "INSERT INTO calendar_events "
                        "(id, title, description, location, start_time, end_time, all_day, "
                        "color, google_event_id, calendar_id, recurrence, created_at, updated_at) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (eid, title, description, location, start, end, int(all_day),
                         "primary", geid, "google", "", db_now, db_now),
                    )
                synced += 1
            conn.commit()

        return {"ok": True, "synced_events": synced}
    except Exception as exc:
        logger.exception("Google Calendar sync failed")
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
        has_file = bool(os.environ.get("GOOGLE_CALENDAR_CREDENTIALS"))
        has_env  = bool(os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_REFRESH_TOKEN"))
        return {
            "google_connected":    connected,
            "google_creds_file":   has_file,
            "google_creds_env":    has_env,
            "local_event_count":   total,
            "sync_hint": (
                "Set GOOGLE_CALENDAR_CREDENTIALS (token JSON path) "
                "or GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET + GOOGLE_REFRESH_TOKEN."
                if not connected else "Google Calendar credentials found — ready to sync."
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


def _get_upcoming_events(horizon_minutes: int = 60) -> list[dict]:
    """Return events starting within the next *horizon_minutes* minutes.

    Used by the proactive companion nudge in routes_surface._background_loop.
    Returns a list of dicts with keys: title, starts_in_minutes, location.
    """
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(minutes=horizon_minutes)
    try:
        with _conn() as conn:
            rows = conn.execute(
                """SELECT title, start_time, location FROM calendar_events
                   WHERE start_time >= ? AND start_time <= ?
                   ORDER BY start_time ASC LIMIT 5""",
                (now.isoformat(), horizon.isoformat()),
            ).fetchall()
    except Exception:
        return []
    result = []
    for row in rows:
        try:
            start = datetime.fromisoformat(str(row["start_time"]))
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            delta_minutes = max(0, int((start - now).total_seconds() / 60))
            result.append({
                "title": row["title"] or "Untitled event",
                "starts_in_minutes": delta_minutes,
                "location": row["location"] or "",
            })
        except Exception:
            continue
    return result
