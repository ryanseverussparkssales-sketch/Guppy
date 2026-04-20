from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.guppy.launcher_application.library_workflow import (
    LibraryWorkflowController,
    _load_workspace_defaults,
    _save_workspace_defaults,
)


class _AssistantView:
    def __init__(self) -> None:
        self.default_source = ""
        self.input_text = ""
        self.background_event = ""
        self.active_items: list[dict[str, str]] = []

    def set_status(self, _text: str) -> None:
        return

    def set_default_context_source(self, title: str) -> None:
        self.default_source = str(title or "")

    def set_input_text(self, text: str) -> None:
        self.input_text = str(text or "")

    def set_background_event(self, text: str) -> None:
        self.background_event = str(text or "")

    def set_active_context_items(self, items: list[dict[str, str]]) -> None:
        self.active_items = [dict(item) for item in items]


class _StatusPanel:
    def __init__(self) -> None:
        self.logs: list[str] = []

    def append_syslog(self, text: str) -> None:
        self.logs.append(text)


class LibraryWorkflowControllerTests(unittest.TestCase):
    def _build_controller(self, status_panel: _StatusPanel, log_event: Mock) -> tuple[LibraryWorkflowController, list[dict[str, str]], _AssistantView]:
        active_items: list[dict[str, str]] = []
        assistant_view = _AssistantView()
        return LibraryWorkflowController(
            assistant_view=assistant_view,
            status_panel=status_panel,
            get_active_items=lambda: active_items,
            set_active_items=lambda items: active_items.clear() or active_items.extend(items),
            get_active_instance_name=lambda: "guppy-primary",
            get_library_view=lambda: None,
            refresh_library_surface=Mock(),
            on_tab_change=lambda _index: None,
            set_daily_activity=lambda _text: None,
            log_launcher_event=log_event,
        ), active_items, assistant_view

    def test_handle_root_requested_rejects_missing_path(self) -> None:
        status_panel = _StatusPanel()
        log_event = Mock()
        controller, _, _ = self._build_controller(status_panel, log_event)

        with patch("src.guppy.launcher_application.library_workflow.upsert_approved_root") as upsert:
            controller.handle_root_requested("", "")

        upsert.assert_not_called()
        self.assertIn("approved root rejected: missing path", status_panel.logs)
        log_event.assert_called_with("library_root_rejected", reason="missing_path")

    def test_handle_root_requested_rejects_missing_folder(self) -> None:
        status_panel = _StatusPanel()
        log_event = Mock()
        controller, _, _ = self._build_controller(status_panel, log_event)

        missing_path = str(Path(tempfile.gettempdir()) / "guppy-library-root-does-not-exist")
        with patch("src.guppy.launcher_application.library_workflow.upsert_approved_root") as upsert:
            controller.handle_root_requested(missing_path, "")

        upsert.assert_not_called()
        self.assertIn("approved root rejected: folder not found", status_panel.logs)

    def test_handle_root_requested_saves_valid_path_with_default_label(self) -> None:
        status_panel = _StatusPanel()
        log_event = Mock()
        controller, _, _ = self._build_controller(status_panel, log_event)

        with tempfile.TemporaryDirectory() as td:
            expected_path = str(Path(td).resolve())
            with patch(
                "src.guppy.launcher_application.library_workflow.upsert_approved_root",
                return_value={"label": Path(td).name, "root_path": expected_path},
            ) as upsert:
                controller.handle_root_requested(td, "")

        upsert.assert_called_once_with(expected_path, label=Path(expected_path).name, source="library_ui", enabled=True)
        self.assertIn(f"approved root saved: {Path(expected_path).name}", status_panel.logs)

    def test_handle_default_source_requested_pins_and_prioritizes_attached_source(self) -> None:
        status_panel = _StatusPanel()
        log_event = Mock()
        controller, active_items, assistant = self._build_controller(status_panel, log_event)
        active_items.extend(
            [
                {"title": "Spec A", "kind": "file", "detail": "A"},
                {"title": "Spec B", "kind": "file", "detail": "B"},
            ]
        )

        with patch("src.guppy.launcher_application.library_workflow._save_workspace_defaults"):
            controller.handle_default_source_requested("Spec B")

        self.assertEqual(active_items[0]["title"], "Spec B")
        self.assertIn("default source pinned: Spec B", status_panel.logs)
        self.assertEqual(assistant.default_source, "Spec B")

    def test_handle_context_requested_respects_pinned_workspace_default(self) -> None:
        status_panel = _StatusPanel()
        log_event = Mock()
        controller, active_items, _ = self._build_controller(status_panel, log_event)
        active_items.extend(
            [
                {"title": "Pinned Spec", "kind": "file", "detail": "root"},
                {"title": "Other Spec", "kind": "file", "detail": "other"},
            ]
        )

        with patch("src.guppy.launcher_application.library_workflow._save_workspace_defaults"):
            controller.handle_default_source_requested("Pinned Spec")
            controller.handle_context_requested(
                "Fresh Context",
                "C:/tmp/fresh.txt",
                "file",
                "Use Fresh Context",
            )

        self.assertEqual(active_items[0]["title"], "Pinned Spec")

    def test_handle_context_requested_marks_note_origin_and_label(self) -> None:
        status_panel = _StatusPanel()
        log_event = Mock()
        controller, active_items, assistant = self._build_controller(status_panel, log_event)

        controller.handle_context_requested("Review packet", "", "note", "Use Review packet")

        self.assertEqual(active_items[0]["origin"], "library_note")
        self.assertEqual(active_items[0]["source_label"], "Pinned note")
        self.assertEqual(assistant.input_text, "Use Review packet")

    def test_handle_context_requested_saved_reply_note_uses_saved_reply_origin_and_body(self) -> None:
        status_panel = _StatusPanel()
        log_event = Mock()
        controller, active_items, _ = self._build_controller(status_panel, log_event)

        with patch(
            "src.guppy.launcher_application.library_context_support.list_workspace_library_items",
            return_value=[
                {
                    "title": "Review packet",
                    "summary": "Line one of the saved reply note.\nLine two keeps the context going.",
                    "metadata": {"source": "assistant_reply"},
                    "item_path": "",
                }
            ],
        ):
            controller.handle_context_requested("Review packet", "", "note", "Use Review packet")

        self.assertEqual(active_items[0]["origin"], "assistant_reply")
        self.assertEqual(active_items[0]["source_label"], "Saved reply note")
        self.assertIn("Line one of the saved reply note.", active_items[0]["detail"])

    def test_handle_context_requested_resolves_duplicate_titles_by_library_item_id(self) -> None:
        status_panel = _StatusPanel()
        log_event = Mock()
        controller, active_items, _ = self._build_controller(status_panel, log_event)

        with patch(
            "src.guppy.launcher_application.library_context_support.list_workspace_library_items",
            return_value=[
                {
                    "id": 14,
                    "title": "Review packet",
                    "summary": "Wrong note body.",
                    "metadata": {"source": "assistant_reply"},
                    "item_path": "",
                },
                {
                    "id": 42,
                    "title": "Review packet",
                    "summary": "Correct note body for the selected card.",
                    "metadata": {"source": "assistant_reply"},
                    "item_path": "",
                },
            ],
        ):
            controller.handle_context_requested("Review packet", "library-item://42", "note", "Use Review packet")

        self.assertEqual(active_items[0]["origin"], "assistant_reply")
        self.assertIn("Correct note body", active_items[0]["detail"])

    def test_handle_context_requested_marks_media_origin_and_label(self) -> None:
        status_panel = _StatusPanel()
        log_event = Mock()
        controller, active_items, assistant = self._build_controller(status_panel, log_event)

        controller.handle_context_requested(
            "Walkthrough clip",
            "C:/repo/media/walkthrough.mp4",
            "artifact",
            "Use Walkthrough clip",
        )

        self.assertEqual(active_items[0]["origin"], "library_media")
        self.assertEqual(active_items[0]["source_label"], "Local video")
        self.assertIn("Walkthrough clip", assistant.background_event)

    def test_handle_context_requested_saved_reply_artifact_uses_saved_output_origin(self) -> None:
        status_panel = _StatusPanel()
        log_event = Mock()
        controller, active_items, _ = self._build_controller(status_panel, log_event)

        with patch(
            "src.guppy.launcher_application.library_context_support.list_workspace_library_items",
            return_value=[
                {
                    "title": "Release review artifact",
                    "summary": "Checklist and validation notes ready for the next pass.",
                    "metadata": {"source": "assistant_reply_artifact"},
                    "item_path": "C:/tmp/release-review.txt",
                }
            ],
        ):
            controller.handle_context_requested(
                "Release review artifact",
                "C:/tmp/release-review.txt",
                "artifact",
                "Use Release review artifact",
            )

        self.assertEqual(active_items[0]["origin"], "assistant_reply_artifact")
        self.assertEqual(active_items[0]["source_label"], "Saved reply artifact")
        self.assertIn("Checklist and validation notes ready", active_items[0]["detail"])

    def test_handle_context_requested_root_file_uses_approved_root_detail(self) -> None:
        status_panel = _StatusPanel()
        log_event = Mock()
        controller, active_items, _ = self._build_controller(status_panel, log_event)

        with patch(
            "src.guppy.launcher_application.library_context_support.list_approved_roots",
            return_value=[
                {
                    "label": "Current Guppy repo",
                    "root_path": str(Path.cwd()),
                }
            ],
        ):
            controller.handle_context_requested(
                "README",
                str(Path.cwd() / "docs" / "PROJECT_BRIEF.md"),
                "study",
                "Use PROJECT_BRIEF",
            )

        self.assertEqual(active_items[0]["origin"], "library_source")
        self.assertEqual(active_items[0]["source_label"], "Current Guppy repo")
        self.assertIn("docs/PROJECT_BRIEF.md", active_items[0]["detail"])

    def test_save_and_load_workspace_defaults_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            defaults_path = Path(td) / "library_workspace_defaults.json"
            with patch("src.guppy.launcher_application.library_workflow._LIBRARY_DEFAULTS_PATH", defaults_path):
                status_panel = _StatusPanel()
                log_event = Mock()
                controller, _, _ = self._build_controller(status_panel, log_event)

                controller._set_workspace_default_title("MyDoc.pdf")
                _save_workspace_defaults(controller._workspace_default_sources)
                controller._workspace_default_sources = _load_workspace_defaults()

                self.assertEqual(controller._workspace_default_title(), "MyDoc.pdf")

    def test_workspace_default_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            defaults_path = Path(td) / "library_workspace_defaults.json"
            with patch("src.guppy.launcher_application.library_workflow._LIBRARY_DEFAULTS_PATH", defaults_path):
                status_panel = _StatusPanel()
                log_event = Mock()
                controller, _, _ = self._build_controller(status_panel, log_event)

                controller._set_workspace_default_title("DocA")
                _save_workspace_defaults(controller._workspace_default_sources)

                with patch.object(controller, "_active_workspace_name", return_value="workspace-B"):
                    self.assertEqual(controller._workspace_default_title(), "")

    def test_handle_default_source_requested_clears_on_empty_title(self) -> None:
        status_panel = _StatusPanel()
        log_event = Mock()
        controller, active_items, _ = self._build_controller(status_panel, log_event)
        active_items.append({"title": "Attached", "kind": "file", "detail": "A"})

        self.assertEqual(controller._workspace_default_title(), "")
        controller.handle_default_source_requested("")

        self.assertEqual(controller._workspace_default_title(), "")

    def test_stale_default_clears_on_item_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            defaults_path = Path(td) / "library_workspace_defaults.json"
            with patch("src.guppy.launcher_application.library_workflow._LIBRARY_DEFAULTS_PATH", defaults_path):
                status_panel = _StatusPanel()
                log_event = Mock()
                controller, active_items, _ = self._build_controller(status_panel, log_event)
                active_items.append({"title": "OldDoc", "kind": "file", "detail": "A"})

                controller.handle_default_source_requested("OldDoc")
                with patch("src.guppy.launcher_application.library_workflow.delete_workspace_library_item", return_value=True):
                    controller.handle_item_deleted(101, "OldDoc")

                self.assertEqual(controller._workspace_default_title(), "")

    def test_default_source_persists_across_workspace_activation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            defaults_path = Path(td) / "library_workspace_defaults.json"
            with patch("src.guppy.launcher_application.library_workflow._LIBRARY_DEFAULTS_PATH", defaults_path):
                status_panel = _StatusPanel()
                log_event = Mock()
                controller, active_items, _ = self._build_controller(status_panel, log_event)
                active_items.append({"title": "PinnedDoc", "kind": "file", "detail": "A"})

                controller.handle_default_source_requested("PinnedDoc")

                with patch.object(controller, "_active_workspace_name", return_value="workspace-B"):
                    controller.sync()
                    self.assertEqual(controller._workspace_default_title(), "")

                with patch.object(controller, "_active_workspace_name", return_value="guppy-primary"):
                    controller.sync()
                    self.assertEqual(controller._workspace_default_title(), "PinnedDoc")


if __name__ == "__main__":
    unittest.main()
