"""
SAPI TTS Provider
==================

Async wrapper around Windows Speech API (SAPI5) text-to-speech via
the `pyttsx3` package or direct PowerShell SAPI invocation. Reliable
offline fallback when neural providers (Kokoro, ElevenLabs) are
unavailable.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, AsyncGenerator, Optional

from guppy.voice.core import TTSProvider, TTSResult

logger = logging.getLogger(__name__)


class SAPITTSProvider(TTSProvider):
    """Windows SAPI5 TTS via pyttsx3 (preferred) or PowerShell fallback."""

    name = "sapi_tts"

    def __init__(self, sample_rate: int = 22050):
        self._sample_rate = sample_rate
        self._engine_kind: Optional[str] = None  # 'pyttsx3' | 'powershell' | None
        self._available: Optional[bool] = None

    async def health_check(self) -> bool:
        if self._available is not None:
            return self._available
        self._available = await asyncio.to_thread(self._detect_engine) is not None
        return self._available

    def _detect_engine(self) -> Optional[str]:
        if sys.platform != "win32":
            self._engine_kind = None
            return None
        try:
            import pyttsx3  # type: ignore  # noqa: F401
            self._engine_kind = "pyttsx3"
            return "pyttsx3"
        except Exception:
            pass
        if shutil.which("powershell"):
            self._engine_kind = "powershell"
            return "powershell"
        self._engine_kind = None
        return None

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs: Any,
    ) -> TTSResult:
        start = time.monotonic()
        if not await self.health_check():
            return TTSResult(
                audio_data=b"",
                provider=self.name,
                duration_ms=(time.monotonic() - start) * 1000.0,
                sample_rate=self._sample_rate,
                channels=1,
                format="wav",
                playback_duration_s=0.0,
                error="sapi_not_available",
            )

        rate = int(kwargs.get("rate", 0))  # -10..10 in SAPI; 0 = default
        try:
            if self._engine_kind == "pyttsx3":
                audio = await asyncio.to_thread(self._synth_pyttsx3, text, voice, rate)
            else:
                audio = await asyncio.to_thread(self._synth_powershell, text, voice, rate)
        except Exception as e:
            logger.error("SAPI synthesis failed: %s", e)
            return TTSResult(
                audio_data=b"",
                provider=self.name,
                duration_ms=(time.monotonic() - start) * 1000.0,
                sample_rate=self._sample_rate,
                channels=1,
                format="wav",
                playback_duration_s=0.0,
                error=f"sapi_error: {e}",
            )

        duration_ms = (time.monotonic() - start) * 1000.0
        return TTSResult(
            audio_data=audio,
            provider=self.name,
            duration_ms=duration_ms,
            sample_rate=self._sample_rate,
            channels=1,
            format="wav",
            playback_duration_s=self._estimate_duration_s(audio),
            metadata={"engine": self._engine_kind, "voice": voice, "rate": rate},
        )

    def _synth_pyttsx3(self, text: str, voice: Optional[str], rate: int) -> bytes:
        import pyttsx3  # type: ignore
        engine = pyttsx3.init()
        if voice:
            for v in engine.getProperty("voices"):
                if voice.lower() in str(v.name).lower() or voice == v.id:
                    engine.setProperty("voice", v.id)
                    break
        if rate:
            base = engine.getProperty("rate")
            engine.setProperty("rate", base + rate * 20)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            path = tf.name
        try:
            engine.save_to_file(text, path)
            engine.runAndWait()
            with open(path, "rb") as f:
                return f.read()
        finally:
            try:
                os.unlink(path)
            except Exception:
                pass

    def _synth_powershell(self, text: str, voice: Optional[str], rate: int) -> bytes:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            path = tf.name
        try:
            voice_select = ""
            if voice:
                voice_select = f"$s.SelectVoice('{voice}');"
            ps = (
                "Add-Type -AssemblyName System.Speech; "
                "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                f"{voice_select}"
                f"$s.Rate = {rate}; "
                f"$s.SetOutputToWaveFile('{path}'); "
                f"$s.Speak({_ps_quote(text)}); "
                "$s.Dispose();"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                check=True, timeout=30,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )
            with open(path, "rb") as f:
                return f.read()
        finally:
            try:
                os.unlink(path)
            except Exception:
                pass

    def _estimate_duration_s(self, audio: bytes) -> float:
        if len(audio) <= 44:
            return 0.0
        return (len(audio) - 44) / (2 * self._sample_rate)

    async def stream_synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[bytes, None]:
        result = await self.synthesize(text, voice, **kwargs)
        if result.audio_data and not result.error:
            yield result.audio_data


def _ps_quote(s: str) -> str:
    """Single-quote a string for PowerShell, escaping embedded quotes."""
    return "'" + s.replace("'", "''") + "'"
