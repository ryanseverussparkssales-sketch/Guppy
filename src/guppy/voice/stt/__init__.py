"""
Speech-to-Text Providers
========================

Implementations of STTProvider for multiple speech recognition backends.

Providers:
  - GoogleSTTProvider: Google Cloud Speech-to-Text (primary, cloud-based)
  - WhisperSTTProvider: OpenAI Whisper (secondary, cloud-based)
  - SAPISTTProvider: Windows SAPI5 (tertiary, local, always available)

Orchestrator:
  - FallbackChainOrchestrator: Intelligent retry logic across all providers
"""

from guppy.voice.stt.google_stt import GoogleSTTProvider
from guppy.voice.stt.whisper_stt import WhisperSTTProvider
from guppy.voice.stt.sapi_stt import SAPISTTProvider
from guppy.voice.stt.fallback_orchestrator import FallbackChainOrchestrator

__all__ = [
    "GoogleSTTProvider",
    "WhisperSTTProvider",
    "SAPISTTProvider",
    "FallbackChainOrchestrator",
]
