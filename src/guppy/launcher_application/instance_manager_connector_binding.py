"""Connector binding presenter helpers for the launcher workspace manager view."""

from __future__ import annotations

from .instance_manager_models import DEFAULT_CONNECTOR_IDS, ConnectorBindingState, SelectorOption


def selector_label(item: dict[str, object], *, fallback: str) -> str:
    label = str(item.get("label", item.get("id", fallback)) or fallback).strip() or fallback
    auth_state = str(item.get("auth_state", "") or "").strip().upper()
    if auth_state:
        label += f" [{auth_state}]"
    return label


def connector_history_line(payload: dict[str, object]) -> str:
    last_action = str(payload.get("last_action", "") or "").strip()
    last_action_at = str(payload.get("last_action_at", "") or "").strip()
    last_result = str(payload.get("last_result", "") or "").strip()
    if not last_action:
        return "Connector history: no verify/connect activity has been recorded yet."
    summary = f"Connector history: last {last_action}"
    if last_action_at:
        summary += f" @ {last_action_at}"
    if last_result:
        summary += f" | {last_result}"
    return summary


def build_connector_binding_feedback(
    connector_payload: dict[str, object],
    *,
    enabled: bool,
    selected_provider: str,
    selected_account: str,
) -> tuple[str, str]:
    validation = (
        connector_payload.get("binding_validation", {})
        if isinstance(connector_payload.get("binding_validation"), dict)
        else {}
    )
    provider_rows = (
        [row for row in connector_payload.get("providers", []) if isinstance(row, dict)]
        if isinstance(connector_payload.get("providers"), list)
        else []
    )
    account_rows = (
        [row for row in connector_payload.get("accounts", []) if isinstance(row, dict)]
        if isinstance(connector_payload.get("accounts"), list)
        else []
    )
    provider_payload = next(
        (row for row in provider_rows if str(row.get("id", "")).strip().lower() == selected_provider),
        {},
    )
    account_payload = next(
        (row for row in account_rows if str(row.get("id", "")).strip().lower() == selected_account),
        {},
    )
    validation_bits: list[str] = []
    if not enabled:
        validation_bits.append("Workspace binding is currently disabled.")
    if provider_payload:
        validation_bits.append(str(provider_payload.get("auth_detail", "") or "").strip())
    elif provider_rows:
        validation_bits.append("Choose a provider from the machine inventory before saving.")
    if account_payload:
        validation_bits.append(str(account_payload.get("auth_detail", "") or "").strip())
    elif account_rows:
        validation_bits.append("Choose an available account from the machine inventory before saving.")
    validation_bits.append(str(validation.get("message", "") or "").strip())
    history_payload = (
        connector_payload.get("history", {})
        if isinstance(connector_payload.get("history"), dict)
        else {}
    )
    return (
        "Validation: " + " | ".join(bit for bit in validation_bits if bit),
        connector_history_line(history_payload),
    )


def build_connector_binding_editor_state(
    workspace_name: str,
    connector_id: str,
    connectors_by_name: dict[str, dict[str, dict[str, object]]],
) -> ConnectorBindingState:
    workspace_key = str(workspace_name or "").strip()
    connector_map = connectors_by_name.get(workspace_key, {})
    normalized_connector_id = str(connector_id or "").strip().lower()
    connector_ids = tuple(connector_map.keys()) or DEFAULT_CONNECTOR_IDS
    selected_connector_id = normalized_connector_id if normalized_connector_id in connector_ids else connector_ids[0]
    connector_payload = connector_map.get(selected_connector_id, {})
    binding = connector_payload.get("binding", {}) if isinstance(connector_payload.get("binding"), dict) else {}
    provider_rows = (
        [row for row in connector_payload.get("providers", []) if isinstance(row, dict)]
        if isinstance(connector_payload.get("providers"), list)
        else []
    )
    account_rows = (
        [row for row in connector_payload.get("accounts", []) if isinstance(row, dict)]
        if isinstance(connector_payload.get("accounts"), list)
        else []
    )
    saved_provider = str(binding.get("provider", "") or "").strip().lower()
    saved_account = str(binding.get("account_id", "") or "").strip().lower()
    provider_options = [SelectorOption("(no provider)", "")]
    for row in provider_rows:
        provider_options.append(SelectorOption(selector_label(row, fallback="provider"), str(row.get("id", ""))))
    if saved_provider and not any(item.value == saved_provider for item in provider_options):
        provider_options.append(SelectorOption(f"{saved_provider} [SAVED / UNAVAILABLE]", saved_provider))
    account_options = [SelectorOption("(no account)", "")]
    for row in account_rows:
        account_options.append(SelectorOption(selector_label(row, fallback="account"), str(row.get("id", ""))))
    if saved_account and not any(item.value == saved_account for item in account_options):
        account_options.append(SelectorOption(f"{saved_account} [SAVED / UNAVAILABLE]", saved_account))
    validation_text, history_text = build_connector_binding_feedback(
        connector_payload,
        enabled=bool(binding.get("enabled", False)),
        selected_provider=saved_provider,
        selected_account=saved_account,
    )
    auth_state = str(connector_payload.get("auth_state", "unknown") or "unknown")
    auth_mode = str(connector_payload.get("workspace_auth_mode", "runtime_default") or "runtime_default")
    source = str(connector_payload.get("source", "none") or "none")
    return ConnectorBindingState(
        connector_ids=tuple(str(item).strip() for item in connector_ids if str(item).strip()),
        selected_connector_id=selected_connector_id,
        enabled=bool(binding.get("enabled", False)),
        provider_options=tuple(provider_options),
        selected_provider=saved_provider,
        account_options=tuple(account_options),
        selected_account=saved_account,
        action_allow_text="\n".join(str(item) for item in binding.get("action_allow", []) if str(item).strip()),
        action_block_text="\n".join(str(item) for item in binding.get("action_block", []) if str(item).strip()),
        endpoint_allow_text="\n".join(str(item) for item in binding.get("endpoint_allow", []) if str(item).strip()),
        endpoint_block_text="\n".join(str(item) for item in binding.get("endpoint_block", []) if str(item).strip()),
        note=str(binding.get("note", "") or ""),
        status_text=(
            f"Editing {workspace_key or 'workspace'} / {selected_connector_id or 'connector'} | auth={auth_state} | "
            f"source={source} | workspace auth mode={auth_mode}"
        ),
        validation_text=validation_text,
        history_text=history_text,
    )
