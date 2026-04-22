from __future__ import annotations

from src.guppy.workspace_governance import (
    connector_action_for_tool,
    connector_catalog,
    connector_id_for_tool,
    connector_spec,
    list_connector_ids,
    provider_environment_fields,
    provider_metadata,
    provider_spec,
    secret_field_meta,
    validate_secret_value,
)
from utils import connector_manager


def _normalized_mapping_lists(payload: dict[str, list[str] | tuple[str, ...]]) -> dict[str, list[str]]:
    return {key: list(value) for key, value in payload.items()}


def test_connector_catalog_matches_current_connector_manager_metadata() -> None:
    assert list_connector_ids() == connector_manager._CONNECTOR_IDS
    assert connector_catalog() == connector_manager._CONNECTOR_CATALOG
    assert connector_spec("crm") == connector_manager._CONNECTOR_CATALOG["crm"]


def test_provider_maps_match_current_connector_manager_metadata() -> None:
    assert _normalized_mapping_lists(provider_environment_fields("crm")) == connector_manager._CRM_PROVIDER_ENV
    assert _normalized_mapping_lists(provider_environment_fields("voip")) == connector_manager._VOIP_PROVIDER_ENV
    assert provider_metadata("crm") == connector_manager._CRM_PROVIDER_META
    assert provider_metadata("voip") == connector_manager._VOIP_PROVIDER_META
    assert provider_spec("crm", "salesforce") == connector_manager._CRM_PROVIDER_META["salesforce"]


def test_secret_field_meta_matches_connector_manager_behavior() -> None:
    assert secret_field_meta("spotify_client_secret") == connector_manager.secret_field_meta("spotify_client_secret")
    assert secret_field_meta("unknown_field") == connector_manager.secret_field_meta("unknown_field")


def test_secret_validation_matches_connector_manager_behavior() -> None:
    cases = [
        ("", ""),
        ("SALESFORCE_INSTANCE_URL", "https://example.my.salesforce.com"),
        ("SALESFORCE_INSTANCE_URL", "https://example.invalid"),
        ("TWILIO_ACCOUNT_SID", "AC123456789012"),
        ("TWILIO_ACCOUNT_SID", "short"),
        ("SPOTIFY_CLIENT_ID", "short"),
        ("YOUTUBE_API_KEY", "abc"),
        ("YOUTUBE_API_KEY", "abcdefghijk"),
    ]
    for secret_key, value in cases:
        assert validate_secret_value(secret_key, value) == connector_manager._validate_secret_value(secret_key, value)


def test_tool_mappings_match_connector_manager_behavior() -> None:
    tools = [
        "gmail_scan_inbox",
        "gmail_switch_account",
        "send_email",
        "spotify_play",
        "crm_upsert_contact",
        "voip_place_call",
        "unknown_tool",
    ]
    for tool_name in tools:
        assert connector_id_for_tool(tool_name) == connector_manager.connector_id_for_tool(tool_name)
        assert connector_action_for_tool(tool_name) == connector_manager.connector_action_for_tool(tool_name)


def test_metadata_accessors_return_defensive_copies() -> None:
    catalog = connector_catalog()
    catalog["crm"]["label"] = "Changed"
    providers = provider_metadata("crm")
    providers["hubspot"]["label"] = "Changed"

    assert connector_spec("crm")["label"] == connector_manager._CONNECTOR_CATALOG["crm"]["label"]
    assert provider_spec("crm", "hubspot")["label"] == connector_manager._CRM_PROVIDER_META["hubspot"]["label"]


def test_planned_local_adapters_have_explicit_lifecycle_metadata() -> None:
    anythingllm = connector_spec("anythingllm_local")
    huggingface = connector_spec("huggingface_local")

    assert anythingllm["availability_status"] == "planned"
    assert anythingllm["installation_status"] == "not_installed"
    assert anythingllm["default_auth_state"] == "planned"
    assert anythingllm["default_result_code"] == "planned_not_installed"
    assert anythingllm["actions_supported"] == []

    assert huggingface["availability_status"] == "planned"
    assert huggingface["installation_status"] == "not_installed"
    assert huggingface["default_auth_state"] == "planned"
    assert "not installed" in huggingface["default_auth_detail"].lower()
