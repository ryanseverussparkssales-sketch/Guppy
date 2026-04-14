"""
ui/launcher/views/voices_view.py
VOICES tab — per-engine voice browser with preview and active-voice selection.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import importlib.util
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
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

from .. import tokens as T

try:
    from utils.personalization_config import (
        ensure_personalization_scaffold,
        load_voice_bindings,
        save_voice_bindings,
        validate_voice_bindings,
    )
    _VOICE_BINDINGS_BACKEND = True
except Exception:
    _VOICE_BINDINGS_BACKEND = False

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

_PERSONA_OPTIONS = ["guppy", "merlin", "council"]
_MODEL_OPTIONS = [
    "guppy",
    "merlin",
    "guppy-fast",
    "merlin-code",
    "vault-scraper",
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-6",
]


class _VoiceRow(QFrame):
    def __init__(
        self,
        voice_id: str,
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
        name_lbl = QLabel(voice_id)
        name_lbl.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_BODY}pt; letter-spacing: 1px; border: none;"
        )
        name_lbl.setFixedWidth(220)
        row.addWidget(name_lbl)

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
        except Exception:
            pass

    @property
    def voice_id(self) -> str:
        return self._voice_id

    @property
    def select_btn(self) -> QPushButton:
        return self._sel_btn


class VoicesView(QWidget):
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
        self._build_ui()
        self._refresh_engine_capabilities()
        self._load_voice_bindings_state()
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

        self._default_lbl = QLabel("DEFAULT: —")
        self._default_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        bl.addWidget(self._default_lbl)
        bl.addSpacing(14)

        self._active_lbl = QLabel(f"ACTIVE: {self._active_voice.upper()}")
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
        ab.addWidget(self._assign_status)
        root.addWidget(assign_bar)

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

    def _engine_is_available(self, engine: str) -> tuple[bool, str]:
        info = self._engine_capabilities.get(engine, {})
        ok = info.get("ok") == "1"
        reason = info.get("reason", "")
        return ok, reason

    def _validate_engine_selection(self, engine: str, voice_id: str) -> tuple[bool, str]:
        if not self._voice_exists_for_engine(engine, voice_id):
            return False, f"voice {voice_id} not available for {engine}"
        ok, reason = self._engine_is_available(engine)
        if not ok:
            return False, f"{engine} unavailable: {reason}"
        return True, ""

    def _update_engine_status_summary(self) -> None:
        parts: list[str] = []
        for engine in ENGINES.keys():
            ok, _ = self._engine_is_available(engine)
            parts.append(f"{engine}:{'READY' if ok else 'UNAVAILABLE'}")
        self._engine_status_lbl.setText("ENGINES: " + " | ".join(parts))

    def _update_default_label(self) -> None:
        defaults = self._voice_bindings.get("defaults", {}) if isinstance(self._voice_bindings, dict) else {}
        if isinstance(defaults, dict):
            engine = str(defaults.get("engine", "")).strip() or self._active_engine
            voice = str(defaults.get("voice_id", "")).strip() or self._active_voice
            self._default_lbl.setText(f"DEFAULT: {engine} / {voice}")

    def _populate_voices(self, engine: str) -> None:
        # Clear current rows
        for row in self._rows:
            self._list_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

        voices = ENGINES.get(engine, [])
        for vid, lang, gender in voices:
            row = _VoiceRow(vid, lang, gender, engine, self._preview_voice, self)
            row.mark_active(vid == self._active_voice)
            row.select_btn.clicked.connect(lambda _, v=vid: self._select_voice(v))
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)
            self._rows.append(row)

        self._active_engine = engine
        ok, reason = self._engine_is_available(engine)
        if ok:
            self._assign_status.setText(f"{engine} ready")
        else:
            self._assign_status.setText(f"{engine} unavailable: {reason}")

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

    def _preview_voice(self, engine: str, voice_id: str) -> None:
        valid, reason = self._validate_engine_selection(engine, voice_id)
        if not valid:
            self._assign_status.setText(reason)
            return
        self._cancel_preview()
        token = self._preview_generation
        self._assign_status.setText(f"previewing {voice_id} via {engine}")

        def _run_preview() -> None:
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
                        communicate = edge_tts.Communicate(_PREVIEW_PHRASE, voice_id)
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

                import pyttsx3
                eng = pyttsx3.init()
                self._pyttsx3_engine = eng
                try:
                    for voice in eng.getProperty("voices"):
                        vid = str(getattr(voice, "id", ""))
                        vname = str(getattr(voice, "name", ""))
                        if voice_id.lower() in vid.lower() or voice_id.lower() in vname.lower():
                            eng.setProperty("voice", vid)
                            break
                except Exception:
                    pass
                if token != self._preview_generation:
                    return
                eng.say(_PREVIEW_PHRASE)
                eng.runAndWait()
            except Exception as exc:
                self._assign_status.setText(f"preview failed: {exc}")
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
        self._active_lbl.setText(f"ACTIVE: {voice_id.upper()}")
        for row in self._rows:
            row.mark_active(row.voice_id == voice_id)

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
            self._assign_status.setText("voice bindings loaded")
            self._update_default_label()
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
            self._assign_status.setText(
                f"default saved: {self._active_engine} / {self._active_voice}"
            )
            self._update_default_label()

    def _assign_persona_voice(self) -> None:
        valid, reason = self._validate_engine_selection(self._active_engine, self._active_voice)
        if not valid:
            self._assign_status.setText(reason)
            return
        persona = self._persona_cb.currentText().strip().lower()
        self._voice_bindings.setdefault("bindings", {})
        self._voice_bindings["bindings"].setdefault("by_persona", {})
        self._voice_bindings["bindings"]["by_persona"][persona] = {
            "engine": self._active_engine,
            "voice_id": self._active_voice,
        }
        if self._save_voice_bindings_state():
            self._assign_status.setText(f"persona {persona} -> {self._active_voice}")

    def _assign_model_voice(self) -> None:
        valid, reason = self._validate_engine_selection(self._active_engine, self._active_voice)
        if not valid:
            self._assign_status.setText(reason)
            return
        model = self._model_cb.currentText().strip()
        self._voice_bindings.setdefault("bindings", {})
        self._voice_bindings["bindings"].setdefault("by_model", {})
        self._voice_bindings["bindings"]["by_model"][model] = {
            "engine": self._active_engine,
            "voice_id": self._active_voice,
        }
        if self._save_voice_bindings_state():
            self._assign_status.setText(f"model {model} -> {self._active_voice}")
