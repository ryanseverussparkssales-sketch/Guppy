"""
ui/launcher/views/assistant_view.py
ASSISTANT tab — chat input at bottom, mode/persona/profile dropdowns below it.
Agent cards have moved to the StatusPanel (right column).
"""
from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTextBrowser,
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
    cancel_requested = Signal()
    settings_changed = Signal(dict)
    chat_context_changed = Signal(str, str)

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

        home_row = QHBoxLayout()
        home_row.setContentsMargins(0, 8, 0, 0)
        home_row.setSpacing(10)

        self._home_chip = QLabel("HOME SURFACE")
        self._home_chip.setStyleSheet(
            f"color: {T.TEXT};"
            f"background-color: {T.BG1};"
            f"border: 1px solid {T.BORDER};"
            f"font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
            f"letter-spacing: 2px; padding: 3px 8px;"
        )
        self._instance_chip = QLabel("INSTANCE: GUPPY-PRIMARY")
        self._instance_chip.setStyleSheet(
            f"color: {T.PRIMARY};"
            f"background-color: rgba(242,202,80,0.08);"
            f"border: 1px solid rgba(242,202,80,0.2);"
            f"font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
            f"letter-spacing: 2px; padding: 3px 8px;"
        )
        self._background_chip = QLabel("BACKGROUND: IDLE")
        self._background_chip.setStyleSheet(
            f"color: {T.DIM};"
            f"background-color: {T.BG1};"
            f"border: 1px solid {T.BORDER};"
            f"font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
            f"letter-spacing: 1px; padding: 3px 8px;"
        )
        home_row.addWidget(self._home_chip)
        home_row.addWidget(self._instance_chip)
        home_row.addWidget(self._background_chip, stretch=1)
        root.addLayout(home_row)

        self._background_event = QLabel("Background activity: launcher ready")
        self._background_event.setWordWrap(True)
        self._background_event.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px; padding-top: 8px;"
        )
        root.addWidget(self._background_event)

        self._runtime_facts = QLabel("Runtime: profile=STANDARD · model=GUPPY · voice=EDGE · latency=—")
        self._runtime_facts.setWordWrap(True)
        self._runtime_facts.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        root.addWidget(self._runtime_facts)

        self._recovery_summary = QLabel("Recovery: stable")
        self._recovery_summary.setWordWrap(True)
        self._recovery_summary.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px; padding-bottom: 6px;"
        )
        root.addWidget(self._recovery_summary)

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
        self._conversation_history: list[dict[str, str]] = []

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
        self._send_btn = QPushButton("▶")
        self._send_btn.setFixedSize(34, 34)
        self._send_btn.setStyleSheet(
            f"QPushButton {{ border: none; background: {T.PRIMARY};"
            f"  color: {T.BG}; font-size: 11pt; }}"
            f"QPushButton:hover {{ background: white; }}"
        )
        self._send_btn.clicked.connect(self._submit)
        self._cancel_btn = QPushButton("■")
        self._cancel_btn.setFixedSize(34, 34)
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.setToolTip("Cancel the in-flight request")
        self._cancel_btn.setStyleSheet(
            f"QPushButton {{ border: none; background: {T.ERROR};"
            f"  color: {T.BG}; font-size: 10pt; }}"
            f"QPushButton:hover {{ background: white; color: {T.BG}; }}"
        )
        self._cancel_btn.clicked.connect(self.cancel_requested.emit)
        bar.addWidget(mic_btn)
        bar.addWidget(self._send_btn)
        bar.addWidget(self._cancel_btn)
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
        self._session_strip = _lbl("SESSION: --")
        strip.addWidget(self._session_strip)
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
        self._cb_mode.currentTextChanged.connect(self._emit_context_changed)
        self._cb_persona.currentTextChanged.connect(self._emit_context_changed)
        self.add_system_message("Embedded launcher chat ready.")

    def _add_message(self, text: str, role: str) -> None:
        msg_widget: QWidget

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

        if role == "assistant":
            msg = QTextBrowser()
            msg.setOpenExternalLinks(False)
            msg.setReadOnly(True)
            msg.setUndoRedoEnabled(False)
            msg.setMarkdown(text)
            msg.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            msg.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            msg.setStyleSheet(
                f"QTextBrowser {{"
                f"  color: {fg}; background-color: {bg};"
                f"  border: 1px solid {T.BORDER};"
                f"  font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt;"
                f"  padding: 8px;"
                f"}}"
            )
            msg.setMaximumWidth(760)
            msg.setMaximumHeight(280)
            msg_widget = msg
        else:
            msg = QLabel(text)
            msg.setWordWrap(True)
            msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            msg.setStyleSheet(
                f"color: {fg}; background-color: {bg};"
                f"border: 1px solid {T.BORDER};"
                f"font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt;"
                f"padding: 8px;"
            )
            msg.setMaximumWidth(760)
            msg_widget = msg

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        if align == Qt.AlignmentFlag.AlignRight:
            row.addStretch()
            row.addWidget(msg_widget)
        elif align == Qt.AlignmentFlag.AlignLeft:
            row.addWidget(msg_widget)
            row.addStretch()
        else:
            row.addStretch()
            row.addWidget(msg_widget)
            row.addStretch()

        self._chat_layout.insertLayout(self._chat_layout.count() - 1, row)
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        bar = self._chat_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _clear_transcript_widgets(self) -> None:
        while self._chat_layout.count() > 1:
            item = self._chat_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
                continue
            nested = item.layout()
            if nested is not None:
                while nested.count():
                    n_item = nested.takeAt(0)
                    if n_item is None:
                        continue
                    n_widget = n_item.widget()
                    if n_widget is not None:
                        n_widget.deleteLater()

    def add_user_message(self, text: str) -> None:
        self._add_message(text, "user")
        self._conversation_history.append({"role": "user", "content": text})

    def add_assistant_message(self, text: str) -> None:
        self._add_message(text, "assistant")
        self._conversation_history.append({"role": "assistant", "content": text})

    def add_system_message(self, text: str) -> None:
        self._add_message(text, "system")

    def activate_agent(self, agent: str) -> None:
        agents = {"guppy": 0, "merlin": 1, "council": 2}
        key = (agent or "").strip().lower()
        if key in agents:
            self._cb_persona.setCurrentIndex(agents[key])
        self._status_strip.setText(f"ACTIVE AGENT: {(agent or 'guppy').upper()}")
        self.set_background_event(f"Active agent switched to {(agent or 'guppy').upper()}")

    # ── Public API ────────────────────────────────────────────────────────────
    def _submit(self) -> None:
        if not self._input.isEnabled():
            return
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

    def set_active_instance(self, instance: str) -> None:
        name = (instance or "guppy-primary").strip() or "guppy-primary"
        self._instance_chip.setText(f"INSTANCE: {name.upper()}")

    def set_background_status(self, text: str, healthy: bool = True) -> None:
        msg = (text or "idle").strip() or "idle"
        color = T.GREEN if healthy else T.ERROR
        self._background_chip.setText(f"BACKGROUND: {msg.upper()}")
        self._background_chip.setStyleSheet(
            f"color: {color};"
            f"background-color: {T.BG1};"
            f"border: 1px solid {color};"
            f"font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
            f"letter-spacing: 1px; padding: 3px 8px;"
        )

    def set_background_event(self, text: str) -> None:
        msg = (text or "launcher ready").strip() or "launcher ready"
        self._background_event.setText(f"Background activity: {msg}")

    def set_runtime_facts(
        self,
        *,
        profile: str = "standard",
        model: str = "guppy",
        voice: str = "edge",
        latency: str = "—",
        last_query: str = "—",
    ) -> None:
        query = (last_query or "—").strip() or "—"
        query = query[:96] + "..." if len(query) > 96 else query
        self._runtime_facts.setText(
            "Runtime: "
            f"profile={str(profile).upper()} · "
            f"model={str(model).upper()} · "
            f"voice={str(voice).upper()} · "
            f"latency={latency} · "
            f"last={query}"
        )

    def set_recovery_summary(self, text: str, healthy: bool = True) -> None:
        summary = (text or "stable").strip() or "stable"
        color = T.GREEN if healthy else T.ERROR
        self._recovery_summary.setText(f"Recovery: {summary}")
        self._recovery_summary.setStyleSheet(
            f"color: {color}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px; padding-bottom: 6px;"
        )

    def set_request_in_flight(self, in_flight: bool) -> None:
        self._input.setEnabled(not in_flight)
        self._send_btn.setEnabled(not in_flight)
        self._cancel_btn.setEnabled(in_flight)

    def set_session_id(self, session_id: str) -> None:
        sid = (session_id or "").strip()
        suffix = sid[-8:] if sid else "--"
        self._session_strip.setText(f"SESSION: {suffix}")

    def reset_live_history(self) -> None:
        self._conversation_history.clear()

    def clear_transcript(self) -> None:
        self._clear_transcript_widgets()
        self.reset_live_history()

    def restore_history(self, history: list[dict[str, str]]) -> None:
        self.clear_transcript()
        for item in history:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role", "")).strip().lower()
            content = str(item.get("content", "") or "").strip()
            if not content:
                continue
            if role == "user":
                self.add_user_message(content)
            elif role == "assistant":
                self.add_assistant_message(content)

    def recent_history(self, limit: int = 12) -> list[dict[str, str]]:
        trimmed = self._conversation_history[-max(1, limit):]
        return [dict(item) for item in trimmed if item.get("role") in {"user", "assistant"}]

    def set_chat_context(self, mode: str, persona: str) -> None:
        mode_key = (mode or "").strip().lower()
        persona_key = (persona or "").strip().lower()

        for idx in range(self._cb_mode.count()):
            if self._cb_mode.itemText(idx).strip().lower() == mode_key:
                self._cb_mode.setCurrentIndex(idx)
                break

        for idx in range(self._cb_persona.count()):
            if self._cb_persona.itemText(idx).strip().lower() == persona_key:
                self._cb_persona.setCurrentIndex(idx)
                break

    def chat_context(self) -> tuple[str, str]:
        return self.selected_mode(), self._cb_persona.currentText().strip().lower()

    def _emit_context_changed(self, _text: str) -> None:
        self.chat_context_changed.emit(self.selected_mode(), self._cb_persona.currentText().strip().lower())
