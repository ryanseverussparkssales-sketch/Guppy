from __future__ import annotations

import unittest
from unittest.mock import patch

from src.guppy.launcher_application.library_media import describe_library_media_path
from src.guppy.launcher_application.library_presenter import build_library_surface_state


class LibraryPresenterTests(unittest.TestCase):
    def test_build_library_surface_state_uses_note_preview_and_media_flags(self) -> None:
        snapshot = {
            "approved_root_count": 1,
            "approved_roots": [
                {
                    "label": "Current Guppy repo",
                    "root_path": "C:/repo",
                    "source": "repo",
                    "enabled": True,
                }
            ],
            "kind_counts": {"file": 0, "study": 0, "coding": 0, "artifact": 1, "note": 1},
            "recent_items": [
                {
                    "id": 11,
                    "item_kind": "note",
                    "title": "Review packet",
                    "item_path": "",
                    "summary": "Line one of the note body.\nLine two keeps going for a while so preview text has to collapse cleanly.",
                    "metadata": {"source": "library_ui"},
                },
                {
                    "id": 12,
                    "item_kind": "artifact",
                    "title": "Walkthrough clip",
                    "item_path": "C:/repo/media/walkthrough.mp4",
                    "summary": "Saved demo clip",
                    "metadata": {"source": "library_ui"},
                },
            ],
            "recent_filesystem_items": [
                {
                    "title": "standup.mp3",
                    "item_path": "C:/repo/media/standup.mp3",
                    "item_kind": "file",
                    "summary": "media/standup.mp3 | Current Guppy repo",
                    "source_label": "Current Guppy repo",
                }
            ],
            "user_data_dir": "C:/user-data",
        }
        root_files = [
            {
                "title": "walkthrough.mp4",
                "item_path": "C:/repo/media/walkthrough.mp4",
                "item_kind": "file",
                "summary": "media/walkthrough.mp4 | Current Guppy repo",
                "source_label": "Current Guppy repo",
            }
        ]

        with patch(
            "src.guppy.launcher_application.library_presenter.build_workspace_library_snapshot",
            return_value=snapshot,
        ), patch(
            "src.guppy.launcher_application.library_presenter.list_root_files",
            return_value=root_files,
        ):
            state = build_library_surface_state("builder-collab", workspace_type="builder_instance")

        self.assertEqual(state.saved_item_cards[0]["kind"], "note")
        self.assertIn("Pinned note", state.saved_item_cards[0]["detail"])
        self.assertNotIn("\n", state.saved_item_cards[0]["detail"])
        self.assertEqual(state.saved_item_cards[0]["summary"], snapshot["recent_items"][0]["summary"])
        self.assertTrue(state.saved_item_cards[1]["is_media"])
        self.assertEqual(state.saved_item_cards[1]["media_kind"], "video")
        self.assertTrue(state.root_file_cards[0]["is_media"])
        self.assertEqual(state.root_file_cards[0]["media_kind"], "video")
        self.assertTrue(any(card["is_media"] for card in state.recent_cards))

    def test_describe_library_media_path_detects_supported_local_media(self) -> None:
        descriptor = describe_library_media_path("C:/repo/media/standup.mp3")

        self.assertTrue(descriptor.is_local_file)
        self.assertTrue(descriptor.is_media)
        self.assertEqual(descriptor.media_kind, "audio")
        self.assertEqual(descriptor.source_label, "Local audio")


if __name__ == "__main__":
    unittest.main()
