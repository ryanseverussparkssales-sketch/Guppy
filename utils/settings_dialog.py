"""
utils/settings_dialog.py — Shared runtime settings dialog (PySide6)
====================================================================
Used by Guppy, Merlin, and Council to open the same settings panel
with surface-specific theming.  Import RuntimeSettingsDialog from here;
do NOT import from guppy_ui to avoid circular/full-module init.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QCheckBox,
)
from PySide6.QtGui import QFont

from utils.runtime_profile import recommend_runtime_profile, save_app_settings, apply_settings_to_env


class RuntimeSettingsDialog(QDialog):
    """
    Profile + settings dialog.  Accepts a ``theme`` dict so each surface
    can pass its own colour tokens without duplicating the class.

    Minimum required keys: bg, bg3, text, dim, border, accent.
    ``font_family`` and ``font_size`` are optional (fall back to safe defaults).
    """

    def __init__(self, settings: dict, recommendation: dict, theme: dict, parent=None):
        super().__init__(parent)
        self._recommendation = dict(recommendation or {})
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(520, 460)

        bg     = theme.get("bg",     "#0f0f0f")
        bg3    = theme.get("bg3",    "#1e1e1e")
        text   = theme.get("text",   "#e8e8e8")
        dim    = theme.get("dim",    "#707070")
        border = theme.get("border", "#2a2a2a")
        accent = theme.get("accent", "#d4af37")
        ff     = theme.get("font_family", "Consolas")
        fs     = int(theme.get("font_size", 13))

        self.setStyleSheet(
            f"QDialog{{background:{bg};color:{text};}}"
            f"QLabel{{background:transparent;color:{text};}}"
            f"QComboBox{{background:{bg3};color:{text};border:1px solid {border};"
            f"border-radius:4px;padding:4px 6px;}}"
            f"QComboBox QAbstractItemView{{background:{bg3};color:{text};"
            f"selection-background-color:{accent}33;}}"
            f"QCheckBox{{color:{text};spacing:6px;}}"
            f"QPushButton{{background:{bg3};color:{text};border:1px solid {border};"
            f"border-radius:4px;padding:6px 10px;}}"
            f"QPushButton:hover{{border-color:{accent};background:{accent}11;}}"
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(10)

        title = QLabel("Runtime Profile & Settings")
        title.setFont(QFont(ff, fs + 2, QFont.Weight.Bold))
        lay.addWidget(title)

        # Hardware summary
        rec_profile = str(self._recommendation.get("profile", "standard")).upper()
        rec_text = (
            f"Recommended: {rec_profile}  |  "
            f"CPU {self._recommendation.get('cpu_percent', 0):.1f}%  |  "
            f"RAM {self._recommendation.get('available_ram_gb', 0):.1f}/"
            f"{self._recommendation.get('total_ram_gb', 0):.1f} GB  |  "
            f"Ollama {'READY' if self._recommendation.get('ollama_ready') else 'DOWN'}"
        )
        hw_lbl = QLabel(rec_text)
        hw_lbl.setWordWrap(True)
        hw_lbl.setStyleSheet(f"color:{dim};font-size:{fs - 1}px;")
        lay.addWidget(hw_lbl)

        reasons = self._recommendation.get("reasons", [])
        if reasons:
            r_lbl = QLabel("\n".join(f"  · {r}" for r in reasons))
            r_lbl.setWordWrap(True)
            r_lbl.setStyleSheet(f"color:{dim};font-size:{fs - 2}px;")
            lay.addWidget(r_lbl)

        # Separator line
        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{border};")
        lay.addWidget(sep)

        # ── Controls ──────────────────────────────────────────────────────────

        def _row(label: str, widget) -> QHBoxLayout:
            h = QHBoxLayout()
            h.setSpacing(12)
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color:{dim};font-size:{fs - 1}px;letter-spacing:1px;")
            lbl.setFixedWidth(220)
            h.addWidget(lbl)
            h.addWidget(widget)
            return h

        self._profile = QComboBox()
        self._profile.addItems(["light", "standard", "power"])
        self._profile.setCurrentText(str(settings.get("runtime_profile", "standard")))
        lay.addLayout(_row("RUNTIME PROFILE", self._profile))

        self._default_mode = QComboBox()
        self._default_mode.addItems(["auto", "claude", "ollama", "teaching"])
        self._default_mode.setCurrentText(str(settings.get("default_mode", "auto")))
        lay.addLayout(_row("DEFAULT MODE", self._default_mode))

        self._default_surface = QComboBox()
        self._default_surface.addItems(["guppy", "merlin", "council"])
        self._default_surface.setCurrentText(str(settings.get("default_surface", "guppy")))
        lay.addLayout(_row("DEFAULT SURFACE", self._default_surface))

        self._show_advanced = QCheckBox("Show Merlin / Council surfaces")
        self._show_advanced.setChecked(bool(settings.get("show_advanced_surfaces", True)))
        lay.addWidget(self._show_advanced)

        self._enable_daemon = QCheckBox("Enable background daemon services")
        self._enable_daemon.setChecked(bool(settings.get("enable_daemon", True)))
        lay.addWidget(self._enable_daemon)

        self._enable_voice = QCheckBox("Enable voice subsystem")
        self._enable_voice.setChecked(bool(settings.get("enable_voice", True)))
        lay.addWidget(self._enable_voice)

        self._wake_word = QCheckBox("Enable wake word by default")
        self._wake_word.setChecked(bool(settings.get("wake_word_default", False)))
        lay.addWidget(self._wake_word)

        lay.addStretch()

        # ── Buttons ───────────────────────────────────────────────────────────
        btns = QHBoxLayout()
        use_rec = QPushButton(f"Use Recommended ({rec_profile.capitalize()})")
        use_rec.clicked.connect(self._apply_recommended)
        btns.addWidget(use_rec)
        btns.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.clicked.connect(self.accept)
        btns.addWidget(cancel)
        btns.addWidget(save)
        lay.addLayout(btns)

    def _apply_recommended(self):
        self._profile.setCurrentText(str(self._recommendation.get("profile", "standard")))

    def settings_payload(self) -> dict:
        return {
            "runtime_profile": self._profile.currentText(),
            "default_surface": self._default_surface.currentText(),
            "show_advanced_surfaces": self._show_advanced.isChecked(),
            "enable_daemon": self._enable_daemon.isChecked(),
            "enable_voice": self._enable_voice.isChecked(),
            "wake_word_default": self._wake_word.isChecked(),
            "default_mode": self._default_mode.currentText(),
        }


def open_settings(parent, current_settings: dict, theme: dict) -> dict | None:
    """
    Convenience: open the dialog, save on accept, return merged settings dict.
    Returns None if the user cancelled.
    Automatically calls save_app_settings() + apply_settings_to_env().
    """
    rec = recommend_runtime_profile()
    dlg = RuntimeSettingsDialog(current_settings, rec, theme, parent)
    if dlg.exec():
        payload = dlg.settings_payload()
        save_app_settings(payload)
        return apply_settings_to_env(payload)
    return None
