"""
ui/launcher/components/sidebar.py
Compact left navigation rail for the launcher.
"""
from __future__ import annotations

from pathlib import Path

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

_NAV: list[tuple[str, str, int, frozenset[int], bool]] = [
    ("\u2302", "HOME", 0, frozenset({0}), True),
    ("\u265E", "MODELS", 5, frozenset({5, 6, 7, 8, 9}), True),
    ("\u2692", "TOOLS", 3, frozenset({3}), True),
    ("\U0001F4DA", "LIBRARY", 2, frozenset({2}), True),
    ("\u2699", "SETTINGS", 4, frozenset({4}), True),
    ("\U0001F310", "SPACES", 1, frozenset({1}), False),
    ("\U0001F5A5", "MY PC", 5, frozenset({5}), False),
    ("\u269b", "LOCAL LLM", 6, frozenset({6}), False),
    ("\u21BB", "RUNTIME", 8, frozenset({8}), False),
    ("\u266B", "VOICE", 9, frozenset({9}), False),
]
_ROOT = Path(__file__).resolve().parents[3]
_DESKTOP_G_LOGO = _ROOT / "assets" / "desktop" / "guppy_launcher_icon.png"


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
    if _DESKTOP_G_LOGO.exists():
        icon = QIcon(str(_DESKTOP_G_LOGO))
        if not icon.isNull():
            return icon

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
        self.setFixedSize(48, 48)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 253, 248, 232))
        painter.drawEllipse(self.rect().adjusted(1, 1, -1, -1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 160), 1.2))
        painter.drawEllipse(self.rect().adjusted(1, 1, -1, -1))
        _paint_guppy_fish(painter, self.rect().adjusted(6, 6, -6, -6))
        painter.end()


class _NavItem(QWidget):
    clicked = Signal(int)

    def __init__(
        self,
        icon: str,
        label: str,
        route_index: int,
        active_routes: frozenset[int],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._route_index = route_index
        self._active_routes = active_routes
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._btn = QPushButton(icon)
        self._btn.setFlat(True)
        self._btn.setFixedSize(58, 44)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._btn.setAccessibleName(label)
        self._btn.setAccessibleDescription(label)
        self._btn.clicked.connect(lambda: self.clicked.emit(self._route_index))

        self._label = QLabel(label)
        self._label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._label.setAccessibleName(label)
        self._label.setAccessibleDescription(label)
        self._label.setVisible(True)
        self._btn.setToolTip(label.title())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self._btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self._label)
        self._apply_style(active=False)
        self.set_compact(False)

    def _apply_style(self, active: bool) -> None:
        if active:
            # Glass warm-sand active state: SAND_1 background + teal left accent border
            self._btn.setStyleSheet(
                f"QPushButton {{ background-color: {T.SAND_1}; color: {T.ACCENT_TEAL};"
                f" border: none; border-radius: 22px;"
                f" border-left: 3px solid {T.ACCENT_TEAL};"
                " font-family: 'Segoe UI Symbol';"
                f" font-size: {T.FS_LABEL + 1}pt; font-weight: bold; }}"
            )
            self._label.setStyleSheet(
                f"color: {T.ACCENT_TEAL}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px; font-weight: bold;"
            )
            return
        self._btn.setStyleSheet(
            f"QPushButton {{ background-color: rgba(255,255,255,0.88); color: {T.DIM}; border: 1px solid rgba(214,197,174,0.64);"
            " border-radius: 22px; font-family: 'Segoe UI Symbol';"
            f" font-size: {T.FS_LABEL + 1}pt; font-weight: bold; }}"
            f"QPushButton:hover {{ color: {T.TERTIARY}; border-color: {T.TERTIARY}; background-color: #ffffff; }}"
        )
        self._label.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )

    def set_active(self, v: bool) -> None:
        self._apply_style(v)

    def matches_route(self, route_index: int) -> bool:
        return route_index in self._active_routes

    def set_compact(self, compact: bool) -> None:
        self._label.setVisible(not compact)
        self._btn.setFixedSize(44 if compact else 58, 40 if compact else 44)
        self.layout().setSpacing(0 if compact else 2)


