"""Chat request idempotency helpers for API runtime endpoints.

This module owns idempotency record state so API entrypoints can reuse
the same behavior without keeping lock/record logic inline.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from typing import Any, Dict


_CHAT_IDEMPOTENCY_TTL_SECONDS = max(
    60.0,
    float(os.environ.get("GUPPY_CHAT_IDEMPOTENCY_TTL_SECONDS", "300") or "300"),
)
_chat_idempotency_lock = threading.Lock()
_chat_idempotency_records: Dict[str, Dict[str, Any]] = {}


def _prune_chat_idempotency_records(now: float | None = None) -> None:
    cutoff = (time.monotonic() if now is None else now) - _CHAT_IDEMPOTENCY_TTL_SECONDS
    stale_keys = [
        key
        for key, record in _chat_idempotency_records.items()
        if float(record.get("created_at", 0.0) or 0.0) < cutoff
    ]
    for key in stale_keys:
        _chat_idempotency_records.pop(key, None)


def build_chat_request_fingerprint(
    *,
    message: str,
    session_id: str | None,
    mode: str | None,
    persona: str | None,
    history: Any,
) -> str:
    payload = {
        "message": message,
        "session_id": session_id or "",
        "mode": mode or "",
        "persona": persona or "",
        "history": history or [],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def register_chat_idempotency_key(key: str, fingerprint: str) -> tuple[bool, threading.Event]:
    now = time.monotonic()
    with _chat_idempotency_lock:
        _prune_chat_idempotency_records(now)
        record = _chat_idempotency_records.get(key)
        if isinstance(record, dict):
            return False, record["event"]
        event = threading.Event()
        _chat_idempotency_records[key] = {
            "created_at": now,
            "event": event,
            "fingerprint": fingerprint,
            "response": None,
            "error": None,
            "status": None,
            "headers": None,
        }
        return True, event


def resolve_chat_idempotency_key(key: str, fingerprint: str) -> Dict[str, Any] | None:
    with _chat_idempotency_lock:
        record = _chat_idempotency_records.get(key)
        if not isinstance(record, dict):
            return None
        if str(record.get("fingerprint", "") or "") != fingerprint:
            return None
        event = record.get("event")
        if not isinstance(event, threading.Event) or not event.is_set():
            return None
        response = record.get("response")
        payload: Dict[str, Any] = {
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


def takeover_chat_idempotency_key(key: str, fingerprint: str) -> tuple[bool, threading.Event, bool]:
    now = time.monotonic()
    with _chat_idempotency_lock:
        _prune_chat_idempotency_records(now)
        record = _chat_idempotency_records.get(key)
        if isinstance(record, dict):
            event = record.get("event")
            if not isinstance(event, threading.Event):
                event = threading.Event()
            stored_fingerprint = str(record.get("fingerprint", "") or "")
            if stored_fingerprint == fingerprint:
                return False, event, False
            if not event.is_set():
                return False, event, False
            _chat_idempotency_records.pop(key, None)
        event = threading.Event()
        _chat_idempotency_records[key] = {
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
    key: str,
    *,
    response: Dict[str, Any] | None = None,
    error: Any = None,
    status_code: int = 200,
    headers: Dict[str, str] | None = None,
) -> None:
    with _chat_idempotency_lock:
        record = _chat_idempotency_records.get(key)
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


def clear_chat_idempotency_key(key: str) -> None:
    with _chat_idempotency_lock:
        _chat_idempotency_records.pop(key, None)
