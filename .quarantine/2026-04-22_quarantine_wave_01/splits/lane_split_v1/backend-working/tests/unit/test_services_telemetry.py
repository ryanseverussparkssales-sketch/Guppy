from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.guppy.api import services_telemetry
from utils.db_utils import open_db


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def _read_jsonl_tail(path: Path, limit: int) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
    return [json.loads(line) for line in lines if line.strip()]


def test_query_jsonl_telemetry_filters_and_orders_events(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    recent = now.isoformat()
    older = (now - timedelta(minutes=10)).isoformat()
    stale = (now - timedelta(days=3)).isoformat()

    session_path = tmp_path / "session_events.jsonl"
    integration_path = tmp_path / "integration_events.jsonl"
    _write_jsonl(
        session_path,
        [
            {"ts": stale, "event": "chat", "level": "info", "latency_ms": 90},
            {"ts": older, "event": "chat", "level": "warning", "latency_ms": 1500},
        ],
    )
    _write_jsonl(
        integration_path,
        [
            {"timestamp": recent, "event_type": "sync", "level": "ERROR", "elapsed_ms": 2100},
        ],
    )

    events = services_telemetry.query_jsonl_telemetry(
        stream_jsonl_map={
            "session_events": session_path,
            "integration_events": integration_path,
        },
        read_jsonl_tail=_read_jsonl_tail,
        stream=None,
        event=None,
        level=None,
        since_minutes=60,
        limit=5,
    )

    assert [item["stream"] for item in events] == ["session_events", "integration_events"]
    assert [item["event"] for item in events] == ["chat", "sync"]
    assert [item["level"] for item in events] == ["warning", "error"]


def test_query_sqlite_telemetry_reads_and_parses_payloads(tmp_path: Path) -> None:
    db_path = tmp_path / "ops.sqlite3"
    schema = """
    CREATE TABLE operational_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        stream TEXT NOT NULL,
        event TEXT NOT NULL,
        level TEXT NOT NULL,
        payload_json TEXT NOT NULL
    );
    """
    with open_db(db_path, schema_sql=schema) as conn:
        conn.execute(
            "INSERT INTO operational_events (ts, stream, event, level, payload_json) VALUES (?, ?, ?, ?, ?)",
            (
                (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
                "session_events",
                "chat",
                "info",
                json.dumps({"latency_ms": 120}),
            ),
        )
        conn.execute(
            "INSERT INTO operational_events (ts, stream, event, level, payload_json) VALUES (?, ?, ?, ?, ?)",
            (
                datetime.now(timezone.utc).isoformat(),
                "integration_events",
                "sync",
                "warning",
                "not-json",
            ),
        )

    events = services_telemetry.query_sqlite_telemetry(
        db_path=db_path,
        timeout_seconds=1.0,
        busy_timeout_ms=1000,
        stream=None,
        event=None,
        level=None,
        since_minutes=60,
        limit=10,
    )

    assert [item["event"] for item in events] == ["chat", "sync"]
    assert events[0]["payload"]["latency_ms"] == 120
    assert events[1]["payload"]["parse_error"] is True


def test_build_telemetry_report_counts_streams_and_slow_requests() -> None:
    events = [
        {
            "ts": "2026-04-19T10:00:00+00:00",
            "stream": "session_events",
            "event": "chat",
            "level": "info",
            "payload": {"latency_ms": 120},
        },
        {
            "ts": "2026-04-19T10:01:00+00:00",
            "stream": "integration_events",
            "event": "sync",
            "level": "warning",
            "payload": {"elapsed_ms": 1800},
        },
    ]

    report = services_telemetry.build_telemetry_report(events, slow_request_ms=1500)

    assert report["count"] == 2
    assert report["streams"] == {"session_events": 1, "integration_events": 1}
    assert report["events"] == {"chat": 1, "sync": 1}
    assert report["latency"]["samples"] == 2
    assert report["latency"]["slow_count"] == 1
    assert report["latency"]["p95_ms"] == 120.0
