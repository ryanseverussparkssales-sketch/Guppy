from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.guppy.api import snapshot_telemetry_support


def _fake_owner() -> SimpleNamespace:
    return SimpleNamespace(
        _ops_telemetry_db=Path("ops.sqlite3"),
        _SQLITE_TIMEOUT_SECONDS=10.0,
        _SQLITE_BUSY_TIMEOUT_MS=5000,
        _stream_jsonl_map={"session_events": Path("session_events.jsonl")},
        _read_jsonl_tail=lambda path, limit=50: [{"path": str(path), "limit": limit}],
        SLOW_REQUEST_MS=1500,
    )


def test_build_telemetry_query_response_uses_sqlite_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = _fake_owner()

    monkeypatch.setattr(
        snapshot_telemetry_support.services_telemetry,
        "query_sqlite_telemetry",
        lambda **kwargs: [{"backend": "sqlite", "filters": kwargs}],
    )
    monkeypatch.setattr(
        snapshot_telemetry_support.services_telemetry,
        "query_jsonl_telemetry",
        lambda **kwargs: [{"backend": "jsonl", "filters": kwargs}],
    )

    payload = snapshot_telemetry_support.build_telemetry_query_response(
        owner,
        stream=" agent_performance ",
        event=" request_complete ",
        level=" WARNING ",
        since_minutes=90,
        limit=5000,
        backend="auto",
    )

    assert payload["source"] == "sqlite"
    assert payload["count"] == 1
    assert payload["filters"] == {
        "stream": "agent_performance",
        "event": "request_complete",
        "level": "warning",
        "since_minutes": 90,
        "limit": 1000,
    }
    assert payload["events"][0]["backend"] == "sqlite"


def test_build_telemetry_query_response_falls_back_to_jsonl(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = _fake_owner()

    monkeypatch.setattr(
        snapshot_telemetry_support.services_telemetry,
        "query_sqlite_telemetry",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        snapshot_telemetry_support.services_telemetry,
        "query_jsonl_telemetry",
        lambda **kwargs: [{"backend": "jsonl", "filters": kwargs}],
    )

    payload = snapshot_telemetry_support.build_telemetry_query_response(
        owner,
        stream=None,
        event=None,
        level=None,
        since_minutes=-5,
        limit=10,
        backend="auto",
    )

    assert payload["source"] == "jsonl"
    assert payload["filters"]["since_minutes"] == 0
    assert payload["events"][0]["backend"] == "jsonl"


def test_build_telemetry_report_response_builds_window_and_report(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = _fake_owner()

    monkeypatch.setattr(
        snapshot_telemetry_support.services_telemetry,
        "query_sqlite_telemetry",
        lambda **kwargs: [{"event": "request_complete"}],
    )
    monkeypatch.setattr(
        snapshot_telemetry_support.services_telemetry,
        "query_jsonl_telemetry",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        snapshot_telemetry_support.services_telemetry,
        "build_telemetry_report",
        lambda events, slow_request_ms: {
            "count": len(events),
            "slow_request_ms": slow_request_ms,
        },
    )

    payload = snapshot_telemetry_support.build_telemetry_report_response(
        owner,
        stream="session_events",
        since_minutes=30,
        limit=9999,
        backend="sqlite",
    )

    assert payload["source"] == "sqlite"
    assert payload["window"] == {
        "stream": "session_events",
        "since_minutes": 30,
        "limit": 2000,
    }
    assert payload["report"] == {
        "count": 1,
        "slow_request_ms": 1500,
    }


def test_invalid_backend_raises_http_exception() -> None:
    owner = _fake_owner()

    with pytest.raises(HTTPException) as exc_info:
        snapshot_telemetry_support.build_telemetry_query_response(
            owner,
            stream=None,
            event=None,
            level=None,
            since_minutes=5,
            limit=10,
            backend="bogus",
        )

    assert exc_info.value.status_code == 400
