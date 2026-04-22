from __future__ import annotations

import logging
import os
import queue
import threading
import time
from dataclasses import dataclass

try:
    from utils.env_bootstrap import load_env_file
except Exception:
    load_env_file = None

if callable(load_env_file):
    load_env_file()

try:
    import numpy as np
except Exception:
    np = None

try:
    import sounddevice as sd
except Exception:
    sd = None

try:
    import soundfile as sf
except Exception:
    sf = None

try:
    import requests
except Exception:
    requests = None

from . import voice_runtime as _runtime
from .voice_support import (
    build_backend_status,
    clean_for_tts,
    eleven_api_key,
    eleven_model_id,
    kokoro_speed_value,
    preferred_sapi_voice,
    resolve_kokoro_voice,
    sapi_rate_value,
    tts_provider_pref,
    win_hidden_popen_flags,
)


logger = logging.getLogger(__name__)
TTS_ENABLED = True


@dataclass(slots=True)
class VoiceConfig:
    tts_voice: str = "en-GB-RyanNeural"
    tts_rate: str = "+8%"
    tts_pitch: str = "+4Hz"
    stt_model: str = os.environ.get("GUPPY_WHISPER_MODEL", "large-v3")
    stt_fallback: str = "google"
    samplerate: int = 22050
    lang_code: str = "en-us"
    noise_reduction: bool = False
    min_silence_threshold: int = 150
    min_duration: float = 0.3
    max_duration: float = 45.0
    silence_cutoff: float = float(os.environ.get("GUPPY_SILENCE_CUTOFF", "0.7"))
    speech_threshold: float = float(os.environ.get("GUPPY_SPEECH_THRESHOLD", "0.01"))