class Sidebar(QFrame):
    tab_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._collapsed = False
        self.setFixedWidth(T.SIDEBAR_W)
        self.setObjectName("sidebar")
        self.setStyleSheet(
            "QFrame#sidebar { background-color: rgba(255,253,248,0.86); border-right: 1px solid rgba(214,197,174,0.60); }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 12, 0, 12)
        root.setSpacing(0)

        self._art_card = QFrame()
        self._art_card.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {T.ART_RED}, stop:0.55 {T.ART_GOLD}, stop:1 {T.ART_PLUM});"
            "border-radius: 20px; margin: 0 12px;"
        )
        art_layout = QVBoxLayout(self._art_card)
        art_layout.setContentsMargins(8, 8, 8, 8)
        art_layout.setSpacing(3)
        art_layout.addWidget(_GuppyBadge(), alignment=Qt.AlignmentFlag.AlignHCenter)
        self._deck = QLabel("GUPPY")
        self._deck.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._deck.setStyleSheet(
            f"color: rgba(255,255,255,0.88); font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 2px;"
        )
        art_layout.addWidget(self._deck)
        root.addWidget(self._art_card)

        # Refined "Guppy G" logo mark: bold teal serif letter beneath art card
        self._g_mark = QLabel("G")
        self._g_mark.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._g_mark.setStyleSheet(
            f"color: {T.ACCENT_TEAL}; font-family: '{T.FONT_SERIF}', '{T.FF_HEAD}', serif;"
            " font-size: 28pt; font-weight: bold; padding: 4px 0 0 0;"
        )
        root.addWidget(self._g_mark)

        # Sunset gradient accent bar (2px) beneath the G mark
        self._brand_bar = QFrame()
        self._brand_bar.setFixedHeight(2)
        self._brand_bar.setStyleSheet(
            f"background: {T.GRADIENT_SUNSET}; margin: 0 16px;"
        )
        root.addWidget(self._brand_bar)
        root.addSpacing(10)

        self._primary_lbl = QLabel("DAILY PATH")
        self._primary_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._primary_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 3px;"
        )
        root.addWidget(self._primary_lbl)
        root.addSpacing(10)

        self._collapse_btn = QPushButton("COLLAPSE")
        self._collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._collapse_btn.setStyleSheet(
            f"QPushButton {{ background-color: rgba(255,255,255,0.88); color: {T.DIM}; border: 1px solid rgba(214,197,174,0.64);"
            f" border-radius: 12px; padding: 5px 9px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px; }}"
            f"QPushButton:hover {{ color: {T.TERTIARY}; border-color: {T.TERTIARY}; background-color: #ffffff; }}"
        )
        self._collapse_btn.clicked.connect(self.toggle_collapsed)
        root.addWidget(self._collapse_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        root.addSpacing(10)

        self._items: list[_NavItem] = []
        self._visible_items: list[_NavItem] = []
        for icon, label, route_index, active_routes, visible in _NAV:
            item = _NavItem(icon, label, route_index, active_routes, self)
            item.clicked.connect(self._on_nav_click)
            self._items.append(item)
            if visible:
                self._visible_items.append(item)
                root.addWidget(item, alignment=Qt.AlignmentFlag.AlignHCenter)
                root.addSpacing(10)
            else:
                item.hide()

        root.addSpacing(6)

        root.addStretch()

        self._sys_lbl = QLabel("SYSTEM")
        self._sys_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._sys_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 3px;"
        )
        root.addWidget(self._sys_lbl)

        self._items[0].set_active(True)

    def _on_nav_click(self, index: int) -> None:
        for item in self._items:
            item.set_active(item.matches_route(index))
        self.tab_changed.emit(index)

    def set_active(self, index: int) -> None:
        for item in self._items:
            item.set_active(item.matches_route(index))

    def toggle_collapsed(self) -> None:
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = bool(collapsed)
        self.setFixedWidth(T.SIDEBAR_W_COLLAPSED if self._collapsed else T.SIDEBAR_W_EXPANDED)
        self._deck.setVisible(not self._collapsed)
        self._g_mark.setVisible(not self._collapsed)
        self._brand_bar.setVisible(not self._collapsed)
        self._primary_lbl.setVisible(not self._collapsed)
        self._sys_lbl.setVisible(not self._collapsed)
        self._collapse_btn.setText(">" if self._collapsed else "COLLAPSE")
        self._collapse_btn.setToolTip("Expand navigation" if self._collapsed else "Collapse navigation")
        for item in self._visible_items:
            item.set_compact(self._collapsed)

    def is_collapsed(self) -> bool:
        return self._collapsed
