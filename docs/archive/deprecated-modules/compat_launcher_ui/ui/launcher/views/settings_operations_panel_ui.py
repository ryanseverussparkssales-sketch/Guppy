"""
settings_operations_panel_ui.py
UI build for SettingsOperationsPanel — extracted from settings_operations_panel.py.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .settings_operations_sections import (
    build_automation_test_section as _build_automation_test_section,
    build_connected_services_section as _build_connected_services_section,
    build_windows_runtime_section as _build_windows_runtime_section,
)
from .settings_workflow_terminal_sections import (
    build_operator_logs_section as _build_operator_logs_section,
    build_terminal_section as _build_terminal_section,
    build_workflow_section as _build_workflow_section,
)
from .settings_snapshot_panel import (
    refresh_windows_ops_labels as _refresh_windows_ops_labels,
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


def build_operations_panel_ui(owner: QWidget) -> None:
    outer = QVBoxLayout(owner)
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
    owner._details_btn = QPushButton("ADVANCED")
    owner._details_btn.setToolTip("Show deeper diagnostics, connectors, and terminal lanes")
    owner._details_btn.setAccessibleName("Advanced details")
    owner._details_btn.setAccessibleDescription("Shows or hides advanced operational controls")
    owner._details_btn.setStyleSheet(
        f"QPushButton {{ background: rgba(255,255,255,0.88); color: {T.DIM}; border: 1px solid {T.BORDER_SOFT}; border-radius: 4px;"
        f" padding: 5px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        f"QPushButton:hover {{ border-color: {T.ACCENT_TEAL}; color: {T.ACCENT_TEAL}; }}"
    )
    owner._details_btn.clicked.connect(owner._toggle_details)
    title_row.addWidget(owner._details_btn)
    header_layout.addLayout(title_row)

    info_row = QHBoxLayout()
    info_row.setSpacing(8)
    dot = QLabel("•")
    dot.setStyleSheet(f"color: {T.ACCENT_ORANGE}; font-size: {T.FS_TINY}pt;")
    info_row.addWidget(dot)
    info_row.addWidget(_mono("SETTINGS + RECOVERY", T.PRIMARY, T.FS_TINY, True))
    info_row.addSpacing(12)
    owner._header_scope_lbl = _mono("SYSTEM HEALTH / CONNECTORS / AUTOMATION / DESKTOP RUNTIME", T.DIM, T.FS_TINY)
    info_row.addWidget(owner._header_scope_lbl)
    info_row.addStretch()
    header_layout.addLayout(info_row)
    subtitle = _mono(
        "Keep setup, connectors, health, security checks, packaging readiness, recovery, and machine operations in one secondary surface. Use details only when you need the deeper system lanes. Models and voices now live in the Models hub.",
        T.DIM,
        T.FS_SMALL,
    )
    subtitle.setWordWrap(True)
    header_layout.addWidget(subtitle)
    layout.addWidget(header_frame)

    owner._boundary_frame = QFrame()
    owner._boundary_frame.setStyleSheet(
        f"QFrame {{ background: rgba(244,239,231,0.82); border: 1px solid rgba(214,197,174,0.52); border-radius: 22px; }}"
    )
    boundary_layout = QVBoxLayout(owner._boundary_frame)
    boundary_layout.setContentsMargins(16, 14, 16, 14)
    boundary_layout.setSpacing(8)
    boundary_layout.addWidget(_mono("BOUNDARY", T.PRIMARY, T.FS_TINY, True))
    boundary_layout.addWidget(_mono("Open this tab for app-wide setup, recovery, diagnostics, workflow loops, logs, account linking, and system configuration. Models, runtime loadouts, and voices stay in the Models hub.", T.DIM, T.FS_SMALL))
    layout.addWidget(owner._boundary_frame)
    owner._detail_frames.append(owner._boundary_frame)

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
    owner._daily_activity_lbl = _mono("Recent activity: launcher ready", T.DIM, T.FS_SMALL)
    owner._daily_workspace_lbl = _mono("Current workspace: Daily assistant workspace", T.TEXT, T.FS_SMALL)
    owner._daily_runtime_lbl = _mono("Ready now: waiting for first status poll", T.DIM, T.FS_SMALL)
    owner._daily_route_lbl = _mono("Route preview: waiting for your next message", T.DIM, T.FS_SMALL)
    owner._daily_recovery_lbl = _mono("Recovery: all clear", T.GREEN, T.FS_SMALL)
    for widget in (
        owner._daily_activity_lbl,
        owner._daily_workspace_lbl,
        owner._daily_runtime_lbl,
        owner._daily_route_lbl,
        owner._daily_recovery_lbl,
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

    owner._recovery_status = _mono("Nothing needs attention right now.", T.DIM, T.FS_TINY)
    actions_layout.addWidget(owner._recovery_status)

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
        btn.clicked.connect(lambda _=False, a=action: owner.recovery_requested.emit(a))
        owner._quick_fix_buttons[action] = btn
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
    owner._health_lbl = _mono("API health: unknown", T.DIM, T.FS_SMALL)
    owner._instances_lbl = _mono("Workspaces: unknown", T.DIM, T.FS_SMALL)
    owner._voice_lbl = _mono("Voice services: unknown", T.DIM, T.FS_SMALL)
    owner._route_health_lbl = _mono("Route evidence: unknown", T.DIM, T.FS_SMALL)
    owner._resource_lbl = _mono("Resource envelope: unknown", T.DIM, T.FS_SMALL)
    owner._last_recovery_lbl = _mono("Last recovery action: idle", T.DIM, T.FS_SMALL)
    for widget in [
        owner._health_lbl,
        owner._instances_lbl,
        owner._voice_lbl,
        owner._route_health_lbl,
        owner._resource_lbl,
        owner._last_recovery_lbl,
    ]:
        widget.setWordWrap(True)
        diag_layout.addWidget(widget)
    layout.addWidget(diag_frame)

    _build_windows_runtime_section(owner, layout, _mono)
    _build_connected_services_section(owner, layout, _mono)
    _build_automation_test_section(owner, layout, _mono)

    _build_workflow_section(owner, layout, _mono)
    _build_operator_logs_section(owner, layout, _mono)
    _build_terminal_section(owner, layout, _mono)

    layout.addStretch()
    scroll.setWidget(content)
    outer.addWidget(scroll)

    timer = QTimer(owner)
    timer.timeout.connect(owner._refresh_operator_logs)
    timer.start(4000)
    owner._refresh_operator_logs()

    owner._terminal_timer = QTimer(owner)
    owner._terminal_timer.timeout.connect(owner._drain_terminal_queue)
    owner._terminal_timer.start(150)
    owner._sync_workflow_recipe()
    owner.set_automation_snapshot({})
    _refresh_windows_ops_labels(owner)
    owner._detail_widgets.extend(
        [
            owner._daily_route_lbl,
            owner._daily_recovery_lbl,
            owner._instances_lbl,
            owner._voice_lbl,
            owner._route_health_lbl,
            owner._resource_lbl,
            owner._last_recovery_lbl,
            owner._windows_paths_lbl,
            owner._windows_update_lbl,
            owner._windows_diagnostics_lbl,
            owner._windows_entry_lbl,
            owner._windows_change_lbl,
            owner._windows_gate_lbl,
            owner._windows_gate_fix_lbl,
            owner._windows_handoff_lbl,
        ]
    )
    owner._sync_detail_visibility()