class GuppyVoice:
    _whisper_singleton: "WhisperModel | None" = None  # type: ignore[name-defined]
    _whisper_singleton_name: str = ""

    def __init__(
        self,
        config: VoiceConfig | str | None = None,
        whisper_model: str = os.environ.get("GUPPY_WHISPER_MODEL", "large-v3"),
        sample_rate: int = 22050,
        lang_code: str = "en-us",
        default_voice: str = "bm_lewis",
    ):
        if isinstance(config, VoiceConfig):
            self.cfg = config
        elif isinstance(config, str):
            whisper_model = config
            self.cfg = VoiceConfig(
                stt_model=whisper_model,
                samplerate=sample_rate,
                lang_code=lang_code,
                tts_voice=default_voice,
            )
        else:
            self.cfg = VoiceConfig(
                stt_model=whisper_model,
                samplerate=sample_rate,
                lang_code=lang_code,
                tts_voice=default_voice,
            )

        self.sample_rate = int(self.cfg.samplerate)
        self.default_voice = self.cfg.tts_voice or default_voice
        self.whisper_model = None
        self.kokoro_pipeline = None
        self._whisper_error = ""
        self._tts_error = ""
        self._sr_module = None
        self.quiet_mode = False

        self.wake_words = [
            "guppy",
            "hey guppy",
            "butler",
            "copy",
            "gopi",
            "goppy",
            "gaby",
            "gabby",
            "hey copy",
            "hey gopi",
        ]
        self.is_listening_for_wake_word = False
        self.wake_word_thread = None
        self.wake_word_callback = None
        self._oww_available: bool | None = None

        self._is_speaking = False
        self.speaking_lock = threading.Lock()
        self._listening = threading.Event()
        self._stop_listening = threading.Event()
        self._stop_speaking = threading.Event()
        self._record_q: queue.Queue = queue.Queue()
        self._tts_process = None

        self._init_stt_backends()
        self._init_tts_backend()

    def _init_stt_backends(self) -> None:
        _runtime.init_stt_backends(self, GuppyVoice)

    def _init_tts_backend(self) -> None:
        _runtime.init_tts_backend(self)

    @staticmethod
    def _tts_provider_pref() -> str:
        return tts_provider_pref()

    @staticmethod
    def _eleven_model_id() -> str:
        return eleven_model_id()

    @staticmethod
    def _eleven_api_key() -> str:
        return eleven_api_key()

    def backend_status(self) -> dict:
        return build_backend_status(
            provider=self._tts_provider_pref(),
            eleven_ready=bool(self._eleven_api_key()) and requests is not None,
            has_kokoro=self.kokoro_pipeline is not None,
            has_whisper=self.whisper_model is not None,
            has_speech_recognition=self._sr_module is not None,
            oww_available=self._oww_available,
            wake_enabled=self.is_listening_for_wake_word,
            quiet_mode=self.quiet_mode,
            whisper_model_name=self.cfg.stt_model or "",
            tts_error=self._tts_error or "",
            stt_error=self._whisper_error or "",
        )

    def toggle_quiet(self) -> bool:
        self.quiet_mode = not self.quiet_mode
        return self.quiet_mode

    def _resolve_kokoro_voice(self, voice: str | None) -> str:
        return resolve_kokoro_voice(voice, self.default_voice)

    @staticmethod
    def _sapi_rate_value(rate_text: str | None) -> int:
        return sapi_rate_value(rate_text)

    @staticmethod
    def _preferred_sapi_voice(requested: str | None) -> str:
        return preferred_sapi_voice(requested)

    @staticmethod
    def _kokoro_speed_value(rate_text: str | None, base_speed: float = 1.0) -> float:
        return kokoro_speed_value(rate_text, base_speed)

    def _clear_record_queue(self) -> None:
        _runtime.clear_record_queue(self)

    def _record_worker(self, timeout: float | None = None) -> None:
        _runtime.record_worker(self, timeout=timeout)

    def _transcribe_file(self, audio_path: str) -> str:
        return _runtime.transcribe_file(self, audio_path)

    def _speak_with_kokoro(self, text: str, voice: str, speed: float) -> None:
        _runtime.speak_with_kokoro(self, text, voice, speed)

    def _speak_with_windows_tts(self, text: str, voice: str | None) -> None:
        _runtime.speak_with_windows_tts(
            self,
            text,
            voice,
            hidden_popen_flags=win_hidden_popen_flags,
            preferred_sapi_voice=preferred_sapi_voice,
            sapi_rate_value=sapi_rate_value,
        )

    def _speak_with_elevenlabs(self, text: str, voice: str | None) -> None:
        _runtime.speak_with_elevenlabs(
            self,
            text,
            voice,
            eleven_api_key=eleven_api_key,
            eleven_model_id=eleven_model_id,
        )

    def speak(self, text, voice=None, speed=1.0):
        if not TTS_ENABLED or self.quiet_mode:
            return

        text = clean_for_tts(str(text or ""))
        if not text:
            return

        self._stop_speaking.clear()
        with self.speaking_lock:
            self._is_speaking = True

        try:
            provider = self._tts_provider_pref()
            if provider == "elevenlabs":
                self._speak_with_elevenlabs(text, voice or self.default_voice)
            elif provider == "sapi":
                self._speak_with_windows_tts(text, voice or self.default_voice)
            elif self.kokoro_pipeline is not None:
                self._speak_with_kokoro(
                    text,
                    voice or self.default_voice,
                    self._kokoro_speed_value(self.cfg.tts_rate, speed),
                )
            elif provider == "auto" and self._eleven_api_key() and requests is not None:
                self._speak_with_elevenlabs(text, voice or self.default_voice)
            else:
                self._speak_with_windows_tts(text, voice or self.default_voice)

            if not self._stop_speaking.is_set():
                time.sleep(0.2)
        except Exception as exc:
            self._tts_error = str(exc)
        finally:
            with self.speaking_lock:
                self._is_speaking = False
            self._stop_speaking.clear()

    def stop_speaking(self):
        _runtime.stop_speaking(self)

    def stop_tts(self):
        self.stop_speaking()

    def stop_listening(self):
        self._stop_listening.set()

    def listen_once(self, timeout: float | None = None) -> dict:
        return _runtime.listen_once(self, timeout)

    def listen(self, duration=5, silence_threshold=0.01):
        del silence_threshold
        result = self.listen_once(timeout=duration)
        return result.get("text", "") if isinstance(result, dict) else ""

    def _wake_word_listener(self):
        _runtime.wake_word_listener(self)

    def _wake_word_listener_oww(self):
        _runtime.wake_word_listener_oww(self)

    def start_wake_word_detection(self, callback_function=None):
        _runtime.start_wake_word_detection(self, callback_function)

    def stop_wake_word_detection(self):
        _runtime.stop_wake_word_detection(self)

    def hold_to_talk(self, on_result=None):
        return _runtime.hold_to_talk(self, on_result)
