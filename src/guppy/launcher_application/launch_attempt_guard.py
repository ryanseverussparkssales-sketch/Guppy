"""Small runtime-backed debounce helpers for launcher process start attempts."""

from __future__ import annotations

import time
from pathlib import Path


def attempt_stamp_path(runtime_dir: Path, name: str) -> Path:
    return runtime_dir / f"{name}.starting"


def mark_launch_attempt(runtime_dir: Path, name: str) -> None:
    path = attempt_stamp_path(runtime_dir, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(time.time()), encoding="utf-8")


def clear_launch_attempt(runtime_dir: Path, name: str) -> None:
    try:
        attempt_stamp_path(runtime_dir, name).unlink(missing_ok=True)
    except Exception:
        pass


def launch_attempt_recent(runtime_dir: Path, name: str, *, ttl_seconds: float) -> bool:
    path = attempt_stamp_path(runtime_dir, name)
    if not path.exists():
        return False
    try:
        age_seconds = time.time() - path.stat().st_mtime
    except OSError:
        return False
    if age_seconds <= ttl_seconds:
        return True
    clear_launch_attempt(runtime_dir, name)
    return False
