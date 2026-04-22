from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout

from .. import tokens as T


def _button_style(accent: str) -> str:
    return (
        f"QPushButton {{ background: {T.BG0}; color: {accent}; border: 1px solid {accent};"
        f" padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        f"QPushButton:hover {{ background: {accent}; color: {T.BG}; }}"
    )


def _combo_style() -> str:
    return (
        f"QComboBox {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
        f" font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; padding: 4px 8px; }}"
    )


def _line_edit_style() -> str:
    return (
        f"QLineEdit {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
        f" font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; padding: 4px 8px; }}"
    )


def build_windows_runtime_section(panel, layout, mono) -> None:
    windows_ops = QFrame()
    windows_ops.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}")
    windows_ops_layout = QVBoxLayout(windows_ops)
    windows_ops_layout.setContentsMargins(16, 16, 16, 16)
    windows_ops_layout.setSpacing(12)
    windows_ops_layout.addWidget(mono("DESKTOP RUNTIME", T.PRIMARY, T.FS_TINY, True))
    windows_ops_layout.addWidget(
        mono(
            "See what is ready on this PC, which local AI engine is active, and the safest next step if something needs attention.",
            T.DIM,
            T.FS_SMALL,
        )
    )

    panel._windows_install_lbl = mono("", T.TEXT, T.FS_SMALL)
    panel._windows_runtime_lbl = mono("", T.DIM, T.FS_SMALL)
    panel._windows_paths_lbl = mono("", T.DIM, T.FS_SMALL)
    panel._windows_repair_lbl = mono("", T.DIM, T.FS_SMALL)
    panel._windows_update_lbl = mono("", T.PRIMARY_DIM, T.FS_SMALL)
    panel._windows_diagnostics_lbl = mono("", T.DIM, T.FS_SMALL)
    panel._windows_entry_lbl = mono("", T.PRIMARY_DIM, T.FS_SMALL)
    panel._windows_next_lbl = mono("", T.TEXT, T.FS_SMALL)
    panel._windows_service_lbl = mono("", T.TEXT, T.FS_SMALL)
    panel._windows_change_lbl = mono("", T.DIM, T.FS_SMALL)
    panel._windows_gate_lbl = mono("", T.TEXT, T.FS_SMALL)
    panel._windows_gate_fix_lbl = mono("", T.PRIMARY_DIM, T.FS_SMALL)
    panel._windows_handoff_lbl = mono("", T.PRIMARY_DIM, T.FS_SMALL)
    panel._windows_detail_buttons = []

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
        btn.setStyleSheet(_button_style(accent))
        btn.clicked.connect(lambda _=False, a=action: panel.windows_ops_requested.emit(a))
        panel._windows_action_buttons[action] = btn
        windows_actions.addWidget(btn)
        if action in {"update_runtime", "package_desktop", "release_dry_run", "restart_runtime"}:
            panel._windows_detail_buttons.append(btn)
    windows_actions.addStretch()
    windows_ops_layout.addLayout(windows_actions)

    for widget in (
        panel._windows_install_lbl,
        panel._windows_runtime_lbl,
        panel._windows_paths_lbl,
        panel._windows_repair_lbl,
        panel._windows_update_lbl,
        panel._windows_diagnostics_lbl,
        panel._windows_entry_lbl,
        panel._windows_next_lbl,
        panel._windows_service_lbl,
        panel._windows_change_lbl,
        panel._windows_gate_lbl,
        panel._windows_gate_fix_lbl,
        panel._windows_handoff_lbl,
    ):
        widget.setWordWrap(True)
        windows_ops_layout.addWidget(widget)
    layout.addWidget(windows_ops)


