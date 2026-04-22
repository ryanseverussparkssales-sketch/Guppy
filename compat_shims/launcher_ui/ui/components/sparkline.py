from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget


class Sparkline(QWidget):
    """Shared sparkline widget used by compatibility and launcher UI surfaces.

    Supports both APIs:
    - compatibility API: set_values([...])
    - launcher: push(v), set_data([...])
    """

    def __init__(self, color: str = "#f2ca50", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._values: list[float] = []
        self._color = QColor(color)
        self.setFixedHeight(36)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def set_values(self, values: list[float]) -> None:
        self.set_data(values)

    def set_data(self, values: list[float]) -> None:
        clipped = [max(0.0, min(1.0, float(v))) for v in (values or [])]
        self._values = clipped[-80:]
        self.update()

    def push(self, value: float) -> None:
        self._values.append(max(0.0, min(1.0, float(value))))
        if len(self._values) > 80:
            self._values = self._values[-80:]
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        if not self._values:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = self.height()
        w = self.width()
        n = len(self._values)
        bar_w = max(2, (w - n) // max(n, 1))
        x = 0

        for i, v in enumerate(self._values):
            bar_h = max(2, int(h * v))
            alpha = int(90 + 160 * (i / max(n - 1, 1)))
            c = QColor(self._color)
            c.setAlpha(alpha)
            p.setBrush(c)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(x, h - bar_h, bar_w, bar_h)
            x += bar_w + 1

        p.end()
