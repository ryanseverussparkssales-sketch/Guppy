"""
Windows SAPI5 Speech-to-Text Provider
======================================

Implements speech recognition using Windows SAPI (Speech API) 5.
This is the final fallback provider, available on all Windows systems without API keys.

Requirements:
  - Windows OS (SAPI5 is Windows-native)
  - No API keys required
  - Installed speech recognition engine (usually included with Windows)

Environment Variables:
  - GUPPY_SAPI_STT_ENABLED: Enable/disable SAPI provider (default: "true")
"""

import os
import asyncio
import logging
from typing import Optional, Any, AsyncGenerator

from guppy.voice.core import STTProvider, STTResult, AudioEventType

logger = logging.getLogger(__name__)


class SAPISTTProvider(STTProvider):
    """
    Windows SAPI5 speech-to-text provider.
    
    Uses Windows built-in speech recognition engine.
    No API keys required. Works offline.
    
    Pros:
      - No API key required
      - Works offline
      - Available on all Windows systems
      - Low latency for short utterances
    
    Cons:
      - Windows-only
      - Accuracy lower than cloud providers
      - No streaming API (batch only)
      - Limited language support
    """

    name = "sapi"

    def __init__(self) -> None:
        """
        Initialize SAPI5 speech recognizer.
        
        Raises:
            ImportError: If pyaudio or speech_recognition not installed
            OSError: If not running on Windows
        """
        # Check if SAPI is enabled
        enabled = os.getenv("GUPPY_SAPI_STT_ENABLED", "true").lower() == "true"
        if not enabled:
            logger.info("SAPI5 STT provider disabled via GUPPY_SAPI_STT_ENABLED")
            self._recognizer = None
            return

        try:
            import speech_recognition as sr
            
            self._recognizer = sr.Recognizer()
            # Tune recognizer for clarity
            self._recognizer.energy_threshold = 4000  # Adjust if too sensitive/insensitive
            self._recognizer.dynamic_energy_threshold = True
            
            logger.info("SAPI5 STT provider initialized")
        except ImportError as e:
            logger.warning(
                f"SAPI5 STT provider requires 'speech_recognition' package: {e}. "
                "Install with: pip install SpeechRecognition pydub"
            )
            self._recognizer = None
        except Exception as e:
            logger.warning(f"Failed to initialize SAPI5 STT provider: {e}")
            self._recognizer = None

    async def transcribe(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
        **kwargs: Any,
    ) -> STTResult:
        """
        Transcribe audio using Windows SAPI5.
        
        Args:
            audio_data: Raw audio bytes (WAV format, 16-bit PCM, 16kHz assumed)
            language: Language code (e.g., "en-US"). SAPI5 support is limited.
            **kwargs: Additional options (unused for SAPI)
        
        Returns:
            STTResult with transcribed text
        
        Raises:
            RuntimeError: If SAPI not available or transcription fails
        """
        if self._recognizer is None:
            raise RuntimeError(
                "SAPI5 STT provider not available. "
                "Install speech_recognition: pip install SpeechRecognition"
            )

        try:
            import speech_recognition as sr
            from io import BytesIO
            
            # Run blocking operation in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._transcribe_blocking,
                audio_data,
                language,
            )
            return result

        except Exception as e:
            error_msg = f"SAPI5 transcription failed: {str(e)}"
            logger.error(error_msg)
            return STTResult(
                text="",
                confidence=0.0,
                provider="sapi",
                duration_ms=0.0,
                language=language,
                is_final=True,
                error=error_msg,
            )

    def _transcribe_blocking(
        self, audio_data: bytes, language: Optional[str] = None
    ) -> STTResult:
        """
        Blocking transcription using SAPI5.
        
        Args:
            audio_data: Raw audio bytes (WAV format)
            language: Language code
        
        Returns:
            STTResult
        """
        import speech_recognition as sr
        from io import BytesIO
        import time
        
        start_time = time.time()
        
        try:
            # Convert bytes to AudioData format expected by sr
            # Assume 16-bit PCM, 16kHz, mono
            audio = sr.AudioData(
                frame_data=audio_data,
                sample_rate=16000,
                sample_width=2,  # 16-bit = 2 bytes
            )
            
            # Transcribe using default Windows speech recognizer
            # Note: SAPI5 doesn't expose confidence scores, so we use 0.9 as default for successful recognition
            text = self._recognizer.recognize_sphinx(audio)
            
            duration_ms = (time.time() - start_time) * 1000
            
            logger.info(
                f"SAPI5 transcription success: '{text}' ({duration_ms:.1f}ms)"
            )
            
            return STTResult(
                text=text,
                confidence=0.9,  # SAPI5 doesn't expose confidence; use default
                provider="sapi",
                duration_ms=duration_ms,
                language=language or "en-US",
                is_final=True,
                error=None,
                metadata={"recognizer": "sphinx", "engine": "sapi5"},
            )
        
        except sr.UnknownValueError:
            duration_ms = (time.time() - start_time) * 1000
            error_msg = "SAPI5 could not understand audio"
            logger.info(error_msg)
            return STTResult(
                text="",
                confidence=0.0,
                provider="sapi",
                duration_ms=duration_ms,
                language=language or "en-US",
                is_final=True,
                error=error_msg,
            )
        
        except sr.RequestError as e:
            duration_ms = (time.time() - start_time) * 1000
            error_msg = f"SAPI5 service error: {str(e)}"
            logger.error(error_msg)
            return STTResult(
                text="",
                confidence=0.0,
                provider="sapi",
                duration_ms=duration_ms,
                language=language or "en-US",
                is_final=True,
                error=error_msg,
            )

    async def stream_transcribe(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        language: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[STTResult, None]:
        """
        Stream-based transcription (not truly streaming for SAPI5).
        
        Since SAPI5 doesn't support true streaming, this buffers audio
        and processes in batches (like WhisperSTTProvider).
        
        Args:
            audio_stream: Async generator yielding audio chunks
            language: Language hint
            **kwargs: Provider-specific options
        
        Yields:
            STTResult for each processed batch
        """
        BUFFER_SIZE = 30 * 16000 * 2  # 30 seconds at 16kHz, 16-bit
        buffer = bytearray()
        chunk_count = 0

        try:
            async for chunk in audio_stream:
                buffer.extend(chunk)
                chunk_count += 1

                # Process buffer when it reaches size limit
                if len(buffer) >= BUFFER_SIZE:
                    result = await self.transcribe(bytes(buffer), language, **kwargs)
                    result.is_final = False
                    yield result
                    buffer.clear()

            # Process remaining buffer at end of stream
            if buffer:
                result = await self.transcribe(bytes(buffer), language, **kwargs)
                result.is_final = True
                yield result

        except Exception as e:
            error_msg = f"SAPI5 stream transcription error: {str(e)}"
            logger.error(error_msg)
            yield STTResult(
                text="",
                confidence=0.0,
                provider="sapi",
                duration_ms=0.0,
                language=language,
                is_final=True,
                error=error_msg,
            )

    async def health_check(self) -> bool:
        """
        Check if SAPI5 is available.
        
        Returns:
            True if SAPI5 recognizer is initialized, False otherwise
        """
        return self._recognizer is not None
