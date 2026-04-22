"""
ui/launcher/views/assistant_view.py
Home chat surface with a calmer, messenger-style launcher layout.
"""
from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QResizeEvent, QShowEvent
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

from src.guppy.launcher_application.home_presenter import (
    build_home_workspace_copy,
    build_home_starter_state,
    build_home_welcome_message,
    build_home_workspace_state,
    home_workspace_starter_templates,
)
from src.guppy.inference.router import LAUNCHER_MODES_DISPLAY
from .. import tokens as T
from . import assistant_behavior_support as behavior
from .assistant_first_run_banner import FirstRunBanner
from .assistant_context import (
    active_context_titles as context_active_context_titles,
    context_aware_starter_prompt as context_context_aware_starter_prompt,
    context_aware_starter_title as context_context_aware_starter_title,
    refresh_resource_context as context_refresh_resource_context,
    set_background_event as context_set_background_event,
    set_background_status as context_set_background_status,
    set_recovery_summary as context_set_recovery_summary,
    set_route_preview as context_set_route_preview,
    set_runtime_facts as context_set_runtime_facts,
    sync_context_bar_visibility as context_sync_context_bar_visibility,
    toggle_context_details as context_toggle_context_details,
)
from .assistant_shell_sections import build_assistant_shell
from .assistant_transcript import build_transcript_row, clear_transcript_layout


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


def _hero_subtitle_for_workspace(workspace_type: str) -> str:
    key = str(workspace_type or "").strip().lower()
    return {
        "builder_instance": "Plan, review, or build here. Starters are optional.",
        "read_only_instance": "Inspect files, notes, and saved context here. Starters are optional.",
        "admin_instance": "Use this workspace for setup and recovery. Starters are optional.",
    }.get(key, "Start with the next clear ask. Starters are optional.")


