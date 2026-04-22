from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.guppy.api import snapshot_route_support


class _FakeLock:
    def __init__(self, *, acquirable: bool = True) -> None:
        self.acquirable = acquirable
        self.released = False

    def acquire(self, blocking: bool = False) -> bool:
        del blocking
        return self.acquirable

    def release(self) -> None:
        self.released = True


def _query_owner(*, acquirable: bool = True) -> SimpleNamespace:
    saved: dict[str, object] = {"state": None, "logs": []}
    config = {
        "instances": [
            {
                "name": "alpha",
                "mode": "auto",
                "persona": "guide",
                "type": "user_instance",
            }
        ]
    }
    state = {"instances": {}}

    async def run_blocking(func, *args, **kwargs):
        timeout_seconds = kwargs.pop("timeout_seconds", None)
        del timeout_seconds
        return func(*args, **kwargs)

    def call_unified_inference(*args, **kwargs):
        del args, kwargs
        return "response text"

    def append_instance_log(name: str, payload: dict[str, object]) -> None:
        saved["logs"].append((name, payload))

    return SimpleNamespace(
        GUPPY_CORE_AVAILABLE=True,
        _load_normalized_instance_bundle=lambda *, persist_repairs=False: (config, state, [], []),
        _instance_names=lambda cfg: [item["name"] for item in cfg["instances"]],
        _get_instance_entry=lambda cfg, name: next((item for item in cfg["instances"] if item["name"] == name), None),
        check_instance_tool_permission=lambda *args, **kwargs: (True, "", {}),
        _instance_query_lock=_FakeLock(acquirable=acquirable),
        _build_chat_system_prompt=lambda **kwargs: f"prompt:{kwargs['session_id']}",
        _run_blocking=run_blocking,
        _call_unified_inference=call_unified_inference,
        _save_instance_state=lambda new_state: saved.__setitem__("state", new_state),
        _INSTANCE_LOGGER_AVAILABLE=True,
        append_instance_log=append_instance_log,
        _saved=saved,
    )


def test_query_instance_response_updates_state_and_logs() -> None:
    owner = _query_owner()
    request = SimpleNamespace(message="hello there", source_instance="launcher", timeout_s=3.0)

    payload = asyncio.run(snapshot_route_support.query_instance_response(owner, "alpha", request))

    assert payload["status"] == "ok"
    assert payload["target_instance"] == "alpha"
    assert payload["response"] == "response text"
    assert payload["model"] == "auto"
    assert payload["tokens_used"] >= 1
    assert owner._saved["state"]["instances"]["alpha"]["last_message"] == "hello there"
    assert owner._instance_query_lock.released is True
    assert len(owner._saved["logs"]) == 2


def test_recent_logs_response_clamps_limit() -> None:
    owner = SimpleNamespace(
        _runtime_dir=Path("runtime"),
        tail_session_events=lambda limit=50: [{"stream": "session", "limit": limit}],
        _read_jsonl_tail=lambda path, limit=50: [{"path": str(path), "limit": limit}],
    )

    payload = snapshot_route_support.recent_logs_response(owner, limit=999)

    assert payload["session_events"][0]["limit"] == 300
    assert payload["agent_performance"][0]["limit"] == 300
    assert payload["integration_events"][0]["limit"] == 300


def test_repair_token_refresh_response_prefers_in_memory_token() -> None:
    events: list[tuple[str, str, dict[str, object]]] = []
    owner = SimpleNamespace(
        _REPAIR_TOKEN="in-memory-token",
        _SECRET_STORE_AVAILABLE=False,
        _secret_store=None,
        _REPAIR_TOKEN_FILE=Path("missing.txt"),
        log_session_event=lambda scope, event, **kwargs: events.append((scope, event, kwargs)),
    )

    payload = snapshot_route_support.repair_token_refresh_response(owner, "127.0.0.1")

    assert payload == {"repair_token": "in-memory-token"}
    assert events[-1][1] == "repair_token_refresh"
    assert events[-1][2]["has_token"] is True


def test_repair_token_refresh_response_rejects_non_localhost() -> None:
    owner = SimpleNamespace(
        _REPAIR_TOKEN="",
        _SECRET_STORE_AVAILABLE=False,
        _secret_store=None,
        _REPAIR_TOKEN_FILE=Path("missing.txt"),
        log_session_event=lambda *args, **kwargs: None,
    )

    with pytest.raises(HTTPException) as exc_info:
        snapshot_route_support.repair_token_refresh_response(owner, "10.0.0.42")

    assert exc_info.value.status_code == 403


def test_revenue_dashboard_response_requires_memory_support() -> None:
    owner = SimpleNamespace(GUPPY_MEMORY_AVAILABLE=False, memory=None, logger=SimpleNamespace(error=lambda *args, **kwargs: None))

    with pytest.raises(HTTPException) as exc_info:
        snapshot_route_support.revenue_dashboard_response(owner)

    assert exc_info.value.status_code == 503
