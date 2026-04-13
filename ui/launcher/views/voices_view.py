"""
ui/launcher/views/voices_view.py
VOICES tab — per-engine voice browser with preview and active-voice selection.
"""
from __future__ import annotations

import os
import subprocess
import sys
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


class _VoiceRow(QFrame):
    def __init__(
        self,
        voice_id: str,
        language: str,
        gender: str,
        engine: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._voice_id = voice_id
        self._engine = engine
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
        prev_btn.clicked.connect(self._preview)
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

    def _preview(self) -> None:
        """Attempt a quick TTS preview using edge-tts or pyttsx3."""
        try:
            import threading

            def _speak() -> None:
                try:
                    import edge_tts, asyncio  # type: ignore

                    async def _do():
                        communicate = edge_tts.Communicate(_PREVIEW_PHRASE, self._voice_id)
                        import tempfile, sounddevice as sd, numpy as np, soundfile as sf, io
                        chunks: list[bytes] = []
                        async for chunk in communicate.stream():
                            if chunk["type"] == "audio":
                                chunks.append(chunk["data"])
                        buf = io.BytesIO(b"".join(chunks))
                        data, _ = sf.read(buf, dtype="float32")
                        sd.play(data)

                    asyncio.run(_do())
                except Exception:
                    try:
                        import pyttsx3
                        eng = pyttsx3.init()
                        eng.say(_PREVIEW_PHRASE)
                        eng.runAndWait()
                    except Exception:
                        pass

            threading.Thread(target=_speak, daemon=True).start()
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
        self._build_ui()
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
        bl.addStretch()

        self._active_lbl = QLabel(f"ACTIVE: {self._active_voice.upper()}")
        self._active_lbl.setStyleSheet(
            f"color: {T.PRIMARY_DIM}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 2px;"
        )
        bl.addWidget(self._active_lbl)

        root.addWidget(bar)

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

    def _populate_voices(self, engine: str) -> None:
        # Clear current rows
        for row in self._rows:
            self._list_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

        voices = ENGINES.get(engine, [])
        for vid, lang, gender in voices:
            row = _VoiceRow(vid, lang, gender, engine, self)
            row.mark_active(vid == self._active_voice)
            row.select_btn.clicked.connect(lambda _, v=vid: self._select_voice(v))
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)
            self._rows.append(row)

        self._active_engine = engine

    def _select_voice(self, voice_id: str) -> None:
        self._active_voice = voice_id
        os.environ["GUPPY_TTS_VOICE"] = voice_id
        self._active_lbl.setText(f"ACTIVE: {voice_id.upper()}")
        for row in self._rows:
            row.mark_active(row.voice_id == voice_id)
