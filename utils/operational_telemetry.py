"""Operational telemetry sink.

Keeps JSONL as human-readable debug/event stream while mirroring key events
into SQLite for low-cost repeated queries and dashboards.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from utils.db_utils import open_db as _open_db

_RUNTIME = Path(__file__).resolve().parent.parent / "runtime"
_DB_PATH = _RUNTIME / "ops_telemetry.sqlite3"
_LOCK = threading.Lock()
_SQLITE_TIMEOUT_SECONDS = float(os.environ.get("GUPPY_SQLITE_TIMEOUT_SECONDS", "10.0"))
_SQLITE_BUSY_TIMEOUT_MS = int(os.environ.get("GUPPY_SQLITE_BUSY_TIMEOUT_MS", "5000"))
_SQLITE_SYNC_MODE = (os.environ.get("GUPPY_SQLITE_SYNC_MODE", "NORMAL") or "NORMAL").strip().upper()


def _enabled() -> bool:
    backend = (os.environ.get("GUPPY_TELEMETRY_BACKEND", "sqlite+jsonl") or "").strip().lower()
    return "sqlite" in backend


def _get_conn() -> sqlite3.Connection:
    conn = _open_db(
        _DB_PATH,
        timeout=_SQLITE_TIMEOUT_SECONDS,
        busy_timeout_ms=_SQLITE_BUSY_TIMEOUT_MS,
        sync_mode=_SQLITE_SYNC_MODE,
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS operational_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            stream TEXT NOT NULL,
            event TEXT NOT NULL,
            level TEXT,
            payload_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_operational_events_stream_ts "
        "ON operational_events(stream, ts DESC)"
    )
    return conn


def log_operational_event(stream: str, event: str, payload: dict[str, Any], level: str = "info") -> None:
    if not _enabled():
        return
    try:
        with _LOCK:
            conn = _get_conn()
            try:
                conn.execute(
                    "INSERT INTO operational_events (ts, stream, event, level, payload_json) VALUES (?, ?, ?, ?, ?)",
                    (
                        datetime.now(timezone.utc).isoformat(),
                        str(stream or "unknown"),
                        str(event or "event"),
                        str(level or "info"),
                        json.dumps(payload, ensure_ascii=True),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
    except Exception:
        # Telemetry should never break product flow.
        return
