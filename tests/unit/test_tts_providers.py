"""
Test Suite: TTS Provider Implementations + Facade
==================================================

Tests Kokoro, SAPI, ElevenLabs providers, the TTSFallbackOrchestrator,
the TTSCache, and the speak()/synthesize() facade.
"""

import os
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from guppy.voice import (
    KokoroTTSProvider,
    SAPITTSProvider,
    ElevenLabsTTSProvider,
    TTSCache,
    TTSFallbackOrchestrator,
    TTSResult,
    AudioEvent,
    AudioEventType,
)


# =================== Cache ===================

class TestTTSCache:
    def test_put_then_get_hits(self):
        cache = TTSCache(max_entries=4)
        result = TTSResult(
            audio_data=b"abc", provider="kokoro_tts",
            duration_ms=100.0, sample_rate=24000, channels=1,
            format="wav", playback_duration_s=0.5,
        )
        cache.put("hello", "voice_a", "fallback_chain", result)
        got = cache.get("hello", "voice_a", "fallback_chain")
        assert got is not None
        assert got.audio_data == b"abc"
        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["entries"] == 1

    def test_miss_returns_none(self):
        cache = TTSCache()
        assert cache.get("missing", None, "x") is None
        assert cache.stats()["misses"] == 1

    def test_does_not_cache_errors(self):
        cache = TTSCache()
        result = TTSResult(
            audio_data=b"", provider="x", duration_ms=0.0,
            sample_rate=0, channels=1, format="wav",
            playback_duration_s=0.0, error="boom",
        )
        cache.put("hello", None, "x", result)
        assert cache.get("hello", None, "x") is None

    def test_lru_eviction(self):
        cache = TTSCache(max_entries=2)
        for i, t in enumerate(["a", "b", "c"]):
            r = TTSResult(
                audio_data=bytes([i]), provider="p",
                duration_ms=1.0, sample_rate=1, channels=1,
                format="wav", playback_duration_s=0.0,
            )
            cache.put(t, None, "p", r)
        assert cache.get("a", None, "p") is None  # evicted
        assert cache.get("b", None, "p") is not None
        assert cache.get("c", None, "p") is not None

    def test_voice_distinguishes_keys(self):
        cache = TTSCache()
        r1 = TTSResult(audio_data=b"v1", provider="p", duration_ms=1, sample_rate=1, channels=1, format="wav", playback_duration_s=0)
        r2 = TTSResult(audio_data=b"v2", provider="p", duration_ms=1, sample_rate=1, channels=1, format="wav", playback_duration_s=0)
        cache.put("hello", "alice", "p", r1)
        cache.put("hello", "bob", "p", r2)
        assert cache.get("hello", "alice", "p").audio_data == b"v1"
        assert cache.get("hello", "bob", "p").audio_data == b"v2"


# =================== KokoroTTSProvider ===================

class TestKokoroTTSProvider:
    def test_init(self):
        provider = KokoroTTSProvider(api_url="http://x")
        assert provider.name == "kokoro_tts"

    @pytest.mark.asyncio
    async def test_health_check_returns_false_when_neither_mode_available(self):
        provider = KokoroTTSProvider(api_url="http://invalid:9999")
        # Force both detection paths to fail
        with patch.object(provider, "_probe_api", return_value=False), \
             patch.object(provider, "_load_local", return_value=False):
            assert await provider.health_check() is False

    @pytest.mark.asyncio
    async def test_synthesize_returns_error_when_unavailable(self):
        provider = KokoroTTSProvider(api_url="http://invalid:9999")
        with patch.object(provider, "_probe_api", return_value=False), \
             patch.object(provider, "_load_local", return_value=False):
            result = await provider.synthesize("hi")
            assert result.error == "kokoro_not_available"
            assert result.audio_data == b""

    @pytest.mark.asyncio
    async def test_synthesize_via_api_returns_audio(self):
        provider = KokoroTTSProvider(api_url="http://api/v1/audio/speech")
        with patch.object(provider, "_probe_api", return_value=True), \
             patch.object(provider, "_synthesize_api", return_value=b"WAV...") as m:
            result = await provider.synthesize("hello", voice="af_bella")
            assert result.audio_data == b"WAV..."
            assert result.provider == "kokoro_tts"
            assert result.error is None
            assert result.metadata.get("mode") == "api"
            m.assert_called_once()


# =================== SAPITTSProvider ===================

