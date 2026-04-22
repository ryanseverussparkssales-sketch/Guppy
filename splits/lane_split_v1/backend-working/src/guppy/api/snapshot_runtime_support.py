from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any


def emit_integration_heartbeat(owner: Any, reason: str) -> None:
    now = time.time()
    with owner._integration_heartbeat_lock:
        if now - owner._last_integration_heartbeat_ts < max(60.0, owner._INTEGRATION_HEARTBEAT_SECONDS):
            return
        owner._last_integration_heartbeat_ts = now

    path = owner._stream_jsonl_map["integration_events"]
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ts": datetime.now(timezone.utc).isoformat(),
        "event_type": "integration_heartbeat",
        "event": "integration_heartbeat",
        "level": "info",
        "payload": {
            "state": "idle",
            "reason": reason,
        },
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        owner.rotate_jsonl_file(path)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")
    except Exception:
        return


def secret_ready(value: str) -> bool:
    val = (value or "").strip()
    if not val:
        return False
    placeholder_tokens = {
        "change-me",
        "dev-only-change-me",
        "replace-me",
        "your_",
        "your-",
        "example",
        "placeholder",
    }
    low = val.lower()
    return not any(tok in low for tok in placeholder_tokens)
