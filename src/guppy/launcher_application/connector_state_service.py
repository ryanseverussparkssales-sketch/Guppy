"""Connector runtime state and integration-event helpers."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {"version": 1, "connectors": {}}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "connectors": {}}


def save_state(runtime_dir: Path, state_path: Path, payload: dict[str, Any]) -> None:
    runtime_dir.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def integration_level(event_type: str, payload: dict[str, Any]) -> str:
    normalized_event = str(event_type or "").strip().lower()
    reason_code = str(payload.get("reason_code", "") or "").strip().lower()
    if payload.get("ok") is False or "error" in normalized_event or "failed" in normalized_event:
        return "error"
    if "policy_denied" in normalized_event or reason_code:
        return "warning"
    return "info"


def new_event_id(prefix: str) -> str:
    normalized = str(prefix or "connector").strip().lower() or "connector"
    return f"{normalized}-{uuid4().hex[:10]}"


def log_integration_event(
    runtime_dir: Path,
    events_path: Path,
    event_type: str,
    payload: dict[str, Any],
    *,
    level: str | None = None,
    log_operational_event_fn: Callable[[str, str, dict[str, Any], str], None] | None = None,
) -> None:
    runtime_dir.mkdir(parents=True, exist_ok=True)
    ts = now_iso()
    resolved_level = str(level or integration_level(event_type, payload)).strip().lower() or "info"
    record = {
        "timestamp": ts,
        "ts": ts,
        "event_type": event_type,
        "event": event_type,
        "level": resolved_level,
        "payload": payload,
    }
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")
    if log_operational_event_fn is not None:
        log_operational_event_fn("integration_events", str(event_type or "event"), payload, resolved_level)


def record_auth_state(
    payload: dict[str, Any],
    *,
    load_state_fn: Callable[[], dict[str, Any]],
    save_state_fn: Callable[[dict[str, Any]], None],
    log_event_fn: Callable[[str, dict[str, Any]], None],
    now_iso_fn: Callable[[], str],
) -> None:
    connector_id = str(payload.get("id", "")).strip().lower()
    if not connector_id:
        return
    state = load_state_fn()
    connectors = state.get("connectors", {}) if isinstance(state.get("connectors"), dict) else {}
    previous = connectors.get(connector_id, {}) if isinstance(connectors.get(connector_id), dict) else {}
    next_state = str(payload.get("auth_state", "missing"))
    if str(previous.get("auth_state", "")) != next_state:
        log_event_fn(
            "connector.auth_state_changed",
            {
                "connector": connector_id,
                "from": str(previous.get("auth_state", "unknown")),
                "to": next_state,
                "detail": str(payload.get("auth_detail", "")),
            },
        )
    connectors[connector_id] = {
        **previous,
        "auth_state": next_state,
        "auth_detail": str(payload.get("auth_detail", "")),
        "source": str(payload.get("source", "none")),
        "last_seen_at": now_iso_fn(),
    }
    state["connectors"] = connectors
    save_state_fn(state)


def log_connector_policy_denial(
    connector_id: str,
    workspace_name: str,
    reason_code: str,
    reason: str,
    *,
    recent_denials: dict[str, float],
    dedupe_ttl_s: float,
    log_event_fn: Callable[[str, dict[str, Any]], None],
    monotonic_fn: Callable[[], float] = time.monotonic,
) -> None:
    signature = "|".join(
        [
            str(connector_id or "").strip().lower(),
            str(workspace_name or "").strip().lower(),
            str(reason_code or "").strip().lower(),
            str(reason or "").strip(),
        ]
    )
    now = monotonic_fn()
    previous = recent_denials.get(signature, 0.0)
    if previous and (now - previous) < dedupe_ttl_s:
        return
    recent_denials[signature] = now
    log_event_fn(
        "connector.policy_denied",
        {
            "connector": str(connector_id or "").strip().lower(),
            "workspace": str(workspace_name or "").strip(),
            "reason_code": str(reason_code or "").strip(),
            "reason": str(reason or "").strip(),
        },
    )
