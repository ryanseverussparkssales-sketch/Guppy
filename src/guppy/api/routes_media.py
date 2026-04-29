"""Media library API — qBittorrent torrent management + general media items.

Bridges to existing Calibre (/api/calibre/*) and LazyLibrarian/Prowlarr
(/api/acquisition/*) for books. This module adds:
  • qBittorrent Web API proxy (QBITTORRENT_URL env, default localhost:8080)
  • General media item catalog (movies, music, podcasts) in SQLite
  • Meeting/call recording file storage and Whisper transcription trigger

GET    /api/media/status                       — qBittorrent + services status
GET    /api/media/torrents                     — active torrent list
POST   /api/media/torrents                     — add magnet / torrent URL
DELETE /api/media/torrents/{hash}              — remove torrent
POST   /api/media/torrents/{hash}/pause        — pause
POST   /api/media/torrents/{hash}/resume       — resume
GET    /api/media/items                        — local media catalog (search, type filter)
POST   /api/media/items                        — add item to catalog
DELETE /api/media/items/{id}                   — remove from catalog
POST   /api/media/recordings/upload            — upload call/meeting recording
GET    /api/media/recordings                   — list recordings
POST   /api/media/recordings/{id}/transcribe   — trigger Whisper transcription
GET    /api/media/recordings/{id}              — recording + transcript
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel

from src.guppy.api.server_context import ServerContext

logger = logging.getLogger(__name__)

_DB_PATH    = "runtime/media.db"
_REC_DIR    = Path("runtime/recordings")

# ── DB ────────────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    os.makedirs("runtime", exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS media_items (
            id          TEXT PRIMARY KEY,
            title       TEXT NOT NULL,
            type        TEXT NOT NULL DEFAULT 'movie',  -- movie|music|podcast|other
            year        INTEGER,
            genre       TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            path        TEXT NOT NULL DEFAULT '',
            size_bytes  INTEGER,
            duration_s  INTEGER,
            tags        TEXT NOT NULL DEFAULT '[]',
            created_at  TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS recordings (
            id           TEXT PRIMARY KEY,
            title        TEXT NOT NULL DEFAULT 'Recording',
            source_type  TEXT NOT NULL DEFAULT 'call',  -- call|meeting|ambient
            source_id    TEXT,           -- voip call_id if linked
            file_path    TEXT NOT NULL,
            file_size    INTEGER,
            duration_s   INTEGER,
            transcript   TEXT NOT NULL DEFAULT '',
            transcript_status TEXT NOT NULL DEFAULT 'pending',  -- pending|processing|done|failed
            recorded_at  TEXT NOT NULL,
            created_at   TEXT NOT NULL
        );
    """)
    conn.commit()
    return conn


# ── qBittorrent helpers ───────────────────────────────────────────────────────

def _qb_url() -> str:
    return os.environ.get("QBITTORRENT_URL", "http://localhost:8080").rstrip("/")


