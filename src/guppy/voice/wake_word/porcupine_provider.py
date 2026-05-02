"""
Porcupine Wake-Word Provider
==============================

Wraps Picovoice Porcupine for production-grade wake-word detection.
Requires `pvporcupine` package and a Picovoice access key:

    pip install pvporcupine
    export PORCUPINE_ACCESS_KEY="your-key-from-console"

Optional environment variables:
    PORCUPINE_KEYWORD_PATH  — path to a custom .ppn model file; if set and the
                              file exists, it overrides the built-in keyword arg.
    PORCUPINE_SENSITIVITY   — float 0-1, default 0.5

If pvporcupine is not installed or PORCUPINE_ACCESS_KEY is absent,
health_check() returns False and all detect/listen calls degrade gracefully
(return no-detection rather than raising).
"""

from __future__ import annotations

import asyncio
import logging
import os
import struct
import time
from typing import Any, AsyncGenerator, Optional

from guppy.voice.core import WakeWordProvider

logger = logging.getLogger(__name__)

# Module-level env var reads (evaluated once at import time for efficiency;
# runtime changes to env are picked up via __init__ default parameters).
_DEFAULT_ACCESS_KEY = os.environ.get("PORCUPINE_ACCESS_KEY", "").strip()
_DEFAULT_KEYWORD_PATH = os.environ.get("PORCUPINE_KEYWORD_PATH", "").strip()
_DEFAULT_SENSITIVITY = float(os.environ.get("PORCUPINE_SENSITIVITY", "0.5"))


def _listen_porcupine_blocking(porcupine, timeout_seconds: float = 30.0) -> bool:
    """Block until the wake word is detected or *timeout_seconds* elapses.

    Reads audio from the default sounddevice input in Porcupine-sized frames.
    Returns True on detection, False on timeout or error.
    """
    try:
        import numpy as np  # type: ignore
        import sounddevice as sd  # type: ignore
    except ImportError:
        logger.debug("sounddevice/numpy not installed — Porcupine live listen unavailable")
        return False

    frame_length = porcupine.frame_length
    sample_rate = porcupine.sample_rate
    start = time.monotonic()

    try:
        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype=np.int16,
            blocksize=frame_length,
        ) as stream:
            while time.monotonic() - start < timeout_seconds:
                pcm, _ = stream.read(frame_length)
                result = porcupine.process(pcm[:, 0].tolist())
                if result >= 0:
                    return True
    except Exception as exc:
        logger.warning("Porcupine listen loop error: %s", exc)
    return False


class PorcupineWakeWordProvider(WakeWordProvider):
    """Porcupine-based wake-word detector (requires pvporcupine + access key)."""

    name = "porcupine"

    def __init__(
        self,
        keyword: str = "hey google",  # built-in keyword name OR path to .ppn file
        access_key: Optional[str] = None,
        sensitivity: Optional[float] = None,
        sample_rate: int = 16000,
    ):
        self._keyword = keyword
        self._access_key = (access_key or _DEFAULT_ACCESS_KEY).strip()
        self._sensitivity = sensitivity if sensitivity is not None else _DEFAULT_SENSITIVITY
        # PORCUPINE_KEYWORD_PATH overrides the keyword arg when it points to a real file
        self._keyword_path = _DEFAULT_KEYWORD_PATH
        self._sample_rate = sample_rate
        self._engine = None
        self._available: Optional[bool] = None

    async def health_check(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import pvporcupine  # type: ignore  # noqa: F401
            if not self._access_key:
                logger.warning(
                    "Porcupine: PORCUPINE_ACCESS_KEY not set. "
                    "Set it via the environment variable to enable wake-word detection."
                )
                self._available = False
                return False
            # Log keyword path status so operators know what's configured
            if self._keyword_path:
                if os.path.exists(self._keyword_path):
                    logger.info("Porcupine: using custom .ppn file at %r", self._keyword_path)
                else:
                    logger.warning(
                        "Porcupine: PORCUPINE_KEYWORD_PATH=%r does not exist; "
                        "will fall back to built-in keyword %r",
                        self._keyword_path,
                        self._keyword,
                    )
            self._available = True
            return True
        except ImportError:
            logger.debug("Porcupine: pvporcupine not installed")
            self._available = False
            return False

    def _ensure_engine(self):
        if self._engine is not None:
            return self._engine
        import pvporcupine  # type: ignore

        # Priority: explicit .ppn path > keyword arg (try built-in first, then path)
        if self._keyword_path and os.path.exists(self._keyword_path):
            self._engine = pvporcupine.create(
                access_key=self._access_key,
                keyword_paths=[self._keyword_path],
                sensitivities=[self._sensitivity],
            )
            logger.info("Porcupine: loaded custom .ppn from %r", self._keyword_path)
            return self._engine

        # Try as a built-in keyword name first; fall back to treating it as a path
        try:
            self._engine = pvporcupine.create(
                access_key=self._access_key,
                keywords=[self._keyword],
                sensitivities=[self._sensitivity],
            )
        except Exception:
            self._engine = pvporcupine.create(
                access_key=self._access_key,
                keyword_paths=[self._keyword],
                sensitivities=[self._sensitivity],
            )
        return self._engine

    async def listen_for_wake_word(self, timeout_seconds: float = 30.0) -> bool:
        """Block (in a thread) until the wake word fires or *timeout_seconds* elapses.

        Returns True on detection, False if unavailable or timed out.
        This is the high-level convenience method for one-shot wake detection;
        use stream_detect() for streaming / continuous monitoring.
        """
        if not await self.health_check():
            return False
        try:
            engine = self._ensure_engine()
        except Exception as exc:
            logger.error("Porcupine: failed to create engine: %s", exc)
            return False
        try:
            return await asyncio.to_thread(_listen_porcupine_blocking, engine, timeout_seconds)
        except Exception as exc:
            logger.error("Porcupine: listen_for_wake_word error: %s", exc)
            return False

    async def detect(self, audio_data: bytes, **kwargs: Any) -> tuple[bool, float]:
        """Scan *audio_data* (raw 16-bit PCM) for the wake word frame-by-frame."""
        if not await self.health_check():
            return (False, 0.0)
        try:
            engine = self._ensure_engine()
        except Exception as exc:
            logger.error("Porcupine: engine creation failed: %s", exc)
            return (False, 0.0)

        frame_length = engine.frame_length
        frame_count = len(audio_data) // (2 * frame_length)
        for i in range(frame_count):
            offset = i * 2 * frame_length
            frame = struct.unpack(
                f"<{frame_length}h", audio_data[offset : offset + 2 * frame_length]
            )
            keyword_index = engine.process(frame)
            if keyword_index >= 0:
                return (True, self._sensitivity)
        return (False, 0.0)

    async def stream_detect(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        **kwargs: Any,
    ) -> AsyncGenerator[tuple[bool, float], None]:
        """Yield (detected, confidence) for each audio chunk in *audio_stream*."""
        async for chunk in audio_stream:
            yield await self.detect(chunk)
