"""
ui/launcher/views/assistant_view.py
Home chat surface with a calmer, messenger-style launcher layout.
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
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from src.guppy.inference.router import LAUNCHER_MODES_DISPLAY
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
    mic_requested = Signal()
    starter_requested = Signal(str, str)
    settings_changed = Signal(dict)
    chat_context_changed = Signal(str, str)
    launcher_summary_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._request_in_flight_ui = False
        self._mic_capture_active = False
        self._workspace_type = "user_instance"
        self._workspace_role = "Daily assistant workspace"
        self._workspace_purpose = "General help, chat, and quick tasks."
        self._starter_buttons: dict[str, QPushButton] = {}
        self._starter_meta: dict[str, tuple[str, str, str]] = {}
        self._conversation_history: list[dict[str, str]] = []
        self._empty_state_title_text = "Start with one clear ask"
        self._empty_state_subtitle_text = "Use the composer below for the next thing you want to move forward. Starters are optional."
        self._empty_state_recipe_text = "Next step: type one request and press Send."

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 12)
        root.setSpacing(12)

        self._hero_title = QLabel("One clear ask at a time.")
        self._hero_subtitle = QLabel("Use the composer below for the main action. Start with a starter only if you want a head start.")
        self._rec_chip = QLabel("RECOMMENDED / STANDARD")
        self._instance_chip = QLabel("WORKSPACE / GUPPY-PRIMARY")
        self._background_chip = QLabel("READY")
        self._entry_hint = QLabel("Primary action: type one short request and press Send.")
        self._background_event = QLabel("Latest activity: launcher ready", self)
        self._background_event.setVisible(False)
        self._workspace_summary = QLabel("Active workspace: Daily assistant workspace. General help, chat, and quick tasks.", self)
        self._workspace_summary.setVisible(False)
        self._runtime_facts = QLabel("Ready now: Standard profile, Guppy model, Edge voice.", self)
        self._runtime_facts.setVisible(False)
        self._route_facts = QLabel("Next reply: waiting for your next message.", self)
        self._route_facts.setVisible(False)
        self._recovery_summary = QLabel("System health: stable", self)
        self._recovery_summary.setVisible(False)
        self._context_bar = QFrame()
        self._context_bar.setObjectName("home_context_bar")
        self._context_bar.setStyleSheet(
            f"QFrame#home_context_bar {{ background-color: rgba(255,250,243,0.52); border: 1px solid rgba(205,181,154,0.28); border-radius: 16px; }}"
        )
        context_bar_layout = QVBoxLayout(self._context_bar)
        context_bar_layout.setContentsMargins(12, 9, 12, 9)
        context_bar_layout.setSpacing(4)
        for widget in (
            self._background_event,
            self._workspace_summary,
            self._runtime_facts,
            self._route_facts,
            self._recovery_summary,
        ):
            widget.setWordWrap(True)
            widget.setStyleSheet(
                f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
            )
            context_bar_layout.addWidget(widget)
        self._context_bar.setVisible(False)

        self._starter_summary = QLabel(
            "Optional starters are here if you want a head start."
        )
        self._starter_summary.setWordWrap(True)
        self._starter_summary.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._starter_summary.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;"
        )
        self._starter_summary.setVisible(True)
        self._starter_row = QHBoxLayout()
        self._starter_row.setSpacing(8)
        for starter_id, title, mode, prompt in self._starter_templates():
            btn = QPushButton(title)
            btn.setToolTip(prompt)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{ background: {T.BG0}; color: {T.TEXT}; border: 1px solid {T.BORDER};"
                f" border-radius: 11px; padding: 5px 9px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ border-color: {T.PRIMARY}; color: {T.PRIMARY}; background: rgba(242,202,80,0.05); }}"
            )
            btn.clicked.connect(lambda _=False, sid=starter_id: self._load_starter_by_id(sid))
            self._starter_buttons[starter_id] = btn
            self._starter_row.addWidget(btn)
        self._starter_row.addStretch()
        self._refresh_starter_buttons()

        transcript = QFrame()
        transcript.setObjectName("chat_surface")
        transcript.setStyleSheet(
            f"QFrame#chat_surface {{ background-color: rgba(255,250,243,0.62); border: 1px solid rgba(205,181,154,0.42); border-radius: 24px; }}"
        )
        tcol = QVBoxLayout(transcript)
        tcol.setContentsMargins(16, 14, 16, 14)
        tcol.setSpacing(10)

        transcript_hdr = QHBoxLayout()
        transcript_hdr.setSpacing(8)
        self._status_strip = QLabel("READY")
        self._status_strip.setStyleSheet(
            f"color: {T.GREEN}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        transcript_hdr.addStretch()
        transcript_hdr.addWidget(self._status_strip)
        tcol.addLayout(transcript_hdr)

        self._chat_scroll = QScrollArea()
        self._chat_scroll.setWidgetResizable(True)
        self._chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._chat_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self._chat_content = QWidget()
        self._chat_content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._chat_layout = QVBoxLayout(self._chat_content)
        self._chat_layout.setContentsMargins(12, 8, 12, 8)
        self._chat_layout.setSpacing(18)
        self._empty_state = self._build_empty_state()
        self._chat_layout.addWidget(self._empty_state)
        self._chat_layout.addStretch()
        self._chat_scroll.setWidget(self._chat_content)
        root.addWidget(self._context_bar)
        tcol.addWidget(self._chat_scroll, stretch=1)
        root.addWidget(transcript, stretch=1)

        composer = QFrame()
        composer.setObjectName("chat_composer")
        composer.setStyleSheet(
            f"QFrame#chat_composer {{ background-color: rgba(255,250,243,0.74); border: 1px solid rgba(205,181,154,0.34); border-radius: 26px; }}"
        )
        composer_col = QVBoxLayout(composer)
        composer_col.setContentsMargins(12, 9, 12, 8)
        composer_col.setSpacing(6)

        starter_strip = QHBoxLayout()
        starter_strip.setSpacing(8)
        composer_col.addWidget(self._starter_summary)
        starter_strip.addLayout(self._starter_row, stretch=1)
        composer_col.addLayout(starter_strip)

        self._launcher_panel = QFrame()
        self._launcher_panel.setObjectName("launcher_panel")
        self._launcher_panel.setStyleSheet(
            f"QFrame#launcher_panel {{ background-color: rgba(255,250,243,0.86); border: 1px solid {T.BORDER}; border-radius: 14px; }}"
        )
        launcher_panel_col = QVBoxLayout(self._launcher_panel)
        launcher_panel_col.setContentsMargins(12, 10, 12, 10)
        launcher_panel_col.setSpacing(8)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        for header, opts, cb_attr in [
            ("MODE", list(LAUNCHER_MODES_DISPLAY), "_cb_mode"),
            ("PERSONA", ["GUPPY"], "_cb_persona"),
            ("PROFILE", ["LIGHT", "STANDARD", "POWER"], "_cb_profile"),
        ]:
            col = QVBoxLayout()
            col.setSpacing(4)
            col.addWidget(_lbl(header))
            cb = _dropdown(opts)
            cb.setStyleSheet(
                f"QComboBox {{ background: {T.BG0}; color: {T.TEXT}; border: 1px solid {T.BORDER};"
                f" border-radius: 10px; padding: 4px 8px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            )
            setattr(self, cb_attr, cb)
            col.addWidget(cb)
            controls.addLayout(col)
        controls.addStretch()
        launcher_panel_col.addLayout(controls)
        composer_col.addWidget(self._launcher_panel)
        self._launcher_panel.setVisible(False)

        input_shell = QFrame()
        input_shell.setObjectName("composer_shell")
        input_shell.setStyleSheet(
            f"QFrame#composer_shell {{ background-color: rgba(255,255,255,0.78); border: 1px solid rgba(205,181,154,0.34); border-radius: 28px; }}"
        )
        input_row = QHBoxLayout(input_shell)
        input_row.setContentsMargins(16, 7, 7, 7)
        input_row.setSpacing(7)

        self._input = QLineEdit()
        self._input.setPlaceholderText(self._workspace_input_placeholder("user_instance"))
        self._input.setStyleSheet(
            f"QLineEdit {{ background: transparent; border: none; color: {T.TEXT};"
            f" font-family: '{T.FF_BODY}'; font-size: {T.FS_LABEL}pt; padding: 2px 0; }}"
        )
        self._input.returnPressed.connect(self._submit)
        input_row.addWidget(self._input, stretch=1)

        self._mic_btn = QPushButton("\u25cf")
        self._mic_btn.setFixedSize(32, 32)
        self._mic_btn.setToolTip("Push to talk. Click again while listening to stop capture.")
        self._mic_btn.setStyleSheet(
            f"QPushButton {{ border: 1px solid rgba(205,181,154,0.34); border-radius: 16px; background: rgba(255,250,243,0.92); color: {T.PRIMARY}; font-size: 10pt; }}"
            f"QPushButton:hover {{ border-color: rgba(255,107,61,0.55); background: #ffffff; }}"
        )
        self._mic_btn.clicked.connect(self.mic_requested.emit)

        self._cancel_btn = QPushButton("\u25a0")
        self._cancel_btn.setFixedSize(32, 32)
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.setToolTip("Cancel the in-flight request")
        self._cancel_btn.setStyleSheet(
            f"QPushButton {{ border: 1px solid rgba(200,75,68,0.42); border-radius: 16px; background: rgba(255,250,243,0.80); color: {T.ERROR}; font-size: 8pt; }}"
            f"QPushButton:hover {{ background: rgba(200,75,68,0.10); }}"
        )
        self._cancel_btn.clicked.connect(self.cancel_requested.emit)

        self._send_btn = QPushButton("\u25b6")
        self._send_btn.setFixedSize(36, 36)
        self._send_btn.setStyleSheet(
            f"QPushButton {{ border: none; border-radius: 18px; background: {T.PRIMARY}; color: {T.BG}; font-size: 10pt; }}"
            f"QPushButton:hover {{ background: {T.PRIMARY_DIM}; }}"
        )
        self._send_btn.clicked.connect(self._submit)

        input_row.addWidget(self._mic_btn)
        input_row.addWidget(self._cancel_btn)
        input_row.addWidget(self._send_btn)
        composer_col.addWidget(input_shell)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        self._session_strip = _lbl("SESSION: --")
        self._session_strip.setStyleSheet(
            f"color: rgba(115,96,79,0.72); font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        footer.addWidget(self._session_strip)
        footer.addStretch()
        composer_col.addLayout(footer)
        root.addWidget(composer)

        self._cb_mode.currentTextChanged.connect(self._emit_context_changed)
        self._cb_persona.currentTextChanged.connect(self._emit_context_changed)
        self._cb_mode.currentTextChanged.connect(self._sync_launcher_summary)
        self._cb_persona.currentTextChanged.connect(self._sync_launcher_summary)
        self._cb_profile.currentTextChanged.connect(self._sync_launcher_summary)
        self.set_persona_options([("GUPPY", "guppy")], selected="guppy")
        self._sync_launcher_summary()
        self._refresh_empty_state()
        self._sync_context_bar_visibility()

    def _sync_context_bar_visibility(self) -> None:
        visible = any(
            widget.isVisible()
            for widget in (
                self._background_event,
                self._workspace_summary,
                self._runtime_facts,
                self._route_facts,
                self._recovery_summary,
            )
        )
        self._context_bar.setVisible(visible)

    def _build_empty_state(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("empty_state")
        frame.setStyleSheet(
            f"QFrame#empty_state {{ background-color: rgba(255,250,243,0.78); border: 1px solid rgba(205,181,154,0.55); border-radius: 28px; }}"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)

        self._empty_state_title_lbl = QLabel(self._empty_state_title_text)
        self._empty_state_title_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._empty_state_title_lbl.setStyleSheet(
            f"color: {T.INK}; font-family: '{T.FF_HEAD}'; font-size: 23pt; font-weight: bold;"
        )
        layout.addWidget(self._empty_state_title_lbl)

        self._empty_state_subtitle_lbl = QLabel(self._empty_state_subtitle_text)
        self._empty_state_subtitle_lbl.setWordWrap(True)
        self._empty_state_subtitle_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._empty_state_subtitle_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_LABEL}pt;"
        )
        layout.addWidget(self._empty_state_subtitle_lbl)
        self._empty_state_recipe_lbl = QLabel(self._empty_state_recipe_text)
        self._empty_state_recipe_lbl.setWordWrap(True)
        self._empty_state_recipe_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._empty_state_recipe_lbl.setStyleSheet(
            f"color: {T.PRIMARY}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        layout.addWidget(self._empty_state_recipe_lbl)
        return frame

    def _refresh_empty_state(self) -> None:
        has_history = any(item.get("role") in {"user", "assistant"} for item in self._conversation_history)
        self._empty_state.setVisible(not has_history)

    def _refresh_empty_state_copy(self) -> None:
        title, subtitle, recipe = self._workspace_onboarding_copy(self._workspace_type)
        self._empty_state_title_text = title
        self._empty_state_subtitle_text = subtitle
        self._empty_state_recipe_text = recipe
        if hasattr(self, "_empty_state_title_lbl"):
            self._empty_state_title_lbl.setText(title)
        if hasattr(self, "_empty_state_subtitle_lbl"):
            self._empty_state_subtitle_lbl.setText(subtitle)
        if hasattr(self, "_empty_state_recipe_lbl"):
            self._empty_state_recipe_lbl.setText(recipe)

    def _add_message(self, text: str, role: str) -> None:
        row_host = QWidget()
        row = QHBoxLayout(row_host)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        if role == "system":
            pill = QLabel(text)
            pill.setWordWrap(True)
            pill.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            pill.setStyleSheet(
                f"color: {T.DIM}; background-color: {T.BG0}; border: 1px solid {T.BORDER};"
                f"border-radius: 12px; padding: 6px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
            )
            row.addStretch()
            row.addWidget(pill)
            row.addStretch()
            self._chat_layout.insertWidget(self._chat_layout.count() - 1, row_host)
            QTimer.singleShot(0, self._scroll_to_bottom)
            return

        bubble = QFrame()
        bubble.setObjectName(f"bubble_{role}")
        bubble_bg = T.PRIMARY if role == "user" else "rgba(255,255,255,0.78)"
        bubble_fg = T.BG if role == "user" else T.TEXT
        if role == "user":
            radius = "24px 24px 8px 24px"
            border = "none"
        else:
            radius = "24px 24px 24px 8px"
            border = f"1px solid rgba(205,181,154,0.38)"
        bubble.setStyleSheet(
            f"QFrame#bubble_{role} {{ background-color: {bubble_bg}; border: {border}; border-top-left-radius: 24px; border-top-right-radius: 24px; border-bottom-left-radius: { '8px' if role == 'assistant' else '24px' }; border-bottom-right-radius: { '8px' if role == 'user' else '24px' }; }}"
        )
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(16, 12, 16, 11)
        bubble_layout.setSpacing(4)

        speaker = _lbl(
            "YOU" if role == "user" else "GUPPY",
            color="rgba(255,250,243,0.88)" if role == "user" else T.PRIMARY,
            size=T.FS_TINY,
            bold=True,
        )
        bubble_layout.addWidget(speaker)

        if role == "assistant":
            body = QTextBrowser()
            body.setOpenExternalLinks(False)
            body.setReadOnly(True)
            body.setUndoRedoEnabled(False)
            body.setMarkdown(text)
            body.setFrameStyle(0)
            body.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            body.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            body.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
            body.setStyleSheet(
                f"QTextBrowser {{ background: transparent; color: {bubble_fg}; border: none;"
                f" font-family: '{T.FF_BODY}'; font-size: {T.FS_LABEL}pt; line-height: 1.4em; padding: 0; }}"
            )
            body.document().setDocumentMargin(0)
            body.document().adjustSize()
            body_height = max(36, min(260, int(body.document().size().height()) + 10))
            body.setFixedHeight(body_height)
            bubble_layout.addWidget(body)
        else:
            body = QLabel(text)
            body.setWordWrap(True)
            body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            body.setStyleSheet(
                f"color: {bubble_fg}; background: transparent; border: none;"
                f"font-family: '{T.FF_BODY}'; font-size: {T.FS_LABEL}pt; line-height: 1.4em;"
            )
            bubble_layout.addWidget(body)

        bubble.setMaximumWidth(488 if role == "assistant" else 320)
        if role == "user":
            row.addStretch()
            row.addWidget(bubble)
        else:
            row.addWidget(bubble)
            row.addStretch()
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, row_host)
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
            if nested is None:
                continue
            while nested.count():
                nested_item = nested.takeAt(0)
                if nested_item is None:
                    continue
                nested_widget = nested_item.widget()
                if nested_widget is not None:
                    nested_widget.deleteLater()

    def add_user_message(self, text: str) -> None:
        self._add_message(text, "user")
        self._conversation_history.append({"role": "user", "content": text})
        self._refresh_empty_state()

    def add_assistant_message(self, text: str) -> None:
        self._add_message(text, "assistant")
        self._conversation_history.append({"role": "assistant", "content": text})
        self._refresh_empty_state()

    def add_system_message(self, text: str) -> None:
        self._add_message(text, "system")

    def ensure_welcome_message(self) -> None:
        if any(item.get("role") in {"user", "assistant"} for item in self._conversation_history):
            return
        title, subtitle, recipe = self._workspace_onboarding_copy(self._workspace_type)
        starter = self._primary_starter_label(self._workspace_type)
        self.add_assistant_message(
            f"{title}. {subtitle} {recipe} Optional starter: {starter}."
        )

    def toggle_launcher_panel(self) -> None:
        self._launcher_panel.setVisible(not self._launcher_panel.isVisible())
        self._sync_launcher_summary()

    def _sync_launcher_summary(self, _text: str = "") -> None:
        mode = self._cb_mode.currentText().strip().upper() or "AUTO"
        persona = self._cb_persona.currentText().strip().upper() or "GUPPY"
        profile = self._cb_profile.currentText().strip().upper() or "LIGHT"
        suffix = "OPEN" if self._launcher_panel.isVisible() else "EDIT"
        self.launcher_summary_changed.emit(f"{mode} / {persona} / {profile} [{suffix}]")

    def activate_agent(self, agent: str) -> None:
        del agent
        self._cb_persona.setCurrentIndex(0)
        self._status_strip.setText("ACTIVE AGENT · GUPPY")
        self.set_background_event("Active agent switched to GUPPY")

    def _submit(self) -> None:
        if not self._input.isEnabled():
            return
        text = self._input.text().strip()
        if text:
            self.command_submitted.emit(text)
            self._input.clear()

    def set_recommendation(self, profile: str) -> None:
        self._rec_chip.setText(f"RECOMMENDED · {profile.upper()}")

    def apply_settings(self, settings: dict) -> None:
        modes = {"auto": 0, "claude": 1, "ollama": 2, "local": 3, "code": 4, "teaching": 5}
        self._cb_mode.setCurrentIndex(modes.get(settings.get("default_mode", "auto"), 0))
        profiles = {"light": 0, "standard": 1, "power": 2}
        self._cb_profile.setCurrentIndex(profiles.get(settings.get("runtime_profile", "standard"), 1))

    def selected_mode(self) -> str:
        mode = self._cb_mode.currentText().strip().lower()
        return mode or "auto"

    def selected_persona(self) -> str:
        persona = str(self._cb_persona.currentData() or self._cb_persona.currentText()).strip().lower()
        return persona or "guppy"

    def set_persona_options(self, options: list[tuple[str, str]], selected: str | None = None) -> None:
        target = str(selected or self._cb_persona.currentData() or self._cb_persona.currentText()).strip().lower()
        normalized = [
            (str(label).strip() or str(value).strip(), str(value).strip())
            for label, value in options
            if str(value).strip()
        ]
        if not normalized:
            normalized = [("GUPPY", "guppy")]
        self._cb_persona.blockSignals(True)
        self._cb_persona.clear()
        for label, value in normalized:
            self._cb_persona.addItem(label, value)
        target_index = 0
        for idx in range(self._cb_persona.count()):
            if str(self._cb_persona.itemData(idx) or "").strip().lower() == target:
                target_index = idx
                break
        self._cb_persona.setCurrentIndex(target_index)
        self._cb_persona.blockSignals(False)

    def set_route_preview(
        self,
        *,
        task_type: str = "unknown",
        route: str = "pending",
        model: str = "",
        backup_model: str = "",
        reason: str = "",
        evidence: str = "",
    ) -> None:
        reason_text = (reason or "").strip()
        evidence_text = (evidence or "").strip()
        route_bits: list[str] = []
        if str(task_type or "").strip():
            route_bits.append(f"{str(task_type).strip().capitalize()} task")
        if str(route or "").strip():
            route_bits.append(f"via {str(route).strip().upper()}")
        if model:
            route_bits.append(f"using {str(model).strip().upper()}")
        if backup_model:
            route_bits.append(f"backup {str(backup_model).strip().upper()}")
        summary = ", ".join(route_bits) if route_bits else "waiting for your next message"
        details: list[str] = []
        if reason_text:
            details.append(f"Why: {reason_text}")
        if evidence_text:
            details.append(f"Evidence: {evidence_text}")
        self._route_facts.setText(f"Next reply: {summary}." + (f" {' '.join(details)}" if details else ""))
        self._route_facts.setVisible(True)

    def set_input_text(self, text: str) -> None:
        self._input.setText(text)
        self._input.setFocus()

    def _starter_templates(self) -> list[tuple[str, str, str, str]]:
        key = (self._workspace_type or "user_instance").strip().lower()
        templates = {
            "user_instance": [
                (
                    "morning_brief",
                    "MORNING BRIEF",
                    "auto",
                    "Give me a morning brief for this workspace: priorities, blockers, and the best first move.",
                ),
                (
                    "focused_research",
                    "FOCUSED RESEARCH",
                    "claude",
                    "Research this topic for the active workspace and return a concise brief with recommendations: ",
                ),
                (
                    "file_triage",
                    "FILE TRIAGE",
                    "local",
                    "Help me triage files for this workspace. Start by asking which folder or files I want reviewed.",
                ),
                (
                    "builder_review",
                    "BUILDER REVIEW",
                    "code",
                    "Review the current builder work for this workspace with bugs, regressions, and missing tests first.",
                ),
            ],
            "builder_instance": [
                (
                    "morning_brief",
                    "PLAN NEXT PASS",
                    "code",
                    "Plan the next builder pass for this workspace: goals, review targets, and the safest high-value next move.",
                ),
                (
                    "focused_research",
                    "DESIGN RESEARCH",
                    "claude",
                    "Research this implementation question for the builder workspace and return tradeoffs, risks, and a recommended plan: ",
                ),
                (
                    "file_triage",
                    "PATCH TRIAGE",
                    "local",
                    "Help me triage changed files for this builder workspace. Start by asking which files or modules need review.",
                ),
                (
                    "builder_review",
                    "BUILDER REVIEW",
                    "code",
                    "Review the current builder work for this workspace with bugs, regressions, and missing tests first.",
                ),
            ],
            "read_only_instance": [
                (
                    "morning_brief",
                    "REFERENCE SNAPSHOT",
                    "auto",
                    "Summarize the key reference context for this workspace: what matters now, what changed, and what to inspect next.",
                ),
                (
                    "focused_research",
                    "SOURCE RESEARCH",
                    "claude",
                    "Research this topic for the reference workspace and return a concise evidence-first brief: ",
                ),
                (
                    "file_triage",
                    "SOURCE TRIAGE",
                    "local",
                    "Help me inspect files for this read-only workspace. Start by asking which folder or files I want compared or reviewed.",
                ),
                (
                    "builder_review",
                    "REFERENCE REVIEW",
                    "code",
                    "Review this source or diff for the reference workspace and call out risks, gaps, and evidence without proposing writes first.",
                ),
            ],
            "admin_instance": [
                (
                    "morning_brief",
                    "OPS CHECK",
                    "auto",
                    "Give me an operations check for this workspace: current health, likely blockers, and the safest first operator step.",
                ),
                (
                    "focused_research",
                    "INCIDENT RESEARCH",
                    "claude",
                    "Research this operational issue for the active workspace and return a concise diagnosis brief with likely follow-ups: ",
                ),
                (
                    "file_triage",
                    "EVIDENCE TRIAGE",
                    "local",
                    "Help me triage logs or artifacts for this operations workspace. Start by asking which files or folders need inspection.",
                ),
                (
                    "builder_review",
                    "RECOVERY REVIEW",
                    "code",
                    "Review the current recovery or servicing work for this workspace with failure points, regressions, and missing validation first.",
                ),
            ],
        }
        return templates.get(key, templates["user_instance"])

    def _refresh_starter_buttons(self) -> None:
        self._starter_meta = {}
        for index, (starter_id, title, mode, prompt) in enumerate(self._starter_templates()):
            self._starter_meta[starter_id] = (title, mode, prompt)
            button = self._starter_buttons.get(starter_id)
            if button is None:
                continue
            button.setText(title)
            button.setToolTip(prompt)
            button.setStyleSheet(self._starter_button_style(primary=index == 0))

    def _load_starter_by_id(self, starter_id: str) -> None:
        title, mode, prompt = self._starter_meta.get(starter_id, ("STARTER", "auto", ""))
        self._load_starter(starter_id, title, mode, prompt)

    def _load_starter(self, starter_id: str, label: str, mode: str, prompt: str) -> None:
        self.set_input_text(prompt)
        self.set_chat_context(mode, self.selected_persona())
        self.set_background_event(f"Starter loaded: {label}. Edit the draft if needed, then press send.")
        self._starter_summary.setText(f"{label} is ready if you want a head start. Edit it in the composer, then send.")
        self.set_status("STARTER READY")
        self.starter_requested.emit(starter_id, prompt)

    def set_status(self, text: str) -> None:
        status = (text or "Ready").strip().upper()
        self._status_strip.setText(status)
        color = T.PRIMARY
        if "ERROR" in status:
            color = T.ERROR
        elif "READY" in status:
            color = T.GREEN
        self._status_strip.setStyleSheet(
            f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 2px;"
        )

    def set_active_instance(
        self,
        instance: str,
        *,
        workspace_type: str = "user_instance",
        description: str = "",
        mode: str = "auto",
        persona: str = "guppy",
        voice: str = "default",
        last_message: str = "",
    ) -> None:
        name = (instance or "guppy-primary").strip() or "guppy-primary"
        role = self._workspace_role_label(workspace_type)
        purpose = (description or self._workspace_default_purpose(workspace_type)).strip()
        self._workspace_type = (workspace_type or "user_instance").strip().lower() or "user_instance"
        self._workspace_role = role
        self._workspace_purpose = purpose
        self._refresh_empty_state_copy()
        self._refresh_starter_buttons()
        self._starter_summary.setText(self._starter_summary_copy(self._workspace_type))
        self._input.setPlaceholderText(self._workspace_input_placeholder(self._workspace_type))
        mode_label = (mode or "auto").strip().upper() or "AUTO"
        persona_label = (persona or "guppy").strip().upper() or "GUPPY"
        voice_label = (voice or "default").strip().upper() or "DEFAULT"
        recent_text = self._workspace_recent_context(last_message)
        self._instance_chip.setText(f"WORKSPACE · {name.upper()}")
        self._workspace_summary.setText(
            f"Active workspace: {role}. {purpose} "
            f"Saved context: {mode_label} mode | {persona_label} persona | {voice_label} voice. "
            f"{recent_text}"
        )
        self._workspace_summary.setVisible(True)
        self._entry_hint.setText(f"Start here in {name}: {self._workspace_entry_hint(workspace_type)}")
        self._sync_context_bar_visibility()

    def set_background_status(self, text: str, healthy: bool = True) -> None:
        msg = (text or "ready").strip() or "ready"
        color = T.GREEN if healthy else T.ERROR
        background = "rgba(90,196,122,0.08)" if healthy else "rgba(226,92,92,0.08)"
        border = "rgba(90,196,122,0.24)" if healthy else "rgba(226,92,92,0.24)"
        self._background_chip.setText(msg.upper())
        self._background_chip.setStyleSheet(
            f"color: {color}; background-color: {background}; border: 1px solid {border};"
            f"border-radius: 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px; padding: 4px 8px;"
        )

    def set_background_event(self, text: str) -> None:
        msg = (text or "launcher ready").strip() or "launcher ready"
        self._background_event.setText(f"Latest activity: {msg}")
        self._background_event.setVisible(True)
        self._hero_subtitle.setText(msg)
        self._sync_context_bar_visibility()

    def set_runtime_facts(
        self,
        *,
        profile: str = "standard",
        model: str = "guppy",
        voice: str = "edge",
        latency: str = "-",
        last_query: str = "-",
    ) -> None:
        query = (last_query or "-").strip() or "-"
        query = query[:96] + "..." if len(query) > 96 else query
        details = [
            f"{str(profile).capitalize()} profile",
            f"{str(model).upper()} model",
            f"{str(voice).strip() or 'edge'} voice",
        ]
        if str(latency).strip() and str(latency).strip() not in {"-", "—"}:
            details.append(f"{latency} ms latency")
        if query not in {"-", "—"}:
            details.append(f"last request: {query}")
        self._runtime_facts.setText("Ready now: " + ", ".join(details) + ".")
        self._runtime_facts.setVisible(True)
        self._sync_context_bar_visibility()

    def set_recovery_summary(self, text: str, healthy: bool = True) -> None:
        summary = (text or "stable").strip() or "stable"
        color = T.GREEN if healthy else T.ERROR
        prefix = "System health" if healthy else "Needs attention"
        self._recovery_summary.setText(f"{prefix}: {summary}")
        self._recovery_summary.setVisible(True)
        self._entry_hint.setStyleSheet(
            f"color: {T.PRIMARY if healthy else T.ERROR}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        self._recovery_summary.setStyleSheet(
            f"color: {color}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        self._sync_context_bar_visibility()

    def set_request_in_flight(self, in_flight: bool) -> None:
        self._request_in_flight_ui = in_flight
        self._input.setEnabled(not in_flight)
        self._send_btn.setEnabled(not in_flight)
        self._cancel_btn.setEnabled(in_flight)
        self._mic_btn.setEnabled(self._mic_capture_active or not in_flight)

    def set_mic_capture_state(self, listening: bool) -> None:
        self._mic_capture_active = listening
        if listening:
            self._mic_btn.setText("\u25c9")
            self._mic_btn.setToolTip("Listening now. Click to stop capture.")
            self._status_strip.setText("LISTENING")
            self._mic_btn.setEnabled(True)
            return
        self._mic_btn.setText("\u25cf")
        self._mic_btn.setToolTip("Push to talk. Click again while listening to stop capture.")
        self._mic_btn.setEnabled(not self._request_in_flight_ui)

    def set_session_id(self, session_id: str) -> None:
        sid = (session_id or "").strip()
        suffix = sid[-8:] if sid else "--"
        self._session_strip.setText(f"SESSION: {suffix}")

    def reset_live_history(self) -> None:
        self._conversation_history.clear()
        self._refresh_empty_state()

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
        self._refresh_empty_state()

    def recent_history(self, limit: int = 12) -> list[dict[str, str]]:
        if limit <= 0:
            return []
        trimmed = self._conversation_history[-max(0, limit):]
        return [dict(item) for item in trimmed if item.get("role") in {"user", "assistant"}]

    def set_chat_context(self, mode: str, persona: str) -> None:
        mode_key = (mode or "").strip().lower()
        persona_key = (persona or "").strip().lower()

        for idx in range(self._cb_mode.count()):
            if self._cb_mode.itemText(idx).strip().lower() == mode_key:
                self._cb_mode.setCurrentIndex(idx)
                break

        for idx in range(self._cb_persona.count()):
            option_key = str(self._cb_persona.itemData(idx) or self._cb_persona.itemText(idx)).strip().lower()
            if option_key == persona_key:
                self._cb_persona.setCurrentIndex(idx)
                break

    def chat_context(self) -> tuple[str, str]:
        return self.selected_mode(), self.selected_persona()

    def _emit_context_changed(self, _text: str) -> None:
        self.chat_context_changed.emit(self.selected_mode(), self.selected_persona())

    @staticmethod
    def _workspace_role_label(workspace_type: str) -> str:
        key = (workspace_type or "user_instance").strip().lower()
        return {
            "user_instance": "Daily assistant workspace",
            "builder_instance": "Builder collaborator workspace",
            "read_only_instance": "Read-only reference workspace",
            "admin_instance": "Operations workspace",
        }.get(key, key.replace("_", " ").strip().capitalize() or "Workspace")

    @staticmethod
    def _workspace_default_purpose(workspace_type: str) -> str:
        key = (workspace_type or "user_instance").strip().lower()
        return {
            "user_instance": "General help, recurring work, and quick tasks.",
            "builder_instance": "Planning, review, and low-risk builder collaboration.",
            "read_only_instance": "Safe research, source review, and reference work without writes.",
            "admin_instance": "Recovery, diagnostics, and guarded changes.",
        }.get(key, "Task-focused context for this workspace.")

    @staticmethod
    def _workspace_entry_hint(workspace_type: str) -> str:
        key = (workspace_type or "user_instance").strip().lower()
        return {
            "user_instance": "type one short request and press Send.",
            "builder_instance": "start with PLAN NEXT PASS if you want a draft first.",
            "read_only_instance": "start with SOURCE RESEARCH if you want evidence first.",
            "admin_instance": "start with a short status check if you want a quick read first.",
        }.get(key, "type one short request and press Send.")

    @staticmethod
    def _workspace_first_run_recipe(workspace_type: str) -> str:
        key = (workspace_type or "user_instance").strip().lower()
        return {
            "user_instance": "First run: type one short request, then use MORNING BRIEF only if you want a head start.",
            "builder_instance": "First run: ask for the next pass, or load PLAN NEXT PASS if you want a draft first.",
            "read_only_instance": "First run: ask one evidence question, or load SOURCE RESEARCH if you want a starting brief.",
            "admin_instance": "First run: ask for a short status check, or load OPS CHECK if you want a quick read first.",
        }.get(key, "First run: type one short request, then use a starter only if you want a head start.")

    @staticmethod
    def _starter_summary_copy(workspace_type: str) -> str:
        key = (workspace_type or "user_instance").strip().lower()
        return {
            "user_instance": "Optional starter if you want one: MORNING BRIEF.",
            "builder_instance": "Optional starter if you want a draft: PLAN NEXT PASS.",
            "read_only_instance": "Optional starter if you want evidence first: SOURCE RESEARCH.",
            "admin_instance": "Optional starter if you want a quick read: OPS CHECK.",
        }.get(key, "Optional starters are here if you want a head start.")

    @staticmethod
    def _workspace_onboarding_copy(workspace_type: str) -> tuple[str, str, str]:
        key = (workspace_type or "user_instance").strip().lower()
        mapping = {
            "user_instance": (
                "Start here",
                "Use the composer for the next thing you want to move forward. Starters are optional.",
                "Next step: ask one clear question and press Send.",
            ),
            "builder_instance": (
                "Builder workspace ready",
                "Use the composer for the next pass you want help with. Starters are optional.",
                "Next step: ask for the next pass or load PLAN NEXT PASS.",
            ),
            "read_only_instance": (
                "Reference workspace ready",
                "Use the composer for one evidence question or source check. Starters are optional.",
                "Next step: ask for evidence first or load SOURCE RESEARCH.",
            ),
            "admin_instance": (
                "Operations workspace ready",
                "Keep the first ask small and clear. Starters are optional.",
                "Next step: ask for a short status check or load OPS CHECK.",
            ),
        }
        return mapping.get(key, mapping["user_instance"])

    @staticmethod
    def _primary_starter_label(workspace_type: str) -> str:
        key = (workspace_type or "user_instance").strip().lower()
        return {
            "user_instance": "MORNING BRIEF",
            "builder_instance": "PLAN NEXT PASS",
            "read_only_instance": "SOURCE RESEARCH",
            "admin_instance": "OPS CHECK",
        }.get(key, "MORNING BRIEF")

    @staticmethod
    def _workspace_input_placeholder(workspace_type: str) -> str:
        key = (workspace_type or "user_instance").strip().lower()
        return {
            "user_instance": "Ask for the next thing you want to move forward...",
            "builder_instance": "Ask for the next pass, review, or draft you need...",
            "read_only_instance": "Ask one evidence or source-check question...",
            "admin_instance": "Ask for a short status check or the safest next step...",
        }.get(key, "Type one request for this workspace...")

    @staticmethod
    def _workspace_recent_context(last_message: str) -> str:
        snippet = str(last_message or "").strip()
        if not snippet:
            return "Recent context: no recent thread is pinned yet."
        snippet = snippet[:120] + ("..." if len(snippet) > 120 else "")
        return f"Recent context: {snippet}"

    @staticmethod
    def _starter_button_style(primary: bool = False) -> str:
        border = T.PRIMARY if primary else T.BORDER
        color = T.PRIMARY if primary else T.TEXT
        background = "rgba(242,202,80,0.10)" if primary else T.BG0
        return (
            f"QPushButton {{ background: {background}; color: {color}; border: 1px solid {border};"
            f" border-radius: 11px; padding: 5px 9px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: {T.PRIMARY}; color: {T.PRIMARY}; background: rgba(242,202,80,0.12); }}"
        )