def _qb_request(path: str, method: str = "GET", data: dict | None = None) -> Any:
    """Make a request to the qBittorrent Web API."""
    import urllib.request as _req, urllib.parse as _parse, json as _json
    url = f"{_qb_url()}/api/v2{path}"
    body = _parse.urlencode(data).encode() if data else None
    req = _req.Request(url, data=body, method=method,
                       headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with _req.urlopen(req, timeout=8) as resp:
            text = resp.read().decode(errors="replace")
            try:
                return _json.loads(text)
            except Exception:
                return text
    except Exception as exc:
        raise ConnectionError(f"qBittorrent unreachable: {exc}") from exc


def _qb_alive() -> bool:
    try:
        _qb_request("/app/version")
        return True
    except Exception:
        return False


def _fmt_torrent(t: dict) -> dict:
    return {
        "hash":         t.get("hash", ""),
        "name":         t.get("name", ""),
        "state":        t.get("state", ""),
        "progress":     round(t.get("progress", 0) * 100, 1),
        "size_bytes":   t.get("size", 0),
        "dl_speed":     t.get("dlspeed", 0),
        "ul_speed":     t.get("upspeed", 0),
        "eta":          t.get("eta", -1),
        "added_on":     t.get("added_on", 0),
        "save_path":    t.get("save_path", ""),
        "category":     t.get("category", ""),
        "num_seeds":    t.get("num_seeds", 0),
        "num_leechs":   t.get("num_leechs", 0),
    }


# ── Whisper transcription helper ──────────────────────────────────────────────

def _transcribe_recording(recording_id: str, file_path: str) -> None:
    """Run Whisper on a recording file and update the DB. Call in a thread."""
    import subprocess, sys
    try:
        with _conn() as conn:
            conn.execute(
                "UPDATE recordings SET transcript_status='processing' WHERE id=?",
                (recording_id,),
            )
            conn.commit()

        # Use faster-whisper if available, else fall back to whisper CLI
        result = subprocess.run(
            [sys.executable, "-c",
             f"from faster_whisper import WhisperModel; "
             f"m=WhisperModel('base', device='cpu', compute_type='int8'); "
             f"segs,_=m.transcribe(r'{file_path}'); "
             f"print(''.join(s.text for s in segs))"],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0:
            transcript = result.stdout.strip()
            status = "done"
        else:
            transcript = f"[transcription failed: {result.stderr[:200]}]"
            status = "failed"
    except Exception as exc:
        transcript = f"[transcription error: {exc}]"
        status = "failed"

    with _conn() as conn:
        conn.execute(
            "UPDATE recordings SET transcript=?, transcript_status=? WHERE id=?",
            (transcript, status, recording_id),
        )
        conn.commit()
    logger.info("[media] transcription %s: %s (%d chars)", recording_id[:8], status, len(transcript))


# ── Pydantic ──────────────────────────────────────────────────────────────────

class TorrentAdd(BaseModel):
    url: str          # magnet: or http(s): .torrent URL
    category: str = ""
    save_path: str = ""


class MediaItemCreate(BaseModel):
    title:       str
    type:        str = "movie"   # movie | music | podcast | other
    year:        Optional[int] = None
    genre:       str = ""
    description: str = ""
    path:        str = ""
    tags:        list[str] = []


# ── Router ────────────────────────────────────────────────────────────────────

def build_media_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/media", tags=["media"])

    @router.get("/status")
    def media_status(_uid: str = Depends(ctx.require_rate_limit)):
        qb_alive = _qb_alive()
        with _conn() as conn:
            items = conn.execute("SELECT COUNT(*) FROM media_items").fetchone()[0]
            recs  = conn.execute("SELECT COUNT(*) FROM recordings").fetchone()[0]
        return {
            "qbittorrent_available": qb_alive,
            "qbittorrent_url": _qb_url(),
            "media_item_count": items,
            "recording_count": recs,
        }

    # ── Torrents ───────────────────────────────────────────────────────────────

    @router.get("/torrents")
    def list_torrents(_uid: str = Depends(ctx.require_rate_limit)):
        try:
            data = _qb_request("/torrents/info")
            if isinstance(data, list):
                return [_fmt_torrent(t) for t in data]
            return []
        except ConnectionError as e:
            raise HTTPException(503, str(e))

    @router.post("/torrents")
    def add_torrent(body: TorrentAdd, _uid: str = Depends(ctx.require_rate_limit)):
        try:
            payload: dict[str, Any] = {"urls": body.url}
            if body.category:  payload["category"]  = body.category
            if body.save_path: payload["savepath"]  = body.save_path
            _qb_request("/torrents/add", method="POST", data=payload)
            return {"ok": True}
        except ConnectionError as e:
            raise HTTPException(503, str(e))

    @router.delete("/torrents/{torrent_hash}")
    def remove_torrent(torrent_hash: str, delete_files: bool = False,
                       _uid: str = Depends(ctx.require_rate_limit)):
        try:
            _qb_request("/torrents/delete", method="POST", data={
                "hashes": torrent_hash,
                "deleteFiles": "true" if delete_files else "false",
            })
            return {"ok": True}
        except ConnectionError as e:
            raise HTTPException(503, str(e))

    @router.post("/torrents/{torrent_hash}/pause")
    def pause_torrent(torrent_hash: str, _uid: str = Depends(ctx.require_rate_limit)):
        try:
            _qb_request("/torrents/pause", method="POST", data={"hashes": torrent_hash})
            return {"ok": True}
        except ConnectionError as e:
            raise HTTPException(503, str(e))

    @router.post("/torrents/{torrent_hash}/resume")
    def resume_torrent(torrent_hash: str, _uid: str = Depends(ctx.require_rate_limit)):
        try:
            _qb_request("/torrents/resume", method="POST", data={"hashes": torrent_hash})
            return {"ok": True}
        except ConnectionError as e:
            raise HTTPException(503, str(e))

    # ── Media catalog ──────────────────────────────────────────────────────────

    @router.get("/items")
    def list_media_items(
        type:   str = "",
        search: str = "",
        limit:  int = 100,
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        limit = min(limit, 500)
        with _conn() as conn:
            if search and type:
                rows = conn.execute(
                    "SELECT * FROM media_items WHERE type=? AND (title LIKE ? OR description LIKE ?) "
                    "ORDER BY title ASC LIMIT ?",
                    (type, f"%{search}%", f"%{search}%", limit),
                ).fetchall()
            elif type:
                rows = conn.execute(
                    "SELECT * FROM media_items WHERE type=? ORDER BY title ASC LIMIT ?",
                    (type, limit),
                ).fetchall()
            elif search:
                rows = conn.execute(
                    "SELECT * FROM media_items WHERE title LIKE ? OR description LIKE ? "
                    "ORDER BY title ASC LIMIT ?",
                    (f"%{search}%", f"%{search}%", limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM media_items ORDER BY title ASC LIMIT ?", (limit,)
                ).fetchall()
        return [
            {**dict(r), "tags": json.loads(r["tags"] or "[]")}
            for r in rows
        ]

    @router.post("/items")
    def add_media_item(body: MediaItemCreate, _uid: str = Depends(ctx.require_rate_limit)):
        mid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with _conn() as conn:
            conn.execute(
                "INSERT INTO media_items (id, title, type, year, genre, description, path, tags, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (mid, body.title, body.type, body.year, body.genre,
                 body.description, body.path, json.dumps(body.tags), now),
            )
            conn.commit()
        return {"ok": True, "id": mid}

    @router.delete("/items/{item_id}")
    def delete_media_item(item_id: str, _uid: str = Depends(ctx.require_rate_limit)):
        with _conn() as conn:
            conn.execute("DELETE FROM media_items WHERE id=?", (item_id,))
            conn.commit()
        return {"ok": True}

    # ── Recordings ────────────────────────────────────────────────────────────

    @router.post("/recordings/upload")
    async def upload_recording(
        file: UploadFile = File(...),
        source_type: str = "call",
        source_id:   str = "",
        title:       str = "",
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        _REC_DIR.mkdir(parents=True, exist_ok=True)
        rid       = str(uuid.uuid4())
        ext       = Path(file.filename or "rec.wav").suffix or ".wav"
        dest_path = _REC_DIR / f"{rid}{ext}"
        data      = await file.read()
        dest_path.write_bytes(data)

        now = datetime.now(timezone.utc).isoformat()
        rec_title = title or file.filename or f"Recording {now[:10]}"
        with _conn() as conn:
            conn.execute(
                "INSERT INTO recordings (id, title, source_type, source_id, file_path, file_size, recorded_at, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (rid, rec_title, source_type, source_id or None,
                 str(dest_path), len(data), now, now),
            )
            conn.commit()
        return {"ok": True, "id": rid, "file": str(dest_path)}

    @router.get("/recordings")
    def list_recordings(limit: int = 50, _uid: str = Depends(ctx.require_rate_limit)):
        with _conn() as conn:
            rows = conn.execute(
                "SELECT id, title, source_type, source_id, file_size, duration_s, "
                "transcript_status, recorded_at FROM recordings ORDER BY recorded_at DESC LIMIT ?",
                (min(limit, 200),),
            ).fetchall()
        return [dict(r) for r in rows]

    @router.get("/recordings/{rec_id}")
    def get_recording(rec_id: str, _uid: str = Depends(ctx.require_rate_limit)):
        with _conn() as conn:
            row = conn.execute("SELECT * FROM recordings WHERE id=?", (rec_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Recording not found")
        return dict(row)

    @router.post("/recordings/{rec_id}/transcribe")
    def transcribe_recording(rec_id: str, _uid: str = Depends(ctx.require_rate_limit)):
        with _conn() as conn:
            row = conn.execute("SELECT * FROM recordings WHERE id=?", (rec_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Recording not found")
        if row["transcript_status"] == "processing":
            return {"ok": False, "message": "Transcription already in progress"}

        import threading
        threading.Thread(
            target=_transcribe_recording,
            args=(rec_id, row["file_path"]),
            daemon=True,
        ).start()
        return {"ok": True, "message": "Transcription started (faster-whisper)"}

    return router
