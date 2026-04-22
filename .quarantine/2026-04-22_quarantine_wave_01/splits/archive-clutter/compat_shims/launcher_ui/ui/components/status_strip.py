from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel
from src.guppy.ui.theme import SHARED


class IncidentBadge(QLabel):
    _COLORS = {
        "info": "#4a6fa8",
        "warn": "#b7862e",
        "error": "#a84646",
    }

    def __init__(self, text: str, severity: str = "info", parent=None):
        super().__init__(text, parent)
        sev = severity if severity in self._COLORS else "info"
        col = self._COLORS[sev]
        self.setStyleSheet(
            f"background:{col}22;color:{col};border:1px solid {col}66;"
            f"border-radius:{max(3, SHARED.panel_radius - 2)}px;padding:1px {max(4, SHARED.spacing_xs + 2)}px;"
        )
        self.setFont(QFont(SHARED.font_family_mono, SHARED.sidebar_label_font_size))


class StatusStrip(QFrame):
    def __init__(self, accent: str = "#6aa7ff", parent=None):
        super().__init__(parent)
        self._accent = accent
        self.setStyleSheet(
            f"QFrame{{background:#0b0e16;border:1px solid {accent}33;border-radius:{SHARED.panel_radius}px;}}"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(SHARED.spacing_sm, SHARED.spacing_xs, SHARED.spacing_sm, SHARED.spacing_xs)
        lay.setSpacing(SHARED.spacing_sm)

        self._summary = QLabel("MODE - | AUTH - | OLLAMA - | VOICE -")
        self._summary.setStyleSheet("color:#a0a8b8;background:transparent;")
        self._summary.setFont(QFont(SHARED.font_family_mono, SHARED.sidebar_label_font_size))
        lay.addWidget(self._summary, stretch=1)

        self._lat = QLabel("p95 - | p99 - | qd 0")
        self._lat.setStyleSheet("color:#7fb0ff;background:transparent;")
        self._lat.setFont(QFont(SHARED.font_family_mono, SHARED.sidebar_label_font_size))
        lay.addWidget(self._lat)

        self._voice_detail = QLabel("tts - | voice -")
        self._voice_detail.setStyleSheet("color:#92a0b4;background:transparent;")
        self._voice_detail.setFont(QFont(SHARED.font_family_mono, SHARED.sidebar_label_font_size))
        lay.addWidget(self._voice_detail)

        self._incidents = QHBoxLayout()
        self._incidents.setSpacing(SHARED.spacing_xs)
        lay.addLayout(self._incidents)

    def set_summary(self, mode: str, auth: str, ollama: str, voice: str):
        self._summary.setText(
            f"MODE {str(mode).upper()} | AUTH {auth} | OLLAMA {ollama} | VOICE {voice}"
        )

    def set_latency(self, p95_ms: float, p99_ms: float, queue_depth: int):
        p95 = f"{p95_ms:.0f}ms" if p95_ms else "-"
        p99 = f"{p99_ms:.0f}ms" if p99_ms else "-"
        self._lat.setText(f"p95 {p95} | p99 {p99} | qd {max(0, int(queue_depth))}")
        if queue_depth > 0:
            self._lat.setStyleSheet("color:#d9a94f;background:transparent;")
        else:
            self._lat.setStyleSheet("color:#7fb0ff;background:transparent;")

    def set_voice_detail(self, tts_backend: str, voice_name: str):
        backend = (tts_backend or "-").strip().upper()
        voice = (voice_name or "-").strip()
        if len(voice) > 18:
            voice = f"{voice[:7]}...{voice[-7:]}"
        self._voice_detail.setText(f"tts {backend} | voice {voice}")

    def set_incidents(self, incidents):
        while self._incidents.count():
            item = self._incidents.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        for inc in (incidents or [])[:4]:
            if not isinstance(inc, dict):
                continue
            txt = str(inc.get("text", "")).strip()
            sev = str(inc.get("severity", "info")).lower()
            if txt:
                self._incidents.addWidget(IncidentBadge(txt, sev, self))
