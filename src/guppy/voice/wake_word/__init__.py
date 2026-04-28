"""Wake-word detection module."""

from guppy.voice.wake_word.detector import (
    WakeWordDetector,
    WakeWordConfig,
    WakeWordEvent,
)
from guppy.voice.wake_word.energy_provider import EnergyThresholdWakeWordProvider
from guppy.voice.wake_word.porcupine_provider import PorcupineWakeWordProvider

__all__ = [
    "WakeWordDetector",
    "WakeWordConfig",
    "WakeWordEvent",
    "EnergyThresholdWakeWordProvider",
    "PorcupineWakeWordProvider",
]
