"""
Voice Module Facade
====================

High-level async API for voice operations.
"""

import asyncio
import logging
import os
from typing import Optional, AsyncGenerator, AsyncContextManager
from datetime import datetime
from contextlib import asynccontextmanager

from guppy.voice.core import (
    STTResult,
    TTSResult,
    VoiceConfig,
    AudioEvent,
    AudioEventType,
    AudioQualityRating,
    AudioQualityFeedback,
)
from guppy.voice.stt.fallback_orchestrator import FallbackChainOrchestrator

logger = logging.getLogger(__name__)


_stt_orchestrator: Optional[FallbackChainOrchestrator] = None
_tts_orchestrator = None  # TTSFallbackOrchestrator (lazy)
_tts_cache = None  # TTSCache (lazy)
_voice_config: Optional[VoiceConfig] = None
_telemetry_events: list[AudioEvent] = []
_MAX_TELEMETRY_EVENTS = 1000


def _ensure_orchestrator() -> FallbackChainOrchestrator:
    global _stt_orchestrator
    if _stt_orchestrator is None:
        _stt_orchestrator = FallbackChainOrchestrator()
    return _stt_orchestrator


def _ensure_tts_orchestrator():
    global _tts_orchestrator
    if _tts_orchestrator is None:
        from guppy.voice.tts.fallback_orchestrator import TTSFallbackOrchestrator
        _tts_orchestrator = TTSFallbackOrchestrator()
    return _tts_orchestrator


def _ensure_tts_cache():
    global _tts_cache
    if _tts_cache is None:
        from guppy.voice.tts.cache import TTSCache
        _tts_cache = TTSCache(max_entries=256)
    return _tts_cache


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.environ.get(key, str(default)))
    except (ValueError, TypeError):
        return default


def _ensure_config() -> VoiceConfig:
    global _voice_config
    if _voice_config is None:
        _voice_config = VoiceConfig(
            active_stt_provider=os.environ.get("GUPPY_STT_PROVIDER", "fallback_chain"),
            active_tts_provider=os.environ.get("GUPPY_TTS_PROVIDER", "kokoro"),
            active_wake_word_provider=None,
            stt_language=os.environ.get("GUPPY_STT_LANGUAGE", "en-US"),
            tts_voice=os.environ.get("GUPPY_TTS_VOICE", "bm_lewis"),
            tts_speed=_env_float("GUPPY_TTS_RATE", 1.0),
            tts_pitch=0.0,
            enable_telemetry=True,
            enable_quality_feedback=True,
            fallback_enabled=True,
        )
    return _voice_config


def record_audio_event(event: AudioEvent) -> None:
    global _telemetry_events
    config = _ensure_config()
    if not config.enable_telemetry:
        return
    _telemetry_events.append(event)
    if len(_telemetry_events) > _MAX_TELEMETRY_EVENTS:
        _telemetry_events = _telemetry_events[-_MAX_TELEMETRY_EVENTS:]


def get_audio_telemetry(limit: Optional[int] = None) -> list[AudioEvent]:
    if limit is None:
        return _telemetry_events.copy()
    return _telemetry_events[-limit:].copy()


def clear_audio_telemetry() -> None:
    global _telemetry_events
    _telemetry_events = []


async def transcribe(
    audio_data: bytes,
    language: Optional[str] = None,
) -> STTResult:
    """Transcribe pre-captured audio via the STT fallback orchestrator."""
    config = _ensure_config()
    orchestrator = _ensure_orchestrator()
    lang = language or config.stt_language

    start_event = AudioEvent(
        event_type=AudioEventType.STT_START,
        provider="fallback_chain",
        metadata={"language": lang, "audio_bytes": len(audio_data)},
    )
    record_audio_event(start_event)

    try:
        result = await orchestrator.transcribe(audio_data, language=lang)
    except Exception as e:
        logger.error(f"transcribe() unexpected error: {e}")
        record_audio_event(AudioEvent(
            event_type=AudioEventType.STT_ERROR,
            provider="fallback_chain",
            error_message=str(e),
            metadata={"utterance_id": start_event.event_id},
        ))
        return STTResult(
            text="", confidence=0.0, provider="fallback_chain",
            duration_ms=0.0, language=lang, error=str(e),
        )

    chain = list(result.metadata.get("fallback_chain", []))
    if result.error:
        record_audio_event(AudioEvent(
            event_type=AudioEventType.STT_ERROR,
            provider=result.provider,
            duration_ms=result.duration_ms,
            error_message=result.error,
            fallback_chain=chain,
            metadata={"utterance_id": start_event.event_id},
        ))
    else:
        primary_won = bool(chain) and chain[0] == result.provider
        if chain and not primary_won:
            record_audio_event(AudioEvent(
                event_type=AudioEventType.STT_FALLBACK,
                provider=result.provider,
                duration_ms=result.duration_ms,
                fallback_chain=chain,
                metadata={"utterance_id": start_event.event_id},
            ))
        record_audio_event(AudioEvent(
            event_type=AudioEventType.STT_SUCCESS,
            provider=result.provider,
            duration_ms=result.duration_ms,
            output_text=result.text,
            fallback_chain=chain,
            metadata={
                "utterance_id": start_event.event_id,
                "confidence": result.confidence,
                "language": result.language,
            },
        ))
    return result


