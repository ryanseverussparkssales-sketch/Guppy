"""Hub card widgets extracted from monolithic hub app module."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QBrush, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .theme_config import ACNT, ACNT2, BG2, BG3, DIM


class GlowOrb(QWidget):
    """Pulsing G orb widget used by hub agent cards."""

    def __init__(self, size: int = 28, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.state = "idle"
        self._alpha = 180
        self._dir = 1
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._pulse)

    def set_state(self, state: str):
        self.state = state
        if state in ("pulse_on", "pulse_off", "running"):
            self._timer.start(60)
        else:
            self._timer.stop()
        self.update()

    def _pulse(self):
        self._alpha += self._dir * 12
        if self._alpha >= 255:
            self._alpha = 255
            self._dir = -1
        elif self._alpha <= 80:
            self._alpha = 80
            self._dir = 1
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy, r = self.width() // 2, self.height() // 2, self.width() // 2 - 2

        accent = QColor(ACNT)
        glow = QColor(ACNT)
        glow.setAlpha(self._alpha if self.state != "idle" else 120)

        pen = QPen(glow, 2)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        grad = QRadialGradient(cx, cy, r)
        inner = QColor(BG3)
        inner.setAlpha(220)
        grad.setColorAt(0.0, inner)
        grad.setColorAt(1.0, QColor(ACNT2 if self.state != "idle" else BG2))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(cx - r + 1, cy - r + 1, (r - 1) * 2, (r - 1) * 2)

        p.setPen(QPen(accent if self.state != "idle" else QColor(DIM), 1))
        font = QFont("Segoe UI", r - 4, QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "G")


class ManagerCard(QFrame):
    """UI card for hub recommendation manager state."""

    def __init__(self, manager, text_color: str, parent=None):
        super().__init__(parent)
        self._mgr = manager
        self._text_color = text_color
        self.setObjectName("ManagerCard")
        self._build_ui()
        manager.recommendation_changed.connect(self._on_rec)

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(2)

        top = QHBoxLayout()
        icon_lbl = QLabel(">>")
        icon_lbl.setStyleSheet(f"color:{ACNT}; background:transparent; border:none;")
        lbl = QLabel("OMNISSIAH")
        lbl.setStyleSheet(f"color:{ACNT}; background:transparent; border:none;")
        lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        sub = QLabel("Omnissiah's Vigil")
        sub.setStyleSheet(f"color:{DIM}; background:transparent; border:none;")
        sub.setFont(QFont("Segoe UI", 7))
        top.addWidget(icon_lbl)
        top.addWidget(lbl)
        top.addWidget(sub)
        top.addStretch()
        lay.addLayout(top)

        self._mode_lbl = QLabel(self._mgr.mode)
        self._mode_lbl.setStyleSheet(f"color:{DIM}; background:transparent; border:none;")
        self._mode_lbl.setFont(QFont("Segoe UI", 7))
        lay.addWidget(self._mode_lbl)

        self._rec_lbl = QLabel(self._mgr._recommendation_summary)
        self._rec_lbl.setStyleSheet(f"color:{self._text_color}; background:transparent; border:none;")
        self._rec_lbl.setFont(QFont("Segoe UI", 7))
        lay.addWidget(self._rec_lbl)

        self._ctx_lbl = QLabel(self._mgr._context_summary)
        self._ctx_lbl.setStyleSheet(f"color:{DIM}; background:transparent; border:none;")
        self._ctx_lbl.setFont(QFont("Segoe UI", 7))
        self._ctx_lbl.setWordWrap(True)
        lay.addWidget(self._ctx_lbl)

        self._update_style()

    def _update_style(self):
        active = self._mgr.mode not in ("DISABLED",)
        col = ACNT if active else DIM
        self.setStyleSheet(
            f"ManagerCard{{background:{BG2};"
            f"border:1px solid {col}44;border-radius:6px;}}"
        )

    def _on_rec(self, _agent_id: str, reason: str):
        self._rec_lbl.setText(reason)
        self._ctx_lbl.setText(self._mgr._context_summary)
        self._mode_lbl.setText(self._mgr.mode)
        self._update_style()

    def refresh(self):
        self._mode_lbl.setText(self._mgr.mode)
        self._rec_lbl.setText(self._mgr._recommendation_summary)
        self._ctx_lbl.setText(self._mgr._context_summary)
