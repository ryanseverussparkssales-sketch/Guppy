"""VoIP call log API.

Stores inbound/outbound call records in SQLite. Twilio webhook stub is
included for future live integration — it logs the call metadata and
can trigger CRM note creation.

GET    /api/voip/calls                — list recent calls
POST   /api/voip/calls                — log a call manually
PATCH  /api/voip/calls/{id}           — update notes / status
DELETE /api/voip/calls/{id}           — delete call record
POST   /api/voip/webhook/twilio       — Twilio status callback stub
GET    /api/voip/status               — Twilio integration status
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from src.guppy.api.server_context import ServerContext

# ── DB ────────────────────────────────────────────────────────────────────────

_DB_PATH = "runtime/voip.db"


def _conn() -> sqlite3.Connection:
    import os
    os.makedirs("runtime", exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS voip_calls (
            id           TEXT PRIMARY KEY,
            contact_name TEXT NOT NULL DEFAULT '',
            phone_number TEXT NOT NULL,
            direction    TEXT NOT NULL DEFAULT 'outbound',
            status       TEXT NOT NULL DEFAULT 'completed',
            duration_s   INTEGER,
            notes        TEXT NOT NULL DEFAULT '',
            called_at    TEXT NOT NULL,
            created_at   TEXT NOT NULL,
            twilio_sid   TEXT
        )
    """)
    conn.commit()
    return conn


def _row_to_dict(r: sqlite3.Row) -> dict[str, Any]:
    return {
        "id":           r["id"],
        "contact_name": r["contact_name"],
        "phone_number": r["phone_number"],
        "direction":    r["direction"],
        "status":       r["status"],
        "duration_s":   r["duration_s"],
        "notes":        r["notes"],
        "called_at":    r["called_at"],
        "created_at":   r["created_at"],
        "twilio_sid":   r["twilio_sid"],
    }


# ── Pydantic ──────────────────────────────────────────────────────────────────

class CallCreate(BaseModel):
    phone_number: str
    contact_name: str = ""
    direction:    str = "outbound"   # 'inbound' | 'outbound'
    status:       str = "completed"  # 'completed' | 'missed' | 'failed' | 'incoming'
    duration_s:   Optional[int] = None
    notes:        str = ""
    called_at:    str = ""           # ISO timestamp; defaults to now


class CallUpdate(BaseModel):
    notes:      Optional[str] = None
    status:     Optional[str] = None
    duration_s: Optional[int] = None


# ── Router ────────────────────────────────────────────────────────────────────

def build_voip_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/voip", tags=["voip"])

    @router.get("/calls")
    def list_calls(
        limit: int = 50,
        direction: str = "",
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        with _conn() as conn:
            if direction:
                rows = conn.execute(
                    "SELECT * FROM voip_calls WHERE direction=? ORDER BY called_at DESC LIMIT ?",
                    (direction, min(limit, 200)),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM voip_calls ORDER BY called_at DESC LIMIT ?",
                    (min(limit, 200),),
                ).fetchall()
        return [_row_to_dict(r) for r in rows]

    @router.post("/calls")
    def log_call(body: CallCreate, _uid: str = Depends(ctx.require_rate_limit)):
        cid      = str(uuid.uuid4())
        now      = datetime.now(timezone.utc).isoformat()
        called   = body.called_at or now
        with _conn() as conn:
            conn.execute(
                "INSERT INTO voip_calls "
                "(id, contact_name, phone_number, direction, status, duration_s, notes, called_at, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (cid, body.contact_name, body.phone_number, body.direction,
                 body.status, body.duration_s, body.notes, called, now),
            )
            conn.commit()
        return {"ok": True, "id": cid}

    @router.patch("/calls/{call_id}")
    def update_call(call_id: str, body: CallUpdate, _uid: str = Depends(ctx.require_rate_limit)):
        updates = {}
        if body.notes  is not None: updates["notes"]      = body.notes
        if body.status is not None: updates["status"]     = body.status
        if body.duration_s is not None: updates["duration_s"] = body.duration_s
        if not updates:
            raise HTTPException(400, "Nothing to update")
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values     = list(updates.values()) + [call_id]
        with _conn() as conn:
            conn.execute(f"UPDATE voip_calls SET {set_clause} WHERE id=?", values)
            conn.commit()
        return {"ok": True}

    @router.delete("/calls/{call_id}")
    def delete_call(call_id: str, _uid: str = Depends(ctx.require_rate_limit)):
        with _conn() as conn:
            conn.execute("DELETE FROM voip_calls WHERE id=?", (call_id,))
            conn.commit()
        return {"ok": True}

    # ── Twilio webhook stub ────────────────────────────────────────────────────

    @router.post("/webhook/twilio")
    async def twilio_webhook(request: Request, _uid: str = Depends(ctx.require_rate_limit)):
        """
        Twilio StatusCallback webhook. In production, Twilio POSTs form data here
        when a call status changes. We log it and optionally create a CRM note.

        Form fields: CallSid, CallStatus, From, To, Direction, Duration
        """
        # Accept the raw request to parse form data
        form = await request.form() if hasattr(request, "form") else {}
        sid      = form.get("CallSid", "")
        status   = form.get("CallStatus", "completed")
        from_    = form.get("From", "")
        to       = form.get("To", "")
        direction = "inbound" if form.get("Direction", "").startswith("inbound") else "outbound"
        duration  = int(form.get("Duration", 0) or 0)

        if sid:
            cid = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()
            phone = from_ if direction == "inbound" else to
            with _conn() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO voip_calls "
                    "(id, phone_number, direction, status, duration_s, called_at, created_at, twilio_sid) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (cid, phone, direction, status, duration or None, now, now, sid),
                )
                conn.commit()

        # Twilio expects a TwiML response (even empty)
        return {"ok": True, "sid": sid}

    @router.get("/status")
    def voip_status(_uid: str = Depends(ctx.require_rate_limit)):
        import os
        twilio_configured = bool(
            os.environ.get("TWILIO_ACCOUNT_SID") and
            os.environ.get("TWILIO_AUTH_TOKEN")
        )
        with _conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM voip_calls").fetchone()[0]
        return {
            "twilio_configured": twilio_configured,
            "total_calls": total,
        }

    return router
