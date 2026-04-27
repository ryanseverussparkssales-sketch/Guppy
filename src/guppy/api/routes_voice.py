"""Voice API — provider status, settings persistence, TTS synthesis for browser playback.

GET  /api/voices                — backend status + available providers/voices
PUT  /api/voices/settings       — persist TTS/STT preferences to settings DB
POST /api/voices/test           — trigger server-side TTS (plays through server speakers)
POST /api/voices/speak          — synthesize text → audio bytes for browser playback
POST /api/voices/transcribe     — STT: Deepgram nova-3 preferred, Whisper fallback
POST /api/voices/stop           — interrupt active server-side TTS
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import struct
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── Kokoro availability cache ─────────────────────────────────────────────────
_kokoro_available: bool | None = None
_kokoro_checked_at: float = 0.0
_KOKORO_CACHE_TTL = 60.0  # re-probe at most once per minute

# ── ElevenLabs voices cache ───────────────────────────────────────────────────
_eleven_voices_cache: list[dict] | None = None
_eleven_voices_fetched_at: float = 0.0
_ELEVEN_VOICES_CACHE_TTL = 300.0  # 5 min

# ── GuppyVoice process-level cache ───────────────────────────────────────────
_voice_instance: Any = None  # cached after first construction

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
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
    {"id": "af_heart",   "name": "Heart (American Female)","lang": "en-us"},
]

# Fallback when ElevenLabs API is unreachable
_ELEVENLABS_VOICES_DEFAULT = [
    {"id": "21m00Tcm4TlvDq8ikWAM", "name": "Rachel",  "lang": "en-us"},
    {"id": "AZnzlk1XvdvUeBnXmlld", "name": "Domi",    "lang": "en-us"},
    {"id": "EXAVITQu4vr4xnSDxMaL", "name": "Bella",   "lang": "en-us"},
    {"id": "ErXwobaYiN019PkySvjV", "name": "Antoni",  "lang": "en-us"},
    {"id": "MF3mGyEYCl7XYWbV9V6O", "name": "Elli",    "lang": "en-us"},
    {"id": "VR6AewLTigWG4xSOukaG", "name": "Arnold",  "lang": "en-us"},
    {"id": "pNInz6obpgDQGcFmaJgB", "name": "Adam",    "lang": "en-us"},
]

_WHISPER_MODELS = [
    {"id": "large-v3",  "name": "Whisper Large v3 (best accuracy)"},
    {"id": "medium",    "name": "Whisper Medium (balanced)"},
    {"id": "small",     "name": "Whisper Small (faster)"},
    {"id": "tiny",      "name": "Whisper Tiny (fastest)"},
]

_KOKORO_VOICE_IDS = {v["id"] for v in _KOKORO_VOICES}


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


def _fetch_elevenlabs_voices() -> list[dict]:
    """Fetch user's ElevenLabs voice library (cached 5 min). Falls back to default list."""
    global _eleven_voices_cache, _eleven_voices_fetched_at
    now = time.monotonic()
    if _eleven_voices_cache is not None and now - _eleven_voices_fetched_at < _ELEVEN_VOICES_CACHE_TTL:
        return _eleven_voices_cache
    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        return _ELEVENLABS_VOICES_DEFAULT
    try:
        req = urllib.request.Request(
            "https://api.elevenlabs.io/v1/voices",
            headers={"xi-api-key": api_key, "Accept": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        voices = data.get("voices", [])
        result = [
            {"id": v["voice_id"], "name": v["name"], "lang": "en-us"}
            for v in voices
            if v.get("voice_id") and v.get("name")
        ]
        _eleven_voices_cache = result or _ELEVENLABS_VOICES_DEFAULT
        _eleven_voices_fetched_at = now
        logger.debug("[voice] ElevenLabs: fetched %d voices", len(_eleven_voices_cache))
        return _eleven_voices_cache
    except Exception as exc:
        logger.warning("[voice] ElevenLabs voice fetch failed: %s", exc)
        _eleven_voices_cache = _ELEVENLABS_VOICES_DEFAULT
        _eleven_voices_fetched_at = now
        return _ELEVENLABS_VOICES_DEFAULT


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
        # output_format as query param (header approach doesn't work)
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream?output_format=mp3_44100_128",
            data=payload,
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        return data if data else None
    except Exception as exc:
        logger.warning("[voice] ElevenLabs TTS failed: %s", exc)
        return None


def _resolve_elevenlabs_voice(voice: str) -> str:
    """Given a voice ID, return an ElevenLabs voice ID.

    If the requested voice looks like a Kokoro voice or is empty, fall back to
    the env-configured default ElevenLabs voice.
    """
    if not voice or voice in _KOKORO_VOICE_IDS:
        return os.environ.get("ELEVENLABS_DEFAULT_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
    return voice


def _transcribe_deepgram_bytes(audio_bytes: bytes, api_key: str, content_type: str = "audio/webm") -> str:
    """Send audio bytes directly to Deepgram nova-3, return transcript."""
    ct = content_type or "audio/webm"
    req = urllib.request.Request(
        "https://api.deepgram.com/v1/listen?model=nova-3&smart_format=true&language=en",
        data=audio_bytes,
        headers={
            "Authorization": f"Token {api_key}",
            "Content-Type": ct,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return (
        data.get("results", {})
        .get("channels", [{}])[0]
        .get("alternatives", [{}])[0]
        .get("transcript", "")
        .strip()
    )


async def _synthesize_for_browser(
    text: str, voice: str, speed: float, provider: str = "auto"
) -> tuple[bytes, str]:
    """Synthesize TTS honouring provider preference; return (audio_bytes, mime_type) or raise."""
    want_kokoro = provider in ("auto", "kokoro")
    want_eleven = provider in ("auto", "elevenlabs")

    if want_kokoro:
        wav = await asyncio.to_thread(_try_kokoro_api, text, voice, speed)
        if wav:
            return wav, "audio/wav"
        if provider == "kokoro":
            raise RuntimeError("Kokoro TTS unavailable — is the Kokoro API server running?")

    if want_eleven:
        eleven_voice = _resolve_elevenlabs_voice(voice)
        mp3 = await asyncio.to_thread(_try_elevenlabs, text, eleven_voice)
        if mp3:
            return mp3, "audio/mpeg"
        if provider == "elevenlabs":
            raise RuntimeError("ElevenLabs TTS failed — check ELEVENLABS_API_KEY and voice ID")

    if provider == "sapi":
        raise RuntimeError("Windows SAPI is server-side only and cannot be streamed to the browser")

    raise RuntimeError(
        "No browser-streamable TTS backend available. "
        "Start the Kokoro API server (port 8881) or configure ELEVENLABS_API_KEY."
    )


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
        eleven_key   = bool(os.environ.get("ELEVENLABS_API_KEY", "").strip())
        deepgram_key = bool(os.environ.get("DEEPGRAM_API_KEY", "").strip())
        whisper_model = os.environ.get("GUPPY_WHISPER_MODEL", "large-v3").strip()
        stt_provider  = os.environ.get("GUPPY_STT_PROVIDER", "auto").strip().lower()

        kokoro_available = await asyncio.to_thread(_probe_kokoro) if tts_provider != "sapi" else False

        # Fetch ElevenLabs voices (cached, non-blocking)
        eleven_voices = await asyncio.to_thread(_fetch_elevenlabs_voices) if eleven_key else _ELEVENLABS_VOICES_DEFAULT

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
                    "elevenlabs": eleven_voices,
                },
                "active_voice": os.environ.get("GUPPY_TTS_VOICE", "bm_lewis"),
                "speed":        os.environ.get("GUPPY_TTS_RATE",  "1.0"),
            },
            "stt": {
                "active_provider": stt_provider,
                "active_model":    whisper_model,
                "providers": [
                    {"id": "auto",     "name": "Auto (Deepgram → Whisper)", "available": True},
                    {"id": "deepgram", "name": "Deepgram nova-3",           "available": deepgram_key},
                    {"id": "whisper",  "name": "Whisper (local)",           "available": True},
                    {"id": "browser",  "name": "Browser Web Speech",        "available": True},
                ],
                "models": _WHISPER_MODELS,
                "deepgram_available": deepgram_key,
            },
            "voice_available": getattr(owner, "GUPPY_VOICE_AVAILABLE", False),
        }

    @router.put("/settings")
    async def update_voice_settings(
        payload: Dict[str, Any],
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        """Persist TTS provider, voice, speed, STT provider/model preferences."""
        from src.guppy.api.routes_settings import _settings_db

        mapping = {
            "tts_provider":  ("tts_provider",  "GUPPY_TTS_PROVIDER"),
            "tts_voice":     ("tts_voice",     "GUPPY_TTS_VOICE"),
            "tts_speed":     ("tts_speed",     "GUPPY_TTS_RATE"),
            "stt_provider":  ("stt_provider",  "GUPPY_STT_PROVIDER"),
            "stt_model":     ("stt_model",     "GUPPY_WHISPER_MODEL"),
        }
        for key, (db_key, env_key) in mapping.items():
            if key in payload:
                val = str(payload[key])
                await asyncio.to_thread(_settings_db.set_setting, db_key, val)
                os.environ[env_key] = val

        return {"ok": True}

    @router.post("/transcribe")
    async def transcribe_audio(
        file: UploadFile = File(...),
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        """STT: Accept browser audio upload, return plain transcript.

        Priority: Deepgram nova-3 (cloud, needs DEEPGRAM_API_KEY) →
                  GuppyVoice whisper (local) → 503
        """
        audio_bytes = await file.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio upload")

        content_type = file.content_type or "audio/webm"
        deepgram_key = os.environ.get("DEEPGRAM_API_KEY", "").strip()
        stt_provider  = os.environ.get("GUPPY_STT_PROVIDER", "auto").strip().lower()

        want_deepgram = stt_provider in ("auto", "deepgram") and bool(deepgram_key)
        want_whisper  = stt_provider in ("auto", "whisper")

        # ── Deepgram ────────────────────────────────────────────────────────
        if want_deepgram:
            try:
                transcript = await asyncio.to_thread(
                    _transcribe_deepgram_bytes, audio_bytes, deepgram_key, content_type
                )
                if transcript:
                    return {"transcript": transcript, "provider": "deepgram"}
            except Exception as exc:
                logger.warning("[voice] Deepgram STT failed, falling back: %s", exc)

        # ── Whisper via GuppyVoice ──────────────────────────────────────────
        if want_whisper and getattr(owner, "GUPPY_VOICE_AVAILABLE", False):
            suffix = Path(file.filename or "audio.webm").suffix or ".webm"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name
            try:
                voice_handler = await _get_voice_handler(ctx, owner)
                if hasattr(voice_handler, "transcribe_audio"):
                    transcript = await ctx.run_blocking(
                        voice_handler.transcribe_audio, tmp_path, timeout_seconds=60
                    )
                    if transcript:
                        return {"transcript": transcript, "provider": "whisper"}
            except Exception as exc:
                logger.warning("[voice] Whisper STT failed: %s", exc)
            finally:
                try:
                    Path(tmp_path).unlink(missing_ok=True)
                except Exception:
                    pass

        raise HTTPException(
            status_code=503,
            detail=(
                "No STT backend available. "
                "Configure DEEPGRAM_API_KEY or ensure Whisper is loaded."
            ),
        )

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

        Respects the active TTS provider (kokoro / elevenlabs / auto).
        Returns audio/wav or audio/mpeg. Frontend plays via <audio> element.
        Falls back gracefully: caller should use Web Speech API on 503.
        """
        text = str(payload.get("text", "")).strip()[:1000]
        if not text:
            raise HTTPException(status_code=400, detail="text required")

        # Voice: caller can override; otherwise use server setting
        voice = str(
            payload.get("voice") or os.environ.get("GUPPY_TTS_VOICE", "bm_lewis")
        ).strip()
        speed = float(payload.get("speed", 1.0))
        speed = max(0.5, min(2.0, speed))

        # Provider: caller can override; otherwise use server setting
        provider = str(
            payload.get("provider") or os.environ.get("GUPPY_TTS_PROVIDER", "auto")
        ).strip().lower()

        try:
            audio_bytes, mime = await _synthesize_for_browser(text, voice, speed, provider)
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
