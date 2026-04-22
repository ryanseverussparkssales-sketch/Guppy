from __future__ import annotations

import os
import re
import subprocess


def win_hidden_popen_flags() -> dict[str, object]:
    if os.name != "nt":
        return {}
    flags: dict[str, object] = {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
    }
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
    startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
    flags["startupinfo"] = startupinfo
    return flags


def clean_for_tts(text: str) -> str:
    """Strip markdown and symbol noise before passing text to speech synthesis."""
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"_{1,3}(.*?)_{1,3}", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"`{1,3}[^`]*`{1,3}", "", text, flags=re.DOTALL)
    text = re.sub(r"\|[-: ]+\|[-| :]*", "", text)
    text = text.replace("|", " ")
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"https?://\S+", "", text)
    text = text.replace("\u2013", " - ").replace("\u2014", " - ")
    text = re.sub(r"[^\x00-\x7F\u00A0-\u024F]", "", text)
    text = re.sub(r"[#>~^\\`]", "", text)
    text = re.sub(r"\n{2,}", ". ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def tts_provider_pref() -> str:
    return (os.environ.get("GUPPY_TTS_PROVIDER", "auto") or "auto").strip().lower()


def eleven_model_id() -> str:
    return (os.environ.get("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5") or "eleven_turbo_v2_5").strip()


def eleven_api_key() -> str:
    return (os.environ.get("ELEVENLABS_API_KEY", "") or "").strip()


def build_backend_status(
    *,
    provider: str,
    eleven_ready: bool,
    has_kokoro: bool,
    has_whisper: bool,
    has_speech_recognition: bool,
    oww_available: bool | None,
    wake_enabled: bool,
    quiet_mode: bool,
    whisper_model_name: str,
    tts_error: str,
    stt_error: str,
) -> dict:
    if provider == "elevenlabs" and eleven_ready:
        tts_backend = "elevenlabs"
    elif provider == "sapi":
        tts_backend = "sapi"
    elif has_kokoro:
        tts_backend = "kokoro"
    elif eleven_ready:
        tts_backend = "elevenlabs"
    else:
        tts_backend = "sapi"

    stt_backend = "whisper" if has_whisper else ("google" if has_speech_recognition else "none")
    wake_backend = "openwakeword" if oww_available is True else ("transcription" if wake_enabled else "idle")
    return {
        "tts_backend": tts_backend,
        "tts_provider_pref": provider,
        "stt_backend": stt_backend,
        "wake_backend": wake_backend,
        "wake_enabled": bool(wake_enabled),
        "quiet_mode": bool(quiet_mode),
        "whisper_model": whisper_model_name.strip(),
        "tts_fallback_active": bool(tts_backend == "sapi" and provider not in {"sapi"}),
        "tts_error": tts_error.strip(),
        "stt_error": stt_error.strip(),
    }


def resolve_kokoro_voice(requested: str | None, default_voice: str) -> str:
    voice = (requested or default_voice or "").strip()
    voice_l = voice.lower()
    if voice_l.startswith(("af_", "am_", "bf_", "bm_")):
        return voice
    if any(name in voice_l for name in ("ryan", "thomas", "connor", "lewis", "merlin", "guppy")):
        return "bm_lewis"
    return "bm_lewis"


def sapi_rate_value(rate_text: str | None) -> int:
    text = (rate_text or "").strip()
    if not text:
        return 1
    try:
        if text.endswith("%"):
            num = int(text.replace("%", "").replace("+", "").replace("-", "").strip())
            sign = -1 if text.strip().startswith("-") else 1
            value = int((num / 100.0) * 6) * sign
        else:
            value = int(text)
    except Exception:
        value = 1
    return max(-6, min(6, value))


def preferred_sapi_voice(requested: str | None) -> str:
    req = (requested or "").strip()
    req_low = req.lower()
    if req and ("neural" not in req_low) and ("bm_" not in req_low) and ("af_" not in req_low):
        return req
    return os.environ.get("GUPPY_SAPI_VOICE", "Microsoft Zira Desktop").strip() or "Microsoft Zira Desktop"


def kokoro_speed_value(rate_text: str | None, base_speed: float = 1.0) -> float:
    text = (rate_text or "").strip()
    speed = float(base_speed or 1.0)
    if not text:
        return max(0.7, min(1.45, speed))
    try:
        if text.endswith("%"):
            num = float(text.replace("%", "").replace("+", "").replace("-", "").strip())
            sign = -1.0 if text.startswith("-") else 1.0
            speed *= 1.0 + ((num / 100.0) * sign)
        else:
            speed *= float(text)
    except Exception:
        pass
    return max(0.7, min(1.45, speed))
