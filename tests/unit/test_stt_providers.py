"""
Test Suite: STT Provider Implementations
=========================================

Tests all three STT providers (Google, Whisper, SAPI) and FallbackChainOrchestrator.

Tests:
  - GoogleSTTProvider initialization and health check
  - WhisperSTTProvider initialization and health check
  - SAPISTTProvider initialization and health check
  - FallbackChainOrchestrator fallback logic
  - AudioEvent telemetry recording
  - Error handling and recovery
"""

import pytest
import asyncio
import os
import sys
from unittest.mock import MagicMock, patch, AsyncMock

from guppy.voice import (
    GoogleSTTProvider,
    WhisperSTTProvider,
    SAPISTTProvider,
    FallbackChainOrchestrator,
    STTResult,
    AudioEvent,
    AudioEventType,
)


class TestGoogleSTTProvider:
    """Test Google Cloud Speech-to-Text provider."""

    def test_init_enabled(self):
        """Test initialization when provider is enabled."""
        with patch.dict(os.environ, {"GUPPY_GOOGLE_STT_ENABLED": "true"}):
            provider = GoogleSTTProvider()
            # If no Google Cloud credentials, client will be None, but that's OK
            assert provider.name == "google_stt"

    def test_init_disabled(self):
        """Test initialization when provider is disabled."""
        with patch.dict(os.environ, {"GUPPY_GOOGLE_STT_ENABLED": "false"}):
            provider = GoogleSTTProvider()
            assert provider.client is None

    @pytest.mark.asyncio
    async def test_health_check_disabled(self):
        """Test health check when provider is disabled."""
        with patch.dict(os.environ, {"GUPPY_GOOGLE_STT_ENABLED": "false"}):
            provider = GoogleSTTProvider()
            health = await provider.health_check()
            assert health is False

    @pytest.mark.asyncio
    async def test_transcribe_not_available(self):
        """Test transcribe when provider not available."""
        with patch.dict(os.environ, {"GUPPY_GOOGLE_STT_ENABLED": "false"}):
            provider = GoogleSTTProvider()
            with pytest.raises(RuntimeError, match="GoogleSTTProvider not initialized"):
                await provider.transcribe(b"test audio", language="en-US")


