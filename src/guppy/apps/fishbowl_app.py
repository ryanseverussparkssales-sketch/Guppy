"""fishbowl_app.py — Always-on-top Guppy quick-chat companion.

A floating fishbowl with an animated guppy fish. Click the bowl or press
Ctrl+Space to summon the chat panel. Esc or click-away to dismiss.

Run standalone:
    python src/guppy/apps/fishbowl_app.py
Or via CLI:
    python src/guppy/cli/launch.py fishbowl
"""
from __future__ import annotations

import json
import math
import random
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from PySide6.QtCore import (
    Qt, QPoint, QPointF, QRectF, QTimer, Signal, QThread,
)
from PySide6.QtGui import (
    QColor, QLinearGradient, QPainter, QPainterPath, QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QSizePolicy, QTextEdit,
    QVBoxLayout, QWidget,
)

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_API_BASE = "http://127.0.0.1:8081"
_BOWL_W, _BOWL_H = 130, 148
_PANEL_W = 300
_SUMMON_FLAG: threading.Event = threading.Event()


# ── State constants ────────────────────────────────────────────────────────────

class _S:
    IDLE       = "idle"
    LISTENING  = "listening"
    THINKING   = "thinking"
    RESPONDING = "responding"


# ── Fish drawing ───────────────────────────────────────────────────────────────

def _draw_fish(
    painter: QPainter,
    cx: float, cy: float,
    scale: float,
    direction_deg: float,
    eye_open: bool = True,
) -> None:
    """Draw a guppy fish centred at (cx, cy), facing direction_deg."""
    painter.save()
    painter.translate(cx, cy)
    painter.rotate(direction_deg)
    painter.scale(scale, scale)

    body = QPainterPath()
    body.moveTo(-10, 0)
    body.cubicTo(-10, -6, 5, -7, 8, -2)
    body.cubicTo(10, -1, 10, 1, 8, 2)
    body.cubicTo(5, 7, -10, 6, -10, 0)

    tail = QPainterPath()
    tail.moveTo(-10, -1.5)
    tail.lineTo(-20, -8)
    tail.lineTo(-16, 0)
    tail.lineTo(-20, 8)
    tail.lineTo(-10, 1.5)
    tail.closeSubpath()

    fin = QPainterPath()
    fin.moveTo(-2, -7)
    fin.lineTo(1, -12)
    fin.lineTo(5, -7)
    fin.closeSubpath()

    grad = QLinearGradient(-10, 0, 9, 0)
    grad.setColorAt(0.0, QColor("#c0392b"))
    grad.setColorAt(0.5, QColor("#e2b659"))
    grad.setColorAt(1.0, QColor("#8e44ad"))

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(grad)
    painter.drawPath(body)
    painter.drawPath(tail)

    painter.setBrush(QColor(255, 200, 220, 200))
    painter.drawPath(fin)

    if eye_open:
        painter.setBrush(QColor("white"))
        painter.drawEllipse(QPointF(5.5, -2), 2.5, 2.5)
        painter.setBrush(QColor("#18120e"))
        painter.drawEllipse(QPointF(6.2, -1.8), 1.5, 1.5)
        painter.setBrush(QColor("white"))
        painter.drawEllipse(QPointF(6.7, -2.3), 0.6, 0.6)

    painter.restore()


# ── Bowl widget ────────────────────────────────────────────────────────────────

