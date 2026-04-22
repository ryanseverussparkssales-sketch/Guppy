from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import backup_seed_vault


class BackupSeedVaultTests(unittest.TestCase):
    def test_collect_candidates_includes_external_user_data_storage(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source_root = root / "repo"
            source_root.mkdir(parents=True, exist_ok=True)
            (source_root / "README.md").write_text("repo", encoding="utf-8")

            user_data = root / "user-data"
            user_data.mkdir(parents=True, exist_ok=True)
            memory_db = user_data / "guppy_memory.db"
            library_db = user_data / "library.db"
            chroma_dir = user_data / "indexes" / "semantic-chroma"
            mempalace_dir = user_data / "memory" / "mempalace"
            chroma_dir.mkdir(parents=True, exist_ok=True)
            mempalace_dir.mkdir(parents=True, exist_ok=True)
            memory_db.write_text("memory", encoding="utf-8")
            library_db.write_text("library", encoding="utf-8")
            (chroma_dir / "chroma.sqlite3").write_text("chroma", encoding="utf-8")
            (mempalace_dir / "mempalace_drawers.sqlite3").write_text("palace", encoding="utf-8")

            with patch.object(backup_seed_vault, "SOURCE_ROOT", source_root), patch.object(
                backup_seed_vault, "DEFAULT_INCLUDE_PATHS", ["README.md"]
            ), patch.object(
                backup_seed_vault, "DEFAULT_GLOBS", []
            ), patch.object(
                backup_seed_vault, "DEFAULT_EXTERNAL_PATHS", [memory_db, library_db, chroma_dir, mempalace_dir]
            ):
                candidates = backup_seed_vault._collect_candidates()

            rel_paths = [rel.as_posix() for _src, rel in candidates]
            self.assertIn("README.md", rel_paths)
            self.assertIn("external/user-data/guppy_memory.db", rel_paths)
            self.assertIn("external/user-data/library.db", rel_paths)
            self.assertIn("external/semantic-chroma/chroma.sqlite3", rel_paths)
            self.assertIn("external/mempalace/mempalace_drawers.sqlite3", rel_paths)


if __name__ == "__main__":
    unittest.main()
