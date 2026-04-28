"""
Voice Module Integration Utilities
====================================

Test helpers and integration utilities for the voice module.

Provides:
  - Mock providers for unit testing
  - Test audio generators (silence, white noise, speech)
  - Integration test helpers

This module is a placeholder for integration test utilities.
Full implementation in Phase 1, Task 3.2 (Comprehensive Test Suite).
"""

import math
import random
import struct
from typing import AsyncGenerator

from guppy.voice.core import (
    STTProvider,
    TTSProvider,
    WakeWordProvider,
    STTResult,
    TTSResult,
)


class MockSTTProvider(STTProvider):
    """Mock STT provider for testing."""

    name = "mock_stt"

    async def transcribe(self, audio_data: bytes, language: str = None, **kwargs) -> STTResult:
        return STTResult(
            text="mock transcription",
            confidence=1.0,
            provider=self.name,
            duration_ms=0.0,
            language=language or "en",
            is_final=True,
        )

    async def stream_transcribe(
        self, audio_stream: AsyncGenerator[bytes, None], language: str = None, **kwargs
    ) -> AsyncGenerator[STTResult, None]:
        async for _ in audio_stream:
            pass
        yield STTResult(
            text="mock transcription",
            confidence=1.0,
            provider=self.name,
            duration_ms=0.0,
            language=language or "en",
            is_final=True,
        )

    async def health_check(self) -> bool:
        return True


class MockTTSProvider(TTSProvider):
    """Mock TTS provider for testing."""

    name = "mock_tts"

    async def synthesize(self, text: str, voice: str = None, **kwargs) -> TTSResult:
        return TTSResult(
            audio_data=b"\x00" * 100,
            provider=self.name,
            duration_ms=0.0,
            sample_rate=22050,
            channels=1,
            format="wav",
            playback_duration_s=0.0,
        )

    async def stream_synthesize(
        self, text: str, voice: str = None, **kwargs
    ) -> AsyncGenerator[bytes, None]:
        yield b"\x00" * 100

    async def health_check(self) -> bool:
        return True


class MockWakeWordProvider(WakeWordProvider):
    """Mock wake-word provider for testing."""

    name = "mock_wake_word"

    async def detect(self, audio_data: bytes, **kwargs) -> tuple[bool, float]:
        return False, 0.0

    async def stream_detect(
        self, audio_stream: AsyncGenerator[bytes, None], **kwargs
    ) -> AsyncGenerator[tuple[bool, float], None]:
        async for _ in audio_stream:
            pass
        yield False, 0.0

    async def health_check(self) -> bool:
        return True


def generate_test_audio_silence(duration_ms: int, sample_rate: int = 16000) -> bytes:
    """Return 16-bit mono PCM silence of the given duration."""
    num_samples = int(sample_rate * duration_ms / 1000)
    return b"\x00\x00" * num_samples


def generate_test_audio_white_noise(duration_ms: int, sample_rate: int = 16000) -> bytes:
    """Return 16-bit mono PCM white noise of the given duration."""
    num_samples = int(sample_rate * duration_ms / 1000)
    samples = [random.randint(-32768, 32767) for _ in range(num_samples)]
    return struct.pack(f"<{num_samples}h", *samples)


def generate_test_audio_sine_wave(
    duration_ms: int,
    frequency_hz: float = 440,
    sample_rate: int = 16000,
) -> bytes:
    """Return 16-bit mono PCM sine wave of the given duration and frequency."""
    num_samples = int(sample_rate * duration_ms / 1000)
    amplitude = 32767
    samples = [
        int(amplitude * math.sin(2 * math.pi * frequency_hz * i / sample_rate))
        for i in range(num_samples)
    ]
    return struct.pack(f"<{num_samples}h", *samples)
