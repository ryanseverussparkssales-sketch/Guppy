"""
ui/launcher/views/settings_view.py
Runtime settings plus assistant/persona configuration for the unified launcher.
"""
from __future__ import annotations

import time
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.guppy.experience_config import (
    apply_runtime_settings_to_env as apply_settings_to_env,
    load_runtime_settings as load_app_settings,
    personalization_backend_available,
    recommend_runtime_profile,
    runtime_settings_backend_available,
    save_persona_config,
    save_runtime_settings as save_app_settings,
    validate_persona_config,
)
from src.guppy.experience_config.personalization_defaults import DEFAULT_ASSISTANT_NAME, DEFAULT_PERSONA_CONFIG
from src.guppy.inference.router import LAUNCHER_MODES_DISPLAY
from .. import tokens as T
from .settings_view_persona_logic import (
    _PERSONALIZATION_BACKEND,
    build_persona_config as _build_persona_config_fn,
    create_persona,
    deepcopy_json,
    delete_persona,
    load_model_binding_options,
    load_persona_settings,
    next_persona_id,
    on_persona_selected,
    on_scope_changed,
    persona_items,
    populate_persona_form,
    refresh_assignment_summary,
    refresh_persona_lists,
    refresh_preview,
    selected_persona,
    set_persona_controls_enabled,
)
from .settings_view_sections import (
    _MODEL_BINDING_OPTIONS,
    build_settings_persona_frame,
    build_settings_runtime_frame,
)

_PROFILE_BACKEND = runtime_settings_backend_available()


