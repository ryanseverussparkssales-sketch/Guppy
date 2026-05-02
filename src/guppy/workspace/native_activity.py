"""Native Windows screen/window activity tracker.

Screenpipe-compatible fallback that uses ctypes (always available on Windows)
to poll the foreground window title and process name every 30 s. Results are
stored in a bounded deque so callers can retrieve recent activity without
spinning up the full Screenpipe daemon.

Public API
----------
start_tracker()         — start the background daemon thread (idempotent)
get_recent_activity(minutes=5)
                        — return list of activity dicts compatible with
                          Screenpipe /search response items
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import os
import threading
import time
from collections import deque
from typing import Any

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 30  # seconds between samples
_MAX_ENTRIES   = 500  # rolling window (500 × 30s ≈ 4 hours)

_entries: deque[dict[str, Any]] = deque(maxlen=_MAX_ENTRIES)
_lock    = threading.Lock()
_started = False


# ── ctypes helpers ────────────────────────────────────────────────────────────

def _get_foreground_window_info() -> dict[str, str]:
    """Return title and process name of the current foreground window."""
    result = {"title": "", "app": ""}
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return result

        # Window title
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            result["title"] = buf.value

        # Process name via PID → QueryFullProcessImageName
        pid = ctypes.wintypes.DWORD(0)
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        h_proc = ctypes.windll.kernel32.OpenProcess(
            0x0410,  # PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
            False,
            pid,
        )
        if h_proc:
            try:
                buf = ctypes.create_unicode_buffer(260)
                size = ctypes.wintypes.DWORD(260)
                ctypes.windll.kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size))
                path = buf.value
                result["app"] = os.path.basename(path) if path else ""
            finally:
                ctypes.windll.kernel32.CloseHandle(h_proc)
    except Exception:
        pass
    return result


# ── Background polling thread ─────────────────────────────────────────────────

def _poll_loop() -> None:
    logger.info("[native_activity] tracker started (poll interval %ds)", _POLL_INTERVAL)
    while True:
        try:
            info = _get_foreground_window_info()
            if info["title"] or info["app"]:
                entry = {
                    "timestamp": time.time(),
                    "title": info["title"],
                    "app": info["app"],
                }
                with _lock:
                    _entries.append(entry)
        except Exception as exc:
            logger.debug("[native_activity] poll error: %s", exc)
        time.sleep(_POLL_INTERVAL)


def start_tracker() -> None:
    """Start the background daemon thread. Safe to call multiple times."""
    global _started
    if _started:
        return
    _started = True
    t = threading.Thread(target=_poll_loop, name="native-activity-tracker", daemon=True)
    t.start()


# ── Public query API ──────────────────────────────────────────────────────────

def get_recent_activity(minutes: int = 5) -> list[dict[str, Any]]:
    """Return recent activity entries in Screenpipe-compatible format.

    Each item matches the shape of a Screenpipe /search content block so
    callers that already handle Screenpipe output need no changes.
    """
    cutoff = time.time() - (minutes * 60)
    with _lock:
        recent = [e for e in _entries if e["timestamp"] >= cutoff]

    return [
        {
            "type": "UI",
            "content": {
                "window_name": e["title"],
                "app_name": e["app"],
                "timestamp": _ts_iso(e["timestamp"]),
                "text": e["title"],
            },
        }
        for e in recent
    ]


def _ts_iso(ts: float) -> str:
    import datetime
    return datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")
