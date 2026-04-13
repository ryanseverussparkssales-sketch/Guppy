"""
ui/launcher/components/toggle_row.py
A horizontal row: [label (left)] [ToggleSwitch (right)].
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from .. import tokens as T


class ToggleSwitch(QWidget):
    toggled = Signal(bool)

    def __init__(self, checked: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._checked = checked
        self.setFixedSize(36, 20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    @property
    def is_checked(self) -> bool:
        return self._checked

    def setChecked(self, v: bool) -> None:  # noqa: N802
        self._checked = bool(v)
        self.update()

    def mousePressEvent(self, _event) -> None:  # noqa: N802
        self._checked = not self._checked
        self.toggled.emit(self._checked)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        track = QColor(T.PRIMARY if self._checked else T.BG3)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(QRect(0, 4, 36, 12), 6, 6)

        thumb_x = 20 if self._checked else 2
        thumb_color = QColor(T.BG if self._checked else T.DIM)
        p.setBrush(thumb_color)
        p.drawEllipse(QPoint(thumb_x + 8, 10), 7, 7)
        p.end()


class ToggleRow(QWidget):
    """Horizontal row with a label and a toggle or checkbox on the right."""

    toggled = Signal(bool)

    def __init__(
        self,
        label: str,
        checked: bool = False,
        dim_label: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color: {T.DIM if dim_label else T.TEXT};"
            f"font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; letter-spacing: 1px;"
        )

        self._toggle = ToggleSwitch(checked=checked)
        self._toggle.toggled.connect(self.toggled)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 4, 0, 4)
        row.setSpacing(0)
        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(self._toggle)

    @property
    def is_checked(self) -> bool:
        return self._toggle.is_checked

    def setChecked(self, v: bool) -> None:  # noqa: N802
        self._toggle.setChecked(v)
