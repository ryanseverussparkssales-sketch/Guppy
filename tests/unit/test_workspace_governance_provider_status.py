from __future__ import annotations

import os
from unittest.mock import patch

from src.guppy.workspace_governance import (
    build_crm_status,
    build_provider_guidance,
    build_provider_row,
    build_voip_status,
    select_account_row,
    select_provider_row,
)


def test_provider_and_account_selectors_preserve_current_fallback_rules() -> None:
    status = {
        "providers": [
            {"id": "hubspot", "label": "HubSpot"},
            {"id": "salesforce", "label": "Salesforce"},
        ],
        "accounts": [
            {"id": "primary", "label": "Primary"},
            {"id": "backup", "label": "Backup"},
        ],
    }

    assert select_provider_row(status, " Salesforce ")["id"] == "salesforce"
    assert select_provider_row(status)["id"] == "hubspot"
    assert select_provider_row(status, "missing") == {}
    assert select_account_row(status, "backup")["id"] == "backup"
    assert select_account_row(status) == {}
    assert select_account_row({"accounts": [{"id": "primary", "label": "Primary"}]})["id"] == "primary"


def test_provider_guidance_preserves_ready_and_partial_text() -> None:
    ready = build_provider_guidance(
        {
            "label": "Salesforce",
            "auth_state": "ready",
            "verify_checks": [
                {"label": "Host", "passed": True},
                {"label": "Scope", "passed": False},
            ],
        }
    )
    partial = build_provider_guidance(
        {
            "label": "HubSpot",
            "auth_state": "partial",
            "verify_summary": "HubSpot verify found missing token readiness.",
        }
    )

    assert ready["result_code"] == "ready"
    assert ready["fix_target"] == "Workspaces > Connector Bindings"
    assert "Workspaces" in ready["next_step"]
    assert ready["verify_check_summary"] == "Host=OK, Scope=MISS"
    assert partial["result_code"] == "provider_verify_needed"
    assert "Current result: HubSpot verify found missing token readiness." in partial["next_step"]


def test_build_provider_row_merges_secret_state_and_verify_payload() -> None:
    with patch(
        "src.guppy.workspace_governance.provider_status.secret_status",
        return_value={
            "auth_state": "partial",
            "required_fields": ["SALESFORCE_ACCESS_TOKEN", "SALESFORCE_INSTANCE_URL"],
            "present_fields": ["SALESFORCE_ACCESS_TOKEN"],
            "missing_fields": ["SALESFORCE_INSTANCE_URL"],
            "field_sources": {
                "SALESFORCE_ACCESS_TOKEN": "keyring",
                "SALESFORCE_INSTANCE_URL": "none",
            },
            "source": "mixed",
        },
    ), patch(
        "src.guppy.integrations.crm_voip.verify_connector_provider",
        return_value={
            "auth_state": "ready",
            "summary": "Salesforce verify passed for contacts + opportunities.",
            "checks": [{"label": "Host", "passed": True}],
            "scope_detail": "Expected scope: contacts + opportunities against the configured Salesforce org host.",
        },
    ):
        row = build_provider_row(
            "crm",
            "salesforce",
            required_fields=["SALESFORCE_ACCESS_TOKEN", "SALESFORCE_INSTANCE_URL"],
            meta={
                "label": "Salesforce",
                "scope_label": "contacts + opportunities",
                "endpoint_prefixes": ["connector://crm/salesforce"],
                "actions": ["contact_write", "opportunity_write"],
            },
        )

    assert row["auth_state"] == "ready"
    assert row["ready"] is True
    assert row["field_details"][0]["present"] is True
    assert row["field_details"][1]["missing"] is True
    assert row["field_details"][1]["step"] == 2
    assert row["field_details"][1]["total_steps"] == 2
    assert row["next_field"]["key"] == "SALESFORCE_INSTANCE_URL"
    assert row["verify_summary"] == "Salesforce verify passed for contacts + opportunities."
    assert row["verify_check_summary"] == "Host=OK"
    assert row["result_code"] == "ready"
    assert "Workspaces" in row["next_step"]


def test_provider_family_status_uses_selected_provider_and_voip_env_default() -> None:
    crm_rows = [
        {
            "id": "hubspot",
            "label": "HubSpot",
            "ready": False,
            "auth_state": "partial",
            "auth_detail": "HubSpot still needs token.",
            "source": "env",
            "endpoint_prefixes": ["connector://crm/hubspot"],
        },
        {
            "id": "salesforce",
            "label": "Salesforce",
            "ready": True,
            "auth_state": "ready",
            "auth_detail": "Salesforce is ready for contacts + opportunities.",
            "source": "keyring",
            "endpoint_prefixes": ["connector://crm/salesforce"],
        },
        {"id": "gohighlevel", "label": "GoHighLevel", "ready": False, "auth_state": "missing", "source": "none", "endpoint_prefixes": []},
        {"id": "zoho", "label": "Zoho", "ready": False, "auth_state": "missing", "source": "none", "endpoint_prefixes": []},
    ]
    voip_rows = [
        {
            "id": "twilio",
            "label": "Twilio",
            "ready": True,
            "auth_state": "ready",
            "auth_detail": "Twilio is ready for outbound calling.",
            "source": "keyring",
            "endpoint_prefixes": ["connector://voip/twilio"],
        },
        {
            "id": "generic",
            "label": "Generic SIP",
            "ready": True,
            "auth_state": "optional",
            "auth_detail": "Generic SIP remains operator-managed.",
            "source": "none",
            "endpoint_prefixes": ["connector://voip/generic"],
        },
    ]

    with patch("src.guppy.workspace_governance.provider_status.build_provider_row", side_effect=crm_rows):
        crm_status = build_crm_status("salesforce")
    with patch.dict(os.environ, {"VOIP_PROVIDER": "generic"}), patch(
        "src.guppy.workspace_governance.provider_status.build_provider_row",
        side_effect=voip_rows,
    ):
        voip_status = build_voip_status()

    assert crm_status["auth_state"] == "ready"
    assert crm_status["source"] == "keyring"
    assert crm_status["auth_detail"] == "Salesforce provider credentials are configured."
    assert crm_status["scope_telemetry"]["endpoint_prefixes"] == [
        "connector://crm/hubspot",
        "connector://crm/salesforce",
    ]
    assert voip_status["auth_state"] == "optional"
    assert voip_status["source"] == "none"
    assert voip_status["auth_detail"] == "Generic SIP remains operator-managed."
    assert voip_status["scope_telemetry"]["endpoint_prefixes"] == [
        "connector://voip/twilio",
        "connector://voip/generic",
    ]
