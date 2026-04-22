"""
src/guppy/api/snapshot_voice_support.py

Voice-backend probe helper for the API server.
Extracted from server_runtime_snapshot as part of TR54 wave 9 / Step 3 decomposition.

Detects which TTS and STT backends are available without triggering heavy
native import stacks at module-load time.
"""
from __future__ import annotations

import importlib.util
import os


def detect_voice_backends() -> tuple[str, str, list[str]]:
    """Return (tts_backend, stt_backend, detail_messages).

    Probes installed packages to decide which TTS and STT stacks are
    available.  Imported heavy backends (e.g. torch / ctranslate2 via
    faster-whisper) are guarded by a GUPPY_API_PROBE_WHISPER env flag so
    they are not actually imported at API startup unless opted-in.
    """
    tts, stt, details = "sapi", "none", []
    try:
        if importlib.util.find_spec("kokoro") is not None:
            tts = "kokoro"
            details.append("kokoro module found")
        else:
            details.append("kokoro unavailable -> sapi fallback")
    except Exception:
        details.append("kokoro unavailable -> sapi fallback")

    probe_whisper = os.environ.get("GUPPY_API_PROBE_WHISPER", "0").strip().lower() in {"1", "true", "yes", "on"}
    try:
        # Avoid importing native torch/ctranslate stacks at module import-time by default.
        if importlib.util.find_spec("faster_whisper") is not None:
            if probe_whisper:
                from faster_whisper import WhisperModel as _WM  # noqa: F401
                stt = "whisper"
                details.append("faster-whisper import ok")
            else:
                stt = "whisper"
                details.append("faster-whisper module found (lazy import)")
        else:
            raise ImportError("faster_whisper module not found")
    except Exception:
        try:
            if importlib.util.find_spec("speech_recognition") is not None:
                stt = "google"
                details.append("speech_recognition module found")
            else:
                details.append("no transcription backend available")
        except Exception:
            details.append("no transcription backend available")
    return tts, stt, details
