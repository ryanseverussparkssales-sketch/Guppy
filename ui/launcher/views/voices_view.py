"""
ui/launcher/views/voices_view.py
VOICES tab — per-engine voice browser with preview and active-voice selection.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import importlib.util
from pathlib import Path
from typing import Any

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

from src.guppy.experience_config import (
    ensure_personalization_scaffold,
    list_model_ids,
    list_persona_choices,
    load_persona_config,
    load_provider_registry,
    load_voice_bindings,
    personalization_backend_available,
    save_voice_bindings,
    validate_voice_bindings,
)
from .. import tokens as T

try:
    from src.guppy.voice.voice import GuppyVoice
except Exception:
    GuppyVoice = None  # type: ignore[assignment]

_VOICE_BINDINGS_BACKEND = personalization_backend_available()

# ── Voice catalogues ──────────────────────────────────────────────────────────

EDGE_VOICES: list[tuple[str, str, str]] = [
    ("en-GB-RyanNeural",     "British English",     "Male"),
    ("en-GB-SoniaNeural",    "British English",     "Female"),
    ("en-US-JennyNeural",    "American English",    "Female"),
    ("en-US-GuyNeural",      "American English",    "Male"),
    ("en-US-AriaNeural",     "American English",    "Female"),
    ("en-US-DavisNeural",    "American English",    "Male"),
    ("en-AU-NatashaNeural",  "Australian English",  "Female"),
    ("en-AU-WilliamNeural",  "Australian English",  "Male"),
    ("en-CA-ClaraNeural",    "Canadian English",    "Female"),
    ("en-IE-ConnorNeural",   "Irish English",       "Male"),
]

KOKORO_VOICES: list[tuple[str, str, str]] = [
    ("af_bella",   "North American English", "Female"),
    ("af_nicole",  "North American English", "Female"),
    ("af_sarah",   "North American English", "Female"),
    ("am_adam",    "North American English", "Male"),
    ("am_michael", "North American English", "Male"),
    ("bf_emma",    "British English",        "Female"),
    ("bm_george",  "British English",        "Male"),
    ("bm_lewis",   "British English",        "Male"),
]

SAPI_VOICES: list[tuple[str, str, str]] = [
    ("Microsoft David Desktop",  "American English", "Male"),
    ("Microsoft Zira Desktop",   "American English", "Female"),
    ("Microsoft Mark Desktop",   "American English", "Male"),
    ("Microsoft Hazel Desktop",  "British English",  "Female"),
    ("Microsoft George Desktop", "British English",  "Male"),
]

ELEVENLABS_VOICES: list[tuple[str, str, str]] = [
    ("Rachel",   "American English", "Female"),
    ("Domi",     "American English", "Female"),
    ("Bella",    "American English", "Female"),
    ("Antoni",   "American English", "Male"),
    ("Thomas",   "American English", "Male"),
    ("Charlie",  "Australian English", "Male"),
    ("Emily",    "British English",    "Female"),
    ("Clyde",    "American English",   "Male"),
]

ENGINES: dict[str, list[tuple[str, str, str]]] = {
    "EDGE TTS":    EDGE_VOICES,
    "KOKORO":      KOKORO_VOICES,
    "WINDOWS SAPI": SAPI_VOICES,
    "ELEVENLABS":  ELEVENLABS_VOICES,
}

_PREVIEW_PHRASE = "Hey, I'm your AI assistant. How can I help you today?"

_LOGGER = logging.getLogger(__name__)

_PERSONA_OPTIONS = ["guppy"]
_MODEL_OPTIONS = [
    "guppy",
    "guppy-fast",
    "vault-scraper",
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-6",
]


class _VoiceRow(QFrame):
    def __init__(
        self,
        voice_id: str,
        display_name: str,
        language: str,
        gender: str,
        engine: str,
        preview_handler,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._voice_id = voice_id
        self._engine = engine
        self._preview_handler = preview_handler
        self.setObjectName("voice_row")
        self.setFixedHeight(52)
        self.setStyleSheet(
            f"QFrame#voice_row {{"
            f"  background-color: {T.BG1}; border: 1px solid {T.BORDER};"
            f"}}"
            f"QFrame#voice_row:hover {{ background-color: {T.BG2}; }}"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 0, 16, 0)
        row.setSpacing(12)

        # Voice name
        name_lbl = QLabel(display_name)
        name_lbl.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_BODY}pt; letter-spacing: 1px; border: none;"
        )
        name_lbl.setFixedWidth(220)
        row.addWidget(name_lbl)

        if display_name != voice_id:
            id_lbl = QLabel(voice_id)
            id_lbl.setStyleSheet(
                f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
                f"font-size: {T.FS_TINY}pt; letter-spacing: 1px; border: none;"
            )
            id_lbl.setFixedWidth(220)
            row.addWidget(id_lbl)

        # Language
        lang_lbl = QLabel(language)
        lang_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px; border: none;"
        )
        row.addWidget(lang_lbl)

        row.addStretch()

        # Gender badge
        gcolor = T.TERTIARY if gender == "Male" else T.SECONDARY
        g_lbl = QLabel(gender.upper())
        g_lbl.setStyleSheet(
            f"color: {gcolor}; background: transparent; border: 1px solid {gcolor};"
            f"font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
            f"letter-spacing: 1px; padding: 1px 6px;"
        )
        row.addWidget(g_lbl)

        # Preview button
        prev_btn = QPushButton("PREVIEW")
        prev_btn.setFixedSize(70, 26)
        prev_btn.setStyleSheet(
            f"QPushButton {{ color: {T.DIM}; border: 1px solid {T.BORDER};"
            f"  font-family: '{T.FF_MONO}'; font-size: 7pt; }}"
            f"QPushButton:hover {{ color: {T.TEXT}; border-color: {T.DIM}; }}"
        )
        prev_btn.clicked.connect(self._on_preview_clicked)
        row.addWidget(prev_btn)

        # Select button
        self._sel_btn = QPushButton("SELECT")
        self._sel_btn.setFixedSize(70, 26)
        self._sel_btn.setStyleSheet(
            f"QPushButton {{ color: {T.PRIMARY}; border: 1px solid {T.PRIMARY};"
            f"  font-family: '{T.FF_MONO}'; font-size: 7pt; }}"
            f"QPushButton:hover {{ background: rgba(242,202,80,0.12); }}"
        )
        row.addWidget(self._sel_btn)

        self._active_bar = QFrame()
        self._active_bar.setFixedSize(3, 52)
        self._active_bar.setStyleSheet("background: transparent;")
        row.insertWidget(0, self._active_bar)

    def mark_active(self, active: bool) -> None:
        c = T.PRIMARY if active else "transparent"
        self._active_bar.setStyleSheet(f"background: {c};")
        self._sel_btn.setText("ACTIVE" if active else "SELECT")
        self._sel_btn.setEnabled(not active)

    def _on_preview_clicked(self) -> None:
        try:
            self._preview_handler(self._engine, self._voice_id)
        except Exception as exc:
            _LOGGER.exception("Voice preview failed for %s/%s", self._engine, self._voice_id)
            parent = self.parent()
            emitter = getattr(parent, "preview_status", None)
            if emitter is not None and hasattr(emitter, "emit"):
                emitter.emit(f"preview failed: {exc}")

    @property
    def voice_id(self) -> str:
        return self._voice_id

    @property
    def select_btn(self) -> QPushButton:
        return self._sel_btn


class VoicesView(QWidget):
    bindings_changed = Signal(dict)
    preview_status = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._active_voice = os.environ.get("GUPPY_TTS_VOICE", "en-GB-RyanNeural")
        self._active_engine = "EDGE TTS"
        self._rows: list[_VoiceRow] = []
        self._voice_bindings: dict[str, Any] = {
            "version": 1,
            "defaults": {"engine": self._active_engine, "voice_id": self._active_voice},
            "bindings": {"by_model": {}, "by_persona": {}},
            "imports": [],
        }
        self._engine_capabilities: dict[str, dict[str, str]] = {}
        self._preview_generation = 0
        self._preview_lock = threading.Lock()
        self._pyttsx3_engine = None
        self._guppy_voice = None
        self._build_ui()
        self._refresh_engine_capabilities()
        self._load_voice_bindings_state()
        self._load_assignment_options()
        self._populate_voices(self._active_engine)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top control bar ───────────────────────────────────────────────────
        bar = QFrame()
        bar.setFixedHeight(64)
        bar.setObjectName("voices_topbar")
        bar.setStyleSheet(
            f"QFrame#voices_topbar {{"
            f"  background-color: {T.BG0}; border-bottom: 1px solid {T.BORDER};"
            f"}}"
        )
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(28, 0, 28, 0)
        bl.setSpacing(20)

        title = QLabel("VOICE LIBRARY")
        title.setStyleSheet(
            f"color: {T.PRIMARY}; font-family: '{T.FF_HEAD}';"
            f"font-size: {T.FS_TITLE}pt; font-weight: bold; letter-spacing: 2px;"
        )
        bl.addWidget(title)
        bl.addSpacing(24)

        engine_lbl = QLabel("ENGINE")
        engine_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 2px;"
        )
        bl.addWidget(engine_lbl)

        self._engine_cb = QComboBox()
        self._engine_cb.addItems(list(ENGINES.keys()))
        self._engine_cb.setFixedWidth(180)
        self._engine_cb.currentTextChanged.connect(self._populate_voices)
        bl.addWidget(self._engine_cb)

        self._engine_status_lbl = QLabel("ENGINES: probing...")
        self._engine_status_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        bl.addWidget(self._engine_status_lbl)
        bl.addStretch()

        self._default_lbl = QLabel("DEFAULT VOICE: loading...")
        self._default_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        bl.addWidget(self._default_lbl)
        bl.addSpacing(14)

        self._active_lbl = QLabel(f"ACTIVE VOICE: {self._describe_voice_choice(self._active_engine, self._active_voice)}")
        self._active_lbl.setStyleSheet(
            f"color: {T.PRIMARY_DIM}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 2px;"
        )
        bl.addWidget(self._active_lbl)

        self._save_default_btn = QPushButton("SAVE AS DEFAULT")
        self._save_default_btn.setFixedHeight(28)
        self._save_default_btn.clicked.connect(self._save_default_voice)
        bl.addSpacing(12)
        bl.addWidget(self._save_default_btn)

        root.addWidget(bar)

        # ── Guided assignment strip (persona/model) ─────────────────────────
        assign_bar = QFrame()
        assign_bar.setFixedHeight(62)
        assign_bar.setStyleSheet(
            f"QFrame {{ background-color: {T.BG0}; border-bottom: 1px solid {T.BORDER}; }}"
        )
        ab = QHBoxLayout(assign_bar)
        ab.setContentsMargins(28, 0, 28, 0)
        ab.setSpacing(10)

        p_lbl = QLabel("ASSIGN TO PERSONA")
        p_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        ab.addWidget(p_lbl)
        self._persona_cb = QComboBox()
        self._persona_cb.addItems(_PERSONA_OPTIONS)
        self._persona_cb.setFixedWidth(140)
        ab.addWidget(self._persona_cb)
        self._assign_persona_btn = QPushButton("ASSIGN")
        self._assign_persona_btn.setFixedHeight(28)
        self._assign_persona_btn.clicked.connect(self._assign_persona_voice)
        ab.addWidget(self._assign_persona_btn)

        ab.addSpacing(18)

        m_lbl = QLabel("ASSIGN TO MODEL")
        m_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        ab.addWidget(m_lbl)
        self._model_cb = QComboBox()
        self._model_cb.addItems(_MODEL_OPTIONS)
        self._model_cb.setFixedWidth(210)
        ab.addWidget(self._model_cb)
        self._assign_model_btn = QPushButton("ASSIGN")
        self._assign_model_btn.setFixedHeight(28)
        self._assign_model_btn.clicked.connect(self._assign_model_voice)
        ab.addWidget(self._assign_model_btn)

        ab.addStretch()
        self._assign_status = QLabel("Voice bindings ready")
        self._assign_status.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        self.preview_status.connect(self._assign_status.setText)
        ab.addWidget(self._assign_status)
        root.addWidget(assign_bar)

        manage_bar = QFrame()
        manage_bar.setStyleSheet(
            f"QFrame {{ background-color: {T.BG0}; border-bottom: 1px solid {T.BORDER}; }}"
        )
        mb = QVBoxLayout(manage_bar)
        mb.setContentsMargins(28, 10, 28, 10)
        mb.setSpacing(8)

        preview_row = QHBoxLayout()
        preview_row.setSpacing(10)
        preview_lbl = QLabel("PREVIEW PHRASE")
        preview_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        preview_row.addWidget(preview_lbl)
        self._preview_phrase_input = QLineEdit(_PREVIEW_PHRASE)
        self._preview_phrase_input.setStyleSheet(
            f"QLineEdit {{ background: {T.BG1}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
            f" font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; padding: 4px 8px; }}"
        )
        preview_row.addWidget(self._preview_phrase_input, stretch=1)
        self._stop_preview_btn = QPushButton("STOP PREVIEW")
        self._stop_preview_btn.setFixedHeight(28)
        self._stop_preview_btn.clicked.connect(self._cancel_preview)
        preview_row.addWidget(self._stop_preview_btn)
        mb.addLayout(preview_row)

        import_row = QHBoxLayout()
        import_row.setSpacing(10)
        import_lbl = QLabel("IMPORT VOICE")
        import_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        import_row.addWidget(import_lbl)
        self._import_engine_cb = QComboBox()
        self._import_engine_cb.addItems(list(ENGINES.keys()))
        import_row.addWidget(self._import_engine_cb)
        self._import_voice_id = QLineEdit()
        self._import_voice_id.setPlaceholderText("voice id")
        self._import_label = QLineEdit()
        self._import_label.setPlaceholderText("display label (optional)")
        for widget in (self._import_voice_id, self._import_label):
            widget.setStyleSheet(
                f"QLineEdit {{ background: {T.BG1}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
                f" font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; padding: 4px 8px; }}"
            )
        import_row.addWidget(self._import_voice_id)
        import_row.addWidget(self._import_label)
        self._import_btn = QPushButton("IMPORT")
        self._import_btn.setFixedHeight(28)
        self._import_btn.clicked.connect(self._import_voice)
        import_row.addWidget(self._import_btn)
        mb.addLayout(import_row)

        self._bindings_summary_lbl = QLabel("Voice sources: Using the default voice for everything right now.")
        self._bindings_summary_lbl.setWordWrap(True)
        self._bindings_summary_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        mb.addWidget(self._bindings_summary_lbl)
        self._voice_evidence_lbl = QLabel("Voice readiness appears here once Guppy loads bindings and engine status.")
        self._voice_evidence_lbl.setWordWrap(True)
        self._voice_evidence_lbl.setStyleSheet(
            f"color: {T.PRIMARY_DIM}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        mb.addWidget(self._voice_evidence_lbl)
        root.addWidget(manage_bar)

        # ── Voice list scrollable area ────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self._list_widget = QWidget()
        self._list_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(28, 20, 28, 24)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch()

        scroll.setWidget(self._list_widget)
        root.addWidget(scroll, stretch=1)

    def _refresh_engine_capabilities(self) -> None:
        caps: dict[str, dict[str, str]] = {}
        for engine in ENGINES.keys():
            ok, reason = self._engine_capability(engine)
            caps[engine] = {"ok": "1" if ok else "0", "reason": reason}
        self._engine_capabilities = caps
        self._update_engine_status_summary()

    @staticmethod
    def _engine_capability(engine: str) -> tuple[bool, str]:
        if engine == "EDGE TTS":
            ok = importlib.util.find_spec("edge_tts") is not None
            return ok, "edge-tts installed" if ok else "missing edge-tts"
        if engine == "KOKORO":
            ok = importlib.util.find_spec("kokoro") is not None or importlib.util.find_spec("kokoro_onnx") is not None
            return ok, "kokoro runtime detected" if ok else "kokoro runtime missing"
        if engine == "WINDOWS SAPI":
            if not sys.platform.startswith("win"):
                return False, "Windows only"
            ok = importlib.util.find_spec("pyttsx3") is not None
            return ok, "pyttsx3 available" if ok else "missing pyttsx3"
        if engine == "ELEVENLABS":
            api_key = (os.environ.get("ELEVENLABS_API_KEY", "") or "").strip()
            return bool(api_key), "API key present" if api_key else "missing ELEVENLABS_API_KEY"
        return False, "unknown engine"

    @staticmethod
    def _voice_exists_for_engine(engine: str, voice_id: str) -> bool:
        return any(v[0] == voice_id for v in ENGINES.get(engine, []))

    def _voice_records_for_engine(self, engine: str) -> list[dict[str, str]]:
        records: list[dict[str, str]] = []
        for voice_id, language, gender in ENGINES.get(engine, []):
            records.append(
                {
                    "voice_id": voice_id,
                    "display_name": voice_id,
                    "language": language,
                    "gender": gender,
                    "engine": engine,
                    "imported": "0",
                }
            )
        imports = self._voice_bindings.get("imports", []) if isinstance(self._voice_bindings, dict) else []
        if isinstance(imports, list):
            for item in imports:
                if not isinstance(item, dict):
                    continue
                item_engine = str(item.get("engine", "") or "").strip()
                voice_id = str(item.get("voice_id", "") or "").strip()
                if item_engine != engine or not voice_id:
                    continue
                records.append(
                    {
                        "voice_id": voice_id,
                        "display_name": str(item.get("label", "") or voice_id).strip() or voice_id,
                        "language": str(item.get("language", "Imported") or "Imported").strip(),
                        "gender": str(item.get("gender", "Custom") or "Custom").strip(),
                        "engine": engine,
                        "imported": "1",
                    }
                )
        deduped: dict[str, dict[str, str]] = {}
        for record in records:
            deduped[str(record.get("voice_id", ""))] = record
        return list(deduped.values())

    def _catalog_contains_voice(self, engine: str, voice_id: str) -> bool:
        return any(item.get("voice_id") == voice_id for item in self._voice_records_for_engine(engine))

    def _engine_is_available(self, engine: str) -> tuple[bool, str]:
        info = self._engine_capabilities.get(engine, {})
        ok = info.get("ok") == "1"
        reason = info.get("reason", "")
        return ok, reason

    def _validate_engine_selection(self, engine: str, voice_id: str) -> tuple[bool, str]:
        if not self._catalog_contains_voice(engine, voice_id):
            return False, f"voice {voice_id} not available for {engine}"
        ok, reason = self._engine_is_available(engine)
        if not ok:
            return False, f"{engine} unavailable: {reason}"
        return True, ""

    @staticmethod
    def _set_combo_options(combo: QComboBox, options: list[tuple[str, str]], *, selected: str = "") -> None:
        target = str(selected or combo.currentData() or combo.currentText()).strip().lower()
        combo.blockSignals(True)
        combo.clear()
        for label, value in options:
            combo.addItem(label, value)
        index = 0
        for idx in range(combo.count()):
            if str(combo.itemData(idx) or "").strip().lower() == target:
                index = idx
                break
        combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def _load_assignment_options(self) -> None:
        personas = list_persona_choices(load_persona_config())
        persona_options = [(item["name"], item["id"]) for item in personas]
        self._set_combo_options(self._persona_cb, persona_options, selected=str(self._persona_cb.currentData() or "guppy"))

        model_options = [(model_id, model_id) for model_id in list_model_ids(load_provider_registry())]
        self._set_combo_options(self._model_cb, model_options, selected=str(self._model_cb.currentData() or self._model_cb.currentText()))

    def _refresh_bindings_summary(self) -> None:
        bindings = self._voice_bindings.get("bindings", {}) if isinstance(self._voice_bindings, dict) else {}
        by_persona = bindings.get("by_persona", {}) if isinstance(bindings.get("by_persona"), dict) else {}
        by_model = bindings.get("by_model", {}) if isinstance(bindings.get("by_model"), dict) else {}
        imports = self._voice_bindings.get("imports", []) if isinstance(self._voice_bindings, dict) else []
        parts = [
            f"Default: {self._default_lbl.text().replace('DEFAULT VOICE: ', '').strip() or 'unset'}",
            f"Persona bindings: {len(by_persona)}",
            f"Model bindings: {len(by_model)}",
            f"Imports: {len(imports) if isinstance(imports, list) else 0}",
        ]
        self._bindings_summary_lbl.setText("Voice sources: " + " | ".join(parts))

    def _emit_bindings_changed(self) -> None:
        self.bindings_changed.emit(dict(self._voice_bindings))

    def _update_engine_status_summary(self) -> None:
        parts: list[str] = []
        for engine in ENGINES.keys():
            ok, _ = self._engine_is_available(engine)
            parts.append(f"{engine}:{'READY' if ok else 'UNAVAILABLE'}")
        self._engine_status_lbl.setText("ENGINES: " + " | ".join(parts))
        self._refresh_voice_evidence()

    def _update_default_label(self) -> None:
        defaults = self._voice_bindings.get("defaults", {}) if isinstance(self._voice_bindings, dict) else {}
        if isinstance(defaults, dict):
            engine = str(defaults.get("engine", "")).strip() or self._active_engine
            voice = str(defaults.get("voice_id", "")).strip() or self._active_voice
            self._default_lbl.setText(f"DEFAULT VOICE: {self._describe_voice_choice(engine, voice)}")
        self._refresh_voice_evidence()

    def _populate_voices(self, engine: str) -> None:
        # Clear current rows
        for row in self._rows:
            self._list_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

        voices = self._voice_records_for_engine(engine)
        for record in voices:
            voice_id = record.get("voice_id", "")
            row = _VoiceRow(
                voice_id,
                record.get("display_name", voice_id),
                record.get("language", "Imported"),
                record.get("gender", "Custom"),
                engine,
                self._preview_voice,
                self,
            )
            row.mark_active(voice_id == self._active_voice)
            row.select_btn.clicked.connect(lambda _, v=voice_id: self._select_voice(v))
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)
            self._rows.append(row)

        self._active_engine = engine
        ok, reason = self._engine_is_available(engine)
        if ok:
            self._assign_status.setText(f"{engine} is ready for preview and assignment.")
        else:
            self._assign_status.setText(f"{engine} is unavailable: {reason}")
        self._update_default_label()
        self._refresh_bindings_summary()
        self._refresh_voice_evidence()

    def _cancel_preview(self) -> None:
        self._preview_generation += 1
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass
        try:
            if self._pyttsx3_engine is not None:
                self._pyttsx3_engine.stop()
        except Exception:
            pass
        try:
            if self._guppy_voice is not None:
                self._guppy_voice.stop_tts()
        except Exception:
            pass

    def _preview_voice(self, engine: str, voice_id: str) -> None:
        valid, reason = self._validate_engine_selection(engine, voice_id)
        if not valid:
            self._assign_status.setText(reason)
            return
        self._cancel_preview()
        token = self._preview_generation
        self._assign_status.setText(f"Previewing {voice_id} with {engine}.")
        preview_text = self._preview_phrase_input.text().strip() or _PREVIEW_PHRASE

        def _run_preview() -> None:
            env_backup = {
                "GUPPY_TTS_PROVIDER": os.environ.get("GUPPY_TTS_PROVIDER"),
                "GUPPY_TTS_VOICE": os.environ.get("GUPPY_TTS_VOICE"),
            }
            try:
                if token != self._preview_generation:
                    return
                if engine == "EDGE TTS":
                    import asyncio
                    import io
                    import edge_tts  # type: ignore
                    import sounddevice as sd
                    import soundfile as sf

                    async def _do() -> None:
                        communicate = edge_tts.Communicate(preview_text, voice_id)
                        chunks: list[bytes] = []
                        async for chunk in communicate.stream():
                            if token != self._preview_generation:
                                return
                            if chunk.get("type") == "audio":
                                chunks.append(chunk["data"])
                        if not chunks or token != self._preview_generation:
                            return
                        buf = io.BytesIO(b"".join(chunks))
                        data, sample_rate = sf.read(buf, dtype="float32")
                        if token != self._preview_generation:
                            return
                        sd.play(data, sample_rate)

                    asyncio.run(_do())
                    return

                if GuppyVoice is None:
                    raise RuntimeError("GuppyVoice backend unavailable")
                provider_map = {
                    "KOKORO": "auto",
                    "WINDOWS SAPI": "sapi",
                    "ELEVENLABS": "elevenlabs",
                }
                os.environ["GUPPY_TTS_PROVIDER"] = provider_map.get(engine, "auto")
                os.environ["GUPPY_TTS_VOICE"] = voice_id
                voice_backend = GuppyVoice(default_voice=voice_id)
                self._guppy_voice = voice_backend
                voice_backend.speak(preview_text, voice=voice_id)
            except Exception as exc:
                self.preview_status.emit(f"preview failed: {exc}")
            finally:
                for key, value in env_backup.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
                self._pyttsx3_engine = None
                self._guppy_voice = None

        threading.Thread(target=_run_preview, daemon=True).start()

    def _select_voice(self, voice_id: str) -> None:
        valid, reason = self._validate_engine_selection(self._active_engine, voice_id)
        if not valid:
            self._assign_status.setText(reason)
            return
        self._active_voice = voice_id
        os.environ["GUPPY_TTS_VOICE"] = voice_id
        os.environ["GUPPY_TTS_ENGINE"] = self._active_engine
        self._active_lbl.setText(f"ACTIVE VOICE: {self._describe_voice_choice(self._active_engine, voice_id)}")
        for row in self._rows:
            row.mark_active(row.voice_id == voice_id)
        self._refresh_voice_evidence()

    def _load_voice_bindings_state(self) -> None:
        if not _VOICE_BINDINGS_BACKEND:
            self._assign_status.setText("voice bindings backend unavailable")
            return
        try:
            ensure_personalization_scaffold()
            data = load_voice_bindings()
            if isinstance(data, dict):
                self._voice_bindings = data
            defaults = self._voice_bindings.get("defaults", {})
            if isinstance(defaults, dict):
                self._active_engine = str(defaults.get("engine", self._active_engine))
                self._active_voice = str(defaults.get("voice_id", self._active_voice))
            idx = self._engine_cb.findText(self._active_engine)
            if idx >= 0:
                self._engine_cb.setCurrentIndex(idx)
            self._assign_status.setText("Voice choices loaded.")
            self._update_default_label()
            self._active_lbl.setText(f"ACTIVE VOICE: {self._describe_voice_choice(self._active_engine, self._active_voice)}")
            self._refresh_bindings_summary()
            self._refresh_voice_evidence()
        except Exception as e:
            self._assign_status.setText(f"load failed: {e}")

    def _save_voice_bindings_state(self) -> bool:
        if not _VOICE_BINDINGS_BACKEND:
            self._assign_status.setText("voice bindings backend unavailable")
            return False
        try:
            errors = validate_voice_bindings(self._voice_bindings)
            if errors:
                self._assign_status.setText(f"invalid bindings: {errors[0]}")
                return False
            save_voice_bindings(self._voice_bindings)
            self._refresh_bindings_summary()
            self._emit_bindings_changed()
            return True
        except Exception as e:
            self._assign_status.setText(f"save failed: {e}")
            return False

    def _save_default_voice(self) -> None:
        valid, reason = self._validate_engine_selection(self._active_engine, self._active_voice)
        if not valid:
            self._assign_status.setText(reason)
            return
        self._voice_bindings.setdefault("defaults", {})
        self._voice_bindings["defaults"] = {
            "engine": self._active_engine,
            "voice_id": self._active_voice,
        }
        if self._save_voice_bindings_state():
            os.environ["GUPPY_TTS_ENGINE"] = self._active_engine
            os.environ["GUPPY_TTS_VOICE"] = self._active_voice
            self._assign_status.setText(
                f"Default voice saved: {self._describe_voice_choice(self._active_engine, self._active_voice)}"
            )
            self._update_default_label()

    def _assign_persona_voice(self) -> None:
        valid, reason = self._validate_engine_selection(self._active_engine, self._active_voice)
        if not valid:
            self._assign_status.setText(reason)
            return
        persona = str(self._persona_cb.currentData() or self._persona_cb.currentText()).strip().lower()
        self._voice_bindings.setdefault("bindings", {})
        self._voice_bindings["bindings"].setdefault("by_persona", {})
        self._voice_bindings["bindings"]["by_persona"][persona] = {
            "engine": self._active_engine,
            "voice_id": self._active_voice,
        }
        if self._save_voice_bindings_state():
            self._assign_status.setText(
                f"Persona {persona} now uses {self._describe_voice_choice(self._active_engine, self._active_voice)}."
            )

    def _assign_model_voice(self) -> None:
        valid, reason = self._validate_engine_selection(self._active_engine, self._active_voice)
        if not valid:
            self._assign_status.setText(reason)
            return
        model = str(self._model_cb.currentData() or self._model_cb.currentText()).strip()
        self._voice_bindings.setdefault("bindings", {})
        self._voice_bindings["bindings"].setdefault("by_model", {})
        self._voice_bindings["bindings"]["by_model"][model] = {
            "engine": self._active_engine,
            "voice_id": self._active_voice,
        }
        if self._save_voice_bindings_state():
            self._assign_status.setText(
                f"Model {model} now uses {self._describe_voice_choice(self._active_engine, self._active_voice)}."
            )

    def _import_voice(self) -> None:
        engine = self._import_engine_cb.currentText().strip()
        voice_id = self._import_voice_id.text().strip()
        label = self._import_label.text().strip()
        if not engine or not voice_id:
            self._assign_status.setText("import requires engine and voice id")
            return
        imports = self._voice_bindings.setdefault("imports", [])
        if not isinstance(imports, list):
            imports = []
            self._voice_bindings["imports"] = imports
        imports = [
            item
            for item in imports
            if not (
                isinstance(item, dict)
                and str(item.get("engine", "")).strip() == engine
                and str(item.get("voice_id", "")).strip() == voice_id
            )
        ]
        imports.append(
            {
                "engine": engine,
                "voice_id": voice_id,
                "label": label or voice_id,
                "language": "Imported",
                "gender": "Custom",
            }
        )
        self._voice_bindings["imports"] = imports
        if self._save_voice_bindings_state():
            self._assign_status.setText(f"Imported {voice_id} into {engine}.")
            self._import_voice_id.clear()
            self._import_label.clear()
            if self._active_engine == engine:
                self._populate_voices(engine)

    @staticmethod
    def _describe_voice_choice(engine: str, voice_id: str) -> str:
        engine_text = str(engine or "").strip() or "Default engine"
        voice_text = str(voice_id or "").strip() or "default voice"
        return f"{voice_text} on {engine_text}"

    def _refresh_voice_evidence(self) -> None:
        ok, reason = self._engine_is_available(self._active_engine)
        readiness = "ready" if ok else f"needs attention ({reason})"
        bindings = self._voice_bindings.get("bindings", {}) if isinstance(self._voice_bindings, dict) else {}
        by_persona = bindings.get("by_persona", {}) if isinstance(bindings.get("by_persona"), dict) else {}
        by_model = bindings.get("by_model", {}) if isinstance(bindings.get("by_model"), dict) else {}
        self._voice_evidence_lbl.setText(
            f"Ready now: selected voice {self._describe_voice_choice(self._active_engine, self._active_voice)} is {readiness}. "
            f"Default runtime voice stays {self._default_lbl.text().replace('DEFAULT VOICE: ', '').strip() or 'unset'}. "
            f"Live bindings: {len(by_persona)} persona, {len(by_model)} model."
        )
