from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException

from src.guppy.api import services_telemetry


def _normalize_backend_key(backend: str) -> str:
    backend_key = (backend or "auto").strip().lower()
    if backend_key not in {"auto", "sqlite", "jsonl"}:
        raise HTTPException(status_code=400, detail="backend must be one of: auto, sqlite, jsonl")
    return backend_key


def _normalize_query_filters(
    *,
    stream: Optional[str],
    event: Optional[str],
    level: Optional[str],
    since_minutes: int,
    limit: int,
    max_limit: int,
    backend: str,
) -> dict[str, Any]:
    return {
        "stream": (stream or "").strip() or None,
        "event": (event or "").strip() or None,
        "level": (level or "").strip().lower() or None,
        "since_minutes": max(0, int(since_minutes)),
        "limit": max(1, min(int(limit), max_limit)),
        "backend": _normalize_backend_key(backend),
    }


def _load_telemetry_events(
    owner: Any,
    *,
    stream: Optional[str],
    event: Optional[str],
    level: Optional[str],
    since_minutes: int,
    limit: int,
    backend: str,
) -> tuple[str, list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    source = backend
    if backend in {"auto", "sqlite"}:
        events = services_telemetry.query_sqlite_telemetry(
            db_path=owner._ops_telemetry_db,
            timeout_seconds=owner._SQLITE_TIMEOUT_SECONDS,
            busy_timeout_ms=owner._SQLITE_BUSY_TIMEOUT_MS,
            stream=stream,
            event=event,
            level=level,
            since_minutes=since_minutes,
            limit=limit,
        )
        source = "sqlite"

    if backend == "jsonl" or (backend == "auto" and not events):
        events = services_telemetry.query_jsonl_telemetry(
            stream_jsonl_map=owner._stream_jsonl_map,
            read_jsonl_tail=owner._read_jsonl_tail,
            stream=stream,
            event=event,
            level=level,
            since_minutes=since_minutes,
            limit=limit,
        )
        source = "jsonl"

    return source, events


def build_telemetry_query_response(
    owner: Any,
    *,
    stream: Optional[str],
    event: Optional[str],
    level: Optional[str],
    since_minutes: int,
    limit: int,
    backend: str,
) -> dict[str, Any]:
    filters = _normalize_query_filters(
        stream=stream,
        event=event,
        level=level,
        since_minutes=since_minutes,
        limit=limit,
        max_limit=1000,
        backend=backend,
    )
    source, events = _load_telemetry_events(
        owner,
        stream=filters["stream"],
        event=filters["event"],
        level=filters["level"],
        since_minutes=filters["since_minutes"],
        limit=filters["limit"],
        backend=filters["backend"],
    )
    return {
        "source": source,
        "count": len(events),
        "filters": {
            "stream": filters["stream"],
            "event": filters["event"],
            "level": filters["level"],
            "since_minutes": filters["since_minutes"],
            "limit": filters["limit"],
        },
        "events": events,
    }


def build_telemetry_report_response(
    owner: Any,
    *,
    stream: Optional[str],
    since_minutes: int,
    limit: int,
    backend: str,
) -> dict[str, Any]:
    filters = _normalize_query_filters(
        stream=stream,
        event=None,
        level=None,
        since_minutes=since_minutes,
        limit=limit,
        max_limit=2000,
        backend=backend,
    )
    source, events = _load_telemetry_events(
        owner,
        stream=filters["stream"],
        event=None,
        level=None,
        since_minutes=filters["since_minutes"],
        limit=filters["limit"],
        backend=filters["backend"],
    )
    report = services_telemetry.build_telemetry_report(
        events,
        slow_request_ms=owner.SLOW_REQUEST_MS,
    )
    return {
        "source": source,
        "window": {
            "stream": filters["stream"],
            "since_minutes": filters["since_minutes"],
            "limit": filters["limit"],
        },
        "report": report,
    }
