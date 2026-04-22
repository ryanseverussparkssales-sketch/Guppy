from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

from .. import tokens as T
from .settings_accounts_sections import mono


def ensure_field_row_count(owner, count: int) -> None:
    while len(owner._field_rows) < max(0, count):
        row = QWidget()
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(4)
        label = mono("", T.TEXT, T.FS_TINY, True)
        input_box = QLineEdit()
        input_box.setStyleSheet(
            f"QLineEdit {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
            f" font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; padding: 4px 8px; }}"
        )
        hint = mono("", T.DIM, T.FS_TINY)
        row_layout.addWidget(label)
        row_layout.addWidget(input_box)
        row_layout.addWidget(hint)
        row.setVisible(False)
        owner._fields_host.addWidget(row)
        owner._field_rows.append((row, label, input_box, hint))


def reset_field_rows(owner) -> None:
    for row_widget, label, input_box, hint in owner._field_rows:
        row_widget.setVisible(False)
        row_widget.setProperty("secret_key", "")
        label.setText("")
        input_box.clear()
        input_box.setPlaceholderText("")
        input_box.setEchoMode(QLineEdit.EchoMode.Normal)
        hint.setText("")


def apply_field_payloads(owner, field_payloads: list[dict[str, Any]]) -> None:
    ensure_field_row_count(owner, len(field_payloads))
    reset_field_rows(owner)
    for idx, field in enumerate(field_payloads):
        row_widget, label, input_box, hint = owner._field_rows[idx]
        label.setText(str(field.get("label", field.get("key", "Credential")) or "Credential"))
        input_box.setPlaceholderText(str(field.get("placeholder", "") or ""))
        input_box.setEchoMode(
            QLineEdit.EchoMode.Password if bool(field.get("masked", True)) else QLineEdit.EchoMode.Normal
        )
        hint_text = str(field.get("input_hint", "") or field.get("validation_hint", "") or "").strip()
        hint.setText(hint_text)
        row_widget.setProperty("secret_key", str(field.get("key", "") or ""))
        row_widget.setVisible(True)


def apply_empty_connector_state(owner) -> None:
    owner._provider_cb.clear()
    owner._account_cb.clear()
    owner._selector_row_widget.setVisible(False)
    owner._account_status_lbl.setText("No services are ready to link yet.")
    owner._account_detail_lbl.setText("Install or enable a connector, then come back here to sign in.")
    owner._account_step_lbl.setText("Next step: add a service first.")
    owner._account_step_lbl.setStyleSheet(
        f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
    )
    owner._next_step_hint_lbl.setText("")
    owner._next_step_hint_lbl.setVisible(False)
    reset_field_rows(owner)
    owner._connect_btn.setVisible(False)
    owner._save_btn.setVisible(False)
    owner._verify_btn.setEnabled(False)
    owner._disconnect_btn.setEnabled(False)
    owner._disable_btn.setVisible(False)
    owner._refresh_connector_card_styles()


def apply_connector_action_state(
    owner,
    *,
    connector_label: str,
    auth_kind: str,
    auth_state: str,
    supports: set[str],
    connect_hint: str,
    verify_hint: str,
) -> None:
    has_secret_flow = auth_kind in {"api_key", "provider_secret", "oauth_secret"}
    if auth_kind == "api_key":
        owner._save_btn.setText("SAVE API KEY")
        owner._verify_btn.setText("VERIFY KEY")
        owner._disconnect_btn.setText("REMOVE KEY")
    elif auth_kind == "provider_secret":
        owner._save_btn.setText("SAVE DETAILS")
        owner._verify_btn.setText("VERIFY SETUP")
        owner._disconnect_btn.setText("CLEAR DETAILS")
    elif auth_kind == "oauth_file_token":
        owner._connect_btn.setText("RECONNECT" if auth_state == "partial" else "SIGN IN")
        owner._verify_btn.setText("VERIFY SIGN-IN")
        owner._disconnect_btn.setText("REMOVE SIGN-IN")
    elif auth_kind == "oauth_secret":
        owner._connect_btn.setText("RECONNECT" if auth_state == "partial" else "OPEN SIGN-IN")
        owner._save_btn.setText("SAVE APP KEYS")
        owner._verify_btn.setText("VERIFY CONNECTION")
        owner._disconnect_btn.setText("REMOVE CONNECTION")
    else:
        owner._connect_btn.setText("SIGN IN")
        owner._save_btn.setText("SAVE")
        owner._verify_btn.setText("VERIFY")
        owner._disconnect_btn.setText("REMOVE")

    show_connect = (
        "connect" in supports
        and auth_kind not in {"api_key", "provider_secret"}
        and not (auth_kind == "oauth_file_token" and auth_state == "missing")
    )
    owner._connect_btn.setVisible(show_connect)
    owner._connect_btn.setEnabled(show_connect)
    owner._save_btn.setVisible(has_secret_flow)
    owner._save_btn.setEnabled(has_secret_flow)
    owner._verify_btn.setVisible("verify" in supports)
    owner._verify_btn.setEnabled("verify" in supports)
    owner._disconnect_btn.setVisible("disconnect" in supports)
    owner._disconnect_btn.setEnabled("disconnect" in supports)
    owner._disable_btn.setVisible(True)
    owner._disable_btn.setEnabled(False)
    owner._connect_btn.setToolTip(connect_hint)
    owner._save_btn.setToolTip(f"Save the current {connector_label} details on this PC.")
    owner._verify_btn.setToolTip(verify_hint)
    owner._disconnect_btn.setToolTip(f"Remove the current {connector_label} connection from this PC.")
