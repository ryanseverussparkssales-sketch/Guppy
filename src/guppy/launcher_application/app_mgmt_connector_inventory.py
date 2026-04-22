"""Connector inventory presenter state and validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ConnectorSelectorOption:
    label: str
    value: str


@dataclass(frozen=True, slots=True)
class ConnectorActionButtonState:
    text: str
    visible: bool
    enabled: bool
    tooltip: str


@dataclass(frozen=True, slots=True)
class ConnectorInventoryState:
    provider_options: tuple[ConnectorSelectorOption, ...]
    selected_provider: str
    account_options: tuple[ConnectorSelectorOption, ...]
    selected_account: str
    secret_field_options: tuple[ConnectorSelectorOption, ...]
    selected_secret_key: str
    state_text: str
    auth_text: str
    detail_text: str
    validation_text: str
    scope_text: str
    setup_text: str
    next_step_text: str
    history_text: str
    recent_text: str
    secret_text: str
    secret_placeholder: str
    secret_masked: bool
    button_states: dict[str, ConnectorActionButtonState]


def _clean_guidance_text(text: str) -> str:
    cleaned = str(text or "").strip()
    replacements = (
        ("App Mgmt:", ""),
        ("Workspaces >", ""),
        ("App Mgmt >", ""),
    )
    for old, new in replacements:
        cleaned = cleaned.replace(old, new)
    return " ".join(cleaned.split())


def _service_purpose(connector_id: str) -> str:
    return {
        "gmail": "Email",
        "calendar": "Calendar",
        "spotify": "Music",
        "youtube": "Video tools",
        "crm": "Customer records",
        "voip": "Calling",
    }.get(str(connector_id or "").strip().lower(), "Connected service")


def _friendly_auth_state(auth_state: str) -> str:
    normalized = str(auth_state or "").strip().lower()
    return {
        "ready": "Connected",
        "optional": "Optional",
        "partial": "Almost ready",
        "missing": "Needs setup",
    }.get(normalized, "Needs setup")


def _selector_label(item: Mapping[str, object], *, fallback: str) -> str:
    label = str(item.get("label", item.get("id", fallback)) or fallback).strip() or fallback
    auth_state = str(item.get("auth_state", "") or "").strip().upper()
    if auth_state:
        label += f" [{auth_state}]"
    return label


def _history_line(history: Mapping[str, object]) -> str:
    last_action = str(history.get("last_action", "") or "").strip()
    last_action_at = str(history.get("last_action_at", "") or "").strip()
    last_result = str(history.get("last_result", "") or "").strip()
    last_event_id = str(history.get("last_event_id", "") or "").strip()
    if not last_action:
        return "History: no connector action has been recorded yet."
    summary = f"History: last {last_action}"
    if last_action_at:
        summary += f" @ {last_action_at}"
    if last_result:
        summary += f" | {last_result}"
    if last_event_id:
        summary += f" | Ref: {last_event_id}"
    return summary


def _recent_history_line(history: Mapping[str, object]) -> str:
    recent_summary = str(history.get("recent_summary", "") or "").strip()
    if recent_summary:
        return "Recent attempts: " + recent_summary
    timeline = [item for item in history.get("timeline", []) if isinstance(item, dict)] if isinstance(history.get("timeline"), list) else []
    if not timeline:
        return "Recent attempts: none recorded yet."
    rendered: list[str] = []
    for item in timeline[-3:]:
        action = str(item.get("action", "action") or "action").strip()
        result = str(item.get("result", item.get("status", "")) or "").strip()
        when = str(item.get("timestamp", item.get("at", "")) or "").strip()
        bit = action
        if result:
            bit += f"={result}"
        if when:
            bit += f" @ {when}"
        rendered.append(bit)
    return "Recent attempts: " + " | ".join(rendered)


def _provider_field_details(payload: Mapping[str, object]) -> list[dict[str, object]]:
    field_details = payload.get("field_details", [])
    return [row for row in field_details if isinstance(row, dict)] if isinstance(field_details, list) else []


def _provider_secret_fields(payload: Mapping[str, object], item: Mapping[str, object]) -> list[str]:
    provider_field_details = _provider_field_details(payload)
    fields = [
        str(row.get("key", "")).strip()
        for row in provider_field_details
        if str(row.get("key", "")).strip()
    ]
    if fields:
        return fields
    required_fields = payload.get("required_fields", [])
    if isinstance(required_fields, list):
        fields = [str(row).strip() for row in required_fields if str(row).strip()]
    if fields:
        return fields
    secret_fields = item.get("secret_fields", [])
    return [str(row).strip() for row in secret_fields if str(row).strip()] if isinstance(secret_fields, list) else []


def build_connector_inventory_state(
    item: Mapping[str, object] | None,
    *,
    previous_provider: str = "",
    previous_account: str = "",
    previous_secret_key: str = "",
    fallback_connector_id: str = "",
) -> ConnectorInventoryState:
    payload = item if isinstance(item, Mapping) else {}
    providers = [row for row in payload.get("providers", []) if isinstance(row, dict)] if isinstance(payload.get("providers"), list) else []
    accounts = [row for row in payload.get("accounts", []) if isinstance(payload.get("accounts"), list) and isinstance(row, dict)] if isinstance(payload.get("accounts"), list) else []
    history = payload.get("history", {}) if isinstance(payload.get("history"), Mapping) else {}
    scope = payload.get("scope_telemetry", {}) if isinstance(payload.get("scope_telemetry"), Mapping) else {}

    selected_provider_payload = next(
        (row for row in providers if str(row.get("id", "")).strip().lower() == str(previous_provider).strip().lower()),
        providers[0] if providers else {},
    )
    selected_account_payload = next(
        (row for row in accounts if str(row.get("id", "")).strip().lower() == str(previous_account).strip().lower()),
        accounts[0] if accounts else {},
    )
    provider_field_details = _provider_field_details(selected_provider_payload)
    secret_fields = _provider_secret_fields(selected_provider_payload, payload)
    default_secret_key = str(selected_provider_payload.get("next_field", {}).get("key", "") or "").strip() if isinstance(selected_provider_payload, Mapping) else ""
    if default_secret_key and default_secret_key in secret_fields:
        selected_secret_key = default_secret_key
    elif previous_secret_key and previous_secret_key in secret_fields:
        selected_secret_key = previous_secret_key
    else:
        selected_secret_key = secret_fields[0] if secret_fields else ""

    selected_field_detail = next(
        (row for row in provider_field_details if str(row.get("key", "")).strip() == selected_secret_key),
        {},
    )
    selected_provider = str(selected_provider_payload.get("id", "") or "").strip()
    selected_account = str(selected_account_payload.get("id", "") or "").strip()

    connector_id = str(payload.get("id", fallback_connector_id) or fallback_connector_id).strip().lower()
    auth_kind = str(payload.get("auth_kind", "unknown") or "unknown")
    auth_state = str(payload.get("auth_state", "unknown") or "unknown").upper()
    detail = str(payload.get("auth_detail", "") or "").strip()
    connector_label = str(payload.get("label", connector_id or "Service") or connector_id or "Service")
    purpose = _service_purpose(connector_id)

    validation_bits: list[str] = []
    if providers:
        if selected_provider_payload:
            validation_bits.append(str(selected_provider_payload.get("auth_detail", "") or "").strip())
            setup_summary = str(selected_provider_payload.get("setup_summary", "") or "").strip()
            if setup_summary:
                validation_bits.append(setup_summary)
            verify_summary = str(selected_provider_payload.get("verify_summary", "") or "").strip()
            if verify_summary:
                validation_bits.append(verify_summary)
            verify_check_summary = str(selected_provider_payload.get("verify_check_summary", "") or "").strip()
            if verify_check_summary:
                validation_bits.append("Checks: " + verify_check_summary)
        else:
            validation_bits.append("Choose a provider before you save or verify this connector.")
    if accounts:
        if selected_account_payload:
            validation_bits.append(str(selected_account_payload.get("auth_detail", "") or "").strip())
        else:
            validation_bits.append("Choose which account you want to use on this PC.")
    if not validation_bits:
        validation_bits.append(detail or "This service is ready to review.")

    endpoint_prefixes = [str(entry).strip() for entry in scope.get("endpoint_prefixes", []) if str(entry).strip()] if isinstance(scope.get("endpoint_prefixes"), list) else []
    scope_summary = str(scope.get("summary", "") or "").strip()
    selected_scope = str(selected_provider_payload.get("scope_label", "") or selected_account_payload.get("label", "") or "").strip()
    rendered_scope = selected_scope or scope_summary or "No explicit scope guidance is available."
    provider_scope_detail = str(selected_provider_payload.get("scope_detail", "") or "").strip()
    if provider_scope_detail:
        rendered_scope += f" | {provider_scope_detail}"
    if endpoint_prefixes:
        rendered_scope += f" | {len(endpoint_prefixes[:3])} machine actions available"

    if provider_field_details:
        present_count = len([row for row in provider_field_details if bool(row.get("present", False))])
        total_count = len(provider_field_details)
        next_field = selected_provider_payload.get("next_field", {}) if isinstance(selected_provider_payload, Mapping) else {}
        next_label = str(next_field.get("label", next_field.get("key", "")) or next_field.get("key", "")).strip()
        next_hint = str(next_field.get("validation_hint", "") or next_field.get("input_hint", "") or "").strip()
        setup_text = f"Saved details: {present_count}/{total_count} ready"
        if next_label and present_count < total_count:
            setup_text += f" | Next: add {next_label}"
        if next_hint:
            setup_text += f" | {next_hint}"
    elif secret_fields:
        setup_text = "Saved details: choose the detail you want to save, then test the connection."
    else:
        setup_text = "Saved details: this service mostly uses account selection or browser sign-in."

    next_step = str(selected_provider_payload.get("next_step", "") or payload.get("next_step", "") or "").strip()
    fix_target = str(selected_provider_payload.get("fix_target", "") or payload.get("fix_target", "") or "").strip()
    next_step_text = (
        "Next step: " + _clean_guidance_text(next_step) + (f" | Change it in {fix_target}" if fix_target else "")
        if next_step
        else "Next step: choose a service or test the current connection."
    )
    if auth_kind == "oauth_file_token" and auth_state == "MISSING":
        next_step_text = (
            f"Next step: add the downloaded {connector_label.lower()} credentials JSON on this PC before browser sign-in can start."
        )

    if provider_field_details:
        field_summary = ", ".join(
            f"{str(row.get('label', row.get('key', 'field')))}={'READY' if bool(row.get('present', False)) else 'MISSING'}"
            for row in provider_field_details
        )
        secret_text = "Saved details: " + (field_summary or "none")
    else:
        secret_text = "Saved details: " + (", ".join(secret_fields) if secret_fields else "none")

    secret_placeholder = "secret value for API-key or provider-backed connectors"
    secret_masked = True
    if selected_field_detail:
        secret_placeholder = str(
            selected_field_detail.get("placeholder")
            or selected_field_detail.get("input_hint")
            or secret_placeholder
        ).strip() or secret_placeholder
        secret_masked = bool(selected_field_detail.get("masked", True))

    actions = {str(action).strip() for action in payload.get("actions_supported", []) if str(action).strip()} if isinstance(payload.get("actions_supported"), list) else set()
    provider_required = bool(providers)
    provider_selected = bool(selected_provider_payload) or not provider_required
    action_text = {
        "verify": "VERIFY",
        "connect": "CONNECT",
        "reconnect": "RECONNECT",
        "disconnect": "DISCONNECT",
        "save_secret": "SAVE SECRET",
        "clear_secret": "CLEAR SECRET",
    }
    if auth_kind == "api_key":
        action_text.update({"verify": "TEST KEY", "connect": "SAVE KEY", "reconnect": "RECONNECT", "disconnect": "REMOVE KEY"})
    elif auth_kind == "oauth_file_token":
        action_text.update({"verify": "CHECK SIGN-IN", "connect": "SIGN IN", "reconnect": "SIGN IN AGAIN", "disconnect": "REMOVE SIGN-IN"})
    elif auth_kind in {"provider_secret", "oauth_secret"}:
        action_text.update({"verify": "CHECK SETUP", "connect": "SAVE DETAILS", "reconnect": "RECONNECT", "disconnect": "CLEAR DETAILS"})

    button_states: dict[str, ConnectorActionButtonState] = {}
    for action_name in ("verify", "connect", "reconnect", "disconnect", "save_secret", "clear_secret"):
        resolved_action = "connect" if action_name == "save_secret" else "disconnect" if action_name == "clear_secret" else action_name
        enabled = resolved_action in actions
        if action_name in {"save_secret", "clear_secret"}:
            enabled = enabled and bool(secret_fields)
        enabled = enabled and provider_selected
        if auth_kind == "api_key" and action_name in {"connect", "reconnect"}:
            visible = False
        elif auth_kind == "provider_secret" and action_name == "reconnect":
            visible = False
        elif auth_kind == "oauth_file_token" and auth_state == "MISSING" and action_name in {"connect", "reconnect"}:
            visible = False
        else:
            visible = True
        if enabled:
            tooltip = ""
        elif provider_required and not provider_selected:
            tooltip = "Choose a provider from the inventory before running connector actions."
        else:
            tooltip = f"{connector_id or 'connector'} does not support {resolved_action}."
        button_states[action_name] = ConnectorActionButtonState(
            text=action_text[action_name],
            visible=visible,
            enabled=enabled,
            tooltip=tooltip,
        )

    return ConnectorInventoryState(
        provider_options=tuple(
            ConnectorSelectorOption(_selector_label(value, fallback="(provider)"), str(value.get("id", "")))
            for value in providers
        ),
        selected_provider=selected_provider,
        account_options=tuple(
            ConnectorSelectorOption(_selector_label(value, fallback="(account)"), str(value.get("id", "")))
            for value in accounts
        ),
        selected_account=selected_account,
        secret_field_options=tuple(ConnectorSelectorOption(field, field) for field in secret_fields),
        selected_secret_key=selected_secret_key,
        state_text=f"{connector_label} helps with {purpose.lower()} on this PC.",
        auth_text=f"Connection status: {_friendly_auth_state(auth_state)}",
        detail_text=_clean_guidance_text(detail or f"Choose {connector_label} to see how to connect it."),
        validation_text="What to do next: " + " | ".join(_clean_guidance_text(bit) for bit in validation_bits if bit),
        scope_text=f"What it can help with: {_clean_guidance_text(rendered_scope)}",
        setup_text=setup_text,
        next_step_text=next_step_text,
        history_text=_history_line(history),
        recent_text=_recent_history_line(history),
        secret_text=secret_text,
        secret_placeholder=secret_placeholder,
        secret_masked=secret_masked,
        button_states=button_states,
    )


def validate_connector_action(
    item: Mapping[str, object] | None,
    action: str,
    *,
    selected_provider_id: str = "",
    selected_secret_key: str = "",
    secret_value: str = "",
) -> str:
    payload = item if isinstance(item, Mapping) else {}
    connector_id = str(payload.get("id", "") or "").strip().lower()
    providers = [row for row in payload.get("providers", []) if isinstance(row, dict)] if isinstance(payload.get("providers"), list) else []
    provider_payload = next(
        (row for row in providers if str(row.get("id", "")).strip().lower() == str(selected_provider_id).strip().lower()),
        {},
    )
    if providers and not provider_payload:
        return "Choose a provider from the connector inventory before running this action."
    if action in {"connect", "save_secret"}:
        field_details = _provider_field_details(provider_payload)
        needs_secret = bool(field_details) or bool(_provider_secret_fields(provider_payload, payload))
        if needs_secret and not selected_secret_key:
            return "Choose which provider field you want to save before continuing."
        if selected_secret_key and not str(secret_value or "").strip():
            selected_field = next(
                (row for row in field_details if str(row.get("key", "")).strip() == selected_secret_key),
                {},
            )
            field_label = str(selected_field.get("label", selected_secret_key) or selected_secret_key).strip() or selected_secret_key
            return f"Enter a value for {field_label} before saving it."
    if action == "reconnect" and connector_id in {"crm", "voip", "youtube"}:
        return f"{connector_id} does not expose reconnect in this guided secret flow."
    return ""
