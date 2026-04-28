"""
Voice Module Core Types
=======================

Type definitions and base classes for the audio pipeline.
All types are mypy-compliant with full type hints.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Optional
import uuid


class AudioEventType(str, Enum):
    """Types of audio events for telemetry."""
    STT_START = "stt_start"
    STT_SUCCESS = "stt_success"
    STT_ERROR = "stt_error"
    STT_FALLBACK = "stt_fallback"
    TTS_START = "tts_start"
    TTS_SUCCESS = "tts_success"
    TTS_ERROR = "tts_error"
    TTS_FALLBACK = "tts_fallback"
    WAKE_WORD_DETECTED = "wake_word_detected"
    PUSH_TO_TALK_START = "ppt_start"
    PUSH_TO_TALK_END = "ppt_end"
    AUDIO_QUALITY_FEEDBACK = "audio_quality_feedback"


class AudioQualityRating(str, Enum):
    """User-provided quality rating for audio output."""
    POOR = "poor"
    FAIR = "fair"
    GOOD = "good"
    EXCELLENT = "excellent"


@dataclass
class AudioQualityFeedback:
    """User feedback on audio quality (TTS output, STT accuracy, etc.)."""
    rating: AudioQualityRating
    provider: str
    event_type: AudioEventType  # e.g., TTS_SUCCESS, STT_SUCCESS
    timestamp: datetime = field(default_factory=datetime.utcnow)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for storage."""
        return {
            "rating": self.rating.value,
            "provider": self.provider,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "notes": self.notes,
        }


@dataclass
class AudioEvent:
    """
    Telemetry event for all audio operations.

    Used to track STT/TTS latency, fallback triggers, errors, and user quality ratings.
    Every audio operation produces one or more AudioEvents.

    Fields:
        event_id: Unique identifier for this event
        event_type: Type of audio event (see AudioEventType)
        provider: Which provider handled this (e.g., "google_stt", "kokoro_tts", "ollama")
        timestamp: When the event occurred
        duration_ms: How long the operation took (None if in-progress)
        input_text: Text input (for TTS events)
        output_text: Transcribed text (for STT events)
        error_message: Error details if event_type is *_ERROR
        fallback_chain: List of providers tried before success (for *_FALLBACK events)
        latency_p95: P95 latency for this provider (cached from dashboard)
        cost_estimate: Estimated cost for this operation (for cloud providers)
        metadata: Additional context (language, quality settings, etc.)
    """
    event_type: AudioEventType
    provider: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    duration_ms: Optional[float] = None
    input_text: Optional[str] = None
    output_text: Optional[str] = None
    error_message: Optional[str] = None
    fallback_chain: list[str] = field(default_factory=list)
    latency_p95: Optional[float] = None
    cost_estimate: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for storage/API."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "provider": self.provider,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
            "input_text": self.input_text,
            "output_text": self.output_text,
            "error_message": self.error_message,
            "fallback_chain": self.fallback_chain,
            "latency_p95": self.latency_p95,
            "cost_estimate": self.cost_estimate,
            "metadata": self.metadata,
        }


