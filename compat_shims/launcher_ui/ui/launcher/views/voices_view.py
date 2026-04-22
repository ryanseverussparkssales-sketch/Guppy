"""
ui/launcher/views/voices_view.py
Voice panel used inside Models Hub for per-engine browsing, preview, and active-voice selection.
"""
from __future__ import annotations

import os
import threading
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget

from src.guppy.experience_config import (
    personalization_backend_available,
)
from src.guppy.launcher_application.voice_catalog_support import (
    build_engine_capabilities,
    build_engine_status_summary,
    build_voice_evidence_text,
    engine_capability,
    engine_is_available,
)
from .voices_bindings_support import (
    assign_model_voice,
    assign_persona_voice,
    emit_bindings_changed,
    import_voice,
    load_assignment_options,
    load_voice_bindings_state,
    refresh_bindings_summary,
    save_default_voice,
    save_voice_bindings_state,
    set_combo_options,
)
from .voices_sections import _VoiceRow, build_voices_ui

try:
    from src.guppy.voice.voice import GuppyVoice
except Exception:
    GuppyVoice = None  # type: ignore[assignment]

_VOICE_BINDINGS_BACKEND = personalization_backend_available()

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

_PERSONA_OPTIONS = ["guppy"]
_MODEL_OPTIONS = [
    "guppy",
    "guppy-fast",
    "vault-scraper",
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-6",
]


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
    def _provider_owner_note(engine: str) -> str:
        normalized = str(engine or "").strip().upper()
        if normalized == "ELEVENLABS":
            return " Add or update the ElevenLabs key in Settings > Device & Accounts."
        return ""

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
        set_combo_options(combo, options, selected=selected)

    def _load_assignment_options(self) -> None:
        load_assignment_options(self)

    def _refresh_bindings_summary(self) -> None:
        refresh_bindings_summary(self)

    def _emit_bindings_changed(self) -> None:
        emit_bindings_changed(self)

    def _update_engine_status_summary(self) -> None:
        self._engine_status_lbl.setText(build_engine_status_summary(ENGINES, self._engine_capabilities))
        ownership_tooltip = (
            "Voice readiness is shown here inside Models. "
            "Provider keys and account sign-in stay in Settings > Device & Accounts."
        )
        self._engine_status_lbl.setToolTip(ownership_tooltip)
        self._voice_evidence_lbl.setToolTip(ownership_tooltip)
        self._assign_status.setToolTip(ownership_tooltip)
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
            self._assign_status.setText(f"{engine} is unavailable: {reason}.{self._provider_owner_note(engine)}".strip())
        self._update_default_label()
        self._refresh_bindings_summary()
        self._refresh_voice_evidence()

    def _cancel_preview(self) -> None:
        self._cancel_preview_with_status()

    def _cancel_preview_with_status(self, *, announce: bool = True) -> None:
        had_preview = (
            "previewing " in self._assign_status.text().strip().lower()
            or self._guppy_voice is not None
        )
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
        if announce and had_preview:
            self.preview_status.emit("Preview stopped.")

    def _preview_is_current(self, token: int) -> bool:
        return token == self._preview_generation

    def _emit_preview_status_if_current(self, token: int, message: str) -> None:
        if self._preview_is_current(token):
            self.preview_status.emit(message)

    def _speak_preview_with_voice_backend(
        self,
        *,
        token: int,
        engine: str,
        voice_id: str,
        preview_text: str,
    ) -> None:
        if GuppyVoice is None:
            raise RuntimeError("GuppyVoice backend unavailable")

        provider_map = {
            "KOKORO": "auto",
            "WINDOWS SAPI": "sapi",
            "ELEVENLABS": "elevenlabs",
        }
        env_backup = {
            "GUPPY_TTS_PROVIDER": os.environ.get("GUPPY_TTS_PROVIDER"),
            "GUPPY_TTS_VOICE": os.environ.get("GUPPY_TTS_VOICE"),
        }
        voice_backend = None
        try:
            if not self._preview_is_current(token):
                return
            os.environ["GUPPY_TTS_PROVIDER"] = provider_map.get(engine, "auto")
            os.environ["GUPPY_TTS_VOICE"] = voice_id
            voice_backend = GuppyVoice(default_voice=voice_id)
            self._guppy_voice = voice_backend
            voice_backend.speak(preview_text, voice=voice_id)
        finally:
            for key, value in env_backup.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            if self._guppy_voice is voice_backend:
                self._guppy_voice = None

    def _preview_voice(self, engine: str, voice_id: str) -> None:
        valid, reason = self._validate_engine_selection(engine, voice_id)
        if not valid:
            self._assign_status.setText(reason)
            return
        self._cancel_preview_with_status(announce=False)
        token = self._preview_generation
        self._assign_status.setText(f"Previewing {voice_id} with {engine}.")
        preview_text = self._preview_phrase_input.text().strip() or _PREVIEW_PHRASE

        def _run_preview() -> None:
            try:
                with self._preview_lock:
                    if not self._preview_is_current(token):
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
                                if not self._preview_is_current(token):
                                    return
                                if chunk.get("type") == "audio":
                                    chunks.append(chunk["data"])
                            if not chunks or not self._preview_is_current(token):
                                return
                            buf = io.BytesIO(b"".join(chunks))
                            data, sample_rate = sf.read(buf, dtype="float32")
                            if not self._preview_is_current(token):
                                return
                            sd.play(data, sample_rate)

                        asyncio.run(_do())
                    else:
                        self._speak_preview_with_voice_backend(
                            token=token,
                            engine=engine,
                            voice_id=voice_id,
                            preview_text=preview_text,
                        )
                self._emit_preview_status_if_current(
                    token,
                    f"Preview finished for {self._describe_voice_choice(engine, voice_id)}.",
                )
            except Exception as exc:
                self._emit_preview_status_if_current(token, f"preview failed: {exc}")
            finally:
                self._pyttsx3_engine = None

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
        load_voice_bindings_state(self, backend_available=_VOICE_BINDINGS_BACKEND)

    def _save_voice_bindings_state(self) -> bool:
        return save_voice_bindings_state(self, backend_available=_VOICE_BINDINGS_BACKEND)

    def _save_default_voice(self) -> None:
        if save_default_voice(self, backend_available=_VOICE_BINDINGS_BACKEND):
            os.environ["GUPPY_TTS_ENGINE"] = self._active_engine
            os.environ["GUPPY_TTS_VOICE"] = self._active_voice

    def _assign_persona_voice(self) -> None:
        assign_persona_voice(self, backend_available=_VOICE_BINDINGS_BACKEND)

    def _assign_model_voice(self) -> None:
        assign_model_voice(self, backend_available=_VOICE_BINDINGS_BACKEND)

    def _import_voice(self) -> None:
        import_voice(self, backend_available=_VOICE_BINDINGS_BACKEND)

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

