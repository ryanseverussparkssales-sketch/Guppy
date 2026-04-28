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
        """Return mock transcription result."""
        raise NotImplementedError("Phase 1 implementation pending")

    async def stream_transcribe(self, audio_stream: AsyncGenerator[bytes, None], language: str = None, **kwargs) -> AsyncGenerator[STTResult, None]:
        """Stream mock transcription."""
        raise NotImplementedError("Phase 1 implementation pending")

    async def health_check(self) -> bool:
        """Always healthy."""
        return True


class MockTTSProvider(TTSProvider):
    """Mock TTS provider for testing."""

    name = "mock_tts"

    async def synthesize(self, text: str, voice: str = None, **kwargs) -> TTSResult:
        """Return mock audio result."""
        raise NotImplementedError("Phase 1 implementation pending")

    async def stream_synthesize(self, text: str, voice: str = None, **kwargs) -> AsyncGenerator[bytes, None]:
        """Stream mock audio chunks."""
        raise NotImplementedError("Phase 1 implementation pending")

    async def health_check(self) -> bool:
        """Always healthy."""
        return True


class MockWakeWordProvider(WakeWordProvider):
    """Mock wake-word provider for testing."""

    name = "mock_wake_word"

    async def detect(self, audio_data: bytes, **kwargs) -> tuple[bool, float]:
        """Return mock detection result."""
        raise NotImplementedError("Phase 1 implementation pending")

    async def stream_detect(self, audio_stream: AsyncGenerator[bytes, None], **kwargs) -> AsyncGenerator[tuple[bool, float], None]:
        """Stream mock detection results."""
        raise NotImplementedError("Phase 1 implementation pending")

    async def health_check(self) -> bool:
        """Always healthy."""
        return True


def generate_test_audio_silence(duration_ms: int, sample_rate: int = 16000) -> bytes:
    """
    Generate silence audio for testing.

    Args:
        duration_ms: Duration in milliseconds
        sample_rate: Sample rate (default 16000 Hz)

    Returns:
        Raw audio bytes (PCM)

    Phase 1 implementation pending.
    """
    raise NotImplementedError("Phase 1 implementation pending")


def generate_test_audio_white_noise(duration_ms: int, sample_rate: int = 16000) -> bytes:
    """
    Generate white noise audio for testing.

    Args:
        duration_ms: Duration in milliseconds
        sample_rate: Sample rate (default 16000 Hz)

    Returns:
        Raw audio bytes (PCM)

    Phase 1 implementation pending.
    """
    raise NotImplementedError("Phase 1 implementation pending")


def generate_test_audio_sine_wave(
    duration_ms: int,
    frequency_hz: float = 440,
    sample_rate: int = 16000,
) -> bytes:
    """
    Generate sine wave audio for testing.

    Args:
        duration_ms: Duration in milliseconds
        frequency_hz: Frequency in Hertz (default 440 Hz / A note)
        sample_rate: Sample rate (default 16000 Hz)

    Returns:
        Raw audio bytes (PCM)

    Phase 1 implementation pending.
    """
    raise NotImplementedError("Phase 1 implementation pending")
