"""
ui/launcher/views/settings_view.py
Minimal settings view used by the launcher and smoke tests.
"""
from __future__ import annotations

import time

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QLabel, QPushButton, QVBoxLayout, QWidget

from inference_router import LAUNCHER_MODES_DISPLAY

try:
    from utils.runtime_profile import (
        apply_settings_to_env,
        load_app_settings,
        recommend_runtime_profile,
        save_app_settings,
    )
    _PROFILE_BACKEND = True
except Exception:
    _PROFILE_BACKEND = False

    def load_app_settings():
        return {}

    def recommend_runtime_profile():
        return {"profile": "standard"}

    def save_app_settings(_payload):
        return None

    def apply_settings_to_env(_payload):
        return None

_PERSONALIZATION_BACKEND = False


class _Toggle(QCheckBox):
    @property
    def is_checked(self) -> bool:
        return self.isChecked()


class SettingsView(QWidget):
    settings_saved = Signal(dict)
    recovery_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self._cb_profile = QComboBox()
        self._cb_profile.addItems(["LIGHT", "STANDARD", "POWER"])
        layout.addWidget(self._cb_profile)

        self._cb_mode = QComboBox()
        self._cb_mode.addItems(list(LAUNCHER_MODES_DISPLAY))
        layout.addWidget(self._cb_mode)

        self._cb_surface = QComboBox()
        self._cb_surface.addItems(["GUPPY", "MERLIN", "COUNCIL"])
        layout.addWidget(self._cb_surface)

        self._t_daemon = _Toggle("Daemon Background Execution")
        self._t_voice = _Toggle("Voice Synthesis Feedback")
        self._t_wake = _Toggle("Active Wake-Word Detection")
        self._t_adv = _Toggle("Show Advanced Surfaces")
        self._t_daemon.setChecked(True)
        self._t_voice.setChecked(True)
        self._t_adv.setChecked(True)
        for toggle in [self._t_daemon, self._t_voice, self._t_wake, self._t_adv]:
            layout.addWidget(toggle)

        self._hw_lbl = QLabel("Hardware: detecting...")
        self._recovery_status = QLabel("Recovery idle")
        self._last_mod_lbl = QLabel("Last saved: -")
        self._save_confirm = QLabel("")
        for label in [self._hw_lbl, self._recovery_status, self._last_mod_lbl, self._save_confirm]:
            layout.addWidget(label)

        self._save_btn = QPushButton("SAVE SETTINGS")
        self._save_btn.clicked.connect(self._save)
        layout.addWidget(self._save_btn)
        layout.addStretch()

    def _load(self) -> None:
        if not _PROFILE_BACKEND:
            return
        try:
            settings = load_app_settings()
            profiles = {"light": 0, "standard": 1, "power": 2}
            modes = {"auto": 0, "claude": 1, "ollama": 2, "local": 3, "code": 4, "teaching": 5}
            surfaces = {"guppy": 0, "merlin": 1, "council": 2}
            self._cb_profile.setCurrentIndex(profiles.get(settings.get("runtime_profile", "standard"), 1))
            self._cb_mode.setCurrentIndex(modes.get(settings.get("default_mode", "auto"), 0))
            self._cb_surface.setCurrentIndex(surfaces.get(settings.get("default_surface", "guppy"), 0))
            self._t_daemon.setChecked(bool(settings.get("enable_daemon", True)))
            self._t_voice.setChecked(bool(settings.get("enable_voice", True)))
            self._t_wake.setChecked(bool(settings.get("wake_word_default", False)))
            self._t_adv.setChecked(bool(settings.get("show_advanced_surfaces", True)))
            saved_at = str(settings.get("_saved_at", "")).strip()
            if saved_at:
                self._last_mod_lbl.setText(f"Last saved: {saved_at}")
            rec = recommend_runtime_profile()
            profile = rec.get("profile", "standard") if isinstance(rec, dict) else str(rec)
            self._hw_lbl.setText(f"Recommended profile: {profile.upper()}")
        except Exception:
            return

    def _save(self) -> None:
        profile_map = {0: "light", 1: "standard", 2: "power"}
        mode_map = {0: "auto", 1: "claude", 2: "ollama", 3: "local", 4: "code", 5: "teaching"}
        surface_map = {0: "guppy", 1: "merlin", 2: "council"}
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        payload = {
            "runtime_profile": profile_map.get(self._cb_profile.currentIndex(), "standard"),
            "default_mode": mode_map.get(self._cb_mode.currentIndex(), "auto"),
            "default_surface": surface_map.get(self._cb_surface.currentIndex(), "guppy"),
            "enable_daemon": self._t_daemon.is_checked,
            "enable_voice": self._t_voice.is_checked,
            "wake_word_default": self._t_wake.is_checked,
            "show_advanced_surfaces": self._t_adv.is_checked,
            "_saved_at": ts,
        }
        if _PROFILE_BACKEND:
            try:
                save_app_settings(payload)
                apply_settings_to_env(payload)
            except Exception:
                pass
        self._last_mod_lbl.setText(f"Last saved: {ts}")
        self._save_confirm.setText("SAVED")
        self.settings_saved.emit(payload)

    def set_hardware_label(self, text: str) -> None:
        self._hw_lbl.setText(text)

    def set_recovery_status(self, text: str) -> None:
        self._recovery_status.setText(text)
