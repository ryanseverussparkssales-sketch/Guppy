"""
Energy-Threshold Wake-Word Provider (stub)
============================================

Lightweight wake-word stub that fires whenever audio energy exceeds
a configured RMS threshold. NOT a true wake-word recognizer — useful as:
  - A test double for unit tests (deterministic on synthetic audio)
  - A development stub before real models are wired (Porcupine, OpenWakeWord)
  - A "voice activity" gate when no real wake-word is needed

Real wake-word providers (Porcupine, OpenWakeWord, Whisper-keyword) plug
into the same WakeWordProvider interface defined in guppy/voice/core.py.
"""

from __future__ import annotations

import logging
import math
from typing import Any, AsyncGenerator

from guppy.voice.core import WakeWordProvider

logger = logging.getLogger(__name__)


class EnergyThresholdWakeWordProvider(WakeWordProvider):
    """RMS-energy gate that masquerades as a wake-word provider."""

    name = "energy_threshold"

    def __init__(
        self,
        rms_threshold: float = 0.05,  # 0..1 normalized
        sample_width_bytes: int = 2,  # 16-bit
    ):
        self._rms_threshold = rms_threshold
        self._sample_width = sample_width_bytes

    async def health_check(self) -> bool:
        return True  # always available

    @staticmethod
    def _rms_normalized(audio: bytes, sample_width: int) -> float:
        if not audio:
            return 0.0
        if sample_width == 2:
            import struct
            count = len(audio) // 2
            if count == 0:
                return 0.0
            samples = struct.unpack(f"<{count}h", audio[: count * 2])
            sumsq = 0.0
            for s in samples:
                sumsq += (s / 32768.0) ** 2
            return math.sqrt(sumsq / count)
        # Fallback: byte-level estimate
        return sum(b for b in audio) / (len(audio) * 255.0)

    async def detect(
        self,
        audio_data: bytes,
        **kwargs: Any,
    ) -> tuple[bool, float]:
        rms = self._rms_normalized(audio_data, self._sample_width)
        # Map RMS to a confidence-like score in [0,1]
        confidence = min(1.0, rms / max(self._rms_threshold * 2, 1e-6))
        return (rms >= self._rms_threshold, confidence)

    async def stream_detect(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        **kwargs: Any,
    ) -> AsyncGenerator[tuple[bool, float], None]:
        async for chunk in audio_stream:
            yield await self.detect(chunk)
