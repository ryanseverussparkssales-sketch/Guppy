from src.guppy.launcher_application.instance_manager_presenter import (
    build_connector_binding_save_request,
    build_workspace_create_copy,
    build_workspace_create_form_state,
    build_workspace_create_request,
    build_workspace_activity_log_text,
    build_connector_binding_editor_state,
    build_connector_binding_feedback,
    build_workspace_editors_state,
    build_governance_editor_state,
    build_governance_save_request,
    build_instance_manager_state,
    build_save_affordance_state,
    build_section_toggle_state,
    parse_policy_lines,
    role_preset,
    workspace_onboarding_ready_message,
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
                    "continuity": {
                        "continuity_summary": "Continuity: 2 recent sessions are saved here. Last saved thread: Review the next patch",
                    },
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
    assert "Continuity: 2 recent sessions are saved here." in state.recurring_text


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


def test_build_workspace_create_copy_exposes_role_aware_workspace_framing() -> None:
    copy = build_workspace_create_copy("builder_instance")

    assert copy.workspace_type == "builder_instance"
    assert copy.role_label == "Builder collaborator"
    assert copy.name_placeholder == "builder-collab"
    assert copy.default_mode == "code"
    assert "builder workspace defaults" in copy.preset_summary.lower()
    assert "PLAN NEXT PASS" in copy.first_run_recipe
    assert "release-review" in copy.example_names


def test_workspace_request_builders_shape_payloads_and_validation() -> None:
    create_request = build_workspace_create_request(
        name=" builder-collab ",
        description="Review loops",
        mode="code",
        persona="guppy",
        voice="default",
        workspace_type="builder_instance",
        enabled=True,
    )
    assert create_request.as_payload()["name"] == "builder-collab"
    assert create_request.as_payload()["type"] == "builder_instance"

    governance_request, governance_error = build_governance_save_request(
        target="builder-collab",
        policy={"instance_type": "builder_instance"},
        auth_mode="local_only",
        tool_allow_text="query_instance\nwrite_file",
        tool_block_text="execute_command",
        endpoint_allow_text="instance://*",
        endpoint_block_text="https://external*",
        policy_note="Builder stays local-first.",
    )
    assert governance_error == ""
    assert governance_request is not None
    assert governance_request.tool_allow == ("query_instance", "write_file")

    connector_request, connector_error = build_connector_binding_save_request(
        workspace_name="builder-collab",
        connector_id="gmail",
        enabled=True,
        account_id="sales",
        provider="",
        action_allow_text="compose\nsend",
        action_block_text="cleanup",
        endpoint_allow_text="connector://gmail*",
        endpoint_block_text="",
        note="Builder can draft from sales.",
    )
    assert connector_error == ""
    assert connector_request is not None
    assert connector_request.action_allow == ("compose", "send")

    missing_governance, missing_governance_error = build_governance_save_request(
        target="",
        policy=None,
        auth_mode="runtime_default",
        tool_allow_text="",
        tool_block_text="",
        endpoint_allow_text="",
        endpoint_block_text="",
        policy_note="",
    )
    assert missing_governance is None
    assert "Choose a workspace" in missing_governance_error

    missing_connector, missing_connector_error = build_connector_binding_save_request(
        workspace_name="",
        connector_id="",
        enabled=False,
        account_id="",
        provider="",
        action_allow_text="",
        action_block_text="",
        endpoint_allow_text="",
        endpoint_block_text="",
        note="",
    )
    assert missing_connector is None
    assert "Choose a workspace and connector" in missing_connector_error


def test_workspace_form_and_editor_helpers_preserve_targeted_role_context() -> None:
    previous_copy = build_workspace_create_copy("builder_instance")
    form_state = build_workspace_create_form_state(
        workspace_type="read_only_instance",
        current_description=previous_copy.description_placeholder,
        current_mode=previous_copy.default_mode,
        previous_copy=previous_copy,
    )
    assert form_state.copy.role_label == "Read-only reference"
    assert form_state.description_value == "Source checking, comparisons, and safe reference work"
    assert form_state.mode_value == "local"

    instance_state = build_instance_manager_state(
        {
            "active_instance": "ops-console",
            "instances": [
                {
                    "name": "reference-desk",
                    "type": "read_only_instance",
                    "status": "idle",
                    "mode": "local",
                    "persona": "guppy",
                    "voice": "default",
                    "description": "Reference review",
                    "governance": {
                        "auth_mode": "local_only",
                        "policy_note": "Reference stays read-mostly.",
                    },
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
                    "governance": {},
                    "connectors": [{"id": "gmail"}],
                },
                {
                    "name": "ops-console",
                    "type": "admin_instance",
                    "status": "running",
                    "mode": "auto",
                    "persona": "guppy",
                    "voice": "default",
                    "description": "Diagnostics and recovery",
                    "governance": {},
                    "connectors": [],
                },
            ],
        },
        previous_governance_workspace="reference-desk",
        previous_connector_workspace="builder-collab",
        previous_connector_id="gmail",
    )
    editors_state = build_workspace_editors_state(instance_state)

    assert editors_state.governance_workspace.selected_value == "reference-desk"
    assert editors_state.connector_workspace.selected_value == "builder-collab"
    assert editors_state.connector_id.selected_value == "gmail"
    assert "Reference stays read-mostly." == editors_state.governance_editor.policy_note


def test_save_affordance_and_activity_log_helpers_keep_workspace_flows_clear() -> None:
    blocked = build_save_affordance_state(
        candidate_name="new-space",
        known_names={"guppy-primary", "builder-collab"},
        configured=5,
        max_configured=5,
    )
    allowed = build_save_affordance_state(
        candidate_name="builder-collab",
        known_names={"guppy-primary", "builder-collab"},
        configured=5,
        max_configured=5,
    )

    assert not blocked.enabled
    assert "Workspace limit reached (5 / 5)." in blocked.warning_text
    assert allowed.enabled
    assert allowed.warning_text == ""

    log_text = build_workspace_activity_log_text(
        "builder-collab",
        [
            {"timestamp": "2026-04-17T12:00:00+00:00", "role": "assistant", "message": "Ready for the next pass."},
            {"timestamp": "2026-04-17T12:01:00+00:00", "role": "system", "response": "Connector verify passed."},
        ],
    )
    empty_log_text = build_workspace_activity_log_text("reference-desk", [])

    assert "ASSISTANT: Ready for the next pass." in log_text
    assert "SYSTEM: Connector verify passed." in log_text
    assert empty_log_text == "No recent conversation or ops activity yet for workspace reference-desk"


def test_workspace_toggle_and_onboarding_helpers_keep_role_language_consistent() -> None:
    governance_state = build_section_toggle_state(True, show_label="SHOW ACCESS RULES", hide_label="HIDE ACCESS RULES")
    connector_state = build_section_toggle_state(False, show_label="SHOW CONNECTOR RULES", hide_label="HIDE CONNECTOR RULES")

    assert governance_state.button_label == "HIDE ACCESS RULES"
    assert connector_state.button_label == "SHOW CONNECTOR RULES"
    assert "Builder collaborator workspace builder-collab is ready." in workspace_onboarding_ready_message(
        "builder-collab",
        "builder_instance",
    )