class TestWhisperSTTProvider:
    """Test OpenAI Whisper provider."""

    def test_init_missing_api_key(self):
        """Test initialization when API key is missing."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
            provider = WhisperSTTProvider()
            # Should disable provider if key missing
            assert provider.client is None

    def test_init_enabled(self):
        """Test initialization when provider is enabled."""
        with patch.dict(
            os.environ,
            {
                "GUPPY_WHISPER_STT_ENABLED": "true",
                "OPENAI_API_KEY": "test-key-12345",
            },
        ):
            provider = WhisperSTTProvider()
            assert provider.name == "whisper_stt"

    def test_init_disabled(self):
        """Test initialization when provider is disabled."""
        with patch.dict(os.environ, {"GUPPY_WHISPER_STT_ENABLED": "false"}):
            provider = WhisperSTTProvider()
            assert provider.client is None

    @pytest.mark.asyncio
    async def test_health_check_disabled(self):
        """Test health check when provider is disabled."""
        with patch.dict(os.environ, {"GUPPY_WHISPER_STT_ENABLED": "false"}):
            provider = WhisperSTTProvider()
            health = await provider.health_check()
            assert health is False

    @pytest.mark.asyncio
    async def test_transcribe_not_available(self):
        """Test transcribe when provider not available."""
        with patch.dict(os.environ, {"GUPPY_WHISPER_STT_ENABLED": "false"}):
            provider = WhisperSTTProvider()
            with pytest.raises(RuntimeError, match="WhisperSTTProvider not initialized"):
                await provider.transcribe(b"test audio", language="en-US")


class TestSAPISTTProvider:
    """Test Windows SAPI5 provider."""

    def test_init_enabled(self):
        """Test initialization when provider is enabled."""
        with patch.dict(os.environ, {"GUPPY_SAPI_STT_ENABLED": "true"}):
            # Mock the speech_recognition module before it's imported
            mock_sr = MagicMock()
            mock_sr.Recognizer = MagicMock
            with patch.dict(sys.modules, {"speech_recognition": mock_sr}):
                provider = SAPISTTProvider()
                assert provider.name == "sapi"

    def test_init_disabled(self):
        """Test initialization when provider is disabled."""
        with patch.dict(os.environ, {"GUPPY_SAPI_STT_ENABLED": "false"}):
            provider = SAPISTTProvider()
            assert provider._recognizer is None

    @pytest.mark.asyncio
    async def test_health_check_disabled(self):
        """Test health check when provider is disabled."""
        with patch.dict(os.environ, {"GUPPY_SAPI_STT_ENABLED": "false"}):
            provider = SAPISTTProvider()
            health = await provider.health_check()
            assert health is False

    @pytest.mark.asyncio
    async def test_transcribe_not_available(self):
        """Test transcribe when provider not available."""
        with patch.dict(os.environ, {"GUPPY_SAPI_STT_ENABLED": "false"}):
            provider = SAPISTTProvider()
            with pytest.raises(RuntimeError, match="SAPI5 STT provider not available"):
                await provider.transcribe(b"test audio", language="en-US")


class TestFallbackChainOrchestrator:
    """Test STT fallback orchestration."""

    def test_init(self):
        """Test orchestrator initialization."""
        orchestrator = FallbackChainOrchestrator()
        assert orchestrator.google_provider is not None
        assert orchestrator.whisper_provider is not None
        assert orchestrator.sapi_provider is not None

    @pytest.mark.asyncio
    async def test_health_check_all_unavailable(self):
        """Test health check when all providers unavailable."""
        with patch.dict(
            os.environ,
            {
                "GUPPY_GOOGLE_STT_ENABLED": "false",
                "GUPPY_WHISPER_STT_ENABLED": "false",
                "GUPPY_SAPI_STT_ENABLED": "false",
            },
        ):
            orchestrator = FallbackChainOrchestrator()
            health = await orchestrator.health_check()
            # Should return False if no providers available
            assert health is False

    @pytest.mark.asyncio
    async def test_transcribe_all_fail(self):
        """Test transcribe when all providers fail."""
        orchestrator = FallbackChainOrchestrator()
        
        # Mock all providers to fail
        orchestrator.google_provider.transcribe = AsyncMock(
            side_effect=Exception("Google API error")
        )
        orchestrator.whisper_provider.transcribe = AsyncMock(
            side_effect=Exception("Whisper API error")
        )
        orchestrator.sapi_provider.transcribe = AsyncMock(
            side_effect=Exception("SAPI error")
        )

        with pytest.raises(RuntimeError, match="STT failed"):
            await orchestrator.transcribe(b"test audio", language="en-US")

    @pytest.mark.asyncio
    async def test_transcribe_google_success(self):
        """Test transcribe when Google succeeds."""
        orchestrator = FallbackChainOrchestrator()
        
        expected_result = STTResult(
            text="Hello world",
            confidence=0.95,
            provider="google_stt",
            duration_ms=100.0,
            language="en-US",
            is_final=True,
            error=None,
        )

        orchestrator.google_provider.transcribe = AsyncMock(
            return_value=expected_result
        )
        orchestrator.whisper_provider.transcribe = AsyncMock(
            side_effect=Exception("Should not be called")
        )

        result = await orchestrator.transcribe(b"test audio", language="en-US")

        assert result.text == "Hello world"
        assert result.provider == "google_stt"
        assert result.error is None

    @pytest.mark.asyncio
    async def test_transcribe_google_fails_whisper_succeeds(self):
        """Test fallback: Google fails, Whisper succeeds."""
        orchestrator = FallbackChainOrchestrator()
        
        google_result = STTResult(
            text="",
            confidence=0.0,
            provider="google_stt",
            duration_ms=100.0,
            language="en-US",
            is_final=True,
            error="Google API error",
        )

        whisper_result = STTResult(
            text="Hello from Whisper",
            confidence=0.92,
            provider="whisper_stt",
            duration_ms=150.0,
            language="en-US",
            is_final=True,
            error=None,
        )

        orchestrator.google_provider.transcribe = AsyncMock(
            return_value=google_result
        )
        orchestrator.whisper_provider.transcribe = AsyncMock(
            return_value=whisper_result
        )
        # Note: sapi runs in parallel with whisper in the orchestrator's race,
        # so we give it a slow result rather than an exception that would
        # fire concurrently. Whisper's faster path wins the race.
        slow_sapi = STTResult(
            text="late sapi",
            confidence=0.5,
            provider="sapi_stt",
            duration_ms=999.0,
            language="en-US",
        )
        async def _slow(*args, **kwargs):
            await asyncio.sleep(1.0)
            return slow_sapi
        orchestrator.sapi_provider.transcribe = _slow

        result = await orchestrator.transcribe(b"test audio", language="en-US")

        assert result.text == "Hello from Whisper"
        assert result.provider == "whisper_stt"
        chain = result.metadata.get("fallback_chain", [])
        # Provider names in chain are "google_stt" and "whisper_stt"
        assert any("google" in p for p in chain)
        assert any("whisper" in p for p in chain)


class TestAudioEventTelemetry:
    """Test audio event recording and telemetry."""

    def test_record_audio_event(self):
        """Test recording an audio event."""
        from guppy.voice import record_audio_event, get_audio_telemetry, clear_audio_telemetry
        
        clear_audio_telemetry()
        
        event = AudioEvent(
            event_type=AudioEventType.STT_SUCCESS,
            provider="google",
            output_text="Hello world",
            duration_ms=100.0,
        )
        
        record_audio_event(event)
        
        events = get_audio_telemetry()
        assert len(events) == 1
        assert events[0].event_type == AudioEventType.STT_SUCCESS
        assert events[0].provider == "google"
        assert events[0].output_text == "Hello world"

    def test_get_audio_telemetry_limit(self):
        """Test getting telemetry with limit."""
        from guppy.voice import record_audio_event, get_audio_telemetry, clear_audio_telemetry
        
        clear_audio_telemetry()
        
        # Record 5 events
        for i in range(5):
            event = AudioEvent(
                event_type=AudioEventType.STT_SUCCESS,
                provider=f"provider_{i}",
                duration_ms=float(i * 10),
            )
            record_audio_event(event)
        
        # Get with limit
        recent = get_audio_telemetry(limit=2)
        assert len(recent) == 2
        assert recent[0].provider == "provider_3"
        assert recent[1].provider == "provider_4"

    def test_clear_audio_telemetry(self):
        """Test clearing telemetry."""
        from guppy.voice import record_audio_event, get_audio_telemetry, clear_audio_telemetry
        
        clear_audio_telemetry()
        
        event = AudioEvent(
            event_type=AudioEventType.STT_SUCCESS,
            provider="google",
        )
        record_audio_event(event)
        
        assert len(get_audio_telemetry()) == 1
        
        clear_audio_telemetry()
        assert len(get_audio_telemetry()) == 0


class TestFacadeTranscribe:
    """Tests for the high-level facade transcribe() and listen() wiring."""

    @pytest.mark.asyncio
    async def test_transcribe_records_start_and_success_events(self):
        from guppy.voice import transcribe, clear_audio_telemetry, get_audio_telemetry
        from guppy.voice import voice as voice_facade

        clear_audio_telemetry()
        fake_result = STTResult(
            text="hello world",
            confidence=0.95,
            provider="google_stt",
            duration_ms=120.0,
            language="en-US",
            metadata={"fallback_chain": ["google_stt"]},
        )
        fake = MagicMock()
        fake.transcribe = AsyncMock(return_value=fake_result)
        voice_facade._stt_orchestrator = fake

        result = await transcribe(b"\x00" * 16, language="en-US")

        assert result.text == "hello world"
        assert result.provider == "google_stt"
        events = get_audio_telemetry()
        types = [e.event_type for e in events]
        assert AudioEventType.STT_START in types
        assert AudioEventType.STT_SUCCESS in types
        assert AudioEventType.STT_FALLBACK not in types
        start = next(e for e in events if e.event_type == AudioEventType.STT_START)
        success = next(e for e in events if e.event_type == AudioEventType.STT_SUCCESS)
        assert success.metadata.get("utterance_id") == start.event_id

    @pytest.mark.asyncio
    async def test_transcribe_records_fallback_event_when_secondary_wins(self):
        from guppy.voice import transcribe, clear_audio_telemetry, get_audio_telemetry
        from guppy.voice import voice as voice_facade

        clear_audio_telemetry()
        fake_result = STTResult(
            text="from whisper",
            confidence=0.88,
            provider="whisper_stt",
            duration_ms=320.0,
            language="en-US",
            metadata={"fallback_chain": ["google_stt", "whisper_stt", "sapi_stt"]},
        )
        fake = MagicMock()
        fake.transcribe = AsyncMock(return_value=fake_result)
        voice_facade._stt_orchestrator = fake

        await transcribe(b"\x00" * 16)

        events = get_audio_telemetry()
        types = [e.event_type for e in events]
        assert AudioEventType.STT_FALLBACK in types
        assert AudioEventType.STT_SUCCESS in types
        fallback = next(e for e in events if e.event_type == AudioEventType.STT_FALLBACK)
        assert fallback.provider == "whisper_stt"
        assert fallback.fallback_chain == ["google_stt", "whisper_stt", "sapi_stt"]

    @pytest.mark.asyncio
    async def test_transcribe_records_error_event(self):
        from guppy.voice import transcribe, clear_audio_telemetry, get_audio_telemetry
        from guppy.voice import voice as voice_facade

        clear_audio_telemetry()
        fake_result = STTResult(
            text="",
            confidence=0.0,
            provider="fallback_chain",
            duration_ms=10000.0,
            language="en-US",
            error="all_providers_failed",
            metadata={"fallback_chain": ["google_stt", "whisper_stt", "sapi_stt"]},
        )
        fake = MagicMock()
        fake.transcribe = AsyncMock(return_value=fake_result)
        voice_facade._stt_orchestrator = fake

        result = await transcribe(b"\x00" * 16)
        assert result.error == "all_providers_failed"
        types = [e.event_type for e in get_audio_telemetry()]
        assert AudioEventType.STT_ERROR in types

    @pytest.mark.asyncio
    async def test_transcribe_swallows_orchestrator_exception(self):
        from guppy.voice import transcribe, clear_audio_telemetry, get_audio_telemetry
        from guppy.voice import voice as voice_facade

        clear_audio_telemetry()
        fake = MagicMock()
        fake.transcribe = AsyncMock(side_effect=RuntimeError("network down"))
        voice_facade._stt_orchestrator = fake

        result = await transcribe(b"\x00" * 16)
        assert result.error == "network down"
        assert result.text == ""
        types = [e.event_type for e in get_audio_telemetry()]
        assert AudioEventType.STT_ERROR in types

    @pytest.mark.asyncio
    async def test_listen_no_microphone_yields_no_microphone_error(self):
        from guppy.voice import listen, clear_audio_telemetry

        clear_audio_telemetry()
        async with listen() as result:
            assert result.error == "no_microphone"
            assert result.text == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
