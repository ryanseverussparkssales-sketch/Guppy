"""
TTS Fallback Orchestrator
==========================

Runs configured TTS providers in priority order with fast failover.
Default chain: ElevenLabs (if API key) -> Kokoro -> SAPI.

Returns the first successful TTSResult; collects partial errors in
result.metadata['fallback_chain'].
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator, List, Optional

from guppy.voice.core import TTSProvider, TTSResult

logger = logging.getLogger(__name__)


class TTSFallbackOrchestrator:
    """Sequential TTS fallback with timeout per provider."""

    def __init__(
        self,
        providers: Optional[List[TTSProvider]] = None,
        per_provider_timeout_s: float = 30.0,
    ):
        if providers is None:
            from guppy.voice.tts.kokoro_provider import KokoroTTSProvider
            from guppy.voice.tts.sapi_provider import SAPITTSProvider
            from guppy.voice.tts.elevenlabs_provider import ElevenLabsTTSProvider
            providers = [
                ElevenLabsTTSProvider(),
                KokoroTTSProvider(),
                SAPITTSProvider(),
            ]
        self._providers = providers
        self._timeout_s = per_provider_timeout_s

    async def synthesize(self, text: str, voice: Optional[str] = None, **kwargs) -> TTSResult:
        chain = []
        last_error = None
        for provider in self._providers:
            chain.append(provider.name)
            try:
                result = await asyncio.wait_for(
                    provider.synthesize(text, voice, **kwargs),
                    timeout=self._timeout_s,
                )
            except asyncio.TimeoutError:
                last_error = f"{provider.name}_timeout"
                logger.warning("[TTS] %s timed out after %.1fs", provider.name, self._timeout_s)
                continue
            except Exception as e:
                last_error = f"{provider.name}_error: {e}"
                logger.warning("[TTS] %s raised: %s", provider.name, e)
                continue

            if not result.error and result.audio_data:
                # Winner
                meta = dict(result.metadata or {})
                meta["fallback_chain"] = chain
                result.metadata = meta
                return result
            last_error = result.error or "empty_audio"
            logger.info("[TTS] %s did not produce audio: %s", provider.name, last_error)

        # All providers failed
        return TTSResult(
            audio_data=b"",
            provider="fallback_chain",
            duration_ms=0.0,
            sample_rate=0,
            channels=1,
            format="wav",
            playback_duration_s=0.0,
            error=f"all_tts_providers_failed: {last_error}",
            metadata={"fallback_chain": chain},
        )

    async def stream_synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs,
    ) -> AsyncGenerator[bytes, None]:
        """Yield audio chunks from the first provider that produces any data."""
        for provider in self._providers:
            try:
                available = await provider.health_check()
            except Exception:
                available = False
            if not available:
                continue
            got_any = False
            try:
                async for chunk in provider.stream_synthesize(text, voice, **kwargs):
                    got_any = True
                    yield chunk
            except Exception as e:
                logger.warning("[TTS stream] %s raised: %s", provider.name, e)
                continue
            if got_any:
                return

    async def health_check(self) -> dict:
        statuses = {}
        for p in self._providers:
            try:
                statuses[p.name] = await p.health_check()
            except Exception as e:
                statuses[p.name] = False
                logger.debug("health_check failed for %s: %s", p.name, e)
        return statuses
