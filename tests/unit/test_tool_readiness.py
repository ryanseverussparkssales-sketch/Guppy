from src.guppy.launcher_application.tool_readiness import (
    tool_policy_fix_hint,
    tool_readiness_debug_fields,
    tool_readiness_summary,
    tool_settings_route,
)


def test_tool_policy_fix_hint_prefers_readiness_next_step() -> None:
    hint = tool_policy_fix_hint(
        "unknown_reason",
        {
            "next_step": "Verify the connector from App Mgmt.",
            "fix_target": "Settings",
        },
    )

    assert hint == "Verify the connector from Settings > Device & Accounts. Fix in: Settings."


def test_tool_readiness_summary_and_debug_fields_use_payload() -> None:
    payload = {
        "state": "pending_verify",
        "label": "Connector policy allows access, but no verify evidence has been recorded yet.",
        "summary": "Evidence: pending verify.",
        "history_summary": "No verify/connect activity has been recorded yet.",
        "result_code": "verify_required",
        "next_step": "Run verify.",
        "fix_target": "Settings",
        "auth_state": "ready",
        "auth_source": "keyring",
    }

    assert tool_readiness_summary(payload) == "Evidence: pending verify."
    assert tool_readiness_debug_fields(payload) == {
        "readiness_state": "pending_verify",
        "readiness_label": "Connector policy allows access, but no verify evidence has been recorded yet.",
        "readiness_summary": "Evidence: pending verify.",
        "readiness_history_summary": "No verify/connect activity has been recorded yet.",
        "readiness_result_code": "verify_required",
        "readiness_next_step": "Run verify.",
        "readiness_fix_target": "Settings",
        "readiness_auth_state": "ready",
        "readiness_auth_source": "keyring",
    }


def test_tool_settings_route_only_surfaces_settings_owned_connector_fixes() -> None:
    route = tool_settings_route(
        "send_email",
        "connector_host_auth_missing",
        {
            "next_step": "App Mgmt: connect Gmail on this machine, then run Verify.",
            "fix_target": "App Mgmt > Connector Inventory",
        },
    )
    workspace_only = tool_settings_route(
        "send_email",
        "connector_unbound",
        {
            "next_step": "Use Workspaces to bind Gmail.",
            "fix_target": "Workspaces > Connector Bindings",
        },
    )

    assert route == {
        "connector": "gmail",
        "tool": "send_email",
        "destination": "settings_device_accounts",
        "button_label": "OPEN DEVICE & ACCOUNTS",
        "destination_label": "Settings > Device & Accounts",
        "note": "Settings > Device & Accounts: connect Gmail on this machine, then run Verify. Open Settings > Device & Accounts > Gmail to continue.",
        "fix_target": "Settings > Device & Accounts",
    }
    assert workspace_only == {}
