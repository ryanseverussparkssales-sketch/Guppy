"""Thread-local SQLite connection helpers.

All connections are opened with:
- WAL journal mode (concurrent reads + writes)
- foreign_keys = ON
- busy_timeout = 5000 ms
- synchronous = NORMAL (safe with WAL)
- temp_store = MEMORY
"""

from __future__ import annotations

import contextlib
import sqlite3
import threading
from pathlib import Path
from typing import Generator

from src.guppy.paths import MAIN_DB_PATH, MEMORY_DB_PATH, RUNTIME_DIR

# ---------------------------------------------------------------------------
# Canonical DB paths
# ---------------------------------------------------------------------------

TRIAGE_DB_PATH: Path = RUNTIME_DIR / "triage.db"

# ---------------------------------------------------------------------------
# Connection pragmas
# ---------------------------------------------------------------------------

_PRAGMAS = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;
PRAGMA synchronous=NORMAL;
PRAGMA temp_store=MEMORY;
"""


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    conn.executescript(_PRAGMAS)


# ---------------------------------------------------------------------------
# Thread-local caches
# ---------------------------------------------------------------------------

_main_local = threading.local()
_memory_local = threading.local()


def _open(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    _apply_pragmas(conn)
    return conn


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def get_main_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager yielding a connection to ``guppy_main.db``."""
    if not hasattr(_main_local, "conn") or _main_local.conn is None:
        _main_local.conn = _open(MAIN_DB_PATH)
    yield _main_local.conn


@contextlib.contextmanager
def get_memory_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager yielding a connection to ``guppy_memory.db``."""
    if not hasattr(_memory_local, "conn") or _memory_local.conn is None:
        _memory_local.conn = _open(MEMORY_DB_PATH)
    yield _memory_local.conn


@contextlib.contextmanager
def get_triage_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager yielding a fresh connection to ``triage.db``.

    Triage uses separate short-lived connections (codespace module manages
    its own thread local) — we open a fresh one per call here for callers
    outside the codespace package.
    """
    TRIAGE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(TRIAGE_DB_PATH), check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    _apply_pragmas(conn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Convenience: open any path with standard pragmas (for migrations / tests)
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def open_db(path: Path | str) -> Generator[sqlite3.Connection, None, None]:
    """Open *any* SQLite file with standard pragmas.  Commits on clean exit."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p), check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    _apply_pragmas(conn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
