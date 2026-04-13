"""
ui/launcher/views/tools_view.py
TOOLS tab — scrollable tool-toggle rows grouped by category.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import tokens as T
from ..components.toggle_row import ToggleRow

# (section_title, [(tool_key, tool_name, description, default_on)])
_TOOL_SECTIONS: list[tuple[str, list[tuple[str, str, str, bool]]]] = [
    ("MEMORY_SYSTEM", [
        ("long_term_memory",  "Long_Term_Context",
         "Retain cross-session user preferences and historical entities.", True),
        ("vector_index",      "Vector_Index_Local",
         "Semantic search across local document directory.", True),
    ]),
    ("WEB_SEARCH_PROTOCOLS", [
        ("realtime_crawler",  "Realtime_Crawler",
         "Live web parsing for breaking news and technical documentation.", True),
        ("academic_relay",    "Academic_Relay",
         "Direct integration with arXiv and scientific journal repositories.", False),
    ]),
    ("MEDIA_PROCESSING", [
        ("vision_engine",     "Vision_Engine_V4",
         "Analyse and describe images or screen captures in real-time.", True),
        ("audio_transcription", "Audio_Transcription",
         "Multilingual Whisper-based speech recognition.", True),
    ]),
    ("TEMPORAL_COORDINATION", [
        ("event_scheduler",   "Event_Scheduler",
         "Auto-reconciliation of conflicting meeting requests.", True),
        ("timezone_harmonizer", "TimeZone_Harmonizer",
         "Contextual time display for global collaboration.", False),
    ]),
    ("SYSTEM_INTEGRITY", [
        ("self_heal_daemon",  "Self_Heal_Daemon",
         "Automatic detection and restart of failing logic modules.", True),
        ("latent_audit",      "Latent_Audit",
         "Continuous logging of AI inference grounding accuracy.", True),
        ("crm_voip",          "CRM_VoIP_Bridge",
         "Integrates contact records and VoIP call events.", False),
    ]),
]


class ToolsView(QWidget):
    tool_state_changed = Signal(str, bool)  # (tool_key, enabled)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._toggles: dict[str, ToggleRow] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(24)

        for section_name, tools in _TOOL_SECTIONS:
            layout.addLayout(self._build_section(section_name, tools))

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _build_section(
        self, title: str, tools: list[tuple[str, str, str, bool]]
    ) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(6)

        # Section header
        header_row = QHBoxLayout()
        header_row.setSpacing(12)
        hdr_lbl = QLabel(title)
        hdr_lbl.setStyleSheet(
            f"color: rgba(242,202,80,0.8); font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_SMALL}pt; font-weight: bold; letter-spacing: 2px;"
        )
        header_row.addWidget(hdr_lbl)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {T.BORDER};")
        line.setSizePolicy(
            line.sizePolicy().horizontalPolicy(),
            line.sizePolicy().verticalPolicy(),
        )
        header_row.addWidget(line, stretch=1)
        col.addLayout(header_row)

        for key, name, desc, default_on in tools:
            row = self._build_tool_row(key, name, desc, default_on)
            col.addWidget(row)

        return col

    def _build_tool_row(
        self, key: str, name: str, desc: str, default_on: bool
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("tool_row")
        card.setStyleSheet(
            f"QFrame#tool_row {{"
            f"  background-color: {T.BG1};"
            f"  border: 1px solid transparent;"
            f"}}"
            f"QFrame#tool_row:hover {{"
            f"  border: 1px solid rgba(77,70,53,0.4);"
            f"}}"
        )

        h = QHBoxLayout(card)
        h.setContentsMargins(16, 12, 16, 12)
        h.setSpacing(12)

        info = QVBoxLayout()
        info.setSpacing(3)

        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_LABEL}pt; font-weight: 600; letter-spacing: 1px;"
        )
        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_BODY}';"
            f"font-size: {T.FS_SMALL}pt;"
        )
        desc_lbl.setWordWrap(True)
        info.addWidget(name_lbl)
        info.addWidget(desc_lbl)

        toggle = ToggleRow("", checked=default_on)
        toggle.toggled.connect(lambda v, k=key: self.tool_state_changed.emit(k, v))
        self._toggles[key] = toggle

        h.addLayout(info, stretch=1)
        h.addWidget(toggle)
        return card

    def get_states(self) -> dict[str, bool]:
        return {k: t.is_checked for k, t in self._toggles.items()}

    def set_states(self, states: dict[str, bool]) -> None:
        for k, v in states.items():
            if k in self._toggles:
                self._toggles[k].setChecked(v)
