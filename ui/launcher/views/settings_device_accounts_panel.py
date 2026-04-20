from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QResizeEvent, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.guppy.launcher_application.provider_registry import get_example_prompt, get_provider
from src.guppy.launcher_application.settings_device_accounts_presenter import (
    build_connector_card_specs,
    build_connector_panel_state,
    build_device_accounts_density_state,
    connector_brand,
    friendly_runtime_summary,
    provider_tier_badge,
    resolve_field_payloads,
    selector_label,
)
from .. import tokens as T


def _mono(text: str, color: str = T.DIM, size: int = T.FS_SMALL, bold: bool = False) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {size}pt; letter-spacing: 1px;"
        + (" font-weight: bold;" if bold else "")
    )
    return lbl

class SettingsDeviceAccountsPanel(QWidget):
    windows_ops_requested = Signal(str)
    connector_action_requested = Signal(dict)
    connector_guided_link_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._windows_snapshot: dict[str, str] = {}
        self._connector_inventory: list[dict[str, object]] = []
        self._field_rows: list[tuple[QWidget, QLabel, QLineEdit, QLabel]] = []
        self._connector_card_buttons: list[tuple[str, QPushButton]] = []
        self._desktop_action_buttons: list[QPushButton] = []
        self._current_auth_kind = "unknown"
        self._scroll_area: QScrollArea | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._scroll_area = scroll

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(20)

        title = QLabel("Device & Accounts")
        title.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_HEAD}'; font-size: 30pt; font-weight: 900; letter-spacing: -1px;"
        )
        layout.addWidget(title)
        layout.addWidget(
            _mono(
                "Manage this Windows device, your local AI runtime, and the accounts Guppy can use here.",
                T.DIM,
                T.FS_SMALL,
            )
        )

        self._summary_lbl = _mono("Checking this PC now.", T.PRIMARY_DIM, T.FS_SMALL)
        layout.addWidget(self._summary_lbl)

        desktop_frame = QFrame()
        desktop_frame.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}")
        desktop_layout = QVBoxLayout(desktop_frame)
        desktop_layout.setContentsMargins(16, 14, 16, 14)
        desktop_layout.setSpacing(8)
        desktop_layout.addWidget(_mono("THIS PC", T.PRIMARY, T.FS_TINY, True))
        self._pc_install_lbl = _mono("Ready on this PC: checking now", T.DIM, T.FS_SMALL)
        self._pc_runtime_lbl = _mono("Local AI health: checking now", T.DIM, T.FS_SMALL)
        self._pc_next_lbl = _mono("Next step: checking now", T.DIM, T.FS_SMALL)
        self._pc_diag_lbl = _mono("Health notes: checking now", T.DIM, T.FS_TINY)
        for widget in (self._pc_install_lbl, self._pc_runtime_lbl, self._pc_next_lbl, self._pc_diag_lbl):
            desktop_layout.addWidget(widget)
        action_row = QHBoxLayout()
        for label, action, accent in [
            ("VERIFY", "verify_runtime", T.PRIMARY),
            ("UPDATE", "update_runtime", T.PRIMARY_DIM),
            ("START API", "supervised_api", T.SECONDARY),
            ("RESTART", "restart_api", T.ERROR),
            ("REPAIR", "repair", T.PRIMARY),
        ]:
            btn = QPushButton(label)
            btn.setStyleSheet(
                f"QPushButton {{ background: {T.BG0}; color: {accent}; border: 1px solid {accent};"
                f" padding: 5px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ background: {accent}; color: {T.BG}; }}"
            )
            btn.clicked.connect(lambda _=False, a=action: self.windows_ops_requested.emit(a))
            action_row.addWidget(btn)
            self._desktop_action_buttons.append(btn)
        action_row.addStretch()
        desktop_layout.addLayout(action_row)
        layout.addWidget(desktop_frame)

        accounts_frame = QFrame()
        accounts_frame.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}")
        accounts_layout = QVBoxLayout(accounts_frame)
        accounts_layout.setContentsMargins(16, 14, 16, 14)
        accounts_layout.setSpacing(10)
        accounts_layout.addWidget(_mono("ACCOUNT LINKER", T.PRIMARY, T.FS_TINY, True))
        accounts_layout.addWidget(
            _mono(
                "Connect the services you want Guppy to use on this PC. Some use browser sign-in, and some use API keys.",
                T.DIM,
                T.FS_SMALL,
            )
        )

        self._connector_cards_host = QWidget()
        self._connector_cards_grid = QGridLayout(self._connector_cards_host)
        self._connector_cards_grid.setContentsMargins(0, 0, 0, 0)
        self._connector_cards_grid.setHorizontalSpacing(10)
        self._connector_cards_grid.setVerticalSpacing(10)
        accounts_layout.addWidget(self._connector_cards_host)

        self._selector_row_widget = QWidget()
        top_row = QHBoxLayout(self._selector_row_widget)
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(10)
        self._connector_cb = QComboBox()
        self._provider_cb = QComboBox()
        self._account_cb = QComboBox()
        for combo in (self._connector_cb, self._provider_cb, self._account_cb):
            combo.setStyleSheet(
                f"QComboBox {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
                f" font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; padding: 4px 8px; }}"
            )
        self._connector_cb.currentIndexChanged.connect(self._sync_account_controls)
        self._provider_cb.currentIndexChanged.connect(self._sync_account_controls)
        self._account_cb.currentIndexChanged.connect(self._sync_account_controls)
        self._connector_cb.setVisible(False)
        top_row.addWidget(self._provider_cb, stretch=1)
        top_row.addWidget(self._account_cb, stretch=1)
        accounts_layout.addWidget(self._selector_row_widget)

        self._account_status_lbl = _mono("Choose a service to get started.", T.TEXT, T.FS_SMALL)
        self._account_detail_lbl = _mono("Pick a card to see what that service helps with and how to connect it.", T.DIM, T.FS_SMALL)
        self._account_step_lbl = _mono("Next step: pick a service.", T.DIM, T.FS_TINY)
        self._next_step_hint_lbl = QLabel("")
        self._next_step_hint_lbl.setWordWrap(True)
        self._next_step_hint_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
            " letter-spacing: 1px; font-style: italic;"
        )
        self._next_step_hint_lbl.setVisible(False)
        for widget in (self._account_status_lbl, self._account_detail_lbl, self._account_step_lbl, self._next_step_hint_lbl):
            accounts_layout.addWidget(widget)

        self._fields_host = QVBoxLayout()
        self._fields_host.setContentsMargins(0, 0, 0, 0)
        self._fields_host.setSpacing(8)
        self._ensure_field_row_count(3)
        accounts_layout.addLayout(self._fields_host)

        action_row = QHBoxLayout()
        self._connect_btn = QPushButton("BROWSER SIGN-IN")
        self._save_btn = QPushButton("SAVE & VERIFY")
        self._verify_btn = QPushButton("VERIFY ONLY")
        self._disconnect_btn = QPushButton("DISCONNECT")
        for btn, accent in [
            (self._connect_btn, T.PRIMARY_DIM),
            (self._save_btn, T.PRIMARY),
            (self._verify_btn, T.SECONDARY),
            (self._disconnect_btn, T.ERROR),
        ]:
            btn.setStyleSheet(
                f"QPushButton {{ background: {T.BG0}; color: {accent}; border: 1px solid {accent};"
                f" padding: 5px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ background: {accent}; color: {T.BG}; }}"
            )
            action_row.addWidget(btn)
        action_row.addStretch()
        self._connect_btn.clicked.connect(lambda: self._emit_basic_connector_action("connect"))
        self._verify_btn.clicked.connect(lambda: self._emit_basic_connector_action("verify"))
        self._disconnect_btn.clicked.connect(lambda: self._emit_basic_connector_action("disconnect"))
        self._save_btn.clicked.connect(self._emit_guided_save)
        accounts_layout.addLayout(action_row)
        layout.addWidget(accounts_frame)
        layout.addStretch(1)

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def set_windows_snapshot(self, payload: dict[str, str]) -> None:
        self._windows_snapshot = dict(payload or {})
        summary, install_text, runtime_text, next_text, diagnostics_text = friendly_runtime_summary(self._windows_snapshot)
        self._summary_lbl.setText(summary)
        self._pc_install_lbl.setText(install_text)
        self._pc_runtime_lbl.setText(runtime_text)
        self._pc_next_lbl.setText(next_text)
        self._pc_diag_lbl.setText(diagnostics_text)

    def set_connector_inventory(self, items: list[dict[str, object]]) -> None:
        self._connector_inventory = [item for item in items if isinstance(item, dict)]
        current = self._connector_cb.currentData()
        self._connector_cb.blockSignals(True)
        self._connector_cb.clear()
        for item in self._connector_inventory:
            connector_id = str(item.get("id", "")).strip().lower()
            label = str(item.get("label", connector_id.title()) or connector_id.title())
            state = str(item.get("auth_state", "") or "").strip().upper()
            if connector_id:
                self._connector_cb.addItem(f"{label} [{state or 'UNKNOWN'}]", connector_id)
        self._connector_cb.blockSignals(False)
        if current:
            idx = self._connector_cb.findData(current)
            if idx >= 0:
                self._connector_cb.setCurrentIndex(idx)
            elif self._connector_cb.count() > 0:
                self._connector_cb.setCurrentIndex(0)
        elif self._connector_cb.count() > 0:
            self._connector_cb.setCurrentIndex(0)
        self._rebuild_connector_cards()
        self._sync_account_controls()

    def _ensure_field_row_count(self, count: int) -> None:
        while len(self._field_rows) < max(0, count):
            row = QWidget()
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)
            label = _mono("", T.TEXT, T.FS_TINY, True)
            input_box = QLineEdit()
            input_box.setStyleSheet(
                f"QLineEdit {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
                f" font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; padding: 4px 8px; }}"
            )
            hint = _mono("", T.DIM, T.FS_TINY)
            row_layout.addWidget(label)
            row_layout.addWidget(input_box)
            row_layout.addWidget(hint)
            row.setVisible(False)
            self._fields_host.addWidget(row)
            self._field_rows.append((row, label, input_box, hint))

    def set_account_result(self, text: str, ok: bool | None = True) -> None:
        if ok is None:
            prefix = "Heads up: "
            color = T.SECONDARY
        else:
            prefix = "Latest result: " if ok else "Needs attention: "
            color = T.GREEN if ok else T.ERROR
        self._account_step_lbl.setText(prefix + str(text or "").strip())
        self._account_step_lbl.setStyleSheet(
            f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )

    def _current_connector_payload(self) -> dict[str, object]:
        connector_id = str(self._connector_cb.currentData() or "").strip().lower()
        if not connector_id and self._connector_inventory:
            first = self._connector_inventory[0]
            if isinstance(first, dict):
                connector_id = str(first.get("id", "")).strip().lower()
        return next(
            (item for item in self._connector_inventory if str(item.get("id", "")).strip().lower() == connector_id),
            {},
        )

    def _sync_combo(self, combo: QComboBox, rows: list[dict[str, object]], previous: str, placeholder: str) -> None:
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(placeholder, "")
        for row in rows:
            tier_badge = provider_tier_badge(str(row.get("provider_tier", "") or ""))
            base_label = selector_label(row, fallback=placeholder.strip("()"))
            combo.addItem(base_label + tier_badge, str(row.get("id", "")))
        idx = combo.findData(previous)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        elif len(rows) == 1:
            combo.setCurrentIndex(1)
        else:
            combo.setCurrentIndex(0)
        combo.blockSignals(False)

    def _connector_card_style(self, *, selected: bool, ready: bool, accent: str, wash: str) -> str:
        border = accent if selected else (T.GREEN if ready else T.BORDER)
        background = wash if selected else T.BG1
        text = T.TEXT if selected or ready else T.DIM
        return (
            f"QPushButton {{ background: {background}; color: {text}; border: 1px solid {border};"
            f" border-left: 6px solid {accent}; padding: 10px 12px; text-align: left;"
            f" font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: {accent}; color: {T.TEXT}; background: {wash}; }}"
        )

    def _rebuild_connector_cards(self) -> None:
        while self._connector_cards_grid.count():
            item = self._connector_cards_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._connector_card_buttons = []
        if not self._connector_inventory:
            empty = _mono("No services are available on this machine yet.", T.DIM, T.FS_SMALL)
            self._connector_cards_grid.addWidget(empty, 0, 0)
            return
        columns = self._connector_grid_columns()
        for index, spec in enumerate(build_connector_card_specs(self._connector_inventory)):
            button = QPushButton(spec.button_text)
            button.setCheckable(True)
            button.clicked.connect(lambda _=False, cid=spec.connector_id: self._select_connector_card(cid))
            button.setProperty("connector_id", spec.connector_id)
            self._connector_cards_grid.addWidget(button, index // columns, index % columns)
            self._connector_card_buttons.append((spec.connector_id, button))
        self._refresh_connector_card_styles()

    def _connector_grid_columns(self) -> int:
        width = self.width()
        if self._scroll_area is not None and self._scroll_area.viewport() is not None:
            width = max(width, self._scroll_area.viewport().width())
        if width <= 900:
            return 1
        if width <= 1280:
            return 2
        return 3

    def _apply_density_mode(self, width: int) -> None:
        density = build_device_accounts_density_state(width, self._current_auth_kind)
        for button, text in zip(self._desktop_action_buttons, density.desktop_action_labels):
            button.setText(text)
        self._connect_btn.setText(density.connect_text)
        self._save_btn.setText(density.save_text)
        self._verify_btn.setText(density.verify_text)
        self._disconnect_btn.setText(density.disconnect_text)

    def showEvent(self, event: QShowEvent) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._rebuild_connector_cards()
        self._apply_density_mode(self.width())

    def resizeEvent(self, event: QResizeEvent) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._rebuild_connector_cards()
        self._apply_density_mode(event.size().width())

    def _select_connector_card(self, connector_id: str) -> None:
        idx = self._connector_cb.findData(connector_id)
        if idx >= 0:
            self._connector_cb.setCurrentIndex(idx)
        self._refresh_connector_card_styles()

    def _refresh_connector_card_styles(self) -> None:
        current = str(self._connector_cb.currentData() or "").strip().lower()
        for connector_id, button in self._connector_card_buttons:
            item = next(
                (row for row in self._connector_inventory if str(row.get("id", "")).strip().lower() == connector_id),
                {},
            )
            ready = str(item.get("auth_state", "") or "").strip().upper() == "READY"
            selected = connector_id == current
            brand = connector_brand(connector_id)
            button.setChecked(selected)
            button.setStyleSheet(
                self._connector_card_style(
                    selected=selected,
                    ready=ready,
                    accent=brand.accent,
                    wash=brand.wash,
                )
            )

    def _current_field_payloads(self) -> list[dict[str, Any]]:
        item = self._current_connector_payload()
        selected_provider_id = str(self._provider_cb.currentData() or "").strip().lower()
        return resolve_field_payloads(item, selected_provider_id)

    def _sync_account_controls(self) -> None:
        item = self._current_connector_payload()
        if not item:
            self._provider_cb.clear()
            self._account_cb.clear()
            self._selector_row_widget.setVisible(False)
            self._account_status_lbl.setText("No services are ready to link yet.")
            self._account_detail_lbl.setText("Install or enable a connector, then come back here to sign in.")
            self._account_step_lbl.setText("Next step: add a service first.")
            self._account_step_lbl.setStyleSheet(
                f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
            )
            for row_widget, label, input_box, hint in self._field_rows:
                row_widget.setVisible(False)
                label.setText("")
                input_box.clear()
                hint.setText("")
                input_box.setPlaceholderText("")
                input_box.setEchoMode(QLineEdit.EchoMode.Normal)
            self._next_step_hint_lbl.setText("")
            self._next_step_hint_lbl.setVisible(False)
            self._connect_btn.setVisible(False)
            self._save_btn.setVisible(False)
            self._verify_btn.setEnabled(False)
            self._disconnect_btn.setEnabled(False)
            self._refresh_connector_card_styles()
            return
        providers = [row for row in item.get("providers", []) if isinstance(row, dict)] if isinstance(item.get("providers"), list) else []
        accounts = [row for row in item.get("accounts", []) if isinstance(row, dict)] if isinstance(item.get("accounts"), list) else []
        previous_provider = str(self._provider_cb.currentData() or "").strip()
        previous_account = str(self._account_cb.currentData() or "").strip()
        self._sync_combo(self._provider_cb, providers, previous_provider, "(choose provider)")
        self._sync_combo(self._account_cb, accounts, previous_account, "(choose account)")
        self._provider_cb.setVisible(bool(providers))
        self._account_cb.setVisible(bool(accounts))
        self._selector_row_widget.setVisible(bool(providers) or bool(accounts))

        self._refresh_connector_card_styles()

        field_payloads = self._current_field_payloads()
        self._ensure_field_row_count(len(field_payloads))
        for row_widget, label, input_box, hint in self._field_rows:
            row_widget.setVisible(False)
            label.setText("")
            input_box.clear()
            hint.setText("")
            input_box.setPlaceholderText("")
            input_box.setEchoMode(QLineEdit.EchoMode.Normal)

        for idx, field in enumerate(field_payloads):
            row_widget, label, input_box, hint = self._field_rows[idx]
            label.setText(str(field.get("label", field.get("key", "Credential")) or "Credential"))
            input_box.setPlaceholderText(str(field.get("placeholder", "") or ""))
            input_box.setEchoMode(QLineEdit.EchoMode.Password if bool(field.get("masked", True)) else QLineEdit.EchoMode.Normal)
            hint_text = str(field.get("input_hint", "") or field.get("validation_hint", "") or "").strip()
            hint.setText(hint_text)
            row_widget.setVisible(True)
            row_widget.setProperty("secret_key", str(field.get("key", "") or ""))

        panel_state = build_connector_panel_state(
            item=item,
            providers=providers,
            accounts=accounts,
            fields=field_payloads,
            selected_provider_id=str(self._provider_cb.currentData() or "").strip(),
        )
        connector_label = str(item.get("label", "Connector") or "Connector")
        auth_kind = panel_state.current_auth_kind
        auth_state = str(item.get("auth_state", "missing") or "missing").strip().lower()
        self._current_auth_kind = panel_state.current_auth_kind
        self._account_status_lbl.setText(panel_state.status_text)
        self._account_detail_lbl.setText(panel_state.detail_text)
        self._account_step_lbl.setText(panel_state.step_text)
        self._account_status_lbl.setToolTip(panel_state.status_text)
        self._account_detail_lbl.setToolTip(panel_state.detail_text)
        self._account_step_lbl.setToolTip(panel_state.step_text)
        self._account_step_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )

        connector_id = str(item.get("id", "") or "").strip().lower()
        is_verified = auth_state in {"ready", "optional"}
        registry_entry = get_provider(connector_id)
        hint_text = (registry_entry.next_step_hint if registry_entry else "").strip()
        example_prompt = get_example_prompt(connector_id).strip()
        if is_verified and hint_text:
            extra = f" {example_prompt}" if example_prompt else ""
            self._next_step_hint_lbl.setText(f"Connected — {hint_text}{extra}")
            self._next_step_hint_lbl.setVisible(True)
            self._next_step_hint_lbl.setToolTip(self._next_step_hint_lbl.text())
        else:
            self._next_step_hint_lbl.setText("")
            self._next_step_hint_lbl.setVisible(False)

        supports = {str(item).strip().lower() for item in item.get("actions_supported", []) if str(item).strip()}
        has_secret_flow = auth_kind in {"api_key", "provider_secret", "oauth_secret"}
        if auth_kind == "api_key":
            self._save_btn.setText("SAVE API KEY")
            self._verify_btn.setText("TEST KEY")
            self._disconnect_btn.setText("REMOVE KEY")
        elif auth_kind == "provider_secret":
            self._save_btn.setText("SAVE DETAILS")
            self._verify_btn.setText("CHECK SETUP")
            self._disconnect_btn.setText("CLEAR DETAILS")
        elif auth_kind == "oauth_file_token":
            self._connect_btn.setText("SIGN IN")
            self._verify_btn.setText("CHECK SIGN-IN")
            self._disconnect_btn.setText("REMOVE SIGN-IN")
        elif auth_kind == "oauth_secret":
            self._connect_btn.setText("OPEN SIGN-IN")
            self._save_btn.setText("SAVE APP KEYS")
            self._verify_btn.setText("CHECK CONNECTION")
            self._disconnect_btn.setText("REMOVE CONNECTION")
        else:
            self._connect_btn.setText("SIGN IN")
            self._save_btn.setText("SAVE")
            self._verify_btn.setText("CHECK")
            self._disconnect_btn.setText("REMOVE")

        show_connect = (
            "connect" in supports
            and auth_kind not in {"api_key", "provider_secret"}
            and not (auth_kind == "oauth_file_token" and auth_state == "missing")
        )
        self._connect_btn.setVisible(show_connect)
        self._connect_btn.setEnabled(show_connect)
        self._save_btn.setVisible(has_secret_flow)
        self._save_btn.setEnabled(has_secret_flow)
        self._verify_btn.setVisible("verify" in supports)
        self._verify_btn.setEnabled("verify" in supports)
        self._disconnect_btn.setVisible("disconnect" in supports)
        self._disconnect_btn.setEnabled("disconnect" in supports)
        connect_hint = (registry_entry.connect_hint if registry_entry else "").strip() or f"Connect {connector_label} on this PC."
        self._connect_btn.setToolTip(connect_hint)
        self._save_btn.setToolTip(f"Save the current {connector_label} details on this PC.")
        verify_hint = f"Verify {connector_label} on this PC."
        if example_prompt:
            verify_hint += f" {example_prompt}"
        self._verify_btn.setToolTip(verify_hint)
        self._disconnect_btn.setToolTip(f"Remove the current {connector_label} connection from this PC.")
        if self.isVisible():
            self._apply_density_mode(self.width())

    def _base_connector_payload(self) -> dict[str, str]:
        return {
            "connector": str(self._connector_cb.currentData() or "").strip(),
            "provider": str(self._provider_cb.currentData() or "").strip(),
            "account_id": str(self._account_cb.currentData() or "").strip(),
            "request_source": "settings_device_accounts",
        }

    def _emit_basic_connector_action(self, action: str) -> None:
        payload = self._base_connector_payload()
        if not payload["connector"]:
            self.set_account_result("Choose a service first.", ok=False)
            return
        self.connector_action_requested.emit({**payload, "action": action, "secret_key": "", "secret_value": ""})

    def _emit_guided_save(self) -> None:
        payload = self._base_connector_payload()
        if not payload["connector"]:
            self.set_account_result("Choose a service first.", ok=False)
            return
        secrets: list[dict[str, str]] = []
        for row_widget, _label, input_box, _hint in self._field_rows:
            if not row_widget.isVisible():
                continue
            secret_key = str(row_widget.property("secret_key") or "").strip()
            secret_value = input_box.text().strip()
            if secret_key and secret_value:
                secrets.append({"secret_key": secret_key, "secret_value": secret_value})
        if not secrets:
            self.set_account_result("Add an API key or account details before saving.", ok=False)
            return
        self.connector_guided_link_requested.emit({**payload, "secrets": secrets, "verify_after": True})

    def focus_connector(
        self,
        connector_id: str,
        *,
        provider: str = "",
        account_id: str = "",
        note: str = "",
    ) -> None:
        normalized_connector = str(connector_id or "").strip().lower()
        if not normalized_connector:
            return
        connector_index = self._connector_cb.findData(normalized_connector)
        if connector_index >= 0:
            self._connector_cb.setCurrentIndex(connector_index)
        if provider:
            provider_index = self._provider_cb.findData(str(provider or "").strip().lower())
            if provider_index >= 0:
                self._provider_cb.setCurrentIndex(provider_index)
        if account_id:
            account_index = self._account_cb.findData(str(account_id or "").strip().lower())
            if account_index >= 0:
                self._account_cb.setCurrentIndex(account_index)
        self._sync_account_controls()
        if note:
            self.set_account_result(note, ok=None)
        focus_target = next(
            (
                input_box
                for row_widget, _label, input_box, _hint in self._field_rows
                if row_widget.isVisible()
            ),
            self._provider_cb if self._provider_cb.isVisible() else self._account_cb if self._account_cb.isVisible() else self._connector_cb,
        )
        if focus_target is not None:
            focus_target.setFocus(Qt.FocusReason.OtherFocusReason)
        if self._scroll_area is not None:
            self._scroll_area.ensureWidgetVisible(self, 0, 48)
