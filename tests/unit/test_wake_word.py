"""
Test Suite: Wake-Word Detection
=================================

Tests EnergyThresholdWakeWordProvider, PorcupineWakeWordProvider (skeleton),
WakeWordDetector orchestration with debouncing and threshold filtering.
"""

import struct
import math
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from guppy.voice import (
    WakeWordDetector,
    WakeWordConfig,
    WakeWordEvent,
    EnergyThresholdWakeWordProvider,
    PorcupineWakeWordProvider,
)


def _silence(samples: int = 16000) -> bytes:
    return b"\x00\x00" * samples


def _tone(samples: int = 16000, amplitude: int = 8000, freq: int = 440, sr: int = 16000) -> bytes:
    out = bytearray()
    for n in range(samples):
        v = int(amplitude * math.sin(2 * math.pi * freq * n / sr))
        out += struct.pack("<h", v)
    return bytes(out)


# =================== Energy threshold provider ===================

class TestEnergyThresholdProvider:
    def test_init(self):
        p = EnergyThresholdWakeWordProvider()
        assert p.name == "energy_threshold"

    @pytest.mark.asyncio
    async def test_health_check_always_true(self):
        p = EnergyThresholdWakeWordProvider()
        assert await p.health_check() is True

    @pytest.mark.asyncio
    async def test_silence_does_not_fire(self):
        p = EnergyThresholdWakeWordProvider(rms_threshold=0.05)
        detected, conf = await p.detect(_silence())
        assert detected is False
        assert conf == 0.0

    @pytest.mark.asyncio
    async def test_loud_tone_fires(self):
        p = EnergyThresholdWakeWordProvider(rms_threshold=0.05)
        detected, conf = await p.detect(_tone(amplitude=16000))
        assert detected is True
        assert conf > 0.5

    @pytest.mark.asyncio
    async def test_quiet_tone_does_not_fire(self):
        p = EnergyThresholdWakeWordProvider(rms_threshold=0.5)
        detected, _ = await p.detect(_tone(amplitude=500))
        assert detected is False

    @pytest.mark.asyncio
    async def test_empty_audio(self):
        p = EnergyThresholdWakeWordProvider()
        detected, conf = await p.detect(b"")
        assert detected is False
        assert conf == 0.0


# =================== Porcupine provider skeleton ===================

class TestPorcupineProvider:
    def test_init(self):
        p = PorcupineWakeWordProvider(keyword="hey google", access_key="xxx")
        assert p.name == "porcupine"

    @pytest.mark.asyncio
    async def test_health_check_false_when_no_key(self):
        p = PorcupineWakeWordProvider(keyword="hey google", access_key="")
        # Even if pvporcupine is installed, missing access_key should fail
        with patch.dict("os.environ", {"PORCUPINE_ACCESS_KEY": ""}, clear=False):
            p._available = None
            # Will return False if no key, regardless of pvporcupine availability
            assert await p.health_check() is False

    @pytest.mark.asyncio
    async def test_detect_returns_false_when_unavailable(self):
        p = PorcupineWakeWordProvider(keyword="hey google", access_key="")
        p._available = False
        detected, conf = await p.detect(_silence())
        assert detected is False
        assert conf == 0.0


# =================== WakeWordDetector orchestration ===================

class TestWakeWordDetector:
    def test_init_uses_provider_name(self):
        provider = EnergyThresholdWakeWordProvider()
        detector = WakeWordDetector(provider=provider)
        assert detector.config.provider_name == "energy_threshold"

    @pytest.mark.asyncio
    async def test_detect_one_below_threshold(self):
        provider = EnergyThresholdWakeWordProvider(rms_threshold=0.5)
        detector = WakeWordDetector(provider=provider, config=WakeWordConfig(detection_threshold=0.5))
        event = await detector.detect_one(_silence())
        # Confidence below threshold → no audio_excerpt populated
        assert event.confidence < 0.5
        assert event.audio_excerpt == b""

    @pytest.mark.asyncio
    async def test_detect_one_above_threshold(self):
        provider = EnergyThresholdWakeWordProvider(rms_threshold=0.05)
        detector = WakeWordDetector(provider=provider, config=WakeWordConfig(detection_threshold=0.5))
        event = await detector.detect_one(_tone(amplitude=16000))
        assert event.confidence > 0.5
        assert event.keyword == "hey_guppy"
        assert event.provider == "energy_threshold"
        assert len(event.audio_excerpt) > 0  # excerpt populated on detection

    @pytest.mark.asyncio
    async def test_detect_one_handles_provider_exception(self):
        provider = MagicMock()
        provider.name = "broken"
        provider.detect = AsyncMock(side_effect=RuntimeError("crash"))
        detector = WakeWordDetector(provider=provider, config=WakeWordConfig(provider_name="broken"))
        event = await detector.detect_one(b"\x00")
        assert event.confidence == 0.0  # graceful

    @pytest.mark.asyncio
    async def test_listen_yields_on_detection_above_threshold(self):
        # Build a fake provider that always fires above threshold
        provider = MagicMock()
        provider.name = "test"

        async def fake_stream(stream):
            async for _ in stream:
                yield (True, 0.9)

        provider.stream_detect = fake_stream

        async def gen():
            for _ in range(3):
                yield b"\x00\x00"

        detector = WakeWordDetector(
            provider=provider,
            config=WakeWordConfig(
                provider_name="test",
                detection_threshold=0.5,
                debounce_ms=0.0,  # no debounce → all 3 fire
                sample_rate=16000,
                frame_duration_ms=30.0,
            ),
        )
        events = [e async for e in detector.listen(gen())]
        assert len(events) == 3
        assert all(e.confidence == 0.9 for e in events)

    @pytest.mark.asyncio
    async def test_listen_filters_below_threshold(self):
        provider = MagicMock()
        provider.name = "test"

        async def fake_stream(stream):
            async for _ in stream:
                yield (True, 0.2)  # below threshold

        provider.stream_detect = fake_stream

        async def gen():
            for _ in range(3):
                yield b"\x00\x00"

        detector = WakeWordDetector(
            provider=provider,
            config=WakeWordConfig(provider_name="test", detection_threshold=0.5, debounce_ms=0.0),
        )
        events = [e async for e in detector.listen(gen())]
        assert events == []  # all filtered

    @pytest.mark.asyncio
    async def test_listen_debounces_rapid_detections(self):
        provider = MagicMock()
        provider.name = "test"

        async def fake_stream(stream):
            async for _ in stream:
                yield (True, 0.9)

        provider.stream_detect = fake_stream

        async def gen():
            # 100 chunks, 30ms each = 3000ms total
            for _ in range(100):
                yield b"\x00\x00"

        detector = WakeWordDetector(
            provider=provider,
            config=WakeWordConfig(
                provider_name="test",
                detection_threshold=0.5,
                debounce_ms=1000.0,  # 1s debounce
                sample_rate=16000,
                frame_duration_ms=30.0,
            ),
        )
        events = [e async for e in detector.listen(gen())]
        # 3000ms / 1000ms debounce → at most ~3-4 fires
        assert len(events) <= 4
        assert len(events) >= 2

    @pytest.mark.asyncio
    async def test_listen_disabled_yields_nothing(self):
        provider = EnergyThresholdWakeWordProvider()

        async def gen():
            yield _tone(amplitude=16000)

        detector = WakeWordDetector(
            provider=provider,
            config=WakeWordConfig(provider_name="energy_threshold", enabled=False),
        )
        events = [e async for e in detector.listen(gen())]
        assert events == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
