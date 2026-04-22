"""utils/db_utils.py — Production-grade SQLite connection factory.

Every database path in the system should open connections through this module
so that WAL mode, busy timeout, foreign-key enforcement, and synchronous level
are applied consistently rather than being re-implemented (or forgotten) at
each call site.

Usage
-----
    from utils.db_utils import open_db

    conn = open_db(db_path)
    try:
        conn.execute("INSERT INTO ...")
        conn.commit()
    finally:
        conn.close()

    # Context-manager form (commit on exit, rollback on exception):
    with open_db(db_path) as conn:
        conn.execute("INSERT INTO ...")

Schema helpers
--------------
Pass *schema_sql* to run one-time DDL (CREATE TABLE IF NOT EXISTS …) before
returning the connection.  This keeps each module's schema co-located with its
data-access code while still benefiting from the shared pragma baseline.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Optional

# ── Defaults (overridden by environment variables) ────────────────────────────

_SQLITE_TIMEOUT_SECONDS: float = float(os.environ.get("GUPPY_SQLITE_TIMEOUT_SECONDS", "10.0"))
_SQLITE_BUSY_TIMEOUT_MS: int = int(os.environ.get("GUPPY_SQLITE_BUSY_TIMEOUT_MS", "5000"))
_SQLITE_SYNC_MODE: str = (
    os.environ.get("GUPPY_SQLITE_SYNC_MODE", "NORMAL") or "NORMAL"
).strip().upper()


def open_db(
    path: "str | Path",
    *,
    timeout: Optional[float] = None,
    busy_timeout_ms: Optional[int] = None,
    sync_mode: Optional[str] = None,
    schema_sql: Optional[str] = None,
) -> sqlite3.Connection:
    """Open a SQLite connection with production durability pragmas.

    Pragmas applied on every connection:

    - ``journal_mode=WAL``    — concurrent readers + writer without blocking
    - ``synchronous``         — configurable; defaults to NORMAL (safe default)
    - ``busy_timeout``        — ms to wait before raising ``OperationalError``
    - ``foreign_keys=ON``     — enforce referential integrity
    - ``temp_store=MEMORY``   — keep temp tables in RAM

    Parameters
    ----------
    path:
        Absolute or relative path to the ``.sqlite3`` file.  Parent
        directories are created if they do not exist.
    timeout:
        Seconds to wait when the database lock is held at ``connect()`` time.
        Defaults to ``GUPPY_SQLITE_TIMEOUT_SECONDS`` env var (10 s).
    busy_timeout_ms:
        Milliseconds for the ``busy_timeout`` PRAGMA after connection.
        Defaults to ``GUPPY_SQLITE_BUSY_TIMEOUT_MS`` env var (5000 ms).
    sync_mode:
        SQLite ``synchronous`` mode: ``FULL``, ``NORMAL``, or ``OFF``.
        Defaults to ``GUPPY_SQLITE_SYNC_MODE`` env var (``NORMAL``).
    schema_sql:
        Optional DDL to execute immediately after the pragmas (e.g.
        ``CREATE TABLE IF NOT EXISTS …``).  Committed before returning.
    """
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    t = timeout if timeout is not None else _SQLITE_TIMEOUT_SECONDS
    bt = busy_timeout_ms if busy_timeout_ms is not None else _SQLITE_BUSY_TIMEOUT_MS
    sm = (sync_mode or _SQLITE_SYNC_MODE).strip().upper()

    conn = sqlite3.connect(db_path, timeout=t)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(f"PRAGMA synchronous={sm}")
    conn.execute(f"PRAGMA busy_timeout={bt}")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA temp_store=MEMORY")

    if schema_sql:
        conn.executescript(schema_sql)
        conn.commit()

    return conn