def build_connected_services_section(panel, layout, mono) -> None:
    panel._connectors_frame = QFrame()
    panel._connectors_frame.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}")
    connectors_layout = QVBoxLayout(panel._connectors_frame)
    connectors_layout.setContentsMargins(16, 16, 16, 16)
    connectors_layout.setSpacing(12)
    connectors_layout.addWidget(mono("CONNECTED SERVICES", T.PRIMARY, T.FS_TINY, True))
    connectors_layout.addWidget(
        mono(
            "Connect email, calendar, music, and business tools for this PC. Choose a service, then sign in or save the details it needs.",
            T.DIM,
            T.FS_SMALL,
        )
    )

    connector_row1 = QHBoxLayout()
    panel._connector_cb = QComboBox()
    panel._connector_cb.setStyleSheet(_combo_style())
    panel._connector_cb.currentIndexChanged.connect(panel._sync_connector_controls)
    panel._connector_provider = QComboBox()
    panel._connector_provider.currentIndexChanged.connect(panel._sync_connector_controls)
    panel._connector_account = QComboBox()
    panel._connector_account.currentIndexChanged.connect(panel._sync_connector_controls)
    panel._connector_secret_key = QComboBox()
    panel._connector_secret_key.currentIndexChanged.connect(panel._sync_connector_controls)
    for combo in (panel._connector_provider, panel._connector_account, panel._connector_secret_key):
        combo.setStyleSheet(_combo_style())
    connector_row1.addWidget(panel._connector_cb, stretch=2)
    connector_row1.addWidget(panel._connector_provider, stretch=1)
    connector_row1.addWidget(panel._connector_account, stretch=1)
    connectors_layout.addLayout(connector_row1)

    panel._connector_secret_value = QLineEdit()
    panel._connector_secret_value.setPlaceholderText("Paste an API key or account detail here")
    panel._connector_secret_value.setStyleSheet(_line_edit_style())
    connectors_layout.addWidget(panel._connector_secret_value)

    connector_actions = QHBoxLayout()
    panel._connector_action_buttons = {}
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
        btn.setStyleSheet(_button_style(accent))
        btn.clicked.connect(lambda _=False, a=action: panel._emit_connector_action(a))
        panel._connector_action_buttons[action] = btn
        connector_actions.addWidget(btn)
    connector_actions.addStretch()
    connectors_layout.addLayout(connector_actions)

    panel._connector_state_lbl = mono("Choose a service to get started.", T.DIM, T.FS_SMALL)
    panel._connector_auth_lbl = mono("Connection status will appear here.", T.DIM, T.FS_SMALL)
    panel._connector_detail_lbl = mono("Helpful setup notes will appear here.", T.DIM, T.FS_SMALL)
    panel._connector_validation_lbl = mono("What to do next will appear here.", T.DIM, T.FS_SMALL)
    panel._connector_scope_lbl = mono("What this service can help with will appear here.", T.DIM, T.FS_SMALL)
    panel._connector_setup_lbl = mono("Any required keys or sign-in steps will appear here.", T.DIM, T.FS_SMALL)
    panel._connector_next_step_lbl = mono("Next step: choose a service.", T.DIM, T.FS_SMALL)
    panel._connector_history_lbl = mono("History: unavailable", T.DIM, T.FS_TINY)
    panel._connector_recent_lbl = mono("Recent attempts: unavailable", T.DIM, T.FS_TINY)
    panel._connector_secret_lbl = mono("Secret fields: unavailable", T.DIM, T.FS_TINY)
    for widget in (
        panel._connector_state_lbl,
        panel._connector_auth_lbl,
        panel._connector_detail_lbl,
        panel._connector_validation_lbl,
        panel._connector_scope_lbl,
        panel._connector_setup_lbl,
        panel._connector_next_step_lbl,
        panel._connector_history_lbl,
        panel._connector_recent_lbl,
        panel._connector_secret_lbl,
    ):
        widget.setWordWrap(True)
        connectors_layout.addWidget(widget)

    layout.addWidget(panel._connectors_frame)
    panel._detail_frames.append(panel._connectors_frame)


