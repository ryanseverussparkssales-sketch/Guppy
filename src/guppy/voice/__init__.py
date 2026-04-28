"""
Voice Module
============

High-level voice operations: speech-to-text (STT), text-to-speech (TTS),
wake-word detection, and audio telemetry.
"""

# Core types
from guppy.voice.core import (
    AudioEvent,
    AudioEventType,
    AudioQualityFeedback,
    AudioQualityRating,
    STTResult,
    TTSResult,
    VoiceConfig,
    STTProvider,
    TTSProvider,
    WakeWordProvider,
)

# Facade API
from guppy.voice.voice import (
    listen,
    speak,
    synthesize,
    stream_listen,
    stream_speak,
    transcribe,
    get_audio_telemetry,
    clear_audio_telemetry,
    get_voice_config,
    set_voice_config,
    set_active_stt_provider,
    set_active_tts_provider,
    get_tts_cache_stats,
    clear_tts_cache,
    record_audio_event,
    record_audio_quality_feedback,
)

# Orchestrators
from guppy.voice.stt.fallback_orchestrator import FallbackChainOrchestrator
from guppy.voice.tts.fallback_orchestrator import TTSFallbackOrchestrator

# STT Providers
from guppy.voice.stt.google_stt import GoogleSTTProvider
from guppy.voice.stt.whisper_stt import WhisperSTTProvider
from guppy.voice.stt.sapi_stt import SAPISTTProvider

# TTS Providers
from guppy.voice.tts.kokoro_provider import KokoroTTSProvider
from guppy.voice.tts.sapi_provider import SAPITTSProvider
from guppy.voice.tts.elevenlabs_provider import ElevenLabsTTSProvider
from guppy.voice.tts.cache import TTSCache

# Wake-word
from guppy.voice.wake_word import (
    WakeWordDetector,
    WakeWordConfig,
    WakeWordEvent,
    EnergyThresholdWakeWordProvider,
    PorcupineWakeWordProvider,
)

# Test utilities
from guppy.voice.integration import (
    MockSTTProvider,
    MockTTSProvider,
    MockWakeWordProvider,
    generate_test_audio_silence,
    generate_test_audio_white_noise,
    generate_test_audio_sine_wave,
)

# Push-to-talk
from guppy.voice.ppt import (
    PushToTalkState,
    PushToTalkEvent,
    PushToTalkStateMachine,
)

__all__ = [
    "AudioEvent", "AudioEventType", "AudioQualityFeedback", "AudioQualityRating",
    "STTResult", "TTSResult", "VoiceConfig",
    "STTProvider", "TTSProvider", "WakeWordProvider",
    "listen", "speak", "synthesize", "stream_listen", "stream_speak", "transcribe",
    "get_audio_telemetry", "clear_audio_telemetry",
    "get_voice_config", "set_voice_config",
    "set_active_stt_provider", "set_active_tts_provider",
    "get_tts_cache_stats", "clear_tts_cache",
    "record_audio_event", "record_audio_quality_feedback",
    "FallbackChainOrchestrator", "TTSFallbackOrchestrator",
    "GoogleSTTProvider", "WhisperSTTProvider", "SAPISTTProvider",
    "KokoroTTSProvider", "SAPITTSProvider", "ElevenLabsTTSProvider", "TTSCache",
    "WakeWordDetector", "WakeWordConfig", "WakeWordEvent",
    "EnergyThresholdWakeWordProvider", "PorcupineWakeWordProvider",
    "MockSTTProvider", "MockTTSProvider", "MockWakeWordProvider",
    "generate_test_audio_silence", "generate_test_audio_white_noise", "generate_test_audio_sine_wave",
    "PushToTalkState", "PushToTalkEvent", "PushToTalkStateMachine",
]
