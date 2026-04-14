"""
ui/launcher/components/topbar.py
52-px top navigation / header bar.
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
    QWidget,
)

from .. import tokens as T


class TopBar(QFrame):
    search_submitted = Signal(str)
    quick_action = Signal(str)
    instance_selected = Signal(str)
    # Emits sidebar tab index for the unified launcher stack.
    nav_requested = Signal(int)

    # Tab index map for nav buttons
    _NAV_TABS = [
        ("HOME", 0),
        ("INSTANCES", 1),
        ("APP MGMT",  3),
        ("SETTINGS",  4),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(T.TOPBAR_H)
        self.setObjectName("topbar")
        self.setStyleSheet(
            f"QFrame#topbar {{"
            f"  background-color: rgba(19,19,19,0.92);"
            f"  border-bottom: 1px solid {T.BORDER};"
            f"}}"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(20, 0, 16, 0)
        row.setSpacing(12)

        # ── Left: title ───────────────────────────────────────────────────────
        title = QLabel("COMMAND_INTERFACE")
        title.setStyleSheet(
            f"color: {T.PRIMARY}; font-family: '{T.FF_HEAD}';"
            f"font-size: {T.FS_TITLE}pt; font-weight: 900; letter-spacing: 3px;"
        )

        session_sep = QLabel("//")
        session_sep.setStyleSheet(f"color: {T.BORDER}; font-size: {T.FS_LABEL}pt;")

        self._session_lbl = QLabel("SESSION: ACTIVE")
        self._session_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_SMALL}pt; letter-spacing: 2px;"
        )

        row.addWidget(title)
        row.addWidget(session_sep)
        row.addWidget(self._session_lbl)
        row.addSpacing(24)

        # ── Centre: nav buttons ───────────────────────────────────────────────
        _nav_btn_style = (
            f"QPushButton {{"
            f"  color: {T.DIM}; border: none; background: transparent;"
            f"  font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
            f"  letter-spacing: 2px; padding: 0 10px;"
            f"}}"
            f"QPushButton:hover {{ color: {T.TEXT}; }}"
            f"QPushButton[active='true'] {{"
            f"  color: {T.PRIMARY}; border-bottom: 1px solid {T.PRIMARY};"
            f"}}"
        )
        self._nav_btns: list[QPushButton] = []
        for label, idx in self._NAV_TABS:
            btn = QPushButton(label)
            btn.setFixedHeight(T.TOPBAR_H)
            btn.setStyleSheet(_nav_btn_style)
            btn.clicked.connect(lambda _=False, i=idx: self._on_nav(i))
            row.addWidget(btn)
            self._nav_btns.append(btn)

        row.addStretch()

        # ── Instance quick switcher ──────────────────────────────────────────
        inst_lbl = QLabel("INSTANCE")
        inst_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        self._instance_cb = QComboBox()
        self._instance_cb.setFixedWidth(180)
        self._instance_cb.setStyleSheet(
            f"QComboBox {{"
            f"  background-color: {T.BG0}; color: {T.TEXT};"
            f"  border: 1px solid {T.BORDER}; padding: 2px 8px;"
            f"  font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt;"
            f"}}"
            f"QComboBox:focus {{ border-color: {T.PRIMARY}; }}"
        )
        self._instance_cb.currentTextChanged.connect(self._on_instance_selected)
        row.addWidget(inst_lbl)
        row.addWidget(self._instance_cb)
        row.addSpacing(8)

        # ── Right: search ─────────────────────────────────────────────────────
        self._search = QLineEdit()
        self._search.setPlaceholderText("SEARCH_SYSTEM...")
        self._search.setFixedWidth(220)
        self._search.setStyleSheet(
            f"QLineEdit {{ background-color: {T.BG0};"
            f"  border: 1px solid {T.BORDER}; padding: 3px 8px;"
            f"  font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt;"
            f"  color: {T.TEXT}; }}"
            f"QLineEdit:focus {{ border-color: {T.PRIMARY}; }}"
        )
        self._search.returnPressed.connect(
            lambda: self.search_submitted.emit(self._search.text())
        )

        # notification + terminal buttons
        notif_btn = QPushButton("🔔")
        notif_btn.setFixedSize(32, 32)
        notif_btn.setEnabled(False)
        notif_btn.setToolTip("Notification inbox is not implemented in launcher yet.")
        notif_btn.setStyleSheet(
            f"QPushButton {{ border: none; color: {T.DIM}; font-size: 13pt; }}"
            f"QPushButton:hover {{ color: {T.PRIMARY}; }}"
        )
        notif_btn.clicked.connect(lambda: self.quick_action.emit("notifications"))

        term_btn = QPushButton("⌨")
        term_btn.setFixedSize(32, 32)
        term_btn.setEnabled(False)
        term_btn.setToolTip("Embedded terminal panel is not implemented in launcher yet.")
        term_btn.setStyleSheet(
            f"QPushButton {{ border: none; color: {T.DIM}; font-size: 13pt; }}"
            f"QPushButton:hover {{ color: {T.PRIMARY}; }}"
        )
        term_btn.clicked.connect(lambda: self.quick_action.emit("terminal"))

        row.addWidget(self._search)
        row.addWidget(notif_btn)
        row.addWidget(term_btn)

        # Start with HOME active
        self.set_active_tab(0)
        self.set_instances(["guppy-primary"], active_instance="guppy-primary")

    def _on_nav(self, tab_index: int) -> None:
        self.set_active_tab(tab_index)
        self.nav_requested.emit(tab_index)

    def set_active_tab(self, tab_index: int) -> None:
        """Highlight the nav button matching tab_index."""
        for btn, (_, idx) in zip(self._nav_btns, self._NAV_TABS):
            active = (idx == tab_index)
            btn.setProperty("active", "true" if active else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def set_session(self, text: str) -> None:
        self._session_lbl.setText(f"SESSION: {text.upper()}")

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
