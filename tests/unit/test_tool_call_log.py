"""Unit tests for src.guppy.api.tool_call_log.

Runs offline — uses a temp SQLite DB injected via module-level _DB_PATH.
Verifies that log_tool_call() persists rows and that all three surfaces
(companion, workspace, codespace) produce queryable entries.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest


@pytest.fixture()
def tool_log_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Return (module, db_path) with _DB_PATH pointed at a fresh temp file."""
    import importlib

    db_path = tmp_path / "tool_log_test.db"
    mod = importlib.import_module("src.guppy.api.tool_call_log")
    monkeypatch.setattr(mod, "_DB_PATH", str(db_path))
    yield mod, db_path


def _query_all(db_path: Path) -> list[dict]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM tool_call_events ORDER BY created_at").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def test_log_tool_call_writes_row(tool_log_db) -> None:
    mod, db_path = tool_log_db
    mod.log_tool_call(
        surface="workspace",
        tool_name="web_search",
        tool_args={"query": "test"},
        result={"ok": True, "results": []},
        session_id="sess-001",
    )
    rows = _query_all(db_path)
    assert len(rows) == 1
    r = rows[0]
    assert r["surface"] == "workspace"
    assert r["tool_name"] == "web_search"
    assert json.loads(r["tool_args_json"]) == {"query": "test"}
    assert r["ok"] == 1
    assert r["session_id"] == "sess-001"


def test_log_tool_call_all_three_surfaces(tool_log_db) -> None:
    mod, db_path = tool_log_db
    for surface in ("companion", "workspace", "codespace"):
        mod.log_tool_call(
            surface=surface,
            tool_name="file_read",
            tool_args={"path": "/tmp/x"},
            result="file contents",
        )
    rows = _query_all(db_path)
    assert len(rows) == 3
    surfaces = {r["surface"] for r in rows}
    assert surfaces == {"companion", "workspace", "codespace"}


def test_log_tool_call_empty_name_is_noop(tool_log_db) -> None:
    mod, db_path = tool_log_db
    mod.log_tool_call(
        surface="companion",
        tool_name="",
        tool_args=None,
        result=None,
    )
    # schema table may not even exist — check that no rows written
    if db_path.exists():
        try:
            rows = _query_all(db_path)
        except sqlite3.OperationalError:
            rows = []
        assert len(rows) == 0


def test_log_tool_call_ok_flag_false_when_result_has_no_ok(tool_log_db) -> None:
    mod, db_path = tool_log_db
    mod.log_tool_call(
        surface="codespace",
        tool_name="shell_run",
        tool_args={"command": "git status"},
        result={"stdout": "nothing to commit", "ok": False},
    )
    rows = _query_all(db_path)
    assert len(rows) == 1
    assert rows[0]["ok"] == 0


def test_log_tool_call_result_non_dict_serialises_safely(tool_log_db) -> None:
    mod, db_path = tool_log_db
    mod.log_tool_call(
        surface="workspace",
        tool_name="contacts_search",
        tool_args={"q": "ryan"},
        result=["Alice", "Bob"],  # list, not dict
    )
    rows = _query_all(db_path)
    assert len(rows) == 1
    assert json.loads(rows[0]["result_json"]) == ["Alice", "Bob"]
