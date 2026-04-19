"""
ui/launcher/views/settings_view.py
Runtime settings plus Persona Builder v1 for the unified launcher.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from src.guppy.experience_config import (
    apply_runtime_settings_to_env as apply_settings_to_env,
    ensure_personalization_scaffold,
    list_model_ids,
    load_persona_config_with_diagnostics,
    load_provider_registry,
    load_runtime_settings as load_app_settings,
    personalization_backend_available,
    recommend_runtime_profile,
    runtime_settings_backend_available,
    save_persona_config,
    save_runtime_settings as save_app_settings,
    validate_persona_config,
)
from src.guppy.inference.router import LAUNCHER_MODES_DISPLAY
from .. import tokens as T
_PROFILE_BACKEND = runtime_settings_backend_available()

_DEFAULT_PERSONA_CONFIG: dict[str, Any] = {
    "version": 1,
    "default_persona_id": "main_guppy",
    "personas": [
        {
            "id": "main_guppy",
            "name": "Main Guppy",
            "scope": "global",
            "system_prompt": (
                "You are Main Guppy, Ryan's primary day-to-day assistant. "
                "Be calm, dependable, practical, and quietly confident. "
                "Keep the Jarvis-like feel understated and never theatrical."
            ),
            "traits": {
                "tone": "butler",
                "verbosity": "medium",
                "response_style": "direct",
            },
            "teaching": {
                "enabled": True,
                "socratic_bias": 35,
                "example_bias": 60,
            },
            "profile_summary": (
                "- Ryan prefers concise, high-signal answers with low filler.\n"
                "- Keep the tone calm, exact, proactive, and quietly confident. Aim for a Jarvis-like feel without theatrical phrasing.\n"
                "- Preserve continuity across coding, launcher UX, automation, and workspace work so progress feels cumulative.\n"
                "- Keep Home calm and chat-first. Move heavier runtime, routing, recovery, and logs detail into App Mgmt or dedicated surfaces.\n"
                "- Never pretend an action, tool result, or state change happened unless it was actually executed."
            ),
        }
    ],
    "assignments": {
        "global": "main_guppy",
        "by_model": {},
    },
}

_PERSONALIZATION_BACKEND = personalization_backend_available()

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_TONE_OPTIONS = ["butler", "coach", "mentor", "analyst", "friendly"]
_VERBOSITY_OPTIONS = ["low", "medium", "high"]
_STYLE_OPTIONS = ["direct", "structured", "teaching", "concise"]
_MODEL_BINDING_OPTIONS = [
    "guppy",
    "guppy-fast",
    "vault-scraper",
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-6",
]


def _deepcopy_json(data: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(data))


def _slugify(raw: str) -> str:
    normalized = _SLUG_RE.sub("_", (raw or "").strip().lower()).strip("_")
    return normalized[:40] or "persona"


class _Toggle(QCheckBox):
    @property
    def is_checked(self) -> bool:
        return self.isChecked()


class SettingsView(QWidget):
    settings_saved = Signal(dict)
    recovery_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._persona_config = _deepcopy_json(_DEFAULT_PERSONA_CONFIG)
        self._current_persona_id = "main_guppy"
        self._loading_persona = False
        self._settings_section = "runtime"
        self._section_buttons: dict[str, QPushButton] = {}
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
        title.setStyleSheet("font-size: 26pt; font-weight: 900;")
        layout.addWidget(title)
        subtitle = QLabel("Runtime defaults and Persona Builder v1 for launcher-local behavior.")
        subtitle.setWordWrap(True)
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
        layout.addLayout(section_row)

        self._runtime_frame = QFrame()
        runtime_layout = QVBoxLayout(self._runtime_frame)
        runtime_layout.setContentsMargins(14, 12, 14, 12)
        runtime_layout.setSpacing(10)
        runtime_layout.addWidget(QLabel("Runtime Defaults"))

        self._cb_profile = QComboBox()
        self._cb_profile.addItems(["LIGHT", "STANDARD", "POWER"])
        self._cb_mode = QComboBox()
        self._cb_mode.addItems(list(LAUNCHER_MODES_DISPLAY))

        row = QHBoxLayout()
        row.addWidget(self._cb_profile)
        row.addWidget(self._cb_mode)
        runtime_layout.addLayout(row)

        self._t_daemon = _Toggle("Daemon Background Execution")
        self._t_voice = _Toggle("Voice Synthesis Feedback")
        self._t_wake = _Toggle("Active Wake-Word Detection")
        self._t_daemon.setChecked(True)
        self._t_voice.setChecked(True)
        for toggle in [self._t_daemon, self._t_voice, self._t_wake]:
            runtime_layout.addWidget(toggle)

        self._hw_lbl = QLabel("Hardware: detecting...")
        self._recovery_status = QLabel("Recovery idle")
        self._last_mod_lbl = QLabel("Last saved: -")
        self._save_confirm = QLabel("")
        for label in [self._hw_lbl, self._recovery_status, self._last_mod_lbl, self._save_confirm]:
            label.setWordWrap(True)
            runtime_layout.addWidget(label)
        layout.addWidget(self._runtime_frame)

        self._persona_frame = QFrame()
        persona_layout = QVBoxLayout(self._persona_frame)
        persona_layout.setContentsMargins(14, 12, 14, 12)
        persona_layout.setSpacing(10)
        persona_layout.addWidget(QLabel("Persona Builder v1"))

        picker_row = QHBoxLayout()
        self._persona_picker = QComboBox()
        self._persona_picker.currentIndexChanged.connect(self._on_persona_selected)
        self._new_persona_btn = QPushButton("NEW PERSONA")
        self._new_persona_btn.clicked.connect(self._create_persona)
        self._delete_persona_btn = QPushButton("DELETE")
        self._delete_persona_btn.clicked.connect(self._delete_persona)
        picker_row.addWidget(self._persona_picker, stretch=1)
        picker_row.addWidget(self._new_persona_btn)
        picker_row.addWidget(self._delete_persona_btn)
        persona_layout.addLayout(picker_row)

        identity_row = QHBoxLayout()
        self._persona_name = QLineEdit()
        self._persona_name.setPlaceholderText("Persona name")
        self._persona_name.textChanged.connect(self._refresh_preview)
        self._scope_cb = QComboBox()
        self._scope_cb.addItems(["GLOBAL", "MODEL"])
        self._scope_cb.currentTextChanged.connect(self._on_scope_changed)
        self._model_binding_cb = QComboBox()
        self._model_binding_cb.addItems(_MODEL_BINDING_OPTIONS)
        self._model_binding_cb.currentTextChanged.connect(self._refresh_preview)
        identity_row.addWidget(self._persona_name, stretch=2)
        identity_row.addWidget(self._scope_cb)
        identity_row.addWidget(self._model_binding_cb, stretch=1)
        persona_layout.addLayout(identity_row)

        traits_row = QHBoxLayout()
        self._tone_cb = QComboBox()
        self._tone_cb.addItems([item.upper() for item in _TONE_OPTIONS])
        self._tone_cb.currentTextChanged.connect(self._refresh_preview)
        self._verbosity_cb = QComboBox()
        self._verbosity_cb.addItems([item.upper() for item in _VERBOSITY_OPTIONS])
        self._verbosity_cb.currentTextChanged.connect(self._refresh_preview)
        self._style_cb = QComboBox()
        self._style_cb.addItems([item.upper() for item in _STYLE_OPTIONS])
        self._style_cb.currentTextChanged.connect(self._refresh_preview)
        traits_row.addWidget(self._tone_cb)
        traits_row.addWidget(self._verbosity_cb)
        traits_row.addWidget(self._style_cb)
        persona_layout.addLayout(traits_row)

        self._teaching_toggle = _Toggle("Teaching mode enabled")
        self._teaching_toggle.stateChanged.connect(self._refresh_preview)
        persona_layout.addWidget(self._teaching_toggle)

        self._socratic_slider, self._socratic_value = self._build_slider_row(
            persona_layout,
            "Socratic bias",
            self._refresh_preview,
        )
        self._example_slider, self._example_value = self._build_slider_row(
            persona_layout,
            "Example bias",
            self._refresh_preview,
        )

        assignment_row = QHBoxLayout()
        self._global_persona_cb = QComboBox()
        self._global_persona_cb.currentTextChanged.connect(self._refresh_preview)
        assignment_row.addWidget(QLabel("Global default"))
        assignment_row.addWidget(self._global_persona_cb, stretch=1)
        persona_layout.addLayout(assignment_row)

        self._assignment_summary_lbl = QLabel("Model bindings: -")
        self._assignment_summary_lbl.setWordWrap(True)
        persona_layout.addWidget(self._assignment_summary_lbl)

        self._system_prompt = QPlainTextEdit()
        self._system_prompt.setPlaceholderText("System prompt for this persona")
        self._system_prompt.setMinimumHeight(140)
        self._system_prompt.textChanged.connect(self._refresh_preview)
        persona_layout.addWidget(self._system_prompt)

        self._preview_lbl = QLabel("Preview unavailable")
        self._preview_lbl.setWordWrap(True)
        persona_layout.addWidget(self._preview_lbl)

        self._persona_diag_lbl = QLabel("")
        self._persona_diag_lbl.setWordWrap(True)
        persona_layout.addWidget(self._persona_diag_lbl)
        layout.addWidget(self._persona_frame)

        self._advanced_frame = QFrame()
        advanced_layout = QVBoxLayout(self._advanced_frame)
        advanced_layout.setContentsMargins(14, 12, 14, 12)
        advanced_layout.setSpacing(10)
        advanced_layout.addWidget(QLabel("Advanced Surfaces"))
        advanced_note = QLabel(
            "Diagnostics, runtime controls, operator logs, and recovery flows live in the dedicated advanced surface. Settings stays focused on durable defaults and persona configuration."
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

    def _build_slider_row(self, layout: QVBoxLayout, label_text: str, on_change) -> tuple[QSlider, QLabel]:
        row = QHBoxLayout()
        label = QLabel(label_text)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        value = QLabel("0")
        slider.valueChanged.connect(lambda amount: value.setText(str(amount)))
        slider.valueChanged.connect(lambda _amount: on_change())
        row.addWidget(label)
        row.addWidget(slider, stretch=1)
        row.addWidget(value)
        layout.addLayout(row)
        return slider, value

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
        if not _PERSONALIZATION_BACKEND:
            self._set_persona_controls_enabled(False)
            self._persona_status_lbl.setText("Persona Builder unavailable: personalization backend not loaded.")
            self._refresh_preview()
            return

        try:
            ensure_personalization_scaffold()
            self._load_model_binding_options()
            config, diagnostics = load_persona_config_with_diagnostics()
        except Exception as exc:
            self._set_persona_controls_enabled(False)
            self._persona_status_lbl.setText(f"Persona Builder failed to load: {exc}")
            self._refresh_preview()
            return

        if isinstance(config, dict):
            self._persona_config = config
        self._persona_diag_lbl.setText(
            "Persona config healthy" if not diagnostics else "Config notes: " + " | ".join(diagnostics)
        )
        select_id = str(
            self._persona_config.get("default_persona_id")
            or self._persona_config.get("assignments", {}).get("global", "main_guppy")
        )
        self._refresh_persona_lists(select_id)
        self._persona_status_lbl.setText("Persona Builder ready")

    def _load_model_binding_options(self) -> None:
        options = list_model_ids(load_provider_registry())
        current = self._model_binding_cb.currentText().strip()
        self._model_binding_cb.blockSignals(True)
        self._model_binding_cb.clear()
        self._model_binding_cb.addItems(options or list(_MODEL_BINDING_OPTIONS))
        if current:
            index = self._model_binding_cb.findText(current)
            if index >= 0:
                self._model_binding_cb.setCurrentIndex(index)
        self._model_binding_cb.blockSignals(False)

    def _set_persona_controls_enabled(self, enabled: bool) -> None:
        for widget in [
            self._persona_picker,
            self._new_persona_btn,
            self._delete_persona_btn,
            self._persona_name,
            self._scope_cb,
            self._model_binding_cb,
            self._tone_cb,
            self._verbosity_cb,
            self._style_cb,
            self._teaching_toggle,
            self._socratic_slider,
            self._example_slider,
            self._global_persona_cb,
            self._system_prompt,
        ]:
            widget.setEnabled(enabled)

    def _persona_items(self) -> list[dict[str, Any]]:
        personas = self._persona_config.get("personas", [])
        return [item for item in personas if isinstance(item, dict)]

    def _refresh_persona_lists(self, select_id: str = "") -> None:
        personas = self._persona_items()
        if not personas:
            self._persona_config = _deepcopy_json(_DEFAULT_PERSONA_CONFIG)
            personas = self._persona_items()

        target = select_id or str(personas[0].get("id", "main_guppy"))
        self._persona_picker.blockSignals(True)
        self._global_persona_cb.blockSignals(True)
        self._persona_picker.clear()
        self._global_persona_cb.clear()

        for persona in personas:
            persona_id = str(persona.get("id", "")).strip()
            name = str(persona.get("name", persona_id)).strip() or persona_id
            scope = str(persona.get("scope", "global")).strip().upper()
            label = f"{name} [{scope}]"
            self._persona_picker.addItem(label, persona_id)
            self._global_persona_cb.addItem(name, persona_id)

        picker_index = max(0, self._persona_picker.findData(target))
        self._persona_picker.setCurrentIndex(picker_index)
        global_target = str(self._persona_config.get("assignments", {}).get("global", "") or target)
        global_index = self._global_persona_cb.findData(global_target)
        self._global_persona_cb.setCurrentIndex(max(0, global_index))
        self._persona_picker.blockSignals(False)
        self._global_persona_cb.blockSignals(False)
        self._current_persona_id = str(self._persona_picker.currentData() or target)
        self._populate_persona_form()

    def _selected_persona(self) -> dict[str, Any]:
        for persona in self._persona_items():
            if str(persona.get("id", "")).strip() == self._current_persona_id:
                return persona
        return self._persona_items()[0]

    def _populate_persona_form(self) -> None:
        persona = self._selected_persona()
        traits = persona.get("traits", {}) if isinstance(persona.get("traits"), dict) else {}
        teaching = persona.get("teaching", {}) if isinstance(persona.get("teaching"), dict) else {}

        self._loading_persona = True
        self._persona_name.setText(str(persona.get("name", "")))
        self._scope_cb.setCurrentText(str(persona.get("scope", "global")).upper())
        model_name = str(persona.get("model", _MODEL_BINDING_OPTIONS[0]))
        if model_name not in _MODEL_BINDING_OPTIONS:
            model_name = _MODEL_BINDING_OPTIONS[0]
        model_index = self._model_binding_cb.findText(model_name)
        self._model_binding_cb.setCurrentIndex(max(0, model_index))
        self._tone_cb.setCurrentText(str(traits.get("tone", "butler")).upper())
        self._verbosity_cb.setCurrentText(str(traits.get("verbosity", "medium")).upper())
        self._style_cb.setCurrentText(str(traits.get("response_style", "direct")).upper())
        self._teaching_toggle.setChecked(bool(teaching.get("enabled", True)))
        self._socratic_slider.setValue(int(teaching.get("socratic_bias", 35) or 35))
        self._example_slider.setValue(int(teaching.get("example_bias", 60) or 60))
        self._system_prompt.setPlainText(str(persona.get("system_prompt", "")))
        self._loading_persona = False
        self._on_scope_changed(self._scope_cb.currentText())
        self._refresh_assignment_summary()
        self._refresh_preview()

    def _refresh_assignment_summary(self) -> None:
        mapping = self._persona_config.get("assignments", {}).get("by_model", {})
        if not isinstance(mapping, dict) or not mapping:
            self._assignment_summary_lbl.setText("Model bindings: none")
            return
        persona_names = {
            str(item.get("id", "")).strip(): str(item.get("name", item.get("id", ""))).strip()
            for item in self._persona_items()
        }
        parts = [f"{model} -> {persona_names.get(str(persona_id), str(persona_id))}" for model, persona_id in sorted(mapping.items())]
        self._assignment_summary_lbl.setText("Model bindings: " + " | ".join(parts))

    def _on_persona_selected(self, _index: int) -> None:
        self._current_persona_id = str(self._persona_picker.currentData() or self._current_persona_id)
        self._populate_persona_form()

    def _on_scope_changed(self, text: str) -> None:
        model_scope = (text or "GLOBAL").strip().upper() == "MODEL"
        self._model_binding_cb.setEnabled(model_scope and _PERSONALIZATION_BACKEND)
        self._refresh_preview()

    def _next_persona_id(self, base_name: str) -> str:
        base = _slugify(base_name)
        existing = {str(item.get("id", "")).strip() for item in self._persona_items()}
        candidate = base
        suffix = 2
        while candidate in existing:
            candidate = f"{base}_{suffix}"
            suffix += 1
        return candidate

    def _create_persona(self) -> None:
        if not _PERSONALIZATION_BACKEND:
            return
        name = f"Custom Persona {len(self._persona_items()) + 1}"
        persona_id = self._next_persona_id(name)
        self._persona_config.setdefault("personas", []).append(
            {
                "id": persona_id,
                "name": name,
                "scope": "global",
                "system_prompt": "You are Guppy. Stay explicit, bounded, and practical.",
                "traits": {
                    "tone": "coach",
                    "verbosity": "medium",
                    "response_style": "structured",
                },
                "teaching": {
                    "enabled": True,
                    "socratic_bias": 50,
                    "example_bias": 50,
                },
            }
        )
        self._refresh_persona_lists(persona_id)
        self._persona_status_lbl.setText(f"Draft persona created: {name}")

    def _delete_persona(self) -> None:
        personas = self._persona_items()
        if len(personas) <= 1:
            self._persona_status_lbl.setText("At least one persona must remain.")
            return
        keep = [item for item in personas if str(item.get("id", "")).strip() != self._current_persona_id]
        self._persona_config["personas"] = keep
        assignments = self._persona_config.setdefault("assignments", {"global": keep[0]["id"], "by_model": {}})
        by_model = assignments.get("by_model", {}) if isinstance(assignments.get("by_model"), dict) else {}
        assignments["by_model"] = {model: persona_id for model, persona_id in by_model.items() if persona_id != self._current_persona_id}
        if assignments.get("global") == self._current_persona_id:
            assignments["global"] = str(keep[0].get("id", "main_guppy"))
        self._persona_config["default_persona_id"] = assignments["global"]
        self._refresh_persona_lists(str(keep[0].get("id", "main_guppy")))
        self._persona_status_lbl.setText("Persona removed from draft config")

    def _build_persona_config(self) -> tuple[dict[str, Any], dict[str, Any]]:
        cfg = _deepcopy_json(self._persona_config)
        personas = cfg.get("personas", []) if isinstance(cfg.get("personas"), list) else []
        persona_id = self._current_persona_id or self._next_persona_id(self._persona_name.text().strip())
        name = self._persona_name.text().strip()
        if not name:
            raise ValueError("Persona name is required")
        scope = self._scope_cb.currentText().strip().lower()
        model_name = self._model_binding_cb.currentText().strip()
        if scope == "model" and not model_name:
            raise ValueError("Model scope requires a model binding")

        existing_persona = next(
            (
                item
                for item in personas
                if isinstance(item, dict) and str(item.get("id", "")).strip() == persona_id
            ),
            {},
        )
        preserved = {
            key: value
            for key, value in existing_persona.items()
            if key not in {"id", "name", "scope", "model", "system_prompt", "traits", "teaching"}
        }

        persona = {
            **preserved,
            "id": persona_id,
            "name": name,
            "scope": scope,
            "system_prompt": self._system_prompt.toPlainText().strip() or "You are Guppy. Be concise, dependable, and practical.",
            "traits": {
                "tone": self._tone_cb.currentText().strip().lower(),
                "verbosity": self._verbosity_cb.currentText().strip().lower(),
                "response_style": self._style_cb.currentText().strip().lower(),
            },
            "teaching": {
                "enabled": self._teaching_toggle.isChecked(),
                "socratic_bias": int(self._socratic_slider.value()),
                "example_bias": int(self._example_slider.value()),
            },
        }
        if scope == "model":
            persona["model"] = model_name

        replaced = False
        for index, item in enumerate(personas):
            if isinstance(item, dict) and str(item.get("id", "")).strip() == persona_id:
                personas[index] = persona
                replaced = True
                break
        if not replaced:
            personas.append(persona)
        cfg["personas"] = personas

        assignments = cfg.setdefault("assignments", {"global": persona_id, "by_model": {}})
        if not isinstance(assignments.get("by_model"), dict):
            assignments["by_model"] = {}
        assignments["by_model"] = {
            model: assigned_persona
            for model, assigned_persona in assignments["by_model"].items()
            if assigned_persona != persona_id
        }
        if scope == "model":
            assignments["by_model"][model_name] = persona_id

        global_persona_id = str(self._global_persona_cb.currentData() or persona_id).strip() or persona_id
        if global_persona_id not in {str(item.get("id", "")).strip() for item in personas if isinstance(item, dict)}:
            global_persona_id = persona_id
        assignments["global"] = global_persona_id
        cfg["default_persona_id"] = global_persona_id
        return cfg, persona

    def _refresh_preview(self) -> None:
        if self._loading_persona:
            return
        scope = self._scope_cb.currentText().strip().upper() or "GLOBAL"
        model_text = self._model_binding_cb.currentText().strip()
        tone = self._tone_cb.currentText().strip().upper() or "BUTLER"
        verbosity = self._verbosity_cb.currentText().strip().upper() or "MEDIUM"
        style = self._style_cb.currentText().strip().upper() or "DIRECT"
        teaching = "ON" if self._teaching_toggle.isChecked() else "OFF"
        prompt = self._system_prompt.toPlainText().strip() or "You are Guppy. Be concise, dependable, and practical."
        scope_line = f"Scope: {scope}" + (f" -> {model_text}" if scope == "MODEL" and model_text else "")
        prompt_preview = prompt[:220] + ("..." if len(prompt) > 220 else "")
        self._preview_lbl.setText(
            " | ".join(
                [
                    f"Persona: {(self._persona_name.text().strip() or 'Untitled').upper()}",
                    scope_line,
                    f"Tone: {tone}",
                    f"Verbosity: {verbosity}",
                    f"Style: {style}",
                    f"Teaching: {teaching} ({self._socratic_slider.value()} / {self._example_slider.value()})",
                ]
            )
            + f"\nPrompt preview: {prompt_preview}"
        )

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
                self._persona_status_lbl.setText(f"Persona save blocked: {exc}")
                return

        previous_persona_config = _deepcopy_json(self._persona_config)
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
                f"Persona saved: {active_persona.get('name', 'persona')}"
            )

        self._last_mod_lbl.setText(f"Last saved: {ts}")
        self._save_confirm.setText("SAVED")
        self.settings_saved.emit(payload)

    def set_hardware_label(self, text: str) -> None:
        self._hw_lbl.setText(text)

    def set_recovery_status(self, text: str) -> None:
        self._recovery_status.setText(text)
