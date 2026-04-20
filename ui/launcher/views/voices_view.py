"""
ui/launcher/views/voices_view.py
Voice panel used inside Models Hub for per-engine browsing, preview, and active-voice selection.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
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
from src.guppy.launcher_application.voice_catalog_support import (
    build_bindings_summary_text,
    build_engine_capabilities,
    build_engine_status_summary,
    build_voice_evidence_text,
    engine_capability,
    engine_is_available,
)
from .. import tokens as T
from .voices_sections import build_voices_ui

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
        prev_btn.setFixedSize(70, 28)
        prev_btn.setToolTip("Play a short audio sample of this voice")
        prev_btn.setStyleSheet(
            f"QPushButton {{ color: {T.DIM}; border: 1px solid {T.BORDER};"
            f"  font-family: '{T.FF_MONO}'; font-size: 7pt; }}"
            f"QPushButton:hover {{ color: {T.TEXT}; border-color: {T.DIM}; }}"
        )
        prev_btn.clicked.connect(self._on_preview_clicked)
        row.addWidget(prev_btn)

        # Select button
        self._sel_btn = QPushButton("SELECT")
        self._sel_btn.setFixedSize(70, 28)
        self._sel_btn.setToolTip("Set this voice as the active TTS voice for this workspace")
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
        build_voices_ui(
            self,
            engines=ENGINES,
            persona_options=_PERSONA_OPTIONS,
            model_options=_MODEL_OPTIONS,
            preview_phrase=_PREVIEW_PHRASE,
        )

    def _refresh_engine_capabilities(self) -> None:
        self._engine_capabilities = build_engine_capabilities(ENGINES)
        self._update_engine_status_summary()

    @staticmethod
    def _engine_capability(engine: str) -> tuple[bool, str]:
        return engine_capability(engine)

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
        return engine_is_available(self._engine_capabilities, engine)

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
        self._bindings_summary_lbl.setText(
            build_bindings_summary_text(
                self._voice_bindings,
                default_choice=self._default_lbl.text().replace("DEFAULT VOICE: ", "").strip(),
            )
        )

    def _emit_bindings_changed(self) -> None:
        self.bindings_changed.emit(dict(self._voice_bindings))

    def _update_engine_status_summary(self) -> None:
        self._engine_status_lbl.setText(build_engine_status_summary(ENGINES, self._engine_capabilities))
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
        self._voice_evidence_lbl.setText(
            build_voice_evidence_text(
                active_engine=self._active_engine,
                active_voice=self._active_voice,
                default_choice=self._default_lbl.text().replace("DEFAULT VOICE: ", "").strip(),
                describe_voice_choice=self._describe_voice_choice,
                voice_bindings=self._voice_bindings,
                engine_capabilities=self._engine_capabilities,
            )
        )

