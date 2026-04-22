"""
utils/safe_io.py
Defensive file I/O helpers used across hub, launcher, and daemon.

Problems this solves:
  - Partially-written JSON files crash the reader (status files written mid-crash)
  - JSONL files grow without bound (no rotation)
  - Bare except blocks silently discard errors

All functions are safe to call even if the file doesn't exist.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── JSON helpers ──────────────────────────────────────────────────────────────

def read_json(path: Path | str, default: Any = None) -> Any:
    """
    Read and parse a JSON file. Returns `default` on any error.
    Logs at DEBUG level on parse failure so silent data corruption is visible
    in logs without crashing the caller.
    """
    path = Path(path)
    if not path.exists():
        return default
    try:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            return default
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.debug("Corrupt JSON in %s (offset %d): %s", path.name, e.pos, e.msg)
        return default
    except OSError as e:
        logger.debug("Cannot read %s: %s", path.name, e)
        return default


def read_json_dict(path: Path | str) -> dict:
    """Like read_json but always returns a dict (never None/list)."""
    result = read_json(path, default={})
    if not isinstance(result, dict):
        logger.debug("%s contained %s instead of dict — ignoring", Path(path).name, type(result).__name__)
        return {}
    return result


def write_json_atomic(path: Path | str, data: Any) -> bool:
    """
    Write JSON atomically via a temp file + rename.
    Prevents partial writes from corrupting status files on crash.
    Returns True on success.
    """
    path = Path(path)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(path)
        return True
    except OSError as e:
        logger.warning("Atomic write failed for %s: %s", path.name, e)
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return False


# ── JSONL helpers ─────────────────────────────────────────────────────────────

_JSONL_MAX_BYTES = int(os.environ.get("GUPPY_JSONL_MAX_MB", "20")) * 1024 * 1024
_JSONL_KEEP_LINES = int(os.environ.get("GUPPY_JSONL_KEEP_LINES", "5000"))


def append_jsonl(path: Path | str, record: dict) -> None:
    """
    Append a record to a JSONL file. If the file exceeds _JSONL_MAX_BYTES,
    rotate it by keeping the last _JSONL_KEEP_LINES lines.
    """
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=True) + "\n"
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
    except OSError as e:
        logger.warning("append_jsonl failed for %s: %s", path.name, e)
        return

    # Rotate if oversized (cheap stat check first)
    try:
        if path.stat().st_size > _JSONL_MAX_BYTES:
            _rotate_jsonl(path)
    except OSError:
        pass


def _rotate_jsonl(path: Path) -> None:
    """Keep the last _JSONL_KEEP_LINES lines, archive the rest."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        if len(lines) <= _JSONL_KEEP_LINES:
            return
        archive = path.with_suffix(f".{int(time.time())}.bak.jsonl")
        archive.write_text("".join(lines[:-_JSONL_KEEP_LINES]), encoding="utf-8")
        path.write_text("".join(lines[-_JSONL_KEEP_LINES:]), encoding="utf-8")
        logger.info("Rotated %s → archived %d lines, kept %d",
                    path.name, len(lines) - _JSONL_KEEP_LINES, _JSONL_KEEP_LINES)
    except OSError as e:
        logger.warning("JSONL rotation failed for %s: %s", path.name, e)


def read_jsonl_tail(path: Path | str, limit: int = 50) -> list[dict]:
    """Read the last `limit` valid dict records from a JSONL file."""
    path = Path(path)
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    out: list[dict] = []
    for line in lines[-limit * 2:]:          # over-read then filter
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                out.append(obj)
        except json.JSONDecodeError:
            continue
    return out[-limit:]
