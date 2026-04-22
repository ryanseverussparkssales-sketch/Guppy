from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping


def parse_iso_ts(ts_value: Any) -> datetime | None:
    if not ts_value:
        return None
    try:
        text = str(ts_value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    index = max(0, int(len(ordered) * 0.95) - 1)
    return ordered[index]


def query_sqlite_telemetry(
    *,
    db_path: Path,
    timeout_seconds: float,
    busy_timeout_ms: int,
    stream: str | None,
    event: str | None,
    level: str | None,
    since_minutes: int | None,
    limit: int,
) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []

    where: list[str] = []
    params: list[Any] = []
    if stream:
        where.append("stream = ?")
        params.append(stream)
    if event:
        where.append("event = ?")
        params.append(event)
    if level:
        where.append("level = ?")
        params.append(level)
    if since_minutes is not None and since_minutes >= 0:
        cutoff = datetime.now(timezone.utc).timestamp() - (int(since_minutes) * 60)
        where.append("strftime('%s', ts) >= ?")
        params.append(cutoff)

    query = "SELECT ts, stream, event, level, payload_json FROM operational_events"
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    try:
        from utils.db_utils import open_db as _open_db

        connection = _open_db(
            db_path,
            timeout=timeout_seconds,
            busy_timeout_ms=busy_timeout_ms,
        )
        try:
            rows = connection.execute(query, params).fetchall()
        finally:
            connection.close()
    except Exception:
        return []

    events: list[dict[str, Any]] = []
    for ts, stream_name, event_name, event_level, payload_json in reversed(rows):
        try:
            payload = json.loads(payload_json)
        except Exception:
            payload = {"raw": str(payload_json), "parse_error": True}
        events.append(
            {
                "ts": ts,
                "stream": stream_name,
                "event": event_name,
                "level": event_level,
                "payload": payload,
            }
        )
    return events


def query_jsonl_telemetry(
    *,
    stream_jsonl_map: Mapping[str, Path],
    read_jsonl_tail: Callable[[Path, int], list[dict[str, Any]]],
    stream: str | None,
    event: str | None,
    level: str | None,
    since_minutes: int | None,
    limit: int,
) -> list[dict[str, Any]]:
    requested_streams = [stream] if stream else list(stream_jsonl_map.keys())
    cutoff = None
    if since_minutes is not None and since_minutes >= 0:
        cutoff = datetime.now(timezone.utc).timestamp() - (int(since_minutes) * 60)

    events: list[dict[str, Any]] = []
    for stream_name in requested_streams:
        path = stream_jsonl_map.get(stream_name)
        if path is None:
            continue
        for row in read_jsonl_tail(path, max(limit * 3, 120)):
            event_name = str(row.get("event", row.get("event_type", ""))).strip()
            event_level = str(row.get("level", "")).strip().lower() or "info"
            timestamp_text = row.get("ts", row.get("timestamp"))
            timestamp = parse_iso_ts(timestamp_text)
            if cutoff is not None and (timestamp is None or timestamp.timestamp() < cutoff):
                continue
            if event and event_name != event:
                continue
            if level and event_level != level:
                continue
            events.append(
                {
                    "ts": timestamp_text,
                    "stream": stream_name,
                    "event": event_name or "event",
                    "level": event_level,
                    "payload": row,
                }
            )

    events.sort(key=lambda item: parse_iso_ts(item.get("ts")) or datetime.min.replace(tzinfo=timezone.utc))
    if len(events) > limit:
        return events[-limit:]
    return events


def build_telemetry_report(
    events: list[dict[str, Any]],
    *,
    slow_request_ms: int,
) -> dict[str, Any]:
    stream_counts: Counter[str] = Counter()
    event_counts: Counter[str] = Counter()
    level_counts: Counter[str] = Counter()
    latencies: list[float] = []
    slow_count = 0

    for item in events:
        stream_counts[str(item.get("stream", "unknown"))] += 1
        event_counts[str(item.get("event", "event"))] += 1
        level_counts[str(item.get("level", "info"))] += 1

        payload = item.get("payload")
        if not isinstance(payload, dict):
            continue
        raw_latency = payload.get("latency_ms", payload.get("elapsed_ms"))
        if not isinstance(raw_latency, (int, float)):
            continue
        latency = float(raw_latency)
        latencies.append(latency)
        if latency >= slow_request_ms:
            slow_count += 1

    latest_ts = events[-1].get("ts") if events else None
    return {
        "count": len(events),
        "latest_ts": latest_ts,
        "streams": dict(stream_counts),
        "events": dict(event_counts.most_common(20)),
        "levels": dict(level_counts),
        "latency": {
            "samples": len(latencies),
            "avg_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
            "p95_ms": round(p95(latencies), 2) if latencies else 0.0,
            "slow_count": slow_count,
            "slow_threshold_ms": slow_request_ms,
        },
    }
