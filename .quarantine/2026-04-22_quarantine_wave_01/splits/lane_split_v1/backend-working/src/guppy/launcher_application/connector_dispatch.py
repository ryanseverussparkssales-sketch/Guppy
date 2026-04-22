"""Connector action orchestration helpers for the launcher application layer."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.guppy.workspace_governance import ConnectorActionRequest, ConnectorActionResult


def connector_action_status_label(action: str) -> str:
    normalized = (action or "").strip().lower()
    return {
        "connect": "Opening sign-in flow...",
        "reconnect": "Refreshing sign-in flow...",
        "verify": "Checking connection...",
        "disconnect": "Removing saved connection...",
    }.get(normalized, f"Running {normalized or 'connector action'}...")


def connector_action_http_payload(request: ConnectorActionRequest) -> dict[str, str]:
    return {
        "provider": request.provider,
        "account_id": request.account_id,
        "secret_key": request.secret_key,
        "secret_value": request.secret_value,
    }


def connector_action_record(
    request: ConnectorActionRequest,
    result: ConnectorActionResult,
    *,
    integration_event: str = "",
) -> dict[str, Any]:
    history = result.history if isinstance(result.history, dict) else {}
    action_record = history.get("last_action_record", {}) if isinstance(history.get("last_action_record"), dict) else {}
    event_id = result.event_id or str(action_record.get("event_id", history.get("last_event_id", "")) or "").strip()
    return {
        "connector": request.connector_id,
        "action": request.action,
        "ok": result.ok,
        "summary": result.summary or f"{request.connector_id} {request.action} completed",
        "next_step": result.next_step,
        "result_code": result.result_code,
        "fix_target": result.fix_target,
        "event_id": event_id,
        "status": result.status if isinstance(result.status, dict) else {},
        "integration_event": integration_event or str(action_record.get("integration_event", "") or ""),
        "provider": request.provider,
        "account_id": request.account_id,
    }


def missing_secret_record(connector_id: str, provider: str, account_id: str) -> dict[str, Any]:
    return {
        "connector": str(connector_id or "").strip().lower(),
        "action": "connect",
        "ok": False,
        "summary": "Add an API key or account details before saving.",
        "next_step": "",
        "result_code": "missing_secret",
        "fix_target": "",
        "event_id": "",
        "status": {},
        "integration_event": "",
        "provider": str(provider or "").strip().lower(),
        "account_id": str(account_id or "").strip().lower(),
    }


def execute_guided_connector_setup(
    *,
    connector_id: str,
    provider: str,
    account_id: str,
    secrets: list[dict[str, Any]],
    verify_after: bool,
    performer: Callable[[dict[str, Any]], dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized_connector = str(connector_id or "").strip().lower()
    normalized_provider = str(provider or "").strip().lower()
    normalized_account = str(account_id or "").strip().lower()
    if not normalized_connector or not secrets:
        return [missing_secret_record(normalized_connector, normalized_provider, normalized_account)]

    records: list[dict[str, Any]] = []
    for item in secrets:
        record = performer(
            {
                "connector": normalized_connector,
                "action": "connect",
                "provider": normalized_provider,
                "account_id": normalized_account,
                "secret_key": str(item.get("secret_key", "") or "").strip(),
                "secret_value": str(item.get("secret_value", "") or "").strip(),
            }
        )
        records.append(record)
        if not bool(record.get("ok", False)):
            return records
    if verify_after and records and bool(records[-1].get("ok", False)):
        records.append(
            performer(
                {
                    "connector": normalized_connector,
                    "action": "verify",
                    "provider": normalized_provider,
                    "account_id": normalized_account,
                    "secret_key": "",
                    "secret_value": "",
                }
            )
        )
    return records
