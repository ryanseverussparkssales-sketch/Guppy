from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from src.guppy.experience_config.services import get_runtime_envelope_config
from src.guppy.paths import RUNTIME_DIR

try:
    import psutil

    PSUTIL_AVAILABLE = True
except Exception:
    psutil = None
    PSUTIL_AVAILABLE = False

try:
    from utils.safe_io import write_json_atomic as _write_json_atomic
except ImportError:
    def _write_json_atomic(path, data):  # type: ignore[misc]
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=True), encoding="utf-8")
        tmp.replace(path)

try:
    from utils.operational_telemetry import log_operational_event
except Exception:
    def log_operational_event(*_args, **_kwargs):
        return

try:
    from win11toast import toast as win11_toast

    TOAST_AVAILABLE = True
except ImportError:
    win11_toast = None
    TOAST_AVAILABLE = False

try:
    import win32api  # noqa: F401
    import win32gui

    WIN32_AVAILABLE = True
except ImportError:
    win32api = None
    win32gui = None
    WIN32_AVAILABLE = False


logger = logging.getLogger("src.guppy.daemon.daemon")


def get_operator():
    try:
        from utils.hub_operator import get_operator as _get_operator

        return _get_operator()
    except Exception:
        return None


def is_quiet_hours_now(quiet_hours: str, enabled: bool) -> bool:
    if not enabled:
        return False
    try:
        from datetime import datetime

        parts = quiet_hours.split("-", 1)
        start_h = int(parts[0])
        end_h = int(parts[1])
        hour = datetime.now().hour
        if start_h == end_h:
            return False
        if start_h < end_h:
            return start_h <= hour < end_h
        return hour >= start_h or hour < end_h
    except Exception:
        return False
