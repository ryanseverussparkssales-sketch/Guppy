from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request


def read_jsonl_tail(path: Path, limit: int = 50) -> list[dict[str, Any]]:
    lim = max(1, min(int(limit), 500))
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
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


def read_resource_envelope_status(owner: Any) -> dict[str, Any]:
    path = owner._path_config.runtime_dir / "resource_envelope.status.json"
    if not path.exists():
        return {"state": "unknown", "message": "resource envelope status file missing"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception as exc:
        return {"state": "error", "message": f"resource envelope unreadable: {exc}"}
    return {"state": "unknown", "message": "resource envelope status unavailable"}


def parse_iso_ts(ts_value: Any) -> datetime | None:
    text = str(ts_value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * 0.95)))
    return float(ordered[idx])


def query_sqlite_telemetry(
    owner: Any,
    stream: str | None,
    event: str | None,
    level: str | None,
    since_minutes: int,
    limit: int,
) -> list[dict[str, Any]]:
    db_path = owner._path_config.ops_telemetry_db
    if not db_path.exists():
        return []

    clauses: list[str] = []
    params: list[Any] = []
    if stream:
        clauses.append("stream = ?")
        params.append(stream)
    if event:
        clauses.append("event = ?")
        params.append(event)
    if level:
        clauses.append("level = ?")
        params.append(level)
    if since_minutes > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)
        clauses.append("ts >= ?")
        params.append(cutoff.isoformat())

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = (
        "SELECT ts, stream, event, level, session_id, payload_json "
        f"FROM telemetry {where} ORDER BY ts DESC LIMIT ?"
    )
    params.append(limit)

    try:
        conn = sqlite3.connect(str(db_path), timeout=owner._SQLITE_TIMEOUT_SECONDS)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute(f"PRAGMA busy_timeout = {int(owner._SQLITE_BUSY_TIMEOUT_MS)}")
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()
    except Exception:
        return []

    out: list[dict[str, Any]] = []
    for row in rows:
        payload_json = row["payload_json"]
        payload: dict[str, Any]
        try:
            parsed = json.loads(payload_json) if payload_json else {}
            payload = parsed if isinstance(parsed, dict) else {"value": parsed}
        except Exception:
            payload = {"raw": payload_json, "parse_error": True}
        out.append(
            {
                "ts": row["ts"],
                "stream": row["stream"],
                "event": row["event"],
                "level": row["level"],
                "session_id": row["session_id"],
                "payload": payload,
            }
        )
    return out


def query_jsonl_telemetry(
    owner: Any,
    stream: str | None,
    event: str | None,
    level: str | None,
    since_minutes: int,
    limit: int,
) -> list[dict[str, Any]]:
    stream_map = owner._path_config.stream_jsonl_map
    streams = [stream] if stream else list(stream_map.keys())
    cutoff = (
        datetime.now(timezone.utc) - timedelta(minutes=since_minutes)
        if since_minutes > 0
        else None
    )
    collected: list[dict[str, Any]] = []
    for stream_name in streams:
        path = stream_map.get(stream_name)
        if path is None:
            continue
        for entry in read_jsonl_tail(path, limit=max(limit * 2, 200)):
            if not isinstance(entry, dict):
                continue
            ts_value = entry.get("ts") or entry.get("timestamp") or entry.get("time")
            parsed_ts = parse_iso_ts(ts_value)
            if cutoff is not None and (parsed_ts is None or parsed_ts < cutoff):
                continue
            entry_level = str(entry.get("level", "")).strip().lower()
            entry_event = str(entry.get("event", "")).strip()
            if level and entry_level != level:
                continue
            if event and entry_event != event:
                continue
            collected.append(
                {
                    "ts": parsed_ts.isoformat() if parsed_ts else str(ts_value or ""),
                    "stream": stream_name,
                    "event": entry_event,
                    "level": entry_level or "info",
                    "session_id": str(entry.get("session_id", "") or ""),
                    "payload": entry,
                }
            )

    collected.sort(key=lambda item: str(item.get("ts", "")), reverse=True)
    return collected[:limit]