def build_automation_test_section(panel, layout, mono) -> None:
    panel._automation_frame = QFrame()
    panel._automation_frame.setToolTip(
        "Use this guided check flow to verify readiness, review one safe builder draft, and run focused validation."
    )
    panel._automation_frame.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}")
    automation_layout = QVBoxLayout(panel._automation_frame)
    automation_layout.setContentsMargins(16, 16, 16, 16)
    automation_layout.setSpacing(12)
    automation_layout.addWidget(mono("AUTOMATION TEST", T.PRIMARY, T.FS_TINY, True))
    automation_layout.addWidget(
        mono(
            "Use this guided check flow to verify readiness, queue one safe builder task, review the draft, approve it, and run focused validation.",
            T.DIM,
            T.FS_SMALL,
        )
    )

    panel._automation_summary_lbl = mono(
        "Use this flow when you want one guided launcher test pass with a review bundle at the end.",
        T.DIM,
        T.FS_SMALL,
    )
    panel._automation_summary_lbl.setWordWrap(True)
    automation_layout.addWidget(panel._automation_summary_lbl)

    for text in (
        "1. VERIFY NOW refreshes launcher and local-runtime readiness.",
        "2. SWITCH TO BUILDER WORKSPACE moves to the preferred builder workspace when it exists.",
        "3. QUEUE DRY RUN creates one small builder draft for review.",
        "4. REFRESH EVIDENCE PACK updates the builder report, stress reference, and tester handoff bundle.",
        "5. APPROVE LATEST STAGED TASK only applies reviewed safe output.",
        "6. RUN VALIDATION queues the focused builder check in the embedded terminal.",
    ):
        step_lbl = mono(text, T.DIM, T.FS_TINY)
        step_lbl.setWordWrap(True)
        automation_layout.addWidget(step_lbl)

    panel._automation_action_buttons = {}
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
            button.clicked.connect(
                lambda _=False, action_name=action: panel.automation_action_requested.emit(action_name)
            )
            panel._automation_action_buttons[action] = button
            row.addWidget(button)
        automation_layout.addLayout(row)

    panel._automation_workspace_lbl = mono("Workspace step: waiting for workspace telemetry.", T.TEXT, T.FS_TINY)
    panel._automation_queue_lbl = mono("Queue counts: waiting for builder report.", T.DIM, T.FS_TINY)
    panel._automation_staged_lbl = mono(
        "Latest draft waiting for review: nothing is waiting yet.", T.DIM, T.FS_TINY
    )
    panel._automation_result_lbl = mono(
        "Latest result: no approved builder output has been recorded yet.", T.DIM, T.FS_TINY
    )
    panel._automation_approval_lbl = mono(
        "Latest approval: no queued draft is awaiting approval yet.", T.DIM, T.FS_TINY
    )
    panel._automation_report_lbl = mono("Builder report: runtime/offhours_builder_report.json", T.DIM, T.FS_TINY)
    panel._automation_evidence_lbl = mono("Evidence pack: runtime/user_test_evidence.md", T.DIM, T.FS_TINY)
    panel._automation_stress_lbl = mono("Latest stress run: no stress report recorded yet.", T.DIM, T.FS_TINY)
    panel._automation_recent_lbl = mono("Recent operator notes: no recent launcher notes recorded yet.", T.DIM, T.FS_TINY)
    panel._automation_validation_lbl = mono("Validation command: unavailable", T.PRIMARY_DIM, T.FS_TINY)
    panel._automation_status_lbl = mono("Automation test lane ready", T.DIM, T.FS_TINY)
    for widget in (
        panel._automation_workspace_lbl,
        panel._automation_queue_lbl,
        panel._automation_staged_lbl,
        panel._automation_result_lbl,
        panel._automation_approval_lbl,
        panel._automation_report_lbl,
        panel._automation_evidence_lbl,
        panel._automation_stress_lbl,
        panel._automation_recent_lbl,
        panel._automation_validation_lbl,
        panel._automation_status_lbl,
    ):
        widget.setWordWrap(True)
        automation_layout.addWidget(widget)

    layout.addWidget(panel._automation_frame)
