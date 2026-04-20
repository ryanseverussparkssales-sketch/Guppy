from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
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

from src.guppy.launcher_application.provider_registry import get_provider
from src.guppy.workspace_governance import secret_field_meta
from .. import tokens as T


def _mono(text: str, color: str = T.DIM, size: int = T.FS_SMALL, bold: bool = False) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {size}pt; letter-spacing: 1px;"
        + (" font-weight: bold;" if bold else "")
    )
    return lbl


def _connector_brand(connector_id: str) -> dict[str, str]:
    normalized = str(connector_id or "").strip().lower()
    brands: dict[str, dict[str, str]] = {
        "gmail": {"badge": "G", "accent": "#d74f3f", "wash": "#fff1ed"},
        "youtube": {"badge": ">", "accent": "#e64b3c", "wash": "#fff0ee"},
        "spotify": {"badge": "S", "accent": "#1f8f55", "wash": "#eefaf2"},
        "outlook": {"badge": "O", "accent": "#2f6df6", "wash": "#eef4ff"},
    }
    return brands.get(normalized, {"badge": "#", "accent": T.PRIMARY, "wash": T.BG0})


def _service_purpose(connector_id: str) -> str:
    return {
        "gmail": "Email",
        "calendar": "Calendar",
        "spotify": "Music",
        "youtube": "Video tools",
        "crm": "Customer records",
        "voip": "Calling",
    }.get(str(connector_id or "").strip().lower(), "Connected service")


