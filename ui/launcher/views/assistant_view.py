"""
ui/launcher/views/assistant_view.py
ASSISTANT tab — chat input at bottom, mode/persona/profile dropdowns below it.
Agent cards have moved to the StatusPanel (right column).
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from inference_router import LAUNCHER_MODES_DISPLAY
from .. import tokens as T


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
        root.setContentsMargins(28, 24, 28, 16)
        root.setSpacing(0)

        # ── Recommendation chip (top anchor) ─────────────────────────────────
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

        # ── Chat transcript (above input) ─────────────────────────────────────
        root.addSpacing(8)
        transcript = QFrame()
        transcript.setObjectName("chat_transcript")
        transcript.setStyleSheet(
            f"QFrame#chat_transcript {{"
            f"  background-color: {T.BG};"
            f"  border: 1px solid {T.BORDER};"
            f"}}"
        )
        tcol = QVBoxLayout(transcript)
        tcol.setContentsMargins(8, 8, 8, 8)
        tcol.setSpacing(0)

        self._chat_scroll = QScrollArea()
        self._chat_scroll.setWidgetResizable(True)
        self._chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._chat_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self._chat_content = QWidget()
        self._chat_content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._chat_layout = QVBoxLayout(self._chat_content)
        self._chat_layout.setContentsMargins(0, 0, 0, 0)
        self._chat_layout.setSpacing(8)
        self._chat_layout.addStretch()

        self._chat_scroll.setWidget(self._chat_content)
        tcol.addWidget(self._chat_scroll)
        root.addWidget(transcript, stretch=1)

        # ── Chat input + integrated status strip ──────────────────────────────
        input_frame = QFrame()
        input_frame.setObjectName("chat_bar")
        input_frame.setStyleSheet(
            f"QFrame#chat_bar {{"
            f"  background-color: {T.BG0};"
            f"  border: 1px solid {T.BORDER};"
            f"}}"
        )
        frame_col = QVBoxLayout(input_frame)
        frame_col.setContentsMargins(0, 0, 0, 0)
        frame_col.setSpacing(0)

        # input row
        bar = QHBoxLayout()
        bar.setContentsMargins(12, 6, 8, 6)
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
        frame_col.addLayout(bar)

        # thin divider inside the frame
        inner_div = QFrame()
        inner_div.setFixedHeight(1)
        inner_div.setStyleSheet(f"background: {T.BORDER};")
        frame_col.addWidget(inner_div)

        # status strip — integrated below the input row
        strip = QHBoxLayout()
        strip.setContentsMargins(12, 3, 8, 4)
        strip.setSpacing(12)
        strip.addWidget(_lbl("LINKED: TERMINAL_ALPHA"))
        strip.addWidget(_lbl("ENCRYPTION: AES-256"))
        strip.addStretch()
        self._status_strip = QLabel("SYSTEM READY")
        self._status_strip.setStyleSheet(
            f"color: {T.PRIMARY}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        strip.addWidget(self._status_strip)
        frame_col.addLayout(strip)

        root.addWidget(input_frame)
        root.addSpacing(12)

        # ── Controls row (dropdowns at bottom) ────────────────────────────────
        ctrl = QHBoxLayout()
        ctrl.setSpacing(16)

        for header, opts, cb_attr in [
            ("MODE",            list(LAUNCHER_MODES_DISPLAY),  "_cb_mode"),
            ("PERSONA",         ["GUPPY", "MERLIN", "COUNCIL"],            "_cb_persona"),
            ("RUNTIME PROFILE", ["LIGHT", "STANDARD", "POWER"],            "_cb_profile"),
        ]:
            col = QVBoxLayout()
            col.setSpacing(4)
            col.addWidget(_lbl(header))
            cb = _dropdown(opts)
            setattr(self, cb_attr, cb)
            col.addWidget(cb)
            ctrl.addLayout(col)

        root.addLayout(ctrl)
        self.add_system_message("Embedded launcher chat ready.")

    def _add_message(self, text: str, role: str) -> None:
        msg = QLabel(text)
        msg.setWordWrap(True)
        msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        if role == "user":
            fg = T.BG
            bg = T.PRIMARY
            align = Qt.AlignmentFlag.AlignRight
        elif role == "assistant":
            fg = T.TEXT
            bg = T.BG0
            align = Qt.AlignmentFlag.AlignLeft
        else:
            fg = T.DIM
            bg = T.BG1
            align = Qt.AlignmentFlag.AlignHCenter

        msg.setStyleSheet(
            f"color: {fg}; background-color: {bg};"
            f"border: 1px solid {T.BORDER};"
            f"font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt;"
            f"padding: 8px;"
        )
        msg.setMaximumWidth(760)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        if align == Qt.AlignmentFlag.AlignRight:
            row.addStretch()
            row.addWidget(msg)
        elif align == Qt.AlignmentFlag.AlignLeft:
            row.addWidget(msg)
            row.addStretch()
        else:
            row.addStretch()
            row.addWidget(msg)
            row.addStretch()

        self._chat_layout.insertLayout(self._chat_layout.count() - 1, row)
        self._chat_scroll.verticalScrollBar().setValue(self._chat_scroll.verticalScrollBar().maximum())

    def add_user_message(self, text: str) -> None:
        self._add_message(text, "user")

    def add_assistant_message(self, text: str) -> None:
        self._add_message(text, "assistant")

    def add_system_message(self, text: str) -> None:
        self._add_message(text, "system")

    def activate_agent(self, agent: str) -> None:
        agents = {"guppy": 0, "merlin": 1, "council": 2}
        key = (agent or "").strip().lower()
        if key in agents:
            self._cb_persona.setCurrentIndex(agents[key])
        self._status_strip.setText(f"ACTIVE AGENT: {(agent or 'guppy').upper()}")

    # ── Public API ────────────────────────────────────────────────────────────
    def _submit(self) -> None:
        text = self._input.text().strip()
        if text:
            self.command_submitted.emit(text)
            self._input.clear()

    def set_recommendation(self, profile: str) -> None:
        self._rec_chip.setText(f"RECOMMENDED: {profile.upper()}")

    def apply_settings(self, s: dict) -> None:
        modes = {"auto": 0, "claude": 1, "ollama": 2, "local": 3, "code": 4, "teaching": 5}
        self._cb_mode.setCurrentIndex(modes.get(s.get("default_mode", "auto"), 0))
        profiles = {"light": 0, "standard": 1, "power": 2}
        self._cb_profile.setCurrentIndex(profiles.get(s.get("runtime_profile", "standard"), 1))

    def selected_mode(self) -> str:
        mode = self._cb_mode.currentText().strip().lower()
        return mode or "auto"

    def set_input_text(self, text: str) -> None:
        self._input.setText(text)
        self._input.setFocus()

    def set_status(self, text: str) -> None:
        """Update the integrated status strip (transient state — Processing, Ready, etc)."""
        self._status_strip.setText(text.upper())
