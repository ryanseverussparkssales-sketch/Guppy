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
        ("LIBRARY", 2),
        ("SETTINGS", 4),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._notif_count = 0
        self._notif_severity = "info"
        self.setFixedHeight(T.TOPBAR_H)
        self.setObjectName("topbar")
        self.setStyleSheet(
            f"QFrame#topbar {{ background-color: rgba(255,253,248,0.94); border-bottom: 1px solid rgba(214,197,174,0.60); }}"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(18, 10, 18, 10)
        row.setSpacing(12)

        brand_col = QVBoxLayout()
        brand_col.setSpacing(0)
        title = QLabel("Guppy")
        title.setStyleSheet(
            f"color: {T.INK}; font-family: '{T.FF_HEAD}'; font-size: {T.FS_HERO}pt; font-weight: 700;"
        )
        self._session_lbl = QLabel("daily path for chat, files, and workspace context")
        self._session_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;"
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
            self._nav_btns.append(btn)
            row.addWidget(btn)

        row.addStretch()

        workspace_shell = QFrame()
        workspace_shell.setStyleSheet(
            "background-color: rgba(244,239,231,0.88);"
            " border: 1px solid rgba(214,197,174,0.72);"
            " border-radius: 20px;"
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

        self._launcher_summary_btn = QPushButton("HOME / AUTO / GUPPY / LIGHT")
        self._launcher_summary_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._launcher_summary_btn.setToolTip("Open Home context controls for this workspace.")
        self._launcher_summary_btn.setMinimumWidth(204)
        self._launcher_summary_btn.setStyleSheet(
            f"QPushButton {{ background-color: rgba(244,239,231,0.90); color: {T.TEXT};"
            f" border: 1px solid rgba(214,197,174,0.72); border-radius: 20px; padding: 8px 14px;"
            f" font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px; text-align: left; }}"
            f"QPushButton:hover {{ border-color: {T.TERTIARY}; color: {T.INK}; background-color: #ffffff; }}"
        )
        self._launcher_summary_btn.clicked.connect(self.launcher_context_requested.emit)
        row.addWidget(self._launcher_summary_btn)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search Home, files, and Library")
        self._search.setFixedWidth(236)
        self._search.returnPressed.connect(lambda: self.search_submitted.emit(self._search.text()))
        row.addWidget(self._search)

        system_shell = QFrame()
        system_shell.setObjectName("topbar_system_shell")
        system_shell.setStyleSheet(
            "QFrame#topbar_system_shell { background-color: rgba(244,239,231,0.72);"
            " border: 1px solid rgba(214,197,174,0.62); border-radius: 20px; }"
        )
        system_row = QHBoxLayout(system_shell)
        system_row.setContentsMargins(10, 5, 8, 5)
        system_row.setSpacing(6)
        system_lbl = QLabel("UTILITY")
        system_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        system_row.addWidget(system_lbl)

        notif_wrap = QWidget()
        notif_wrap.setFixedSize(36, 36)
        notif_layout = QVBoxLayout(notif_wrap)
        notif_layout.setContentsMargins(0, 0, 0, 0)
        notif_layout.setSpacing(0)
        self._notif_btn = QPushButton("\U0001F514")
        self._notif_btn.setFixedSize(36, 36)
        self._notif_btn.setToolTip("Open launcher warnings and recovery events in Settings.")
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
        self._term_btn.setToolTip("Open logs and recent command activity in Settings.")
        self._term_btn.setStyleSheet(self._icon_button_style(T.BG0, T.TEXT))
        self._term_btn.clicked.connect(lambda: self.quick_action.emit("terminal"))

        system_row.addWidget(notif_wrap)
        system_row.addWidget(self._term_btn)
        row.addWidget(system_shell)

        self.set_active_tab(0)
        self.set_instances(["guppy-primary"], active_instance="guppy-primary")

    @staticmethod
    def _nav_style(active: bool) -> str:
        if active:
            return (
                f"QPushButton {{ background-color: {T.INK}; color: white; border: none; border-radius: 16px;"
                f" padding: 0 15px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 2px; }}"
            )
        return (
            f"QPushButton {{ background-color: rgba(244,239,231,0.0); color: {T.DIM}; border: none; border-radius: 16px;"
            f" padding: 0 15px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 2px; }}"
            f"QPushButton:hover {{ color: {T.INK}; background-color: rgba(70,98,199,0.08); }}"
        )

    @staticmethod
    def _icon_button_style(bg: str, color: str) -> str:
        return (
            f"QPushButton {{ background-color: {bg}; color: {color}; border: 1px solid rgba(214,197,174,0.72);"
            f" border-radius: 18px; font-size: 12pt; }}"
            f"QPushButton:hover {{ border-color: {T.TERTIARY}; color: {T.TERTIARY}; background-color: #ffffff; }}"
        )

    def _on_nav(self, tab_index: int) -> None:
        self.set_active_tab(tab_index)
        self.nav_requested.emit(tab_index)

    def set_active_tab(self, tab_index: int) -> None:
        for btn, (_, idx) in zip(self._nav_btns, self._NAV_TABS):
            btn.setStyleSheet(self._nav_style(idx == tab_index))

    def set_session(self, text: str) -> None:
        clean = (text or "daily workspace assistant").strip() or "daily workspace assistant"
        self._session_lbl.setText(clean.lower())

    def set_launcher_summary(self, text: str) -> None:
        summary = (text or "AUTO / GUPPY / LIGHT").strip() or "AUTO / GUPPY / LIGHT"
        summary = summary.replace("[EDIT]", "").replace("[OPEN]", "OPEN").strip()
        if not summary.startswith("HOME"):
            summary = f"HOME / {summary}"
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
