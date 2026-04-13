"""
ui/launcher/views/assistant_view.py
ASSISTANT tab — mode/persona/profile dropdowns, agent cards, chat input.
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .. import tokens as T
from ..components.agent_card import AgentCard

_RUNTIME = Path(__file__).resolve().parent.parent.parent.parent / "runtime"


def _lbl(text: str, color: str = T.DIM, size: int = T.FS_TINY, bold: bool = False) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}';"
        f"font-size: {size}pt; letter-spacing: 1px;"
        + ("font-weight: bold;" if bold else "")
    )
    return lbl


def _dropdown(options: list[str]) -> QComboBox:
    cb = QComboBox()
    cb.addItems(options)
    return cb


class AssistantView(QWidget):
    command_submitted = Signal(str)
    settings_changed = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 0)
        root.setSpacing(0)

        # ── Controls row ──────────────────────────────────────────────────────
        ctrl = QHBoxLayout()
        ctrl.setSpacing(16)

        for header, opts, cb_attr in [
            ("MODE",            ["AUTO", "CLAUDE", "OLLAMA", "TEACHING"],       "_cb_mode"),
            ("PERSONA",         ["GUPPY", "MERLIN", "COUNCIL"],                 "_cb_persona"),
            ("RUNTIME PROFILE", ["LIGHT", "STANDARD", "POWER"],                 "_cb_profile"),
        ]:
            col = QVBoxLayout()
            col.setSpacing(4)
            col.addWidget(_lbl(header))
            cb = _dropdown(opts)
            setattr(self, cb_attr, cb)
            col.addWidget(cb)
            ctrl.addLayout(col)

        root.addLayout(ctrl)
        root.addSpacing(10)

        # ── Recommendation chip ───────────────────────────────────────────────
        self._rec_chip = QLabel("RECOMMENDED: STANDARD")
        self._rec_chip.setStyleSheet(
            f"color: {T.PRIMARY};"
            f"background-color: rgba(242,202,80,0.08);"
            f"border: 1px solid rgba(242,202,80,0.2);"
            f"font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
            f"font-weight: bold; letter-spacing: 2px; padding: 3px 8px;"
        )
        self._rec_chip.setFixedHeight(24)
        root.addWidget(self._rec_chip)
        root.addSpacing(16)

        # ── Agent cards (scrollable) ──────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        cards_widget = QWidget()
        cards_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        cards_layout = QVBoxLayout(cards_widget)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(10)

        self._card_guppy   = AgentCard("GUPPY",   accent=T.PRIMARY)
        self._card_merlin  = AgentCard("MERLIN",  accent=T.SECONDARY)
        self._card_council = AgentCard("COUNCIL", accent=T.TERTIARY)

        for c in [self._card_guppy, self._card_merlin, self._card_council]:
            cards_layout.addWidget(c)
        cards_layout.addStretch()

        scroll.setWidget(cards_widget)
        root.addWidget(scroll, stretch=1)

        # ── Chat input ────────────────────────────────────────────────────────
        root.addSpacing(10)
        input_frame = QFrame()
        input_frame.setObjectName("chat_bar")
        input_frame.setStyleSheet(
            f"QFrame#chat_bar {{"
            f"  background-color: {T.BG0};"
            f"  border: 1px solid {T.BORDER};"
            f"}}"
        )
        bar = QHBoxLayout(input_frame)
        bar.setContentsMargins(12, 0, 8, 0)
        bar.setSpacing(8)

        cmd_icon = QLabel("⊞")
        cmd_icon.setStyleSheet(f"color: {T.DIM}; font-size: {T.FS_TITLE}pt;")
        bar.addWidget(cmd_icon)

        self._input = QLineEdit()
        self._input.setPlaceholderText("EXECUTE COMMAND OR ASK GUPPY...")
        self._input.setStyleSheet(
            f"QLineEdit {{ background: transparent; border: none;"
            f"  color: {T.TEXT}; font-family: '{T.FF_MONO}';"
            f"  font-size: {T.FS_LABEL}pt; letter-spacing: 1px; }}"
        )
        self._input.returnPressed.connect(self._submit)
        bar.addWidget(self._input, stretch=1)

        mic_btn = QPushButton("●")
        mic_btn.setFixedSize(34, 34)
        mic_btn.setEnabled(False)
        mic_btn.setToolTip("Launcher PTT is not wired yet. Use Guppy surface for voice capture.")
        mic_btn.setStyleSheet(
            f"QPushButton {{ border: none; color: {T.PRIMARY}; font-size: 13pt; }}"
            f"QPushButton:hover {{ color: white; }}"
        )
        send_btn = QPushButton("▶")
        send_btn.setFixedSize(34, 34)
        send_btn.setStyleSheet(
            f"QPushButton {{ border: none; background: {T.PRIMARY};"
            f"  color: {T.BG}; font-size: 11pt; }}"
            f"QPushButton:hover {{ background: white; }}"
        )
        send_btn.clicked.connect(self._submit)
        bar.addWidget(mic_btn)
        bar.addWidget(send_btn)

        root.addWidget(input_frame)

        # status strip
        strip = QHBoxLayout()
        strip.setContentsMargins(2, 4, 2, 12)
        strip.addWidget(_lbl("LINKED: TERMINAL_ALPHA"))
        strip.addWidget(_lbl("ENCRYPTION: AES-256"))
        strip.addStretch()
        self._status_strip = QLabel("SYSTEM READY")
        self._status_strip.setStyleSheet(
            f"color: {T.PRIMARY}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        strip.addWidget(self._status_strip)
        root.addLayout(strip)

    # ── Public API ────────────────────────────────────────────────────────────
    def _submit(self) -> None:
        text = self._input.text().strip()
        if text:
            self.command_submitted.emit(text)
            self._input.clear()

    def set_recommendation(self, profile: str) -> None:
        self._rec_chip.setText(f"RECOMMENDED: {profile.upper()}")

    def update_agent_status(self, agent: str, online: bool,
                            last_seen: str = "NOW", load: float | None = None) -> None:
        card = {"guppy": self._card_guppy,
                "merlin": self._card_merlin,
                "council": self._card_council}.get(agent.lower())
        if card:
            card.update_status(online, last_seen, load)

    def apply_settings(self, s: dict) -> None:
        modes = {"auto": 0, "claude": 1, "ollama": 2, "teaching": 3}
        self._cb_mode.setCurrentIndex(modes.get(s.get("default_mode", "auto"), 0))
        profiles = {"light": 0, "standard": 1, "power": 2}
        self._cb_profile.setCurrentIndex(profiles.get(s.get("runtime_profile", "standard"), 1))

    def set_input_text(self, text: str) -> None:
        self._input.setText(text)
        self._input.setFocus()
