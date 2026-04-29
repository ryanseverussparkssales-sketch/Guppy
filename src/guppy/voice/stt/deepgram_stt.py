"""Deepgram nova-3 Speech-to-Text provider."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import urllib.request
from typing import Any, AsyncGenerator, Optional

from guppy.voice.core import STTProvider, STTResult

logger = logging.getLogger(__name__)

_DEEPGRAM_URL = "https://api.deepgram.com/v1/listen?model=nova-3&smart_format=true&language=en"


class DeepgramSTTProvider(STTProvider):
    """Deepgram nova-3 cloud STT — fastest, highest accuracy when key is present."""

    name = "deepgram_stt"

    def __init__(self, api_key: Optional[str] = None) -> None:
        key = api_key if api_key is not None else os.environ.get("DEEPGRAM_API_KEY", "")
        self._api_key = key.strip()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def transcribe(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
        content_type: str = "audio/webm",
        **kwargs: Any,
    ) -> STTResult:
        if not self._api_key:
            return STTResult(
                text="", confidence=0.0, provider=self.name,
                duration_ms=0.0, error="DEEPGRAM_API_KEY not set",
            )
        start = time.monotonic()
        try:
            text = await asyncio.to_thread(
                self._call_api, audio_data, content_type or "audio/webm"
            )
            duration_ms = (time.monotonic() - start) * 1000
            return STTResult(
                text=text, confidence=0.95, provider=self.name,
                duration_ms=duration_ms, language=language or "en",
            )
        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            logger.warning("[deepgram] transcribe failed: %s", exc)
            return STTResult(
                text="", confidence=0.0, provider=self.name,
                duration_ms=duration_ms, error=str(exc),
            )

    async def stream_transcribe(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        language: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[STTResult, None]:
        # Collect the stream and call batch endpoint (streaming WebSocket out of scope for now)
        buf = bytearray()
        async for chunk in audio_stream:
            buf.extend(chunk)
        if buf:
            result = await self.transcribe(bytes(buf), language, **kwargs)
            result.is_final = True
            yield result

    async def health_check(self) -> bool:
        return bool(self._api_key)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _call_api(self, audio_data: bytes, content_type: str) -> str:
        req = urllib.request.Request(
            _DEEPGRAM_URL,
            data=audio_data,
            headers={
                "Authorization": f"Token {self._api_key}",
                "Content-Type": content_type,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        return (
            data.get("results", {})
                .get("channels", [{}])[0]
                .get("alternatives", [{}])[0]
                .get("transcript", "")
                .strip()
        )
