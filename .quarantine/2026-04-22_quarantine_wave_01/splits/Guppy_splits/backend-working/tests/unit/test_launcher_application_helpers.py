from __future__ import annotations

from src.guppy.launcher_application.connector_dispatch import (
    connector_action_http_payload,
    connector_action_record,
    connector_action_status_label,
    execute_guided_connector_setup,
    missing_secret_record,
)
from src.guppy.launcher_application.windows_ops import build_windows_ops_descriptor
from src.guppy.launcher_application.workspace_state import (
    enabled_workspace_names,
    resolve_active_instance_payload,
)
from src.guppy.workspace_governance.contracts import ConnectorActionRequest, ConnectorActionResult


def test_connector_action_status_label_covers_known_and_unknown_actions() -> None:
    assert connector_action_status_label("connect") == "Opening sign-in flow..."
    assert connector_action_status_label(" reconnect ") == "Refreshing sign-in flow..."
    assert connector_action_status_label("VERIFY") == "Checking connection..."
    assert connector_action_status_label("disconnect") == "Removing saved connection..."
    assert connector_action_status_label(" sync ") == "Running sync..."
    assert connector_action_status_label("") == "Running connector action..."


def test_connector_action_http_payload_uses_request_fields_only() -> None:
    request = ConnectorActionRequest(
        connector_id="crm",
        action="connect",
        provider="salesforce",
        account_id="primary",
        secret_key="api_key",
        secret_value="shh",
        workspace_name="builder",
    )

    assert connector_action_http_payload(request) == {
        "provider": "salesforce",
        "account_id": "primary",
        "secret_key": "api_key",
        "secret_value": "shh",
    }


def test_connector_action_record_prefers_explicit_result_fields() -> None:
    request = ConnectorActionRequest(connector_id="crm", action="verify", provider="salesforce", account_id="ops")
    result = ConnectorActionResult(
        connector_id="crm",
        action="verify",
        ok=True,
        summary="Verified successfully",
        result_code="ok",
        next_step="Continue",
        fix_target="",
        event_id="evt-123",
        history={
            "last_event_id": "evt-old",
            "last_action_record": {"event_id": "evt-older", "integration_event": "history.event"},
        },
        status={"auth_state": "ready"},
    )

    record = connector_action_record(request, result, integration_event="launcher.verify")

    assert record == {
        "connector": "crm",
        "action": "verify",
        "ok": True,
        "summary": "Verified successfully",
        "next_step": "Continue",
        "result_code": "ok",
        "fix_target": "",
        "event_id": "evt-123",
        "status": {"auth_state": "ready"},
        "integration_event": "launcher.verify",
        "provider": "salesforce",
        "account_id": "ops",
    }


def test_connector_action_record_falls_back_to_history_event_and_default_summary() -> None:
    request = ConnectorActionRequest(connector_id="gmail", action="connect", provider="google", account_id="team")
    result = ConnectorActionResult(
        connector_id="gmail",
        action="connect",
        ok=False,
        summary="",
        history={
            "last_event_id": "evt-history",
            "last_action_record": {"integration_event": "connector.linked"},
        },
        status={},
    )

    record = connector_action_record(request, result)

    assert record["summary"] == "gmail connect completed"
    assert record["event_id"] == "evt-history"
    assert record["integration_event"] == "connector.linked"
    assert record["status"] == {}


def test_missing_secret_record_normalizes_identity_fields() -> None:
    record = missing_secret_record(" CRM ", " Salesforce ", " Team ")

    assert record == {
        "connector": "crm",
        "action": "connect",
        "ok": False,
        "summary": "Add an API key or account details before saving.",
        "next_step": "",
        "result_code": "missing_secret",
        "fix_target": "",
        "event_id": "",
        "status": {},
        "integration_event": "",
        "provider": "salesforce",
        "account_id": "team",
    }


def test_execute_guided_connector_setup_returns_missing_secret_record_when_secrets_absent() -> None:
    calls: list[dict[str, str]] = []

    records = execute_guided_connector_setup(
        connector_id="crm",
        provider="salesforce",
        account_id="ops",
        secrets=[],
        verify_after=True,
        performer=lambda payload: calls.append(payload) or {},
    )

    assert records == [missing_secret_record("crm", "salesforce", "ops")]
    assert calls == []


