from __future__ import annotations

from src.guppy.workspace_governance import (
    build_connector_action_request,
    build_connector_action_result,
    build_connector_inventory,
    build_workspace_governance_snapshot,
    build_workspace_summary,
    connector_id_for_tool,
    provider_environment_fields,
    provider_metadata,
    secret_field_meta,
    summarize_connector_readiness,
)


def test_workspace_summary_normalizes_status_and_label_fallbacks() -> None:
    summary = build_workspace_summary(
        {
            "name": " builder-collab ",
            "title": "Builder Collab",
            "type": "read_only_instance",
            "status": "ready",
            "note": "Operator-managed",
        }
    )

    assert summary.name == "builder-collab"
    assert summary.label == "Builder Collab"
    assert summary.instance_type == "read_only_instance"
    assert summary.status == "READY"
    assert summary.note == "Operator-managed"


def test_connector_inventory_normalizes_tuple_fields_and_fallback_label() -> None:
    inventory = build_connector_inventory(
        [
            {
                "connector": "crm",
                "auth_state": "READY",
                "binding_inherited": True,
                "action_allow": {"contact_write", "", "opportunity_write"},
                "endpoint_block": ["connector://crm/private*", "  "],
            }
        ]
    )

    assert len(inventory) == 1
    item = inventory[0]
    assert item.connector_id == "crm"
    assert item.label == "Crm"
    assert item.auth_state == "ready"
    assert item.inherited is True
    assert set(item.action_allow) == {"contact_write", "opportunity_write"}
    assert item.endpoint_block == ("connector://crm/private*",)


def test_connector_action_request_preserves_secret_key_and_normalizes_ids() -> None:
    request = build_connector_action_request(
        " CRM ",
        " VERIFY ",
        provider=" Salesforce ",
        account_id=" Primary ",
        secret_key="SALESFORCE_ACCESS_TOKEN",
        secret_value=" token-value ",
        workspace_name=" ops-workspace ",
    )

    assert request.connector_id == "crm"
    assert request.action == "verify"
    assert request.provider == "salesforce"
    assert request.account_id == "primary"
    assert request.secret_key == "SALESFORCE_ACCESS_TOKEN"
    assert request.secret_value == "token-value"
    assert request.workspace_name == "ops-workspace"
    assert request.to_payload()["secret_key"] == "SALESFORCE_ACCESS_TOKEN"


def test_connector_action_result_uses_status_id_fallback_and_defaults() -> None:
    result = build_connector_action_result(
        {
            "action": "verify",
            "ok": True,
            "summary": "CRM verify passed.",
            "status": {"id": "crm", "auth_state": "READY"},
            "history": {"attempts": 2},
        }
    )

    assert result.connector_id == "crm"
    assert result.action == "verify"
    assert result.ok is True
    assert result.auth_state == "ready"
    assert result.history == {"attempts": 2}


def test_summarize_connector_readiness_covers_ready_missing_and_unknown() -> None:
    ready_state = summarize_connector_readiness(
        build_connector_inventory(
            [
                {"id": "gmail", "auth_state": "ready"},
                {"id": "calendar", "auth_state": "ready"},
            ]
        )
    )
    missing_state = summarize_connector_readiness(
        build_connector_inventory(
            [
                {"id": "crm", "auth_state": "missing"},
                {"id": "voip", "auth_state": "missing"},
            ]
        )
    )
    unknown_state = summarize_connector_readiness(
        build_connector_inventory(
            [
                {"id": "spotify", "auth_state": "error"},
            ]
        )
    )

    assert ready_state == ("READY", "2/2 ready, 0 partial, 0 missing.")
    assert missing_state == ("MISSING", "0/2 ready, 0 partial, 2 missing.")
    assert unknown_state == ("UNKNOWN", "0/1 ready, 0 partial, 0 missing.")


def test_workspace_governance_snapshot_uses_workspace_auth_mode_and_note_fallbacks() -> None:
    snapshot = build_workspace_governance_snapshot(
        {
            "name": "ops-workspace",
            "status": "ready",
            "auth_mode": "workspace",
            "note": "Workspace note",
        },
        connectors_payload=[{"id": "gmail", "auth_state": "ready"}],
        governance_payload={
            "tool_allow": {"send_email", "", "draft_email"},
            "endpoint_allow": ["connector://gmail*", " "],
        },
    )

    assert snapshot.workspace.name == "ops-workspace"
    assert snapshot.auth_mode == "workspace"
    assert snapshot.policy_state == "ready"
    assert set(snapshot.tool_allow) == {"send_email", "draft_email"}
    assert snapshot.endpoint_allow == ("connector://gmail*",)
    assert snapshot.note == "Workspace note"
    assert snapshot.readiness_state == "READY"


def test_provider_and_secret_helpers_return_defensive_fallbacks() -> None:
    provider_fields = provider_environment_fields("unknown")
    provider_info = provider_metadata("crm")
    provider_info["hubspot"]["label"] = "Changed"
    secret_meta = secret_field_meta("custom_secret")

    assert provider_fields == {}
    assert provider_metadata("crm")["hubspot"]["label"] == "HubSpot"
    assert secret_meta == {
        "key": "CUSTOM_SECRET",
        "label": "Custom Secret",
        "placeholder": "",
        "input_hint": "",
        "validation_hint": "",
        "kind": "token",
        "masked": True,
    }


def test_connector_id_for_tool_keeps_gmail_prefix_shortcut() -> None:
    assert connector_id_for_tool("gmail_archive_thread") == "gmail"
    assert connector_id_for_tool("crm_upsert_contact") == "crm"
    assert connector_id_for_tool("unknown_tool") == ""
