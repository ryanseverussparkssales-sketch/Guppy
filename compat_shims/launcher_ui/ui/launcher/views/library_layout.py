from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
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

from .. import tokens as T
from .library_media_panel import LibraryMediaPanel
from .library_view_components import body_label as _body
from .library_view_components import build_summary_card as _build_summary_card
from .library_view_components import mono_label as _mono


def _styled_line_edit() -> str:
    return (
        f"QLineEdit {{ background: rgba(255,255,255,0.90); border: 1px solid rgba(214,197,174,0.56); color: {T.TEXT};"
        f" border-radius: 14px; padding: 6px 10px; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt; }}"
    )


def _styled_button(color: str) -> str:
    return (
        f"QPushButton {{ background: {T.BG0}; color: {color}; border: 1px solid {T.BORDER};"
        f" border-radius: 12px; padding: 6px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        f"QPushButton:hover {{ border-color: {color}; background: #ffffff; }}"
    )


def build_library_layout(owner) -> None:
    outer = QVBoxLayout(owner)
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
        f"color: {T.TEXT}; font-family: '{T.FF_HEAD}'; font-size: 28pt; font-weight: 700;"
    )
    title_row.addWidget(title)
    title_row.addStretch()
    owner._workspace_chip = QLabel("DAILY WORKSPACE")
    owner._workspace_chip.setStyleSheet(
        f"color: {T.ACCENT_ORANGE}; background: rgba(255,109,0,0.10); border: 1px solid rgba(255,109,0,0.30);"
        f" border-radius: 4px; padding: 6px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
    )
    title_row.addWidget(owner._workspace_chip)
    header_layout.addLayout(title_row)

    purpose = QLabel("LIBRARY — Save files, notes, and assistant output so they can be attached to future conversations.")
    purpose.setObjectName("hub-purpose")
    purpose.setWordWrap(True)
    purpose.setStyleSheet(
        f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
    )
    header_layout.addWidget(purpose)

    owner._summary_lbl = _body("")
    header_layout.addWidget(owner._summary_lbl)

    owner._roots_lbl = _body("", color=T.ACCENT_ORANGE, size=T.FS_TINY)
    header_layout.addWidget(owner._roots_lbl)

    owner._search = QLineEdit()
    owner._search.setPlaceholderText("Search files, notes, and saved workspace context")
    owner._search.setStyleSheet(
        f"QLineEdit {{ background: rgba(255,255,255,0.88); border: 1px solid rgba(214,197,174,0.62); color: {T.TEXT};"
        f" border-radius: 18px; padding: 8px 12px; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt; }}"
    )
    owner._search.textChanged.connect(owner._apply_search_query)
    header_layout.addWidget(owner._search)
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
    owner._root_path = QLineEdit()
    owner._root_path.setPlaceholderText("Approved root path")
    owner._root_label = QLineEdit()
    owner._root_label.setPlaceholderText("Label")
    owner._root_repo_btn = QPushButton("USE REPO")
    owner._root_repo_btn.setToolTip("Use the current Guppy repository as an approved root")
    owner._root_repo_btn.clicked.connect(owner._fill_repo_root)
    owner._root_browse_btn = QPushButton("PICK FOLDER")
    owner._root_browse_btn.setToolTip("Browse and choose a folder to approve")
    owner._root_browse_btn.clicked.connect(owner._choose_root_path)
    owner._root_save_btn = QPushButton("SAVE ROOT")
    owner._root_save_btn.setToolTip("Submit this root for approval in the active workspace")
    owner._root_save_btn.clicked.connect(owner._emit_root_request)
    for widget in (owner._root_path, owner._root_label):
        widget.setStyleSheet(_styled_line_edit())
    for button in (owner._root_repo_btn, owner._root_browse_btn, owner._root_save_btn):
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(_styled_button(T.PRIMARY))
    root_row.addWidget(owner._root_path, stretch=2)
    root_row.addWidget(owner._root_label, stretch=1)
    root_row.addWidget(owner._root_repo_btn)
    root_row.addWidget(owner._root_browse_btn)
    root_row.addWidget(owner._root_save_btn)
    manager_layout.addLayout(root_row)
    owner._root_feedback_lbl = _body("", color=T.DIM, size=T.FS_TINY)
    owner._root_feedback_lbl.setVisible(False)
    manager_layout.addWidget(owner._root_feedback_lbl)

    note_row = QVBoxLayout()
    note_row.setSpacing(8)
    note_top = QHBoxLayout()
    note_top.setSpacing(8)
    owner._note_title = QLineEdit()
    owner._note_title.setPlaceholderText("Pinned note title")
    owner._note_body = QPlainTextEdit()
    owner._note_body.setPlaceholderText("Pinned note body")
    owner._note_body.setFixedHeight(92)
    owner._note_save_btn = QPushButton("PIN NOTE")
    owner._note_save_btn.setToolTip("Save this note and pin it to the active workspace library")
    owner._note_save_btn.clicked.connect(owner._emit_note_request)
    owner._note_title.setStyleSheet(_styled_line_edit())
    owner._note_body.setStyleSheet(
        f"QPlainTextEdit {{ background: rgba(255,255,255,0.90); border: 1px solid rgba(214,197,174,0.56); color: {T.TEXT};"
        f" border-radius: 14px; padding: 8px 10px; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt; }}"
    )
    owner._note_save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    owner._note_save_btn.setStyleSheet(_styled_button(T.PRIMARY))
    owner._note_cancel_btn = QPushButton("CANCEL EDIT")
    owner._note_cancel_btn.setToolTip("Discard changes and reset the note editor")
    owner._note_cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    owner._note_cancel_btn.setStyleSheet(_styled_button(T.SECONDARY))
    owner._note_cancel_btn.clicked.connect(owner._reset_note_editor)
    owner._note_cancel_btn.setVisible(False)
    owner._note_title.textChanged.connect(owner._refresh_note_editor_state)
    owner._note_body.textChanged.connect(owner._refresh_note_editor_state)
    note_top.addWidget(owner._note_title, stretch=1)
    note_top.addWidget(owner._note_save_btn)
    note_top.addWidget(owner._note_cancel_btn)
    note_row.addLayout(note_top)
    note_row.addWidget(owner._note_body)
    owner._note_editor_hint = _body("", color=T.DIM, size=T.FS_TINY)
    note_row.addWidget(owner._note_editor_hint)
    manager_layout.addLayout(note_row)

    artifact_row = QHBoxLayout()
    artifact_row.setSpacing(8)
    owner._artifact_title = QLineEdit()
    owner._artifact_title.setPlaceholderText("Artifact title")
    owner._artifact_path = QLineEdit()
    owner._artifact_path.setPlaceholderText("Artifact path or bundle location")
    owner._artifact_browse_btn = QPushButton("PICK FILE")
    owner._artifact_browse_btn.setToolTip("Browse and select a file to register as a library artifact")
    owner._artifact_browse_btn.clicked.connect(owner._choose_artifact_path)
    owner._artifact_save_btn = QPushButton("SAVE ARTIFACT")
    owner._artifact_save_btn.setToolTip("Save this artifact reference to the active workspace library")
    owner._artifact_save_btn.clicked.connect(owner._emit_artifact_request)
    for widget in (owner._artifact_title, owner._artifact_path):
        widget.setStyleSheet(_styled_line_edit())
    for button in (owner._artifact_browse_btn, owner._artifact_save_btn):
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(_styled_button(T.PRIMARY))
    owner._artifact_cancel_btn = QPushButton("CANCEL EDIT")
    owner._artifact_cancel_btn.setToolTip("Discard changes and reset the artifact editor")
    owner._artifact_cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    owner._artifact_cancel_btn.setStyleSheet(_styled_button(T.SECONDARY))
    owner._artifact_cancel_btn.clicked.connect(owner._reset_artifact_editor)
    owner._artifact_cancel_btn.setVisible(False)
    artifact_row.addWidget(owner._artifact_title, stretch=1)
    artifact_row.addWidget(owner._artifact_path, stretch=2)
    artifact_row.addWidget(owner._artifact_browse_btn)
    artifact_row.addWidget(owner._artifact_save_btn)
    artifact_row.addWidget(owner._artifact_cancel_btn)
    manager_layout.addLayout(artifact_row)
    layout.addWidget(manager)

    owner._recent_lbl = _mono("", T.PRIMARY, T.FS_TINY, True)
    layout.addWidget(owner._recent_lbl)

    owner._roots_header = _mono("APPROVED ROOTS", T.PRIMARY, T.FS_TINY, True)
    layout.addWidget(owner._roots_header)
    owner._roots_hint = _body(
        "Choose which folders Guppy may browse. Nothing outside approved roots is scanned, and Library only reuses files from these approved locations.",
        color=T.DIM,
    )
    layout.addWidget(owner._roots_hint)
    owner._roots_host = QWidget()
    owner._roots_layout = QVBoxLayout(owner._roots_host)
    owner._roots_layout.setContentsMargins(0, 0, 0, 0)
    owner._roots_layout.setSpacing(10)
    layout.addWidget(owner._roots_host)

    owner._browse_header = _mono("BROWSE ROOT FILES", T.PRIMARY, T.FS_TINY, True)
    layout.addWidget(owner._browse_header)
    browse_picker_row = QHBoxLayout()
    browse_picker_row.setSpacing(8)
    owner._root_picker = QComboBox()
    owner._root_picker.setToolTip("Switch between approved roots without scrolling back to the approved-root cards")
    owner._root_picker.setStyleSheet(
        f"QComboBox {{ background: rgba(255,255,255,0.90); border: 1px solid rgba(214,197,174,0.56); color: {T.TEXT};"
        f" border-radius: 14px; padding: 6px 10px; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt; }}"
        "QComboBox::drop-down { border: none; padding-right: 6px; }"
    )
    owner._root_picker.currentIndexChanged.connect(owner._on_root_picker_changed)
    browse_picker_row.addWidget(owner._root_picker, stretch=1)
    layout.addLayout(browse_picker_row)
    owner._selected_root_status = _mono("", T.SECONDARY, T.FS_TINY, True)
    layout.addWidget(owner._selected_root_status)
    owner._browse_hint = _body("", color=T.DIM)
    layout.addWidget(owner._browse_hint)
    owner._browse_host = QWidget()
    owner._browse_layout = QVBoxLayout(owner._browse_host)
    owner._browse_layout.setContentsMargins(0, 0, 0, 0)
    owner._browse_layout.setSpacing(10)
    layout.addWidget(owner._browse_host)

    grid_host = QWidget()
    grid = QGridLayout(grid_host)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(14)
    grid.setVerticalSpacing(14)

    owner._files_card, owner._files_copy = _build_summary_card(
        "FILES & SOURCES",
        "Saved documents, notes, screenshots, and imported context will appear here.",
    )
    owner._study_card, owner._study_copy = _build_summary_card(
        "STUDY CONTEXT",
        "Summaries, outlines, review packets, and reading context will collect here.",
    )
    owner._coding_card, owner._coding_copy = _build_summary_card(
        "CODING CONTEXT",
        "Repo notes, module targets, diffs, and artifact handoffs will appear here.",
    )
    owner._artifact_card, owner._artifact_copy = _build_summary_card(
        "NEXT BUILD",
        "The active workspace will eventually pin recent files, outputs, and reusable context here.",
    )
    grid.addWidget(owner._files_card, 0, 0)
    grid.addWidget(owner._study_card, 0, 1)
    grid.addWidget(owner._coding_card, 1, 0)
    grid.addWidget(owner._artifact_card, 1, 1)
    layout.addWidget(grid_host)

    owner._media_header = _mono("LOCAL MEDIA", T.PRIMARY, T.FS_TINY, True)
    layout.addWidget(owner._media_header)
    owner._media_hint = _body(
        "Load local audio or video from approved roots or saved media artifacts without leaving Library.",
        color=T.DIM,
    )
    layout.addWidget(owner._media_hint)
    owner._media_panel = LibraryMediaPanel(owner)
    layout.addWidget(owner._media_panel)

    owner._recent_header = _mono("READY TO USE IN CHAT", T.PRIMARY, T.FS_TINY, True)
    layout.addWidget(owner._recent_header)
    owner._recent_hint = _body(
        "Recent files and Library saves show up here first. USE IN CHAT attaches one as source context for the next reply and sends it back to Home.",
        color=T.DIM,
    )
    layout.addWidget(owner._recent_hint)
    owner._recent_host = QWidget()
    owner._recent_layout = QVBoxLayout(owner._recent_host)
    owner._recent_layout.setContentsMargins(0, 0, 0, 0)
    owner._recent_layout.setSpacing(10)
    layout.addWidget(owner._recent_host)

    owner._saved_header = _mono("PINNED NOTES & ARTIFACTS", T.PRIMARY, T.FS_TINY, True)
    layout.addWidget(owner._saved_header)
    owner._saved_hint = _body(
        "Keep durable notes and artifacts here so they can be edited, reused in chat, or removed cleanly.",
        color=T.DIM,
    )
    layout.addWidget(owner._saved_hint)
    owner._saved_host = QWidget()
    owner._saved_layout = QVBoxLayout(owner._saved_host)
    owner._saved_layout.setContentsMargins(0, 0, 0, 0)
    owner._saved_layout.setSpacing(10)
    layout.addWidget(owner._saved_host)
    layout.addStretch()

    scroll.setWidget(content)
    outer.addWidget(scroll)
