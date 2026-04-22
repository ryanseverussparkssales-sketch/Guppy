from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


_ROOT = Path(__file__).resolve().parent.parent
_LOG_DIR = _ROOT / "runtime" / "logs"
_RAW_RETENTION_DAYS = 14
_SUMMARY_RETENTION_DAYS = 30
_REDACTION_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\b[A-Fa-f0-9]{32,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]{16,}\b", re.IGNORECASE),
]


def _safe_instance_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", (name or "").strip().lower()).strip("-._")
    return cleaned or "guppy-primary"


def _redact_text(value: Any) -> str:
    text = str(value or "")
    for pattern in _REDACTION_PATTERNS:
        text = pattern.sub("[redacted]", text)
    return text


def instance_log_path(name: str) -> Path:
    return _LOG_DIR / f"instance_{_safe_instance_name(name)}.jsonl"


def instance_summary_path(name: str) -> Path:
    return _LOG_DIR / f"instance_{_safe_instance_name(name)}.summary.json"


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _build_summary(name: str, entries: list[dict[str, Any]]) -> dict[str, Any]:
    roles: dict[str, int] = {}
    statuses: dict[str, int] = {}
    latest_timestamp = None
    for item in entries:
        role = str(item.get("role", "unknown") or "unknown")
        roles[role] = roles.get(role, 0) + 1
        status = str(item.get("status", "unknown") or "unknown")
        statuses[status] = statuses.get(status, 0) + 1
        latest_timestamp = item.get("timestamp") or latest_timestamp
    return {
        "instance": name,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": _SUMMARY_RETENTION_DAYS,
        "entry_count": len(entries),
        "latest_timestamp": latest_timestamp,
        "roles": roles,
        "statuses": statuses,
    }


def _write_summary(name: str, summary: dict[str, Any]) -> None:
    path = instance_summary_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="utf-8")


def _load_summary(name: str) -> dict[str, Any]:
    path = instance_summary_path(name)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _summary_bucket_key(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).date().isoformat()


def _merge_summary_buckets(
    existing_summary: dict[str, Any],
    entries: list[dict[str, Any]],
    summary_cutoff: datetime,
) -> dict[str, Any]:
    buckets: dict[str, dict[str, Any]] = {}
    for key, value in (existing_summary.get("buckets") or {}).items():
        if not isinstance(value, dict):
            continue
        ts = _parse_timestamp(value.get("latest_timestamp") or key)
        if ts is None or ts < summary_cutoff:
            continue
        buckets[str(key)] = {
            "entry_count": int(value.get("entry_count", 0) or 0),
            "roles": dict(value.get("roles") or {}),
            "statuses": dict(value.get("statuses") or {}),
            "latest_timestamp": value.get("latest_timestamp") or ts.isoformat(),
        }

    raw_buckets: dict[str, dict[str, Any]] = {}
    for item in entries:
        ts = _parse_timestamp(item.get("timestamp"))
        if ts is None or ts < summary_cutoff:
            continue
        bucket_key = _summary_bucket_key(ts)
        bucket = raw_buckets.setdefault(
            bucket_key,
            {"entry_count": 0, "roles": {}, "statuses": {}, "latest_timestamp": item.get("timestamp")},
        )
        bucket["entry_count"] = int(bucket.get("entry_count", 0) or 0) + 1
        role = str(item.get("role", "unknown") or "unknown")
        status = str(item.get("status", "unknown") or "unknown")
        bucket_roles = bucket.setdefault("roles", {})
        bucket_statuses = bucket.setdefault("statuses", {})
        bucket_roles[role] = int(bucket_roles.get(role, 0) or 0) + 1
        bucket_statuses[status] = int(bucket_statuses.get(status, 0) or 0) + 1
        bucket["latest_timestamp"] = item.get("timestamp") or bucket.get("latest_timestamp")

    buckets.update(raw_buckets)
    return buckets


def _build_summary_from_buckets(name: str, buckets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    roles: dict[str, int] = {}
    statuses: dict[str, int] = {}
    latest_timestamp = None
    entry_count = 0
    for key in sorted(buckets):
        bucket = buckets[key]
        entry_count += int(bucket.get("entry_count", 0) or 0)
        for role, count in dict(bucket.get("roles") or {}).items():
            roles[str(role)] = roles.get(str(role), 0) + int(count or 0)
        for status, count in dict(bucket.get("statuses") or {}).items():
            statuses[str(status)] = statuses.get(str(status), 0) + int(count or 0)
        latest_timestamp = bucket.get("latest_timestamp") or latest_timestamp
    return {
        "instance": name,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": _SUMMARY_RETENTION_DAYS,
        "entry_count": entry_count,
        "latest_timestamp": latest_timestamp,
        "roles": roles,
        "statuses": statuses,
        "buckets": buckets,
    }


def _prune_instance_log(name: str) -> tuple[list[dict[str, Any]], bool]:
    path = instance_log_path(name)
    if not path.exists():
        _write_summary(name, _build_summary(name, []))
        return [], False

    raw_cutoff = datetime.now(timezone.utc) - timedelta(days=_RAW_RETENTION_DAYS)
    summary_cutoff = datetime.now(timezone.utc) - timedelta(days=_SUMMARY_RETENTION_DAYS)
    kept_raw: list[dict[str, Any]] = []
    summary_entries: list[dict[str, Any]] = []
    mutated = False
    existing_summary = _load_summary(name)
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return [], False

    for line in lines:
        txt = line.strip()
        if not txt:
            mutated = True
            continue
        try:
            obj = json.loads(txt)
        except Exception:
            mutated = True
            continue
        if not isinstance(obj, dict):
            mutated = True
            continue
        ts = _parse_timestamp(obj.get("timestamp"))
        if ts is None:
            mutated = True
            continue
        if ts >= summary_cutoff:
            summary_entries.append(obj)
        if ts >= raw_cutoff:
            kept_raw.append(obj)
        else:
            mutated = True

    if mutated:
        payload = "\n".join(json.dumps(item, ensure_ascii=True) for item in kept_raw)
        path.write_text((payload + "\n") if payload else "", encoding="utf-8")

    buckets = _merge_summary_buckets(existing_summary, summary_entries, summary_cutoff)
    _write_summary(name, _build_summary_from_buckets(name, buckets))
    return kept_raw, mutated


def append_instance_log(name: str, record: dict[str, Any]) -> Path:
    path = instance_log_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    _prune_instance_log(name)
    with path.open("a", encoding="utf-8") as handle:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **record,
        }
        if "message" in payload:
            payload["message"] = _redact_text(payload.get("message", ""))
        if "response" in payload:
            payload["response"] = _redact_text(payload.get("response", ""))
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
    _prune_instance_log(name)
    return path


def read_instance_log_tail(name: str, limit: int = 50) -> list[dict[str, Any]]:
    lim = max(1, min(int(limit), 200))
    try:
        entries, _mutated = _prune_instance_log(name)
    except Exception:
        return []
    items: list[dict[str, Any]] = []
    for obj in entries[-lim:]:
        if isinstance(obj, dict):
            items.append(obj)
    return items


def read_instance_log_summary(name: str) -> dict[str, Any]:
    _prune_instance_log(name)
    path = instance_summary_path(name)
    if not path.exists():
        return _build_summary(name, [])
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _build_summary(name, [])
    return data if isinstance(data, dict) else _build_summary(name, [])


def delete_instance_log(name: str) -> None:
    for path in (instance_log_path(name), instance_summary_path(name)):
        try:
            if path.exists():
                path.unlink()
        except Exception:
            continue