def build_telemetry_report(events: list[dict[str, Any]]) -> dict[str, Any]:
    if not events:
        return {
            "total_events": 0,
            "streams": {},
            "levels": {},
            "top_events": [],
            "active_sessions": 0,
            "window": {"first_ts": None, "last_ts": None},
            "latency_ms": {"count": 0, "avg": 0.0, "p95": 0.0, "max": 0.0},
        }

    stream_counts: dict[str, int] = {}
    level_counts: dict[str, int] = {}
    event_counts: dict[str, int] = {}
    session_ids: set[str] = set()
    latencies: list[float] = []
    timestamps: list[str] = []

    for entry in events:
        stream = str(entry.get("stream", "") or "unknown")
        level = str(entry.get("level", "") or "info").lower()
        event_name = str(entry.get("event", "") or "unknown")
        stream_counts[stream] = stream_counts.get(stream, 0) + 1
        level_counts[level] = level_counts.get(level, 0) + 1
        event_counts[event_name] = event_counts.get(event_name, 0) + 1
        session_id = str(entry.get("session_id", "") or "").strip()
        if session_id:
            session_ids.add(session_id)
        ts = str(entry.get("ts", "") or "").strip()
        if ts:
            timestamps.append(ts)
        payload = entry.get("payload")
        if isinstance(payload, dict):
            for key in ("latency_ms", "duration_ms", "elapsed_ms"):
                if key in payload:
                    try:
                        latencies.append(float(payload[key]))
                    except Exception:
                        pass
                    break

    top_events = sorted(
        (
            {"event": name, "count": count}
            for name, count in event_counts.items()
        ),
        key=lambda item: (-int(item["count"]), str(item["event"])),
    )[:10]

    latency_count = len(latencies)
    latency_avg = sum(latencies) / latency_count if latency_count else 0.0
    return {
        "total_events": len(events),
        "streams": stream_counts,
        "levels": level_counts,
        "top_events": top_events,
        "active_sessions": len(session_ids),
        "window": {
            "first_ts": min(timestamps) if timestamps else None,
            "last_ts": max(timestamps) if timestamps else None,
        },
        "latency_ms": {
            "count": latency_count,
            "avg": round(latency_avg, 2) if latency_count else 0.0,
            "p95": round(p95(latencies), 2) if latency_count else 0.0,
            "max": round(max(latencies), 2) if latency_count else 0.0,
        },
    }


def latest_stress_report_path(owner: Any) -> Path | None:
    reports_dir = owner._path_config.runtime_dir / "stress_reports"
    if not reports_dir.exists():
        return None
    reports = sorted(reports_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return reports[0] if reports else None


def collect_runtime_bundle(owner: Any) -> dict[str, Any]:
    runtime_dir = owner._path_config.runtime_dir
    status_files = [
        runtime_dir / "guppy.status",
        runtime_dir / "resource_envelope.status.json",
    ]
    out: dict[str, Any] = {
        "runtime_dir": str(runtime_dir),
        "files": {},
    }
    latest_report = latest_stress_report_path(owner)
    if latest_report and latest_report.exists():
        out["latest_stress_report"] = str(latest_report)
        try:
            out["files"][latest_report.name] = json.loads(latest_report.read_text(encoding="utf-8"))
        except Exception:
            out["files"][latest_report.name] = {"error": "unreadable"}
    else:
        out["latest_stress_report"] = None

    for path in status_files:
        if not path.exists():
            out["files"][path.name] = {"missing": True}
            continue
        try:
            out["files"][path.name] = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            out["files"][path.name] = {"error": "unreadable"}
    return out


def do_repair_action(owner: Any, action: str, dry_run: bool) -> dict[str, Any]:
    act = (action or "").strip().lower()
    if act == "warmup":
        if dry_run:
            return {
                "ok": True,
                "summary": "dry-run warmup: would refresh startup readiness and clear status cache",
            }
        owner._startup_readiness_snapshot()
        owner._status_cache["expires_at"] = 0.0
        owner._status_cache["payload"] = None
        return {"ok": True, "summary": "startup readiness refreshed; status cache invalidated"}

    if act == "restart_daemon":
        return owner._restart_managed_daemon(dry_run=dry_run)

    if act == "audit_runtime":
        bundle = collect_runtime_bundle(owner)
        if dry_run:
            return {
                "ok": True,
                "summary": "dry-run diagnostics: would collect latest stress report and runtime status files",
                "bundle_preview": {
                    "latest_stress_report": bundle.get("latest_stress_report"),
                    "file_count": len((bundle.get("files") or {}).keys()),
                },
            }
        out = owner._path_config.runtime_dir / (
            f"diagnostics_bundle_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        )
        out.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
        return {"ok": True, "summary": f"diagnostics bundle written: {out.name}", "bundle_path": str(out)}

    raise HTTPException(
        status_code=400,
        detail="unsupported action (expected: warmup|restart_daemon|audit_runtime)",
    )


def require_repair_token(owner: Any, request: Request) -> None:
    provided = (request.headers.get("X-Repair-Token") or "").strip()
    expected = owner._read_repair_token(allow_persistent_fallback=False)

    if not expected:
        owner.log_session_event(
            "api",
            "repair_token_rejected",
            level="warning",
            reason_code="repair_token_uninitialized",
            has_header=bool(provided),
        )
        raise HTTPException(
            status_code=403,
            detail={"code": "repair_token_uninitialized", "message": "Invalid repair token"},
        )

    if not provided:
        owner.log_session_event(
            "api",
            "repair_token_rejected",
            level="warning",
            reason_code="repair_token_missing",
            has_header=False,
        )
        raise HTTPException(
            status_code=403,
            detail={"code": "repair_token_missing", "message": "Invalid repair token"},
        )

    if not secrets.compare_digest(expected, provided):
        owner.log_session_event(
            "api",
            "repair_token_rejected",
            level="warning",
            reason_code="repair_token_mismatch",
            has_header=True,
        )
        raise HTTPException(
            status_code=403,
            detail={"code": "repair_token_mismatch", "message": "Invalid repair token"},
        )
