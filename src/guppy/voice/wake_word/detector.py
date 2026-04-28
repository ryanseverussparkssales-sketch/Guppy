"""
Wake-Word Detector
===================

Service that monitors an audio stream for a configured wake-word and
emits WAKE_WORD_DETECTED events. Uses a pluggable WakeWordProvider
backend (Porcupine, OpenWakeWord, or the simple energy-threshold stub).

Usage:
    detector = WakeWordDetector(provider=PorcupineWakeWordProvider("hey_guppy"))
    async for confidence in detector.listen(audio_stream):
        # Wake word detected at this point
        ...
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional

from guppy.voice.core import WakeWordProvider, AudioEvent, AudioEventType

logger = logging.getLogger(__name__)


@dataclass
class WakeWordConfig:
    """Configuration for wake-word detection."""

    provider_name: str = "energy_threshold"
    keyword: str = "hey_guppy"
    detection_threshold: float = 0.5  # 0.0 to 1.0
    debounce_ms: float = 1500.0  # min ms between detections
    sample_rate: int = 16000  # Hz
    frame_duration_ms: float = 30.0  # ms per analysis window
    enabled: bool = True


@dataclass
class WakeWordEvent:
    """A single wake-word detection event."""

    confidence: float
    keyword: str
    provider: str
    timestamp_ms: float  # ms since start of stream
    audio_excerpt: bytes = b""  # short excerpt around detection (optional)


class WakeWordDetector:
    """
    Stream-based wake-word detector with debouncing.

    Wraps a WakeWordProvider and applies cross-detection debouncing,
    threshold filtering, and WAKE_WORD_DETECTED telemetry.
    """

    def __init__(
        self,
        provider: WakeWordProvider,
        config: Optional[WakeWordConfig] = None,
    ):
        self._provider = provider
        self._config = config or WakeWordConfig(provider_name=provider.name)
        self._last_detection_ms: float = 0.0
        self._sample_count: int = 0

    async def health_check(self) -> bool:
        return await self._provider.health_check()

    async def detect_one(self, audio_data: bytes) -> WakeWordEvent:
        """Run a single-shot detection on a captured audio chunk."""
        try:
            detected, confidence = await self._provider.detect(audio_data)
        except Exception as e:
            logger.error("wake-word detect failed: %s", e)
            return WakeWordEvent(
                confidence=0.0,
                keyword=self._config.keyword,
                provider=self._provider.name,
                timestamp_ms=0.0,
            )
        if detected and confidence >= self._config.detection_threshold:
            return WakeWordEvent(
                confidence=confidence,
                keyword=self._config.keyword,
                provider=self._provider.name,
                timestamp_ms=0.0,
                audio_excerpt=audio_data[-min(len(audio_data), 2 * self._config.sample_rate):],
            )
        return WakeWordEvent(
            confidence=confidence,
            keyword=self._config.keyword,
            provider=self._provider.name,
            timestamp_ms=0.0,
        )

    async def listen(
        self,
        audio_stream: AsyncGenerator[bytes, None],
    ) -> AsyncGenerator[WakeWordEvent, None]:
        """
        Yield WakeWordEvents whenever the wake-word fires above the
        configured threshold and after the debounce window has elapsed.
        """
        if not self._config.enabled:
            return

        try:
            async for detected, confidence in self._provider.stream_detect(audio_stream):
                self._sample_count += int(self._config.sample_rate * self._config.frame_duration_ms / 1000.0)
                ts_ms = (self._sample_count / self._config.sample_rate) * 1000.0

                if not detected or confidence < self._config.detection_threshold:
                    continue
                if ts_ms - self._last_detection_ms < self._config.debounce_ms:
                    continue
                self._last_detection_ms = ts_ms
                yield WakeWordEvent(
                    confidence=confidence,
                    keyword=self._config.keyword,
                    provider=self._provider.name,
                    timestamp_ms=ts_ms,
                )
        except Exception as e:
            logger.error("wake-word listen() failed: %s", e)
            raise

    @property
    def config(self) -> WakeWordConfig:
        return self._config

    @property
    def provider(self) -> WakeWordProvider:
        return self._provider
