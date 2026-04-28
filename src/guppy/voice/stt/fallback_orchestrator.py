"""
STT Fallback Chain Orchestrator
================================

Intelligent retry logic across multiple STT providers.
Implements timeout-based, parallel execution with first-success-wins strategy.

Strategy:
  1. Try Google STT (timeout: 10 seconds)
  2. If Google fails, try Whisper in parallel with SAPI (timeout: 10 seconds each)
  3. Return first successful result
  4. If all fail, raise error with fallback chain recorded

Telemetry:
  - Records which providers were tried
  - Tracks latencies and errors
  - Logs fallback triggers for observability
"""

import asyncio
import logging
import time
from typing import Optional, Any, AsyncGenerator

from guppy.voice.core import (
    STTProvider,
    STTResult,
    AudioEvent,
    AudioEventType,
)
from guppy.voice.stt.google_stt import GoogleSTTProvider
from guppy.voice.stt.whisper_stt import WhisperSTTProvider
from guppy.voice.stt.sapi_stt import SAPISTTProvider

logger = logging.getLogger(__name__)


class FallbackChainOrchestrator:
    """
    Orchestrates fallback chain across STT providers.
    
    Execution strategy:
      1. Google STT (primary, cloud-based, highest accuracy)
      2. Whisper STT (secondary, if Google fails)
      3. SAPI STT (tertiary, always available on Windows)
    
    Timeouts:
      - Google: 10 seconds
      - Whisper: 10 seconds
      - SAPI: 10 seconds (no timeout for SAPI as it's local)
    """

    def __init__(self) -> None:
        """Initialize all STT providers."""
        self.google_provider = GoogleSTTProvider()
        self.whisper_provider = WhisperSTTProvider()
        self.sapi_provider = SAPISTTProvider()
        
        # Execution order
        self.primary_provider = self.google_provider
        self.secondary_provider = self.whisper_provider
        self.tertiary_provider = self.sapi_provider
        
        # Timeouts (seconds)
        self.PRIMARY_TIMEOUT = 10.0
        self.SECONDARY_TIMEOUT = 10.0
        self.TERTIARY_TIMEOUT = 10.0

    async def transcribe(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
        **kwargs: Any,
    ) -> STTResult:
        """
        Transcribe audio with intelligent fallback.
        
        Args:
            audio_data: Raw audio bytes
            language: Language hint (e.g., "en-US")
            **kwargs: Provider-specific options
        
        Returns:
            STTResult from first successful provider
        
        Raises:
            RuntimeError: If all providers fail
        """
        start_time = time.time()
        fallback_chain = []
        last_error = None

        # Step 1: Try Google STT (primary)
        logger.info(f"[STT] Attempting Google STT (timeout: {self.PRIMARY_TIMEOUT}s)")
        fallback_chain.append("google")
        
        try:
            result = await asyncio.wait_for(
                self.primary_provider.transcribe(audio_data, language, **kwargs),
                timeout=self.PRIMARY_TIMEOUT,
            )
            
            if result.error is None and result.text:
                duration = time.time() - start_time
                logger.info(
                    f"[STT] Google STT success: '{result.text}' ({duration:.2f}s)"
                )
                result.metadata["fallback_chain"] = fallback_chain
                return result
            else:
                last_error = result.error or "Empty response"
                logger.warning(f"[STT] Google STT failed: {last_error}")
        
        except asyncio.TimeoutError:
            last_error = f"Google STT timeout ({self.PRIMARY_TIMEOUT}s)"
            logger.warning(f"[STT] {last_error}")
        except Exception as e:
            last_error = f"Google STT error: {str(e)}"
            logger.warning(f"[STT] {last_error}")

        # Step 2: Try Whisper and SAPI in parallel (secondary tier)
        logger.info(
            f"[STT] Primary failed, trying Whisper + SAPI in parallel "
            f"(timeout: {self.SECONDARY_TIMEOUT}s each)"
        )
        fallback_chain.append("whisper")
        fallback_chain.append("sapi")

        try:
            # Race Whisper and SAPI, return first successful result
            whisper_task = asyncio.create_task(
                self.secondary_provider.transcribe(audio_data, language, **kwargs)
            )
            sapi_task = asyncio.create_task(
                self.sapi_provider.transcribe(audio_data, language, **kwargs)
            )

            done, pending = await asyncio.wait(
                [whisper_task, sapi_task],
                timeout=max(self.SECONDARY_TIMEOUT, self.TERTIARY_TIMEOUT),
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Check which one completed first
            for task in done:
                result = await task
                
                # Clean up remaining task
                for pending_task in pending:
                    pending_task.cancel()
                
                if result.error is None and result.text:
                    provider_name = task.get_name() if hasattr(task, 'get_name') else "unknown"
                    duration = time.time() - start_time
                    logger.info(
                        f"[STT] {provider_name} success: '{result.text}' ({duration:.2f}s)"
                    )
                    result.metadata["fallback_chain"] = fallback_chain
                    return result

            # If we reach here, both completed but neither had valid result
            # Try to collect results from both
            whisper_result = whisper_task.result() if not whisper_task.cancelled() else None
            sapi_result = sapi_task.result() if not sapi_task.cancelled() else None

            # Return Whisper result if available (higher accuracy than SAPI)
            if whisper_result and whisper_result.error is None and whisper_result.text:
                duration = time.time() - start_time
                logger.info(
                    f"[STT] Whisper success: '{whisper_result.text}' ({duration:.2f}s)"
                )
                whisper_result.metadata["fallback_chain"] = fallback_chain
                return whisper_result

            # Fall back to SAPI if available
            if sapi_result and sapi_result.error is None and sapi_result.text:
                duration = time.time() - start_time
                logger.info(
                    f"[STT] SAPI success: '{sapi_result.text}' ({duration:.2f}s)"
                )
                sapi_result.metadata["fallback_chain"] = fallback_chain
                return sapi_result

            # All failed
            last_error = "All providers returned errors or empty results"
            logger.error(f"[STT] {last_error}")

        except Exception as e:
            last_error = f"Fallback orchestration error: {str(e)}"
            logger.error(f"[STT] {last_error}")

        # All providers failed
        error_msg = f"STT failed after trying: {' → '.join(fallback_chain)}. Last error: {last_error}"
        logger.error(f"[STT] {error_msg}")

        raise RuntimeError(error_msg)

    async def stream_transcribe(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        language: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[STTResult, None]:
        """
        Stream-based transcription with fallback.
        
        Buffering strategy:
          - Buffer 30 seconds of audio
          - Try Google → Whisper → SAPI in sequence
          - Yield result, reset buffer, repeat
        
        Args:
            audio_stream: Async generator yielding audio chunks
            language: Language hint
            **kwargs: Provider-specific options
        
        Yields:
            STTResult for each processed batch
        """
        BUFFER_SIZE = 30 * 16000 * 2  # 30 seconds at 16kHz, 16-bit
        buffer = bytearray()
        batch_count = 0
        fallback_chain_log = []

        try:
            async for chunk in audio_stream:
                buffer.extend(chunk)

                # Process buffer when it reaches size limit
                if len(buffer) >= BUFFER_SIZE:
                    batch_count += 1
                    logger.info(f"[STT Stream] Processing batch {batch_count} ({len(buffer)} bytes)")
                    
                    try:
                        result = await self.transcribe(bytes(buffer), language, **kwargs)
                        result.is_final = False
                        fallback_chain_log.append(result.metadata.get("fallback_chain", []))
                        yield result
                    except Exception as e:
                        logger.error(f"[STT Stream] Batch {batch_count} failed: {str(e)}")
                        # Yield error result instead of raising
                        yield STTResult(
                            text="",
                            confidence=0.0,
                            provider="fallback_chain",
                            duration_ms=0.0,
                            language=language,
                            is_final=False,
                            error=f"Batch {batch_count} failed: {str(e)}",
                            metadata={"batch_count": batch_count},
                        )
                    
                    buffer.clear()

            # Process remaining buffer at end of stream
            if buffer:
                batch_count += 1
                logger.info(
                    f"[STT Stream] Processing final batch {batch_count} ({len(buffer)} bytes)"
                )
                
                try:
                    result = await self.transcribe(bytes(buffer), language, **kwargs)
                    result.is_final = True
                    fallback_chain_log.append(result.metadata.get("fallback_chain", []))
                    yield result
                except Exception as e:
                    logger.error(f"[STT Stream] Final batch {batch_count} failed: {str(e)}")
                    yield STTResult(
                        text="",
                        confidence=0.0,
                        provider="fallback_chain",
                        duration_ms=0.0,
                        language=language,
                        is_final=True,
                        error=f"Final batch failed: {str(e)}",
                        metadata={
                            "batch_count": batch_count,
                            "fallback_chains": fallback_chain_log,
                        },
                    )

        except Exception as e:
            error_msg = f"STT stream transcription error: {str(e)}"
            logger.error(f"[STT Stream] {error_msg}")
            yield STTResult(
                text="",
                confidence=0.0,
                provider="fallback_chain",
                duration_ms=0.0,
                language=language,
                is_final=True,
                error=error_msg,
                metadata={"fallback_chains": fallback_chain_log},
            )

    async def health_check(self) -> bool:
        """
        Check if at least one STT provider is available.
        
        Returns:
            True if any provider is available
        """
        google_ok = await self.google_provider.health_check()
        whisper_ok = await self.whisper_provider.health_check()
        sapi_ok = await self.sapi_provider.health_check()
        
        status = f"Google: {google_ok}, Whisper: {whisper_ok}, SAPI: {sapi_ok}"
        logger.info(f"[STT Health] {status}")
        
        # At least one provider should be available
        return google_ok or whisper_ok or sapi_ok
