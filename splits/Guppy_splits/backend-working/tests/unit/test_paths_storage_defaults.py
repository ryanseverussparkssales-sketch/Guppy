from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import src.guppy.paths as paths


class PathStorageDefaultsTests(unittest.TestCase):
    def test_user_storage_defaults_live_outside_repo_when_user_data_dir_is_configured(self) -> None:
        importlib.reload(paths)
        with tempfile.TemporaryDirectory() as td:
            configured = Path(td) / "guppy-user-data"
            with patch.dict(
                os.environ,
                {
                    "GUPPY_USER_DATA_DIR": str(configured),
                    "GUPPY_MEMORY_DB_PATH": "",
                    "GUPPY_LIBRARY_DB_PATH": "",
                    "GUPPY_MEMORY_DIR": "",
                    "GUPPY_INDEX_DIR": "",
                    "GUPPY_ARTIFACTS_DIR": "",
                    "GUPPY_CHROMA_PATH": "",
                    "GUPPY_DEFAULT_MEMPALACE_DIR": "",
                    "GUPPY_LIBRARY_INDEX_DIR": "",
                    "GUPPY_LIBRARY_ARTIFACTS_DIR": "",
                },
                clear=False,
            ):
                reloaded = importlib.reload(paths)
                self.assertEqual(reloaded.USER_DATA_DIR, configured.resolve())
                self.assertEqual(reloaded.MEMORY_DB_PATH, configured.resolve() / "guppy_memory.db")
                self.assertEqual(reloaded.LIBRARY_DB_PATH, configured.resolve() / "library.db")
                self.assertEqual(reloaded.CHROMA_DIR, configured.resolve() / "indexes" / "semantic-chroma")
                self.assertEqual(reloaded.MEMPALACE_DIR, configured.resolve() / "memory" / "mempalace")
                self.assertEqual(reloaded.LIBRARY_INDEX_DIR, configured.resolve() / "indexes" / "library")
                self.assertEqual(reloaded.LIBRARY_ARTIFACTS_DIR, configured.resolve() / "artifacts" / "library")
        importlib.reload(paths)


if __name__ == "__main__":
    unittest.main()
