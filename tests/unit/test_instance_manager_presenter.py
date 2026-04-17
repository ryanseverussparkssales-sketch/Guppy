from src.guppy.launcher_application.instance_manager_presenter import (
    build_connector_binding_editor_state,
    build_connector_binding_feedback,
    build_governance_editor_state,
    build_instance_manager_state,
    parse_policy_lines,
    role_preset,
)


def test_instance_manager_state_builds_workspace_and_connector_targets() -> None:
    state = build_instance_manager_state(
        {
            "active_instance": "builder-collab",
            "limits": {
                "configured": 2,
                "max_configured": 5,
                "active_runtime": 1,
                "max_active_runtime": 2,
            },
            "instances": [
                {
                    "name": "guppy-primary",
                    "type": "user_instance",
                    "status": "active",
                    "mode": "auto",
                    "persona": "guppy",
                    "voice": "default",
                    "description": "Daily work",
                    "governance": {},
                    "connectors": [],
                },
                {
                    "name": "builder-collab",
                    "type": "builder_instance",
                    "status": "idle",
                    "mode": "code",
                    "persona": "guppy",
                    "voice": "default",
                    "description": "Builder review",
                    "last_message": "Review the next patch",
                    "governance": {"auth_mode": "local_only"},
                    "connectors": [{"id": "gmail"}],
                },
            ],
            "warnings": ["retained"],
        }
    )

    assert state.governance_target == "builder-collab"
    assert state.connector_target_workspace == "builder-collab"
    assert state.connector_ids == ("gmail",)
    assert "Warnings: 1" in state.summary_text
    assert "Builder collaborator" in state.collaboration_text
    assert "Review the next patch" in state.recurring_text


def test_governance_and_connector_editor_state_render_saved_policy() -> None:
    governance_state = build_governance_editor_state(
        "builder-collab",
        {
            "builder-collab": {
                "auth_mode": "local_only",
                "policy_note": "Builder stays local-first.",
                "tool_allow": ["query_instance"],
                "tool_block": ["execute_command"],
                "endpoint_allow": ["instance://*"],
                "endpoint_block": ["https://external*"],
                "capabilities": {"read": True, "write": True, "execute": False, "network": True},
            }
        },
    )
    assert governance_state.auth_mode == "local_only"
    assert "query_instance" in governance_state.tool_allow_text
    assert "caps r/w/x/n=1/1/0/1" in governance_state.status_text

    connector_state = build_connector_binding_editor_state(
        "builder-collab",
        "gmail",
        {
            "builder-collab": {
                "gmail": {
                    "auth_state": "ready",
                    "source": "token_cache",
                    "workspace_auth_mode": "local_only",
                    "binding_validation": {"message": "Workspace binding matches the current machine inventory."},
                    "history": {"last_action": "verify", "last_result": "ok"},
                    "accounts": [{"id": "sales", "label": "sales@company.com", "auth_state": "ready"}],
                    "binding": {
                        "enabled": True,
                        "account_id": "sales",
                        "provider": "",
                        "action_allow": ["compose"],
                        "action_block": ["cleanup"],
                        "endpoint_allow": ["connector://gmail*"],
                        "endpoint_block": [],
                        "note": "Builder can draft from sales.",
                    },
                }
            }
        },
    )
    assert connector_state.selected_connector_id == "gmail"
    assert connector_state.selected_account == "sales"
    assert "Builder can draft from sales." == connector_state.note
    assert "workspace auth mode=local_only" in connector_state.status_text
    assert "matches the current machine inventory" in connector_state.validation_text


def test_policy_line_and_connector_feedback_helpers_normalize_inputs() -> None:
    assert parse_policy_lines("READ\nread\nwrite\n") == ["read", "write"]

    validation_text, history_text = build_connector_binding_feedback(
        {
            "binding_validation": {"message": "Workspace is not bound yet."},
            "providers": [{"id": "hubspot", "auth_detail": "HubSpot still needs HUBSPOT_API_KEY."}],
            "accounts": [{"id": "sales", "auth_detail": "Cached browser token is present."}],
            "history": {"last_action": "verify", "last_result": "missing credentials"},
        },
        enabled=False,
        selected_provider="",
        selected_account="",
    )
    assert "Workspace binding is currently disabled." in validation_text
    assert "Choose a provider" in validation_text
    assert "Choose an available account" in validation_text
    assert "last verify" in history_text.lower()

    preset = role_preset("admin_instance")
    assert preset.name_placeholder == "ops-console"
    assert "OPS CHECK" in preset.recipe
