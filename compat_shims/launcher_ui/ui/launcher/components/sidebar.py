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
    ("*", "HOME", 0, frozenset({0}), True),
    ("R", "MODELS", 5, frozenset({5, 6, 7, 8, 9}), True),
    ("W", "TOOLS", 3, frozenset({3}), True),
    ("L", "LIBRARY", 2, frozenset({2}), True),
    ("B", "SETTINGS", 4, frozenset({4}), True),
    ("S", "SPACES", 1, frozenset({1}), False),
    ("P", "MY PC", 5, frozenset({5}), False),
    ("M", "LOCAL LLM", 6, frozenset({6}), False),
    ("T", "RUNTIME", 8, frozenset({8}), False),
    ("V", "VOICE", 9, frozenset({9}), False),
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
        self._active = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._icon = icon
        self._label_text = label
        self._label = QLabel(label, self)
        self._label.hide()
        self._btn = QPushButton(f"{icon}  {label}")
        self._btn.setFlat(True)
        self._btn.setFixedSize(T.SIDEBAR_W_EXPANDED - 22, 44)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._btn.setAccessibleName(label)
        self._btn.setAccessibleDescription(label)
        self._btn.clicked.connect(lambda: self.clicked.emit(self._route_index))
        self._btn.setToolTip(label.title())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._btn)
        self._apply_style(active=False)
        self.set_compact(False)

    def _apply_style(self, active: bool) -> None:
        if active:
            self._btn.setStyleSheet(
                f"QPushButton {{ background-color: rgba(0,0,0,0.03); color: {T.ACCENT_TEAL_TEXT};"
                " border: none;"
                f" border-left: 4px solid {T.ACCENT_TEAL_TEXT};"
                " border-top-left-radius: 0px; border-bottom-left-radius: 0px;"
                " border-top-right-radius: 0px; border-bottom-right-radius: 0px;"
                f" padding: 0 16px; margin-left: 8px; text-align: left; font-family: '{T.FF_BODY}';"
                f" font-size: {T.FS_SMALL + 1}pt; font-weight: 600; }}"
            )
            return
        self._btn.setStyleSheet(
            f"QPushButton {{ background-color: transparent; color: {T.DIM}; border: none;"
            " border-left: 4px solid transparent;"
            " border-radius: 0px; margin-left: 8px;"
            f" padding: 0 16px; text-align: left; font-family: '{T.FF_BODY}';"
            f" font-size: {T.FS_SMALL + 1}pt; font-weight: 500; }}"
            f"QPushButton:hover {{ color: {T.TEXT}; background-color: rgba(0,0,0,0.03); border-left-color: {T.ACCENT_TEAL}; }}"
        )

    def set_active(self, v: bool) -> None:
        self._active = bool(v)
        self._apply_style(self._active)

    def matches_route(self, route_index: int) -> bool:
        return route_index in self._active_routes

    def set_compact(self, compact: bool) -> None:
        if compact:
            self._btn.setText(self._icon)
            self._btn.setFixedSize(44, 40)
            self._btn.setStyleSheet(
                f"QPushButton {{ background-color: transparent; color: {T.DIM}; border: none; border-radius: 4px;"
                f" font-family: '{T.FF_BODY}'; font-size: {T.FS_LABEL}pt; font-weight: 600; }}"
                f"QPushButton:hover {{ color: {T.ACCENT_TEAL}; background-color: rgba(0,0,0,0.05); }}"
            )
        else:
            self._btn.setText(f"{self._icon}  {self._label_text}")
            self._btn.setFixedSize(300 - 22, 44)  # Updated to match new sidebar width
            self._apply_style(self._active)


