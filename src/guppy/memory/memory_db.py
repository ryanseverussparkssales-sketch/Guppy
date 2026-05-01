from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from utils.db_utils import open_db as _open_db

from .memory_pipeline_support import ensure_pipeline_schema


def _normalize_workspace_name(workspace_name: str | None) -> str:
    return str(workspace_name or "").strip()


_ALLOWED_MEMORY_TABLES: frozenset[str] = frozenset({"facts", "conversations"})


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    """Add *column* to *table* if it doesn't exist yet.

    Only tables in *_ALLOWED_MEMORY_TABLES* are accepted — guards against
    accidental DDL on arbitrary table names.
    """
    if table not in _ALLOWED_MEMORY_TABLES:
        raise ValueError(f"ensure_column: disallowed table {table!r}")
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def journal_event(conn: sqlite3.Connection, event_type: str, payload: dict) -> None:
    conn.execute(
        "INSERT INTO memory_events (event_type,payload,timestamp) VALUES (?,?,?)",
        (event_type, json.dumps(payload, ensure_ascii=True), datetime.now().isoformat()),
    )


def open_memory_connection(db_path: Path) -> sqlite3.Connection:
    conn = _open_db(db_path)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS facts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT DEFAULT 'general',
        key TEXT,
        value TEXT,
        normalized_key TEXT,
        normalized_value TEXT,
        created TEXT,
        updated TEXT
    )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        role TEXT,
        content TEXT,
        normalized_content TEXT,
        timestamp TEXT
    )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        company TEXT,
        email TEXT,
        phone TEXT,
        notes TEXT,
        last_contact TEXT
    )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task TEXT,
        status TEXT DEFAULT 'pending',
        due_date TEXT,
        created TEXT
    )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS memory_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT,
        payload TEXT,
        timestamp TEXT
    )"""
    )
    ensure_pipeline_schema(conn)

    ensure_column(conn, "facts", "normalized_key", "TEXT")
    ensure_column(conn, "facts", "normalized_value", "TEXT")
    ensure_column(conn, "conversations", "normalized_content", "TEXT")
    ensure_column(conn, "conversations", "workspace_name", "TEXT")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_updated ON facts(updated DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_norm_key ON facts(normalized_key)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_norm_value ON facts(normalized_value)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_conv_session_id ON conversations(session_id, id DESC)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_conv_workspace_session ON conversations(workspace_name, session_id, id DESC)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON memory_events(timestamp DESC)")
    conn.commit()
    return conn
