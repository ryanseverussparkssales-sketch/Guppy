"""Voice API — thin HTTP wrapper over the Stack C voice facade.

GET  /api/voices                — provider status, voices, active config
PUT  /api/voices/settings       — persist TTS/STT preferences
POST /api/voices/test           — synthesize TTS (server-side test)
POST /api/voices/speak          — synthesize text → audio bytes for browser
POST /api/voices/transcribe     — STT via fallback chain (Deepgram → Whisper → SAPI)
POST /api/voices/stop           — interrupt active TTS
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response

from src.guppy.api.server_context import ServerContext
from src.guppy.voice import voice as _voice
from src.guppy.voice.audio_utils import pcm_to_wav
from src.guppy.voice.tts.kokoro_provider import KOKORO_VOICES, KokoroTTSProvider
from src.guppy.voice.tts.elevenlabs_provider import ELEVENLABS_VOICES_DEFAULT, ElevenLabsTTSProvider
from src.guppy.voice.stt.whisper_stt import WHISPER_MODELS

logger = logging.getLogger(__name__)

_FORMAT_TO_MIME: dict[str, str] = {
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "pcm": "audio/wav",  # PCM is wrapped in WAV before responding
}

# Process-level provider instances (reused for both health checks and synthesis)
_kokoro_status = KokoroTTSProvider()
_eleven_status = ElevenLabsTTSProvider()

# Pre-warm Kokoro pipeline in background: on first call KPipeline downloads
# model weights (~200 MB) which can take 30-120 s. Starting this early means
# the model is cached before the first TTS request arrives.
def _preload_kokoro_bg() -> None:
    try:
        import asyncio as _aio
        loop = _aio.new_event_loop()
        loop.run_until_complete(_kokoro_status.health_check())
        loop.close()
        logger.info("Kokoro TTS pre-warm complete")
    except Exception as exc:
        logger.debug("Kokoro TTS pre-warm error: %s", exc)

import threading as _threading
_threading.Thread(target=_preload_kokoro_bg, daemon=True, name="kokoro-preload").start()

def _provider_for_id(provider_id: str):
    """Return the matching TTS provider instance, or None if unknown."""
    pid = (provider_id or "").strip().lower()
    if pid == "elevenlabs":
        return _eleven_status
    if pid == "kokoro":
        return _kokoro_status
    if pid in ("sapi", "windows"):
        from src.guppy.voice.tts.sapi_provider import SAPITTSProvider
        return SAPITTSProvider()
    return None


def _audio_response(audio_data: bytes, fmt: str, sample_rate: int = 22050) -> Response:
    """Build a streaming-friendly audio Response, wrapping PCM in WAV if needed."""
    if fmt == "pcm":
        audio_data = pcm_to_wav(audio_data, sample_rate=sample_rate)
    mime = _FORMAT_TO_MIME.get(fmt, "audio/wav")
    return Response(
        content=audio_data,
        media_type=mime,
        headers={"Cache-Control": "no-store"},
    )


def build_voice_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/voices")

    @router.get("")
    async def get_voices(_user_id: str = Depends(ctx.require_rate_limit)) -> Dict[str, Any]:
        """Return available TTS/STT providers, voices, and active config."""
        eleven_key   = bool(os.environ.get("ELEVENLABS_API_KEY", "").strip())
        deepgram_key = bool(os.environ.get("DEEPGRAM_API_KEY",  "").strip())
        config       = _voice.get_voice_config()

        kokoro_ok    = await _kokoro_status.health_check()
        eleven_voices = (
            await asyncio.to_thread(_eleven_status.list_voices_sync)
            if eleven_key else ELEVENLABS_VOICES_DEFAULT
        )

        return {
            "tts": {
                "active_provider": os.environ.get("GUPPY_TTS_PROVIDER", config.active_tts_provider),
                "providers": [
                    {"id": "auto",       "name": "Auto (recommended)", "available": True},
                    {"id": "kokoro",     "name": "Kokoro (local)",     "available": kokoro_ok},
                    {"id": "elevenlabs", "name": "ElevenLabs",         "available": eleven_key},
                    {"id": "sapi",       "name": "Windows SAPI",       "available": True},
                ],
                "voices": {
                    "kokoro":     KOKORO_VOICES,
                    "elevenlabs": eleven_voices,
                },
                "active_voice": config.tts_voice,
                "speed":        str(config.tts_speed),
            },
            "stt": {
                "active_provider": os.environ.get("GUPPY_STT_PROVIDER", config.active_stt_provider),
                "active_model":    os.environ.get("GUPPY_WHISPER_MODEL", "large-v3"),
                "providers": [
                    {"id": "auto",     "name": "Auto (Deepgram → Whisper)", "available": True},
                    {"id": "deepgram", "name": "Deepgram nova-3",           "available": deepgram_key},
                    {"id": "whisper",  "name": "Whisper (local)",           "available": True},
                    {"id": "browser",  "name": "Browser Web Speech",        "available": True},
                ],
                "models": WHISPER_MODELS,
                "deepgram_available": deepgram_key,
            },
            "voice_available": True,
        }

    @router.put("/settings")
    async def update_voice_settings(
        payload: Dict[str, Any],
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        """Persist TTS/STT preferences to settings DB and live config."""
        from src.guppy.api.routes_settings import _settings_db

        config = _voice.get_voice_config()

        # (payload_key, db_key, env_var, config_attr)
        field_map = [
            ("tts_provider", "tts_provider",  "GUPPY_TTS_PROVIDER",  "active_tts_provider"),
            ("tts_voice",    "tts_voice",     "GUPPY_TTS_VOICE",     "tts_voice"),
            ("tts_speed",    "tts_speed",     "GUPPY_TTS_RATE",      "tts_speed"),
            ("stt_provider", "stt_provider",  "GUPPY_STT_PROVIDER",  "active_stt_provider"),
            ("stt_model",    "stt_model",     "GUPPY_WHISPER_MODEL", None),
        ]
        for payload_key, db_key, env_key, config_attr in field_map:
            if payload_key not in payload:
                continue
            raw = str(payload[payload_key])
            await asyncio.to_thread(_settings_db.set_setting, db_key, raw)
            os.environ[env_key] = raw
            if config_attr and hasattr(config, config_attr):
                val = float(raw) if config_attr == "tts_speed" else raw
                setattr(config, config_attr, val)

        _voice.set_voice_config(config)
        return {"ok": True}

    @router.post("/transcribe")
    async def transcribe_audio(
        file: UploadFile = File(...),
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        """STT: accept browser audio upload, return plain transcript."""
        audio_bytes = await file.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio upload")

        result = await _voice.transcribe(audio_bytes)
        if result.error:
            raise HTTPException(
                status_code=503,
                detail=result.error or "STT failed — no backend available",
            )
        return {"transcript": result.text, "provider": result.provider}

    @router.post("/speak")
    async def speak_for_browser(
        payload: Dict[str, Any],
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        """Synthesize text → audio bytes for browser playback."""
        text = str(payload.get("text", "")).strip()[:1000]
        if not text:
            raise HTTPException(status_code=400, detail="text required")

        voice_id    = str(payload.get("voice") or os.environ.get("GUPPY_TTS_VOICE", "bm_lewis")).strip() or None
        provider_id = str(payload.get("provider") or "").strip().lower()

        # If a specific provider is requested, call it directly instead of the full chain
        specific = _provider_for_id(provider_id) if provider_id and provider_id != "auto" else None
        if specific:
            result = await specific.synthesize(text, voice_id)
        else:
            result = await _voice.synthesize(text, voice=voice_id)

        if result.error or not result.audio_data:
            raise HTTPException(
                status_code=503,
                detail=result.error or "TTS produced no audio",
            )
        return _audio_response(result.audio_data, result.format, getattr(result, "sample_rate", 0) or 22050)

    @router.post("/test")
    async def test_voice(
        payload: Dict[str, str],
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        """Synthesize a test phrase via the TTS stack (server-side verification)."""
        text = payload.get("text", "Voice test. Guppy is ready.").strip()[:500]
        result = await _voice.speak(text)
        if result.error:
            raise HTTPException(status_code=503, detail=result.error)
        return {"ok": True, "text": text}

    @router.post("/stop")
    async def stop_voice(_user_id: str = Depends(ctx.require_rate_limit)):
        """Interrupt active TTS playback."""
        _voice.stop()
        return {"ok": True}

    return router
