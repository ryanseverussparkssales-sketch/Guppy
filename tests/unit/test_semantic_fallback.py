"""
Unit tests: semantic memory degrades gracefully to lexical recall when the
embedding server is offline (no crash, no empty result when data exists).

Strategy: patch `_embed_text` to return [] (simulating a timeout/offline
server) and verify recall still returns content via lexical matching.
"""
from __future__ import annotations

import datetime
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

try:
    from src.guppy.memory import semantic as _sem
    _SEMANTIC_AVAILABLE = True
except ImportError:
    _SEMANTIC_AVAILABLE = False


pytestmark = pytest.mark.skipif(
    not _SEMANTIC_AVAILABLE,
    reason="src.guppy.memory.semantic not importable",
)


def _seed_db(db_path: Path) -> None:
    """Write two semantic_memory rows directly so recall has data to find.

    IMPORTANT: created must be a TEXT ISO-8601 string, not a REAL unix float.
    The production age filter uses `created > datetime('now', '-N days')` which
    returns TEXT.  In SQLite, REAL < TEXT always, so a float timestamp would
    always fail the comparison and the row would never be returned.
    """
    conn = sqlite3.connect(str(db_path))
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS semantic_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_key TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '',
                value TEXT NOT NULL,
                embedding_json TEXT NOT NULL,
                created TEXT NOT NULL
            )
        """)
        conn.execute(
            "INSERT INTO semantic_memory (memory_key, category, value, embedding_json, created) VALUES (?,?,?,?,?)",
            ("key_python", "tech", "Python is a programming language", "[]", now),
        )
        conn.execute(
            "INSERT INTO semantic_memory (memory_key, category, value, embedding_json, created) VALUES (?,?,?,?,?)",
            ("key_coffee", "food", "Coffee is a popular hot drink", "[]", now),
        )
        conn.commit()
    finally:
        conn.close()


def test_recall_sqlite_falls_back_to_lexical_when_embed_offline(tmp_path: Path):
    """
    When _embed_text returns [] (offline server), _recall_sqlite should return
    a non-empty lexical result rather than raising or returning nothing.
    """
    db_path = tmp_path / "semantic.db"
    _seed_db(db_path)

    with (
        patch.object(_sem, "DB_PATH", db_path),
        patch.object(_sem, "_embed_text", return_value=[]),
    ):
        result = _sem._recall_sqlite("python programming", limit=5, cat="")

    assert result, "Expected non-empty result from lexical fallback"
    assert "python" in result.lower() or "Python" in result, (
        f"Lexical recall should surface the python entry; got: {result}"
    )


def test_recall_sqlite_lexical_fallback_no_exception(tmp_path: Path):
    """
    _recall_sqlite must NOT raise when the embed server is simulated offline.
    Asserts graceful degradation: no RuntimeError, no AttributeError.
    """
    db_path = tmp_path / "semantic.db"
    _seed_db(db_path)

    with (
        patch.object(_sem, "DB_PATH", db_path),
        patch.object(_sem, "_embed_text", return_value=[]),
    ):
        try:
            _sem._recall_sqlite("coffee hot drink", limit=3, cat="")
        except Exception as exc:
            pytest.fail(f"_recall_sqlite raised unexpectedly: {exc!r}")


def test_recall_sqlite_empty_db_offline_embed_returns_no_results(tmp_path: Path):
    """
    Empty semantic_memory table + offline embed should return a graceful
    no-results message, not a crash.
    """
    db_path = tmp_path / "semantic_empty.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS semantic_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_key TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT '',
            value TEXT NOT NULL,
            embedding_json TEXT NOT NULL,
            created TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

    with (
        patch.object(_sem, "DB_PATH", db_path),
        patch.object(_sem, "_embed_text", return_value=[]),
    ):
        result = _sem._recall_sqlite("anything", limit=5, cat="")

    assert isinstance(result, str), "Expected a string result even on empty DB"


def test_lexical_recall_helper_scores_by_word_overlap():
    """
    _lexical_recall internal helper: rows with more query-term overlaps
    should rank higher than unrelated rows.
    """
    rows = [
        ("key_a", "tech", "Python is a programming language", "[]"),
        ("key_b", "food", "spaghetti bolognese recipe", "[]"),
    ]
    result = _sem._lexical_recall(rows, query="python programming language", limit=5)
    assert "Python" in result or "python" in result, (
        f"Expected python entry to surface; got: {result}"
    )
