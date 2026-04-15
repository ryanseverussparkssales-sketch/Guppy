from __future__ import annotations

import os
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


if __name__ == "__main__":
    unittest.main()
