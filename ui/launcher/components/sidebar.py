"""
ui/launcher/components/sidebar.py
160-px left navigation panel with 6 tabs.  Emits tab_changed(int) on click.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .. import tokens as T

_NAV: list[tuple[str, str]] = [
    ("◎", "ASSISTANT"),
    ("⚒", "TOOLS"),
    ("⊞", "SETTINGS"),
    ("⌘", "ADVANCED"),
    ("⬡", "MODELS"),
    ("♫", "VOICES"),
]


class _NavItem(QWidget):
    clicked = Signal(int)

    def __init__(self, icon: str, label: str, index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._index = index
        self._active = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._btn = QPushButton(f"  {icon}  {label}")
        self._btn.setFlat(True)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._btn.clicked.connect(lambda: self.clicked.emit(self._index))
        self._apply_style(active=False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._btn)

    def _apply_style(self, active: bool) -> None:
        self._active = active
        if active:
            self._btn.setStyleSheet(
                f"color: {T.PRIMARY};"
                f"background-color: rgba(42,42,42,0.5);"
                f"border-left: 2px solid {T.PRIMARY};"
                f"border-right: none; border-top: none; border-bottom: none;"
                f"font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt;"
                f"letter-spacing: 1px; text-align: left; padding: 10px 0 10px 14px;"
            )
        else:
            self._btn.setStyleSheet(
                f"color: {T.DIM};"
                f"background-color: transparent;"
                f"border: none;"
                f"font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt;"
                f"letter-spacing: 1px; text-align: left; padding: 10px 0 10px 16px;"
            )

    def set_active(self, v: bool) -> None:
        self._apply_style(v)


class Sidebar(QFrame):
    tab_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(T.SIDEBAR_W)
        self.setObjectName("sidebar")
        self.setStyleSheet(
            f"QFrame#sidebar {{ background-color: {T.BG};"
            f" border-right: 1px solid {T.BORDER}; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 28, 0, 28)
        root.setSpacing(0)

        # ── Logo ──────────────────────────────────────────────────────────────
        logo = QLabel("GUPPY_AI")
        logo.setStyleSheet(
            f"color: {T.PRIMARY}; font-family: '{T.FF_HEAD}';"
            f"font-size: {T.FS_HERO}pt; font-weight: bold; letter-spacing: 3px;"
            f"padding-left: 16px;"
        )
        ver = QLabel("V 5.0")
        ver.setStyleSheet(
            f"color: {T.BORDER}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 2px; padding-left: 16px;"
        )

        root.addWidget(logo)
        root.addWidget(ver)
        root.addSpacing(24)

        # ── Nav items ─────────────────────────────────────────────────────────
        self._items: list[_NavItem] = []
        for i, (icon, label) in enumerate(_NAV):
            item = _NavItem(icon, label, i)
            item.clicked.connect(self._on_nav_click)
            self._items.append(item)
            root.addWidget(item)

        root.addStretch()

        # ── Bottom version dim ────────────────────────────────────────────────
        sys_lbl = QLabel("OBSIDIAN UI")
        sys_lbl.setStyleSheet(
            f"color: {T.BORDER}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px; padding-left: 16px;"
        )
        root.addWidget(sys_lbl)

        self._items[0].set_active(True)

    def _on_nav_click(self, index: int) -> None:
        for i, item in enumerate(self._items):
            item.set_active(i == index)
        self.tab_changed.emit(index)

    def set_active(self, index: int) -> None:
        """Update active highlight without re-emitting tab_changed."""
        for i, item in enumerate(self._items):
            item.set_active(i == index)
