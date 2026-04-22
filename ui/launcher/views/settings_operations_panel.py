"""Settings-owned operations panel extracted from the prior advanced surface."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QResizeEvent, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.guppy.experience_config import configured_local_runtime_backend
from src.guppy.launcher_application.embedded_terminal import EmbeddedTerminalSession
from src.guppy.launcher_application.app_mgmt_presenter import (
    build_daily_context_state,
    build_instance_snapshot_state,
)
from src.guppy.launcher_application.operator_logs import build_operator_log_lines, read_launcher_events
from src.guppy.launcher_application.settings_operations_presenter import build_operations_density_state
from src.guppy.launcher_application.terminal_recipes import build_tracked_terminal_recipe
from src.guppy.launcher_application.windows_ops_presenter import (
    apply_windows_ops_feedback,
)
from src.guppy.launcher_application.workflows import list_workflow_specs
from .settings_connector_panel import (
    current_connector_payload as panel_current_connector_payload,
    emit_connector_action as panel_emit_connector_action,
    set_connector_inventory as panel_set_connector_inventory,
    sync_connector_controls as panel_sync_connector_controls,
)
from .settings_terminal_panel import (
    append_terminal_output as panel_append_terminal_output,
    apply_workflow_panel_state as panel_apply_workflow_panel_state,
    drain_terminal_queue as panel_drain_terminal_queue,
    focus_terminal as panel_focus_terminal,
    handle_terminal_recipe_marker as panel_handle_terminal_recipe_marker,
    load_workflow_recipe as panel_load_workflow_recipe,
    run_terminal_commands as panel_run_terminal_commands,
    run_workflow_recipe as panel_run_workflow_recipe,
    stop_terminal_process as panel_stop_terminal_process,
    submit_terminal_command as panel_submit_terminal_command,
    sync_workflow_recipe as panel_sync_workflow_recipe,
)
from .settings_snapshot_panel import (
    apply_automation_snapshot as panel_apply_automation_snapshot,
    apply_recovery_status as panel_apply_recovery_status,
    apply_status_snapshot as panel_apply_status_snapshot,
    build_windows_ops_snapshot as panel_build_windows_ops_snapshot,
    refresh_windows_ops_labels as panel_refresh_windows_ops_labels,
    refresh_windows_ops_snapshot as panel_refresh_windows_ops_snapshot,
    set_automation_status as panel_set_automation_status,
)
from .settings_operations_sections import (
    build_automation_test_section as panel_build_automation_test_section,
    build_connected_services_section as panel_build_connected_services_section,
    build_windows_runtime_section as panel_build_windows_runtime_section,
)
from .settings_workflow_terminal_sections import (
    build_operator_logs_section as panel_build_operator_logs_section,
    build_terminal_section as panel_build_terminal_section,
    build_workflow_section as panel_build_workflow_section,
)

from .. import tokens as T

_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _mono(text: str, color: str = T.DIM, size: int = T.FS_SMALL, bold: bool = False) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}';"
        f"font-size: {size}pt; letter-spacing: 1px;"
        + ("font-weight: bold;" if bold else "")
    )
    return lbl


class SettingsOperationsPanel(QWidget):
    recovery_requested = Signal(str)
    windows_ops_requested = Signal(str)
    connector_action_requested = Signal(dict)
    automation_action_requested = Signal(str)
    terminal_recipe_finished = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._diagnostics: dict[str, str] = {}
        self._log_filter = "ALL"
        self._details_visible = False
        self._terminal_session = EmbeddedTerminalSession(root=_ROOT)
        self._terminal_recipes = self._terminal_session.recipes
        self._windows_ops: dict[str, str] = self._build_windows_ops_snapshot()
        self._connector_inventory: list[dict[str, object]] = []
        self._detail_frames: list[QFrame] = []
        self._detail_widgets: list[QWidget] = []
        self._quick_fix_buttons: dict[str, QPushButton] = {}
        self._windows_action_buttons: dict[str, QPushButton] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(20)

        # Page title
        header_frame = QFrame()
        header_frame.setObjectName("appmgmt_header")
        header_frame.setStyleSheet(
            f"QFrame#appmgmt_header {{ background-color: rgba(255,255,255,0.60); border: 1px solid rgba(214,197,174,0.46); border-radius: 28px; }}"
        )
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(20, 18, 20, 18)
        header_layout.setSpacing(12)

        title_row = QHBoxLayout()
        title = QLabel("Settings & System")
        title.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_HEAD}';"
            f"font-size: 28pt; font-weight: 700; letter-spacing: -1px;"
        )
        title_row.addWidget(title)
        title_row.addStretch()
        self._details_btn = QPushButton("ADVANCED")
        self._details_btn.setToolTip("Show deeper diagnostics, connectors, and terminal lanes")
        self._details_btn.setAccessibleName("Advanced details")
        self._details_btn.setAccessibleDescription("Shows or hides advanced operational controls")
        self._details_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(255,255,255,0.88); color: {T.DIM}; border: 1px solid {T.BORDER_SOFT}; border-radius: 4px;"
            f" padding: 5px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: {T.ACCENT_TEAL}; color: {T.ACCENT_TEAL}; }}"
        )
        self._details_btn.clicked.connect(self._toggle_details)
        title_row.addWidget(self._details_btn)
        header_layout.addLayout(title_row)

        # sub-info
        info_row = QHBoxLayout()
        info_row.setSpacing(8)
        dot = QLabel("•")
        dot.setStyleSheet(f"color: {T.ACCENT_ORANGE}; font-size: {T.FS_TINY}pt;")
        info_row.addWidget(dot)
        info_row.addWidget(_mono("SETTINGS + RECOVERY", T.PRIMARY, T.FS_TINY, True))
        info_row.addSpacing(12)
        self._header_scope_lbl = _mono("SYSTEM HEALTH / CONNECTORS / AUTOMATION / DESKTOP RUNTIME", T.DIM, T.FS_TINY)
        info_row.addWidget(self._header_scope_lbl)
        info_row.addStretch()
        header_layout.addLayout(info_row)
        subtitle = _mono(
            "Keep setup, connectors, health, recovery, and machine operations in one secondary surface. Use details only when you need the deeper system lanes. Models and voices now live in the Models hub.",
            T.DIM,
            T.FS_SMALL,
        )
        subtitle.setWordWrap(True)
        header_layout.addWidget(subtitle)
        layout.addWidget(header_frame)

        self._boundary_frame = QFrame()
        self._boundary_frame.setStyleSheet(
            f"QFrame {{ background: rgba(244,239,231,0.82); border: 1px solid rgba(214,197,174,0.52); border-radius: 22px; }}"
        )
        boundary_layout = QVBoxLayout(self._boundary_frame)
        boundary_layout.setContentsMargins(16, 14, 16, 14)
        boundary_layout.setSpacing(8)
        boundary_layout.addWidget(_mono("BOUNDARY", T.PRIMARY, T.FS_TINY, True))
        boundary_layout.addWidget(_mono("Open this tab for app-wide setup, recovery, diagnostics, workflow loops, logs, account linking, and system configuration. Models, runtime loadouts, and voices stay in the Models hub.", T.DIM, T.FS_SMALL))
        layout.addWidget(self._boundary_frame)
        self._detail_frames.append(self._boundary_frame)

        context_frame = QFrame()
        context_frame.setStyleSheet(
            f"QFrame {{ background: rgba(255,255,255,0.70); border: 1px solid rgba(214,197,174,0.48); border-radius: 22px; }}"
        )
        context_layout = QVBoxLayout(context_frame)
        context_layout.setContentsMargins(16, 16, 16, 16)
        context_layout.setSpacing(10)
        context_layout.addWidget(_mono("DAILY SESSION CONTEXT", T.PRIMARY, T.FS_TINY, True))
        context_layout.addWidget(
            _mono(
                "Chat stays focused on conversation. This page keeps setup, health, and recovery in one place.",
                T.DIM,
                T.FS_SMALL,
            )
        )
        self._daily_activity_lbl = _mono("Recent activity: launcher ready", T.DIM, T.FS_SMALL)
        self._daily_workspace_lbl = _mono("Current workspace: Daily assistant workspace", T.TEXT, T.FS_SMALL)
        self._daily_runtime_lbl = _mono("Ready now: waiting for first status poll", T.DIM, T.FS_SMALL)
        self._daily_route_lbl = _mono("Route preview: waiting for your next message", T.DIM, T.FS_SMALL)
        self._daily_recovery_lbl = _mono("Recovery: all clear", T.GREEN, T.FS_SMALL)
        for widget in (
            self._daily_activity_lbl,
            self._daily_workspace_lbl,
            self._daily_runtime_lbl,
            self._daily_route_lbl,
            self._daily_recovery_lbl,
        ):
            widget.setWordWrap(True)
            context_layout.addWidget(widget)
        layout.addWidget(context_frame)

        actions_frame = QFrame()
        actions_frame.setStyleSheet(
            f"QFrame {{ background: rgba(255,255,255,0.70); border: 1px solid rgba(214,197,174,0.48); border-radius: 22px; }}"
        )
        actions_layout = QVBoxLayout(actions_frame)
        actions_layout.setContentsMargins(16, 16, 16, 16)
        actions_layout.setSpacing(12)
        actions_layout.addWidget(_mono("QUICK FIXES", T.PRIMARY, T.FS_TINY, True))

        self._recovery_status = _mono("Nothing needs attention right now.", T.DIM, T.FS_TINY)
        actions_layout.addWidget(self._recovery_status)

        action_row = QHBoxLayout()
        for label, action, accent in [
            ("SNAPSHOT", "health_snapshot", T.PRIMARY),
            ("WARMUP", "warmup", T.PRIMARY_DIM),
            ("RESTART DAEMON", "restart_daemon", T.ERROR),
            ("AUDIT RUNTIME", "audit_runtime", T.SECONDARY),
        ]:
            btn = QPushButton(label)
            btn.setToolTip(
                {
                    "health_snapshot": "Refresh launcher health and readiness details.",
                    "warmup": "Run the safe warmup flow for the runtime.",
                    "restart_daemon": "Restart the background runtime process when it is stuck.",
                    "audit_runtime": "Run a deeper runtime audit and capture findings.",
                }[action]
            )
            btn.setStyleSheet(
                f"QPushButton {{ background: {T.BG0}; color: {accent}; border: 1px solid {accent};"
                f" padding: 5px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ background: {accent}; color: {T.BG}; }}"
            )
            btn.clicked.connect(lambda _=False, a=action: self.recovery_requested.emit(a))
            self._quick_fix_buttons[action] = btn
            action_row.addWidget(btn)
        action_row.addStretch()
        actions_layout.addLayout(action_row)
        layout.addWidget(actions_frame)

        diag_frame = QFrame()
        diag_frame.setStyleSheet(
            f"QFrame {{ background: rgba(255,255,255,0.70); border: 1px solid rgba(214,197,174,0.48); border-radius: 22px; }}"
        )
        diag_layout = QVBoxLayout(diag_frame)
        diag_layout.setContentsMargins(16, 16, 16, 16)
        diag_layout.setSpacing(12)
        diag_layout.addWidget(_mono("SYSTEM STATUS", T.PRIMARY, T.FS_TINY, True))
        self._health_lbl = _mono("API health: unknown", T.DIM, T.FS_SMALL)
        self._instances_lbl = _mono("Workspaces: unknown", T.DIM, T.FS_SMALL)
        self._voice_lbl = _mono("Voice services: unknown", T.DIM, T.FS_SMALL)
        self._route_health_lbl = _mono("Route evidence: unknown", T.DIM, T.FS_SMALL)
        self._resource_lbl = _mono("Resource envelope: unknown", T.DIM, T.FS_SMALL)
        self._last_recovery_lbl = _mono("Last recovery action: idle", T.DIM, T.FS_SMALL)
        for widget in [
            self._health_lbl,
            self._instances_lbl,
            self._voice_lbl,
            self._route_health_lbl,
            self._resource_lbl,
            self._last_recovery_lbl,
        ]:
            widget.setWordWrap(True)
            diag_layout.addWidget(widget)
        layout.addWidget(diag_frame)

        panel_build_windows_runtime_section(self, layout, _mono)
        panel_build_connected_services_section(self, layout, _mono)
        panel_build_automation_test_section(self, layout, _mono)

        panel_build_workflow_section(self, layout, _mono)
        panel_build_operator_logs_section(self, layout, _mono)
        panel_build_terminal_section(self, layout, _mono)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

        timer = QTimer(self)
        timer.timeout.connect(self._refresh_operator_logs)
        timer.start(4000)
        self._refresh_operator_logs()

        self._terminal_timer = QTimer(self)
        self._terminal_timer.timeout.connect(self._drain_terminal_queue)
        self._terminal_timer.start(150)
        self._sync_workflow_recipe()
        self.set_automation_snapshot({})
        self._refresh_windows_ops_labels()
        self._detail_widgets.extend(
            [
                self._daily_route_lbl,
                self._daily_recovery_lbl,
                self._instances_lbl,
                self._voice_lbl,
                self._route_health_lbl,
                self._resource_lbl,
                self._last_recovery_lbl,
                self._windows_paths_lbl,
                self._windows_update_lbl,
                self._windows_diagnostics_lbl,
                self._windows_entry_lbl,
                self._windows_change_lbl,
                self._windows_gate_lbl,
                self._windows_gate_fix_lbl,
                self._windows_handoff_lbl,
            ]
        )
        self._sync_detail_visibility()

    def showEvent(self, event: QShowEvent) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._apply_density_mode(self.width())

    def resizeEvent(self, event: QResizeEvent) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self.isVisible():
            self._apply_density_mode(event.size().width())

    def _apply_density_mode(self, width: int) -> None:
        density = build_operations_density_state(width, self._details_visible)
        self._header_scope_lbl.setVisible(density.header_scope_visible)
        self._details_btn.setText(density.details_button_text)
        self._automation_summary_lbl.setVisible(density.automation_summary_visible)
        self._workflow_evidence_lbl.setVisible(density.workflow_evidence_visible)
        self._terminal_input.setPlaceholderText(density.terminal_placeholder)
        for action, text in density.quick_fix_labels.items():
            self._quick_fix_buttons[action].setText(text)
        for action, text in density.windows_action_labels.items():
            self._windows_action_buttons[action].setText(text)
        for action, text in density.automation_action_labels.items():
            self._automation_action_buttons[action].setText(text)
        self._workflow_load_btn.setText(density.workflow_load_text)
        self._workflow_run_btn.setText(density.workflow_run_text)

    def _toggle_details(self) -> None:
        self._details_visible = not self._details_visible
        self._sync_detail_visibility()

    def _sync_detail_visibility(self) -> None:
        for frame in self._detail_frames:
            frame.setVisible(self._details_visible)
        for widget in self._detail_widgets:
            widget.setVisible(self._details_visible)
        for button in self._windows_detail_buttons:
            button.setVisible(self._details_visible)
        self._details_btn.setText("LESS ADVANCED" if self._details_visible else "ADVANCED")
        self._details_btn.setToolTip(
            "Hide deeper diagnostics, connectors, and terminal lanes"
            if self._details_visible
            else "Show deeper diagnostics, connectors, and terminal lanes"
        )
        if self.isVisible():
            self._apply_density_mode(self.width())

    def append_log(self, line: str) -> None:
        current = self._syslog.toPlainText().splitlines()
        current.append(f"> {line}")
        self._syslog.setPlainText("\n".join(current[-40:]))

    def set_recovery_status(self, text: str) -> None:
        panel_apply_recovery_status(self, text, root=_ROOT)

    def set_daily_context_activity(self, text: str) -> None:
        self._daily_activity_lbl.setText(build_daily_context_state(activity=text).activity_text)

    def set_daily_context_workspace(self, text: str) -> None:
        self._daily_workspace_lbl.setText(build_daily_context_state(workspace=text).workspace_text)

    def set_daily_context_runtime(self, text: str) -> None:
        self._daily_runtime_lbl.setText(build_daily_context_state(runtime=text).runtime_text)

    def set_daily_context_route(self, text: str) -> None:
        self._daily_route_lbl.setText(build_daily_context_state(route=text).route_text)

    def set_daily_context_recovery(self, text: str, ok: bool = True) -> None:
        state = build_daily_context_state(recovery=text, recovery_ok=ok)
        self._daily_recovery_lbl.setText(state.recovery_text)
        self._daily_recovery_lbl.setStyleSheet(
            f"color: {T.GREEN if ok else T.ERROR}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_SMALL}pt; letter-spacing: 1px;"
        )

    def set_status_snapshot(self, payload: dict[str, object]) -> None:
        panel_apply_status_snapshot(self, payload, root=_ROOT)

    def set_instance_snapshot(self, payload: dict[str, object]) -> None:
        self._instances_lbl.setText(build_instance_snapshot_state(payload).instances_text)

    def set_automation_snapshot(self, payload: dict[str, object]) -> None:
        panel_apply_automation_snapshot(self, payload)

    def set_automation_status(self, text: str, ok: bool = True) -> None:
        panel_set_automation_status(self, text, ok=ok)

    def _set_workflow_status(self, text: str, ok: bool = True) -> None:
        color = T.GREEN if ok else T.ERROR
        self._workflow_status_lbl.setText(text)
        self._workflow_status_lbl.setStyleSheet(
            f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )

    def set_connector_inventory(self, items: list[dict[str, object]]) -> None:
        panel_set_connector_inventory(self, items)

    def _current_connector_payload(self) -> dict[str, object]:
        return panel_current_connector_payload(self)

    def _sync_connector_controls(self) -> None:
        panel_sync_connector_controls(self)

    def _emit_connector_action(self, action: str) -> None:
        panel_emit_connector_action(self, action)

    def _set_log_filter(self, value: str) -> None:
        self._log_filter = (value or "ALL").strip().upper() or "ALL"
        self._refresh_operator_logs()

    def _configured_local_runtime_backend(self) -> str:
        return configured_local_runtime_backend()

    def _build_windows_ops_snapshot(self) -> dict[str, str]:
        return panel_build_windows_ops_snapshot(self, root=_ROOT)

    def _refresh_windows_ops_labels(self) -> None:
        panel_refresh_windows_ops_labels(self)

    def refresh_windows_ops_snapshot(self) -> None:
        panel_refresh_windows_ops_snapshot(self, root=_ROOT)

    def windows_ops_snapshot(self) -> dict[str, str]:
        return dict(self._windows_ops)

    def set_windows_ops_feedback(
        self,
        action: str,
        summary: str,
        changes: str,
        ok: bool = True,
        *,
        next_step: str = "",
        fix_target: str = "",
        docs_hint: str = "",
        entry_point: str = "",
        artifacts: list[dict[str, object]] | None = None,
        receipt_path: str = "",
        summary_path: str = "",
        gate_summary: str = "",
        gate_detail: str = "",
        gate_recommendations: list[str] | None = None,
        gate_recommendation_details: list[dict[str, object]] | None = None,
        review_order: list[str] | None = None,
    ) -> None:
        self._windows_ops = apply_windows_ops_feedback(
            self._windows_ops,
            action=action,
            summary=summary,
            changes=changes,
            ok=ok,
            next_step=next_step,
            fix_target=fix_target,
            docs_hint=docs_hint,
            entry_point=entry_point,
            artifacts=artifacts,
            receipt_path=receipt_path,
            summary_path=summary_path,
            gate_summary=gate_summary,
            gate_detail=gate_detail,
            gate_recommendations=gate_recommendations,
            gate_recommendation_details=gate_recommendation_details,
            review_order=review_order,
            root=_ROOT,
        )
        self._refresh_windows_ops_labels()

    def focus_operator_logs(self, log_filter: str = "ALL", note: str = "") -> None:
        if not self._details_visible:
            self._details_visible = True
            self._sync_detail_visibility()
        target = (log_filter or "ALL").strip().upper() or "ALL"
        idx = self._filter_cb.findText(target)
        if idx >= 0:
            self._filter_cb.setCurrentIndex(idx)
        else:
            self._set_log_filter(target)
        if note:
            self.append_log(note)

    def focus_terminal(self, note: str = "") -> None:
        panel_focus_terminal(self, note)

    def focus_automation_test(self, note: str = "") -> None:
        if note:
            self.set_automation_status(note)
        button = self._automation_action_buttons.get("verify_now")
        if button is not None:
            button.setFocus()

    def queue_terminal_recipe(
        self,
        commands: list[str],
        *,
        label: str,
        recipe_context: dict[str, object] | None = None,
    ) -> bool:
        return self._run_terminal_commands(commands, label=label, recipe_context=recipe_context)

    def _build_tracked_recipe_commands(
        self,
        commands: list[str],
        *,
        label: str,
        recipe_context: dict[str, object] | None = None,
    ) -> tuple[str, tuple[str, ...]]:
        plan = build_tracked_terminal_recipe(
            commands,
            label=label,
            recipe_context=recipe_context or {},
        )
        self._terminal_recipes[plan.recipe_id] = dict(plan.context)
        return plan.recipe_id, plan.wrapped_commands

    def _apply_workflow_panel_state(self, state) -> None:
        panel_apply_workflow_panel_state(self, state)

    def _sync_workflow_recipe(self) -> None:
        panel_sync_workflow_recipe(self)

    def _load_workflow_recipe(self) -> None:
        panel_load_workflow_recipe(self)

    def _handle_terminal_recipe_marker(self, line: str) -> bool:
        return panel_handle_terminal_recipe_marker(self, line)

    def _run_terminal_commands(
        self,
        commands: list[str],
        *,
        label: str,
        recipe_context: dict[str, object] | None = None,
    ) -> bool:
        return panel_run_terminal_commands(
            self,
            commands,
            label=label,
            recipe_context=recipe_context,
        )

    def _run_workflow_recipe(self) -> None:
        panel_run_workflow_recipe(self)

    def _append_terminal_output(self, text: str) -> None:
        panel_append_terminal_output(self, text)

    def _submit_terminal_command(self) -> None:
        panel_submit_terminal_command(self)

    def _drain_terminal_queue(self) -> None:
        panel_drain_terminal_queue(self)

    def _stop_terminal_process(self) -> None:
        panel_stop_terminal_process(self)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._terminal_session.stop()
        super().closeEvent(event)

    def _refresh_operator_logs(self) -> None:
        items = read_launcher_events(_ROOT)
        lines = build_operator_log_lines(items, log_filter=self._log_filter, root=_ROOT)
        self._syslog.setPlainText(
            "\n".join(lines[-50:])
            if lines
            else "No operator log entries matched the current filter yet. Recovery runs, workflow actions, and launcher warnings will appear here."
        )
