from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.guppy.memory.mempalace_adapter import mempalace_recall, mempalace_remember


class MempalaceAdapterTests(unittest.TestCase):
    def test_remember_uses_collection_upsert(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            with patch("src.guppy.memory.mempalace_adapter.get_mempalace_path", return_value=Path(td)), patch(
                "src.guppy.memory.mempalace_adapter._embed_texts",
                return_value=[[0.1, 0.2, 0.3]],
            ):
                result = mempalace_remember("preferences.concise", "Ryan prefers concise answers.", "preferences")
        self.assertIn("Stored in MemPalace memory", result)

    def test_recall_formats_hits(self) -> None:
        def _fake_embed(texts):
            vectors = []
            for text in texts:
                lowered = str(text).lower()
                if "concise" in lowered:
                    vectors.append([1.0, 0.0, 0.0])
                else:
                    vectors.append([0.0, 1.0, 0.0])
            return vectors

        with tempfile.TemporaryDirectory() as td:
            with patch("src.guppy.memory.mempalace_adapter.get_mempalace_path", return_value=Path(td)), patch(
                "src.guppy.memory.mempalace_adapter._embed_texts",
                side_effect=_fake_embed,
            ):
                mempalace_remember("preferences.concise", "Ryan prefers concise answers.", "preferences")
                result = mempalace_recall("concise answers", n=3, category="preferences")
        self.assertIn("MemPalace recall results", result)
        self.assertIn("preferences.concise", result)


if __name__ == "__main__":
    unittest.main()
