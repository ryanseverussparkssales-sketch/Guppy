from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import shutil
import uuid
from contextlib import contextmanager

from src.guppy.launcher_application import library_storage

_TEST_TEMP_ROOT = Path(__file__).resolve().parents[1] / ".tmp" / "test-scratch" / "library-storage"


@contextmanager
def workspace_tempdir():
    _TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = _TEST_TEMP_ROOT / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


tempfile.TemporaryDirectory = workspace_tempdir  # type: ignore[assignment]


class LibraryStorageTests(unittest.TestCase):
    def test_snapshot_seeds_repo_root_and_tracks_workspace_items(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            temp_root = Path(td)
            repo_root = temp_root / "repo"
            repo_root.mkdir(parents=True, exist_ok=True)
            db_path = temp_root / "user-data" / "library.db"
            index_dir = temp_root / "user-data" / "indexes" / "library"
            artifact_dir = temp_root / "user-data" / "artifacts" / "library"
            user_data_dir = temp_root / "user-data"
            with patch.object(library_storage, "LIBRARY_DB_PATH", db_path), patch.object(
                library_storage, "LIBRARY_INDEX_DIR", index_dir
            ), patch.object(library_storage, "LIBRARY_ARTIFACTS_DIR", artifact_dir), patch.object(
                library_storage, "USER_DATA_DIR", user_data_dir
            ), patch.object(library_storage, "REPO_ROOT", repo_root):
                saved = library_storage.save_workspace_library_item(
                    "builder-collab",
                    item_kind="coding",
                    title="Launcher extraction notes",
                    summary="Keep the current refactor context together.",
                    item_path=repo_root / "ui" / "launcher" / "launcher_window.py",
                    metadata={"source": "unit-test"},
                )
                self.assertEqual(saved["item_kind"], "coding")

                snapshot = library_storage.build_workspace_library_snapshot("builder-collab")

                self.assertEqual(snapshot["workspace_name"], "builder-collab")
                self.assertEqual(snapshot["approved_root_count"], 1)
                self.assertEqual(snapshot["approved_roots"][0]["label"], "Current Guppy repo")
                self.assertEqual(snapshot["kind_counts"]["coding"], 1)
                self.assertEqual(snapshot["recent_items"][0]["title"], "Launcher extraction notes")
                self.assertEqual(snapshot["db_path"], str(db_path))
                self.assertEqual(snapshot["index_dir"], str(index_dir))
                self.assertEqual(snapshot["artifacts_dir"], str(artifact_dir))

    def test_upsert_approved_root_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            temp_root = Path(td)
            db_path = temp_root / "user-data" / "library.db"
            index_dir = temp_root / "user-data" / "indexes" / "library"
            artifact_dir = temp_root / "user-data" / "artifacts" / "library"
            user_data_dir = temp_root / "user-data"
            shared_root = temp_root / "shared-drive"
            shared_root.mkdir(parents=True, exist_ok=True)
            with patch.object(library_storage, "LIBRARY_DB_PATH", db_path), patch.object(
                library_storage, "LIBRARY_INDEX_DIR", index_dir
            ), patch.object(library_storage, "LIBRARY_ARTIFACTS_DIR", artifact_dir), patch.object(
                library_storage, "USER_DATA_DIR", user_data_dir
            ), patch.object(library_storage, "REPO_ROOT", temp_root / "repo"):
                library_storage.upsert_approved_root(shared_root, label="Shared drive", source="manual")
                library_storage.upsert_approved_root(shared_root, label="Shared drive", source="manual")

                roots = [
                    root
                    for root in library_storage.list_approved_roots(limit=10)
                    if root["label"] == "Shared drive"
                ]
                self.assertEqual(len(roots), 1)

    def test_snapshot_includes_recent_files_from_approved_roots(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            temp_root = Path(td)
            repo_root = temp_root / "repo"
            repo_root.mkdir(parents=True, exist_ok=True)
            docs_dir = repo_root / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            recent_file = docs_dir / "review-notes.md"
            recent_file.write_text("# notes\n", encoding="utf-8")
            db_path = temp_root / "user-data" / "library.db"
            index_dir = temp_root / "user-data" / "indexes" / "library"
            artifact_dir = temp_root / "user-data" / "artifacts" / "library"
            user_data_dir = temp_root / "user-data"
            with patch.object(library_storage, "LIBRARY_DB_PATH", db_path), patch.object(
                library_storage, "LIBRARY_INDEX_DIR", index_dir
            ), patch.object(library_storage, "LIBRARY_ARTIFACTS_DIR", artifact_dir), patch.object(
                library_storage, "USER_DATA_DIR", user_data_dir
            ), patch.object(library_storage, "REPO_ROOT", repo_root):
                snapshot = library_storage.build_workspace_library_snapshot("guppy-primary")

                recent = snapshot["recent_filesystem_items"]
                self.assertTrue(recent)
                self.assertEqual(recent[0]["title"], "review-notes.md")
                self.assertEqual(recent[0]["item_kind"], "study")
                self.assertEqual(recent[0]["source_label"], "Current Guppy repo")

    def test_list_root_files_and_manage_workspace_library_items(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            temp_root = Path(td)
            repo_root = temp_root / "repo"
            docs_dir = repo_root / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            review_file = docs_dir / "review-notes.md"
            review_file.write_text("# notes\n", encoding="utf-8")
            db_path = temp_root / "user-data" / "library.db"
            index_dir = temp_root / "user-data" / "indexes" / "library"
            artifact_dir = temp_root / "user-data" / "artifacts" / "library"
            user_data_dir = temp_root / "user-data"
            with patch.object(library_storage, "LIBRARY_DB_PATH", db_path), patch.object(
                library_storage, "LIBRARY_INDEX_DIR", index_dir
            ), patch.object(library_storage, "LIBRARY_ARTIFACTS_DIR", artifact_dir), patch.object(
                library_storage, "USER_DATA_DIR", user_data_dir
            ), patch.object(library_storage, "REPO_ROOT", repo_root):
                item = library_storage.save_workspace_library_item(
                    "builder-collab",
                    item_kind="note",
                    title="Review packet",
                    summary="Initial summary line one.\nInitial summary line two.",
                    metadata={"source": "unit-test"},
                )

                updated = library_storage.update_workspace_library_item(
                    int(item["id"]),
                    title="Review packet v2",
                    summary="Updated summary line one.\nUpdated summary line two.",
                )
                browsed = library_storage.list_root_files(repo_root, limit=4)
                deleted = library_storage.delete_workspace_library_item(int(item["id"]))
                remaining = library_storage.list_workspace_library_items("builder-collab", limit=8)

                self.assertIsNotNone(updated)
                self.assertEqual(updated["title"], "Review packet v2")
                self.assertEqual(updated["summary"], "Updated summary line one.\nUpdated summary line two.")
                self.assertTrue(browsed)
                self.assertEqual(browsed[0]["title"], "review-notes.md")
                self.assertEqual(browsed[0]["item_kind"], "study")
                self.assertTrue(deleted)
                self.assertEqual(remaining, [])


if __name__ == "__main__":
    unittest.main()
