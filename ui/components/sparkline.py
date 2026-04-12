from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget
from guppy_theme import SHARED


class Sparkline(QWidget):
    def __init__(self, color: str = "#7cc4ff", parent=None):
        super().__init__(parent)
        self._values = []
        self._line_color = QColor(color)
        self.setMinimumHeight(max(20, SHARED.control_height_sm - 6))

    def set_values(self, values):
        vals = [float(v) for v in (values or []) if isinstance(v, (int, float))]
        self._values = vals[-80:]
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), Qt.GlobalColor.transparent)

        if len(self._values) < 2:
            p.setPen(QPen(QColor("#666666"), 1))
            p.drawLine(2, self.height() - 2, self.width() - 2, self.height() - 2)
            return

        lo = min(self._values)
        hi = max(self._values)
        span = max(1e-6, hi - lo)
        w = max(1, self.width() - 4)
        h = max(1, self.height() - 4)

        p.setPen(QPen(self._line_color, 1.5))
        for i in range(1, len(self._values)):
            x0 = 2 + int((i - 1) * w / (len(self._values) - 1))
            x1 = 2 + int(i * w / (len(self._values) - 1))
            y0 = 2 + int((1.0 - ((self._values[i - 1] - lo) / span)) * h)
            y1 = 2 + int((1.0 - ((self._values[i] - lo) / span)) * h)
            p.drawLine(x0, y0, x1, y1)
