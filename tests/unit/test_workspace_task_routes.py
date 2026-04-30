from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.guppy.api import routes_workspace, routes_workspace_data


def _ctx(calls: list[str] | None = None) -> SimpleNamespace:
    def require_rate_limit() -> str:
        if calls is not None:
            calls.append("rate-limit")
        return "test-user"

    return SimpleNamespace(require_rate_limit=require_rate_limit)


def _client(tmp_path: Path, monkeypatch: Any, calls: list[str] | None = None) -> TestClient:
    monkeypatch.setattr(routes_workspace, "_DB_PATH", str(tmp_path / "workspace.db"))
    monkeypatch.setattr(routes_workspace_data, "MEMORY_DB_PATH", tmp_path / "memory.db")

    app = FastAPI()
    context = _ctx(calls)
    app.include_router(routes_workspace_data.build_workspace_data_router(context))
    app.include_router(routes_workspace.build_workspace_router(context))
    return TestClient(app)


def test_ai_workspace_task_path_wins_without_crm_status(tmp_path: Path, monkeypatch: Any) -> None:
    calls: list[str] = []
    client = _client(tmp_path, monkeypatch, calls)

    created = client.post(
        "/api/workspace/tasks",
        json={"task_description": "Summarize the workspace inbox", "source": "unit"},
    )
    assert created.status_code == 201
    created_payload = created.json()
    task_id = created_payload["id"]
    assert created_payload["state"] == "queued"
    assert created_payload["task_description"] == "Summarize the workspace inbox"
    assert created_payload["events"][0]["event_type"] == "created"

    listed = client.get("/api/workspace/tasks")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [task_id]

    run = client.post(f"/api/workspace/tasks/{task_id}/run")
    assert run.status_code == 200
    assert run.json()["state"] == "complete"

    detail = client.get(f"/api/workspace/tasks/{task_id}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["state"] == "complete"
    assert detail_payload["result"] == "Baseline workspace task run complete."
    assert [step["tool_name"] for step in detail_payload["steps"]] == [
        "task_plan",
        "workspace_summary",
    ]
    assert any(event["event_type"] == "step_completed" for event in detail_payload["events"])
    assert calls


def test_crm_task_compatibility_uses_status_and_legacy_body(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    client = _client(tmp_path, monkeypatch)

    created = client.post(
        "/api/workspace/tasks",
        json={"task": "Call the lead", "due_date": "2026-05-01"},
    )
    assert created.status_code == 200
    assert created.json()["ok"] is True

    crm_tasks = client.get("/api/workspace/tasks?status=pending")
    assert crm_tasks.status_code == 200
    crm_payload = crm_tasks.json()
    assert len(crm_payload) == 1
    assert crm_payload[0]["task"] == "Call the lead"

    ai_tasks = client.get("/api/workspace/tasks")
    assert ai_tasks.status_code == 200
    assert ai_tasks.json() == []


def test_confirming_blocked_workspace_task_completes_baseline_run(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    client = _client(tmp_path, monkeypatch)

    created = client.post(
        "/api/workspace/tasks",
        json={"task_description": "delete old draft after review", "source": "unit"},
    )
    task_id = created.json()["id"]

    run = client.post(f"/api/workspace/tasks/{task_id}/run")
    assert run.status_code == 200
    assert run.json()["state"] == "blocked"

    blocked_detail = client.get(f"/api/workspace/tasks/{task_id}").json()
    blocked_step = next(step for step in blocked_detail["steps"] if step["requires_confirmation"])
    assert blocked_detail["state"] == "blocked"
    assert blocked_step["confirmation_given"] is False

    confirmed = client.post(
        f"/api/workspace/tasks/{task_id}/confirm",
        json={"step_id": blocked_step["id"]},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["state"] == "complete"

    detail = client.get(f"/api/workspace/tasks/{task_id}").json()
    assert detail["state"] == "complete"
    assert detail["steps"][-1]["confirmation_given"] is True
    assert any(event["event_type"] == "step_confirmed" for event in detail["events"])


def test_cancel_workspace_task_records_terminal_state(tmp_path: Path, monkeypatch: Any) -> None:
    client = _client(tmp_path, monkeypatch)

    created = client.post(
        "/api/workspace/tasks",
        json={"task_description": "queue then cancel this baseline task", "source": "unit"},
    )
    task_id = created.json()["id"]

    cancelled = client.post(f"/api/workspace/tasks/{task_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["state"] == "cancelled"

    detail = client.get(f"/api/workspace/tasks/{task_id}").json()
    assert detail["state"] == "cancelled"
    assert any(
        event["event_type"] == "state_changed" and event["payload"]["state"] == "cancelled"
        for event in detail["events"]
    )
