from __future__ import annotations

from PySide6.QtWidgets import QLineEdit

from src.guppy.launcher_application.app_mgmt_presenter import (
    build_connector_inventory_state,
    validate_connector_action,
)

_DEFAULT_CONNECTORS = (
    ("gmail", "Gmail"),
    ("calendar", "Calendar"),
    ("spotify", "Spotify"),
    ("youtube", "YouTube"),
    ("crm", "CRM"),
    ("voip", "VoIP"),
)


def set_connector_inventory(owner, items: list[dict[str, object]]) -> None:
    owner._connector_inventory = [item for item in items if isinstance(item, dict)]
    current = str(owner._connector_cb.currentData() or owner._connector_cb.currentText() or "").strip().lower()
    owner._connector_cb.blockSignals(True)
    owner._connector_cb.clear()
    for item in owner._connector_inventory:
        connector_id = str(item.get("id", "")).strip().lower()
        label = str(item.get("label", connector_id.title()) or connector_id.title())
        if connector_id:
            owner._connector_cb.addItem(label, connector_id)
    if owner._connector_cb.count() == 0:
        for connector_id, label in _DEFAULT_CONNECTORS:
            owner._connector_cb.addItem(label, connector_id)
    idx = owner._connector_cb.findData(current)
    owner._connector_cb.setCurrentIndex(max(0, idx))
    owner._connector_cb.blockSignals(False)
    sync_connector_controls(owner)


def current_connector_payload(owner) -> dict[str, object]:
    connector_id = str(owner._connector_cb.currentData() or owner._connector_cb.currentText() or "").strip().lower()
    return next(
        (
            item
            for item in owner._connector_inventory
            if str(item.get("id", "")).strip().lower() == connector_id
        ),
        {},
    )


def _sync_selector_combo(combo, values, default_label: str, selected_value: str) -> None:
    combo.blockSignals(True)
    combo.clear()
    combo.addItem(default_label, "")
    for value in values:
        combo.addItem(value.label, value.value)
    idx = combo.findData(selected_value)
    combo.setCurrentIndex(0 if idx < 0 else idx)
    combo.blockSignals(False)


def sync_connector_controls(owner) -> None:
    item = current_connector_payload(owner)
    previous_provider = str(owner._connector_provider.currentData() or "").strip().lower()
    previous_account = str(owner._connector_account.currentData() or "").strip().lower()
    previous_secret_key = str(owner._connector_secret_key.currentData() or "").strip()
    state = build_connector_inventory_state(
        item,
        previous_provider=previous_provider,
        previous_account=previous_account,
        previous_secret_key=previous_secret_key,
        fallback_connector_id=str(owner._connector_cb.currentData() or owner._connector_cb.currentText() or "").strip().lower(),
    )
    for combo, values, default_label, selected_value in (
        (owner._connector_provider, state.provider_options, "(provider)", state.selected_provider),
        (owner._connector_account, state.account_options, "(account)", state.selected_account),
    ):
        _sync_selector_combo(combo, values, default_label, selected_value)
    owner._connector_secret_key.blockSignals(True)
    owner._connector_secret_key.clear()
    owner._connector_secret_key.addItem("(secret field)", "")
    for field in state.secret_field_options:
        owner._connector_secret_key.addItem(field.label, field.value)
    secret_idx = owner._connector_secret_key.findData(state.selected_secret_key)
    owner._connector_secret_key.setCurrentIndex(0 if secret_idx < 0 else secret_idx)
    owner._connector_secret_key.blockSignals(False)
    owner._connector_state_lbl.setText(state.state_text)
    owner._connector_auth_lbl.setText(state.auth_text)
    owner._connector_detail_lbl.setText(state.detail_text)
    owner._connector_validation_lbl.setText(state.validation_text)
    owner._connector_scope_lbl.setText(state.scope_text)
    owner._connector_setup_lbl.setText(state.setup_text)
    owner._connector_next_step_lbl.setText(state.next_step_text)
    owner._connector_history_lbl.setText(state.history_text)
    owner._connector_recent_lbl.setText(state.recent_text)
    owner._connector_secret_lbl.setText(state.secret_text)
    owner._connector_secret_value.setPlaceholderText(state.secret_placeholder)
    owner._connector_secret_value.setEchoMode(
        QLineEdit.EchoMode.Password if state.secret_masked and bool(state.selected_secret_key) else QLineEdit.EchoMode.Normal
    )
    for action_name, button in owner._connector_action_buttons.items():
        button_state = state.button_states[action_name]
        button.setText(button_state.text)
        button.setVisible(button_state.visible)
        button.setEnabled(button_state.enabled)
        button.setToolTip(button_state.tooltip)


def emit_connector_action(owner, action: str) -> None:
    connector_id = str(owner._connector_cb.currentData() or owner._connector_cb.currentText() or "").strip().lower()
    if not connector_id:
        owner.append_log("connector action ignored: choose a connector first")
        return
    resolved_action = "connect" if action == "save_secret" else "disconnect" if action == "clear_secret" else action
    item = current_connector_payload(owner)
    selected_secret_key = str(owner._connector_secret_key.currentData() or "").strip()
    secret_value = owner._connector_secret_value.text().strip()
    validation_error = validate_connector_action(
        item,
        action,
        selected_provider_id=str(owner._connector_provider.currentData() or "").strip(),
        selected_secret_key=selected_secret_key,
        secret_value=secret_value,
    )
    if validation_error:
        owner.append_log(f"connector action blocked: {validation_error}")
        return
    owner.connector_action_requested.emit(
        {
            "connector": connector_id,
            "action": resolved_action,
            "provider": str(owner._connector_provider.currentData() or "").strip(),
            "account_id": str(owner._connector_account.currentData() or "").strip(),
            "secret_key": selected_secret_key,
            "secret_value": secret_value,
            "request_source": "settings_operations_panel",
        }
    )
