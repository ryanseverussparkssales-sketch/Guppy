"""
Kokoro TTS Provider
====================

Async wrapper around the Kokoro TTS pipeline. Supports three modes,
tried in order:

1. Kokoro HTTP API  — preferred when GUPPY_KOKORO_API_URL is set or default
                     local server is reachable (http://127.0.0.1:8880)
2. kokoro-onnx      — local ONNX inference; requires ``kokoro-onnx`` package
                     + model/voices files (auto-discovered from HF cache or set
                     via GUPPY_KOKORO_MODEL_PATH / GUPPY_KOKORO_VOICES_PATH)
3. kokoro KPipeline — legacy fallback; requires ``kokoro`` package

Provides clean async/await semantics over what is otherwise a blocking
synthesis call.
"""

from __future__ import annotations

import asyncio
import glob as _glob
import io
import logging
import os
import time
import urllib.request
from typing import Any, AsyncGenerator, Optional

from guppy.voice.core import TTSProvider, TTSResult

logger = logging.getLogger(__name__)

_DEFAULT_API_URL = "http://127.0.0.1:8880/v1/audio/speech"

KOKORO_VOICES = [
    {"id": "bm_lewis",   "name": "Lewis (British Male)",    "lang": "en-gb"},
    {"id": "bm_george",  "name": "George (British Male)",   "lang": "en-gb"},
    {"id": "bf_emma",    "name": "Emma (British Female)",   "lang": "en-gb"},
    {"id": "af_alloy",   "name": "Alloy (American Female)", "lang": "en-us"},
    {"id": "am_adam",    "name": "Adam (American Male)",    "lang": "en-us"},
    {"id": "af_bella",   "name": "Bella (American Female)", "lang": "en-us"},
    {"id": "af_heart",   "name": "Heart (American Female)", "lang": "en-us"},
]

# ── HuggingFace cache auto-discovery ─────────────────────────────────────────

_HF_CACHE_ROOT = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")

def _hf_find_file(repo_slug: str, filename: str) -> Optional[str]:
    """Find *filename* inside any snapshot of *repo_slug* in the HF cache."""
    repo_dir = os.path.join(_HF_CACHE_ROOT, repo_slug, "snapshots")
    if not os.path.isdir(repo_dir):
        return None
    # Return the first snapshot that has the file (newest mtime wins)
    candidates = _glob.glob(os.path.join(repo_dir, "*", filename))
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)


def _default_onnx_model_path() -> Optional[str]:
    p = os.environ.get("GUPPY_KOKORO_MODEL_PATH", "")
    if p and os.path.isfile(p):
        return p
    # mikkoph/kokoro-onnx (smaller, faster ONNX build)
    found = _hf_find_file("models--mikkoph--kokoro-onnx", "kokoro-v1.0.onnx")
    if found:
        return found
    # hexgrad/Kokoro-82M-ONNX (original)
    return _hf_find_file("models--hexgrad--Kokoro-82M-ONNX", "kokoro-v0_19.onnx")


def _default_onnx_voices_path() -> Optional[str]:
    p = os.environ.get("GUPPY_KOKORO_VOICES_PATH", "")
    if p and os.path.isfile(p):
        return p
    found = _hf_find_file("models--mikkoph--kokoro-onnx", "voices-v1.0.bin")
    if found:
        return found
    return _hf_find_file("models--hexgrad--Kokoro-82M-ONNX", "voices.bin")


# ── Provider ──────────────────────────────────────────────────────────────────

