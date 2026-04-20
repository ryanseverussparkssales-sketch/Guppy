"""
ui/launcher/views/library_view.py
LIBRARY tab - saved files, study material, and coding context for the active workspace.
"""
from __future__ import annotations

from pathlib import Path

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
    validate_library_root,
)
from .. import tokens as T
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
            f"color: {T.SECONDARY}; background: rgba(47,111,122,0.10); border: 1px solid rgba(214,197,174,0.40);"
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
        compact = width <= 1120
        tight = width <= 920
        self._search.setPlaceholderText(
            "Search Library" if tight else "Search files, notes, and saved workspace context"
        )
        self._root_repo_btn.setText("REPO" if tight else "USE REPO")
        self._root_browse_btn.setText("FOLDER" if tight else "PICK FOLDER")
        self._root_save_btn.setText("SAVE" if compact else "SAVE ROOT")
        self._note_save_btn.setText(
            "UPDATE" if self._editing_note_id > 0 and tight else
            "UPDATE NOTE" if self._editing_note_id > 0 else
            "SAVE NOTE" if compact else
            "PIN NOTE"
        )
        self._note_cancel_btn.setText("CANCEL" if compact else "CANCEL EDIT")
        self._artifact_browse_btn.setText("FILE" if compact else "PICK FILE")
        self._artifact_save_btn.setText(
            "UPDATE" if self._editing_artifact_id > 0 and compact else
            "UPDATE ARTIFACT" if self._editing_artifact_id > 0 else
            "SAVE" if compact else
            "SAVE ARTIFACT"
        )
        self._artifact_cancel_btn.setText("CANCEL" if compact else "CANCEL EDIT")
        self._roots_hint.setVisible(not tight)
        self._recent_hint.setVisible(not tight)
        self._saved_hint.setVisible(not tight)

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
        for root in self._state.approved_roots:
            if str(root.get("label", "")).strip().lower() == "current guppy repo":
                self._root_label.setText(str(root.get("label", "") or "").strip())
                self._root_path.setText(str(root.get("root_path", "") or "").strip())
                self._set_root_feedback("", is_error=False)
                return

    def _choose_root_path(self) -> None:
        current = self._root_path.text().strip() or self._selected_root_path
        chosen = QFileDialog.getExistingDirectory(self, "Select approved root", current)
        chosen = str(chosen or "").strip()
        if not chosen:
            return
        self._root_path.setText(chosen)
        if not self._root_label.text().strip():
            normalized = chosen.replace("\\", "/").rstrip("/")
            default_label = normalized.rsplit("/", 1)[-1].strip() or "Approved root"
            self._root_label.setText(default_label)
        self._set_root_feedback("", is_error=False)

    def _choose_artifact_path(self) -> None:
        current = self._artifact_path.text().strip() or self._root_path.text().strip()
        chosen, _ = QFileDialog.getOpenFileName(self, "Select artifact file", current)
        chosen = str(chosen or "").strip()
        if chosen:
            self._artifact_path.setText(chosen)

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
        self._editing_note_id = max(0, int(item_id or 0))
        self._note_title.setText(title)
        self._note_body.setPlainText(summary)
        self._refresh_note_editor_state()
        if self.isVisible():
            self._apply_density_mode(self.width())
        self._note_body.setFocus(Qt.FocusReason.OtherFocusReason)

    def _begin_artifact_edit(self, item_id: int, title: str, item_path: str) -> None:
        self._editing_artifact_id = max(0, int(item_id or 0))
        self._artifact_title.setText(title)
        self._artifact_path.setText(item_path)
        self._artifact_save_btn.setText("UPDATE ARTIFACT")
        self._artifact_cancel_btn.setVisible(True)
        if self.isVisible():
            self._apply_density_mode(self.width())

    def _reset_note_editor(self) -> None:
        self._editing_note_id = 0
        self._note_title.clear()
        self._note_body.clear()
        self._refresh_note_editor_state()
        if self.isVisible():
            self._apply_density_mode(self.width())

    def _reset_artifact_editor(self) -> None:
        self._editing_artifact_id = 0
        self._artifact_title.clear()
        self._artifact_path.clear()
        self._artifact_save_btn.setText("SAVE ARTIFACT")
        self._artifact_cancel_btn.setVisible(False)
        if self.isVisible():
            self._apply_density_mode(self.width())

    def _emit_root_request(self) -> None:
        raw_path = self._root_path.text().strip()
        label = self._root_label.text().strip() or "Approved root"
        ok, msg = validate_library_root(raw_path)
        if not ok:
            self._set_root_feedback(msg or "Invalid path.", is_error=True)
            return
        resolved = str(Path(raw_path).expanduser().resolve())
        self.approved_root_requested.emit(resolved, label)
        self._root_path.clear()
        self._root_label.clear()
        self._set_root_feedback("Root save requested. Confirmation will appear in status.", is_error=False)

    def _set_root_feedback(self, message: str, *, is_error: bool) -> None:
        text = str(message or "").strip()
        if not text:
            self._root_feedback_lbl.clear()
            self._root_feedback_lbl.setVisible(False)
            return
        color = T.ERROR if is_error else T.GREEN
        self._root_feedback_lbl.setText(text)
        self._root_feedback_lbl.setStyleSheet(
            f"color: {color}; font-family: '{T.FF_BODY}'; font-size: {T.FS_TINY}pt;"
        )
        self._root_feedback_lbl.setVisible(True)

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
        self._root_picker.blockSignals(True)
        try:
            self._root_picker.clear()
            for root in self._state.approved_roots:
                label = str(root.get("label", "") or "Approved root").strip() or "Approved root"
                detail = str(root.get("detail", "") or "").strip()
                text = label if not detail else f"{label} - {detail}"
                self._root_picker.addItem(text, str(root.get("root_path", "") or "").strip())
            if self._root_picker.count() > 0:
                selected_index = next(
                    (
                        index
                        for index, root in enumerate(self._state.approved_roots)
                        if str(root.get("root_path", "") or "").strip() == self._selected_root_path
                    ),
                    0,
                )
                self._root_picker.setCurrentIndex(max(0, min(selected_index, self._root_picker.count() - 1)))
        finally:
            self._root_picker.blockSignals(False)
        self._root_picker.setVisible(self._root_picker.count() > 0)

    def _refresh_note_editor_state(self) -> None:
        editing = self._editing_note_id > 0
        title = self._note_title.text().strip()
        body_text = self._note_body.toPlainText()
        stripped_body = body_text.strip()
        line_count = len([line for line in body_text.splitlines() if line.strip()])
        self._note_save_btn.setText("UPDATE NOTE" if editing else "PIN NOTE")
        self._note_cancel_btn.setVisible(editing)
        self._note_save_btn.setEnabled(bool(title))
        if editing:
            hint = f"Editing pinned note: {title or 'untitled note'}."
            if stripped_body:
                hint += f" Body ready: {len(stripped_body)} chars across {max(1, line_count)} line(s)."
            else:
                hint += " Add or revise the body, then update it in place."
        elif stripped_body:
            hint = f"New pinned note draft: {len(stripped_body)} chars across {max(1, line_count)} line(s)."
        else:
            hint = "Multiline notes stay in Library and can be reused in Home with USE IN CHAT."
        self._note_editor_hint.setText(hint)

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
        self._clear_dynamic_layout(self._roots_layout)
        roots = [
            root
            for root in self._state.approved_roots
            if self._matches_query(str(root.get("label", "") or ""), str(root.get("detail", "") or ""))
        ]
        if not roots:
            self._roots_layout.addWidget(
                _body(
                    "No approved roots match this search yet." if self._search_query else "No approved roots yet. Add one folder first so Library has a safe place to browse and reuse files from.",
                    color=T.DIM,
                )
            )
            return
        for root in roots:
            root_path = str(root.get("root_path", "") or "").strip()
            is_selected = root_path == self._selected_root_path
            card = QFrame()
            card.setStyleSheet(
                (
                    "QFrame { background-color: rgba(255,255,255,0.80); border: 1px solid rgba(70,98,199,0.34); border-radius: 18px; }"
                    if is_selected
                    else "QFrame { background-color: rgba(255,255,255,0.64); border: 1px solid rgba(214,197,174,0.44); border-radius: 18px; }"
                )
            )
            layout = QVBoxLayout(card)
            layout.setContentsMargins(14, 12, 14, 12)
            layout.setSpacing(6)
            header = QHBoxLayout()
            header.setSpacing(8)
            if is_selected:
                header.addWidget(_mono("ACTIVE ROOT", T.TERTIARY, T.FS_TINY, True))
            header.addWidget(_mono(str(root.get("label", "") or "Approved root"), T.PRIMARY, T.FS_TINY, True))
            header.addStretch()
            browse_btn = QPushButton("BROWSE")
            browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            browse_btn.setStyleSheet(
                f"QPushButton {{ background: {T.BG0}; color: {T.PRIMARY}; border: 1px solid {T.BORDER};"
                f" border-radius: 12px; padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ border-color: {T.PRIMARY}; background: #ffffff; }}"
            )
            browse_btn.clicked.connect(lambda _=False, path=root_path: self._browse_root(path))
            header.addWidget(browse_btn)
            layout.addLayout(header)
            layout.addWidget(_body(str(root.get("detail", "") or "")))
            if is_selected:
                layout.addWidget(_body("This is the current folder Guppy will browse for the file lane below.", color=T.TERTIARY))
            self._roots_layout.addWidget(card)

    def _rebuild_browse_cards(self) -> None:
        self._clear_dynamic_layout(self._browse_layout)
        root_name = self._state.selected_root_label or "Approved root"
        self._selected_root_status.setText(f"CURRENT ROOT · {root_name.upper()}")
        self._selected_root_status.setVisible(bool(self._selected_root_path or self._state.root_file_cards))
        self._browse_hint.setText(self._state.selected_root_hint)
        cards = [
            card
            for card in self._state.root_file_cards
            if self._matches_query(str(card.get("title", "") or ""), str(card.get("detail", "") or ""), str(card.get("kind", "") or ""))
        ]
        if not cards:
            self._browse_layout.addWidget(
                _body(
                    "No browsable files match this search for the selected root." if self._search_query else "No browsable files yet for the current root. Pick a different approved root or add files here, then use USE IN CHAT to send one to Home.",
                    color=T.DIM,
                )
            )
            return
        for card_state in cards:
            card = QFrame()
            card.setStyleSheet(
                "QFrame { background-color: rgba(255,255,255,0.72); border: 1px solid rgba(214,197,174,0.46); border-radius: 20px; }"
            )
            layout = QVBoxLayout(card)
            layout.setContentsMargins(14, 12, 14, 12)
            layout.setSpacing(8)
            top = QHBoxLayout()
            top.setSpacing(8)
            top.addWidget(_mono(str(card_state.get("kind", "file") or "file").upper(), T.SECONDARY, T.FS_TINY, True))
            top.addStretch()
            action = QPushButton(str(card_state.get("action_label", "USE IN CHAT") or "USE IN CHAT"))
            action.setCursor(Qt.CursorShape.PointingHandCursor)
            action.setStyleSheet(
                f"QPushButton {{ background: {T.BG0}; color: {T.PRIMARY}; border: 1px solid {T.BORDER};"
                f" border-radius: 12px; padding: 5px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ border-color: {T.PRIMARY}; background: #ffffff; }}"
            )
            title = str(card_state.get("title", "") or "").strip()
            detail = str(card_state.get("detail", "") or "").strip()
            item_path = str(card_state.get("item_path", "") or "").strip()
            context_ref = str(card_state.get("context_ref", "") or "").strip() or item_path
            prompt = str(card_state.get("prompt", "") or "").strip()
            kind = str(card_state.get("kind", "file") or "file").strip()
            action.clicked.connect(
                lambda _=False, t=title, p=context_ref, k=kind, prompt_text=prompt: self.context_requested.emit(t, p, k, prompt_text)
            )
            top.addWidget(action)
            self._add_media_action(top, card_state)
            layout.addLayout(top)
            layout.addWidget(_body(title, color=T.INK, size=T.FS_LABEL))
            layout.addWidget(_body(detail, color=T.DIM))
            layout.addWidget(_body("USE IN CHAT sends this to Home as the source context for your next reply.", color=T.TERTIARY))
            self._browse_layout.addWidget(card)

    def _rebuild_recent_cards(self) -> None:
        self._clear_dynamic_layout(self._recent_layout)
        cards = [
            card
            for card in self._state.recent_cards
            if self._matches_query(str(card.get("title", "") or ""), str(card.get("detail", "") or ""), str(card.get("kind", "") or ""))
        ]
        if not cards:
            self._recent_layout.addWidget(
                _body(
                    "No recent Library items match this search." if self._search_query else "Recent files, study notes, and coding artifacts from approved roots will show up here after you browse, save, or reuse something from Library.",
                    color=T.DIM,
                )
            )
            return
        for card_state in cards:
            card = QFrame()
            card.setStyleSheet(
                "QFrame { background-color: rgba(255,255,255,0.72); border: 1px solid rgba(214,197,174,0.46); border-radius: 20px; }"
            )
            layout = QVBoxLayout(card)
            layout.setContentsMargins(14, 12, 14, 12)
            layout.setSpacing(8)

            top = QHBoxLayout()
            top.setSpacing(8)
            top.addWidget(_mono(str(card_state.get("kind", "file") or "file").upper(), T.SECONDARY, T.FS_TINY, True))
            top.addStretch()
            action = QPushButton(str(card_state.get("action_label", "USE IN CHAT") or "USE IN CHAT"))
            action.setCursor(Qt.CursorShape.PointingHandCursor)
            action.setStyleSheet(
                f"QPushButton {{ background: {T.BG0}; color: {T.PRIMARY}; border: 1px solid {T.BORDER};"
                f" border-radius: 12px; padding: 5px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ border-color: {T.PRIMARY}; background: #ffffff; }}"
            )
            title = str(card_state.get("title", "") or "").strip()
            detail = str(card_state.get("detail", "") or "").strip()
            item_path = str(card_state.get("item_path", "") or "").strip()
            context_ref = str(card_state.get("context_ref", "") or "").strip() or item_path
            prompt = str(card_state.get("prompt", "") or "").strip()
            kind = str(card_state.get("kind", "file") or "file").strip()
            action.clicked.connect(
                lambda _=False, t=title, p=context_ref, k=kind, prompt_text=prompt: self.context_requested.emit(t, p, k, prompt_text)
            )
            top.addWidget(action)
            self._add_media_action(top, card_state)
            layout.addLayout(top)

            title_lbl = QLabel(title)
            title_lbl.setWordWrap(True)
            title_lbl.setStyleSheet(
                f"color: {T.INK}; font-family: '{T.FF_HEAD}'; font-size: {T.FS_LABEL}pt; font-weight: 700;"
            )
            layout.addWidget(title_lbl)
            layout.addWidget(_body(detail, color=T.DIM))
            layout.addWidget(_body("USE IN CHAT keeps this available on Home as source context for the next reply.", color=T.TERTIARY))
            self._recent_layout.addWidget(card)

    def _rebuild_saved_cards(self) -> None:
        self._clear_dynamic_layout(self._saved_layout)
        cards = [
            card
            for card in self._state.saved_item_cards
            if self._matches_query(
                str(card.get("title", "") or ""),
                str(card.get("detail", "") or ""),
                str(card.get("kind", "") or ""),
                str(card.get("summary", "") or ""),
            )
        ]
        if not cards:
            self._saved_layout.addWidget(
                _body(
                    "No pinned notes or artifacts match this search." if self._search_query else "Pinned notes and saved artifacts stay here until you edit them, send them to Home with USE IN CHAT, or remove them.",
                    color=T.DIM,
                )
            )
            return
        for card_state in cards:
            card = QFrame()
            card.setStyleSheet(
                "QFrame { background-color: rgba(255,255,255,0.72); border: 1px solid rgba(214,197,174,0.46); border-radius: 20px; }"
            )
            layout = QVBoxLayout(card)
            layout.setContentsMargins(14, 12, 14, 12)
            layout.setSpacing(8)
            top = QHBoxLayout()
            top.setSpacing(8)
            top.addWidget(_mono(str(card_state.get("kind", "note") or "note").upper(), T.SECONDARY, T.FS_TINY, True))
            top.addStretch()
            use_btn = QPushButton("USE IN CHAT")
            edit_btn = QPushButton("EDIT")
            delete_btn = QPushButton("DELETE")
            for button in (use_btn, edit_btn, delete_btn):
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                button.setStyleSheet(
                    f"QPushButton {{ background: {T.BG0}; color: {T.PRIMARY}; border: 1px solid {T.BORDER};"
                    f" border-radius: 12px; padding: 5px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                    f"QPushButton:hover {{ border-color: {T.PRIMARY}; background: #ffffff; }}"
                )
            item_id = int(str(card_state.get("id", "0") or "0"))
            title = str(card_state.get("full_title", card_state.get("title", "")) or "").strip()
            detail = str(card_state.get("detail", "") or "").strip()
            item_path = str(card_state.get("item_path", "") or "").strip()
            context_ref = str(card_state.get("context_ref", "") or "").strip() or item_path
            summary = str(card_state.get("summary", "") or "").strip()
            prompt = str(card_state.get("prompt", "") or "").strip()
            kind = str(card_state.get("kind", "note") or "note").strip()
            use_btn.clicked.connect(
                lambda _=False, t=title, p=context_ref, k=kind, prompt_text=prompt: self.context_requested.emit(t, p, k, prompt_text)
            )
            if kind == "note":
                edit_btn.clicked.connect(lambda _=False, i=item_id, t=title, s=summary: self._begin_note_edit(i, t, s))
            else:
                edit_btn.clicked.connect(lambda _=False, i=item_id, t=title, p=item_path: self._begin_artifact_edit(i, t, p))
            delete_btn.clicked.connect(
                lambda _=False, i=item_id, t=title: self.library_item_delete_requested.emit(i, t)
            )
            top.addWidget(use_btn)
            self._add_media_action(top, card_state)
            top.addWidget(edit_btn)
            top.addWidget(delete_btn)
            layout.addLayout(top)
            layout.addWidget(_body(title, color=T.INK, size=T.FS_LABEL))
            layout.addWidget(_body(detail, color=T.DIM))
            layout.addWidget(_body("USE IN CHAT makes this note or artifact available on Home without leaving the current session.", color=T.TERTIARY))
            self._saved_layout.addWidget(card)

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