async def _capture_microphone_audio(
    duration_s: float = 5.0,
    sample_rate: int = 16000,
    channels: int = 1,
) -> bytes:
    """Capture audio from the default microphone. Returns empty bytes if unavailable."""
    try:
        import sounddevice as sd  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        logger.debug("sounddevice/numpy not installed — microphone capture unavailable")
        return b""
    try:
        recording = await asyncio.to_thread(
            sd.rec,
            int(duration_s * sample_rate),
            samplerate=sample_rate,
            channels=channels,
            dtype="int16",
            blocking=True,
        )
        return recording.tobytes()
    except Exception as exc:
        logger.warning("Microphone capture failed: %s", exc)
        return b""


async def _stream_microphone_audio_generator(
    sample_rate: int = 16000,
    chunk_s: float = 0.1,
    channels: int = 1,
) -> AsyncGenerator[bytes, None]:
    """Yield raw PCM chunks from the default microphone until cancelled."""
    try:
        import sounddevice as sd  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        logger.debug("sounddevice/numpy not installed — microphone streaming unavailable")
        return
    chunk_frames = int(sample_rate * chunk_s)
    try:
        with sd.RawInputStream(
            samplerate=sample_rate,
            channels=channels,
            dtype="int16",
            blocksize=chunk_frames,
        ) as stream:
            while True:
                data, _ = await asyncio.to_thread(stream.read, chunk_frames)
                if data:
                    yield bytes(data)
    except Exception as exc:
        logger.warning("Microphone stream failed: %s", exc)


def _stream_microphone_audio(
    sample_rate: int = 16000,
    chunk_s: float = 0.1,
) -> Optional[AsyncGenerator[bytes, None]]:
    """Return an async generator of PCM chunks, or None if sounddevice unavailable."""
    try:
        import sounddevice  # noqa: F401 — just checking availability
        return _stream_microphone_audio_generator(sample_rate=sample_rate, chunk_s=chunk_s)
    except ImportError:
        return None


@asynccontextmanager
async def listen():
    config = _ensure_config()
    try:
        audio_data = await _capture_microphone_audio()
        if not audio_data:
            yield STTResult(
                text="", confidence=0.0, provider="microphone",
                duration_ms=0.0, language=config.stt_language,
                error="no_microphone",
            )
            return
        result = await transcribe(audio_data, language=config.stt_language)
        yield result
    except Exception as e:
        logger.error(f"Error in listen(): {e}")
        raise


async def stream_listen(language: Optional[str] = None):
    config = _ensure_config()
    orchestrator = _ensure_orchestrator()
    lang = language or config.stt_language

    audio_stream = _stream_microphone_audio()
    if audio_stream is None:
        yield STTResult(
            text="", confidence=0.0, provider="microphone",
            duration_ms=0.0, language=lang, error="no_microphone",
        )
        return

    async for result in orchestrator.stream_transcribe(audio_stream, language=lang):
        chain = list(result.metadata.get("fallback_chain", []))
        record_audio_event(AudioEvent(
            event_type=AudioEventType.STT_SUCCESS if not result.error else AudioEventType.STT_ERROR,
            provider=result.provider,
            duration_ms=result.duration_ms,
            output_text=result.text or None,
            error_message=result.error,
            fallback_chain=chain,
            metadata={"is_final": result.is_final, "language": result.language},
        ))
        yield result


