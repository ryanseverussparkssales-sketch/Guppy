"""VoIP call log API — Quo (formerly OpenPhone) integration.

Stores inbound/outbound call records in SQLite. Quo webhook receives
real-time call events and auto-logs them. The /sync endpoint pulls
recent calls from the Quo REST API.

GET    /api/voip/calls                — list recent calls (local DB)
POST   /api/voip/calls                — log a call manually
PATCH  /api/voip/calls/{id}           — update notes / status
DELETE /api/voip/calls/{id}           — delete call record
POST   /api/voip/sync                 — pull recent calls from Quo API
POST   /api/voip/webhook/quo          — Quo event webhook (call.completed etc.)
GET    /api/voip/status               — Quo integration status

Environment:
    QUO_API_KEY            — Quo API key (Settings → API in Quo)
    QUO_PHONE_NUMBER_ID    — Quo phone number ID (format: PN...)
    QUO_WEBHOOK_SECRET     — Webhook signing secret (base64, from Settings → Webhooks)
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from src.guppy.api.server_context import ServerContext

_QUO_API_BASE = "https://api.openphone.com"

# ── DB ────────────────────────────────────────────────────────────────────────

from src.guppy.paths import MAIN_DB_PATH
_DB_PATH = str(MAIN_DB_PATH)


def _conn() -> sqlite3.Connection:
    MAIN_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
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
            external_id  TEXT
        )
    """)
    conn.commit()
    # Migration: rename legacy twilio_sid column if it exists
    try:
        conn.execute("ALTER TABLE voip_calls RENAME COLUMN twilio_sid TO external_id")
        conn.commit()
    except Exception:
        pass
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
        "external_id":  r["external_id"],
    }


# ── Quo helpers ───────────────────────────────────────────────────────────────

def _quo_api_key() -> str:
    return os.environ.get("QUO_API_KEY", "").strip()


def _quo_phone_number_id() -> str:
    return os.environ.get("QUO_PHONE_NUMBER_ID", "").strip()


def _quo_webhook_secret() -> str:
    return os.environ.get("QUO_WEBHOOK_SECRET", "").strip()


def _verify_quo_signature(raw_body: bytes, signature_header: str) -> bool:
    """Verify Quo HMAC-SHA256 webhook signature.

    Header format: "hmac;1;{unix_timestamp};{base64_signature}"
    Signed message: "{timestamp}.{raw_body}"
    """
    secret = _quo_webhook_secret()
    if not secret:
        return True  # no secret configured → skip verification (dev mode)
    try:
        parts = signature_header.split(";")
        if len(parts) != 4 or parts[0] != "hmac":
            return False
        timestamp = parts[2]
        provided_sig = parts[3]
        key = base64.b64decode(secret)
        message = f"{timestamp}.".encode() + raw_body
        expected = base64.b64encode(
            hmac.new(key, message, hashlib.sha256).digest()
        ).decode()
        return hmac.compare_digest(expected, provided_sig)
    except Exception:
        return False


def _fetch_quo_calls(max_results: int = 50) -> list[dict]:
    """Pull recent calls from the Quo REST API."""
    import urllib.request
    import json

    api_key = _quo_api_key()
    phone_id = _quo_phone_number_id()
    if not api_key or not phone_id:
        return []

    from urllib.parse import urlencode
    qs = urlencode({"phoneNumberId": phone_id, "maxResults": min(max_results, 100)})
    url = f"{_QUO_API_BASE}/calls?{qs}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": api_key, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    return data.get("data", [])


def _upsert_quo_call(call: dict) -> None:
    """Insert or ignore a call record from the Quo API payload."""
    ext_id     = call.get("id", "")
    direction  = "inbound" if call.get("direction") == "incoming" else "outbound"
    status     = call.get("status", "completed")
    # Quo status values: completed, missed, voicemail → map to our schema
    if status not in ("completed", "missed", "failed", "incoming"):
        status = "completed"
    duration   = call.get("duration")
    created_at = call.get("createdAt", datetime.now(timezone.utc).isoformat())
    # First participant that isn't our own number
    participants = call.get("participants", [])
    phone = next(
        (p.get("phoneNumber", "") for p in participants if p.get("direction") != "self"),
        participants[0].get("phoneNumber", "") if participants else "",
    )
    cid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO voip_calls "
            "(id, phone_number, direction, status, duration_s, called_at, created_at, external_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (cid, phone, direction, status, duration, created_at, now, ext_id),
        )
        conn.commit()


# ── Pydantic ──────────────────────────────────────────────────────────────────

class CallCreate(BaseModel):
    phone_number: str
    contact_name: str = ""
    direction:    str = "outbound"
    status:       str = "completed"
    duration_s:   Optional[int] = None
    notes:        str = ""
    called_at:    str = ""


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
        cid    = str(uuid.uuid4())
        now    = datetime.now(timezone.utc).isoformat()
        called = body.called_at or now
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
        if body.notes      is not None: updates["notes"]      = body.notes
        if body.status     is not None: updates["status"]     = body.status
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

    # ── Quo sync ──────────────────────────────────────────────────────────────

    @router.post("/sync")
    async def sync_from_quo(_uid: str = Depends(ctx.require_rate_limit)):
        """Pull recent calls from Quo API and upsert into local DB."""
        import asyncio
        if not _quo_api_key():
            raise HTTPException(400, "QUO_API_KEY not configured")
        if not _quo_phone_number_id():
            raise HTTPException(400, "QUO_PHONE_NUMBER_ID not configured")
        try:
            calls = await asyncio.to_thread(_fetch_quo_calls, 50)
        except Exception as exc:
            raise HTTPException(502, f"Quo API error: {exc}")
        for call in calls:
            try:
                _upsert_quo_call(call)
            except Exception:
                pass
        return {"ok": True, "synced": len(calls)}

    # ── Quo webhook ───────────────────────────────────────────────────────────

    @router.post("/webhook/quo")
    async def quo_webhook(request: Request):
        """Receive Quo event webhooks (call.completed, call.ringing, etc.).

        Quo POSTs JSON here when call status changes. Register this URL in
        Quo Settings → Webhooks. No auth dependency — Quo calls this directly;
        signature verified via openphone-signature header.
        """
        raw_body = await request.body()
        sig_header = request.headers.get("openphone-signature", "")

        if _quo_webhook_secret() and not _verify_quo_signature(raw_body, sig_header):
            raise HTTPException(401, "Invalid webhook signature")

        import json
        try:
            payload = json.loads(raw_body)
        except Exception:
            return {"ok": False, "error": "invalid JSON"}

        event_type = payload.get("type", "")
        data_obj   = payload.get("data", {}).get("object", {})

        if event_type == "call.completed":
            _upsert_quo_call(data_obj)
        elif event_type in ("message.received", "message.delivered"):
            pass  # future: log messages
        elif event_type in ("call.summary.completed", "call.transcript.completed"):
            pass  # future: attach transcript to call note

        return {"ok": True, "event": event_type}

    # ── Status ────────────────────────────────────────────────────────────────

    @router.get("/status")
    def voip_status(_uid: str = Depends(ctx.require_rate_limit)):
        configured = bool(_quo_api_key())
        phone_id   = _quo_phone_number_id()
        with _conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM voip_calls").fetchone()[0]
        return {
            "provider":        "quo",
            "quo_configured":  configured,
            "phone_number_id": phone_id or None,
            "total_calls":     total,
        }

    return router
