"""
ui/launcher/views/settings_accounts_sections.py
Shared helpers extracted from settings_device_accounts_panel.py.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from src.guppy.launcher_application.provider_registry import get_example_prompt, get_provider
from src.guppy.launcher_application.settings_device_accounts_presenter import (
    build_connector_panel_state,
    resolve_field_payloads,
)
from .. import tokens as T
from .settings_device_accounts_form_support import (
    apply_connector_action_state as _apply_connector_action_state,
    apply_empty_connector_state as _apply_empty_connector_state,
    apply_field_payloads as _apply_field_payloads,
)


def mono(text: str, color: str = T.DIM, size: int = T.FS_SMALL, bold: bool = False) -> QLabel:
    """Create a word-wrapped monospace label."""
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {size}pt; letter-spacing: 1px;"
        + (" font-weight: bold;" if bold else "")
    )
    return lbl


def connector_card_style(*, selected: bool, ready: bool, accent: str, wash: str) -> str:
    """Return the stylesheet string for a connector card button."""
    border = accent if selected else (T.STATUS_SUCCESS if ready else T.BORDER_SOFT)
    background = wash if selected else T.BG1
    text_color = T.TEXT if selected or ready else T.DIM
    return (
        f"QPushButton {{ background: {background}; color: {text_color}; border: 1px solid {border}; border-radius: 4px;"
        f" border-left: 6px solid {accent}; padding: 10px 12px; text-align: left;"
        f" font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        f"QPushButton:hover {{ border-color: {accent}; color: {T.TEXT}; background: {wash}; }}"
    )


def connector_grid_columns(width: int, viewport_width: int) -> int:
    """Return number of grid columns given effective panel width."""
    effective = max(width, viewport_width)
    if effective <= 900:
        return 1
    if effective <= 1280:
        return 2
    return 3


def sync_account_controls(owner: Any) -> None:
    item = owner._current_connector_payload()
    if not item:
        _apply_empty_connector_state(owner)
        return
    providers = [row for row in item.get("providers", []) if isinstance(row, dict)] if isinstance(item.get("providers"), list) else []
    accounts = [row for row in item.get("accounts", []) if isinstance(row, dict)] if isinstance(item.get("accounts"), list) else []
    previous_provider = str(owner._provider_cb.currentData() or "").strip()
    previous_account = str(owner._account_cb.currentData() or "").strip()
    owner._sync_combo(owner._provider_cb, providers, previous_provider, "(choose provider)")
    owner._sync_combo(owner._account_cb, accounts, previous_account, "(choose account)")
    owner._provider_cb.setVisible(bool(providers))
    owner._account_cb.setVisible(bool(accounts))
    owner._selector_row_widget.setVisible(bool(providers) or bool(accounts))

    owner._refresh_connector_card_styles()

    selected_provider_id = str(owner._provider_cb.currentData() or "").strip().lower()
    field_payloads = resolve_field_payloads(item, selected_provider_id)
    _apply_field_payloads(owner, field_payloads)

    panel_state = build_connector_panel_state(
        item=item,
        providers=providers,
        accounts=accounts,
        fields=field_payloads,
        selected_provider_id=str(owner._provider_cb.currentData() or "").strip(),
        selected_account_id=str(owner._account_cb.currentData() or "").strip(),
    )
    connector_label = str(item.get("label", "Connector") or "Connector")
    auth_kind = panel_state.current_auth_kind
    auth_state = str(item.get("auth_state", "missing") or "missing").strip().lower()
    owner._current_auth_kind = panel_state.current_auth_kind
    owner._account_status_lbl.setText(panel_state.status_text)
    owner._account_detail_lbl.setText(panel_state.detail_text)
    owner._account_step_lbl.setText(panel_state.step_text)
    owner._account_status_lbl.setToolTip(panel_state.status_text)
    owner._account_detail_lbl.setToolTip(panel_state.detail_text)
    owner._account_step_lbl.setToolTip(panel_state.step_text)
    owner._account_step_lbl.setStyleSheet(
        f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
    )

    connector_id = str(item.get("id", "") or "").strip().lower()
    is_verified = auth_state in {"ready", "optional"}
    registry_entry = get_provider(connector_id)
    hint_text = (registry_entry.next_step_hint if registry_entry else "").strip()
    example_prompt = get_example_prompt(connector_id).strip()
    if is_verified and hint_text:
        extra = f" {example_prompt}" if example_prompt else ""
        owner._next_step_hint_lbl.setText(f"Connected — {hint_text}{extra}")
        owner._next_step_hint_lbl.setVisible(True)
        owner._next_step_hint_lbl.setToolTip(owner._next_step_hint_lbl.text())
    else:
        owner._next_step_hint_lbl.setText("")
        owner._next_step_hint_lbl.setVisible(False)

    supports = {str(s).strip().lower() for s in item.get("actions_supported", []) if str(s).strip()}
    connect_hint = (registry_entry.connect_hint if registry_entry else "").strip() or f"Connect {connector_label} on this PC."
    verify_hint = f"Verify {connector_label} on this PC."
    if example_prompt:
        verify_hint += f" {example_prompt}"
    _apply_connector_action_state(
        owner,
        connector_label=connector_label,
        auth_kind=auth_kind,
        auth_state=auth_state,
        supports=supports,
        connect_hint=connect_hint,
        verify_hint=verify_hint,
    )
    if owner.isVisible():
        owner._apply_density_mode(owner.width())


def focus_connector(
    owner: Any,
    connector_id: str,
    *,
    provider: str = "",
    account_id: str = "",
    note: str = "",
) -> None:
    normalized_connector = str(connector_id or "").strip().lower()
    if not normalized_connector:
        return
    connector_index = owner._connector_cb.findData(normalized_connector)
    if connector_index >= 0:
        owner._connector_cb.setCurrentIndex(connector_index)
    if provider:
        provider_index = owner._provider_cb.findData(str(provider or "").strip().lower())
        if provider_index >= 0:
            owner._provider_cb.setCurrentIndex(provider_index)
    if account_id:
        account_index = owner._account_cb.findData(str(account_id or "").strip().lower())
        if account_index >= 0:
            owner._account_cb.setCurrentIndex(account_index)
    owner._sync_account_controls()
    if note:
        owner.set_account_result(note, ok=None)
    focus_target = next(
        (
            input_box
            for row_widget, _label, input_box, _hint in owner._field_rows
            if row_widget.isVisible()
        ),
        owner._provider_cb if owner._provider_cb.isVisible() else owner._account_cb if owner._account_cb.isVisible() else owner._connector_cb,
    )
    if focus_target is not None:
        focus_target.setFocus(Qt.FocusReason.OtherFocusReason)
    if owner._scroll_area is not None:
        owner._scroll_area.ensureWidgetVisible(owner, 0, 48)
