"""
ui/launcher/views/library_view.py
LIBRARY tab - saved files, study material, and coding context for the active workspace.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QResizeEvent, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.guppy.launcher_application.library_presenter import (
    LibrarySurfaceState,
    build_library_surface_state,
)
from .. import tokens as T
from . import library_editor_support as editor
from .library_card_sections import (
    rebuild_browse_cards as render_browse_cards,
    rebuild_recent_cards as render_recent_cards,
    rebuild_root_cards as render_root_cards,
    rebuild_saved_cards as render_saved_cards,
)
from .library_media_panel import LibraryMediaPanel
from .library_view_components import body_label as _body
from .library_view_components import build_summary_card as _build_summary_card
from .library_view_components import mono_label as _mono


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

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(18)

        header = QFrame()
        header.setStyleSheet(
            "QFrame { background-color: rgba(255,255,255,0.60); border: 1px solid rgba(214,197,174,0.46); border-radius: 28px; }"
        )
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(20, 18, 20, 16)
        header_layout.setSpacing(8)

        title_row = QHBoxLayout()
        title = QLabel("Library")
        title.setStyleSheet(
            f"color: {T.INK}; font-family: '{T.FF_HEAD}'; font-size: 28pt; font-weight: 700;"
        )
        title_row.addWidget(title)
        title_row.addStretch()
        self._workspace_chip = QLabel("DAILY WORKSPACE")
        self._workspace_chip.setStyleSheet(
            f"color: {T.ACCENT_TEAL}; background: rgba(0,106,106,0.10); border: 1px solid rgba(0,106,106,0.30);"
            f" border-radius: 14px; padding: 6px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        title_row.addWidget(self._workspace_chip)
        header_layout.addLayout(title_row)

        purpose = QLabel("LIBRARY — Save files, notes, and assistant output so they can be attached to future conversations.")
        purpose.setObjectName("hub-purpose")
        purpose.setWordWrap(True)
        purpose.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        header_layout.addWidget(purpose)

        self._summary_lbl = _body("")
        header_layout.addWidget(self._summary_lbl)

        self._roots_lbl = _body("", color=T.SECONDARY, size=T.FS_TINY)
        header_layout.addWidget(self._roots_lbl)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search files, notes, and saved workspace context")
        self._search.setStyleSheet(
            f"QLineEdit {{ background: rgba(255,255,255,0.88); border: 1px solid rgba(214,197,174,0.62); color: {T.TEXT};"
            f" border-radius: 18px; padding: 8px 12px; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt; }}"
        )
        self._search.textChanged.connect(self._apply_search_query)
        header_layout.addWidget(self._search)
        layout.addWidget(header)

        manager = QFrame()
        manager.setStyleSheet(
            "QFrame { background-color: rgba(255,255,255,0.58); border: 1px solid rgba(214,197,174,0.42); border-radius: 22px; }"
        )
        manager_layout = QVBoxLayout(manager)
        manager_layout.setContentsMargins(16, 14, 16, 14)
        manager_layout.setSpacing(10)
        manager_layout.addWidget(_mono("MANAGE LIBRARY", T.PRIMARY, T.FS_TINY, True))

        root_row = QHBoxLayout()
        root_row.setSpacing(8)
        self._root_path = QLineEdit()
        self._root_path.setPlaceholderText("Approved root path")
        self._root_label = QLineEdit()
        self._root_label.setPlaceholderText("Label")
        self._root_repo_btn = QPushButton("USE REPO")
        self._root_repo_btn.setToolTip("Use the current Guppy repository as an approved root")
        self._root_repo_btn.clicked.connect(self._fill_repo_root)
        self._root_browse_btn = QPushButton("PICK FOLDER")
        self._root_browse_btn.setToolTip("Browse and choose a folder to approve")
        self._root_browse_btn.clicked.connect(self._choose_root_path)
        self._root_save_btn = QPushButton("SAVE ROOT")
        self._root_save_btn.setToolTip("Submit this root for approval in the active workspace")
        self._root_save_btn.clicked.connect(self._emit_root_request)
        for widget in (self._root_path, self._root_label):
            widget.setStyleSheet(
                f"QLineEdit {{ background: rgba(255,255,255,0.90); border: 1px solid rgba(214,197,174,0.56); color: {T.TEXT};"
                f" border-radius: 14px; padding: 6px 10px; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt; }}"
            )
        for button in (self._root_repo_btn, self._root_browse_btn, self._root_save_btn):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(
                f"QPushButton {{ background: {T.BG0}; color: {T.PRIMARY}; border: 1px solid {T.BORDER};"
                f" border-radius: 12px; padding: 6px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ border-color: {T.PRIMARY}; background: #ffffff; }}"
            )
        root_row.addWidget(self._root_path, stretch=2)
        root_row.addWidget(self._root_label, stretch=1)
        root_row.addWidget(self._root_repo_btn)
        root_row.addWidget(self._root_browse_btn)
        root_row.addWidget(self._root_save_btn)
        manager_layout.addLayout(root_row)
        self._root_feedback_lbl = _body("", color=T.DIM, size=T.FS_TINY)
        self._root_feedback_lbl.setVisible(False)
        manager_layout.addWidget(self._root_feedback_lbl)

        note_row = QVBoxLayout()
        note_row.setSpacing(8)
        note_top = QHBoxLayout()
        note_top.setSpacing(8)
        self._note_title = QLineEdit()
        self._note_title.setPlaceholderText("Pinned note title")
        self._note_body = QPlainTextEdit()
        self._note_body.setPlaceholderText("Pinned note body")
        self._note_body.setFixedHeight(92)
        self._note_save_btn = QPushButton("PIN NOTE")
        self._note_save_btn.setToolTip("Save this note and pin it to the active workspace library")
        self._note_save_btn.clicked.connect(self._emit_note_request)
        self._note_title.setStyleSheet(
            f"QLineEdit {{ background: rgba(255,255,255,0.90); border: 1px solid rgba(214,197,174,0.56); color: {T.TEXT};"
            f" border-radius: 14px; padding: 6px 10px; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt; }}"
        )
        self._note_body.setStyleSheet(
            f"QPlainTextEdit {{ background: rgba(255,255,255,0.90); border: 1px solid rgba(214,197,174,0.56); color: {T.TEXT};"
            f" border-radius: 14px; padding: 8px 10px; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt; }}"
        )
        self._note_save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._note_save_btn.setStyleSheet(
            f"QPushButton {{ background: {T.BG0}; color: {T.PRIMARY}; border: 1px solid {T.BORDER};"
            f" border-radius: 12px; padding: 6px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: {T.PRIMARY}; background: #ffffff; }}"
        )
        self._note_cancel_btn = QPushButton("CANCEL EDIT")
        self._note_cancel_btn.setToolTip("Discard changes and reset the note editor")
        self._note_cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._note_cancel_btn.setStyleSheet(
            f"QPushButton {{ background: {T.BG0}; color: {T.SECONDARY}; border: 1px solid {T.BORDER};"
            f" border-radius: 12px; padding: 6px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: {T.SECONDARY}; background: #ffffff; }}"
        )
        self._note_cancel_btn.clicked.connect(self._reset_note_editor)
        self._note_cancel_btn.setVisible(False)
        self._note_title.textChanged.connect(self._refresh_note_editor_state)
        self._note_body.textChanged.connect(self._refresh_note_editor_state)
        note_top.addWidget(self._note_title, stretch=1)
        note_top.addWidget(self._note_save_btn)
        note_top.addWidget(self._note_cancel_btn)
        note_row.addLayout(note_top)
        note_row.addWidget(self._note_body)
        self._note_editor_hint = _body("", color=T.DIM, size=T.FS_TINY)
        note_row.addWidget(self._note_editor_hint)
        manager_layout.addLayout(note_row)

        artifact_row = QHBoxLayout()
        artifact_row.setSpacing(8)
        self._artifact_title = QLineEdit()
        self._artifact_title.setPlaceholderText("Artifact title")
        self._artifact_path = QLineEdit()
        self._artifact_path.setPlaceholderText("Artifact path or bundle location")
        self._artifact_browse_btn = QPushButton("PICK FILE")
        self._artifact_browse_btn.setToolTip("Browse and select a file to register as a library artifact")
        self._artifact_browse_btn.clicked.connect(self._choose_artifact_path)
        self._artifact_save_btn = QPushButton("SAVE ARTIFACT")
        self._artifact_save_btn.setToolTip("Save this artifact reference to the active workspace library")
        self._artifact_save_btn.clicked.connect(self._emit_artifact_request)
        for widget in (self._artifact_title, self._artifact_path):
            widget.setStyleSheet(
                f"QLineEdit {{ background: rgba(255,255,255,0.90); border: 1px solid rgba(214,197,174,0.56); color: {T.TEXT};"
                f" border-radius: 14px; padding: 6px 10px; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt; }}"
            )
        for button in (self._artifact_browse_btn, self._artifact_save_btn):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(
                f"QPushButton {{ background: {T.BG0}; color: {T.PRIMARY}; border: 1px solid {T.BORDER};"
                f" border-radius: 12px; padding: 6px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ border-color: {T.PRIMARY}; background: #ffffff; }}"
            )
        self._artifact_cancel_btn = QPushButton("CANCEL EDIT")
        self._artifact_cancel_btn.setToolTip("Discard changes and reset the artifact editor")
        self._artifact_cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._artifact_cancel_btn.setStyleSheet(
            f"QPushButton {{ background: {T.BG0}; color: {T.SECONDARY}; border: 1px solid {T.BORDER};"
            f" border-radius: 12px; padding: 6px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: {T.SECONDARY}; background: #ffffff; }}"
        )
        self._artifact_cancel_btn.clicked.connect(self._reset_artifact_editor)
        self._artifact_cancel_btn.setVisible(False)
        artifact_row.addWidget(self._artifact_title, stretch=1)
        artifact_row.addWidget(self._artifact_path, stretch=2)
        artifact_row.addWidget(self._artifact_browse_btn)
        artifact_row.addWidget(self._artifact_save_btn)
        artifact_row.addWidget(self._artifact_cancel_btn)
        manager_layout.addLayout(artifact_row)
        layout.addWidget(manager)

        self._recent_lbl = _mono("", T.PRIMARY, T.FS_TINY, True)
        layout.addWidget(self._recent_lbl)

        self._roots_header = _mono("APPROVED ROOTS", T.PRIMARY, T.FS_TINY, True)
        layout.addWidget(self._roots_header)
        self._roots_hint = _body(
            "Choose which folders Guppy may browse. Nothing outside approved roots is scanned, and Library only reuses files from these approved locations.",
            color=T.DIM,
        )
        layout.addWidget(self._roots_hint)
        self._roots_host = QWidget()
        self._roots_layout = QVBoxLayout(self._roots_host)
        self._roots_layout.setContentsMargins(0, 0, 0, 0)
        self._roots_layout.setSpacing(10)
        layout.addWidget(self._roots_host)

        self._browse_header = _mono("BROWSE ROOT FILES", T.PRIMARY, T.FS_TINY, True)
        layout.addWidget(self._browse_header)
        browse_picker_row = QHBoxLayout()
        browse_picker_row.setSpacing(8)
        self._root_picker = QComboBox()
        self._root_picker.setToolTip("Switch between approved roots without scrolling back to the approved-root cards")
        self._root_picker.setStyleSheet(
            f"QComboBox {{ background: rgba(255,255,255,0.90); border: 1px solid rgba(214,197,174,0.56); color: {T.TEXT};"
            f" border-radius: 14px; padding: 6px 10px; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt; }}"
            "QComboBox::drop-down { border: none; padding-right: 6px; }"
        )
        self._root_picker.currentIndexChanged.connect(self._on_root_picker_changed)
        browse_picker_row.addWidget(self._root_picker, stretch=1)
        layout.addLayout(browse_picker_row)
        self._selected_root_status = _mono("", T.SECONDARY, T.FS_TINY, True)
        layout.addWidget(self._selected_root_status)
        self._browse_hint = _body("", color=T.DIM)
        layout.addWidget(self._browse_hint)
        self._browse_host = QWidget()
        self._browse_layout = QVBoxLayout(self._browse_host)
        self._browse_layout.setContentsMargins(0, 0, 0, 0)
        self._browse_layout.setSpacing(10)
        layout.addWidget(self._browse_host)

        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)

        self._files_card, self._files_copy = _build_summary_card(
            "FILES & SOURCES",
            "Saved documents, notes, screenshots, and imported context will appear here.",
        )
        self._study_card, self._study_copy = _build_summary_card(
            "STUDY CONTEXT",
            "Summaries, outlines, review packets, and reading context will collect here.",
        )
        self._coding_card, self._coding_copy = _build_summary_card(
            "CODING CONTEXT",
            "Repo notes, module targets, diffs, and artifact handoffs will appear here.",
        )
        self._artifact_card, self._artifact_copy = _build_summary_card(
            "NEXT BUILD",
            "The active workspace will eventually pin recent files, outputs, and reusable context here.",
        )

        grid.addWidget(self._files_card, 0, 0)
        grid.addWidget(self._study_card, 0, 1)
        grid.addWidget(self._coding_card, 1, 0)
        grid.addWidget(self._artifact_card, 1, 1)
        layout.addWidget(grid_host)

        self._media_header = _mono("LOCAL MEDIA", T.PRIMARY, T.FS_TINY, True)
        layout.addWidget(self._media_header)
        self._media_hint = _body(
            "Load local audio or video from approved roots or saved media artifacts without leaving Library.",
            color=T.DIM,
        )
        layout.addWidget(self._media_hint)
        self._media_panel = LibraryMediaPanel(self)
        layout.addWidget(self._media_panel)

        self._recent_header = _mono("READY TO USE IN CHAT", T.PRIMARY, T.FS_TINY, True)
        layout.addWidget(self._recent_header)
        self._recent_hint = _body(
            "Recent files and Library saves show up here first. USE IN CHAT attaches one as source context for the next reply and sends it back to Home.",
            color=T.DIM,
        )
        layout.addWidget(self._recent_hint)
        self._recent_host = QWidget()
        self._recent_layout = QVBoxLayout(self._recent_host)
        self._recent_layout.setContentsMargins(0, 0, 0, 0)
        self._recent_layout.setSpacing(10)
        layout.addWidget(self._recent_host)

        self._saved_header = _mono("PINNED NOTES & ARTIFACTS", T.PRIMARY, T.FS_TINY, True)
        layout.addWidget(self._saved_header)
        self._saved_hint = _body(
            "Keep durable notes and artifacts here so they can be edited, reused in chat, or removed cleanly.",
            color=T.DIM,
        )
        layout.addWidget(self._saved_hint)
        self._saved_host = QWidget()
        self._saved_layout = QVBoxLayout(self._saved_host)
        self._saved_layout.setContentsMargins(0, 0, 0, 0)
        self._saved_layout.setSpacing(10)
        layout.addWidget(self._saved_host)
        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)
        self.set_instance_context({}, {})
        self._refresh_note_editor_state()

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
        self._state = build_library_surface_state(
            str(self._instance_context.get("name", "guppy-primary") or "guppy-primary"),
            workspace_type=str(self._instance_context.get("type", "user_instance") or "user_instance"),
            description=str(self._instance_context.get("description", "") or ""),
            mode=str(self._instance_context.get("mode", "auto") or "auto"),
            last_message=str(self._instance_context.get("last_message", "") or ""),
            selected_root_path=self._selected_root_path,
        )

    def _browse_root(self, root_path: str) -> None:
        self._selected_root_path = str(root_path or "").strip()
        self._rebuild_state()
        self._apply_state()

    def set_selected_root(self, root_path: str) -> None:
        path = str(root_path or "").strip()
        if not path:
            return
        self._selected_root_path = path
        self._rebuild_state()
        self._apply_state()

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
        if index < 0:
            return
        root_path = str(self._root_picker.itemData(index) or "").strip()
        if not root_path or root_path == self._selected_root_path:
            return
        self._browse_root(root_path)

    def _sync_root_picker(self) -> None:
        editor.sync_root_picker(self)

    def _refresh_note_editor_state(self) -> None:
        editor.refresh_note_editor_state(self)

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
        self._workspace_chip.setText(self._state.workspace_label.upper())
        self._summary_lbl.setText(self._state.library_summary)
        self._roots_lbl.setText(self._state.roots_summary)
        self._recent_lbl.setText(self._state.recent_summary)
        self._search.setPlaceholderText(self._state.search_hint)
        self._files_copy.setText(self._state.files_summary)
        self._study_copy.setText(self._state.study_summary)
        self._coding_copy.setText(self._state.coding_summary)
        self._artifact_copy.setText(self._state.artifact_summary)
        self._sync_root_picker()
        self._rebuild_roots()
        self._rebuild_browse_cards()
        self._rebuild_recent_cards()
        self._rebuild_saved_cards()
        self._root_label.setPlaceholderText(f"Label for {self._state.workspace_label.lower()} root")
        if not self._selected_root_path and self._state.approved_roots:
            self._selected_root_path = str(self._state.approved_roots[0].get("root_path", "") or "").strip()
        if self.isVisible():
            self._apply_density_mode(self.width())

    def set_instance_context(self, instance: dict[str, object], snapshot: dict[str, object] | None = None) -> None:
        del snapshot
        self._instance_context = dict(instance or {})
        self._rebuild_state()
        self._selected_root_path = self._state.approved_roots[0]["root_path"] if self._state.approved_roots and not self._selected_root_path else self._selected_root_path
        self._rebuild_state()
        self._apply_state()

    def _apply_search_query(self, text: str) -> None:
        self._search_query = str(text or "").strip().lower()
        self._apply_state()

    def focus_search_query(self, text: str) -> None:
        query = str(text or "").strip()
        self._search.setText(query)
        self._search.setFocus(Qt.FocusReason.OtherFocusReason)

    def _matches_query(self, *parts: str) -> bool:
        query = self._search_query
        if not query:
            return True
        haystack = " ".join(str(part or "") for part in parts).lower()
        return query in haystack

    def _filtered_root_file_cards(self) -> list[dict[str, str]]:
        return [
            card
            for card in self._state.root_file_cards
            if self._matches_query(str(card.get("title", "") or ""), str(card.get("detail", "") or ""), str(card.get("kind", "") or ""))
        ]

    def _filtered_recent_cards(self) -> list[dict[str, str]]:
        return [
            card
            for card in self._state.recent_cards
            if self._matches_query(str(card.get("title", "") or ""), str(card.get("detail", "") or ""), str(card.get("kind", "") or ""))
        ]

    def _filtered_saved_item_cards(self) -> list[dict[str, str]]:
        return [
            card
            for card in self._state.saved_item_cards
            if self._matches_query(
                str(card.get("title", "") or ""),
                str(card.get("detail", "") or ""),
                str(card.get("kind", "") or ""),
                str(card.get("summary", "") or ""),
            )
        ]

    def _current_source_summary(self, lane: str, fallback: str) -> str:
        kind_map = {
            "files": {"file"},
            "study": {"study", "note"},
            "coding": {"coding", "artifact"},
        }
        target_kinds = kind_map.get(lane, {lane})
        for origin, cards in (
            ("saved", self._filtered_saved_item_cards()),
            ("recent", self._filtered_recent_cards()),
            ("root", self._filtered_root_file_cards()),
        ):
            for card in cards:
                kind = str(card.get("kind", "") or "").strip().lower()
                if kind not in target_kinds:
                    continue
                title = str(card.get("title", "") or "").strip()
                if not title:
                    continue
                detail_bits: list[str] = []
                if origin == "root" and self._state.selected_root_label:
                    detail_bits.append(f"from {self._state.selected_root_label}")
                elif origin == "saved":
                    detail_bits.append("from saved Library items")
                elif origin == "recent":
                    detail_bits.append("from recent Library items")
                if self._search_query:
                    detail_bits.append(f'matching "{self._search_query}"')
                suffix = f" ({'; '.join(detail_bits)})" if detail_bits else ""
                return f"Current source: {title}{suffix}."
        return fallback

    def chat_dock_context(self) -> dict[str, str]:
        return {
            "files": self._current_source_summary("files", self._state.files_summary),
            "study": self._current_source_summary("study", self._state.study_summary),
            "coding": self._current_source_summary("coding", self._state.coding_summary),
        }
