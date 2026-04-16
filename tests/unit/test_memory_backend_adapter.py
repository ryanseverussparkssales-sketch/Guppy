from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from src.guppy.memory import semantic
from src.guppy.memory.backend_adapter import get_memory_backend_id, get_memory_backend_impl


class MemoryBackendAdapterTests(unittest.TestCase):
    def test_backend_aliases_normalize(self) -> None:
        self.assertEqual(get_memory_backend_id("sqlite"), "semantic-sqlite")
        self.assertEqual(get_memory_backend_id("semantic-chroma"), "semantic-chroma")
        self.assertEqual(get_memory_backend_impl("mempalace"), "mempalace")

    def test_mempalace_placeholder_returns_clear_error(self) -> None:
        with patch("src.guppy.memory.semantic.mempalace_recall", return_value="MemPalace recall results:\n- choice [general] (0.900): picked") as mocked:
            with patch.dict(os.environ, {"GUPPY_SEMANTIC_BACKEND": "mempalace"}, clear=False):
                result = semantic.recall_semantic("what did we decide", n=3)
        mocked.assert_called_once()
        self.assertIn("MemPalace recall results", result)

    def test_sqlite_memory_upserts_by_key_and_recall_dedupes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            original_db_path = semantic.DB_PATH
            semantic.DB_PATH = semantic.Path(td) / "guppy_memory.db"
            try:
                with patch("src.guppy.memory.semantic._embed_text", side_effect=[[1.0, 0.0], [0.0, 1.0], [0.0, 1.0]]):
                    first = semantic.remember_semantic("preferences.concise", "Ryan prefers concise answers.", "preferences")
                    second = semantic.remember_semantic("preferences.concise", "Ryan prefers very concise answers.", "preferences")
                    recalled = semantic.recall_semantic("concise", n=5)
                self.assertIn("Stored in semantic memory", first)
                self.assertIn("Stored in semantic memory", second)
                self.assertIn("preferences.concise", recalled)
                self.assertIn("Ryan prefers very concise answers.", recalled)
                self.assertNotIn("Ryan prefers concise answers.", recalled)

                conn = semantic._conn()
                try:
                    count = conn.execute(
                        "SELECT COUNT(*) FROM semantic_memory WHERE memory_key=?",
                        ("preferences.concise",),
                    ).fetchone()[0]
                finally:
                    conn.close()
                self.assertEqual(count, 1)
            finally:
                semantic.DB_PATH = original_db_path


if __name__ == "__main__":
    unittest.main()
