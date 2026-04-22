from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel
from src.guppy.ui.theme import SHARED


class StartupChecklist(QFrame):
    def __init__(self, title: str = "STARTUP CHECKLIST", parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"QFrame{{background:#0b0e16;border:1px solid #2d3446;border-radius:{SHARED.panel_radius}px;}}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(SHARED.spacing_sm, SHARED.spacing_xs + 2, SHARED.spacing_sm, SHARED.spacing_xs + 2)
        lay.setSpacing(2)

        hdr = QLabel(title)
        hdr.setFont(QFont(SHARED.font_family_mono, SHARED.font_size_small, QFont.Weight.Bold))
        hdr.setStyleSheet("color:#9db6df;background:transparent;")
        lay.addWidget(hdr)

        self._rows = {}
        for key in ("auth", "ollama", "voice"):
            lbl = QLabel(f"{key.upper():<7} -")
            lbl.setFont(QFont(SHARED.font_family_mono, SHARED.sidebar_label_font_size))
            lbl.setStyleSheet("color:#8a93a4;background:transparent;")
            lay.addWidget(lbl)
            self._rows[key] = lbl

    def set_checks(self, checks: dict):
        for key, lbl in self._rows.items():
            val = str((checks or {}).get(key, "MISSING")).upper()
            col = "#8a93a4"
            if val == "READY":
                col = "#70d6a5"
            elif val == "PARTIAL":
                col = "#d5ae58"
            elif val == "MISSING":
                col = "#ca6868"
            lbl.setText(f"{key.upper():<7} {val}")
            lbl.setStyleSheet(f"color:{col};background:transparent;")
