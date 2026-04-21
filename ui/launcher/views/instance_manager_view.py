from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget

from src.guppy.launcher_application.instance_manager_presenter import (
    build_connector_binding_editor_state,
    build_connector_binding_save_request,
    build_governance_editor_state,
    build_instance_manager_state,
    build_save_affordance_state,
    build_section_toggle_state,
    build_selector_state,
    build_workspace_activity_log_text,
    build_workspace_create_copy,
    build_workspace_create_form_state,
    build_workspace_create_request,
    build_connector_binding_feedback,
    build_governance_save_request,
    build_workspace_editors_state,
    connector_history_line,
    selector_label,
)
from .. import tokens as T
from .instance_manager_sections import InstanceCard, build_instance_manager_shell


class InstanceManagerView(QWidget):
    refresh_requested = Signal()
    activate_requested = Signal(str)
    delete_requested = Signal(str)
    create_requested = Signal(dict)
    logs_requested = Signal(str)
    governance_save_requested = Signal(dict)
    connector_binding_save_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._known_names: set[str] = set()
        self._configured = 0
        self._max_configured = 5
        self._active_runtime = 0
        self._max_active_runtime = 2
        self._governance_by_name: dict[str, dict[str, object]] = {}
        self._connectors_by_name: dict[str, dict[str, dict[str, object]]] = {}
        self._governance_visible = False
        self._connector_bindings_visible = False
        self._last_role_copy = build_workspace_create_copy("user_instance")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        shell = build_instance_manager_shell()
        for name, value in shell.__dict__.items():
            setattr(self, f"_{name}", value)
        outer.addWidget(self._scroll)

        self._name.textChanged.connect(self._sync_save_affordance)
        self._type.currentTextChanged.connect(self._apply_role_preset)
        self._governance_workspace.currentTextChanged.connect(self._load_governance_editor)
        self._connector_workspace.currentTextChanged.connect(self._load_connector_binding_editor)
        self._connector_id.currentTextChanged.connect(self._load_connector_binding_editor)
        self._connector_provider.currentIndexChanged.connect(self._refresh_connector_binding_feedback)
        self._connector_account.currentIndexChanged.connect(self._refresh_connector_binding_feedback)
        self._connector_enabled.stateChanged.connect(self._refresh_connector_binding_feedback)
        self._governance_toggle_btn.clicked.connect(self._toggle_governance_section)
        self._connector_toggle_btn.clicked.connect(self._toggle_connector_bindings_section)
        self._governance_save_btn.clicked.connect(self._emit_governance_save)
        self._connector_save_btn.clicked.connect(self._emit_connector_binding_save)
        self._refresh_btn.clicked.connect(self.refresh_requested.emit)
        self._save_btn.clicked.connect(self._emit_create)
        self._apply_role_preset(self._type.currentText())
        self._sync_save_affordance()

    def _emit_create(self) -> None:
        request = build_workspace_create_request(
            name=self._name.text(),
            description=self._description.text(),
            mode=self._mode.currentText(),
            persona=str(self._persona.currentData() or self._persona.currentText()),
            voice=str(self._voice.currentData() or self._voice.currentText()),
            workspace_type=self._type.currentText(),
            enabled=self._enabled.isChecked(),
        )
        self.create_requested.emit(request.as_payload())

    def _toggle_governance_section(self) -> None:
        state = build_section_toggle_state(
            not self._governance_visible,
            show_label="SHOW ACCESS RULES",
            hide_label="HIDE ACCESS RULES",
        )
        self._governance_visible = state.visible
        self._governance_frame.setVisible(state.visible)
        self._governance_toggle_btn.setText(state.button_label)

    def _toggle_connector_bindings_section(self) -> None:
        state = build_section_toggle_state(
            not self._connector_bindings_visible,
            show_label="SHOW CONNECTOR RULES",
            hide_label="HIDE CONNECTOR RULES",
        )
        self._connector_bindings_visible = state.visible
        self._connectors_frame.setVisible(state.visible)
        self._connector_toggle_btn.setText(state.button_label)

    @staticmethod
    def _selector_label(item: dict[str, object], *, fallback: str) -> str:
        return selector_label(item, fallback=fallback)

    @staticmethod
    def _history_line(payload: dict[str, object]) -> str:
        return connector_history_line(payload)

    def _apply_role_preset(self, workspace_type: str) -> None:
        form_state = build_workspace_create_form_state(
            workspace_type=workspace_type,
            current_description=self._description.text(),
            current_mode=self._mode.currentText(),
            previous_copy=self._last_role_copy,
        )
        copy = form_state.copy
        self._name.setPlaceholderText(copy.name_placeholder)
        self._description.setPlaceholderText(copy.description_placeholder)
        self._preset_lbl.setText(copy.preset_summary)
        self._recipe_lbl.setText(copy.first_run_recipe)
        self._examples_lbl.setText(copy.example_names)
        if form_state.description_value is not None:
            self._description.setText(form_state.description_value)
        if form_state.mode_value is not None:
            idx = self._mode.findText(form_state.mode_value)
            if idx >= 0:
                self._mode.setCurrentIndex(idx)
        self._last_role_copy = copy

    @staticmethod
    def _apply_selector(combo: QComboBox, state) -> None:
        combo.blockSignals(True)
        combo.clear()
        for option in state.options:
            combo.addItem(option)
        if state.selected_value:
            idx = combo.findText(state.selected_value)
            combo.setCurrentIndex(max(0, idx))
        combo.blockSignals(False)

    def _apply_governance_editor_state(self, state) -> None:
        auth_index = max(0, self._governance_auth_mode.findText(state.auth_mode))
        self._governance_auth_mode.setCurrentIndex(auth_index)
        self._governance_note.setText(state.policy_note)
        self._tool_allow.setPlainText(state.tool_allow_text)
        self._tool_block.setPlainText(state.tool_block_text)
        self._endpoint_allow.setPlainText(state.endpoint_allow_text)
        self._endpoint_block.setPlainText(state.endpoint_block_text)
        self._governance_status.setText(state.status_text)

    def _apply_connector_editor_state(self, state) -> None:
        self._apply_selector(
            self._connector_id,
            build_selector_state(state.connector_ids, state.selected_connector_id),
        )
        self._connector_enabled.setChecked(state.enabled)
        self._connector_provider.blockSignals(True)
        self._connector_provider.clear()
        for option in state.provider_options:
            self._connector_provider.addItem(option.label, option.value)
        provider_idx = self._connector_provider.findData(state.selected_provider)
        self._connector_provider.setCurrentIndex(0 if provider_idx < 0 else provider_idx)
        self._connector_provider.blockSignals(False)
        self._connector_account.blockSignals(True)
        self._connector_account.clear()
        for option in state.account_options:
            self._connector_account.addItem(option.label, option.value)
        account_idx = self._connector_account.findData(state.selected_account)
        self._connector_account.setCurrentIndex(0 if account_idx < 0 else account_idx)
        self._connector_account.blockSignals(False)
        self._connector_action_allow.setPlainText(state.action_allow_text)
        self._connector_action_block.setPlainText(state.action_block_text)
        self._connector_endpoint_allow.setPlainText(state.endpoint_allow_text)
        self._connector_endpoint_block.setPlainText(state.endpoint_block_text)
        self._connector_note.setText(state.note)
        self._connector_status.setText(state.status_text)
        self._connector_validation.setText(state.validation_text)
        self._connector_history.setText(state.history_text)

    def _load_governance_editor(self, workspace_name: str) -> None:
        state = build_governance_editor_state(workspace_name, self._governance_by_name)
        self._apply_governance_editor_state(state)

    def _emit_governance_save(self) -> None:
        target = self._governance_workspace.currentText().strip()
        request, error = build_governance_save_request(
            target=target,
            policy=self._governance_by_name.get(target, {}),
            auth_mode=self._governance_auth_mode.currentText(),
            tool_allow_text=self._tool_allow.toPlainText(),
            tool_block_text=self._tool_block.toPlainText(),
            endpoint_allow_text=self._endpoint_allow.toPlainText(),
            endpoint_block_text=self._endpoint_block.toPlainText(),
            policy_note=self._governance_note.text(),
        )
        if request is None:
            self.set_governance_status(error, ok=False)
            return
        self.governance_save_requested.emit(request.as_payload())

    def _load_connector_binding_editor(self, _value: str) -> None:
        workspace_name = self._connector_workspace.currentText().strip()
        state = build_connector_binding_editor_state(
            workspace_name,
            self._connector_id.currentText().strip().lower(),
            self._connectors_by_name,
        )
        self._apply_connector_editor_state(state)

    def _refresh_connector_binding_feedback(self, *_args) -> None:
        workspace_name = self._connector_workspace.currentText().strip()
        connector_id = self._connector_id.currentText().strip().lower()
        connector_payload = self._connectors_by_name.get(workspace_name, {}).get(connector_id, {})
        validation_text, history_text = build_connector_binding_feedback(
            connector_payload,
            enabled=self._connector_enabled.isChecked(),
            selected_provider=str(self._connector_provider.currentData() or "").strip().lower(),
            selected_account=str(self._connector_account.currentData() or "").strip().lower(),
        )
        self._connector_validation.setText(validation_text)
        self._connector_history.setText(history_text)

    def _emit_connector_binding_save(self) -> None:
        request, error = build_connector_binding_save_request(
            workspace_name=self._connector_workspace.currentText(),
            connector_id=self._connector_id.currentText(),
            enabled=self._connector_enabled.isChecked(),
            account_id=str(self._connector_account.currentData() or ""),
            provider=str(self._connector_provider.currentData() or ""),
            action_allow_text=self._connector_action_allow.toPlainText(),
            action_block_text=self._connector_action_block.toPlainText(),
            endpoint_allow_text=self._connector_endpoint_allow.toPlainText(),
            endpoint_block_text=self._connector_endpoint_block.toPlainText(),
            note=self._connector_note.text(),
        )
        if request is None:
            self.set_connector_binding_status(error, ok=False)
            return
        self.connector_binding_save_requested.emit(request.as_payload())

    def set_persona_options(self, options: list[tuple[str, str]], selected: str | None = None) -> None:
        target = str(selected or self._persona.currentData() or self._persona.currentText()).strip().lower()
        normalized = [(str(label).strip() or str(value).strip(), str(value).strip()) for label, value in options if str(value).strip()]
        if not normalized:
            normalized = [("Guppy", "guppy")]
        self._persona.blockSignals(True)
        self._persona.clear()
        for label, value in normalized:
            self._persona.addItem(label, value)
        index = 0
        for idx in range(self._persona.count()):
            if str(self._persona.itemData(idx) or "").strip().lower() == target:
                index = idx
                break
        self._persona.setCurrentIndex(index)
        self._persona.blockSignals(False)

    def set_voice_options(self, options: list[tuple[str, str]], selected: str | None = None) -> None:
        target = str(selected or self._voice.currentData() or self._voice.currentText()).strip().lower()
        normalized = [(str(label).strip() or str(value).strip(), str(value).strip()) for label, value in options if str(value).strip()]
        if not normalized:
            normalized = [("Default", "default")]
        self._voice.blockSignals(True)
        self._voice.clear()
        for label, value in normalized:
            self._voice.addItem(label, value)
        index = 0
        for idx in range(self._voice.count()):
            if str(self._voice.itemData(idx) or "").strip().lower() == target:
                index = idx
                break
        self._voice.setCurrentIndex(index)
        self._voice.blockSignals(False)

    def _sync_save_affordance(self) -> None:
        state = build_save_affordance_state(
            candidate_name=self._name.text(),
            known_names=self._known_names,
            configured=self._configured,
            max_configured=self._max_configured,
        )
        self._save_btn.setEnabled(state.enabled)
        if state.warning_text:
            self._status_lbl.setText(state.warning_text)
            self._status_lbl.setStyleSheet(
                f"color: {T.ERROR}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
            )

    def set_status(self, text: str, ok: bool = True) -> None:
        color = T.GREEN if ok else T.ERROR
        self._status_lbl.setText(text)
        self._status_lbl.setStyleSheet(
            f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )

    def set_governance_status(self, text: str, ok: bool = True) -> None:
        color = T.GREEN if ok else T.ERROR
        self._governance_status.setText(text)
        self._governance_status.setStyleSheet(
            f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )

    def set_connector_binding_status(self, text: str, ok: bool = True) -> None:
        color = T.GREEN if ok else T.ERROR
        self._connector_status.setText(text)
        self._connector_status.setStyleSheet(
            f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )

    def set_instances(self, payload: dict[str, object]) -> None:
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        state = build_instance_manager_state(
            payload,
            previous_governance_workspace=self._governance_workspace.currentText().strip(),
            previous_connector_workspace=self._connector_workspace.currentText().strip(),
            previous_connector_id=self._connector_id.currentText().strip().lower(),
        )
        editors_state = build_workspace_editors_state(state)
        self._known_names = set(state.ordered_names)
        self._governance_by_name = state.governance_map
        self._connectors_by_name = state.connector_map
        self._apply_selector(self._governance_workspace, editors_state.governance_workspace)
        self._apply_governance_editor_state(editors_state.governance_editor)

        self._apply_selector(self._connector_workspace, editors_state.connector_workspace)
        self._apply_connector_editor_state(editors_state.connector_editor)

        self._configured = state.configured
        self._max_configured = state.max_configured
        self._active_runtime = state.active_runtime
        self._max_active_runtime = state.max_active_runtime
        self._summary_lbl.setText(state.summary_text)
        self._limits_lbl.setText(state.limits_text)
        self._role_mix_lbl.setText(state.role_mix_text)
        self._collab_lbl.setText(state.collaboration_text)
        self._recurring_lbl.setText(state.recurring_text)
        self._empty_state_lbl.setVisible(state.show_empty_state)
        if state.show_empty_state:
            empty_card = QLabel(
                state.empty_state_text
            )
            empty_card.setWordWrap(True)
            empty_card.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            empty_card.setStyleSheet(
                f"color: {T.DIM}; background-color: {T.BG1}; border: 1px dashed {T.BORDER};"
                f" padding: 14px; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;"
            )
            self._cards_layout.addWidget(empty_card)

        for item in state.items:
            card = InstanceCard(item, str(item.get("name", "")).strip() == state.active_instance)
            card.activate_requested.connect(self.activate_requested.emit)
            card.delete_requested.connect(self.delete_requested.emit)
            card.logs_requested.connect(self.logs_requested.emit)
            self._cards_layout.addWidget(card)

        self._cards_layout.addStretch()
        self._sync_save_affordance()

    def set_logs(self, instance_name: str, entries: list[dict[str, object]]) -> None:
        self._logs.setPlainText(build_workspace_activity_log_text(instance_name, entries))