class TestSAPITTSProvider:
    def test_init(self):
        provider = SAPITTSProvider()
        assert provider.name == "sapi_tts"

    @pytest.mark.asyncio
    async def test_health_check_false_when_not_windows(self):
        provider = SAPITTSProvider()
        with patch("sys.platform", "linux"):
            # Force re-detection
            provider._available = None
            assert await provider.health_check() is False

    @pytest.mark.asyncio
    async def test_synthesize_returns_error_when_no_engine(self):
        provider = SAPITTSProvider()
        provider._available = False
        result = await provider.synthesize("hi")
        assert result.error == "sapi_not_available"


# =================== ElevenLabsTTSProvider ===================

class TestElevenLabsTTSProvider:
    def test_init(self):
        provider = ElevenLabsTTSProvider(api_key="xxx")
        assert provider.name == "elevenlabs_tts"

    @pytest.mark.asyncio
    async def test_health_check_requires_api_key(self):
        provider = ElevenLabsTTSProvider(api_key="")
        assert await provider.health_check() is False
        provider2 = ElevenLabsTTSProvider(api_key="abc")
        assert await provider2.health_check() is True

    @pytest.mark.asyncio
    async def test_synthesize_no_api_key(self):
        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": ""}, clear=False):
            provider = ElevenLabsTTSProvider(api_key="")
            result = await provider.synthesize("hi")
            assert result.error == "elevenlabs_no_api_key"

    @pytest.mark.asyncio
    async def test_synthesize_returns_audio_on_success(self):
        provider = ElevenLabsTTSProvider(api_key="abc")
        with patch.object(provider, "_synthesize_blocking", return_value=b"MP3..."):
            result = await provider.synthesize("hello", voice="custom")
            assert result.audio_data == b"MP3..."
            assert result.format == "mp3"
            assert result.error is None
            assert result.metadata["voice_id"] == "custom"


# =================== Fallback Orchestrator ===================

class TestTTSFallbackOrchestrator:
    @pytest.mark.asyncio
    async def test_first_provider_wins(self):
        winner = MagicMock()
        winner.name = "winner"
        winner.synthesize = AsyncMock(return_value=TTSResult(
            audio_data=b"AAA", provider="winner",
            duration_ms=50.0, sample_rate=24000, channels=1,
            format="wav", playback_duration_s=0.1,
        ))
        loser = MagicMock()
        loser.name = "loser"
        loser.synthesize = AsyncMock()  # not called

        orch = TTSFallbackOrchestrator(providers=[winner, loser])
        result = await orch.synthesize("hi")
        assert result.audio_data == b"AAA"
        assert result.metadata["fallback_chain"] == ["winner"]
        loser.synthesize.assert_not_called()

    @pytest.mark.asyncio
    async def test_fallback_when_first_errors(self):
        first = MagicMock()
        first.name = "first"
        first.synthesize = AsyncMock(return_value=TTSResult(
            audio_data=b"", provider="first",
            duration_ms=10.0, sample_rate=0, channels=1,
            format="wav", playback_duration_s=0.0,
            error="api_down",
        ))
        second = MagicMock()
        second.name = "second"
        second.synthesize = AsyncMock(return_value=TTSResult(
            audio_data=b"OK", provider="second",
            duration_ms=20.0, sample_rate=22050, channels=1,
            format="wav", playback_duration_s=0.5,
        ))
        orch = TTSFallbackOrchestrator(providers=[first, second])
        result = await orch.synthesize("hi")
        assert result.audio_data == b"OK"
        assert result.provider == "second"
        assert result.metadata["fallback_chain"] == ["first", "second"]

    @pytest.mark.asyncio
    async def test_all_fail(self):
        bad = MagicMock()
        bad.name = "bad"
        bad.synthesize = AsyncMock(return_value=TTSResult(
            audio_data=b"", provider="bad", duration_ms=1.0,
            sample_rate=0, channels=1, format="wav",
            playback_duration_s=0.0, error="boom",
        ))
        orch = TTSFallbackOrchestrator(providers=[bad])
        result = await orch.synthesize("hi")
        assert result.error is not None
        assert "all_tts_providers_failed" in result.error
        assert result.audio_data == b""


# =================== Facade synthesize/speak ===================

