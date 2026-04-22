import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils.session_logger import rotate_jsonl_file
from utils.operational_telemetry import log_operational_event

_LOCK = threading.Lock()
_LOG_PATH = Path(__file__).resolve().parent.parent / "runtime" / "router_scorecard.jsonl"


def log_router_scorecard(**fields: Any) -> None:
    """Append one router scorecard event as JSONL."""
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": "router_scorecard",
    }
    payload.update(fields)

    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=True)

    with _LOCK:
        rotate_jsonl_file(_LOG_PATH)
        with _LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    log_operational_event(
        stream="router_scorecard",
        event="router_scorecard",
        level="info",
        payload=payload,
    )
