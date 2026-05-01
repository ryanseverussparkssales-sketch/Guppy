from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from src.guppy.paths import MAIN_DB_PATH, ensure_user_data_dir

logger = logging.getLogger(__name__)

_DB_PATH: str = ""

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tool_call_events (
    id TEXT PRIMARY KEY,
    surface TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    tool_args_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    ok INTEGER NOT NULL DEFAULT 0,
    session_id TEXT,
    conversation_id TEXT,
    task_id TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tool_call_surface ON tool_call_events(surface);
CREATE INDEX IF NOT EXISTS idx_tool_call_session ON tool_call_events(session_id);
CREATE INDEX IF NOT EXISTS idx_tool_call_task ON tool_call_events(task_id);
"""


def _db() -> sqlite3.Connection:
    ensure_user_data_dir()
    path = _DB_PATH or str(MAIN_DB_PATH)
    conn = sqlite3.connect(path, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _ensure_schema() -> None:
    with _db() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_tool_call(
    *,
    surface: str,
    tool_name: str,
    tool_args: dict[str, Any] | None,
    result: Any,
    session_id: str | None = None,
    conversation_id: str | None = None,
    task_id: str | None = None,
) -> None:
    """Persist a tool call event to the main DB for audit/debugging."""
    if not tool_name:
        return
    _ensure_schema()
    payload_args = tool_args or {}
    try:
        ok = int(bool(getattr(result, "get", None) and result.get("ok")))
    except Exception:
        ok = 0
    try:
        with _db() as conn:
            conn.execute(
                """
                INSERT INTO tool_call_events
                (id, surface, tool_name, tool_args_json, result_json, ok,
                 session_id, conversation_id, task_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    surface,
                    tool_name,
                    json.dumps(payload_args, ensure_ascii=False, default=str),
                    json.dumps(result, ensure_ascii=False, default=str),
                    ok,
                    session_id,
                    conversation_id,
                    task_id,
                    _now(),
                ),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("Failed to log tool call %s: %s", tool_name, exc)
