"""Email API — Gmail inbox viewer, thread reader, compose stub.

Local email cache in SQLite (runtime/email.db).
When GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET + GOOGLE_REFRESH_TOKEN are set,
the /sync endpoint pulls Gmail threads into the local cache. Until then the
UI shows a "Connect Gmail" state with instructions.

GET  /api/email/status            — Gmail connection status + unread count
GET  /api/email/threads           — inbox thread list (label, unread, search params)
GET  /api/email/threads/{id}      — single thread with all messages
POST /api/email/draft             — save/update draft (local only)
GET  /api/email/drafts            — list drafts
DELETE /api/email/drafts/{id}     — delete draft
POST /api/email/sync              — sync from Gmail (stub until creds configured)
"""
from __future__ import annotations

import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
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
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS email_threads (
            id               TEXT PRIMARY KEY,
            gmail_thread_id  TEXT,
            subject          TEXT NOT NULL DEFAULT '(no subject)',
            snippet          TEXT NOT NULL DEFAULT '',
            from_addr        TEXT NOT NULL DEFAULT '',
            labels           TEXT NOT NULL DEFAULT '["INBOX"]',
            unread           INTEGER NOT NULL DEFAULT 1,
            starred          INTEGER NOT NULL DEFAULT 0,
            message_count    INTEGER NOT NULL DEFAULT 1,
            last_message_at  TEXT NOT NULL,
            created_at       TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS email_messages (
            id               TEXT PRIMARY KEY,
            thread_id        TEXT NOT NULL REFERENCES email_threads(id) ON DELETE CASCADE,
            gmail_message_id TEXT,
            from_addr        TEXT NOT NULL,
            to_addrs         TEXT NOT NULL DEFAULT '',
            cc_addrs         TEXT NOT NULL DEFAULT '',
            subject          TEXT NOT NULL DEFAULT '',
            body_text        TEXT NOT NULL DEFAULT '',
            body_html        TEXT NOT NULL DEFAULT '',
            sent_at          TEXT NOT NULL,
            has_attachments  INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS email_drafts (
            id         TEXT PRIMARY KEY,
            to_addrs   TEXT NOT NULL DEFAULT '',
            cc_addrs   TEXT NOT NULL DEFAULT '',
            subject    TEXT NOT NULL DEFAULT '',
            body       TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)
    conn.commit()
    return conn


def _thread_row(r: sqlite3.Row) -> dict[str, Any]:
    import json as _json
    import arrow
    last_at = r["last_message_at"]
    try:
        last_human = arrow.get(last_at).humanize()
    except Exception:
        last_human = ""
    return {
        "id":             r["id"],
        "gmail_thread_id":r["gmail_thread_id"],
        "subject":        r["subject"],
        "snippet":        r["snippet"],
        "from_addr":      r["from_addr"],
        "labels":         _json.loads(r["labels"] or '["INBOX"]'),
        "unread":         bool(r["unread"]),
        "starred":        bool(r["starred"]),
        "message_count":  r["message_count"],
        "last_message_at":last_at,
        "last_message_at_human": last_human,
    }


def _message_row(r: sqlite3.Row) -> dict[str, Any]:
    return {
        "id":              r["id"],
        "thread_id":       r["thread_id"],
        "from_addr":       r["from_addr"],
        "to_addrs":        r["to_addrs"],
        "cc_addrs":        r["cc_addrs"],
        "subject":         r["subject"],
        "body_text":       r["body_text"],
        "body_html":       r["body_html"],
        "sent_at":         r["sent_at"],
        "has_attachments": bool(r["has_attachments"]),
    }


# ── Gmail helpers ─────────────────────────────────────────────────────────────

def _gmail_configured() -> bool:
    return bool(
        os.environ.get("GOOGLE_CLIENT_ID") and
        os.environ.get("GOOGLE_CLIENT_SECRET") and
        os.environ.get("GOOGLE_REFRESH_TOKEN")
    )


def _get_gmail_service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    creds = Credentials(
        token=None,
        refresh_token=os.environ.get("GOOGLE_REFRESH_TOKEN"),
        client_id=os.environ.get("GOOGLE_CLIENT_ID"),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=[
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.modify",
        ],
    )
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _sync_gmail() -> dict[str, Any]:
    if not _gmail_configured():
        return {
            "ok": False,
            "error": "Gmail credentials not configured",
            "hint": (
                "Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH_TOKEN "
                "environment variables."
            ),
        }
    try:
        import json as _json
        service = _get_gmail_service()
        now = datetime.now(timezone.utc).isoformat()

        result = service.users().threads().list(userId="me", maxResults=100).execute()
        thread_metas = result.get("threads", [])

        def _header(msg: dict, name: str) -> str:
            for h in msg.get("payload", {}).get("headers", []):
                if h["name"].lower() == name.lower():
                    return h["value"]
            return ""

        synced = 0
        with _conn() as conn:
            for tm in thread_metas:
                tid = tm["id"]
                thread = service.users().threads().get(
                    userId="me", id=tid, format="metadata",
                    metadataHeaders=["Subject", "From", "To", "Date"],
                ).execute()
                messages = thread.get("messages", [])
                if not messages:
                    continue

                first_msg = messages[0]
                last_msg = messages[-1]
                subject = _header(first_msg, "Subject") or "(no subject)"
                from_addr = _header(first_msg, "From") or ""
                label_ids = first_msg.get("labelIds", ["INBOX"])
                unread = "UNREAD" in label_ids
                starred = "STARRED" in label_ids
                last_ts_ms = int(last_msg.get("internalDate", 0))
                last_dt = datetime.fromtimestamp(last_ts_ms / 1000, tz=timezone.utc).isoformat()
                snippet = tm.get("snippet", "")

                existing = conn.execute(
                    "SELECT id FROM email_threads WHERE gmail_thread_id=?", (tid,)
                ).fetchone()
                if existing:
                    conn.execute(
                        "UPDATE email_threads SET subject=?, snippet=?, from_addr=?, "
                        "labels=?, unread=?, starred=?, message_count=?, last_message_at=? "
                        "WHERE gmail_thread_id=?",
                        (subject, snippet, from_addr, _json.dumps(label_ids),
                         int(unread), int(starred), len(messages), last_dt, tid),
                    )
                else:
                    lid = str(uuid.uuid4())
                    conn.execute(
                        "INSERT INTO email_threads "
                        "(id, gmail_thread_id, subject, snippet, from_addr, labels, "
                        "unread, starred, message_count, last_message_at, created_at) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (lid, tid, subject, snippet, from_addr, _json.dumps(label_ids),
                         int(unread), int(starred), len(messages), last_dt, now),
                    )
                synced += 1
            conn.commit()

        return {"ok": True, "synced_threads": synced}
    except Exception as exc:
        logger.exception("Gmail sync failed")
        return {"ok": False, "error": str(exc)}


# ── Pydantic ──────────────────────────────────────────────────────────────────

class DraftSave(BaseModel):
    to_addrs: str = ""
    cc_addrs: str = ""
    subject:  str = ""
    body:     str = ""
    draft_id: Optional[str] = None  # if set, update existing draft


# ── Router ────────────────────────────────────────────────────────────────────

def build_email_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/email", tags=["email"])

    @router.get("/status")
    def email_status(_uid: str = Depends(ctx.require_rate_limit)):
        configured = _gmail_configured()
        with _conn() as conn:
            total   = conn.execute("SELECT COUNT(*) FROM email_threads").fetchone()[0]
            unread  = conn.execute("SELECT COUNT(*) FROM email_threads WHERE unread=1").fetchone()[0]
            drafts  = conn.execute("SELECT COUNT(*) FROM email_drafts").fetchone()[0]
        return {
            "gmail_configured": configured,
            "total_threads":    total,
            "unread_count":     unread,
            "draft_count":      drafts,
            "connect_hint": (
                "Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH_TOKEN "
                "to connect Gmail." if not configured else None
            ),
        }

    @router.get("/threads")
    def list_threads(
        label:   str = "INBOX",
        unread:  str = "",
        starred: str = "",
        search:  str = "",
        limit:   int = 50,
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        limit = min(limit, 200)
        with _conn() as conn:
            if search:
                rows = conn.execute(
                    "SELECT * FROM email_threads WHERE subject LIKE ? OR snippet LIKE ? OR from_addr LIKE ? "
                    "ORDER BY last_message_at DESC LIMIT ?",
                    (f"%{search}%", f"%{search}%", f"%{search}%", limit),
                ).fetchall()
            elif starred == "1":
                rows = conn.execute(
                    "SELECT * FROM email_threads WHERE starred=1 "
                    "ORDER BY last_message_at DESC LIMIT ?", (limit,)
                ).fetchall()
            elif unread == "1":
                rows = conn.execute(
                    "SELECT * FROM email_threads WHERE unread=1 "
                    "ORDER BY last_message_at DESC LIMIT ?", (limit,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM email_threads ORDER BY last_message_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [_thread_row(r) for r in rows]

    @router.get("/threads/{thread_id}")
    def get_thread(thread_id: str, _uid: str = Depends(ctx.require_rate_limit)):
        with _conn() as conn:
            thread = conn.execute(
                "SELECT * FROM email_threads WHERE id=?", (thread_id,)
            ).fetchone()
            if not thread:
                raise HTTPException(404, "Thread not found")
            messages = conn.execute(
                "SELECT * FROM email_messages WHERE thread_id=? ORDER BY sent_at ASC",
                (thread_id,),
            ).fetchall()
            # Mark as read
            conn.execute("UPDATE email_threads SET unread=0 WHERE id=?", (thread_id,))
            conn.commit()
        return {
            **_thread_row(thread),
            "messages": [_message_row(m) for m in messages],
        }

    @router.post("/draft")
    def save_draft(body: DraftSave, _uid: str = Depends(ctx.require_rate_limit)):
        now = datetime.now(timezone.utc).isoformat()
        with _conn() as conn:
            if body.draft_id:
                conn.execute(
                    "UPDATE email_drafts SET to_addrs=?, cc_addrs=?, subject=?, body=?, updated_at=? WHERE id=?",
                    (body.to_addrs, body.cc_addrs, body.subject, body.body, now, body.draft_id),
                )
                conn.commit()
                return {"ok": True, "id": body.draft_id}
            did = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO email_drafts (id, to_addrs, cc_addrs, subject, body, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (did, body.to_addrs, body.cc_addrs, body.subject, body.body, now, now),
            )
            conn.commit()
        return {"ok": True, "id": did}

    @router.get("/drafts")
    def list_drafts(_uid: str = Depends(ctx.require_rate_limit)):
        with _conn() as conn:
            rows = conn.execute(
                "SELECT * FROM email_drafts ORDER BY updated_at DESC"
            ).fetchall()
        return [
            {"id": r["id"], "to_addrs": r["to_addrs"], "subject": r["subject"],
             "body": r["body"][:200], "updated_at": r["updated_at"]}
            for r in rows
        ]

    @router.delete("/drafts/{draft_id}")
    def delete_draft(draft_id: str, _uid: str = Depends(ctx.require_rate_limit)):
        with _conn() as conn:
            conn.execute("DELETE FROM email_drafts WHERE id=?", (draft_id,))
            conn.commit()
        return {"ok": True}

    @router.post("/sync")
    def sync_email(_uid: str = Depends(ctx.require_rate_limit)):
        return _sync_gmail()

    return router
