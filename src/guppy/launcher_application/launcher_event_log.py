"""Launcher event journal writer.

Extracted from LauncherWindow._log_launcher_event as part of TR54-B1.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from src.guppy.launcher_application.storage_io import append_jsonl


def log_launcher_event(
    event: str,
    *,
    runtime_path: Path,
    start_time: float,
    **fields: object,
) -> None:
    """Append a structured launcher event record to the runtime journal."""
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source": "launcher",
        "event": event,
        "uptime_s": round(time.monotonic() - start_time, 3),
        **fields,
    }
    try:
        append_jsonl(runtime_path / "launcher_events.jsonl", record)
    except Exception:
        try:
            path = runtime_path / "launcher_events.jsonl"
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=True) + "\n")
        except Exception:
            pass