@dataclass
class STTResult:
    """Result of a speech-to-text operation."""
    text: str
    confidence: float  # 0.0 to 1.0
    provider: str  # Which STT provider produced this
    duration_ms: float  # How long transcription took
    language: Optional[str] = None
    is_final: bool = True
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "text": self.text,
            "confidence": self.confidence,
            "provider": self.provider,
            "duration_ms": self.duration_ms,
            "language": self.language,
            "is_final": self.is_final,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class TTSResult:
    """Result of a text-to-speech operation."""
    audio_data: bytes
    provider: str  # Which TTS provider produced this
    duration_ms: float  # How long generation took
    sample_rate: int  # Audio sample rate (e.g., 24000)
    channels: int  # Mono (1) or stereo (2)
    format: str  # "wav", "mp3", "pcm", etc.
    playback_duration_s: float  # How long the audio will play
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary (audio_data is base64 encoded)."""
        import base64
        return {
            "audio_data_b64": base64.b64encode(self.audio_data).decode("utf-8"),
            "provider": self.provider,
            "duration_ms": self.duration_ms,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "format": self.format,
            "playback_duration_s": self.playback_duration_s,
            "error": self.error,
            "metadata": self.metadata,
        }


class STTProvider(ABC):
    """Abstract base class for Speech-to-Text providers."""

    name: str

    @abstractmethod
    async def transcribe(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
        **kwargs: Any,
    ) -> STTResult:
        """
        Transcribe audio data to text.

        Args:
            audio_data: Raw audio bytes (WAV, PCM, etc.)
            language: Language hint (e.g., "en", "es")
            **kwargs: Provider-specific options

        Returns:
            STTResult with transcribed text and confidence

        Raises:
            Exception: On transcription failure (caught by fallback orchestrator)
        """
        pass

    @abstractmethod
    async def stream_transcribe(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        language: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[STTResult, None]:
        """
        Stream-based transcription (continuous listening).

        Args:
            audio_stream: Async generator yielding audio chunks
            language: Language hint
            **kwargs: Provider-specific options

        Yields:
            STTResult for each completed phrase/sentence
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is available (API key valid, service reachable, etc.)."""
        pass


class TTSProvider(ABC):
    """Abstract base class for Text-to-Speech providers."""

    name: str

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs: Any,
    ) -> TTSResult:
        """
        Synthesize text to speech.

        Args:
            text: Text to speak
            voice: Voice selection (provider-specific, e.g., "en-US-Neural2-A")
            **kwargs: Provider-specific options (speed, pitch, etc.)

        Returns:
            TTSResult with audio data

        Raises:
            Exception: On synthesis failure (caught by fallback orchestrator)
        """
        pass

    @abstractmethod
    async def stream_synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream-based synthesis (returns audio chunks as they're generated).

        Args:
            text: Text to speak
            voice: Voice selection
            **kwargs: Provider-specific options

        Yields:
            Audio chunks (raw bytes)
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is available."""
        pass


class WakeWordProvider(ABC):
    """Abstract base class for wake-word detection."""

    name: str

    @abstractmethod
    async def detect(
        self,
        audio_data: bytes,
        **kwargs: Any,
    ) -> tuple[bool, float]:
        """
        Detect wake word in audio.

        Args:
            audio_data: Raw audio bytes
            **kwargs: Provider-specific options

        Returns:
            (detected: bool, confidence: float)

        Raises:
            Exception: On detection failure
        """
        pass

    @abstractmethod
    async def stream_detect(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        **kwargs: Any,
    ) -> AsyncGenerator[tuple[bool, float], None]:
        """
        Stream-based detection (continuous listening).

        Args:
            audio_stream: Async generator yielding audio chunks
            **kwargs: Provider-specific options

        Yields:
            (detected: bool, confidence: float) for each analysis window
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is available."""
        pass


@dataclass
class VoiceConfig:
    """Runtime voice configuration."""
    active_stt_provider: str  # Name of active STT provider
    active_tts_provider: str  # Name of active TTS provider
    active_wake_word_provider: Optional[str]  # Name of active wake-word provider
    stt_language: str = "en-US"
    tts_voice: str = "en-US-Neural2-A"  # Default voice (provider-specific)
    tts_speed: float = 1.0  # 0.5 to 2.0
    tts_pitch: float = 0.0  # -20 to 20 semitones
    audio_input_device: Optional[str] = None  # "default", device name, or None
    audio_output_device: Optional[str] = None
    enable_telemetry: bool = True
    enable_quality_feedback: bool = True
    fallback_enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "active_stt_provider": self.active_stt_provider,
            "active_tts_provider": self.active_tts_provider,
            "active_wake_word_provider": self.active_wake_word_provider,
            "stt_language": self.stt_language,
            "tts_voice": self.tts_voice,
            "tts_speed": self.tts_speed,
            "tts_pitch": self.tts_pitch,
            "audio_input_device": self.audio_input_device,
            "audio_output_device": self.audio_output_device,
            "enable_telemetry": self.enable_telemetry,
            "enable_quality_feedback": self.enable_quality_feedback,
            "fallback_enabled": self.fallback_enabled,
        }