class AssistantView(QWidget):
    command_submitted = Signal(str)
    cancel_requested = Signal()
    mic_requested = Signal()
    starter_requested = Signal(str, str)
    settings_changed = Signal(dict)
    chat_context_changed = Signal(str, str)
    launcher_summary_changed = Signal(str)
    active_context_clear_requested = Signal()
    active_context_remove_requested = Signal(str)
    active_context_focus_requested = Signal(str)
    active_context_default_requested = Signal(str)
    active_context_library_requested = Signal(str)
    active_context_refresh_requested = Signal(str, bool)
    assistant_reply_library_requested = Signal(str, bool)
    assistant_reply_artifact_requested = Signal(str)
    latest_saved_output_attach_requested = Signal(str, str)
    latest_saved_output_library_requested = Signal(str)
    first_run_action_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        initial_copy = build_home_workspace_copy("user_instance")
        self._request_in_flight_ui = False
        self._mic_capture_active = False
        self._workspace_name = "guppy-primary"
        self._workspace_type = "user_instance"
        self._workspace_role = initial_copy.role_label
        self._workspace_purpose = initial_copy.purpose
        self._starter_buttons: dict[str, QPushButton] = {}
        self._conversation_history: list[dict[str, str]] = []
        self._active_context_items: list[dict[str, str]] = []
        self._empty_state_title_text = initial_copy.onboarding_title
        self._empty_state_subtitle_text = initial_copy.onboarding_subtitle
        self._empty_state_recipe_text = initial_copy.onboarding_recipe
        self._base_empty_state_title = initial_copy.onboarding_title
        self._base_empty_state_subtitle = initial_copy.onboarding_subtitle
        self._base_empty_state_recipe = initial_copy.onboarding_recipe
        self._base_starter_summary = initial_copy.starter_summary
        self._base_input_placeholder = initial_copy.input_placeholder
        self._latest_saved_output: dict[str, str] = {}
        self._latest_assistant_reply_text = ""
        self._swap_source_target_title = ""
        self._workspace_details_expanded = False
        self._starters_expanded = False
        # Home stays visually chat-first. Compatibility setters remain, but
        # operator detail surfaces are hidden until those state contracts move.
        self._home_operator_details_enabled = False
        self._home_workspace_details_enabled = False
        self._launcher_context_controls_enabled = False
        self._first_run_banner_visible = False

        build_assistant_shell(
            self,
            label_factory=_lbl,
            dropdown_factory=_dropdown,
            hero_subtitle_for_workspace=_hero_subtitle_for_workspace,
        )

    def _sync_context_bar_visibility(self) -> None:
        context_sync_context_bar_visibility(self)

    def _toggle_context_details(self) -> None:
        context_toggle_context_details(self)

    def _toggle_workspace_details(self) -> None:
        if not self._home_workspace_details_enabled:
            self._workspace_details_expanded = False
            self._update_workspace_details_visibility()
            return
        self._workspace_details_expanded = not self._workspace_details_expanded
        self._update_workspace_details_visibility()

    def _toggle_starters(self) -> None:
        self._starters_expanded = not self._starters_expanded
        self._update_starter_visibility()

    def _update_workspace_details_visibility(self) -> None:
        if not self._home_workspace_details_enabled:
            self._workspace_details_summary.setText("")
            self._workspace_details_btn.setText("DETAILS")
            self._identity_details_btn.setText("DETAILS")
            self._identity_details_btn.setVisible(False)
            self._workspace_details_strip.setVisible(False)
            self._workspace_details_host.setVisible(False)
            return
        has_saved_output = bool(self._latest_saved_output)
        has_sources = bool(self._active_context_items)
        summary = "Files and saved context are tucked away here."
        if has_sources and has_saved_output:
            summary = "Attached sources and saved output are available here."
        elif has_sources:
            summary = "Attached sources are available here."
        elif has_saved_output:
            summary = "Saved output is available here."
        self._workspace_details_summary.setText(summary)
        self._workspace_details_btn.setText("HIDE DETAILS" if self._workspace_details_expanded else "DETAILS")
        self._identity_details_btn.setText("HIDE DETAILS" if self._workspace_details_expanded else "DETAILS")
        self._workspace_details_host.setVisible(self._workspace_details_expanded)

    def _update_starter_visibility(self) -> None:
        buttons_visible = self._starters_expanded and self.width() >= 920
        has_context = bool(self._active_context_items)
        has_draft = hasattr(self, "_input") and bool(self._input.text().strip())
        self._starter_buttons_host.setVisible(buttons_visible)
        self._starter_summary.setVisible(self.width() >= 920 and (buttons_visible or has_context or has_draft))
        self._starters_btn.setText("HIDE PROMPTS" if self._starters_expanded else "PROMPTS")

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
            f"color: {T.INK}; font-family: '{T.FF_HEAD}'; font-size: 25pt; font-weight: 700;"
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
            f"color: {T.ACCENT_TEAL}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        layout.addWidget(self._empty_state_recipe_lbl)
        return frame

    def _refresh_empty_state(self) -> None:
        has_history = any(item.get("role") in {"user", "assistant"} for item in self._conversation_history)
        self._empty_state.setVisible(not has_history)

    def _refresh_empty_state_copy(self) -> None:
        state = build_home_workspace_state(
            self._workspace_name,
            workspace_type=self._workspace_type,
            description=self._workspace_purpose,
            mode=self.selected_mode(),
            persona=self.selected_persona(),
            voice="default",
            last_message="",
        )
        self._base_empty_state_title = state.onboarding_title
        self._base_empty_state_subtitle = state.onboarding_subtitle
        self._base_empty_state_recipe = state.onboarding_recipe
        self._refresh_empty_state_guidance()

    def _refresh_empty_state_guidance(self) -> None:
        title = self._base_empty_state_title
        subtitle = self._base_empty_state_subtitle
        recipe = self._base_empty_state_recipe
        titles = self._active_context_titles()
        if titles:
            joined = ", ".join(titles)
            subtitle = f"{subtitle} Library sources are already attached: {joined}."
            recipe = f"{recipe} Or ask the next thing using these attached sources: {joined}."
        self._empty_state_title_text = title
        self._empty_state_subtitle_text = subtitle
        self._empty_state_recipe_text = recipe
        if hasattr(self, "_empty_state_title_lbl"):
            self._empty_state_title_lbl.setText(title)
        if hasattr(self, "_empty_state_subtitle_lbl"):
            self._empty_state_subtitle_lbl.setText(subtitle)
        if hasattr(self, "_empty_state_recipe_lbl"):
            self._empty_state_recipe_lbl.setText(recipe)

    def _refresh_resource_context(self) -> None:
        context_refresh_resource_context(self)

    def _add_message(self, text: str, role: str) -> None:
        row_host = build_transcript_row(
            text,
            role,
            on_reply_library=self.assistant_reply_library_requested.emit,
            on_reply_artifact=self.assistant_reply_artifact_requested.emit,
        )
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, row_host)
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        bar = self._chat_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _clear_transcript_widgets(self) -> None:
        clear_transcript_layout(self._chat_layout)

    def add_user_message(self, text: str) -> None:
        self._add_message(text, "user")
        self._conversation_history.append({"role": "user", "content": text})
        self._refresh_resource_context()
        self._refresh_empty_state()

    def add_assistant_message(self, text: str) -> None:
        self._add_message(text, "assistant")
        self._conversation_history.append({"role": "assistant", "content": text})
        self._latest_assistant_reply_text = str(text or "").strip()
        self._refresh_resource_context()
        self._refresh_empty_state()

    def add_system_message(self, text: str) -> None:
        self._add_message(text, "system")
        self._conversation_history.append({"role": "system", "content": text})

    def ensure_welcome_message(self) -> None:
        if any(item.get("role") in {"user", "assistant"} for item in self._conversation_history):
            return
        self.add_assistant_message(
            build_home_welcome_message(
                self._workspace_type,
                description=self._workspace_purpose,
            )
        )

    def toggle_launcher_panel(self) -> None:
        if not self._launcher_context_controls_enabled:
            self._launcher_panel.setVisible(False)
            return
        self._launcher_panel.setVisible(not self._launcher_panel.isVisible())
        self._sync_launcher_summary()

    def _sync_launcher_summary(self, _text: str = "") -> None:
        mode = self._cb_mode.currentText().strip().upper() or "AUTO"
        persona = self._cb_persona.currentText().strip().upper() or "GUPPY"
        profile = self._cb_profile.currentText().strip().upper() or "LIGHT"
        suffix = "OPEN" if self._launcher_panel.isVisible() else "EDIT"
        self._identity_mode_chip.setText(f"{mode} / {profile}")
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
        context_set_route_preview(
            self,
            task_type=task_type,
            route=route,
            model=model,
            backup_model=backup_model,
            reason=reason,
            evidence=evidence,
        )

    def set_input_text(self, text: str) -> None:
        self._input.setText(text)
        self._input.setFocus()

    def _starter_templates(self) -> list[tuple[str, str, str, str]]:
        return [
            (item.starter_id, item.title, item.mode, item.prompt)
            for item in home_workspace_starter_templates(self._workspace_type)
        ]

    def _active_context_titles(self, limit: int = 2) -> list[str]:
        return context_active_context_titles(self._active_context_items, limit)

    def _context_aware_starter_title(self, starter_id: str, title: str) -> str:
        return context_context_aware_starter_title(self._active_context_items, starter_id, title)

    def _context_aware_starter_prompt(self, prompt: str) -> str:
        return context_context_aware_starter_prompt(self._active_context_items, prompt)

    def _refresh_starter_buttons(self) -> None:
        for index, (starter_id, title, mode, prompt) in enumerate(self._starter_templates()):
            button = self._starter_buttons.get(starter_id)
            if button is None:
                continue
            button.setText(self._context_aware_starter_title(starter_id, title))
            button.setToolTip(self._context_aware_starter_prompt(prompt))
            button.setStyleSheet(self._starter_button_style(primary=index == 0))

    def _load_starter_by_id(self, starter_id: str) -> None:
        starter = build_home_starter_state(self._workspace_type, starter_id)
        titles = self._active_context_titles()
        if titles:
            starter = type(starter)(
                starter_id=starter.starter_id,
                label=self._context_aware_starter_title(starter.starter_id, starter.label),
                mode=starter.mode,
                prompt=self._context_aware_starter_prompt(starter.prompt),
                background_event=f"{starter.background_event} Attached sources ready: {', '.join(titles)}.",
                starter_summary=f"{starter.starter_summary} Attached sources: {', '.join(titles)}.",
                status=starter.status,
            )
        self._load_starter(starter)

    def _load_starter(self, starter) -> None:
        self.set_input_text(starter.prompt)
        self.set_chat_context(starter.mode, self.selected_persona())
        self.set_background_event(starter.background_event)
        self._base_starter_summary = starter.starter_summary
        self._refresh_composer_guidance()
        self.set_status(starter.status)
        self._starters_expanded = False
        self._update_starter_visibility()
        self.starter_requested.emit(starter.starter_id, starter.prompt)

    def set_status(self, text: str) -> None:
        behavior.set_status(self, text)

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
        behavior.set_active_instance(
            self,
            instance,
            workspace_type=workspace_type,
            description=description,
            mode=mode,
            persona=persona,
            voice=voice,
            last_message=last_message,
        )

    def set_background_status(self, text: str, healthy: bool = True) -> None:
        context_set_background_status(self, text, healthy=healthy)

    def set_background_event(self, text: str) -> None:
        context_set_background_event(self, text)

    def set_runtime_facts(
        self,
        *,
        profile: str = "standard",
        model: str = "guppy",
        voice: str = "edge",
        latency: str = "-",
        last_query: str = "-",
    ) -> None:
        context_set_runtime_facts(
            self,
            profile=profile,
            model=model,
            voice=voice,
            latency=latency,
            last_query=last_query,
        )

    def set_recovery_summary(self, text: str, healthy: bool = True) -> None:
        context_set_recovery_summary(self, text, healthy=healthy)

    def set_request_in_flight(self, in_flight: bool) -> None:
        behavior.set_request_in_flight(self, in_flight)

    def set_mic_capture_state(self, listening: bool) -> None:
        behavior.set_mic_capture_state(self, listening)

    def set_session_id(self, session_id: str) -> None:
        behavior.set_session_id(self, session_id)

    def reset_live_history(self) -> None:
        self._conversation_history.clear()
        self._latest_assistant_reply_text = ""
        self._refresh_empty_state()

    def clear_transcript(self) -> None:
        self._clear_transcript_widgets()
        self.reset_live_history()

    def restore_history(self, history: list[dict[str, str]]) -> None:
        behavior.restore_history(self, history)

    def recent_history(self, limit: int = 12) -> list[dict[str, str]]:
        if limit <= 0:
            return []
        trimmed = self._conversation_history[-max(0, limit):]
        return [dict(item) for item in trimmed if item.get("role") in {"user", "assistant"}]

    def set_chat_context(self, mode: str, persona: str) -> None:
        behavior.set_chat_context(self, mode, persona)

    def chat_context(self) -> tuple[str, str]:
        return self.selected_mode(), self.selected_persona()

    def set_resource_context(self, *, files: str, study: str, coding: str) -> None:
        behavior.set_resource_context(self, files=files, study=study, coding=coding)

    def set_latest_saved_output(self, *, title: str, summary: str, source_label: str = "Saved reply artifact") -> None:
        behavior.set_latest_saved_output(self, title=title, summary=summary, source_label=source_label)

    def clear_latest_saved_output(self) -> None:
        behavior.clear_latest_saved_output(self)

    def _emit_latest_saved_output_attach(self) -> None:
        behavior.emit_latest_saved_output_attach(self)

    def _emit_latest_saved_output_library(self) -> None:
        behavior.emit_latest_saved_output_library(self)

    def set_active_context_items(self, items: list[dict[str, str]]) -> None:
        behavior.set_active_context_items(self, items)

    def _toggle_active_context_preview(self, title: str) -> None:
        behavior.toggle_active_context_preview(self, title)

    def _emit_active_context_refresh_requested(self) -> None:
        behavior.emit_active_context_refresh_requested(self)

    def _emit_active_context_swap_requested(self) -> None:
        behavior.emit_active_context_swap_requested(self)

    def _emit_active_context_default_requested(self) -> None:
        behavior.emit_active_context_default_requested(self)

    def set_default_context_source(self, title: str) -> None:
        behavior.set_default_context_source(self, title)

    def note_active_context_submission(self, text: str) -> None:
        behavior.note_active_context_submission(self, text)

    def _refresh_grounding_cue(self) -> None:
        behavior.refresh_grounding_cue(self)

    def _refresh_composer_guidance(self) -> None:
        behavior.refresh_composer_guidance(self)

    def _focus_input_for_first_run(self) -> None:
        self._input.setFocus(Qt.FocusReason.OtherFocusReason)

    def set_first_run_status(
        self,
        *,
        visible: bool,
        summary: str = "",
        detail: str = "",
        install_status: str = "pending",
        model_status: str = "pending",
        request_status: str = "pending",
    ) -> None:
        behavior.set_first_run_status(
            self,
            visible=visible,
            summary=summary,
            detail=detail,
            install_status=install_status,
            model_status=model_status,
            request_status=request_status,
        )

    def showEvent(self, event: QShowEvent) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._apply_density_mode(self.width())

    def resizeEvent(self, event: QResizeEvent) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._apply_density_mode(event.size().width())

    def _apply_density_mode(self, width: int) -> None:
        behavior.apply_density_mode(self, width)

    def _emit_context_changed(self, _text: str) -> None:
        self.chat_context_changed.emit(self.selected_mode(), self.selected_persona())

    @staticmethod
    def _hero_subtitle_for_workspace(workspace_type: str) -> str:
        return _hero_subtitle_for_workspace(workspace_type)

    @staticmethod
    def _starter_button_style(primary: bool = False) -> str:
        border = T.ACCENT_ORANGE if primary else T.BORDER
        color = T.ACCENT_ORANGE if primary else T.TEXT
        background = "rgba(255,109,0,0.10)" if primary else T.BG0
        return (
            f"QPushButton {{ background: {background}; color: {color}; border: 1px solid {border};"
            f" border-radius: 13px; padding: 6px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: {T.TERTIARY}; color: {T.INK}; background: rgba(70,98,199,0.08); }}"
        )