class BowlWidget(QWidget):
    clicked = Signal()

    _ORBIT_RX = 26
    _ORBIT_RY = 13
    _CX, _CY = 65, 68
    _R = 54

    _SPEEDS = {
        _S.IDLE:       0.022,
        _S.LISTENING:  0.007,
        _S.THINKING:   0.09,
        _S.RESPONDING: 0.018,
    }

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(_BOWL_W, _BOWL_H)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._state = _S.IDLE
        self._angle = 0.0
        self._wave = 0.0
        self._blink = 0
        self._eye_open = True
        self._bubbles: list[list[float]] = [self._spawn_bubble(anywhere=True) for _ in range(5)]

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def set_state(self, state: str) -> None:
        self._state = state

    def _spawn_bubble(self, anywhere: bool = False) -> list[float]:
        x_off = random.uniform(-22, 22)
        y     = random.uniform(40, 108) if anywhere else random.uniform(100, 115)
        size  = random.uniform(2.5, 5.0)
        alpha = float(random.randint(90, 170))
        speed = random.uniform(0.35, 0.85)
        return [x_off, y, size, alpha, speed]

    def _tick(self) -> None:
        self._angle = (self._angle + self._SPEEDS.get(self._state, 0.022)) % (2 * math.pi)
        self._wave  = (self._wave + 0.05) % (2 * math.pi)

        for b in self._bubbles:
            b[1] -= b[4]
        self._bubbles = [
            self._spawn_bubble() if b[1] < (self._CY - self._R + 18) else b
            for b in self._bubbles
        ]
        if random.random() < 0.006 and len(self._bubbles) < 9:
            self._bubbles.append(self._spawn_bubble())

        self._blink += 1
        if self._blink == 180:
            self._eye_open = False
        elif self._blink >= 185:
            self._eye_open = True
            self._blink = random.randint(0, 30)

        self.update()

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy, r = self._CX, self._CY, self._R
        bowl = QRectF(cx - r, cy - r, r * 2, r * 2)

        # ── water fill (clipped to bowl) ───────────────────────────────────
        clip = QPainterPath()
        clip.addEllipse(bowl.adjusted(2, 2, -2, -2))
        p.setClipPath(clip)

        water = QLinearGradient(cx, cy - r * 0.35, cx, cy + r)
        water.setColorAt(0.0, QColor(28, 110, 155, 195))
        water.setColorAt(1.0, QColor(8,  50,  90,  220))
        p.setBrush(water)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(QRectF(cx - r, cy - r * 0.35, r * 2, r * 1.4))

        # air gap above water
        p.setBrush(QColor(190, 225, 245, 18))
        p.drawRect(QRectF(cx - r, cy - r, r * 2, r * 0.65))

        # animated water-surface wave
        wave_path = QPainterPath()
        water_y = cy - r * 0.32
        wave_path.moveTo(cx - r, water_y)
        steps = 20
        for i in range(steps + 1):
            fx = (cx - r) + (r * 2 * i / steps)
            fy = water_y + math.sin(self._wave + i * 0.6) * 1.8
            wave_path.lineTo(fx, fy)
        wave_path.lineTo(cx + r, cy + r)
        wave_path.lineTo(cx - r, cy + r)
        wave_path.closeSubpath()
        p.setBrush(QColor(28, 110, 155, 195))
        p.drawPath(wave_path)

        # pebbles
        pebbles = [
            (cx - 22, cy + 43, 5.5, 3.0, "#8B7355"),
            (cx - 6,  cy + 49, 4.0, 2.5, "#9B8B72"),
            (cx + 10, cy + 46, 6.0, 3.5, "#7A6248"),
            (cx + 27, cy + 42, 4.5, 2.8, "#A0856C"),
            (cx - 35, cy + 44, 3.5, 2.2, "#6B5B45"),
            (cx + 3,  cy + 43, 7.0, 4.0, "#8D7B62"),
        ]
        for px, py, pw, ph, col in pebbles:
            p.setBrush(QColor(col))
            p.drawEllipse(QPointF(px, py), pw, ph)

        # ── fish ───────────────────────────────────────────────────────────
        fx = cx + self._ORBIT_RX * math.cos(self._angle)
        fy = cy + self._ORBIT_RY * math.sin(self._angle)
        ddx = -self._ORBIT_RX * math.sin(self._angle)
        ddy =  self._ORBIT_RY * math.cos(self._angle)
        fish_dir = math.degrees(math.atan2(ddy, ddx))
        _draw_fish(p, fx, fy, 1.25, fish_dir, self._eye_open)

        # ── bubbles ────────────────────────────────────────────────────────
        for bx_off, by, bs, ba, _ in self._bubbles:
            p.setBrush(QColor(255, 255, 255, int(ba)))
            p.setPen(QPen(QColor(200, 235, 255, int(ba) // 2), 0.5))
            p.drawEllipse(QPointF(cx + bx_off, by), bs, bs)

        p.setClipping(False)

        # ── bowl glass edge ────────────────────────────────────────────────
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(90, 165, 210, 210), 3.5))
        p.drawEllipse(bowl)
        p.setPen(QPen(QColor(180, 225, 255, 55), 1.2))
        p.drawEllipse(bowl.adjusted(3, 3, -3, -3))

        # ── glass highlights ───────────────────────────────────────────────
        p.setPen(QPen(QColor(255, 255, 255, 130), 3,
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(QRectF(cx - r + 9, cy - r + 9, r * 0.65, r * 0.65), 30 * 16, 85 * 16)
        p.setPen(QPen(QColor(255, 255, 255, 55), 1.5))
        p.drawArc(QRectF(cx - r + 22, cy - r + 6,  r * 0.35, r * 0.28), 55 * 16, 60 * 16)

        # ── bowl opening rim ───────────────────────────────────────────────
        rim = QRectF(cx - r * 0.48, cy - r - 7, r * 0.96, 14)
        p.setPen(QPen(QColor(90, 165, 210, 160), 2))
        p.setBrush(QColor(160, 210, 240, 22))
        p.drawEllipse(rim)

        # ── bottom shadow ──────────────────────────────────────────────────
        shadow_grad = QRadialGradient(cx, _BOWL_H - 4, r * 0.5)
        shadow_grad.setColorAt(0.0, QColor(0, 0, 0, 55))
        shadow_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(shadow_grad)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - r * 0.55, _BOWL_H - 10, r * 1.1, 12))

        p.end()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


# ── API worker ─────────────────────────────────────────────────────────────────

class _ApiWorker(QThread):
    response_ready = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, message: str, token: str) -> None:
        super().__init__()
        self._message = message
        self._token = token

    def run(self) -> None:
        try:
            payload = json.dumps({
                "message": self._message,
                "history": [],
                "mode": "auto",
            }).encode()
            req = urllib.request.Request(
                f"{_API_BASE}/chat",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._token}",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                reply = data.get("reply") or data.get("message") or str(data)
                self.response_ready.emit(reply)
        except Exception as exc:
            self.error_occurred.emit(str(exc))


