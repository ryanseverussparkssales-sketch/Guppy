"""Centralised SQLite access layer for Guppy.

All application code should use the helpers here instead of calling
``sqlite3.connect`` directly.  The three canonical databases are:

* ``guppy_main.db``  — primary app data (chat, workspace, library, …)
* ``guppy_memory.db`` — memory / fact store
* ``triage.db``       — codespace-only triage + self-improve history

Usage::

    from src.guppy.db import get_main_db, get_memory_db

    with get_main_db() as conn:
        conn.execute("SELECT 1")
"""

from src.guppy.db.connections import get_main_db, get_memory_db, get_triage_db

__all__ = ["get_main_db", "get_memory_db", "get_triage_db"]
