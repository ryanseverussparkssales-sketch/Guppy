import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from utils.session_logger import rotate_jsonl_file

_LOCK = threading.Lock()
_LOG_PATH = Path(__file__).resolve().parent.parent / "runtime" / "agent_performance.jsonl"


def log_agent_performance(agent: str, event: str, **fields):
    """Append one structured performance event as JSONL."""
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "agent": agent,
        "event": event,
    }
    payload.update(fields)

    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=True)

    with _LOCK:
        rotate_jsonl_file(_LOG_PATH)
        with _LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