def _get_token() -> str:
    req = urllib.request.Request(
        f"{_API_BASE}/auth/local",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read()).get("access_token", "")


# ── Chat panel ─────────────────────────────────────────────────────────────────

class ChatPanel(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(_PANEL_W)

        self._token: str = ""
        self._worker: Optional[_ApiWorker] = None

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 8)
        root.setSpacing(6)

        # header
        hdr = QHBoxLayout()
        lbl = QLabel("🐠 Guppy")
        lbl.setStyleSheet("color: #a0cfe8; font-size: 11px; font-weight: 600; letter-spacing: 1px;")
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(18, 18)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #607080; border: none; font-size: 11px; }"
            "QPushButton:hover { color: #d0e8f8; }"
        )
        close_btn.clicked.connect(self.hide)
        hdr.addWidget(lbl)
        hdr.addStretch()
        hdr.addWidget(close_btn)
        root.addLayout(hdr)

        # response area
        self._response = QTextEdit()
        self._response.setReadOnly(True)
        self._response.setFixedHeight(140)
        self._response.setStyleSheet(
            "QTextEdit {"
            "  background: #0d1821; color: #c8dde8; border: 1px solid #1e3040;"
            "  border-radius: 8px; padding: 8px; font-size: 12px; line-height: 1.5;"
            "}"
        )
        self._response.setPlaceholderText("Ask Guppy anything…")
        root.addWidget(self._response)

        # input row
        row = QHBoxLayout()
        row.setSpacing(6)
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a message…")
        self._input.setStyleSheet(
            "QLineEdit {"
            "  background: #0d1821; color: #d8eaf4; border: 1px solid #1e3040;"
            "  border-radius: 8px; padding: 6px 10px; font-size: 12px;"
            "}"
            "QLineEdit:focus { border-color: #3a7fa8; }"
        )
        self._input.returnPressed.connect(self._send)

        send_btn = QPushButton("→")
        send_btn.setFixedSize(32, 32)
        send_btn.setStyleSheet(
            "QPushButton { background: #1e5070; color: #a0d8f0; border: none;"
            "  border-radius: 8px; font-size: 16px; }"
            "QPushButton:hover { background: #2a6a90; }"
            "QPushButton:pressed { background: #164050; }"
        )
        send_btn.clicked.connect(self._send)
        row.addWidget(self._input)
        row.addWidget(send_btn)
        root.addLayout(row)

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(QPen(QColor(40, 90, 120, 180), 1))
        p.setBrush(QColor(12, 22, 35, 235))
        p.drawRoundedRect(bg, 12, 12)
        p.end()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._input.setFocus()
        if not self._token:
            try:
                self._token = _get_token()
            except Exception:
                pass

    def _send(self) -> None:
        text = self._input.text().strip()
        if not text or self._worker:
            return
        self._input.clear()
        self._response.append(f"<b style='color:#5fa8cc'>You:</b> {text}<br>")

        self._worker = _ApiWorker(text, self._token)
        self._worker.response_ready.connect(self._on_reply)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.finished.connect(self._on_done)
        self._worker.start()
        self.parent().bowl.set_state(_S.THINKING)  # type: ignore[union-attr]

    def _on_reply(self, text: str) -> None:
        self._response.append(f"<span style='color:#9dd0e8'>Guppy:</span> {text}<br>")
        self._response.verticalScrollBar().setValue(
            self._response.verticalScrollBar().maximum()
        )
        self.parent().bowl.set_state(_S.IDLE)  # type: ignore[union-attr]

    def _on_error(self, err: str) -> None:
        self._response.append(f"<span style='color:#e87070'>Error: {err}</span><br>")
        self.parent().bowl.set_state(_S.IDLE)  # type: ignore[union-attr]

    def _on_done(self) -> None:
        self._worker = None

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        super().keyPressEvent(event)


