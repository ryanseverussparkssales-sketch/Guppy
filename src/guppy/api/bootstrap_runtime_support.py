from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import threading
import time
from typing import Any


def detect_voice_backends() -> tuple[str, str, list[str]]:
    tts, stt, details = "sapi", "none", []
    # Prefer edge_tts (Azure Neural voices) > kokoro > sapi
    try:
        if importlib.util.find_spec("edge_tts") is not None:
            tts = "edge_tts"
            details.append("edge_tts module found -> Azure Neural voices")
        elif importlib.util.find_spec("kokoro") is not None:
            tts = "kokoro"
            details.append("kokoro module found")
        else:
            details.append("edge_tts/kokoro unavailable -> sapi fallback")
    except Exception:
        details.append("voice detection error -> sapi fallback")

    probe_whisper = os.environ.get("GUPPY_API_PROBE_WHISPER", "0").strip().lower() in {"1", "true", "yes", "on"}
    try:
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


def prune_chat_idempotency_records(
    records: dict[str, dict[str, Any]],
    *,
    ttl_seconds: float,
    now: float | None = None,
) -> None:
    cutoff = (time.monotonic() if now is None else now) - ttl_seconds
    stale_keys = [
        key
        for key, record in records.items()
        if float(record.get("created_at", 0.0) or 0.0) < cutoff
    ]
    for key in stale_keys:
        records.pop(key, None)


def build_chat_request_fingerprint(request: Any) -> str:
    payload = {
        "message": request.message,
        "session_id": request.session_id or "",
        "mode": request.mode or "",
        "persona": request.persona or "",
        "history": request.history or [],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def register_chat_idempotency_key(
    records: dict[str, dict[str, Any]],
    lock: threading.Lock,
    *,
    key: str,
    fingerprint: str,
    ttl_seconds: float,
) -> tuple[bool, threading.Event]:
    now = time.monotonic()
    with lock:
        prune_chat_idempotency_records(records, ttl_seconds=ttl_seconds, now=now)
        record = records.get(key)
        if isinstance(record, dict):
            return False, record["event"]
        event = threading.Event()
        records[key] = {
            "created_at": now,
            "event": event,
            "fingerprint": fingerprint,
            "response": None,
            "error": None,
            "status": None,
            "headers": None,
        }
        return True, event


def resolve_chat_idempotency_key(
    records: dict[str, dict[str, Any]],
    lock: threading.Lock,
    *,
    key: str,
    fingerprint: str,
) -> dict[str, Any] | None:
    with lock:
        record = records.get(key)
        if not isinstance(record, dict):
            return None
        if str(record.get("fingerprint", "") or "") != fingerprint:
            return None
        event = record.get("event")
        if not isinstance(event, threading.Event) or not event.is_set():
            return None
        response = record.get("response")
        payload: dict[str, Any] = {
            "status": int(record.get("status", 500) or 500),
            "headers": dict(record.get("headers", {})) if isinstance(record.get("headers"), dict) else None,
        }
        if isinstance(response, dict):
            payload["response"] = dict(response)
            return payload
        error = record.get("error")
        if error:
            payload["error"] = error
            return payload
        return None


def takeover_chat_idempotency_key(
    records: dict[str, dict[str, Any]],
    lock: threading.Lock,
    *,
    key: str,
    fingerprint: str,
    ttl_seconds: float,
) -> tuple[bool, threading.Event, bool]:
    now = time.monotonic()
    with lock:
        prune_chat_idempotency_records(records, ttl_seconds=ttl_seconds, now=now)
        record = records.get(key)
        if isinstance(record, dict):
            event = record.get("event")
            if not isinstance(event, threading.Event):
                event = threading.Event()
            stored_fingerprint = str(record.get("fingerprint", "") or "")
            if stored_fingerprint == fingerprint:
                return False, event, False
            if not event.is_set():
                return False, event, False
            records.pop(key, None)
        event = threading.Event()
        records[key] = {
            "created_at": now,
            "event": event,
            "fingerprint": fingerprint,
            "response": None,
            "error": None,
            "status": None,
            "headers": None,
        }
        return True, event, True


def complete_chat_idempotency_key(
    records: dict[str, dict[str, Any]],
    lock: threading.Lock,
    *,
    key: str,
    response: dict[str, Any] | None = None,
    error: Any = None,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> None:
    with lock:
        record = records.get(key)
        if not isinstance(record, dict):
            return
        record["created_at"] = time.monotonic()
        record["response"] = dict(response) if isinstance(response, dict) else None
        record["error"] = error
        record["status"] = int(status_code or 500)
        record["headers"] = dict(headers) if isinstance(headers, dict) else None
        event = record.get("event")
        if isinstance(event, threading.Event):
            event.set()


def clear_chat_idempotency_key(
    records: dict[str, dict[str, Any]],
    lock: threading.Lock,
    *,
    key: str,
) -> None:
    with lock:
        records.pop(key, None)
