import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_RUNTIME = Path(__file__).resolve().parent.parent / "runtime"


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        norm = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(norm)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _tail_jsonl(path: Path, limit: int = 1000) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for line in lines[-max(10, int(limit)):]:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                out.append(obj)
        except Exception:
            continue
    return out


def _pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    vals = sorted(float(v) for v in values)
    if len(vals) == 1:
        return vals[0]
    rank = max(0.0, min(1.0, float(q))) * (len(vals) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(vals) - 1)
    frac = rank - lo
    return vals[lo] * (1.0 - frac) + vals[hi] * frac


def rolling_agent_snapshot(agent: str, window_seconds: int = 900) -> dict[str, Any]:
    aid = str(agent or "").strip().lower()
    perf = _tail_jsonl(_RUNTIME / "agent_performance.jsonl", limit=1200)
    cutoff = datetime.now(timezone.utc).timestamp() - max(60, int(window_seconds))

    starts = set()
    completes = set()
    latencies = []
    latest: dict[str, Any] = {}

    for row in perf:
        row_agent = str(row.get("agent", "")).strip().lower()
        if row_agent != aid:
            continue
        ts = _parse_ts(row.get("ts"))
        if ts is None or ts.timestamp() < cutoff:
            continue
        latest = row
        evt = str(row.get("event", "")).strip().lower()
        req_id = str(row.get("request_id", "")).strip()
        if evt == "request_started" and req_id:
            starts.add(req_id)
        elif evt == "request_complete":
            if req_id:
                completes.add(req_id)
            if isinstance(row.get("latency_ms"), (int, float)):
                latencies.append(float(row.get("latency_ms")))

    queue_depth = len(starts - completes)
    return {
        "latest": latest,
        "p95_ms": round(_pct(latencies, 0.95), 1) if latencies else 0.0,
        "p99_ms": round(_pct(latencies, 0.99), 1) if latencies else 0.0,
        "queue_depth": queue_depth,
        "samples": len(latencies),
        "latencies": latencies[-60:],
    }


def recent_agent_events(agent: str, limit: int = 25) -> list[dict[str, Any]]:
    aid = str(agent or "").strip().lower()
    perf = _tail_jsonl(_RUNTIME / "agent_performance.jsonl", limit=max(50, limit * 6))
    out = []
    for row in perf:
        if str(row.get("agent", "")).strip().lower() == aid:
            out.append(row)
    return out[-max(1, int(limit)):]
