"""
ui/launcher/views/library_view.py
LIBRARY tab - saved files, study material, and coding context for the active workspace.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QResizeEvent, QShowEvent
from PySide6.QtWidgets import QFileDialog, QFrame, QVBoxLayout, QWidget

from src.guppy.launcher_application.library_presenter import build_library_surface_state
from . import library_editor_support as editor
from . import library_state_support as state
from .library_card_sections import (
    rebuild_browse_cards as render_browse_cards,
    rebuild_recent_cards as render_recent_cards,
    rebuild_root_cards as render_root_cards,
    rebuild_saved_cards as render_saved_cards,
)
from .library_layout import build_library_layout


class LibraryView(QWidget):
    context_requested = Signal(str, str, str, str)
    approved_root_requested = Signal(str, str)
    note_requested = Signal(str, str)
    artifact_requested = Signal(str, str, str)
    note_updated = Signal(int, str, str)
    artifact_updated = Signal(int, str, str, str)
    library_item_delete_requested = Signal(int, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = build_library_surface_state("guppy-primary")
        self._instance_context: dict[str, object] = {}
        self._selected_root_path = ""
        self._search_query = ""
        self._editing_note_id = 0
        self._editing_artifact_id = 0
        self._root_cards: list[QFrame] = []
        self._recent_cards: list[QFrame] = []

        build_library_layout(self)
        self.set_instance_context({}, {})
        self._refresh_note_editor_state()
        self._refresh_artifact_editor_state()

    def _apply_density_mode(self, width: int) -> None:
        editor.apply_density_mode(self, width)

    def showEvent(self, event: QShowEvent) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._apply_density_mode(self.width())

    def resizeEvent(self, event: QResizeEvent) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._apply_density_mode(event.size().width())
        self._refresh_note_editor_state()

    def _clear_dynamic_layout(self, layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _fill_repo_root(self) -> None:
        editor.fill_repo_root(self)

    def _choose_root_path(self) -> None:
        editor.choose_root_path(self)

    def _choose_artifact_path(self) -> None:
        editor.choose_artifact_path(self)

    def _rebuild_state(self) -> None:
        state.rebuild_state(self)

    def _browse_root(self, root_path: str) -> None:
        state.browse_root(self, root_path)

    def set_selected_root(self, root_path: str) -> None:
        state.set_selected_root(self, root_path)

    def _begin_note_edit(self, item_id: int, title: str, summary: str) -> None:
        editor.begin_note_edit(self, item_id, title, summary)

    def _begin_artifact_edit(self, item_id: int, title: str, item_path: str) -> None:
        editor.begin_artifact_edit(self, item_id, title, item_path)

    def _reset_note_editor(self) -> None:
        editor.reset_note_editor(self)

    def _reset_artifact_editor(self) -> None:
        editor.reset_artifact_editor(self)

    def _emit_root_request(self) -> None:
        editor.emit_root_request(self)

    def _set_root_feedback(self, message: str, *, is_error: bool) -> None:
        editor.set_root_feedback(self, message, is_error=is_error)

    def set_root_feedback(self, message: str, *, is_error: bool = False) -> None:
        self._set_root_feedback(message, is_error=is_error)

    def _on_root_picker_changed(self, index: int) -> None:
        state.on_root_picker_changed(self, index)

    def _sync_root_picker(self) -> None:
        editor.sync_root_picker(self)

    def _refresh_note_editor_state(self) -> None:
        editor.refresh_note_editor_state(self)

    def _refresh_artifact_editor_state(self) -> None:
        editor.refresh_artifact_editor_state(self)

    def _add_media_action(self, header: QHBoxLayout, card_state: dict[str, str]) -> None:
        if not bool(card_state.get("is_media")):
            return
        title = str(card_state.get("title", "") or "").strip()
        media_path = str(card_state.get("media_path", card_state.get("item_path", "")) or "").strip()
        if not media_path:
            return
        media_btn = QPushButton("LOAD MEDIA")
        media_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        media_btn.setStyleSheet(
            f"QPushButton {{ background: {T.BG0}; color: {T.TERTIARY}; border: 1px solid {T.BORDER};"
            f" border-radius: 12px; padding: 5px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: {T.TERTIARY}; background: #ffffff; }}"
        )
        media_btn.clicked.connect(
            lambda _=False, item_title=title, item_media_path=media_path: self._media_panel.load_media(item_title, item_media_path)
        )
        header.addWidget(media_btn)

    def _emit_note_request(self) -> None:
        title = self._note_title.text().strip()
        summary = self._note_body.toPlainText().strip()
        if not title:
            return
        if self._editing_note_id > 0:
            self.note_updated.emit(self._editing_note_id, title, summary)
        else:
            self.note_requested.emit(title, summary)
        self._reset_note_editor()

    def _emit_artifact_request(self) -> None:
        title = self._artifact_title.text().strip()
        path = self._artifact_path.text().strip()
        if not title:
            return
        summary = f"Saved artifact for {self._state.workspace_label.lower()}."
        if self._editing_artifact_id > 0:
            self.artifact_updated.emit(self._editing_artifact_id, title, path, summary)
        else:
            self.artifact_requested.emit(title, path, summary)
        self._reset_artifact_editor()

    def _rebuild_roots(self) -> None:
        render_root_cards(self)

    def _rebuild_browse_cards(self) -> None:
        render_browse_cards(self)

    def _rebuild_recent_cards(self) -> None:
        render_recent_cards(self)

    def _rebuild_saved_cards(self) -> None:
        render_saved_cards(self)

    def _apply_state(self) -> None:
        state.apply_state(self)

    def set_instance_context(self, instance: dict[str, object], snapshot: dict[str, object] | None = None) -> None:
        state.set_instance_context(self, instance, snapshot)

    def _apply_search_query(self, text: str) -> None:
        state.apply_search_query(self, text)

    def focus_search_query(self, text: str) -> None:
        state.focus_search_query(self, text)

    def _matches_query(self, *parts: str) -> bool:
        return state.matches_query(self, *parts)

    def _matches_card_query(self, card: dict[str, str], *fallback_parts: str) -> bool:
        return state.matches_card_query(self, card, *fallback_parts)

    def _filtered_root_file_cards(self) -> list[dict[str, str]]:
        return state.filtered_root_file_cards(self)

    def _filtered_recent_cards(self) -> list[dict[str, str]]:
        return state.filtered_recent_cards(self)

    def _filtered_saved_item_cards(self) -> list[dict[str, str]]:
        return state.filtered_saved_item_cards(self)

    def _current_source_summary(self, lane: str, fallback: str) -> str:
        return state.current_source_summary(self, lane, fallback)

    def chat_dock_context(self) -> dict[str, str]:
        return state.chat_dock_context(self)
