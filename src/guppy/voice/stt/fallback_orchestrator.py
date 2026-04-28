"""STT Fallback Chain Orchestrator — Deepgram → Whisper → SAPI."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, AsyncGenerator, Optional

from guppy.voice.core import STTProvider, STTResult
from guppy.voice.stt.deepgram_stt import DeepgramSTTProvider
from guppy.voice.stt.whisper_stt import WhisperSTTProvider
from guppy.voice.stt.sapi_stt import SAPISTTProvider

logger = logging.getLogger(__name__)

_PRIMARY_TIMEOUT = 10.0
_SECONDARY_TIMEOUT = 10.0


class FallbackChainOrchestrator:
    """Deepgram (primary) → Whisper (secondary) → SAPI (tertiary).

    Deepgram is skipped when DEEPGRAM_API_KEY is absent so the chain
    degrades gracefully in offline / no-key environments.
    """

    def __init__(self) -> None:
        self.deepgram = DeepgramSTTProvider()
        self.whisper = WhisperSTTProvider()
        self.sapi = SAPISTTProvider()

    # Legacy attribute aliases so pre-6.0a tests and callers keep working.
    @property
    def google_provider(self) -> DeepgramSTTProvider:
        return self.deepgram

    @property
    def whisper_provider(self) -> WhisperSTTProvider:
        return self.whisper

    @property
    def sapi_provider(self) -> SAPISTTProvider:
        return self.sapi

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def transcribe(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
        **kwargs: Any,
    ) -> STTResult:
        start = time.monotonic()
        tried: list[str] = []

        # 1. Deepgram (only when key present)
        if os.environ.get("DEEPGRAM_API_KEY", "").strip():
            tried.append("deepgram")
            logger.info("[STT] Trying Deepgram (timeout %.1fs)", _PRIMARY_TIMEOUT)
            result = await self._attempt(
                self.deepgram.transcribe(audio_data, language, **kwargs),
                _PRIMARY_TIMEOUT, "deepgram",
            )
            if result:
                result.metadata["fallback_chain"] = tried
                return result

        # 2. Whisper
        tried.append("whisper")
        logger.info("[STT] Trying Whisper (timeout %.1fs)", _SECONDARY_TIMEOUT)
        result = await self._attempt(
            self.whisper.transcribe(audio_data, language, **kwargs),
            _SECONDARY_TIMEOUT, "whisper",
        )
        if result:
            result.metadata["fallback_chain"] = tried
            return result

        # 3. SAPI (always available on Windows, no timeout)
        tried.append("sapi")
        logger.info("[STT] Trying SAPI (no timeout)")
        try:
            result = await self.sapi.transcribe(audio_data, language, **kwargs)
            if result and not result.error and result.text:
                result.metadata["fallback_chain"] = tried
                return result
        except Exception as exc:
            logger.warning("[STT] SAPI failed: %s", exc)

        duration_ms = (time.monotonic() - start) * 1000
        msg = f"STT failed after trying: {' → '.join(tried)}"
        logger.error("[STT] %s", msg)
        raise RuntimeError(msg)

    async def stream_transcribe(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        language: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[STTResult, None]:
        """Buffer stream → batch transcribe via the same fallback chain."""
        BUFFER_SIZE = 30 * 16000 * 2  # 30s @ 16kHz 16-bit
        buf = bytearray()
        batch = 0

        async for chunk in audio_stream:
            buf.extend(chunk)
            if len(buf) >= BUFFER_SIZE:
                batch += 1
                try:
                    result = await self.transcribe(bytes(buf), language, **kwargs)
                    result.is_final = False
                    yield result
                except Exception as exc:
                    yield STTResult(
                        text="", confidence=0.0, provider="fallback_chain",
                        duration_ms=0.0, is_final=False, error=str(exc),
                    )
                buf.clear()

        if buf:
            try:
                result = await self.transcribe(bytes(buf), language, **kwargs)
                result.is_final = True
                yield result
            except Exception as exc:
                yield STTResult(
                    text="", confidence=0.0, provider="fallback_chain",
                    duration_ms=0.0, is_final=True, error=str(exc),
                )

    async def health_check(self) -> bool:
        deepgram_ok = await self.deepgram.health_check()
        whisper_ok = await self.whisper.health_check()
        sapi_ok = await self.sapi.health_check()
        logger.info("[STT Health] deepgram=%s whisper=%s sapi=%s", deepgram_ok, whisper_ok, sapi_ok)
        return deepgram_ok or whisper_ok or sapi_ok

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    async def _attempt(coro, timeout: float, name: str) -> Optional[STTResult]:
        """Run coro with timeout; return result on success, None on failure."""
        try:
            result = await asyncio.wait_for(coro, timeout=timeout)
            if result and not result.error and result.text:
                return result
            logger.warning("[STT] %s returned empty/error: %s", name, result.error if result else "None")
        except asyncio.TimeoutError:
            logger.warning("[STT] %s timed out after %.1fs", name, timeout)
        except Exception as exc:
            logger.warning("[STT] %s error: %s", name, exc)
        return None
