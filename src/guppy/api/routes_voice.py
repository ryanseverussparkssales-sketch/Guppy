"""Voice API — provider status, settings persistence, TTS synthesis for browser playback.

GET  /api/voices                — backend status + available providers/voices
PUT  /api/voices/settings       — persist TTS/STT preferences to settings DB
POST /api/voices/test           — trigger server-side TTS (plays through server speakers)
POST /api/voices/speak          — synthesize text → audio bytes for browser playback
POST /api/voices/stop           — interrupt active server-side TTS
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import struct
import time
import urllib.request
from typing import Any, Dict, Optional

# ── Kokoro availability cache ─────────────────────────────────────────────────
_kokoro_available: bool | None = None
_kokoro_checked_at: float = 0.0
_KOKORO_CACHE_TTL = 60.0  # re-probe at most once per minute

# ── GuppyVoice process-level cache ───────────────────────────────────────────
_voice_instance: Any = None  # cached after first construction

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from src.guppy.api.server_context import ServerContext

# ── Kokoro voice display names ────────────────────────────────────────────────
_KOKORO_VOICES = [
    {"id": "bm_lewis",   "name": "Lewis (British Male)",   "lang": "en-gb"},
    {"id": "bm_george",  "name": "George (British Male)",  "lang": "en-gb"},
    {"id": "bf_emma",    "name": "Emma (British Female)",  "lang": "en-gb"},
    {"id": "af_alloy",   "name": "Alloy (American Female)","lang": "en-us"},
    {"id": "am_adam",    "name": "Adam (American Male)",   "lang": "en-us"},
    {"id": "af_bella",   "name": "Bella (American Female)","lang": "en-us"},
]

_ELEVENLABS_VOICES = [
    {"id": "21m00Tcm4TlvDq8ikWAM", "name": "Rachel",  "lang": "en-us"},
    {"id": "AZnzlk1XvdvUeBnXmlld", "name": "Domi",    "lang": "en-us"},
    {"id": "EXAVITQu4vr4xnSDxMaL", "name": "Bella",   "lang": "en-us"},
    {"id": "ErXwobaYiN019PkySvjV", "name": "Antoni",  "lang": "en-us"},
    {"id": "MF3mGyEYCl7XYWbV9V6O", "name": "Elli",    "lang": "en-us"},
]

_WHISPER_MODELS = [
    {"id": "large-v3",  "name": "Whisper Large v3 (best accuracy)"},
    {"id": "medium",    "name": "Whisper Medium (balanced)"},
    {"id": "small",     "name": "Whisper Small (faster)"},
    {"id": "tiny",      "name": "Whisper Tiny (fastest)"},
]


def _pcm_to_wav(pcm: bytes, sample_rate: int = 22050, channels: int = 1, bits: int = 16) -> bytes:
    """Wrap raw PCM bytes in a minimal WAV container."""
    data_size = len(pcm)
    buf = io.BytesIO()
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + data_size))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<IHHIIHH", 16, 1, channels, sample_rate,
                          sample_rate * channels * bits // 8, channels * bits // 8, bits))
    buf.write(b"data")
    buf.write(struct.pack("<I", data_size))
    buf.write(pcm)
    return buf.getvalue()


def _probe_kokoro() -> bool:
    """Return True if the local Kokoro API server is reachable (cached 60 s)."""
    global _kokoro_available, _kokoro_checked_at
    now = time.monotonic()
    if _kokoro_available is not None and now - _kokoro_checked_at < _KOKORO_CACHE_TTL:
        return _kokoro_available
    base = os.environ.get("GUPPY_KOKORO_API_URL", "http://127.0.0.1:8881").rstrip("/")
    try:
        req = urllib.request.Request(f"{base}/v1/models", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            _kokoro_available = resp.status < 500
    except Exception:
        _kokoro_available = False
    _kokoro_checked_at = now
    return bool(_kokoro_available)


def _try_kokoro_api(text: str, voice: str, speed: float) -> bytes | None:
    """Return WAV bytes from the local Kokoro API server, or None on failure."""
    base = os.environ.get("GUPPY_KOKORO_API_URL", "http://127.0.0.1:8881").rstrip("/")
    payload = json.dumps({
        "model": "kokoro",
        "input": text,
        "voice": voice or "bm_lewis",
        "speed": float(speed),
        "response_format": "wav",
    }).encode()
    try:
        req = urllib.request.Request(
            f"{base}/v1/audio/speech",
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "audio/wav"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        return data if data else None
    except Exception:
        return None


def _try_elevenlabs(text: str, voice_id: str) -> bytes | None:
    """Return MP3 bytes from ElevenLabs, or None on failure."""
    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not api_key or not voice_id:
        return None
    model_id = os.environ.get("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5")
    payload = json.dumps({
        "text": text,
        "model_id": model_id,
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.85, "style": 0.2},
    }).encode()
    try:
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream",
            data=payload,
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            method="POST",
        )
        req.add_header("query-output_format", "mp3_44100_128")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        return data if data else None
    except Exception:
        return None


async def _synthesize_for_browser(text: str, voice: str, speed: float) -> tuple[bytes, str]:
    """Try TTS backends in order; return (audio_bytes, mime_type) or raise."""
    # Kokoro API (local, no key needed) → WAV
    wav = await asyncio.to_thread(_try_kokoro_api, text, voice, speed)
    if wav:
        return wav, "audio/wav"

    # ElevenLabs (cloud) → MP3
    eleven_voice = os.environ.get("ELEVENLABS_DEFAULT_VOICE_ID", voice).strip()
    mp3 = await asyncio.to_thread(_try_elevenlabs, text, eleven_voice)
    if mp3:
        return mp3, "audio/mpeg"

    raise RuntimeError("No browser-streamable TTS backend available (Kokoro API or ElevenLabs required)")


async def _get_voice_handler(ctx: ServerContext, owner: Any) -> Any:
    """Return a cached GuppyVoice instance, constructing it on first call."""
    global _voice_instance
    if _voice_instance is None:
        _voice_instance = await ctx.run_blocking(
            owner.voice.GuppyVoice,
            timeout_seconds=getattr(owner, "VOICE_TIMEOUT_SECONDS", 30),
        )
    return _voice_instance


def build_voice_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/voices")
    owner = ctx.owner  # server_runtime module

    @router.get("")
    async def get_voices(_user_id: str = Depends(ctx.require_rate_limit)) -> Dict[str, Any]:
        """Return available TTS/STT providers, voices, and current backend status."""
        tts_provider = os.environ.get("GUPPY_TTS_PROVIDER", "auto").strip().lower()
        eleven_key = bool(os.environ.get("ELEVENLABS_API_KEY", "").strip())
        whisper_model = os.environ.get("GUPPY_WHISPER_MODEL", "large-v3").strip()

        kokoro_available = await asyncio.to_thread(_probe_kokoro) if tts_provider != "sapi" else False

        return {
            "tts": {
                "active_provider": tts_provider,
                "providers": [
                    {"id": "auto",       "name": "Auto (recommended)", "available": True},
                    {"id": "kokoro",     "name": "Kokoro (local)",     "available": kokoro_available},
                    {"id": "elevenlabs", "name": "ElevenLabs",         "available": eleven_key},
                    {"id": "sapi",       "name": "Windows SAPI",       "available": True},
                ],
                "voices": {
                    "kokoro":     _KOKORO_VOICES,
                    "elevenlabs": _ELEVENLABS_VOICES,
                },
                "active_voice": os.environ.get("GUPPY_TTS_VOICE", "bm_lewis"),
                "speed":        os.environ.get("GUPPY_TTS_RATE",  "+8%"),
            },
            "stt": {
                "active_model": whisper_model,
                "models": _WHISPER_MODELS,
                "deepgram_available": bool(os.environ.get("DEEPGRAM_API_KEY", "").strip()),
            },
            "voice_available": getattr(owner, "GUPPY_VOICE_AVAILABLE", False),
        }

    @router.put("/settings")
    async def update_voice_settings(
        payload: Dict[str, Any],
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        """Persist TTS provider, voice, speed, and STT model preferences."""
        from src.guppy.api.routes_settings import _settings_db

        if "tts_provider" in payload:
            await asyncio.to_thread(_settings_db.set_setting, "tts_provider", str(payload["tts_provider"]))
            os.environ["GUPPY_TTS_PROVIDER"] = str(payload["tts_provider"])
        if "tts_voice" in payload:
            await asyncio.to_thread(_settings_db.set_setting, "tts_voice", str(payload["tts_voice"]))
            os.environ["GUPPY_TTS_VOICE"] = str(payload["tts_voice"])
        if "tts_speed" in payload:
            await asyncio.to_thread(_settings_db.set_setting, "tts_speed", str(payload["tts_speed"]))
            os.environ["GUPPY_TTS_RATE"] = str(payload["tts_speed"])
        if "stt_model" in payload:
            await asyncio.to_thread(_settings_db.set_setting, "stt_model", str(payload["stt_model"]))
            os.environ["GUPPY_WHISPER_MODEL"] = str(payload["stt_model"])

        return {"ok": True}

    @router.post("/test")
    async def test_voice(
        payload: Dict[str, str],
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        """Trigger server-side TTS (plays through server speakers)."""
        if not getattr(owner, "GUPPY_VOICE_AVAILABLE", False):
            raise HTTPException(status_code=503, detail="Voice not available")
        text = payload.get("text", "Voice test. Guppy is ready.").strip()[:500]
        try:
            voice_handler = await _get_voice_handler(ctx, owner)
            await ctx.run_blocking(
                voice_handler.speak,
                text,
                timeout_seconds=getattr(owner, "VOICE_TIMEOUT_SECONDS", 30),
            )
            return {"ok": True, "text": text}
        except Exception as e:
            raise HTTPException(status_code=503, detail=str(e))

    @router.post("/speak")
    async def speak_for_browser(
        payload: Dict[str, Any],
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        """Synthesize text → audio bytes for browser playback.

        Returns audio/wav or audio/mpeg. Frontend plays via <audio> element.
        Falls back gracefully: caller should use Web Speech API on 503.
        """
        text = str(payload.get("text", "")).strip()[:1000]
        if not text:
            raise HTTPException(status_code=400, detail="text required")
        voice = str(payload.get("voice", os.environ.get("GUPPY_TTS_VOICE", "bm_lewis"))).strip()
        speed = float(payload.get("speed", 1.0))
        speed = max(0.5, min(2.0, speed))

        try:
            audio_bytes, mime = await _synthesize_for_browser(text, voice, speed)
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))

        return Response(content=audio_bytes, media_type=mime, headers={
            "Cache-Control": "no-store",
        })

    @router.post("/stop")
    async def stop_voice(_user_id: str = Depends(ctx.require_rate_limit)):
        """Interrupt active server-side TTS."""
        if not getattr(owner, "GUPPY_VOICE_AVAILABLE", False) or _voice_instance is None:
            return {"ok": True}
        try:
            await asyncio.to_thread(_voice_instance.stop_speaking)
        except Exception:
            pass
        return {"ok": True}

    return router
