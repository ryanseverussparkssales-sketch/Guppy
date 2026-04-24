"""
ui/launcher/views/settings_view_sections.py
Section builders extracted from settings_view.py.
Provides QFrame factories for runtime and persona sub-panels.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
)

from .. import tokens as T

# ── Option lists reused by SettingsView ──────────────────────────────────────

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


class _Toggle(QCheckBox):
    @property
    def is_checked(self) -> bool:
        return self.isChecked()


def _build_slider_row(
    layout: QVBoxLayout, label_text: str, on_change
) -> tuple[QSlider, QLabel]:
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


# ── Section builders ─────────────────────────────────────────────────────────


def build_settings_runtime_frame(owner, *, launcher_modes: list[str]) -> QFrame:
    """Build the Runtime Defaults QFrame, wiring all widgets onto *owner*."""
    frame = QFrame()
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(10)
    layout.addWidget(QLabel("Runtime Defaults"))

    owner._cb_profile = QComboBox()
    owner._cb_profile.addItems(["LIGHT", "STANDARD", "POWER"])
    owner._cb_mode = QComboBox()
    owner._cb_mode.addItems(launcher_modes)

    row = QHBoxLayout()
    row.addWidget(owner._cb_profile)
    row.addWidget(owner._cb_mode)
    layout.addLayout(row)

    owner._t_daemon = _Toggle("Daemon Background Execution")
    owner._t_voice = _Toggle("Voice Synthesis Feedback")
    owner._t_wake = _Toggle("Active Wake-Word Detection")
    owner._t_daemon.setChecked(True)
    owner._t_voice.setChecked(True)
    for toggle in [owner._t_daemon, owner._t_voice, owner._t_wake]:
        layout.addWidget(toggle)

    owner._hw_lbl = QLabel("Hardware: detecting...")
    owner._recovery_status = QLabel("Recovery idle")
    owner._last_mod_lbl = QLabel("Last saved: -")
    owner._save_confirm = QLabel("")
    for lbl in [owner._hw_lbl, owner._recovery_status, owner._last_mod_lbl, owner._save_confirm]:
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

    return frame


def build_settings_persona_frame(owner) -> QFrame:
    """Build the Assistant & Persona Builder QFrame, wiring all widgets onto *owner*."""
    frame = QFrame()
    persona_layout = QVBoxLayout(frame)
    persona_layout.setContentsMargins(14, 12, 14, 12)
    persona_layout.setSpacing(10)
    persona_layout.addWidget(QLabel("Assistant & Persona Builder"))

    picker_row = QHBoxLayout()
    owner._persona_picker = QComboBox()
    owner._persona_picker.currentIndexChanged.connect(owner._on_persona_selected)
    owner._new_persona_btn = QPushButton("NEW PERSONA")
    owner._new_persona_btn.clicked.connect(owner._create_persona)
    owner._delete_persona_btn = QPushButton("DELETE")
    owner._delete_persona_btn.clicked.connect(owner._delete_persona)
    picker_row.addWidget(owner._persona_picker, stretch=1)
    picker_row.addWidget(owner._new_persona_btn)
    picker_row.addWidget(owner._delete_persona_btn)
    persona_layout.addLayout(picker_row)

    identity_row = QHBoxLayout()
    owner._persona_name = QLineEdit()
    owner._persona_name.setPlaceholderText("Assistant name")
    owner._persona_name.textChanged.connect(owner._refresh_preview)
    owner._scope_cb = QComboBox()
    owner._scope_cb.addItems(["GLOBAL", "MODEL"])
    owner._scope_cb.currentTextChanged.connect(owner._on_scope_changed)
    owner._model_binding_cb = QComboBox()
    owner._model_binding_cb.addItems(_MODEL_BINDING_OPTIONS)
    owner._model_binding_cb.currentTextChanged.connect(owner._refresh_preview)
    identity_row.addWidget(owner._persona_name, stretch=2)
    identity_row.addWidget(owner._scope_cb)
    identity_row.addWidget(owner._model_binding_cb, stretch=1)
    owner._assistant_name_note = QLabel(
        "Platform name stays Guppy. Change the default assistant name here; model identity stays in Models."
    )
    owner._assistant_name_note.setWordWrap(True)
    persona_layout.addLayout(identity_row)
    persona_layout.addWidget(owner._assistant_name_note)

    traits_row = QHBoxLayout()
    owner._tone_cb = QComboBox()
    owner._tone_cb.addItems([item.upper() for item in _TONE_OPTIONS])
    owner._tone_cb.currentTextChanged.connect(owner._refresh_preview)
    owner._verbosity_cb = QComboBox()
    owner._verbosity_cb.addItems([item.upper() for item in _VERBOSITY_OPTIONS])
    owner._verbosity_cb.currentTextChanged.connect(owner._refresh_preview)
    owner._style_cb = QComboBox()
    owner._style_cb.addItems([item.upper() for item in _STYLE_OPTIONS])
    owner._style_cb.currentTextChanged.connect(owner._refresh_preview)
    traits_row.addWidget(owner._tone_cb)
    traits_row.addWidget(owner._verbosity_cb)
    traits_row.addWidget(owner._style_cb)
    persona_layout.addLayout(traits_row)

    owner._teaching_toggle = _Toggle("Teaching mode enabled")
    owner._teaching_toggle.stateChanged.connect(owner._refresh_preview)
    persona_layout.addWidget(owner._teaching_toggle)

    owner._socratic_slider, owner._socratic_value = _build_slider_row(
        persona_layout, "Socratic bias", owner._refresh_preview
    )
    owner._example_slider, owner._example_value = _build_slider_row(
        persona_layout, "Example bias", owner._refresh_preview
    )

    assignment_row = QHBoxLayout()
    owner._global_persona_cb = QComboBox()
    owner._global_persona_cb.currentTextChanged.connect(owner._refresh_preview)
    assignment_row.addWidget(QLabel("Global default"))
    assignment_row.addWidget(owner._global_persona_cb, stretch=1)
    persona_layout.addLayout(assignment_row)

    owner._assignment_summary_lbl = QLabel("Model bindings: -")
    owner._assignment_summary_lbl.setWordWrap(True)
    persona_layout.addWidget(owner._assignment_summary_lbl)

    owner._system_prompt = QPlainTextEdit()
    owner._system_prompt.setPlaceholderText("System prompt for this persona")
    owner._system_prompt.setMinimumHeight(140)
    owner._system_prompt.textChanged.connect(owner._refresh_preview)
    persona_layout.addWidget(owner._system_prompt)

    owner._preview_lbl = QLabel("Preview unavailable")
    owner._preview_lbl.setWordWrap(True)
    persona_layout.addWidget(owner._preview_lbl)

    owner._persona_diag_lbl = QLabel("")
    owner._persona_diag_lbl.setWordWrap(True)
    persona_layout.addWidget(owner._persona_diag_lbl)

    return frame