# ── Main window ────────────────────────────────────────────────────────────────

class FishbowlWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

        self._drag_pos: Optional[QPoint] = None
        self._build_ui()
        self._position_to_corner()

        # hotkey polling
        self._poll = QTimer(self)
        self._poll.timeout.connect(self._check_hotkey)
        self._poll.start(80)

        self._setup_hotkey()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.bowl = BowlWidget(self)
        self.bowl.clicked.connect(self._toggle_chat)
        layout.addWidget(self.bowl, 0, Qt.AlignmentFlag.AlignHCenter)

        self.panel = ChatPanel(self)
        self.panel.hide()
        layout.addWidget(self.panel)

        self.setFixedWidth(_PANEL_W)
        self._update_height()

    def _update_height(self) -> None:
        h = _BOWL_H + (self.panel.height() if self.panel.isVisible() else 0)
        self.setFixedHeight(h)

    def _toggle_chat(self) -> None:
        if self.panel.isVisible():
            self.panel.hide()
            self.bowl.set_state(_S.IDLE)
        else:
            self.panel.show()
            self.bowl.set_state(_S.LISTENING)
        self._update_height()
        self._clamp_to_screen()

    def _position_to_corner(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.right() - self.width() - 16
        y = screen.bottom() - _BOWL_H - 16
        self.move(x, y)

    def _clamp_to_screen(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        pos = self.pos()
        x = max(screen.left(), min(pos.x(), screen.right() - self.width()))
        y = max(screen.top(), min(pos.y(), screen.bottom() - self.height()))
        self.move(x, y)

    def _setup_hotkey(self) -> None:
        try:
            import keyboard as _kb
            _kb.add_hotkey("ctrl+space", _SUMMON_FLAG.set, suppress=False)
        except Exception:
            pass

    def _check_hotkey(self) -> None:
        if _SUMMON_FLAG.is_set():
            _SUMMON_FLAG.clear()
            self._toggle_chat()

    # ── drag ──────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        self._drag_pos = None
        self._clamp_to_screen()
        super().mouseReleaseEvent(event)

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        # Fully transparent window background — children paint themselves.
        pass


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    window = FishbowlWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
