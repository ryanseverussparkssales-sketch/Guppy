"""
ElevenLabs TTS Provider
========================

Async wrapper around the ElevenLabs streaming TTS API. Requires
ELEVENLABS_API_KEY in environment to be active.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import urllib.request
from typing import Any, AsyncGenerator, Optional

from guppy.voice.core import TTSProvider, TTSResult

logger = logging.getLogger(__name__)


class ElevenLabsTTSProvider(TTSProvider):
    """ElevenLabs TTS via REST streaming API."""

    name = "elevenlabs_tts"

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_voice_id: str = "21m00Tcm4TlvDq8ikWAM",  # Rachel
        model_id: str = "eleven_turbo_v2_5",
        sample_rate: int = 22050,
    ):
        self._api_key = (api_key if api_key is not None else os.environ.get("ELEVENLABS_API_KEY", "")).strip()
        self._default_voice = default_voice_id
        self._model_id = model_id
        self._sample_rate = sample_rate

    async def health_check(self) -> bool:
        return bool(self._api_key)

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs: Any,
    ) -> TTSResult:
        start = time.monotonic()
        if not self._api_key:
            return TTSResult(
                audio_data=b"",
                provider=self.name,
                duration_ms=(time.monotonic() - start) * 1000.0,
                sample_rate=self._sample_rate,
                channels=1,
                format="mp3",
                playback_duration_s=0.0,
                error="elevenlabs_no_api_key",
            )
        try:
            audio = await asyncio.to_thread(self._synthesize_blocking, text, voice or self._default_voice)
        except Exception as e:
            logger.error("ElevenLabs synthesis failed: %s", e)
            return TTSResult(
                audio_data=b"",
                provider=self.name,
                duration_ms=(time.monotonic() - start) * 1000.0,
                sample_rate=self._sample_rate,
                channels=1,
                format="mp3",
                playback_duration_s=0.0,
                error=f"elevenlabs_error: {e}",
            )
        duration_ms = (time.monotonic() - start) * 1000.0
        # MP3 duration estimate: ~12 KB/s @ 96kbps; rough only
        playback_s = len(audio) / 12000.0 if audio else 0.0
        return TTSResult(
            audio_data=audio,
            provider=self.name,
            duration_ms=duration_ms,
            sample_rate=self._sample_rate,
            channels=1,
            format="mp3",
            playback_duration_s=playback_s,
            metadata={"voice_id": voice or self._default_voice, "model_id": self._model_id},
        )

    def _synthesize_blocking(self, text: str, voice_id: str) -> bytes:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
        payload = {
            "text": text,
            "model_id": self._model_id,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "xi-api-key": self._api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30.0) as r:
            return r.read()

    async def stream_synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[bytes, None]:
        # Real streaming requires async http client; current impl yields once
        result = await self.synthesize(text, voice, **kwargs)
        if result.audio_data and not result.error:
            yield result.audio_data