def test_execute_guided_connector_setup_short_circuits_on_failed_connect() -> None:
    calls: list[dict[str, str]] = []

    def performer(payload: dict[str, str]) -> dict[str, str | bool]:
        calls.append(payload)
        return {
            "connector": payload["connector"],
            "action": payload["action"],
            "ok": False,
            "summary": "Connect failed",
        }

    records = execute_guided_connector_setup(
        connector_id=" CRM ",
        provider=" Salesforce ",
        account_id=" Primary ",
        secrets=[{"secret_key": " api_key ", "secret_value": " secret "}],
        verify_after=True,
        performer=performer,
    )

    assert len(records) == 1
    assert records[0]["ok"] is False
    assert calls == [
        {
            "connector": "crm",
            "action": "connect",
            "provider": "salesforce",
            "account_id": "primary",
            "secret_key": "api_key",
            "secret_value": "secret",
        }
    ]


def test_execute_guided_connector_setup_appends_verify_after_successful_connects() -> None:
    calls: list[dict[str, str]] = []

    def performer(payload: dict[str, str]) -> dict[str, str | bool]:
        calls.append(payload)
        return {
            "connector": payload["connector"],
            "action": payload["action"],
            "ok": True,
            "summary": f"{payload['action']} ok",
        }

    records = execute_guided_connector_setup(
        connector_id="gmail",
        provider="google",
        account_id="team",
        secrets=[
            {"secret_key": "client_id", "secret_value": "one"},
            {"secret_key": "client_secret", "secret_value": "two"},
        ],
        verify_after=True,
        performer=performer,
    )

    assert [record["action"] for record in records] == ["connect", "connect", "verify"]
    assert calls[-1] == {
        "connector": "gmail",
        "action": "verify",
        "provider": "google",
        "account_id": "team",
        "secret_key": "",
        "secret_value": "",
    }


def test_build_windows_ops_descriptor_classifies_workflow_backed_actions() -> None:
    descriptor = build_windows_ops_descriptor("verify_runtime")

    assert descriptor.action == "verify_runtime"
    assert descriptor.execution_kind == "terminal_recipe"
    assert descriptor.is_queueable is True
    assert descriptor.request_summary == "Windows Verify queued in App Mgmt terminal"
    assert any("verify_runtime_challengers.py" in command for command in descriptor.commands)


def test_build_windows_ops_descriptor_encodes_recovery_chain_steps() -> None:
    descriptor = build_windows_ops_descriptor("repair_runtime")

    assert descriptor.execution_kind == "recovery_chain"
    assert descriptor.is_immediate is True
    assert [step.name for step in descriptor.chain_steps] == ["health_snapshot", "warmup", "audit_runtime"]
    assert [step.delay_ms for step in descriptor.chain_steps] == [0, 250, 1000]


def test_enabled_workspace_names_filters_disabled_invalid_and_duplicates() -> None:
    snapshot = {
        "instances": [
            {"name": "builder", "enabled": True},
            {"name": "builder", "enabled": True},
            {"name": "ops", "enabled": False},
            {"name": "  "},
            "not-a-dict",
            {"name": "team"},
        ]
    }

    assert enabled_workspace_names(snapshot) == ["builder", "team"]


def test_resolve_active_instance_payload_returns_matching_item_or_default() -> None:
    snapshot = {
        "instances": [
            {"name": "builder", "type": "system_instance", "label": "Builder"},
            {"name": "team", "type": "user_instance"},
        ]
    }

    assert resolve_active_instance_payload(snapshot, "builder") == {
        "name": "builder",
        "type": "system_instance",
        "label": "Builder",
    }
    assert resolve_active_instance_payload(snapshot, "missing") == {
        "name": "missing",
        "type": "user_instance",
    }
    assert resolve_active_instance_payload(None, "ops") == {
        "name": "ops",
        "type": "user_instance",
    }
