from src.guppy.launcher_application.settings_device_accounts_presenter import (
    build_connector_panel_state,
    build_device_accounts_density_state,
    friendly_runtime_summary,
    resolve_field_payloads,
)
from src.guppy.launcher_application.settings_operations_presenter import build_operations_density_state


def test_friendly_runtime_summary_surfaces_packaging_and_ready_runtime() -> None:
    summary, install_text, runtime_text, next_text, diagnostics_text = friendly_runtime_summary(
        {
            "install": "Ollama CLI: found | Packager: ready | Supervisor script: ready",
            "runtime": "local ai runtime: ollama | live backend: ollama | status: ready",
            "next": "Next: build_executable.bat for packaging",
        }
    )

    assert "ready on this pc" in install_text.lower()
    assert "ollama is ready" in summary.lower()
    assert "healthy and ready" in runtime_text.lower()
    assert "models > model sourcing" in runtime_text.lower()
    assert "fresh desktop build" in next_text.lower()
    assert "repair tools" in diagnostics_text.lower()
    assert "device & accounts" in diagnostics_text.lower()
    assert "keyring-first posture" in diagnostics_text.lower()


def test_resolve_field_payloads_prefers_provider_field_details() -> None:
    payloads = resolve_field_payloads(
        {
            "providers": [
                {
                    "id": "salesforce",
                    "field_details": [
                        {"key": "A", "label": "Field A", "placeholder": "a", "masked": True},
                        {"key": "B", "label": "Field B", "placeholder": "b", "masked": False},
                    ],
                }
            ],
            "secret_fields": ["IGNORED"],
        },
        "salesforce",
    )

    assert [item["key"] for item in payloads] == ["A", "B"]


def test_build_connector_panel_state_guides_provider_selection_before_secret_entry() -> None:
    state = build_connector_panel_state(
        item={
            "id": "crm",
            "label": "CRM",
            "auth_kind": "provider_secret",
            "auth_state": "missing",
            "actions_supported": ["verify", "disconnect"],
        },
        providers=[{"id": "salesforce", "label": "Salesforce"}],
        accounts=[],
        fields=[{"key": "TOKEN", "label": "Access Token"}],
        selected_provider_id="",
    )

    assert state.current_auth_kind == "provider_secret"
    assert "pick a crm provider first" in state.step_text.lower()
    assert state.show_connect is False
    assert state.show_save is True
    assert state.verify_text == "VERIFY SETUP"


def test_build_connector_panel_state_calls_out_degraded_env_fallback_without_secret_names() -> None:
    state = build_connector_panel_state(
        item={
            "id": "crm",
            "label": "CRM",
            "auth_kind": "provider_secret",
            "auth_state": "ready",
            "actions_supported": ["verify", "disconnect"],
        },
        providers=[
            {
                "id": "salesforce",
                "label": "Salesforce",
                "storage_posture": "mixed_env",
                "auth_detail": "Salesforce still needs SALESFORCE_ACCESS_TOKEN and SALESFORCE_INSTANCE_URL.",
            }
        ],
        accounts=[],
        fields=[{"key": "TOKEN", "label": "Access Token"}],
        selected_provider_id="salesforce",
    )

    assert "keyring-first storage" in state.detail_text.lower()
    assert "degraded environment fallback" in state.detail_text.lower()
    assert "salesforce_access_token" not in state.detail_text.lower()
    assert "salesforce_instance_url" not in state.detail_text.lower()


def test_build_connector_panel_state_requires_account_pick_before_multi_account_sign_in() -> None:
    state = build_connector_panel_state(
        item={
            "id": "gmail",
            "label": "Gmail",
            "auth_kind": "oauth_file_token",
            "auth_state": "ready",
            "actions_supported": ["connect", "verify", "disconnect"],
        },
        providers=[],
        accounts=[
            {"id": "work", "label": "Work inbox"},
            {"id": "personal", "label": "Personal inbox"},
        ],
        fields=[],
        selected_provider_id="",
        selected_account_id="",
    )

    assert "2 accounts are available on this pc" in state.detail_text.lower()
    assert "choose a gmail account" in state.connect_tooltip.lower()
    assert state.connect_enabled is False
    assert state.verify_enabled is False
    assert state.disconnect_enabled is False


def test_build_connector_panel_state_adds_keyring_migration_hint_for_ready_env_fallback() -> None:
    state = build_connector_panel_state(
        item={
            "id": "crm",
            "label": "CRM",
            "auth_kind": "provider_secret",
            "auth_state": "ready",
            "actions_supported": ["verify", "disconnect"],
        },
        providers=[
            {
                "id": "salesforce",
                "label": "Salesforce",
                "storage_posture": "env_only",
            }
        ],
        accounts=[],
        fields=[{"key": "TOKEN", "label": "Access Token"}],
        selected_provider_id="salesforce",
    )

    assert "move them into keyring-first storage" in state.next_step_hint.lower()


def test_build_device_accounts_density_state_shortens_labels_for_tight_widths() -> None:
    density = build_device_accounts_density_state(860, "oauth_secret")

    assert density.desktop_action_labels == ("VERIFY", "UPDATE", "START", "RESET", "REPAIR")
    assert density.connect_text == "SIGN IN"
    assert density.save_text == "SAVE"
    assert density.verify_text == "VERIFY"
    assert density.disconnect_text == "CLEAR"


def test_build_operations_density_state_shortens_secondary_controls() -> None:
    density = build_operations_density_state(940, False)

    assert density.header_scope_visible is False
    assert density.details_button_text == "DETAILS"
    assert density.quick_fix_labels["restart_daemon"] == "RESTART"
    assert density.windows_action_labels["start_supervised_api"] == "START"
    assert density.automation_action_labels["approve_latest_staged_task"] == "APPROVE"
    assert density.workflow_load_text == "LOAD"
