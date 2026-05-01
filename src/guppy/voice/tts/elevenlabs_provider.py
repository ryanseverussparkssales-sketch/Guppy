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

# Module-level cache shared across all ElevenLabsTTSProvider instances
_voices_cache: list[dict] | None = None
_voices_cached_at: float = 0.0
_VOICES_CACHE_TTL = 300.0  # 5 minutes

ELEVENLABS_VOICES_DEFAULT = [
    {"id": "21m00Tcm4TlvDq8ikWAM", "name": "Rachel",  "lang": "en-us"},
    {"id": "AZnzlk1XvdvUeBnXmlld", "name": "Domi",    "lang": "en-us"},
    {"id": "EXAVITQu4vr4xnSDxMaL", "name": "Bella",   "lang": "en-us"},
    {"id": "ErXwobaYiN019PkySvjV",  "name": "Antoni",  "lang": "en-us"},
    {"id": "MF3mGyEYCl7XYWbV9V6O", "name": "Elli",    "lang": "en-us"},
    {"id": "VR6AewLTigWG4xSOukaG", "name": "Arnold",  "lang": "en-us"},
    {"id": "pNInz6obpgDQGcFmaJgB",  "name": "Adam",    "lang": "en-us"},
]


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

    def list_voices_sync(self) -> list[dict]:
        """Return the user's ElevenLabs voice library (blocking, cached 5 min)."""
        global _voices_cache, _voices_cached_at
        now = time.monotonic()
        if _voices_cache is not None and now - _voices_cached_at < _VOICES_CACHE_TTL:
            return _voices_cache
        if not self._api_key:
            return ELEVENLABS_VOICES_DEFAULT
        try:
            req = urllib.request.Request(
                "https://api.elevenlabs.io/v1/voices",
                headers={"xi-api-key": self._api_key, "Accept": "application/json"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            voices = data.get("voices", [])
            result = [
                {"id": v["voice_id"], "name": v["name"], "lang": "en-us"}
                for v in voices
                if v.get("voice_id") and v.get("name")
            ]
            _voices_cache = result or ELEVENLABS_VOICES_DEFAULT
            _voices_cached_at = now
            logger.debug("ElevenLabs: fetched %d voices", len(_voices_cache))
            return _voices_cache
        except Exception as exc:
            logger.warning("ElevenLabs voice fetch failed: %s", exc)
            _voices_cache = ELEVENLABS_VOICES_DEFAULT
            _voices_cached_at = now
            return ELEVENLABS_VOICES_DEFAULT

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

    def _stream_chunks_blocking(self, text: str, voice_id: str):
        """Blocking generator that yields 4-KB MP3 chunks from the streaming endpoint."""
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
            while True:
                chunk = r.read(4096)
                if not chunk:
                    break
                yield chunk

    async def stream_synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[bytes, None]:
        """True chunked streaming: yields 4-KB MP3 chunks as the ElevenLabs
        streaming endpoint delivers them."""
        if not self._api_key:
            return
        loop = asyncio.get_event_loop()
        it = iter(self._stream_chunks_blocking(text, voice or self._default_voice))
        while True:
            try:
                chunk = await loop.run_in_executor(None, next, it)
                yield chunk
            except StopIteration:
                break
            except Exception as e:
                logger.error("ElevenLabs stream_synthesize failed: %s", e)
                break