class SettingsView(QWidget):
    settings_saved = Signal(dict)
    recovery_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._persona_config = deepcopy_json(DEFAULT_PERSONA_CONFIG)
        self._current_persona_id = "main_guppy"
        self._loading_persona = False
        self._settings_section = "runtime"
        self._section_buttons: dict[str, QPushButton] = {}
        self._embedded_mode = False
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QLabel("Settings")
        title.setStyleSheet(f"color: {T.TEXT}; font-family: '{T.FF_HEAD}'; font-size: 26pt; font-weight: 900;")
        self._title_lbl = title
        layout.addWidget(title)
        subtitle = QLabel("Runtime defaults plus assistant naming and persona behavior for launcher-local use.")
        subtitle.setWordWrap(True)
        self._subtitle_lbl = subtitle
        layout.addWidget(subtitle)

        section_row = QHBoxLayout()
        section_row.setSpacing(8)
        for key, label in (("runtime", "RUNTIME"), ("personas", "PERSONAS"), ("advanced", "ADVANCED")):
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, section=key: self._set_settings_section(section))
            self._section_buttons[key] = btn
            section_row.addWidget(btn)
        section_row.addStretch()
        self._section_row = section_row
        self._section_row_host = QWidget()
        self._section_row_host.setLayout(section_row)
        layout.addWidget(self._section_row_host)

        self._runtime_frame = build_settings_runtime_frame(
            self, launcher_modes=list(LAUNCHER_MODES_DISPLAY)
        )
        layout.addWidget(self._runtime_frame)

        self._persona_frame = build_settings_persona_frame(self)
        layout.addWidget(self._persona_frame)

        self._advanced_frame = QFrame()
        advanced_layout = QVBoxLayout(self._advanced_frame)
        advanced_layout.setContentsMargins(14, 12, 14, 12)
        advanced_layout.setSpacing(10)
        advanced_layout.addWidget(QLabel("Advanced Surfaces"))
        advanced_note = QLabel(
            "Diagnostics, runtime controls, operator logs, and recovery flows live in the dedicated advanced surface. Settings stays focused on durable defaults, assistant naming, and persona configuration."
        )
        advanced_note.setWordWrap(True)
        advanced_layout.addWidget(advanced_note)
        layout.addWidget(self._advanced_frame)

        self._persona_status_lbl = QLabel("")
        self._persona_status_lbl.setWordWrap(True)
        layout.addWidget(self._persona_status_lbl)

        save_row = QHBoxLayout()
        self._save_btn = QPushButton("SAVE SETTINGS")
        self._save_btn.clicked.connect(self._save)
        save_row.addWidget(self._save_btn)
        save_row.addStretch()
        layout.addLayout(save_row)
        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)
        self._set_settings_section("runtime")

    def set_embed_mode(self, embedded: bool) -> None:
        self._embedded_mode = bool(embedded)
        self._title_lbl.setVisible(not self._embedded_mode)
        self._subtitle_lbl.setVisible(not self._embedded_mode)
        self._section_row_host.setVisible(not self._embedded_mode)

    def show_settings_section(self, section: str) -> None:
        aliases = {
            "general": "runtime",
            "performance": "runtime",
            "customization": "personas",
            "persona": "personas",
            "help": "advanced",
        }
        target = aliases.get(str(section or "").strip().lower(), str(section or "").strip().lower())
        self._set_settings_section(target or "runtime")

    def _set_settings_section(self, section: str) -> None:
        target = str(section or "runtime").strip().lower() or "runtime"
        self._settings_section = target
        self._runtime_frame.setVisible(target == "runtime")
        self._persona_frame.setVisible(target == "personas")
        self._advanced_frame.setVisible(target == "advanced")
        for key, button in self._section_buttons.items():
            active = key == target
            button.setStyleSheet(
                (
                    f"QPushButton {{ background-color: {T.INK}; color: white; border: none; border-radius: 14px;"
                    f" padding: 6px 12px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px; }}"
                )
                if active
                else (
                    f"QPushButton {{ background-color: rgba(244,239,231,0.90); color: {T.DIM}; border: 1px solid rgba(214,197,174,0.64); border-radius: 14px;"
                    f" padding: 6px 12px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px; }}"
                    f"QPushButton:hover {{ color: {T.TERTIARY}; border-color: {T.TERTIARY}; background-color: #ffffff; }}"
                )
            )

    def _load(self) -> None:
        self._load_runtime_settings()
        self._load_persona_settings()

    def _load_runtime_settings(self) -> None:
        if not _PROFILE_BACKEND:
            return
        try:
            settings = load_app_settings()
            profiles = {"light": 0, "standard": 1, "power": 2}
            modes = {"auto": 0, "claude": 1, "ollama": 2, "local": 3, "code": 4, "teaching": 5}
            self._cb_profile.setCurrentIndex(profiles.get(settings.get("runtime_profile", "standard"), 1))
            self._cb_mode.setCurrentIndex(modes.get(settings.get("default_mode", "auto"), 0))
            self._t_daemon.setChecked(bool(settings.get("enable_daemon", True)))
            self._t_voice.setChecked(bool(settings.get("enable_voice", True)))
            self._t_wake.setChecked(bool(settings.get("wake_word_default", False)))
            saved_at = str(settings.get("_saved_at", "")).strip()
            if saved_at:
                self._last_mod_lbl.setText(f"Last saved: {saved_at}")
            rec = recommend_runtime_profile()
            profile = rec.get("profile", "standard") if isinstance(rec, dict) else str(rec)
            self._hw_lbl.setText(f"Recommended profile: {profile.upper()}")
        except Exception:
            return

    def _load_persona_settings(self) -> None:
        load_persona_settings(self)

    def _load_model_binding_options(self) -> None:
        load_model_binding_options(self)

    def _set_persona_controls_enabled(self, enabled: bool) -> None:
        set_persona_controls_enabled(self, enabled)

    def _persona_items(self) -> list[dict[str, Any]]:
        return persona_items(self)

    def _refresh_persona_lists(self, select_id: str = "") -> None:
        refresh_persona_lists(self, select_id)

    def _selected_persona(self) -> dict[str, Any]:
        return selected_persona(self)

    def _populate_persona_form(self) -> None:
        populate_persona_form(self)

    def _refresh_assignment_summary(self) -> None:
        refresh_assignment_summary(self)

    def _on_persona_selected(self, _index: int) -> None:
        on_persona_selected(self, _index)

    def _on_scope_changed(self, text: str) -> None:
        on_scope_changed(self, text)

    def _next_persona_id(self, base_name: str) -> str:
        return next_persona_id(self, base_name)

    def _create_persona(self) -> None:
        create_persona(self)

    def _delete_persona(self) -> None:
        delete_persona(self)

    def _build_persona_config(self) -> tuple[dict[str, Any], dict[str, Any]]:
        return _build_persona_config_fn(self)

    def _refresh_preview(self) -> None:
        refresh_preview(self)

    def _save(self) -> None:
        profile_map = {0: "light", 1: "standard", 2: "power"}
        mode_map = {0: "auto", 1: "claude", 2: "ollama", 3: "local", 4: "code", 5: "teaching"}
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        payload = {
            "runtime_profile": profile_map.get(self._cb_profile.currentIndex(), "standard"),
            "default_mode": mode_map.get(self._cb_mode.currentIndex(), "auto"),
            "enable_daemon": self._t_daemon.is_checked,
            "enable_voice": self._t_voice.is_checked,
            "wake_word_default": self._t_wake.is_checked,
            "_saved_at": ts,
        }

        persona_payload = None
        active_persona: dict[str, Any] | None = None
        if _PERSONALIZATION_BACKEND:
            try:
                persona_payload, active_persona = self._build_persona_config()
                errors = validate_persona_config(persona_payload)
                if errors:
                    raise ValueError("; ".join(errors[:3]))
            except Exception as exc:
                self._save_confirm.setText("")
                self._persona_status_lbl.setText(f"Assistant save blocked: {exc}")
                return

        previous_persona_config = deepcopy_json(self._persona_config)
        previous_runtime_settings = load_app_settings() if _PROFILE_BACKEND else None

        try:
            if persona_payload is not None and active_persona is not None:
                save_persona_config(persona_payload)

            if _PROFILE_BACKEND:
                save_app_settings(payload)
                apply_settings_to_env(payload)
        except Exception as exc:
            if persona_payload is not None and active_persona is not None:
                try:
                    save_persona_config(previous_persona_config)
                except Exception:
                    pass
            if _PROFILE_BACKEND and previous_runtime_settings is not None:
                try:
                    save_app_settings(previous_runtime_settings)
                    apply_settings_to_env(previous_runtime_settings)
                except Exception:
                    pass
            self._save_confirm.setText("")
            self._persona_status_lbl.setText(f"Save failed: {exc}")
            return

        if persona_payload is not None and active_persona is not None:
            self._persona_config = persona_payload
            self._refresh_persona_lists(str(active_persona.get("id", self._current_persona_id)))
            payload.update(
                {
                    "active_persona_id": str(active_persona.get("id", "")),
                    "active_persona_name": str(active_persona.get("name", "")),
                    "global_persona_id": str(persona_payload.get("assignments", {}).get("global", "")),
                }
            )
            self._persona_status_lbl.setText(
                f"Assistant saved: {active_persona.get('name', DEFAULT_ASSISTANT_NAME)}"
            )

        self._last_mod_lbl.setText(f"Last saved: {ts}")
        self._save_confirm.setText("SAVED")
        self.settings_saved.emit(payload)

    def set_hardware_label(self, text: str) -> None:
        self._hw_lbl.setText(text)

    def set_recovery_status(self, text: str) -> None:
        self._recovery_status.setText(text)
