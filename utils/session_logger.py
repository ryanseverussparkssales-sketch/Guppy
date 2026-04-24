import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from utils.operational_telemetry import log_operational_event
except Exception:
    def log_operational_event(*_args, **_kwargs):
        return

_LOCK = threading.Lock()
_LOG_PATH = Path(__file__).resolve().parent.parent / "runtime" / "session_events.jsonl"
_MAX_BYTES = int(os.environ.get("GUPPY_LOG_MAX_BYTES", "5000000"))
_KEEP_FILES = int(os.environ.get("GUPPY_LOG_KEEP_FILES", "5"))


def rotate_jsonl_file(path: Path, max_bytes: int | None = None, keep_files: int | None = None) -> None:
    max_size = int(max_bytes or _MAX_BYTES)
    keep = max(1, int(keep_files or _KEEP_FILES))
    if not path.exists():
        return
    try:
        if path.stat().st_size < max_size:
            return
    except Exception:
        return

    oldest = path.with_suffix(path.suffix + f".{keep}")
    if oldest.exists():
        oldest.unlink(missing_ok=True)
    for idx in range(keep - 1, 0, -1):
        src = path.with_suffix(path.suffix + f".{idx}")
        dst = path.with_suffix(path.suffix + f".{idx + 1}")
        if src.exists():
            src.replace(dst)
    path.replace(path.with_suffix(path.suffix + ".1"))


def log_session_event(
    source: str,
    event: str,
    level: str = "info",
    session_id: str = "",
    **fields: Any,
) -> None:
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": (source or "unknown").strip() or "unknown",
        "event": (event or "event").strip() or "event",
        "level": (level or "info").strip().lower() or "info",
    }
    if session_id:
        payload["session_id"] = str(session_id)
    payload.update(fields)

    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=True)

    with _LOCK:
        rotate_jsonl_file(_LOG_PATH)
        with _LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    log_operational_event(
        stream="session_events",
        event=payload.get("event", "event"),
        level=payload.get("level", "info"),
        payload=payload,
    )


def tail_session_events(limit: int = 50) -> list[dict[str, Any]]:
    lim = max(1, min(int(limit), 500))
    if not _LOG_PATH.exists():
        return []

    with _LOCK:
        lines = _LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()

    out: list[dict[str, Any]] = []
    for line in lines[-lim:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            out.append({"raw": line, "parse_error": True})
    return out