class KokoroTTSProvider(TTSProvider):
    """Kokoro TTS via HTTP API, local ONNX, or local KPipeline."""

    name = "kokoro_tts"

    def __init__(
        self,
        api_url: Optional[str] = None,
        local_lang_code: str = "a",  # 'a'=US English
        sample_rate: int = 24000,
    ):
        self._api_url = (api_url or os.environ.get("GUPPY_KOKORO_API_URL") or _DEFAULT_API_URL).rstrip("/")
        self._local_lang_code = local_lang_code
        self._sample_rate = sample_rate
        self._onnx_model: Any = None      # kokoro_onnx.Kokoro instance
        self._pipeline: Any = None        # kokoro.KPipeline instance (legacy)
        self._mode: Optional[str] = None  # 'api' | 'onnx' | 'local' | None

    # ── Mode detection ────────────────────────────────────────────────────────

    async def _detect_mode(self) -> Optional[str]:
        """Try API → ONNX → KPipeline, cache the winner."""
        if self._mode is not None:
            return self._mode

        if await asyncio.to_thread(self._probe_api):
            self._mode = "api"
            logger.info("Kokoro: using HTTP API at %s", self._api_url)
            return "api"

        if await asyncio.to_thread(self._load_onnx):
            self._mode = "onnx"
            logger.info("Kokoro: using local ONNX inference")
            return "onnx"

        if await asyncio.to_thread(self._load_local):
            self._mode = "local"
            logger.info("Kokoro: using local KPipeline")
            return "local"

        self._mode = None
        return None

    def _probe_api(self) -> bool:
        try:
            url = self._api_url.replace("/v1/audio/speech", "/v1/models")
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as r:
                return r.status == 200
        except Exception:
            return False

    def _load_onnx(self) -> bool:
        """Load kokoro-onnx Kokoro instance from model files."""
        model_path  = _default_onnx_model_path()
        voices_path = _default_onnx_voices_path()
        if not model_path or not voices_path:
            logger.debug("Kokoro ONNX: model or voices file not found; skipping")
            return False
        try:
            from kokoro_onnx import Kokoro  # type: ignore
            self._onnx_model = Kokoro(model_path, voices_path)
            logger.info(
                "Kokoro ONNX loaded — model=%s voices=%s",
                os.path.basename(model_path),
                os.path.basename(voices_path),
            )
            return True
        except Exception as e:
            logger.debug("Kokoro ONNX unavailable: %s", e)
            return False

    def _load_local(self) -> bool:
        """Load legacy kokoro KPipeline."""
        try:
            from kokoro import KPipeline  # type: ignore
            self._pipeline = KPipeline(lang_code=self._local_lang_code, device="cpu")
            return True
        except Exception as e:
            logger.debug("Kokoro local pipeline unavailable: %s", e)
            return False

    # ── Health ────────────────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        return await self._detect_mode() is not None

    # ── Synthesize ────────────────────────────────────────────────────────────

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs: Any,
    ) -> TTSResult:
        start = time.monotonic()
        mode = await self._detect_mode()
        _voice = voice or "af_bella"
        _speed = float(kwargs.get("speed", 1.0))

        if mode == "api":
            return await self._synth_api(text, _voice, _speed, start)
        if mode == "onnx":
            return await self._synth_onnx(text, _voice, _speed, start)
        if mode == "local":
            return await self._synth_local(text, _voice, _speed, start)

        return TTSResult(
            audio_data=b"",
            provider=self.name,
            duration_ms=(time.monotonic() - start) * 1000.0,
            sample_rate=self._sample_rate,
            channels=1,
            format="wav",
            playback_duration_s=0.0,
            error="kokoro_not_available",
        )

    # ── API mode ──────────────────────────────────────────────────────────────

    async def _synth_api(self, text: str, voice: str, speed: float, start: float) -> TTSResult:
        try:
            audio = await asyncio.to_thread(self._call_api, text, voice, speed)
            return TTSResult(
                audio_data=audio,
                provider=self.name,
                duration_ms=(time.monotonic() - start) * 1000.0,
                sample_rate=self._sample_rate,
                channels=1,
                format="wav",
                playback_duration_s=self._estimate_duration_s(audio),
                metadata={"mode": "api", "voice": voice},
            )
        except Exception as e:
            logger.error("Kokoro API synthesis failed: %s", e)
            return self._error_result(start, f"kokoro_api_error: {e}")

    def _call_api(self, text: str, voice: str, speed: float) -> bytes:
        import json
        payload = {
            "model": "kokoro",
            "input": text,
            "voice": voice,
            "speed": speed,
            "response_format": "wav",
        }
        req = urllib.request.Request(
            self._api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30.0) as r:
            return r.read()

    # ── ONNX mode ─────────────────────────────────────────────────────────────

    async def _synth_onnx(self, text: str, voice: str, speed: float, start: float) -> TTSResult:
        try:
            audio_bytes, sr = await asyncio.to_thread(
                self._call_onnx, text, voice, speed
            )
            return TTSResult(
                audio_data=audio_bytes,
                provider=self.name,
                duration_ms=(time.monotonic() - start) * 1000.0,
                sample_rate=sr,
                channels=1,
                format="pcm",
                playback_duration_s=len(audio_bytes) / (2 * sr),
                metadata={"mode": "onnx", "voice": voice},
            )
        except Exception as e:
            logger.error("Kokoro ONNX synthesis failed: %s", e)
            return self._error_result(start, f"kokoro_onnx_error: {e}")

    def _call_onnx(self, text: str, voice: str, speed: float) -> tuple[bytes, int]:
        """Blocking ONNX synthesis → (int16 PCM bytes, sample_rate)."""
        import numpy as np  # type: ignore
        if self._onnx_model is None:
            raise RuntimeError("ONNX model not loaded")
        audio_arr, sr = self._onnx_model.create(text, voice=voice, speed=speed)
        # float32 → int16
        pcm = (np.asarray(audio_arr, dtype=np.float32) * 32767).clip(-32768, 32767).astype(np.int16)
        return pcm.tobytes(), int(sr)

    # ── KPipeline (legacy local) mode ─────────────────────────────────────────

    async def _synth_local(self, text: str, voice: str, speed: float, start: float) -> TTSResult:
        try:
            audio = await asyncio.to_thread(self._call_local, text, voice, speed)
            return TTSResult(
                audio_data=audio,
                provider=self.name,
                duration_ms=(time.monotonic() - start) * 1000.0,
                sample_rate=self._sample_rate,
                channels=1,
                format="pcm",
                playback_duration_s=self._estimate_duration_s(audio, format_="pcm"),
                metadata={"mode": "local", "voice": voice},
            )
        except Exception as e:
            logger.error("Kokoro local synthesis failed: %s", e)
            return self._error_result(start, f"kokoro_local_error: {e}", format_="pcm")

    def _call_local(self, text: str, voice: str, speed: float) -> bytes:
        try:
            import numpy as np  # type: ignore
        except Exception:
            raise RuntimeError("numpy required for Kokoro local mode")
        if self._pipeline is None:
            raise RuntimeError("Kokoro pipeline not loaded")
        chunks = []
        for _, _, audio in self._pipeline(text, voice=voice, speed=speed):
            arr = np.asarray(audio, dtype=np.float32)
            chunks.append((arr * 32767).clip(-32768, 32767).astype(np.int16).tobytes())
        return b"".join(chunks)

    # ── Streaming ─────────────────────────────────────────────────────────────

    async def stream_synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[bytes, None]:
        """True chunked streaming.

        - ONNX mode: uses ``create_stream`` async generator (native chunks).
        - Local KPipeline mode: yields one PCM chunk per pipeline segment.
        - API mode: synthesize-then-yield (API doesn't support streaming).
        """
        mode = await self._detect_mode()
        _voice = voice or "af_bella"
        _speed = float(kwargs.get("speed", 1.0))

        if mode == "onnx" and self._onnx_model is not None:
            import numpy as np  # type: ignore
            try:
                async for audio_arr, _sr in self._onnx_model.create_stream(
                    text, voice=_voice, speed=_speed
                ):
                    pcm = (np.asarray(audio_arr, dtype=np.float32) * 32767).clip(-32768, 32767).astype(np.int16)
                    yield pcm.tobytes()
            except Exception as e:
                logger.error("Kokoro ONNX stream_synthesize failed: %s", e)
            return

        if mode == "local" and self._pipeline is not None:
            try:
                import numpy as np  # type: ignore
                loop = asyncio.get_event_loop()
                it = iter(self._pipeline(text, voice=_voice, speed=_speed))
                while True:
                    try:
                        _, _, audio = await loop.run_in_executor(None, next, it)
                        arr = np.asarray(audio, dtype=np.float32)
                        yield (arr * 32767).clip(-32768, 32767).astype(np.int16).tobytes()
                    except StopIteration:
                        break
            except Exception as e:
                logger.error("Kokoro local stream_synthesize failed: %s", e)
            return

        # API mode or fallback: synthesize whole then yield
        result = await self.synthesize(text, voice, **kwargs)
        if result.audio_data and not result.error:
            yield result.audio_data

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _estimate_duration_s(self, audio: bytes, format_: str = "wav") -> float:
        if not audio:
            return 0.0
        if format_ == "pcm":
            return len(audio) / (2 * self._sample_rate)
        if len(audio) <= 44:
            return 0.0
        return (len(audio) - 44) / (2 * self._sample_rate)

    def _error_result(
        self,
        start: float,
        error: str,
        format_: str = "wav",
    ) -> TTSResult:
        return TTSResult(
            audio_data=b"",
            provider=self.name,
            duration_ms=(time.monotonic() - start) * 1000.0,
            sample_rate=self._sample_rate,
            channels=1,
            format=format_,
            playback_duration_s=0.0,
            error=error,
        )
