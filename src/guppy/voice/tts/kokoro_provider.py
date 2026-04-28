"""
Kokoro TTS Provider
====================

Async wrapper around the Kokoro TTS pipeline. Supports two modes:
1. Kokoro HTTP API (preferred when GUPPY_KOKORO_API_URL is set or default reachable)
2. Local Kokoro KPipeline (fallback, requires `kokoro` package)

Provides clean async/await semantics over what is otherwise a blocking
synthesis call.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import time
import urllib.request
from typing import Any, AsyncGenerator, Optional

from guppy.voice.core import TTSProvider, TTSResult

logger = logging.getLogger(__name__)

_DEFAULT_API_URL = "http://127.0.0.1:8880/v1/audio/speech"


class KokoroTTSProvider(TTSProvider):
    """Kokoro TTS via HTTP API or local pipeline."""

    name = "kokoro_tts"

    def __init__(
        self,
        api_url: Optional[str] = None,
        local_lang_code: str = "a",  # 'a'=US English
        sample_rate: int = 24000,
    ):
        self._api_url = (api_url or os.environ.get("GUPPY_KOKORO_API_URL") or _DEFAULT_API_URL).rstrip("/")
        self._local_lang_code = local_lang_code
        self._sample_rate = sample_rate
        self._pipeline = None  # lazy-loaded local pipeline
        self._mode: Optional[str] = None  # 'api' | 'local' | None (unhealthy)

    async def _detect_mode(self) -> Optional[str]:
        """Probe API first, fall back to local pipeline import."""
        if self._mode is not None:
            return self._mode
        if await asyncio.to_thread(self._probe_api):
            self._mode = "api"
            logger.info("Kokoro: using HTTP API at %s", self._api_url)
            return "api"
        if await asyncio.to_thread(self._load_local):
            self._mode = "local"
            logger.info("Kokoro: using local KPipeline")
            return "local"
        self._mode = None
        return None

    def _probe_api(self) -> bool:
        try:
            url = self._api_url.replace("/v1/audio/speech", "/v1/models")
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as r:
                return r.status == 200
        except Exception:
            return False

    def _load_local(self) -> bool:
        try:
            from kokoro import KPipeline  # type: ignore
            self._pipeline = KPipeline(lang_code=self._local_lang_code, device="cpu")
            return True
        except Exception as e:
            logger.debug("Kokoro local pipeline unavailable: %s", e)
            return False

    async def health_check(self) -> bool:
        return await self._detect_mode() is not None

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs: Any,
    ) -> TTSResult:
        start = time.monotonic()
        mode = await self._detect_mode()
        if mode == "api":
            try:
                audio = await asyncio.to_thread(self._synthesize_api, text, voice or "af_bella", float(kwargs.get("speed", 1.0)))
                duration_ms = (time.monotonic() - start) * 1000.0
                return TTSResult(
                    audio_data=audio,
                    provider=self.name,
                    duration_ms=duration_ms,
                    sample_rate=self._sample_rate,
                    channels=1,
                    format="wav",
                    playback_duration_s=self._estimate_duration_s(audio),
                    metadata={"mode": "api", "voice": voice or "af_bella"},
                )
            except Exception as e:
                logger.error("Kokoro API synthesis failed: %s", e)
                return TTSResult(
                    audio_data=b"",
                    provider=self.name,
                    duration_ms=(time.monotonic() - start) * 1000.0,
                    sample_rate=self._sample_rate,
                    channels=1,
                    format="wav",
                    playback_duration_s=0.0,
                    error=f"kokoro_api_error: {e}",
                )
        if mode == "local":
            try:
                audio = await asyncio.to_thread(self._synthesize_local, text, voice or "af_bella", float(kwargs.get("speed", 1.0)))
                duration_ms = (time.monotonic() - start) * 1000.0
                return TTSResult(
                    audio_data=audio,
                    provider=self.name,
                    duration_ms=duration_ms,
                    sample_rate=self._sample_rate,
                    channels=1,
                    format="pcm",
                    playback_duration_s=self._estimate_duration_s(audio, format_="pcm"),
                    metadata={"mode": "local", "voice": voice or "af_bella"},
                )
            except Exception as e:
                logger.error("Kokoro local synthesis failed: %s", e)
                return TTSResult(
                    audio_data=b"",
                    provider=self.name,
                    duration_ms=(time.monotonic() - start) * 1000.0,
                    sample_rate=self._sample_rate,
                    channels=1,
                    format="pcm",
                    playback_duration_s=0.0,
                    error=f"kokoro_local_error: {e}",
                )
        return TTSResult(
            audio_data=b"",
            provider=self.name,
            duration_ms=(time.monotonic() - start) * 1000.0,
            sample_rate=self._sample_rate,
            channels=1,
            format="wav",
            playback_duration_s=0.0,
            error="kokoro_not_available",
        )

    def _synthesize_api(self, text: str, voice: str, speed: float) -> bytes:
        import json
        payload = {
            "model": "kokoro",
            "input": text,
            "voice": voice,
            "speed": speed,
            "response_format": "wav",
        }
        req = urllib.request.Request(
            self._api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30.0) as r:
            return r.read()

    def _synthesize_local(self, text: str, voice: str, speed: float) -> bytes:
        # KPipeline yields (graphemes, phonemes, audio) tuples; concatenate audio
        try:
            import numpy as np  # type: ignore
        except Exception:
            raise RuntimeError("numpy required for Kokoro local mode")
        if self._pipeline is None:
            raise RuntimeError("Kokoro pipeline not loaded")
        chunks = []
        for _, _, audio in self._pipeline(text, voice=voice, speed=speed):
            arr = np.asarray(audio, dtype=np.float32)
            chunks.append((arr * 32767).clip(-32768, 32767).astype(np.int16).tobytes())
        return b"".join(chunks)

    def _estimate_duration_s(self, audio: bytes, format_: str = "wav") -> float:
        if not audio:
            return 0.0
        if format_ == "pcm":
            # 16-bit mono at sample_rate
            return len(audio) / (2 * self._sample_rate)
        # WAV header is 44 bytes; rest is samples (assume 16-bit mono)
        if len(audio) <= 44:
            return 0.0
        return (len(audio) - 44) / (2 * self._sample_rate)

    async def stream_synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[bytes, None]:
        """For now, synthesize whole then yield single chunk. True streaming TBD."""
        result = await self.synthesize(text, voice, **kwargs)
        if result.audio_data and not result.error:
            yield result.audio_data