def _auth_state_text(auth_state: str) -> str:
    normalized = str(auth_state or "").strip().lower()
    return {
        "ready": "Connected",
        "optional": "Optional",
        "partial": "Finish setup",
        "missing": "Needs setup",
    }.get(normalized, "Needs setup")


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
        self._current_auth_kind = "unknown"
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

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
        for _ in range(3):
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
        summary, install_text, runtime_text, next_text, diagnostics_text = self._friendly_runtime_summary()
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

    def set_account_result(self, text: str, ok: bool = True) -> None:
        self._account_step_lbl.setText(("Latest result: " if ok else "Needs attention: ") + str(text or "").strip())
        self._account_step_lbl.setStyleSheet(
            f"color: {T.GREEN if ok else T.ERROR}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
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

    @staticmethod
    def _selector_label(item: dict[str, object], *, fallback: str) -> str:
        label = str(item.get("label", item.get("id", fallback)) or fallback).strip() or fallback
        auth_state = str(item.get("auth_state", "") or "").strip().upper()
        if auth_state:
            label += f" [{auth_state}]"
        return label

    def _sync_combo(self, combo: QComboBox, rows: list[dict[str, object]], previous: str, placeholder: str) -> None:
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(placeholder, "")
        for row in rows:
            combo.addItem(self._selector_label(row, fallback=placeholder.strip("()")), str(row.get("id", "")))
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
        for index, item in enumerate(self._connector_inventory):
            connector_id = str(item.get("id", "")).strip().lower()
            label = str(item.get("label", connector_id.title()) or connector_id.title())
            auth_state = str(item.get("auth_state", "") or "").strip()
            status = _auth_state_text(auth_state)
            purpose = _service_purpose(connector_id)
            brand = _connector_brand(connector_id)
            button = QPushButton(f"{brand['badge']}  {label}\n{purpose} - {status}")
            button.setCheckable(True)
            button.clicked.connect(lambda _=False, cid=connector_id: self._select_connector_card(cid))
            button.setProperty("connector_id", connector_id)
            self._connector_cards_grid.addWidget(button, index // 3, index % 3)
            self._connector_card_buttons.append((connector_id, button))
        self._refresh_connector_card_styles()

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
            brand = _connector_brand(connector_id)
            button.setChecked(selected)
            button.setStyleSheet(
                self._connector_card_style(
                    selected=selected,
                    ready=ready,
                    accent=brand["accent"],
                    wash=brand["wash"],
                )
            )

    @staticmethod
    def _line_value(text: str) -> str:
        value = str(text or "").strip()
        return value.split(":", 1)[1].strip() if ":" in value else value

    @staticmethod
    def _pipe_fields(text: str) -> dict[str, str]:
        fields: dict[str, str] = {}
        for segment in [part.strip() for part in str(text or "").split("|") if part.strip()]:
            if ":" in segment:
                label, value = segment.split(":", 1)
                fields[label.strip().lower()] = value.strip()
        return fields

    def _friendly_runtime_summary(self) -> tuple[str, str, str, str, str]:
        install_raw = str(self._windows_snapshot.get("install", "") or "")
        runtime_raw = str(self._windows_snapshot.get("runtime", "") or "")
        next_raw = str(self._windows_snapshot.get("next", "") or "")
        runtime_fields = self._pipe_fields(runtime_raw)
        configured = runtime_fields.get("local ai runtime", "local ai").upper()
        live_backend = runtime_fields.get("live backend", configured).upper()
        state = runtime_fields.get("status", "unknown").strip().lower()

        installed_bits: list[str] = []
        if "Ollama CLI: found" in install_raw:
            installed_bits.append("Ollama")
        if "Lemonade CLI: found" in install_raw:
            installed_bits.append("Lemonade")
        if "Packager: ready" in install_raw:
            installed_bits.append("desktop packaging")
        if "Supervisor script: ready" in install_raw:
            installed_bits.append("supervised launch")
        install_text = "Ready on this PC: " + (
            ", ".join(installed_bits) + " are available."
            if installed_bits
            else "Core launcher tools are available."
        )

        if state == "ready":
            runtime_text = f"Local AI health: {live_backend.title()} is healthy and ready on this PC."
            summary = f"{live_backend.title()} is ready on this PC."
        elif state == "unknown":
            runtime_text = f"Local AI health: {configured.title()} is selected, but it still needs a quick Verify check."
            summary = f"{configured.title()} is selected, but it still needs a quick health check."
        else:
            runtime_text = f"Local AI health: {configured.title()} needs attention before you rely on it."
            summary = f"{configured.title()} needs attention before you rely on it."

        next_value = self._line_value(next_raw).lower()
        if "verification passed" in next_value:
            next_text = "Next step: Everything looks okay. Run Verify again after major model or runtime changes."
        elif "build_executable" in next_value or "package" in next_value:
            next_text = "Next step: Use Package when you want a fresh desktop build to share."
        elif next_value:
            next_text = "Next step: " + self._line_value(next_raw)
        else:
            next_text = "Next step: Use Verify to check that your local setup is healthy."

        diagnostics_text = "Health notes: Logs, supervised launch, and repair tools are ready if something goes wrong."
        return summary, install_text, runtime_text, next_text, diagnostics_text

    def _friendly_connector_copy(
        self,
        *,
        item: dict[str, object],
        providers: list[dict[str, object]],
        accounts: list[dict[str, object]],
        fields: list[dict[str, Any]],
    ) -> tuple[str, str, str]:
        label = str(item.get("label", "This service") or "This service")
        purpose = _service_purpose(str(item.get("id", "") or ""))
        auth_kind = str(item.get("auth_kind", "unknown") or "unknown").strip().lower()
        auth_state = str(item.get("auth_state", "missing") or "missing").strip().lower()
        first_field = fields[0] if fields else {}
        first_field_label = str(first_field.get("label", "details") or "details")

        if auth_kind == "api_key":
            status = f"{label} helps with {purpose.lower()} on this PC."
            if auth_state == "optional":
                detail = f"You can keep using basic {label.lower()} features without a key. Adding one makes results more reliable."
            elif auth_state == "ready":
                detail = f"Your {label} API key is saved and ready to use."
            else:
                detail = f"{label} uses a single API key on this PC."
            step = f"Paste your {first_field_label.lower()}, then click Save API Key."
            return status, detail, "Next step: " + step

        if auth_kind == "oauth_file_token":
            status = f"{label} uses browser sign-in for {purpose.lower()}."
            if auth_state == "ready":
                detail = f"{label} is already connected on this PC."
            elif auth_state == "partial":
                detail = f"{label} is almost ready, but browser sign-in still needs to finish."
            else:
                detail = f"{label} still needs the downloaded Google credentials file on this PC before browser sign-in can start."
            if auth_state == "missing":
                step = f"Add the {label.lower()} credentials JSON on this PC, then come back here to sign in."
            elif len(accounts) > 1:
                step = f"Choose the {label} account you want to use, then click Sign In."
            else:
                step = f"Click Sign In to connect {label} on this PC."
            return status, detail, "Next step: " + step

        if auth_kind == "oauth_secret":
            status = f"{label} needs app details before it can sign in."
            if providers and not str(self._provider_cb.currentData() or "").strip():
                return status, f"Choose which {label} provider you use first.", f"Next step: pick your {label} provider."
            detail = f"{label} uses app credentials plus browser sign-in."
            step = f"Add your {first_field_label.lower()}, save it, then use Sign In."
            return status, detail, "Next step: " + step

        if auth_kind == "provider_secret":
            status = f"{label} can connect after you add the provider details for this PC."
            if providers and not str(self._provider_cb.currentData() or "").strip():
                return status, f"Choose which {label} provider you use first.", f"Next step: pick your {label} provider."
            if auth_state in {"ready", "optional"}:
                detail = f"{label} is ready. You can now allow it in a workspace when you need it."
            else:
                detail = f"Enter the provider details Guppy needs for {label.lower()}."
            step = f"Add your {first_field_label.lower()}, then click Save Details."
            return status, detail, "Next step: " + step

        status = f"{label} is available as a connected service."
        detail = "Choose this service to see what sign-in it needs."
        return status, detail, "Next step: pick a service."

    def _current_field_payloads(self) -> list[dict[str, Any]]:
        item = self._current_connector_payload()
        providers = item.get("providers", []) if isinstance(item.get("providers"), list) else []
        selected_provider_id = str(self._provider_cb.currentData() or "").strip().lower()
        selected_provider = next(
            (row for row in providers if isinstance(row, dict) and str(row.get("id", "")).strip().lower() == selected_provider_id),
            {},
        )
        field_details = [row for row in selected_provider.get("field_details", []) if isinstance(row, dict)] if isinstance(selected_provider, dict) else []
        if field_details:
            return field_details[:3]
        return [secret_field_meta(field) for field in item.get("secret_fields", []) if str(field).strip()][:3]

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

        connector_label = str(item.get("label", "Connector") or "Connector")
        auth_kind = str(item.get("auth_kind", "unknown") or "unknown").strip().lower()
        auth_state = str(item.get("auth_state", "missing") or "missing").strip().lower()
        self._current_auth_kind = auth_kind
        self._refresh_connector_card_styles()

        for row_widget, label, input_box, hint in self._field_rows:
            row_widget.setVisible(False)
            label.setText("")
            input_box.clear()
            hint.setText("")
            input_box.setPlaceholderText("")
            input_box.setEchoMode(QLineEdit.EchoMode.Normal)

        for idx, field in enumerate(self._current_field_payloads()):
            row_widget, label, input_box, hint = self._field_rows[idx]
            label.setText(str(field.get("label", field.get("key", "Credential")) or "Credential"))
            input_box.setPlaceholderText(str(field.get("placeholder", "") or ""))
            input_box.setEchoMode(QLineEdit.EchoMode.Password if bool(field.get("masked", True)) else QLineEdit.EchoMode.Normal)
            hint_text = str(field.get("input_hint", "") or field.get("validation_hint", "") or "").strip()
            hint.setText(hint_text)
            row_widget.setVisible(True)
            row_widget.setProperty("secret_key", str(field.get("key", "") or ""))

        field_payloads = self._current_field_payloads()
        friendly_status, friendly_detail, friendly_step = self._friendly_connector_copy(
            item=item,
            providers=providers,
            accounts=accounts,
            fields=field_payloads,
        )
        self._account_status_lbl.setText(friendly_status)
        self._account_detail_lbl.setText(friendly_detail)
        self._account_step_lbl.setText(friendly_step)
        self._account_step_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )

        connector_id = str(item.get("id", "") or "").strip().lower()
        is_verified = auth_state in {"ready", "optional"}
        registry_entry = get_provider(connector_id)
        hint_text = (registry_entry.next_step_hint if registry_entry else "").strip()
        if is_verified and hint_text:
            self._next_step_hint_lbl.setText(f"Connected — {hint_text}")
            self._next_step_hint_lbl.setVisible(True)
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

    def _base_connector_payload(self) -> dict[str, str]:
        return {
            "connector": str(self._connector_cb.currentData() or "").strip(),
            "provider": str(self._provider_cb.currentData() or "").strip(),
            "account_id": str(self._account_cb.currentData() or "").strip(),
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
