from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QListWidget, QListWidgetItem
from src.guppy.ui.theme import SHARED


class TimelinePanel(QFrame):
    def __init__(self, title: str = "TIMELINE", parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"QFrame{{background:#0b0e16;border:1px solid #273246;border-radius:{SHARED.panel_radius}px;}}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(SHARED.spacing_sm, SHARED.spacing_xs + 2, SHARED.spacing_sm, SHARED.spacing_xs + 2)
        lay.setSpacing(SHARED.spacing_xs)

        hdr = QLabel(title)
        hdr.setFont(QFont(SHARED.font_family_mono, SHARED.font_size_small, QFont.Weight.Bold))
        hdr.setStyleSheet("color:#8fb7ff;background:transparent;")
        lay.addWidget(hdr)

        self._list = QListWidget()
        self._list.setStyleSheet(
            f"QListWidget{{background:#090c14;color:#b8c4d8;border:1px solid #1b2433;border-radius:{max(3, SHARED.panel_radius - 2)}px;}}"
            "QListWidget::item{padding:2px 4px;}"
        )
        self._list.setFont(QFont(SHARED.font_family_mono, SHARED.sidebar_label_font_size))
        lay.addWidget(self._list)

    def add_event(self, when: str, text: str):
        item = QListWidgetItem(f"{when}  {text}")
        self._list.addItem(item)
        while self._list.count() > 120:
            self._list.takeItem(0)
        self._list.scrollToBottom()
