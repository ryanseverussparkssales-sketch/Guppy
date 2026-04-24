from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from src.guppy.workspace_governance import (
    auth_mode_label,
    build_connector_action_request,
    build_connector_action_result,
    build_connector_inventory,
    build_workspace_governance_snapshot,
    build_workspace_summary,
    check_instance_tool_permission,
    connector_id_for_tool,
    instance_policy_backend_available,
    provider_environment_fields,
    provider_metadata,
    required_capability_for_tool,
    resolve_instance_permissions,
    secret_field_meta,
    set_instance_tool_permission_policy,
    summarize_connector_readiness,
)
from src.guppy.workspace_governance import access_policy as access_policy_module


ROOT = Path(__file__).resolve().parents[2]


def _repo_tmp_dir(label: str) -> Path:
    path = ROOT / ".tmp" / "pytest-local" / f"{label}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


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
    assert item.label == "CRM"
    assert item.auth_state == "ready"
    assert item.inherited is True
    assert set(item.action_allow) == {"contact_write", "opportunity_write"}
    assert item.endpoint_block == ("connector://crm/private*",)


def test_connector_inventory_synthesizes_planned_adapter_lifecycle_from_catalog() -> None:
    inventory = build_connector_inventory(
        [
            {
                "id": "anythingllm_local",
                "auth_state": "missing",
            }
        ]
    )

    item = inventory[0]
    assert item.connector_id == "anythingllm_local"
    assert item.label == "AnythingLLM"
    assert item.auth_state == "planned"
    assert item.auth_kind == "planned_adapter"
    assert item.supported_actions == ()
    assert item.note.startswith("Planned adapter lane reserved")
    assert item.raw["installation_status"] == "not_installed"
    assert item.raw["result_code"] == "planned_not_installed"
    assert "not installed" in item.raw["auth_detail"].lower()
    assert "future build" in item.raw["next_step"].lower()


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


def test_summarize_connector_readiness_reports_planned_rows_explicitly() -> None:
    planned_state = summarize_connector_readiness(
        build_connector_inventory(
            [
                {"id": "anythingllm_local", "auth_state": "missing"},
                {"id": "huggingface_local", "auth_state": "unknown"},
            ]
        )
    )

    assert planned_state == ("PLANNED", "0/2 ready, 0 partial, 0 missing, 2 planned.")


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


def test_workspace_governance_exports_policy_helpers() -> None:
    assert auth_mode_label("runtime_default") == "runtime default"
    assert required_capability_for_tool("read_file") == "read"
    assert isinstance(instance_policy_backend_available(), bool)
    allowed, reason, details = check_instance_tool_permission("read_file", instance_type="user_instance")
    assert isinstance(allowed, bool)
    assert isinstance(reason, str)
    assert isinstance(details, dict)
    assert isinstance(resolve_instance_permissions(instance_type="user_instance"), dict)
    tmp_dir = _repo_tmp_dir("workspace-governance")
    try:
        config_path = tmp_dir / "tool_permissions.json"
        saved_path = set_instance_tool_permission_policy("builder-collab", {"read": True}, config_path=config_path)
        assert saved_path == config_path
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_access_policy_fallback_is_fail_closed() -> None:
    allowed, reason, details = access_policy_module._fallback_check_instance_tool_permission(
        "read_file",
        instance_name="builder-collab",
        instance_type="builder_instance",
    )
    assert allowed is False
    assert "backend unavailable" in reason
    assert details["_policy_reason_code"] == "instance_policy_backend_unavailable"
    assert details["read"] is False
    assert details["write"] is False
    assert details["execute"] is False
    assert details["network"] is False
