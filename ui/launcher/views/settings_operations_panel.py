"""Settings-owned operations panel extracted from the legacy advanced surface."""
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
            f"color: {T.INK}; font-family: '{T.FF_HEAD}';"
            f"font-size: 28pt; font-weight: 700; letter-spacing: -1px;"
        )
        title_row.addWidget(title)
        title_row.addStretch()
        self._details_btn = QPushButton("ADVANCED")
        self._details_btn.setToolTip("Show deeper diagnostics, connectors, and terminal lanes")
        self._details_btn.setAccessibleName("Advanced details")
        self._details_btn.setAccessibleDescription("Shows or hides advanced operational controls")
        self._details_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(255,255,255,0.88); color: {T.DIM}; border: 1px solid rgba(214,197,174,0.62);"
            f" padding: 5px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: {T.TERTIARY}; color: {T.TERTIARY}; }}"
        )
        self._details_btn.clicked.connect(self._toggle_details)
        title_row.addWidget(self._details_btn)
        header_layout.addLayout(title_row)

        # sub-info
        info_row = QHBoxLayout()
        info_row.setSpacing(8)
        dot = QLabel("•")
        dot.setStyleSheet(f"color: {T.PRIMARY}; font-size: {T.FS_TINY}pt;")
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

        windows_ops = QFrame()
        windows_ops.setStyleSheet(
            f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}"
        )
        windows_ops_layout = QVBoxLayout(windows_ops)
        windows_ops_layout.setContentsMargins(16, 16, 16, 16)
        windows_ops_layout.setSpacing(12)
        windows_ops_layout.addWidget(_mono("DESKTOP RUNTIME", T.PRIMARY, T.FS_TINY, True))
        windows_ops_layout.addWidget(
            _mono(
                "See what is ready on this PC, which local AI engine is active, and the safest next step if something needs attention.",
                T.DIM,
                T.FS_SMALL,
            )
        )
        self._windows_install_lbl = _mono("", T.TEXT, T.FS_SMALL)
        self._windows_runtime_lbl = _mono("", T.DIM, T.FS_SMALL)
        self._windows_paths_lbl = _mono("", T.DIM, T.FS_SMALL)
        self._windows_repair_lbl = _mono("", T.DIM, T.FS_SMALL)
        self._windows_update_lbl = _mono("", T.PRIMARY_DIM, T.FS_SMALL)
        self._windows_diagnostics_lbl = _mono("", T.DIM, T.FS_SMALL)
        self._windows_entry_lbl = _mono("", T.PRIMARY_DIM, T.FS_SMALL)
        self._windows_next_lbl = _mono("", T.TEXT, T.FS_SMALL)
        self._windows_service_lbl = _mono("", T.TEXT, T.FS_SMALL)
        self._windows_change_lbl = _mono("", T.DIM, T.FS_SMALL)
        self._windows_gate_lbl = _mono("", T.TEXT, T.FS_SMALL)
        self._windows_gate_fix_lbl = _mono("", T.PRIMARY_DIM, T.FS_SMALL)
        self._windows_handoff_lbl = _mono("", T.PRIMARY_DIM, T.FS_SMALL)
        self._windows_detail_buttons: list[QPushButton] = []
        windows_actions = QHBoxLayout()
        for label, action, accent in [
            ("VERIFY", "verify_runtime", T.PRIMARY),
            ("UPDATE", "update_runtime", T.PRIMARY_DIM),
            ("PACKAGE", "package_desktop", T.SECONDARY),
            ("RELEASE DRY RUN", "release_dry_run", T.PRIMARY),
            ("START API", "start_supervised_api", T.PRIMARY_DIM),
            ("RESTART", "restart_runtime", T.ERROR),
            ("REPAIR", "repair_runtime", T.SECONDARY),
        ]:
            btn = QPushButton(label)
            btn.setToolTip(
                {
                    "verify_runtime": "Check local runtime health and refresh launcher evidence.",
                    "update_runtime": "Refresh or install the local runtime dependencies.",
                    "package_desktop": "Run the packaging flow for a desktop build.",
                    "release_dry_run": "Run the release-ready validation flow without shipping.",
                    "start_supervised_api": "Start the local API through the launcher-controlled path.",
                    "restart_runtime": "Restart the local runtime when it needs recovery.",
                    "repair_runtime": "Run the repair flow for local runtime issues.",
                }[action]
            )
            btn.setStyleSheet(
                f"QPushButton {{ background: {T.BG0}; color: {accent}; border: 1px solid {accent};"
                f" padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ background: {accent}; color: {T.BG}; }}"
            )
            btn.clicked.connect(lambda _=False, a=action: self.windows_ops_requested.emit(a))
            self._windows_action_buttons[action] = btn
            windows_actions.addWidget(btn)
            if action in {"update_runtime", "package_desktop", "release_dry_run", "restart_runtime"}:
                self._windows_detail_buttons.append(btn)
        windows_actions.addStretch()
        windows_ops_layout.addLayout(windows_actions)
        for widget in (
            self._windows_install_lbl,
            self._windows_runtime_lbl,
            self._windows_paths_lbl,
            self._windows_repair_lbl,
            self._windows_update_lbl,
            self._windows_diagnostics_lbl,
            self._windows_entry_lbl,
            self._windows_next_lbl,
            self._windows_service_lbl,
            self._windows_change_lbl,
            self._windows_gate_lbl,
            self._windows_gate_fix_lbl,
            self._windows_handoff_lbl,
        ):
            widget.setWordWrap(True)
            windows_ops_layout.addWidget(widget)
        layout.addWidget(windows_ops)

        self._connectors_frame = QFrame()
        self._connectors_frame.setStyleSheet(
            f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}"
        )
        connectors_layout = QVBoxLayout(self._connectors_frame)
        connectors_layout.setContentsMargins(16, 16, 16, 16)
        connectors_layout.setSpacing(12)
        connectors_layout.addWidget(_mono("CONNECTED SERVICES", T.PRIMARY, T.FS_TINY, True))
        connectors_layout.addWidget(
            _mono(
                "Connect email, calendar, music, and business tools for this PC. Choose a service, then sign in or save the details it needs.",
                T.DIM,
                T.FS_SMALL,
            )
        )
        connector_row1 = QHBoxLayout()
        self._connector_cb = QComboBox()
        self._connector_cb.setStyleSheet(
            f"QComboBox {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
            f" font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; padding: 4px 8px; }}"
        )
        self._connector_cb.currentIndexChanged.connect(self._sync_connector_controls)
        self._connector_provider = QComboBox()
        self._connector_provider.currentIndexChanged.connect(self._sync_connector_controls)
        self._connector_account = QComboBox()
        self._connector_account.currentIndexChanged.connect(self._sync_connector_controls)
        self._connector_secret_key = QComboBox()
        self._connector_secret_key.currentIndexChanged.connect(self._sync_connector_controls)
        for combo in (self._connector_provider, self._connector_account, self._connector_secret_key):
            combo.setStyleSheet(
                f"QComboBox {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
                f" font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; padding: 4px 8px; }}"
            )
        connector_row1.addWidget(self._connector_cb, stretch=2)
        connector_row1.addWidget(self._connector_provider, stretch=1)
        connector_row1.addWidget(self._connector_account, stretch=1)
        connectors_layout.addLayout(connector_row1)

        self._connector_secret_value = QLineEdit()
        self._connector_secret_value.setPlaceholderText("Paste an API key or account detail here")
        self._connector_secret_value.setStyleSheet(
            f"QLineEdit {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
            f" font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; padding: 4px 8px; }}"
        )
        connectors_layout.addWidget(self._connector_secret_value)

        connector_actions = QHBoxLayout()
        self._connector_action_buttons: dict[str, QPushButton] = {}
        for label, action, accent in [
            ("VERIFY", "verify", T.PRIMARY),
            ("CONNECT", "connect", T.PRIMARY_DIM),
            ("RECONNECT", "reconnect", T.SECONDARY),
            ("DISCONNECT", "disconnect", T.ERROR),
            ("SAVE SECRET", "save_secret", T.PRIMARY_DIM),
            ("CLEAR SECRET", "clear_secret", T.ERROR),
        ]:
            btn = QPushButton(label)
            btn.setToolTip(
                {
                    "verify": "Verify the selected service with the current account or key.",
                    "connect": "Open the sign-in or connect flow for the selected service.",
                    "reconnect": "Retry sign-in for the selected service.",
                    "disconnect": "Remove the current linked account from this machine.",
                    "save_secret": "Save the current key or secret value for this service.",
                    "clear_secret": "Remove the saved key or secret value for this service.",
                }[action]
            )
            btn.setStyleSheet(
                f"QPushButton {{ background: {T.BG0}; color: {accent}; border: 1px solid {accent};"
                f" padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ background: {accent}; color: {T.BG}; }}"
            )
            btn.clicked.connect(lambda _=False, a=action: self._emit_connector_action(a))
            self._connector_action_buttons[action] = btn
            connector_actions.addWidget(btn)
        connector_actions.addStretch()
        connectors_layout.addLayout(connector_actions)

        self._connector_state_lbl = _mono("Choose a service to get started.", T.DIM, T.FS_SMALL)
        self._connector_auth_lbl = _mono("Connection status will appear here.", T.DIM, T.FS_SMALL)
        self._connector_detail_lbl = _mono("Helpful setup notes will appear here.", T.DIM, T.FS_SMALL)
        self._connector_validation_lbl = _mono("What to do next will appear here.", T.DIM, T.FS_SMALL)
        self._connector_scope_lbl = _mono("What this service can help with will appear here.", T.DIM, T.FS_SMALL)
        self._connector_setup_lbl = _mono("Any required keys or sign-in steps will appear here.", T.DIM, T.FS_SMALL)
        self._connector_next_step_lbl = _mono("Next step: choose a service.", T.DIM, T.FS_SMALL)
        self._connector_history_lbl = _mono("History: unavailable", T.DIM, T.FS_TINY)
        self._connector_recent_lbl = _mono("Recent attempts: unavailable", T.DIM, T.FS_TINY)
        self._connector_secret_lbl = _mono("Secret fields: unavailable", T.DIM, T.FS_TINY)
        for widget in (
            self._connector_state_lbl,
            self._connector_auth_lbl,
            self._connector_detail_lbl,
            self._connector_validation_lbl,
            self._connector_scope_lbl,
            self._connector_setup_lbl,
            self._connector_next_step_lbl,
            self._connector_history_lbl,
            self._connector_recent_lbl,
            self._connector_secret_lbl,
        ):
            widget.setWordWrap(True)
            connectors_layout.addWidget(widget)
        layout.addWidget(self._connectors_frame)
        self._detail_frames.append(self._connectors_frame)

        self._automation_frame = QFrame()
        self._automation_frame.setToolTip("Use this guided check flow to verify readiness, review one safe builder draft, and run focused validation.")
        self._automation_frame.setStyleSheet(
            f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}"
        )
        automation_layout = QVBoxLayout(self._automation_frame)
        automation_layout.setContentsMargins(16, 16, 16, 16)
        automation_layout.setSpacing(12)
        automation_layout.addWidget(_mono("AUTOMATION TEST", T.PRIMARY, T.FS_TINY, True))
        automation_layout.addWidget(
            _mono(
                "Use this guided check flow to verify readiness, queue one safe builder task, review the draft, approve it, and run focused validation.",
                T.DIM,
                T.FS_SMALL,
            )
        )
        self._automation_summary_lbl = _mono(
            "Use this flow when you want one guided launcher test pass with a review bundle at the end.",
            T.DIM,
            T.FS_SMALL,
        )
        self._automation_summary_lbl.setWordWrap(True)
        automation_layout.addWidget(self._automation_summary_lbl)

        for text in (
            "1. VERIFY NOW refreshes launcher and local-runtime readiness.",
            "2. SWITCH TO BUILDER WORKSPACE moves to the preferred builder workspace when it exists.",
            "3. QUEUE DRY RUN creates one small builder draft for review.",
            "4. REFRESH EVIDENCE PACK updates the builder report, stress reference, and tester handoff bundle.",
            "5. APPROVE LATEST STAGED TASK only applies reviewed safe output.",
            "6. RUN VALIDATION queues the focused builder check in the embedded terminal.",
        ):
            step_lbl = _mono(text, T.DIM, T.FS_TINY)
            step_lbl.setWordWrap(True)
            automation_layout.addWidget(step_lbl)

        self._automation_action_buttons: dict[str, QPushButton] = {}
        action_rows = [
            [
                ("VERIFY NOW", "verify_now", T.PRIMARY),
                ("SWITCH TO BUILDER WORKSPACE", "switch_builder_workspace", T.SECONDARY),
                ("QUEUE DRY RUN", "queue_dry_run", T.PRIMARY_DIM),
            ],
            [
                ("REFRESH EVIDENCE PACK", "open_latest_report", T.DIM),
                ("APPROVE LATEST STAGED TASK", "approve_latest_staged_task", T.GREEN),
                ("RUN VALIDATION", "run_validation", T.PRIMARY),
            ],
        ]
        for row_actions in action_rows:
            row = QHBoxLayout()
            row.setSpacing(8)
            for label, action, accent in row_actions:
                button = QPushButton(label)
                button.setStyleSheet(
                    f"QPushButton {{ background: {T.BG0}; color: {accent}; border: 1px solid {accent};"
                    f" padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                    f"QPushButton:hover {{ background: rgba(242,202,80,0.12); }}"
                )
                button.clicked.connect(lambda _=False, action_name=action: self.automation_action_requested.emit(action_name))
                self._automation_action_buttons[action] = button
                row.addWidget(button)
            automation_layout.addLayout(row)

        self._automation_workspace_lbl = _mono("Workspace step: waiting for workspace telemetry.", T.TEXT, T.FS_TINY)
        self._automation_queue_lbl = _mono("Queue counts: waiting for builder report.", T.DIM, T.FS_TINY)
        self._automation_staged_lbl = _mono("Latest draft waiting for review: nothing is waiting yet.", T.DIM, T.FS_TINY)
        self._automation_result_lbl = _mono("Latest result: no approved builder output has been recorded yet.", T.DIM, T.FS_TINY)
        self._automation_approval_lbl = _mono("Latest approval: no queued draft is awaiting approval yet.", T.DIM, T.FS_TINY)
        self._automation_report_lbl = _mono("Builder report: runtime/offhours_builder_report.json", T.DIM, T.FS_TINY)
        self._automation_evidence_lbl = _mono("Evidence pack: runtime/user_test_evidence.md", T.DIM, T.FS_TINY)
        self._automation_stress_lbl = _mono("Latest stress run: no stress report recorded yet.", T.DIM, T.FS_TINY)
        self._automation_recent_lbl = _mono("Recent operator notes: no recent launcher notes recorded yet.", T.DIM, T.FS_TINY)
        self._automation_validation_lbl = _mono("Validation command: unavailable", T.PRIMARY_DIM, T.FS_TINY)
        self._automation_status_lbl = _mono("Automation test lane ready", T.DIM, T.FS_TINY)
        for widget in (
            self._automation_workspace_lbl,
            self._automation_queue_lbl,
            self._automation_staged_lbl,
            self._automation_result_lbl,
            self._automation_approval_lbl,
            self._automation_report_lbl,
            self._automation_evidence_lbl,
            self._automation_stress_lbl,
            self._automation_recent_lbl,
            self._automation_validation_lbl,
            self._automation_status_lbl,
        ):
            widget.setWordWrap(True)
            automation_layout.addWidget(widget)
        layout.addWidget(self._automation_frame)

        self._workflow_frame = QFrame()
        self._workflow_frame.setStyleSheet(
            f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}"
        )
        workflow_layout = QVBoxLayout(self._workflow_frame)
        workflow_layout.setContentsMargins(16, 16, 16, 16)
        workflow_layout.setSpacing(12)
        workflow_layout.addWidget(_mono("WORKFLOW LOOPS", T.PRIMARY, T.FS_TINY, True))
        workflow_layout.addWidget(
            _mono(
                "Launcher-first shortcuts for Morning, acceptance, midday, evening, and overnight operations.",
                T.DIM,
                T.FS_SMALL,
            )
        )

        workflow_row = QHBoxLayout()
        self._workflow_cb = QComboBox()
        self._workflow_cb.setStyleSheet(
            f"QComboBox {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
            f" font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; padding: 4px 8px; }}"
        )
        for recipe in list_workflow_specs(category="workflow_loop"):
            self._workflow_cb.addItem(recipe.title, recipe.workflow_id)
        self._workflow_cb.currentIndexChanged.connect(self._sync_workflow_recipe)
        workflow_row.addWidget(self._workflow_cb, stretch=1)

        self._workflow_load_btn = QPushButton("LOAD FIRST CMD")
        self._workflow_load_btn.setToolTip("Load the first command from the selected workflow into the embedded terminal.")
        self._workflow_load_btn.clicked.connect(self._load_workflow_recipe)
        self._workflow_run_btn = QPushButton("RUN ALL")
        self._workflow_run_btn.setToolTip("Queue the full selected workflow in the embedded terminal.")
        self._workflow_run_btn.clicked.connect(self._run_workflow_recipe)
        for button in (self._workflow_load_btn, self._workflow_run_btn):
            button.setStyleSheet(
                f"QPushButton {{ background: {T.BG0}; color: {T.DIM}; border: 1px solid {T.BORDER};"
                f" padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ border-color: {T.PRIMARY}; color: {T.PRIMARY}; }}"
            )
            workflow_row.addWidget(button)
        workflow_layout.addLayout(workflow_row)

        self._workflow_summary_lbl = _mono("", T.DIM, T.FS_TINY)
        self._workflow_summary_lbl.setWordWrap(True)
        workflow_layout.addWidget(self._workflow_summary_lbl)
        self._workflow_steps_lbl = _mono("", T.PRIMARY_DIM, T.FS_TINY)
        self._workflow_steps_lbl.setWordWrap(True)
        workflow_layout.addWidget(self._workflow_steps_lbl)
        self._workflow_next_step_lbl = _mono("", T.DIM, T.FS_TINY)
        self._workflow_next_step_lbl.setWordWrap(True)
        workflow_layout.addWidget(self._workflow_next_step_lbl)
        self._workflow_outcome_lbl = _mono("Outcome: waiting for a workflow action.", T.DIM, T.FS_TINY)
        self._workflow_outcome_lbl.setWordWrap(True)
        workflow_layout.addWidget(self._workflow_outcome_lbl)
        self._workflow_status_lbl = _mono("Workflow shortcuts ready", T.DIM, T.FS_TINY)
        workflow_layout.addWidget(self._workflow_status_lbl)
        self._workflow_evidence_lbl = _mono(
            "Evidence: pick a workflow to see command count, shell state, and next checks.",
            T.DIM,
            T.FS_TINY,
        )
        self._workflow_evidence_lbl.setWordWrap(True)
        workflow_layout.addWidget(self._workflow_evidence_lbl)
        layout.addWidget(self._workflow_frame)
        self._detail_frames.append(self._workflow_frame)

        self._operator_logs_frame = QFrame()
        self._operator_logs_frame.setObjectName("syslog_term")
        self._operator_logs_frame.setStyleSheet(
            f"QFrame#syslog_term {{ background-color: {T.BG0}; border: 1px solid {T.BORDER}; }}"
        )
        term_layout = QVBoxLayout(self._operator_logs_frame)
        term_layout.setContentsMargins(16, 16, 16, 16)
        term_layout.setSpacing(10)

        term_hdr = QHBoxLayout()
        term_hdr.addWidget(_mono("OPERATOR LOGS", T.DIM, T.FS_TINY))
        term_hdr.addStretch()
        self._filter_cb = QComboBox()
        self._filter_cb.addItems(["ALL", "WARN", "ERROR"])
        self._filter_cb.setStyleSheet(
            f"QComboBox {{ background: {T.BG1}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
            f" font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; padding: 2px 6px; }}"
        )
        self._filter_cb.currentTextChanged.connect(self._set_log_filter)
        term_hdr.addWidget(self._filter_cb)
        term_layout.addLayout(term_hdr)

        self._syslog = QPlainTextEdit()
        self._syslog.setReadOnly(True)
        self._syslog.setMinimumHeight(200)
        self._syslog.setStyleSheet(
            f"QPlainTextEdit {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
            f" font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        )
        term_layout.addWidget(self._syslog)
        layout.addWidget(self._operator_logs_frame)
        self._detail_frames.append(self._operator_logs_frame)

        self._terminal_frame = QFrame()
        self._terminal_frame.setObjectName("embedded_terminal")
        self._terminal_frame.setStyleSheet(
            f"QFrame#embedded_terminal {{ background-color: {T.BG0}; border: 1px solid {T.BORDER}; }}"
        )
        terminal_layout = QVBoxLayout(self._terminal_frame)
        terminal_layout.setContentsMargins(16, 14, 16, 14)
        terminal_layout.setSpacing(12)

        terminal_hdr = QHBoxLayout()
        terminal_hdr.addWidget(_mono("EMBEDDED TERMINAL", T.DIM, T.FS_TINY))
        terminal_hdr.addStretch()
        self._terminal_status_lbl = _mono("Shell idle", T.DIM, T.FS_TINY)
        terminal_hdr.addWidget(self._terminal_status_lbl)
        terminal_layout.addLayout(terminal_hdr)

        self._terminal_output = QPlainTextEdit()
        self._terminal_output.setReadOnly(True)
        self._terminal_output.setMinimumHeight(200)
        self._terminal_output.setStyleSheet(
            f"QPlainTextEdit {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
            f" font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        )
        terminal_layout.addWidget(self._terminal_output)

        terminal_input_row = QHBoxLayout()
        self._terminal_input = QLineEdit()
        self._terminal_input.setPlaceholderText("Enter a PowerShell command to run inside the launcher terminal")
        self._terminal_input.returnPressed.connect(self._submit_terminal_command)
        self._terminal_input.setStyleSheet(
            f"QLineEdit {{ background: {T.BG1}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
            f" font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; padding: 4px 8px; }}"
        )
        terminal_input_row.addWidget(self._terminal_input, stretch=1)

        self._terminal_run_btn = QPushButton("RUN")
        self._terminal_run_btn.setToolTip("Run the current PowerShell command in the embedded terminal.")
        self._terminal_run_btn.clicked.connect(self._submit_terminal_command)
        self._terminal_clear_btn = QPushButton("CLEAR")
        self._terminal_clear_btn.setToolTip("Clear the terminal output pane.")
        self._terminal_clear_btn.clicked.connect(self._terminal_output.clear)
        self._terminal_stop_btn = QPushButton("STOP")
        self._terminal_stop_btn.setToolTip("Stop the currently running terminal command.")
        self._terminal_stop_btn.clicked.connect(self._stop_terminal_process)
        for button in (self._terminal_run_btn, self._terminal_clear_btn, self._terminal_stop_btn):
            button.setStyleSheet(
                f"QPushButton {{ background: {T.BG1}; color: {T.DIM}; border: 1px solid {T.BORDER};"
                f" padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ border-color: {T.PRIMARY}; color: {T.PRIMARY}; }}"
            )
            terminal_input_row.addWidget(button)
        terminal_layout.addLayout(terminal_input_row)
        layout.addWidget(self._terminal_frame)
        self._detail_frames.append(self._terminal_frame)

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
        compact = width <= 1180
        tight = width <= 980
        self._header_scope_lbl.setVisible(not tight)
        self._details_btn.setText(
            "LESS ADVANCED" if self._details_visible and not tight else
            "LESS" if self._details_visible else
            "ADVANCED" if not tight else
            "DETAILS"
        )
        self._automation_summary_lbl.setVisible(not tight)
        self._workflow_evidence_lbl.setVisible(not tight)
        self._terminal_input.setPlaceholderText(
            "Enter a PowerShell command"
            if tight
            else "Enter a PowerShell command to run inside the launcher terminal"
        )
        for action, text in {
            "health_snapshot": "SNAPSHOT",
            "warmup": "WARMUP",
            "restart_daemon": "RESTART" if compact else "RESTART DAEMON",
            "audit_runtime": "AUDIT" if compact else "AUDIT RUNTIME",
        }.items():
            self._quick_fix_buttons[action].setText(text)
        for action, text in {
            "release_dry_run": "DRY RUN" if compact else "RELEASE DRY RUN",
            "start_supervised_api": "START" if tight else "START API",
        }.items():
            self._windows_action_buttons[action].setText(text)
        for action, text in {
            "verify_now": "VERIFY" if tight else "VERIFY NOW",
            "switch_builder_workspace": "BUILDER" if tight else "SWITCH TO BUILDER WORKSPACE",
            "queue_dry_run": "DRY RUN",
            "open_latest_report": "REFRESH" if tight else "REFRESH EVIDENCE PACK",
            "approve_latest_staged_task": "APPROVE" if tight else "APPROVE LATEST STAGED TASK",
            "run_validation": "VALIDATE" if tight else "RUN VALIDATION",
        }.items():
            self._automation_action_buttons[action].setText(text)
        self._workflow_load_btn.setText("LOAD" if compact else "LOAD FIRST CMD")
        self._workflow_run_btn.setText("RUN" if compact else "RUN ALL")

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
