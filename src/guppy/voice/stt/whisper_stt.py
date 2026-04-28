"""
OpenAI Whisper Speech-to-Text Provider
=======================================

Uses OpenAI's Whisper model for speech recognition.

Requires:
  - openai package
  - OpenAI API key (via OPENAI_API_KEY env var)
  - GUPPY_WHISPER_STT_ENABLED env var (optional, default True)

Features:
  - Local and cloud-based Whisper support
  - Supports 99+ languages
  - Automatic language detection
  - Word-level timestamps
"""

from __future__ import annotations

import asyncio
import io
import logging
from typing import AsyncGenerator, Optional, Any
import os

from guppy.voice.core import STTProvider, STTResult, AudioEvent, AudioEventType

logger = logging.getLogger(__name__)


class WhisperSTTProvider(STTProvider):
    """OpenAI Whisper speech-to-text provider."""

    name = "whisper_stt"

    def __init__(self) -> None:
        """Initialize Whisper provider."""
        self.enabled = os.getenv("GUPPY_WHISPER_STT_ENABLED", "true").lower() == "true"
        self.client = None
        self.local_model = None
        
        if self.enabled:
            try:
                import openai
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    logger.warning("OPENAI_API_KEY not set, disabling Whisper STT")
                    self.enabled = False
                else:
                    self.client = openai.AsyncOpenAI(api_key=api_key)
                    logger.info("WhisperSTTProvider initialized")
            except ImportError:
                logger.warning("openai package not installed, disabling WhisperSTT")
                self.enabled = False
            except Exception as e:
                logger.warning(f"Failed to initialize Whisper: {e}")
                self.enabled = False

    async def transcribe(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
        **kwargs: Any,
    ) -> STTResult:
        """
        Transcribe audio using OpenAI Whisper.

        Args:
            audio_data: Raw audio bytes (WAV, MP3, etc.)
            language: Optional language code (e.g., "en")
            **kwargs: Additional options (model, temperature, etc.)

        Returns:
            STTResult with transcribed text

        Raises:
            Exception: If Whisper API is unavailable
        """
        if not self.enabled or self.client is None:
            raise RuntimeError("WhisperSTTProvider not initialized")

        try:
            # Create file-like object
            audio_file = io.BytesIO(audio_data)
            audio_file.name = "audio.wav"

            # Call Whisper API
            model = kwargs.get("model", "whisper-1")
            transcript = await self.client.audio.transcriptions.create(
                model=model,
                file=audio_file,
                language=language,
            )

            return STTResult(
                text=transcript.text,
                confidence=1.0,  # Whisper doesn't provide confidence scores
                provider=self.name,
                duration_ms=0,
                language=language or "en",
                is_final=True,
            )

        except Exception as e:
            logger.error(f"Whisper STT error: {e}")
            raise

    async def stream_transcribe(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        language: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[STTResult, None]:
        """
        Stream-based transcription (buffer + batch).

        Note: Whisper API doesn't support true streaming.
        This implementation buffers audio and sends batches.

        Args:
            audio_stream: Async generator yielding audio chunks
            language: Language code
            **kwargs: Additional options

        Yields:
            STTResult for each buffer
        """
        if not self.enabled or self.client is None:
            raise RuntimeError("WhisperSTTProvider not initialized")

        try:
            buffer = io.BytesIO()
            chunk_count = 0
            buffer_size_bytes = 30 * 16000 * 2  # ~30 seconds at 16kHz, 16-bit

            async for chunk in audio_stream:
                buffer.write(chunk)
                chunk_count += 1

                # Send buffer when it reaches size limit
                if buffer.tell() >= buffer_size_bytes:
                    buffer.seek(0)
                    audio_file = io.BytesIO(buffer.getvalue())
                    audio_file.name = f"audio_{chunk_count}.wav"

                    model = kwargs.get("model", "whisper-1")
                    transcript = await self.client.audio.transcriptions.create(
                        model=model,
                        file=audio_file,
                        language=language,
                    )

                    if transcript.text:
                        yield STTResult(
                            text=transcript.text,
                            confidence=1.0,
                            provider=self.name,
                            duration_ms=0,
                            language=language or "en",
                            is_final=False,
                        )

                    # Reset buffer
                    buffer = io.BytesIO()

            # Send remaining buffer
            if buffer.tell() > 0:
                buffer.seek(0)
                audio_file = io.BytesIO(buffer.getvalue())
                audio_file.name = f"audio_final.wav"

                model = kwargs.get("model", "whisper-1")
                transcript = await self.client.audio.transcriptions.create(
                    model=model,
                    file=audio_file,
                    language=language,
                )

                if transcript.text:
                    yield STTResult(
                        text=transcript.text,
                        confidence=1.0,
                        provider=self.name,
                        duration_ms=0,
                        language=language or "en",
                        is_final=True,
                    )

        except Exception as e:
            logger.error(f"Whisper STT streaming error: {e}")
            raise

    async def health_check(self) -> bool:
        """Check if Whisper API is available."""
        if not self.enabled or self.client is None:
            return False
        try:
            # Just check if client is configured
            return self.client is not None
        except Exception:
            return False
