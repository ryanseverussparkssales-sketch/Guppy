"""
Porcupine Wake-Word Provider (skeleton)
=========================================

Wraps Picovoice Porcupine for production-grade wake-word detection.
Requires `pvporcupine` package and a Picovoice access key:

    pip install pvporcupine
    export PORCUPINE_ACCESS_KEY="your-key-from-console"

This file currently provides the class skeleton; the runtime path
expects pvporcupine to be installed before use. If unavailable,
health_check() returns False and detect() raises clearly.
"""

from __future__ import annotations

import logging
import os
from typing import Any, AsyncGenerator, Optional

from guppy.voice.core import WakeWordProvider

logger = logging.getLogger(__name__)


class PorcupineWakeWordProvider(WakeWordProvider):
    """Porcupine-based wake-word detector (requires pvporcupine + access key)."""

    name = "porcupine"

    def __init__(
        self,
        keyword: str = "hey google",  # built-in keyword name OR path to .ppn file
        access_key: Optional[str] = None,
        sensitivity: float = 0.5,
        sample_rate: int = 16000,
    ):
        self._keyword = keyword
        self._access_key = access_key or os.environ.get("PORCUPINE_ACCESS_KEY", "").strip()
        self._sensitivity = sensitivity
        self._sample_rate = sample_rate
        self._engine = None
        self._available: Optional[bool] = None

    async def health_check(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import pvporcupine  # type: ignore  # noqa: F401
            if not self._access_key:
                logger.warning("Porcupine: PORCUPINE_ACCESS_KEY not set")
                self._available = False
                return False
            self._available = True
            return True
        except ImportError:
            logger.debug("Porcupine: pvporcupine not installed")
            self._available = False
            return False

    def _ensure_engine(self):
        if self._engine is not None:
            return self._engine
        import pvporcupine  # type: ignore
        # Try built-in keyword first; if not found, treat as path
        try:
            self._engine = pvporcupine.create(
                access_key=self._access_key,
                keywords=[self._keyword],
                sensitivities=[self._sensitivity],
            )
        except Exception:
            self._engine = pvporcupine.create(
                access_key=self._access_key,
                keyword_paths=[self._keyword],
                sensitivities=[self._sensitivity],
            )
        return self._engine

    async def detect(self, audio_data: bytes, **kwargs: Any) -> tuple[bool, float]:
        if not await self.health_check():
            return (False, 0.0)
        engine = self._ensure_engine()
        # Porcupine processes 16-bit int frames of size frame_length
        import struct
        frame_length = engine.frame_length
        frame_count = len(audio_data) // (2 * frame_length)
        for i in range(frame_count):
            offset = i * 2 * frame_length
            frame = struct.unpack(
                f"<{frame_length}h", audio_data[offset:offset + 2 * frame_length]
            )
            keyword_index = engine.process(frame)
            if keyword_index >= 0:
                return (True, self._sensitivity)
        return (False, 0.0)

    async def stream_detect(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        **kwargs: Any,
    ) -> AsyncGenerator[tuple[bool, float], None]:
        async for chunk in audio_stream:
            yield await self.detect(chunk)
