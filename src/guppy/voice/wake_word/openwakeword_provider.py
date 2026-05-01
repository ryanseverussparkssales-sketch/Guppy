"""
OpenWakeWord Provider
======================

Wraps the `openwakeword` library for zero-API-key wake-word detection.
Requires the optional ``openwakeword`` package:

    pip install openwakeword

No API key or cloud service needed — all inference runs locally.
Supports any .onnx model file or the built-in "hey_jarvis", "alexa",
"hey_mycroft", "timer", "weather", etc. models bundled with the library.

Priority in the Guppy wake-word stack:
    1. Porcupine  (best accuracy, needs PORCUPINE_ACCESS_KEY)
    2. OpenWakeWord (good accuracy, zero-key — this file)
    3. EnergyThreshold (voice-activity stub, always available)
"""

from __future__ import annotations

import logging
import os
from typing import Any, AsyncGenerator, Optional

from guppy.voice.core import WakeWordProvider

logger = logging.getLogger(__name__)

# Default model name shipped with openwakeword.
# Can be overridden via env var OPENWAKEWORD_MODEL.
_DEFAULT_OWW_MODEL = "hey_jarvis_v0.1"


class OpenWakeWordProvider(WakeWordProvider):
    """OpenWakeWord-based wake-word detector (zero API key required).

    Parameters
    ----------
    keyword:
        Model name (e.g. ``"hey_jarvis_v0.1"``) or absolute path to a
        custom ``.onnx`` model file.
    threshold:
        Detection score threshold in ``[0, 1]``.  Higher → fewer false
        positives at the cost of sensitivity.  Default ``0.5``.
    sample_rate:
        Audio sample rate expected by the model (default 16 kHz).
    """

    name = "openwakeword"

    def __init__(
        self,
        keyword: Optional[str] = None,
        threshold: float = 0.5,
        sample_rate: int = 16000,
    ):
        self._keyword = keyword or os.environ.get("OPENWAKEWORD_MODEL", _DEFAULT_OWW_MODEL)
        self._threshold = threshold
        self._sample_rate = sample_rate
        self._model: Any = None
        self._available: Optional[bool] = None

    # ── availability ──────────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import openwakeword  # noqa: F401  type: ignore
            self._available = True
            return True
        except ImportError:
            logger.debug("OpenWakeWord: openwakeword package not installed")
            self._available = False
            return False

    # ── lazy model load ───────────────────────────────────────────────────────

    def _ensure_model(self) -> Any:
        if self._model is not None:
            return self._model
        from openwakeword.model import Model  # type: ignore
        if os.path.isfile(self._keyword):
            self._model = Model(wakeword_models=[self._keyword], inference_framework="onnx")
        else:
            self._model = Model(wakeword_models=[self._keyword], inference_framework="onnx")
        logger.info("OpenWakeWord: loaded model %r", self._keyword)
        return self._model

    # ── WakeWordProvider interface ────────────────────────────────────────────

    async def detect(self, audio_data: bytes, **kwargs: Any) -> tuple[bool, float]:
        """Score a single audio chunk and return (detected, confidence)."""
        if not await self.health_check():
            return (False, 0.0)
        try:
            import numpy as np  # type: ignore
            model = self._ensure_model()
            # Convert 16-bit PCM bytes → int16 numpy array
            audio_int16 = np.frombuffer(audio_data, dtype=np.int16)
            prediction = model.predict(audio_int16)
            # prediction is {model_name: score}; take max across all loaded models
            score = max(prediction.values()) if prediction else 0.0
            return (float(score) >= self._threshold, float(score))
        except Exception as exc:
            logger.warning("OpenWakeWord detect error: %s", exc)
            return (False, 0.0)

    async def stream_detect(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        **kwargs: Any,
    ) -> AsyncGenerator[tuple[bool, float], None]:
        async for chunk in audio_stream:
            yield await self.detect(chunk)