class Sidebar(QFrame):
    tab_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._collapsed = False
        self.setFixedWidth(300)  # Atoll Editorial: persistent 300px sidebar
        self.setObjectName("sidebar")
        self.setStyleSheet(
            f"QFrame#sidebar {{ background-color: {T.SURFACE_BASE}; border-right: none; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 18, 0, 16)
        root.setSpacing(2)

        self._art_card = QFrame()
        self._art_card.setStyleSheet(
            f"background: {T.SURFACE_BASE};"
            "border-radius: 12px; margin: 0 14px;"
        )
        art_layout = QVBoxLayout(self._art_card)
        art_layout.setContentsMargins(8, 8, 8, 8)
        art_layout.setSpacing(3)
        art_layout.addWidget(_GuppyBadge(), alignment=Qt.AlignmentFlag.AlignHCenter)
        self._deck = QLabel("The Curator")
        self._deck.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._deck.setStyleSheet(
            f"color: {T.TEXT}; background-color: {T.SURFACE_ELEVATED_92};"
            " border-radius: 10px;"
            f" padding: 4px 8px; font-family: '{T.FF_BODY}';"
            f" font-size: {T.FS_SMALL + 1}pt; font-weight: 700;"
        )
        art_layout.addWidget(self._deck)
        self._deck_sub = QLabel("TECHNICAL INTELLIGENCE")
        self._deck_sub.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._deck_sub.setStyleSheet(
            f"color: {T.TEXT_DIM_72}; font-family: '{T.FF_MONO}';"
            f" font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        art_layout.addWidget(self._deck_sub)
        root.addWidget(self._art_card)

        self._compact_badge = _GuppyBadge()
        self._compact_badge.hide()
        root.addWidget(self._compact_badge, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._g_mark = QLabel("")
        self._g_mark.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._g_mark.setStyleSheet(
            f"color: {T.ACCENT_TEAL_TEXT}; font-family: '{T.FONT_SERIF}', '{T.FF_HEAD}', serif;"
            " font-size: 12pt; font-weight: bold; padding: 0 0 0 0;"
        )
        root.addWidget(self._g_mark)

        # Sunset gradient accent bar (2px) beneath the G mark
        self._brand_bar = QFrame()
        self._brand_bar.setFixedHeight(1)
        self._brand_bar.setStyleSheet(
            f"background: {T.GRADIENT_SUNSET}; margin: 0 16px;"
        )
        root.addWidget(self._brand_bar)
        root.addSpacing(12)

        self._primary_lbl = QLabel("")
        self._primary_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._primary_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 3px;"
        )
        root.addWidget(self._primary_lbl)
        root.addSpacing(6)

        self._collapse_btn = QPushButton("<")
        self._collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._collapse_btn.setStyleSheet(
            f"QPushButton {{ background-color: transparent; color: {T.DIM}; border: 1px solid {T.BORDER_SOFT_64};"
            f" border-radius: 10px; padding: 4px 8px; font-family: '{T.FF_BODY}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ color: {T.PRIMARY}; border-color: {T.PRIMARY}; background-color: {T.WHITE}; }}"
        )
        self._collapse_btn.clicked.connect(self.toggle_collapsed)
        root.addWidget(self._collapse_btn, alignment=Qt.AlignmentFlag.AlignRight)
        root.addSpacing(8)

        self._items: list[_NavItem] = []
        self._visible_items: list[_NavItem] = []
        for icon, label, route_index, active_routes, visible in _NAV:
            item = _NavItem(icon, label, route_index, active_routes, self)
            item.clicked.connect(self._on_nav_click)
            self._items.append(item)
            if visible:
                self._visible_items.append(item)
                root.addWidget(item, alignment=Qt.AlignmentFlag.AlignLeft)
                root.addSpacing(2)
            else:
                item.hide()

        root.addSpacing(10)

        root.addStretch()

        self._sys_lbl = QLabel("HELP CENTER")
        self._sys_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._sys_lbl.setStyleSheet(
            f"color: {T.TEXT_DIM_72}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;"
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
        self._art_card.setVisible(not self._collapsed)
        self._compact_badge.setVisible(self._collapsed)
        self._deck.setVisible(not self._collapsed)
        self._deck_sub.setVisible(not self._collapsed)
        self._g_mark.setVisible(not self._collapsed)
        self._brand_bar.setVisible(not self._collapsed)
        self._primary_lbl.setVisible(not self._collapsed)
        self._sys_lbl.setVisible(not self._collapsed)
        self._collapse_btn.setText(">" if self._collapsed else "<")
        self._collapse_btn.setToolTip("Expand navigation" if self._collapsed else "Collapse navigation")
        for item in self._visible_items:
            item.set_compact(self._collapsed)

    def is_collapsed(self) -> bool:
        return self._collapsed