async def synthesize(
    text: str,
    voice: Optional[str] = None,
    use_cache: bool = True,
) -> TTSResult:
    """
    Synthesize text to speech via the TTS fallback orchestrator.

    Records TTS_START, TTS_SUCCESS / TTS_ERROR / TTS_FALLBACK events
    with utterance_id linking. Caches successful synthesis when
    use_cache is True (default).
    """
    config = _ensure_config()
    orchestrator = _ensure_tts_orchestrator()
    cache = _ensure_tts_cache() if use_cache else None

    start_event = AudioEvent(
        event_type=AudioEventType.TTS_START,
        provider="fallback_chain",
        input_text=text,
        metadata={"voice": voice, "text_len": len(text)},
    )
    record_audio_event(start_event)

    # Cache hit?
    if cache is not None:
        cached = cache.get(text, voice, "fallback_chain")
        if cached is not None:
            record_audio_event(AudioEvent(
                event_type=AudioEventType.TTS_SUCCESS,
                provider=cached.provider,
                duration_ms=0.0,  # cache hit
                input_text=text,
                metadata={
                    "utterance_id": start_event.event_id,
                    "cache_hit": True,
                    "voice": voice,
                },
            ))
            return cached

    try:
        result = await orchestrator.synthesize(text, voice=voice)
    except Exception as e:
        logger.error(f"synthesize() unexpected error: {e}")
        record_audio_event(AudioEvent(
            event_type=AudioEventType.TTS_ERROR,
            provider="fallback_chain",
            input_text=text,
            error_message=str(e),
            metadata={"utterance_id": start_event.event_id},
        ))
        return TTSResult(
            audio_data=b"", provider="fallback_chain",
            duration_ms=0.0, sample_rate=0, channels=1,
            format="wav", playback_duration_s=0.0, error=str(e),
        )

    chain = list(result.metadata.get("fallback_chain", []))
    if result.error:
        record_audio_event(AudioEvent(
            event_type=AudioEventType.TTS_ERROR,
            provider=result.provider,
            duration_ms=result.duration_ms,
            input_text=text,
            error_message=result.error,
            fallback_chain=chain,
            metadata={"utterance_id": start_event.event_id},
        ))
    else:
        primary_won = bool(chain) and chain[0] == result.provider
        if chain and not primary_won:
            record_audio_event(AudioEvent(
                event_type=AudioEventType.TTS_FALLBACK,
                provider=result.provider,
                duration_ms=result.duration_ms,
                fallback_chain=chain,
                metadata={"utterance_id": start_event.event_id},
            ))
        record_audio_event(AudioEvent(
            event_type=AudioEventType.TTS_SUCCESS,
            provider=result.provider,
            duration_ms=result.duration_ms,
            input_text=text,
            fallback_chain=chain,
            metadata={
                "utterance_id": start_event.event_id,
                "voice": voice,
                "playback_duration_s": result.playback_duration_s,
            },
        ))
        if cache is not None:
            cache.put(text, voice, "fallback_chain", result)
    return result


async def speak(text: str, voice: Optional[str] = None) -> TTSResult:
    """
    Text-to-speech with fallback support.

    Synthesizes text via TTS orchestrator (ElevenLabs -> Kokoro -> SAPI)
    and returns the TTSResult. Audio playback (writing to speaker) is
    delegated to the platform wrapper; this returns the raw audio bytes
    in the result.
    """
    return await synthesize(text, voice=voice)


async def stream_speak(text: str, voice: Optional[str] = None):
    """Stream-based text-to-speech. Yields audio chunks."""
    result = await synthesize(text, voice=voice)
    if result.audio_data and not result.error:
        yield result.audio_data


def get_voice_config() -> VoiceConfig:
    return _ensure_config()


def set_voice_config(config: VoiceConfig) -> None:
    global _voice_config
    _voice_config = config


def set_active_stt_provider(provider_name: str) -> None:
    config = _ensure_config()
    config.active_stt_provider = provider_name


def set_active_tts_provider(provider_name: str) -> None:
    config = _ensure_config()
    config.active_tts_provider = provider_name


def get_tts_cache_stats() -> dict:
    cache = _ensure_tts_cache()
    return cache.stats()


def clear_tts_cache() -> None:
    cache = _ensure_tts_cache()
    cache.clear()


def stop() -> None:
    """Interrupt active TTS playback. No-op until async speaker output is wired."""
    logger.debug("[voice] stop() called — no active playback to interrupt")


class GuppyVoice:
    """Compatibility shim for routes that still call owner.voice.GuppyVoice().
    Phase 6.0 will rewrite those routes to call the async facade directly.
    """

    def transcribe_audio(self, path: str) -> str:
        result = asyncio.get_event_loop().run_until_complete(
            transcribe(open(path, "rb").read())  # noqa: WPS515
        )
        return result.text if result else ""


def record_audio_quality_feedback(
    rating: AudioQualityRating,
    provider: str,
    event_type: AudioEventType,
    notes: str = "",
) -> None:
    config = _ensure_config()
    if not config.enable_quality_feedback:
        return
    feedback = AudioQualityFeedback(
        rating=rating, provider=provider, event_type=event_type,
        timestamp=datetime.utcnow(), notes=notes,
    )
    event = AudioEvent(
        event_type=AudioEventType.AUDIO_QUALITY_FEEDBACK,
        provider=provider, timestamp=feedback.timestamp,
        metadata=feedback.to_dict(),
    )
    record_audio_event(event)
