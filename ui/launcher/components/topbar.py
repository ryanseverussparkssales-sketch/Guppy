"""
ui/launcher/components/topbar.py
Premium top navigation / header bar.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import tokens as T


class TopBar(QFrame):
    search_submitted = Signal(str)
    quick_action = Signal(str)
    instance_selected = Signal(str)
    nav_requested = Signal(int)
    launcher_context_requested = Signal()

    _NAV_TABS = [
        ("HOME", 0),
        ("WORKSPACES", 1),
        ("APP MGMT", 3),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._notif_count = 0
        self._notif_severity = "info"
        self.setFixedHeight(T.TOPBAR_H)
        self.setObjectName("topbar")
        self.setStyleSheet(
            f"QFrame#topbar {{ background-color: rgba(246,240,228,0.92); border-bottom: 1px solid rgba(205,181,154,0.45); }}"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 0, 16, 0)
        row.setSpacing(10)

        brand_col = QVBoxLayout()
        brand_col.setSpacing(0)
        title = QLabel("Guppy")
        title.setStyleSheet(
            f"color: {T.INK}; font-family: '{T.FF_HEAD}'; font-size: {T.FS_HERO}pt; font-weight: bold;"
        )
        self._session_lbl = QLabel("daily assistant workspace")
        self._session_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        brand_col.addWidget(title)
        brand_col.addWidget(self._session_lbl)
        row.addLayout(brand_col)

        self._nav_btns: list[QPushButton] = []
        for label, idx in self._NAV_TABS:
            btn = QPushButton(label)
            btn.setFixedHeight(34)
            btn.clicked.connect(lambda _=False, i=idx: self._on_nav(i))
            btn.setStyleSheet(self._nav_style(False))
            btn.setVisible(False)
            self._nav_btns.append(btn)

        row.addStretch()

        workspace_shell = QFrame()
        workspace_shell.setStyleSheet(
            "background-color: rgba(255,250,243,0.88);"
            " border: 1px solid rgba(205,181,154,0.55);"
            " border-radius: 18px;"
        )
        workspace_row = QHBoxLayout(workspace_shell)
        workspace_row.setContentsMargins(10, 5, 10, 5)
        workspace_row.setSpacing(7)
        inst_lbl = QLabel("Workspace")
        inst_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        self._instance_cb = QComboBox()
        self._instance_cb.setFixedWidth(168)
        self._instance_cb.currentTextChanged.connect(self._on_instance_selected)
        workspace_row.addWidget(inst_lbl)
        workspace_row.addWidget(self._instance_cb)
        row.addWidget(workspace_shell)

        self._launcher_summary_btn = QPushButton("CHAT / AUTO / GUPPY / LIGHT")
        self._launcher_summary_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._launcher_summary_btn.setToolTip("Open the active chat context controls.")
        self._launcher_summary_btn.setMinimumWidth(204)
        self._launcher_summary_btn.setStyleSheet(
            f"QPushButton {{ background-color: rgba(255,250,243,0.88); color: {T.TEXT};"
            f" border: 1px solid rgba(205,181,154,0.55); border-radius: 18px; padding: 8px 12px;"
            f" font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px; text-align: left; }}"
            f"QPushButton:hover {{ border-color: {T.PRIMARY}; color: {T.PRIMARY}; background-color: #ffffff; }}"
        )
        self._launcher_summary_btn.clicked.connect(self.launcher_context_requested.emit)
        row.addWidget(self._launcher_summary_btn)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search system, notes, or commands")
        self._search.setFixedWidth(214)
        self._search.returnPressed.connect(lambda: self.search_submitted.emit(self._search.text()))
        row.addWidget(self._search)

        notif_wrap = QWidget()
        notif_wrap.setFixedSize(36, 36)
        notif_layout = QVBoxLayout(notif_wrap)
        notif_layout.setContentsMargins(0, 0, 0, 0)
        notif_layout.setSpacing(0)
        self._notif_btn = QPushButton("\U0001F514")
        self._notif_btn.setFixedSize(36, 36)
        self._notif_btn.setToolTip("Open launcher warnings and recovery events in App Management.")
        self._notif_btn.clicked.connect(lambda: self.quick_action.emit("notifications"))
        self._notif_btn.setStyleSheet(self._icon_button_style(T.BG0, T.TEXT))
        notif_layout.addWidget(self._notif_btn)
        self._notif_badge = QLabel("")
        self._notif_badge.setParent(notif_wrap)
        self._notif_badge.setFixedHeight(16)
        self._notif_badge.setMinimumWidth(16)
        self._notif_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._notif_badge.move(20, 0)
        self._notif_badge.hide()
        self._apply_notif_style()

        self._term_btn = QPushButton("\u2328")
        self._term_btn.setFixedSize(36, 36)
        self._term_btn.setToolTip("Open operator logs and recent command activity in App Management.")
        self._term_btn.setStyleSheet(self._icon_button_style(T.BG0, T.TEXT))
        self._term_btn.clicked.connect(lambda: self.quick_action.emit("terminal"))

        row.addWidget(notif_wrap)
        row.addWidget(self._term_btn)

        self.set_active_tab(0)
        self.set_instances(["guppy-primary"], active_instance="guppy-primary")

    @staticmethod
    def _nav_style(active: bool) -> str:
        if active:
            return (
                f"QPushButton {{ background-color: {T.INK}; color: white; border: none; border-radius: 14px;"
                f" padding: 0 14px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 2px; }}"
            )
        return (
            f"QPushButton {{ background-color: transparent; color: {T.DIM}; border: none; border-radius: 14px;"
            f" padding: 0 14px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 2px; }}"
            f"QPushButton:hover {{ color: {T.INK}; background-color: rgba(255,107,61,0.08); }}"
        )

    @staticmethod
    def _icon_button_style(bg: str, color: str) -> str:
        return (
            f"QPushButton {{ background-color: {bg}; color: {color}; border: 1px solid rgba(205,181,154,0.55);"
            f" border-radius: 18px; font-size: 13pt; }}"
            f"QPushButton:hover {{ border-color: {T.PRIMARY}; color: {T.PRIMARY}; background-color: #ffffff; }}"
        )

    def _on_nav(self, tab_index: int) -> None:
        self.set_active_tab(tab_index)
        self.nav_requested.emit(tab_index)

    def set_active_tab(self, tab_index: int) -> None:
        for btn, (_, idx) in zip(self._nav_btns, self._NAV_TABS):
            btn.setStyleSheet(self._nav_style(idx == tab_index))

    def set_session(self, text: str) -> None:
        clean = (text or "daily assistant workspace").strip() or "daily assistant workspace"
        self._session_lbl.setText(clean.lower())

    def set_launcher_summary(self, text: str) -> None:
        summary = (text or "AUTO / GUPPY / LIGHT").strip() or "AUTO / GUPPY / LIGHT"
        summary = summary.replace("[EDIT]", "").replace("[OPEN]", "OPEN").strip()
        if not summary.startswith("CHAT"):
            summary = f"CHAT / {summary}"
        self._launcher_summary_btn.setText(summary)

    def set_notification_badge(self, count: int, severity: str = "info") -> None:
        self._notif_count = max(0, int(count or 0))
        self._notif_severity = (severity or "info").strip().lower() or "info"
        self._apply_notif_style()

    def _apply_notif_style(self) -> None:
        btn_color = T.TEXT
        badge_color = T.TERTIARY
        if self._notif_severity == "error":
            btn_color = T.ERROR
            badge_color = T.ERROR
        elif self._notif_severity == "warn":
            btn_color = T.PRIMARY
            badge_color = T.PRIMARY

        self._notif_btn.setStyleSheet(self._icon_button_style(T.BG0, btn_color))
        if self._notif_count <= 0:
            self._notif_badge.hide()
            return

        text = "99+" if self._notif_count > 99 else str(self._notif_count)
        width = 24 if len(text) > 2 else 16
        self._notif_badge.setFixedWidth(width)
        self._notif_badge.move(max(12, 36 - width), 0)
        self._notif_badge.setText(text)
        self._notif_badge.setStyleSheet(
            f"background-color: {badge_color}; color: white; border-radius: 8px;"
            f"font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; padding: 0 2px;"
        )
        self._notif_badge.show()

    def set_instances(self, instances: list[str], active_instance: str = "") -> None:
        names = [str(item).strip() for item in instances if str(item).strip()]
        if not names:
            names = ["guppy-primary"]
        target = (active_instance or "").strip() or names[0]

        self._instance_cb.blockSignals(True)
        self._instance_cb.clear()
        self._instance_cb.addItems(names)
        if target in names:
            self._instance_cb.setCurrentText(target)
        else:
            self._instance_cb.setCurrentIndex(0)
        self._instance_cb.blockSignals(False)

    def set_active_instance(self, name: str) -> None:
        target = (name or "").strip()
        if not target:
            return
        idx = self._instance_cb.findText(target)
        if idx >= 0 and idx != self._instance_cb.currentIndex():
            self._instance_cb.blockSignals(True)
            self._instance_cb.setCurrentIndex(idx)
            self._instance_cb.blockSignals(False)

    def _on_instance_selected(self, name: str) -> None:
        target = (name or "").strip()
        if target:
            self.instance_selected.emit(target)
