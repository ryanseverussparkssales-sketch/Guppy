"""
ui/launcher/views/settings_view.py
SETTINGS tab — identity fields, profile/mode dropdowns, runtime toggles,
neural sliders, visual toggles, API credentials, and save.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import tokens as T
from ..components.toggle_row import ToggleRow

try:
    from utils.runtime_profile import (
        load_app_settings,
        recommend_runtime_profile,
        save_app_settings,
        apply_settings_to_env,
    )
    _PROFILE_BACKEND = True
except Exception:
    _PROFILE_BACKEND = False

try:
    from utils.personalization_config import (
        ensure_personalization_scaffold,
        load_persona_config,
        load_provider_registry,
        load_voice_bindings,
        save_persona_config,
        save_provider_registry,
        save_voice_bindings,
        validate_persona_config,
        validate_provider_registry,
        validate_voice_bindings,
    )
    _PERSONALIZATION_BACKEND = True
except Exception:
    _PERSONALIZATION_BACKEND = False


def _section_header(title: str) -> QLabel:
    lbl = QLabel(title)
    lbl.setStyleSheet(
        f"color: {T.PRIMARY}; font-family: '{T.FF_HEAD}';"
        f"font-size: {T.FS_TITLE}pt; font-weight: bold; letter-spacing: 1px;"
        f"border-bottom: 1px solid {T.BORDER}; padding-bottom: 4px;"
    )
    return lbl


def _row_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
        f"font-size: {T.FS_SMALL}pt; letter-spacing: 1px;"
    )
    return lbl


class _SliderRow(QWidget):
    """Labelled horizontal slider with live value readout."""

    def __init__(
        self,
        label: str,
        lo: int = 0,
        hi: int = 100,
        default: int = 50,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 4, 0, 4)
        row.setSpacing(12)

        row.addWidget(_row_label(label))

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(lo, hi)
        self._slider.setValue(default)
        self._slider.setFixedWidth(180)
        self._slider.setStyleSheet(
            f"QSlider::groove:horizontal {{"
            f"  height: 4px; background: {T.BORDER}; border-radius: 2px;"
            f"}}"
            f"QSlider::handle:horizontal {{"
            f"  width: 12px; height: 12px; margin: -4px 0;"
            f"  background: {T.PRIMARY}; border-radius: 6px;"
            f"}}"
            f"QSlider::sub-page:horizontal {{"
            f"  background: {T.PRIMARY}; border-radius: 2px;"
            f"}}"
        )

        self._val_lbl = QLabel(str(default))
        self._val_lbl.setFixedWidth(30)
        self._val_lbl.setStyleSheet(
            f"color: {T.PRIMARY}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_SMALL}pt;"
        )
        self._slider.valueChanged.connect(lambda v: self._val_lbl.setText(str(v)))

        row.addStretch()
        row.addWidget(self._slider)
        row.addWidget(self._val_lbl)

    @property
    def value(self) -> int:
        return self._slider.value()

    def set_value(self, v: int) -> None:
        self._slider.setValue(v)


class SettingsView(QWidget):
    settings_saved = Signal(dict)
    recovery_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._persona_editor: QPlainTextEdit | None = None
        self._providers_editor: QPlainTextEdit | None = None
        self._voice_editor: QPlainTextEdit | None = None
        self._build_ui()
        self._load()
        self._load_personalization_editors()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(36, 28, 36, 28)
        layout.setSpacing(20)

        # ── Title ─────────────────────────────────────────────────────────────
        title = QLabel("Guppy AI Settings")
        title.setStyleSheet(
            f"color: {T.PRIMARY}; font-family: '{T.FF_HEAD}';"
            f"font-size: 22pt; font-weight: 900; letter-spacing: -1px;"
        )
        accent_bar = QFrame()
        accent_bar.setFixedSize(40, 2)
        accent_bar.setStyleSheet(f"background: {T.PRIMARY};")

        layout.addWidget(title)
        layout.addWidget(accent_bar)
        layout.addSpacing(10)

        # ── Identity section ──────────────────────────────────────────────────
        layout.addWidget(_section_header("CORE_IDENTITY"))

        # Display name
        name_row = QHBoxLayout()
        name_row.setSpacing(12)
        name_row.addWidget(_row_label("Display Name"))
        self._display_name = QLineEdit()
        self._display_name.setPlaceholderText("e.g. GUPPY_PRIME")
        self._display_name.setFixedWidth(200)
        self._display_name.setStyleSheet(
            f"QLineEdit {{ background-color: {T.BG0}; border: 1px solid {T.BORDER};"
            f"  color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt;"
            f"  padding: 3px 8px; }}"
            f"QLineEdit:focus {{ border-color: {T.PRIMARY}; }}"
        )
        name_row.addStretch()
        name_row.addWidget(self._display_name)
        layout.addLayout(name_row)

        # Personality matrix
        persona_row = QHBoxLayout()
        persona_row.setSpacing(12)
        persona_row.addWidget(_row_label("Personality Matrix"))
        self._cb_persona_matrix = QComboBox()
        self._cb_persona_matrix.addItems([
            "BUTLER_PROFESSIONAL", "ASSISTANT_CASUAL",
            "ANALYST_PRECISE", "MENTOR_SOCRATIC",
        ])
        self._cb_persona_matrix.setFixedWidth(200)
        persona_row.addStretch()
        persona_row.addWidget(self._cb_persona_matrix)
        layout.addLayout(persona_row)

        # Model core selector
        model_row = QHBoxLayout()
        model_row.setSpacing(12)
        model_row.addWidget(_row_label("Model Core"))
        self._cb_model_core = QComboBox()
        self._cb_model_core.addItems([
            "claude-sonnet-4-6", "claude-haiku-4-5-20251001", "claude-opus-4-6", "LOCAL_GUPPY",
        ])
        self._cb_model_core.setFixedWidth(200)
        model_row.addStretch()
        model_row.addWidget(self._cb_model_core)
        layout.addLayout(model_row)

        self._cb_profile = self._dropdown_row(layout, "Profile", ["LIGHT", "STANDARD", "POWER"])
        self._cb_mode    = self._dropdown_row(layout, "Mode",    ["AUTO", "CLAUDE", "OLLAMA", "TEACHING"])
        self._cb_surface = self._dropdown_row(layout, "Default Surface", ["GUPPY", "MERLIN", "COUNCIL"])

        # Last modified
        self._last_mod_lbl = QLabel("Last saved: —")
        self._last_mod_lbl.setStyleSheet(
            f"color: {T.BORDER}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
        )
        layout.addWidget(self._last_mod_lbl)

        layout.addSpacing(12)

        # ── Neural sliders ────────────────────────────────────────────────────
        layout.addWidget(_section_header("NEURAL_PARAMETERS"))

        self._s_creativity = _SliderRow("Creativity", 0, 100, 50)
        self._s_precision  = _SliderRow("Precision",  0, 100, 70)
        self._s_verbosity  = _SliderRow("Verbosity",  0, 100, 40)

        for s in [self._s_creativity, self._s_precision, self._s_verbosity]:
            layout.addWidget(s)

        layout.addSpacing(12)

        # ── Runtime flags ─────────────────────────────────────────────────────
        layout.addWidget(_section_header("RUNTIME_FLAGS"))

        self._t_daemon = ToggleRow("Daemon Background Execution", checked=True)
        self._t_voice  = ToggleRow("Voice Synthesis Feedback",    checked=True)
        self._t_wake   = ToggleRow("Active Wake-Word Detection",  checked=False)
        self._t_adv    = ToggleRow("Show Advanced Surfaces",       checked=True)

        for w in [self._t_daemon, self._t_voice, self._t_wake, self._t_adv]:
            layout.addWidget(w)

        layout.addSpacing(12)

        # ── Visual / UI toggles ───────────────────────────────────────────────
        layout.addWidget(_section_header("VISUAL_CONFIG"))

        self._t_high_contrast  = ToggleRow("High Contrast Mode",      checked=False)
        self._t_bg_gradients   = ToggleRow("Background Gradients",     checked=True)
        self._t_scanlines      = ToggleRow("Scanline Overlay",          checked=False)

        for w in [self._t_high_contrast, self._t_bg_gradients, self._t_scanlines]:
            layout.addWidget(w)

        layout.addSpacing(12)

        # ── API credentials ───────────────────────────────────────────────────
        layout.addWidget(_section_header("API_CREDENTIALS"))

        api_row = QHBoxLayout()
        api_row.setSpacing(12)
        api_row.addWidget(_row_label("Local API Key"))
        self._api_key = QLineEdit()
        self._api_key.setPlaceholderText("sk-...")
        self._api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key.setFixedWidth(260)
        self._api_key.setStyleSheet(
            f"QLineEdit {{ background-color: {T.BG0}; border: 1px solid {T.BORDER};"
            f"  color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt;"
            f"  padding: 3px 8px; }}"
            f"QLineEdit:focus {{ border-color: {T.PRIMARY}; }}"
        )
        api_row.addStretch()
        api_row.addWidget(self._api_key)
        layout.addLayout(api_row)

        layout.addSpacing(12)

        # ── Recovery actions ────────────────────────────────────────────────
        layout.addWidget(_section_header("RECOVERY"))

        rec_row = QHBoxLayout()
        rec_row.setSpacing(10)
        rec_actions = [
            ("SNAPSHOT", "health_snapshot", "Run /status + /startup/check?deep=true"),
            ("WARMUP", "warmup", "Warm startup/status readiness caches"),
            ("RESTART DAEMON", "restart_daemon", "Safely restart daemon manager"),
            ("COLLECT DIAGNOSTICS", "audit_runtime", "Collect latest stress + runtime status bundle"),
        ]
        for label, action, tip in rec_actions:
            btn = QPushButton(label)
            btn.setToolTip(tip)
            btn.setStyleSheet(
                f"QPushButton {{"
                f"  background-color: {T.BG0}; color: {T.DIM};"
                f"  border: 1px solid {T.BORDER}; padding: 6px 12px;"
                f"  font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
                f"}}"
                f"QPushButton:hover {{ border-color: {T.PRIMARY}; color: {T.PRIMARY}; }}"
            )
            btn.clicked.connect(lambda _=False, a=action: self.recovery_requested.emit(a))
            rec_row.addWidget(btn)
        rec_row.addStretch()
        layout.addLayout(rec_row)

        self._recovery_status = QLabel("Recovery idle")
        self._recovery_status.setStyleSheet(
            f"color: {T.BORDER}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
        )
        layout.addWidget(self._recovery_status)

        layout.addSpacing(12)

        # ── Personalization config tabs ─────────────────────────────────────
        layout.addWidget(_section_header("PERSONALIZATION CONFIG"))
        self._config_tabs = QTabWidget()
        self._config_tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: 1px solid {T.BORDER}; background: {T.BG0}; }}"
            f"QTabBar::tab {{ color: {T.DIM}; background: {T.BG1}; padding: 6px 10px;"
            f"  border: 1px solid {T.BORDER}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QTabBar::tab:selected {{ color: {T.PRIMARY}; border-color: {T.PRIMARY}; }}"
        )

        self._persona_editor = QPlainTextEdit()
        self._providers_editor = QPlainTextEdit()
        self._voice_editor = QPlainTextEdit()
        for editor in [self._persona_editor, self._providers_editor, self._voice_editor]:
            editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            editor.setMinimumHeight(220)
            editor.setStyleSheet(
                f"QPlainTextEdit {{ background: {T.BG0}; border: 1px solid {T.BORDER};"
                f" color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            )

        self._config_tabs.addTab(self._persona_editor, "PERSONAS")
        self._config_tabs.addTab(self._providers_editor, "PROVIDERS")
        self._config_tabs.addTab(self._voice_editor, "VOICES")
        layout.addWidget(self._config_tabs)

        cfg_btns = QHBoxLayout()
        cfg_btns.setSpacing(8)
        self._cfg_reload_btn = QPushButton("RELOAD")
        self._cfg_validate_btn = QPushButton("VALIDATE")
        self._cfg_save_btn = QPushButton("SAVE ACTIVE")
        for btn in [self._cfg_reload_btn, self._cfg_validate_btn, self._cfg_save_btn]:
            btn.setStyleSheet(
                f"QPushButton {{ background: {T.BG0}; color: {T.DIM}; border: 1px solid {T.BORDER};"
                f"  padding: 5px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ border-color: {T.PRIMARY}; color: {T.PRIMARY}; }}"
            )
        self._cfg_reload_btn.clicked.connect(self._load_personalization_editors)
        self._cfg_validate_btn.clicked.connect(self._validate_active_personalization_editor)
        self._cfg_save_btn.clicked.connect(self._save_active_personalization_editor)
        cfg_btns.addWidget(self._cfg_reload_btn)
        cfg_btns.addWidget(self._cfg_validate_btn)
        cfg_btns.addWidget(self._cfg_save_btn)
        cfg_btns.addStretch()
        self._cfg_status_lbl = QLabel("Personalization config idle")
        self._cfg_status_lbl.setStyleSheet(
            f"color: {T.BORDER}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
        )
        cfg_btns.addWidget(self._cfg_status_lbl)
        layout.addLayout(cfg_btns)

        layout.addStretch()

        # ── Save button ───────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._save_confirm = QLabel("")
        self._save_confirm.setStyleSheet(
            f"color: {T.GREEN}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
        )
        btn_row.addWidget(self._save_confirm)
        save_btn = QPushButton("SAVE SETTINGS  →")
        save_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {T.PRIMARY_DIM}; color: {T.BG};"
            f"  border: none; padding: 8px 24px;"
            f"  font-family: '{T.FF_HEAD}'; font-size: {T.FS_LABEL}pt; font-weight: bold;"
            f"  letter-spacing: 2px;"
            f"}}"
            f"QPushButton:hover {{ background-color: {T.PRIMARY}; }}"
        )
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        scroll.setWidget(content)
        outer.addWidget(scroll, stretch=1)

        # ── Hardware footer ───────────────────────────────────────────────────
        footer = QFrame()
        footer.setFixedHeight(34)
        footer.setObjectName("hw_footer")
        footer.setStyleSheet(
            f"QFrame#hw_footer {{"
            f"  background-color: {T.BG0}; border-top: 1px solid {T.BORDER};"
            f"}}"
        )
        frow = QHBoxLayout(footer)
        frow.setContentsMargins(20, 0, 20, 0)
        frow.setSpacing(20)
        self._hw_lbl = QLabel("Hardware: detecting...")
        self._hw_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
        )
        frow.addWidget(self._hw_lbl)
        frow.addStretch()
        outer.addWidget(footer)

    def _dropdown_row(
        self, layout: QVBoxLayout, label: str, options: list[str]
    ) -> QComboBox:
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(_row_label(label))
        row.addStretch()
        cb = QComboBox()
        cb.addItems(options)
        cb.setFixedWidth(200)
        row.addWidget(cb)
        layout.addLayout(row)
        return cb

    # ── Data I/O ──────────────────────────────────────────────────────────────
    def _load(self) -> None:
        if not _PROFILE_BACKEND:
            return
        try:
            s = load_app_settings()
            profiles = {"light": 0, "standard": 1, "power": 2}
            self._cb_profile.setCurrentIndex(profiles.get(s.get("runtime_profile", "standard"), 1))
            modes = {"auto": 0, "claude": 1, "ollama": 2, "teaching": 3}
            self._cb_mode.setCurrentIndex(modes.get(s.get("default_mode", "auto"), 0))
            surfaces = {"guppy": 0, "merlin": 1, "council": 2}
            self._cb_surface.setCurrentIndex(surfaces.get(s.get("default_surface", "guppy"), 0))
            self._t_daemon.setChecked(s.get("enable_daemon", True))
            self._t_voice.setChecked(s.get("enable_voice", True))
            self._t_wake.setChecked(s.get("wake_word_default", False))
            self._t_adv.setChecked(s.get("show_advanced_surfaces", True))

            # Sliders
            self._s_creativity.set_value(s.get("creativity", 50))
            self._s_precision.set_value(s.get("precision", 70))
            self._s_verbosity.set_value(s.get("verbosity", 40))

            # Identity
            self._display_name.setText(s.get("display_name", ""))
            persona_map = {
                "BUTLER_PROFESSIONAL": 0, "ASSISTANT_CASUAL": 1,
                "ANALYST_PRECISE": 2, "MENTOR_SOCRATIC": 3,
            }
            self._cb_persona_matrix.setCurrentIndex(
                persona_map.get(s.get("personality_matrix", "BUTLER_PROFESSIONAL"), 0)
            )

            # Visual
            self._t_high_contrast.setChecked(s.get("high_contrast", False))
            self._t_bg_gradients.setChecked(s.get("bg_gradients", True))
            self._t_scanlines.setChecked(s.get("scanlines", False))

            # Last saved timestamp
            ts = s.get("_saved_at", "")
            if ts:
                self._last_mod_lbl.setText(f"Last saved: {ts}")

            rec = recommend_runtime_profile()
            rec_profile = rec.get("profile", "standard") if isinstance(rec, dict) else str(rec)
            self._hw_lbl.setText(
                f"Recommended profile: {rec_profile.upper()} — press Save to apply"
            )
        except Exception:
            pass

    def _save(self) -> None:
        import time as _time
        profile_map = {0: "light", 1: "standard", 2: "power"}
        mode_map    = {0: "auto", 1: "claude",   2: "ollama",  3: "teaching"}
        surface_map = {0: "guppy", 1: "merlin", 2: "council"}
        persona_options = [
            "BUTLER_PROFESSIONAL", "ASSISTANT_CASUAL",
            "ANALYST_PRECISE", "MENTOR_SOCRATIC",
        ]
        model_options = [
            "claude-sonnet-4-6", "claude-haiku-4-5-20251001", "claude-opus-4-6", "LOCAL_GUPPY",
        ]

        ts = _time.strftime("%Y-%m-%d %H:%M:%S")
        payload = {
            "runtime_profile":        profile_map.get(self._cb_profile.currentIndex(), "standard"),
            "default_mode":           mode_map.get(self._cb_mode.currentIndex(), "auto"),
            "default_surface":        surface_map.get(self._cb_surface.currentIndex(), "guppy"),
            "enable_daemon":          self._t_daemon.is_checked,
            "enable_voice":           self._t_voice.is_checked,
            "wake_word_default":      self._t_wake.is_checked,
            "show_advanced_surfaces": self._t_adv.is_checked,
            # identity
            "display_name":           self._display_name.text().strip(),
            "personality_matrix":     persona_options[self._cb_persona_matrix.currentIndex()],
            "model_core":             model_options[self._cb_model_core.currentIndex()],
            # sliders
            "creativity":             self._s_creativity.value,
            "precision":              self._s_precision.value,
            "verbosity":              self._s_verbosity.value,
            # visual
            "high_contrast":          self._t_high_contrast.is_checked,
            "bg_gradients":           self._t_bg_gradients.is_checked,
            "scanlines":              self._t_scanlines.is_checked,
            "_saved_at":              ts,
        }

        if _PROFILE_BACKEND:
            try:
                save_app_settings(payload)
                apply_settings_to_env(payload)
            except Exception:
                pass

        self._last_mod_lbl.setText(f"Last saved: {ts}")
        self._save_confirm.setText("SAVED ✓")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(3000, lambda: self._save_confirm.setText(""))

        self.settings_saved.emit(payload)

    def set_hardware_label(self, text: str) -> None:
        self._hw_lbl.setText(text)

    def set_recovery_status(self, text: str) -> None:
        self._recovery_status.setText(text)

    def _set_cfg_status(self, text: str, ok: bool = True) -> None:
        color = T.GREEN if ok else T.ERROR
        self._cfg_status_lbl.setText(text)
        self._cfg_status_lbl.setStyleSheet(
            f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
        )

    def _active_personalization_slot(self) -> tuple[str, QPlainTextEdit | None]:
        idx = self._config_tabs.currentIndex()
        if idx == 0:
            return "persona", self._persona_editor
        if idx == 1:
            return "providers", self._providers_editor
        return "voice", self._voice_editor

    def _load_personalization_editors(self) -> None:
        if not _PERSONALIZATION_BACKEND:
            if getattr(self, "_cfg_status_lbl", None):
                self._set_cfg_status("Personalization backend unavailable", ok=False)
            return
        try:
            ensure_personalization_scaffold()
            if self._persona_editor is not None:
                self._persona_editor.setPlainText(__import__("json").dumps(load_persona_config(), indent=2))
            if self._providers_editor is not None:
                self._providers_editor.setPlainText(__import__("json").dumps(load_provider_registry(), indent=2))
            if self._voice_editor is not None:
                self._voice_editor.setPlainText(__import__("json").dumps(load_voice_bindings(), indent=2))
            if getattr(self, "_cfg_status_lbl", None):
                self._set_cfg_status("Personalization configs loaded", ok=True)
        except Exception as e:
            if getattr(self, "_cfg_status_lbl", None):
                self._set_cfg_status(f"Load failed: {e}", ok=False)

    def _validate_active_personalization_editor(self) -> None:
        if not _PERSONALIZATION_BACKEND:
            self._set_cfg_status("Personalization backend unavailable", ok=False)
            return
        slot, editor = self._active_personalization_slot()
        if editor is None:
            self._set_cfg_status("Editor unavailable", ok=False)
            return
        try:
            data = __import__("json").loads(editor.toPlainText() or "{}")
        except Exception as e:
            self._set_cfg_status(f"Invalid JSON: {e}", ok=False)
            return

        if slot == "persona":
            errors = validate_persona_config(data)
        elif slot == "providers":
            errors = validate_provider_registry(data)
        else:
            errors = validate_voice_bindings(data)

        if errors:
            self._set_cfg_status(f"{slot} invalid: {errors[0]}", ok=False)
        else:
            self._set_cfg_status(f"{slot} config valid", ok=True)

    def _save_active_personalization_editor(self) -> None:
        if not _PERSONALIZATION_BACKEND:
            self._set_cfg_status("Personalization backend unavailable", ok=False)
            return
        slot, editor = self._active_personalization_slot()
        if editor is None:
            self._set_cfg_status("Editor unavailable", ok=False)
            return
        try:
            data = __import__("json").loads(editor.toPlainText() or "{}")
        except Exception as e:
            self._set_cfg_status(f"Invalid JSON: {e}", ok=False)
            return

        if slot == "persona":
            errors = validate_persona_config(data)
            if errors:
                self._set_cfg_status(f"persona invalid: {errors[0]}", ok=False)
                return
            path = save_persona_config(data)
        elif slot == "providers":
            errors = validate_provider_registry(data)
            if errors:
                self._set_cfg_status(f"providers invalid: {errors[0]}", ok=False)
                return
            path = save_provider_registry(data)
        else:
            errors = validate_voice_bindings(data)
            if errors:
                self._set_cfg_status(f"voice invalid: {errors[0]}", ok=False)
                return
            path = save_voice_bindings(data)

        self._set_cfg_status(f"Saved {slot}: {path.name}", ok=True)
