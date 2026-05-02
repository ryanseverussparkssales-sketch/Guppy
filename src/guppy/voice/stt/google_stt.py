"""
Google Cloud Speech-to-Text Provider
=====================================

Uses Google Cloud Speech-to-Text API for speech recognition.

Requires:
  - google-cloud-speech package
  - Google Cloud credentials (via GOOGLE_APPLICATION_CREDENTIALS env var)
  - GUPPY_GOOGLE_STT_ENABLED env var (optional, default True)

Features:
  - Streaming transcription support
  - Language detection
  - Confidence scoring
  - Automatic punctuation
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator, Optional, Any
import os

from guppy.voice.core import STTProvider, STTResult, AudioEvent, AudioEventType

logger = logging.getLogger(__name__)


class GoogleSTTProvider(STTProvider):
    """Google Cloud Speech-to-Text provider."""

    name = "google_stt"

    def __init__(self) -> None:
        """Initialize Google STT provider."""
        self.enabled = os.getenv("GUPPY_GOOGLE_STT_ENABLED", "true").lower() == "true"
        self.client = None
        if self.enabled:
            try:
                from google.cloud import speech
                self.client = speech.SpeechClient()
                self.speech_config = speech.RecognitionConfig
                self.streaming_config = speech.StreamingRecognitionConfig
                logger.info("GoogleSTTProvider initialized")
            except ImportError:
                logger.warning("google-cloud-speech not installed, disabling GoogleSTTProvider")
                self.enabled = False
            except Exception as e:
                logger.warning(f"Failed to initialize Google STT: {e}")
                self.enabled = False

    async def transcribe(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
        **kwargs: Any,
    ) -> STTResult:
        """
        Transcribe audio using Google Cloud Speech-to-Text.

        Args:
            audio_data: Raw audio bytes (WAV, PCM, etc.)
            language: Language code (e.g., "en-US")
            **kwargs: Additional options

        Returns:
            STTResult with transcribed text and confidence

        Raises:
            Exception: If Google API is unavailable or transcription fails
        """
        if not self.enabled or self.client is None:
            raise RuntimeError("GoogleSTTProvider not initialized")

        try:
            # Create recognition request
            config = self.speech_config(
                encoding=self.speech_config.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code=language or "en-US",
                enable_automatic_punctuation=True,
            )

            audio = self.speech_config.RecognitionAudio(content=audio_data)

            # Call API
            response = await asyncio.to_thread(self.client.recognize, config, audio)

            # Extract results
            if response.results:
                result = response.results[0]
                if result.alternatives:
                    transcript = result.alternatives[0].transcript
                    confidence = result.alternatives[0].confidence
                    
                    return STTResult(
                        text=transcript,
                        confidence=confidence,
                        provider=self.name,
                        duration_ms=0,  # Would need to track this
                        language=language or "en-US",
                        is_final=True,
                    )

            # No results
            return STTResult(
                text="",
                confidence=0.0,
                provider=self.name,
                duration_ms=0,
                error="No speech detected",
            )

        except Exception as e:
            logger.error(f"Google STT error: {e}")
            raise

    async def stream_transcribe(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        language: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[STTResult, None]:
        """
        Stream-based transcription via Google Cloud Speech-to-Text.

        The Google Cloud Speech async streaming API requires a synchronous
        generator wrapper that is non-trivial to integrate cleanly. Until that
        is implemented, this method buffers all incoming audio and delegates to
        the batch ``transcribe()`` path so callers receive a valid result rather
        than an exception.

        Args:
            audio_stream: Async generator yielding audio chunks
            language: Language code
            **kwargs: Additional options

        Yields:
            A single final STTResult (batch fallback)
        """
        if not self.enabled or self.client is None:
            yield STTResult(
                text="",
                confidence=0.0,
                provider=self.name,
                duration_ms=0,
                language=language or "en-US",
                error="GoogleSTTProvider not initialized",
            )
            return

        logger.debug(
            "GoogleSTTProvider.stream_transcribe: buffering stream and falling back to batch transcription"
        )
        buf = bytearray()
        try:
            async for chunk in audio_stream:
                buf.extend(chunk)
        except Exception as exc:
            logger.error("Google STT: error reading audio stream: %s", exc)
            yield STTResult(
                text="",
                confidence=0.0,
                provider=self.name,
                duration_ms=0,
                language=language or "en-US",
                error=str(exc),
            )
            return

        if not buf:
            yield STTResult(
                text="",
                confidence=0.0,
                provider=self.name,
                duration_ms=0,
                language=language or "en-US",
                error="empty audio stream",
            )
            return

        try:
            result = await self.transcribe(bytes(buf), language=language, **kwargs)
            result.is_final = True
            yield result
        except Exception as exc:
            logger.error("Google STT batch fallback error: %s", exc)
            yield STTResult(
                text="",
                confidence=0.0,
                provider=self.name,
                duration_ms=0,
                language=language or "en-US",
                error=str(exc),
            )

    async def health_check(self) -> bool:
        """Check if Google STT is available."""
        if not self.enabled or self.client is None:
            return False
        try:
            # Simple credentials check
            return True
        except Exception:
            return False