class TestFacadeSynthesize:
    @pytest.mark.asyncio
    async def test_synthesize_records_start_and_success_events(self):
        from guppy.voice import synthesize, clear_audio_telemetry, get_audio_telemetry, clear_tts_cache
        from guppy.voice import voice as voice_facade

        clear_audio_telemetry()
        clear_tts_cache()

        fake_result = TTSResult(
            audio_data=b"AUDIO", provider="kokoro_tts",
            duration_ms=120.0, sample_rate=24000, channels=1,
            format="wav", playback_duration_s=0.5,
            metadata={"fallback_chain": ["kokoro_tts"]},
        )
        fake = MagicMock()
        fake.synthesize = AsyncMock(return_value=fake_result)
        voice_facade._tts_orchestrator = fake

        result = await synthesize("hello", voice="af_bella")
        assert result.audio_data == b"AUDIO"
        types = [e.event_type for e in get_audio_telemetry()]
        assert AudioEventType.TTS_START in types
        assert AudioEventType.TTS_SUCCESS in types
        assert AudioEventType.TTS_FALLBACK not in types  # primary won

    @pytest.mark.asyncio
    async def test_synthesize_fallback_event_when_secondary_wins(self):
        from guppy.voice import synthesize, clear_audio_telemetry, get_audio_telemetry, clear_tts_cache
        from guppy.voice import voice as voice_facade

        clear_audio_telemetry()
        clear_tts_cache()

        fake_result = TTSResult(
            audio_data=b"X", provider="sapi_tts",
            duration_ms=60.0, sample_rate=22050, channels=1,
            format="wav", playback_duration_s=0.2,
            metadata={"fallback_chain": ["elevenlabs_tts", "kokoro_tts", "sapi_tts"]},
        )
        fake = MagicMock()
        fake.synthesize = AsyncMock(return_value=fake_result)
        voice_facade._tts_orchestrator = fake

        await synthesize("hi")
        types = [e.event_type for e in get_audio_telemetry()]
        assert AudioEventType.TTS_FALLBACK in types

    @pytest.mark.asyncio
    async def test_cache_hit_skips_orchestrator(self):
        from guppy.voice import synthesize, clear_audio_telemetry, get_audio_telemetry, clear_tts_cache
        from guppy.voice import voice as voice_facade

        clear_audio_telemetry()
        clear_tts_cache()

        fake_result = TTSResult(
            audio_data=b"FIRST", provider="kokoro_tts",
            duration_ms=100.0, sample_rate=24000, channels=1,
            format="wav", playback_duration_s=0.3,
            metadata={"fallback_chain": ["kokoro_tts"]},
        )
        fake = MagicMock()
        fake.synthesize = AsyncMock(return_value=fake_result)
        voice_facade._tts_orchestrator = fake

        # First call: orchestrator invoked, result cached
        r1 = await synthesize("hello", voice="alice")
        assert r1.audio_data == b"FIRST"
        assert fake.synthesize.call_count == 1

        # Second call (same args): served from cache, orchestrator NOT called again
        r2 = await synthesize("hello", voice="alice")
        assert r2.audio_data == b"FIRST"
        assert fake.synthesize.call_count == 1  # unchanged

        # Verify cache_hit metadata present in second event
        success_events = [e for e in get_audio_telemetry() if e.event_type == AudioEventType.TTS_SUCCESS]
        assert any(e.metadata.get("cache_hit") for e in success_events)

    @pytest.mark.asyncio
    async def test_speak_returns_tts_result(self):
        from guppy.voice import speak, clear_audio_telemetry, clear_tts_cache
        from guppy.voice import voice as voice_facade

        clear_audio_telemetry()
        clear_tts_cache()

        fake_result = TTSResult(
            audio_data=b"OK", provider="sapi_tts",
            duration_ms=10.0, sample_rate=22050, channels=1,
            format="wav", playback_duration_s=0.1,
            metadata={"fallback_chain": ["sapi_tts"]},
        )
        fake = MagicMock()
        fake.synthesize = AsyncMock(return_value=fake_result)
        voice_facade._tts_orchestrator = fake

        result = await speak("hello")
        assert isinstance(result, TTSResult)
        assert result.audio_data == b"OK"

    @pytest.mark.asyncio
    async def test_synthesize_swallows_orchestrator_exception(self):
        from guppy.voice import synthesize, clear_audio_telemetry, get_audio_telemetry, clear_tts_cache
        from guppy.voice import voice as voice_facade

        clear_audio_telemetry()
        clear_tts_cache()

        fake = MagicMock()
        fake.synthesize = AsyncMock(side_effect=RuntimeError("boom"))
        voice_facade._tts_orchestrator = fake

        result = await synthesize("hi")
        assert result.error == "boom"
        types = [e.event_type for e in get_audio_telemetry()]
        assert AudioEventType.TTS_ERROR in types


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
