"""
assistant_shell_workspace.py
Workspace-details host builder — extracted from assistant_shell_sections.py.
"""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from .. import tokens as T


def build_workspace_details_host(
    owner,
    label_factory: Callable[[str, str, int, bool], QLabel],
) -> None:
    owner._workspace_details_strip = QFrame()
    owner._workspace_details_strip.setObjectName("workspace_details_strip")
    owner._workspace_details_strip.setStyleSheet(
        "QFrame#workspace_details_strip { background-color: rgba(255,255,255,0.48); border: 1px solid rgba(214,197,174,0.36); border-radius: 18px; }"
    )
    details_strip_layout = QHBoxLayout(owner._workspace_details_strip)
    details_strip_layout.setContentsMargins(14, 10, 14, 10)
    details_strip_layout.setSpacing(10)
    owner._workspace_details_summary = QLabel("")
    owner._workspace_details_summary.setWordWrap(True)
    owner._workspace_details_summary.setStyleSheet(
        f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_TINY}pt;"
    )
    owner._workspace_details_btn = QPushButton("DETAILS")
    owner._workspace_details_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    owner._workspace_details_btn.setStyleSheet(
        f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.DIM}; border: 1px solid rgba(214,197,174,0.54);"
        f" border-radius: 12px; padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        f"QPushButton:hover {{ border-color: rgba(0,106,106,0.46); color: {T.ACCENT_TEAL}; background: #ffffff; }}"
    )
    owner._workspace_details_btn.clicked.connect(owner._toggle_workspace_details)
    details_strip_layout.addWidget(owner._workspace_details_summary, stretch=1)
    details_strip_layout.addWidget(owner._workspace_details_btn)

    owner._workspace_details_host = QFrame()
    workspace_details_layout = QVBoxLayout(owner._workspace_details_host)
    workspace_details_layout.setContentsMargins(0, 0, 0, 0)
    workspace_details_layout.setSpacing(10)

    owner._workspace_dock = QFrame()
    owner._workspace_dock.setObjectName("workspace_dock")
    owner._workspace_dock.setStyleSheet(
        "QFrame#workspace_dock { background-color: rgba(255,255,255,0.56); border: 1px solid rgba(214,197,174,0.42); border-radius: 24px; }"
    )
    dock_layout = QHBoxLayout(owner._workspace_dock)
    dock_layout.setContentsMargins(14, 14, 14, 14)
    dock_layout.setSpacing(12)
    owner._files_context_lbl = QLabel("")
    owner._study_context_lbl = QLabel("")
    owner._coding_context_lbl = QLabel("")
    for title, target in (
        ("FILES", owner._files_context_lbl),
        ("STUDY", owner._study_context_lbl),
        ("BUILD", owner._coding_context_lbl),
    ):
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background-color: rgba(255,255,255,0.72); border: 1px solid rgba(214,197,174,0.40); border-radius: 18px; }"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(6)
        card_layout.addWidget(label_factory(title, T.PRIMARY, T.FS_TINY, True))
        target.setWordWrap(True)
        target.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;"
        )
        card_layout.addWidget(target)
        dock_layout.addWidget(card, stretch=1)
    workspace_details_layout.addWidget(owner._workspace_dock)

    owner._latest_output_host = QFrame()
    owner._latest_output_host.setObjectName("latest_output_host")
    owner._latest_output_host.setStyleSheet(
        "QFrame#latest_output_host { background-color: rgba(255,255,255,0.54); border: 1px solid rgba(214,197,174,0.40); border-radius: 18px; }"
    )
    latest_output_layout = QHBoxLayout(owner._latest_output_host)
    latest_output_layout.setContentsMargins(14, 12, 14, 12)
    latest_output_layout.setSpacing(12)
    latest_output_text = QVBoxLayout()
    latest_output_text.setSpacing(4)
    owner._latest_output_title = label_factory("LATEST SAVED OUTPUT", T.PRIMARY, T.FS_TINY, True)
    owner._latest_output_summary = QLabel("")
    owner._latest_output_summary.setWordWrap(True)
    owner._latest_output_summary.setStyleSheet(
        f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;"
    )
    latest_output_text.addWidget(owner._latest_output_title)
    latest_output_text.addWidget(owner._latest_output_summary)
    latest_output_layout.addLayout(latest_output_text, stretch=1)
    owner._latest_output_library_btn = QPushButton("IN LIBRARY")
    owner._latest_output_library_btn.setToolTip("Open this saved output in the Library view")
    owner._latest_output_attach_btn = QPushButton("ATTACH NOW")
    owner._latest_output_attach_btn.setToolTip("Attach this saved output as context for the next reply")
    for button in (owner._latest_output_library_btn, owner._latest_output_attach_btn):
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(
            f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.TERTIARY}; border: 1px solid rgba(214,197,174,0.44);"
            f" border-radius: 10px; padding: 4px 8px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: rgba(70,98,199,0.42); background: #ffffff; }}"
        )
    owner._latest_output_library_btn.clicked.connect(owner._emit_latest_saved_output_library)
    owner._latest_output_attach_btn.clicked.connect(owner._emit_latest_saved_output_attach)
    latest_output_layout.addWidget(owner._latest_output_library_btn)
    latest_output_layout.addWidget(owner._latest_output_attach_btn)
    owner._latest_output_host.setVisible(False)
    workspace_details_layout.addWidget(owner._latest_output_host)

    owner._active_context_host = QFrame()
    owner._active_context_host.setObjectName("active_context_host")
    owner._active_context_host.setStyleSheet(
        "QFrame#active_context_host { background-color: rgba(255,255,255,0.52); border: 1px solid rgba(214,197,174,0.38); border-radius: 20px; }"
    )
    active_context_layout = QVBoxLayout(owner._active_context_host)
    active_context_layout.setContentsMargins(16, 14, 16, 14)
    active_context_layout.setSpacing(10)
    active_context_top = QHBoxLayout()
    active_context_top.setSpacing(10)
    owner._active_context_title = label_factory("CURRENT SOURCES", T.PRIMARY, T.FS_TINY, True)
    active_context_top.addWidget(owner._active_context_title)
    active_context_top.addStretch()
    owner._active_context_clear_btn = QPushButton("CLEAR SOURCES")
    owner._active_context_clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    owner._active_context_clear_btn.setToolTip("Remove all currently attached sources")
    owner._active_context_clear_btn.setAccessibleName("Clear attached sources")
    owner._active_context_clear_btn.setAccessibleDescription("Clears all active context sources")
    owner._active_context_clear_btn.setStyleSheet(
        f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.ERROR}; border: 1px solid rgba(214,197,174,0.54);"
        f" border-radius: 12px; padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        f"QPushButton:hover {{ border-color: rgba(200,75,68,0.42); background: #ffffff; }}"
    )
    owner._active_context_clear_btn.clicked.connect(owner.active_context_clear_requested.emit)
    owner._active_context_refresh_btn = QPushButton("REFRESH SAVED SOURCE")
    owner._active_context_refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    owner._active_context_refresh_btn.setToolTip("Refresh the primary saved source using the latest assistant reply")
    owner._active_context_refresh_btn.setAccessibleName("Refresh saved source")
    owner._active_context_refresh_btn.setAccessibleDescription("Refreshes the primary saved source")
    owner._active_context_refresh_btn.setStyleSheet(
        f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.TERTIARY}; border: 1px solid rgba(214,197,174,0.54);"
        f" border-radius: 12px; padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        f"QPushButton:hover {{ border-color: rgba(70,98,199,0.42); background: #ffffff; }}"
    )
    owner._active_context_refresh_btn.clicked.connect(owner._emit_active_context_refresh_requested)
    owner._active_context_refresh_btn.setVisible(False)
    owner._active_context_pin_default_btn = QPushButton("PIN PRIMARY")
    owner._active_context_pin_default_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    owner._active_context_pin_default_btn.setToolTip("Pin the primary source as this workspace default")
    owner._active_context_pin_default_btn.setAccessibleName("Pin default source")
    owner._active_context_pin_default_btn.setAccessibleDescription("Pins the primary source for this workspace")
    owner._active_context_pin_default_btn.setStyleSheet(
        f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.SECONDARY}; border: 1px solid rgba(214,197,174,0.54);"
        f" border-radius: 12px; padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        f"QPushButton:hover {{ border-color: rgba(47,111,122,0.42); background: #ffffff; }}"
    )
    owner._active_context_pin_default_btn.clicked.connect(owner._emit_active_context_default_requested)
    owner._active_context_pin_default_btn.setVisible(False)
    owner._active_context_swap_btn = QPushButton("MAKE PRIMARY SOURCE")
    owner._active_context_swap_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    owner._active_context_swap_btn.setToolTip("Promote another attached source to primary")
    owner._active_context_swap_btn.setAccessibleName("Make primary source")
    owner._active_context_swap_btn.setAccessibleDescription("Promotes a non-primary source to primary")
    owner._active_context_swap_btn.setStyleSheet(
        f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.TERTIARY}; border: 1px solid rgba(214,197,174,0.54);"
        f" border-radius: 12px; padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        f"QPushButton:hover {{ border-color: rgba(70,98,199,0.42); background: #ffffff; }}"
    )
    owner._active_context_swap_btn.clicked.connect(owner._emit_active_context_swap_requested)
    owner._active_context_swap_btn.setVisible(False)
    active_context_top.addWidget(owner._active_context_refresh_btn)
    active_context_top.addWidget(owner._active_context_pin_default_btn)
    active_context_top.addWidget(owner._active_context_swap_btn)
    active_context_top.addWidget(owner._active_context_clear_btn)
    active_context_layout.addLayout(active_context_top)
    owner._active_context_summary = QLabel("No Library sources attached yet. Open Library and use USE IN CHAT to ground the next reply.")
    owner._active_context_summary.setWordWrap(True)
    owner._active_context_summary.setStyleSheet(
        f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;"
    )
    active_context_layout.addWidget(owner._active_context_summary)
    owner._active_context_row = QHBoxLayout()
    owner._active_context_row.setSpacing(10)
    active_context_layout.addLayout(owner._active_context_row)
    owner._active_context_host.setVisible(False)
    owner._last_context_notice = ""
    owner._focused_context_title = ""
    owner._previewed_context_title = ""
    owner._default_context_source_title = ""
    workspace_details_layout.addWidget(owner._active_context_host)
