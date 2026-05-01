"""Wake-word detection module."""

from guppy.voice.wake_word.detector import (
    WakeWordDetector,
    WakeWordConfig,
    WakeWordEvent,
)
from guppy.voice.wake_word.energy_provider import EnergyThresholdWakeWordProvider
from guppy.voice.wake_word.porcupine_provider import PorcupineWakeWordProvider
from guppy.voice.wake_word.openwakeword_provider import OpenWakeWordProvider


def make_best_provider(keyword: str = "hey_jarvis_v0.1") -> "PorcupineWakeWordProvider | OpenWakeWordProvider | EnergyThresholdWakeWordProvider":
    """Return the highest-priority available wake-word provider.

    Priority:
      1. Porcupine  — best accuracy; requires ``pvporcupine`` + ``PORCUPINE_ACCESS_KEY``
      2. OpenWakeWord — good accuracy, zero API key; requires ``openwakeword`` package
      3. EnergyThreshold — always available; voice-activity gate only
    """
    import os
    # 1) Porcupine — needs package AND access key
    if os.environ.get("PORCUPINE_ACCESS_KEY", "").strip():
        try:
            import pvporcupine  # noqa: F401  type: ignore
            return PorcupineWakeWordProvider(keyword=keyword)
        except ImportError:
            pass
    # 2) OpenWakeWord — needs package only
    try:
        import openwakeword  # noqa: F401  type: ignore
        return OpenWakeWordProvider(keyword=keyword)
    except ImportError:
        pass
    # 3) Fallback
    return EnergyThresholdWakeWordProvider()


__all__ = [
    "WakeWordDetector",
    "WakeWordConfig",
    "WakeWordEvent",
    "EnergyThresholdWakeWordProvider",
    "OpenWakeWordProvider",
    "PorcupineWakeWordProvider",
    "make_best_provider",
]
