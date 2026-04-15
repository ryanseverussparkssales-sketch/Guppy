"""
ui/launcher/components/sidebar.py
Compact left navigation rail for the launcher.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
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
    ("\u2302", "HOME"),
    ("\U0001F310", "WORKSPACES"),
    ("\u2692", "TOOLS"),
    ("\u2699", "APP MGMT"),
    ("\u265E", "MODELS"),
    ("\u266B", "VOICES"),
]


def _paint_guppy_fish(painter: QPainter, bounds) -> None:
    grad = QLinearGradient(bounds.topLeft(), bounds.bottomRight())
    grad.setColorAt(0.0, QColor(T.ART_RED))
    grad.setColorAt(0.55, QColor(T.ART_GOLD))
    grad.setColorAt(1.0, QColor(T.ART_PLUM))
    painter.setBrush(grad)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(bounds)

    fish = QPainterPath()
    fish.moveTo(16, 28)
    fish.cubicTo(22, 15, 40, 15, 42, 28)
    fish.cubicTo(40, 39, 24, 42, 16, 31)
    fish.cubicTo(14, 30, 13, 29, 12, 28)
    fish.cubicTo(13, 27, 14, 26, 16, 25)
    fish.closeSubpath()

    tail = QPainterPath()
    tail.moveTo(12, 28)
    tail.lineTo(6, 22)
    tail.lineTo(8, 28)
    tail.lineTo(6, 34)
    tail.closeSubpath()

    fin = QPainterPath()
    fin.moveTo(26, 21)
    fin.lineTo(31, 15)
    fin.lineTo(33, 23)
    fin.closeSubpath()

    painter.setBrush(QColor("#fff8f1"))
    painter.drawPath(fish)
    painter.drawPath(tail)
    painter.setBrush(QColor("#ffd7df"))
    painter.drawPath(fin)

    eye_pen = QPen(QColor("#18120e"))
    eye_pen.setWidthF(1.6)
    painter.setPen(eye_pen)
    painter.setBrush(QColor("#ffffff"))
    painter.drawEllipse(29, 22, 12, 12)
    painter.setBrush(QColor("#18120e"))
    painter.drawEllipse(33, 26, 5, 5)

    painter.setPen(QPen(QColor(255, 248, 241, 180), 1.2))
    painter.drawArc(bounds.adjusted(5, 5, -5, -5), 40 * 16, 80 * 16)


def create_guppy_fish_icon(size: int = 64) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    _paint_guppy_fish(painter, pixmap.rect().adjusted(2, 2, -2, -2))
    painter.end()
    return QIcon(pixmap)


class _GuppyBadge(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(56, 56)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        _paint_guppy_fish(painter, self.rect().adjusted(2, 2, -2, -2))
        painter.end()


class _NavItem(QWidget):
    clicked = Signal(int)

    def __init__(self, icon: str, label: str, index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._index = index
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._btn = QPushButton(icon)
        self._btn.setFlat(True)
        self._btn.setFixedSize(58, 44)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._btn.setAccessibleName(label)
        self._btn.setAccessibleDescription(label)
        self._btn.clicked.connect(lambda: self.clicked.emit(self._index))

        self._label = QLabel(label)
        self._label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._label.setAccessibleName(label)
        self._label.setAccessibleDescription(label)
        self._label.setVisible(False)
        self._btn.setToolTip(label.title())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self._btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self._label)
        self._apply_style(active=False)

    def _apply_style(self, active: bool) -> None:
        if active:
            self._btn.setStyleSheet(
                f"QPushButton {{ background-color: {T.INK}; color: #ffffff; border: none; border-radius: 22px;"
                " font-family: 'Segoe UI Symbol';"
                f" font-size: {T.FS_LABEL + 1}pt; font-weight: bold; }}"
            )
            self._label.setStyleSheet(
                f"color: {T.INK}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px; font-weight: bold;"
            )
            return
        self._btn.setStyleSheet(
            f"QPushButton {{ background-color: rgba(255,250,243,0.76); color: {T.DIM}; border: 1px solid rgba(205,181,154,0.55);"
            " border-radius: 22px; font-family: 'Segoe UI Symbol';"
            f" font-size: {T.FS_LABEL + 1}pt; font-weight: bold; }}"
            f"QPushButton:hover {{ color: {T.PRIMARY}; border-color: {T.PRIMARY}; background-color: #ffffff; }}"
        )
        self._label.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
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
            "QFrame#sidebar { background-color: rgba(255,250,243,0.68); border-right: 1px solid rgba(205,181,154,0.45); }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 20, 0, 20)
        root.setSpacing(0)

        art_card = QFrame()
        art_card.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {T.ART_RED}, stop:0.5 {T.ART_GOLD}, stop:1 {T.ART_PLUM});"
            "border-radius: 18px; margin: 0 14px;"
        )
        art_layout = QVBoxLayout(art_card)
        art_layout.setContentsMargins(10, 10, 10, 10)
        art_layout.setSpacing(4)
        art_layout.addWidget(_GuppyBadge(), alignment=Qt.AlignmentFlag.AlignHCenter)
        deck = QLabel("guppy")
        deck.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        deck.setStyleSheet(
            f"color: rgba(255,255,255,0.88); font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 2px;"
        )
        art_layout.addWidget(deck)
        root.addWidget(art_card)
        root.addSpacing(16)

        self._items: list[_NavItem] = []
        for i, (icon, label) in enumerate(_NAV):
            item = _NavItem(icon, label, i)
            item.clicked.connect(self._on_nav_click)
            self._items.append(item)
            root.addWidget(item, alignment=Qt.AlignmentFlag.AlignHCenter)
            root.addSpacing(10)

        root.addStretch()

        sys_lbl = QLabel("ART")
        sys_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        sys_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 3px;"
        )
        root.addWidget(sys_lbl)

        self._items[0].set_active(True)

    def _on_nav_click(self, index: int) -> None:
        for i, item in enumerate(self._items):
            item.set_active(i == index)
        self.tab_changed.emit(index)

    def set_active(self, index: int) -> None:
        for i, item in enumerate(self._items):
            item.set_active(i == index)
