"""
ui/launcher/views/advanced_view.py
APP MGMT tab - app-level recovery actions, diagnostics, settings, and operator logs.
"""
from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
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

from .. import tokens as T

_ROOT = Path(__file__).resolve().parent.parent.parent.parent

try:
    from utils.runtime_profile import load_app_settings
    _RUNTIME_SETTINGS_BACKEND = True
except Exception:
    _RUNTIME_SETTINGS_BACKEND = False

    def load_app_settings() -> dict[str, object]:
        return {}

_WORKFLOW_RECIPES: list[dict[str, object]] = [
    {
        "id": "morning_boot",
        "title": "MORNING BOOT",
        "summary": "Start the day with the pilot gate and the fast canary checks.",
        "commands": [
            "python tools/pilot_exit_check.py --allow-limited-go",
            "python -m pytest -q tests/test_pilot_exit_decision_canary.py",
            "python tools/run_triage_fault_canary.py",
        ],
    },
    {
        "id": "acceptance_snapshot",
        "title": "ACCEPTANCE SNAPSHOT",
        "summary": "Run the signed evidence sequence after major functionality, auth, or security changes.",
        "commands": [
            "python -m pytest tests/unit/test_security_hardening.py tests/smoke/test_launcher_interactions_smoke.py -W error::DeprecationWarning",
            "python -m pytest tests/smoke/test_runtime_smoke.py -v",
            "python tools/check_architecture_boundaries.py",
            "python tools/check_new_module_line_cap.py",
            "python tools/check_wrapper_integrity.py",
            "python tools/check_core_surface_integrity.py",
            "python tools/check_doc_ownership.py",
            "python tools/verify_logging_health.py --emit-probe --require-fresh-core",
        ],
    },
    {
        "id": "midday_stability",
        "title": "MIDDAY STABILITY",
        "summary": "Refresh telemetry and local-model health when behavior starts to drift.",
        "commands": [
            "python tools/verify_logging_health.py --emit-probe --require-fresh-core",
            "python tools/verify_ollama_runtime.py --prompt ok",
        ],
    },
    {
        "id": "evening_close",
        "title": "EVENING CLOSE",
        "summary": "Re-check pilot readiness and write the day-end triage summary.",
        "commands": [
            "python tools/pilot_exit_check.py --allow-limited-go",
            "python tools/generate_triage_summary.py",
        ],
    },
    {
        "id": "overnight_low_compute",
        "title": "OVERNIGHT LOW-COMPUTE",
        "summary": "Queue the lower-cost unattended verification loop.",
        "commands": [
            "python tools/run_overnight_low_compute.py --cycles 3 --interval-minutes 180",
        ],
    },
]


def _mono(text: str, color: str = T.DIM, size: int = T.FS_SMALL, bold: bool = False) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}';"
        f"font-size: {size}pt; letter-spacing: 1px;"
        + ("font-weight: bold;" if bold else "")
    )
    return lbl


class AdvancedView(QWidget):
    recovery_requested = Signal(str)
    windows_ops_requested = Signal(str)
    connector_action_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._diagnostics: dict[str, str] = {}
        self._log_filter = "ALL"
        self._terminal_queue: queue.SimpleQueue[tuple[str, str]] = queue.SimpleQueue()
        self._terminal_process: subprocess.Popen[str] | None = None
        self._terminal_focus_pending = False
        self._windows_ops: dict[str, str] = self._build_windows_ops_snapshot()
        self._connector_inventory: list[dict[str, object]] = []

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
        title_row = QHBoxLayout()
        title = QLabel("App Management")
        title.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_HEAD}';"
            f"font-size: 30pt; font-weight: 900; letter-spacing: -1px;"
        )
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)

        # sub-info
        info_row = QHBoxLayout()
        info_row.setSpacing(8)
        dot = QLabel("*")
        dot.setStyleSheet(f"color: {T.PRIMARY}; font-size: {T.FS_TINY}pt;")
        info_row.addWidget(dot)
        info_row.addWidget(_mono("APP-LEVEL OPERATIONS + SETTINGS", T.PRIMARY, T.FS_TINY))
        info_row.addSpacing(12)
        info_row.addWidget(_mono("RECOVERY / DIAGNOSTICS / SETTINGS / OPERATOR LOGS / WORKFLOW LOOPS", T.DIM, T.FS_TINY))
        info_row.addStretch()
        layout.addLayout(info_row)
        layout.addSpacing(12)

        boundary = QFrame()
        boundary.setStyleSheet(
            f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}"
        )
        boundary_layout = QVBoxLayout(boundary)
        boundary_layout.setContentsMargins(12, 10, 12, 10)
        boundary_layout.setSpacing(4)
        boundary_layout.addWidget(_mono("BOUNDARY", T.PRIMARY, T.FS_TINY, True))
        boundary_layout.addWidget(_mono("Open this tab for app-wide recovery, diagnostics, settings, workflow loops, operator logs, and the Home context that no longer lives above the chat. Workspace task tools now live in the right tray.", T.DIM, T.FS_SMALL))
        layout.addWidget(boundary)

        context_frame = QFrame()
        context_frame.setStyleSheet(
            f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}"
        )
        context_layout = QVBoxLayout(context_frame)
        context_layout.setContentsMargins(16, 14, 16, 14)
        context_layout.setSpacing(6)
        context_layout.addWidget(_mono("DAILY SESSION CONTEXT", T.PRIMARY, T.FS_TINY, True))
        context_layout.addWidget(
            _mono(
                "Home now stays chat-first. Runtime, routing, recovery, settings, and latest launcher activity are summarized here.",
                T.DIM,
                T.FS_SMALL,
            )
        )
        self._daily_activity_lbl = _mono("Latest activity: launcher ready", T.DIM, T.FS_SMALL)
        self._daily_workspace_lbl = _mono("Workspace: Daily assistant workspace", T.TEXT, T.FS_SMALL)
        self._daily_runtime_lbl = _mono("Runtime: waiting for first status poll", T.DIM, T.FS_SMALL)
        self._daily_route_lbl = _mono("Route preview: waiting for your next message", T.DIM, T.FS_SMALL)
        self._daily_recovery_lbl = _mono("Recovery: stable", T.GREEN, T.FS_SMALL)
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
            f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}"
        )
        actions_layout = QVBoxLayout(actions_frame)
        actions_layout.setContentsMargins(16, 14, 16, 14)
        actions_layout.setSpacing(10)
        actions_layout.addWidget(_mono("RECOVERY ACTIONS", T.PRIMARY, T.FS_TINY, True))

        self._recovery_status = _mono("Recovery idle", T.DIM, T.FS_TINY)
        actions_layout.addWidget(self._recovery_status)

        action_row = QHBoxLayout()
        for label, action, accent in [
            ("SNAPSHOT", "health_snapshot", T.PRIMARY),
            ("WARMUP", "warmup", T.PRIMARY_DIM),
            ("RESTART DAEMON", "restart_daemon", T.ERROR),
            ("AUDIT RUNTIME", "audit_runtime", T.SECONDARY),
        ]:
            btn = QPushButton(label)
            btn.setStyleSheet(
                f"QPushButton {{ background: {T.BG0}; color: {accent}; border: 1px solid {accent};"
                f" padding: 5px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ background: {accent}; color: {T.BG}; }}"
            )
            btn.clicked.connect(lambda _=False, a=action: self.recovery_requested.emit(a))
            action_row.addWidget(btn)
        action_row.addStretch()
        actions_layout.addLayout(action_row)
        layout.addWidget(actions_frame)

        diag_frame = QFrame()
        diag_frame.setStyleSheet(
            f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}"
        )
        diag_layout = QVBoxLayout(diag_frame)
        diag_layout.setContentsMargins(16, 14, 16, 14)
        diag_layout.setSpacing(8)
        diag_layout.addWidget(_mono("SYSTEM HEALTH", T.PRIMARY, T.FS_TINY, True))
        self._health_lbl = _mono("API: unknown", T.DIM, T.FS_SMALL)
        self._instances_lbl = _mono("Instances: unknown", T.DIM, T.FS_SMALL)
        self._voice_lbl = _mono("Voice: unknown", T.DIM, T.FS_SMALL)
        self._route_health_lbl = _mono("Route evidence: unknown", T.DIM, T.FS_SMALL)
        self._resource_lbl = _mono("Resource envelope: unknown", T.DIM, T.FS_SMALL)
        self._last_recovery_lbl = _mono("Last recovery: idle", T.DIM, T.FS_SMALL)
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
        windows_ops_layout.setContentsMargins(16, 14, 16, 14)
        windows_ops_layout.setSpacing(8)
        windows_ops_layout.addWidget(_mono("WINDOWS INSTALL / UPDATE / DIAGNOSTICS", T.PRIMARY, T.FS_TINY, True))
        windows_ops_layout.addWidget(
            _mono(
                "Keep the desktop runtime legible here: what is installed, which local runtime is active, where data lives, and which repair path to run next.",
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
        windows_actions = QHBoxLayout()
        for label, action, accent in [
            ("VERIFY", "verify_runtime", T.PRIMARY),
            ("UPDATE", "update_runtime", T.PRIMARY_DIM),
            ("RESTART", "restart_runtime", T.ERROR),
            ("REPAIR", "repair_runtime", T.SECONDARY),
        ]:
            btn = QPushButton(label)
            btn.setStyleSheet(
                f"QPushButton {{ background: {T.BG0}; color: {accent}; border: 1px solid {accent};"
                f" padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ background: {accent}; color: {T.BG}; }}"
            )
            btn.clicked.connect(lambda _=False, a=action: self.windows_ops_requested.emit(a))
            windows_actions.addWidget(btn)
        windows_actions.addStretch()
        windows_ops_layout.addLayout(windows_actions)
        for widget in (
            self._windows_install_lbl,
            self._windows_runtime_lbl,
            self._windows_paths_lbl,
            self._windows_repair_lbl,
            self._windows_update_lbl,
            self._windows_diagnostics_lbl,
        ):
            widget.setWordWrap(True)
            windows_ops_layout.addWidget(widget)
        layout.addWidget(windows_ops)

        connectors_frame = QFrame()
        connectors_frame.setStyleSheet(
            f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}"
        )
        connectors_layout = QVBoxLayout(connectors_frame)
        connectors_layout.setContentsMargins(16, 14, 16, 14)
        connectors_layout.setSpacing(8)
        connectors_layout.addWidget(_mono("CONNECTOR INVENTORY + AUTH", T.PRIMARY, T.FS_TINY, True))
        connectors_layout.addWidget(
            _mono(
                "Machine-level connector auth lives here. Verify readiness, reconnect OAuth-backed tools, and manage stored secrets without changing workspace policy.",
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
        self._connector_account = QComboBox()
        self._connector_secret_key = QComboBox()
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
        self._connector_secret_value.setPlaceholderText("secret value for API-key or provider-backed connectors")
        self._connector_secret_value.setStyleSheet(
            f"QLineEdit {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
            f" font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; padding: 4px 8px; }}"
        )
        connectors_layout.addWidget(self._connector_secret_value)

        connector_actions = QHBoxLayout()
        for label, action, accent in [
            ("VERIFY", "verify", T.PRIMARY),
            ("CONNECT", "connect", T.PRIMARY_DIM),
            ("RECONNECT", "reconnect", T.SECONDARY),
            ("DISCONNECT", "disconnect", T.ERROR),
            ("SAVE SECRET", "save_secret", T.PRIMARY_DIM),
            ("CLEAR SECRET", "clear_secret", T.ERROR),
        ]:
            btn = QPushButton(label)
            btn.setStyleSheet(
                f"QPushButton {{ background: {T.BG0}; color: {accent}; border: 1px solid {accent};"
                f" padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ background: {accent}; color: {T.BG}; }}"
            )
            btn.clicked.connect(lambda _=False, a=action: self._emit_connector_action(a))
            connector_actions.addWidget(btn)
        connector_actions.addStretch()
        connectors_layout.addLayout(connector_actions)

        self._connector_state_lbl = _mono("Connector inventory waiting for first refresh", T.DIM, T.FS_SMALL)
        self._connector_auth_lbl = _mono("Auth: unavailable", T.DIM, T.FS_SMALL)
        self._connector_detail_lbl = _mono("Detail: unavailable", T.DIM, T.FS_SMALL)
        self._connector_secret_lbl = _mono("Secret fields: unavailable", T.DIM, T.FS_TINY)
        for widget in (
            self._connector_state_lbl,
            self._connector_auth_lbl,
            self._connector_detail_lbl,
            self._connector_secret_lbl,
        ):
            widget.setWordWrap(True)
            connectors_layout.addWidget(widget)
        layout.addWidget(connectors_frame)

        workflow_frame = QFrame()
        workflow_frame.setStyleSheet(
            f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}"
        )
        workflow_layout = QVBoxLayout(workflow_frame)
        workflow_layout.setContentsMargins(16, 14, 16, 14)
        workflow_layout.setSpacing(8)
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
        for recipe in _WORKFLOW_RECIPES:
            self._workflow_cb.addItem(str(recipe.get("title", "WORKFLOW")), str(recipe.get("id", "")))
        self._workflow_cb.currentIndexChanged.connect(self._sync_workflow_recipe)
        workflow_row.addWidget(self._workflow_cb, stretch=1)

        self._workflow_load_btn = QPushButton("LOAD FIRST CMD")
        self._workflow_load_btn.clicked.connect(self._load_workflow_recipe)
        self._workflow_run_btn = QPushButton("RUN ALL")
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
        layout.addWidget(workflow_frame)

        term = QFrame()
        term.setObjectName("syslog_term")
        term.setStyleSheet(
            f"QFrame#syslog_term {{ background-color: {T.BG0}; border: 1px solid {T.BORDER}; }}"
        )
        term_layout = QVBoxLayout(term)
        term_layout.setContentsMargins(16, 12, 16, 12)
        term_layout.setSpacing(6)

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
        layout.addWidget(term)

        terminal_frame = QFrame()
        terminal_frame.setObjectName("embedded_terminal")
        terminal_frame.setStyleSheet(
            f"QFrame#embedded_terminal {{ background-color: {T.BG0}; border: 1px solid {T.BORDER}; }}"
        )
        terminal_layout = QVBoxLayout(terminal_frame)
        terminal_layout.setContentsMargins(16, 12, 16, 12)
        terminal_layout.setSpacing(8)

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
        self._terminal_run_btn.clicked.connect(self._submit_terminal_command)
        self._terminal_clear_btn = QPushButton("CLEAR")
        self._terminal_clear_btn.clicked.connect(self._terminal_output.clear)
        self._terminal_stop_btn = QPushButton("STOP")
        self._terminal_stop_btn.clicked.connect(self._stop_terminal_process)
        for button in (self._terminal_run_btn, self._terminal_clear_btn, self._terminal_stop_btn):
            button.setStyleSheet(
                f"QPushButton {{ background: {T.BG1}; color: {T.DIM}; border: 1px solid {T.BORDER};"
                f" padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ border-color: {T.PRIMARY}; color: {T.PRIMARY}; }}"
            )
            terminal_input_row.addWidget(button)
        terminal_layout.addLayout(terminal_input_row)
        layout.addWidget(terminal_frame)

        settings_frame = QFrame()
        settings_frame.setObjectName("embedded_settings")
        settings_frame.setStyleSheet(
            f"QFrame#embedded_settings {{ background-color: {T.BG1}; border: 1px solid {T.BORDER}; }}"
        )
        settings_layout = QVBoxLayout(settings_frame)
        settings_layout.setContentsMargins(16, 14, 16, 14)
        settings_layout.setSpacing(10)
        settings_layout.addWidget(_mono("SETTINGS", T.PRIMARY, T.FS_TINY, True))
        settings_layout.addWidget(
            _mono(
                "Runtime preferences and persona controls now live inside App Mgmt so operational setup stays in one place.",
                T.DIM,
                T.FS_SMALL,
            )
        )
        self._settings_host = QVBoxLayout()
        self._settings_host.setContentsMargins(0, 0, 0, 0)
        self._settings_host.setSpacing(0)
        settings_layout.addLayout(self._settings_host)
        layout.addWidget(settings_frame)

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
        self._refresh_windows_ops_labels()

    def attach_settings_panel(self, widget: QWidget) -> None:
        while self._settings_host.count():
            item = self._settings_host.takeAt(0)
            if item is None:
                continue
            child = item.widget()
            if child is not None:
                child.setParent(None)
        self._settings_host.addWidget(widget)

    def append_log(self, line: str) -> None:
        current = self._syslog.toPlainText().splitlines()
        current.append(f"> {line}")
        self._syslog.setPlainText("\n".join(current[-40:]))

    def set_recovery_status(self, text: str) -> None:
        msg = (text or "Recovery idle").strip() or "Recovery idle"
        self._recovery_status.setText(msg)
        self._last_recovery_lbl.setText(f"Last recovery: {msg}")
        runtime_line = self._windows_ops.get("runtime", "")
        self._windows_ops = self._build_windows_ops_snapshot()
        if runtime_line:
            self._windows_ops["runtime"] = runtime_line
        self._refresh_windows_ops_labels()

    def set_daily_context_activity(self, text: str) -> None:
        msg = (text or "launcher ready").strip() or "launcher ready"
        self._daily_activity_lbl.setText(f"Latest activity: {msg}")

    def set_daily_context_workspace(self, text: str) -> None:
        msg = (text or "workspace context unavailable").strip() or "workspace context unavailable"
        self._daily_workspace_lbl.setText(msg)

    def set_daily_context_runtime(self, text: str) -> None:
        msg = (text or "runtime details unavailable").strip() or "runtime details unavailable"
        self._daily_runtime_lbl.setText(msg)

    def set_daily_context_route(self, text: str) -> None:
        msg = (text or "route preview unavailable").strip() or "route preview unavailable"
        self._daily_route_lbl.setText(msg)

    def set_daily_context_recovery(self, text: str, ok: bool = True) -> None:
        msg = (text or "Recovery: stable").strip() or "Recovery: stable"
        self._daily_recovery_lbl.setText(msg)
        self._daily_recovery_lbl.setStyleSheet(
            f"color: {T.GREEN if ok else T.ERROR}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_SMALL}pt; letter-spacing: 1px;"
        )

    def set_status_snapshot(self, payload: dict[str, object]) -> None:
        runtime_line = self._windows_ops.get("runtime", "")
        self._windows_ops = self._build_windows_ops_snapshot()
        if runtime_line:
            self._windows_ops["runtime"] = runtime_line
        api_state = str(payload.get("status", "unknown") or "unknown").upper()
        startup = payload.get("startup_readiness", {})
        startup_overall = "unknown"
        if isinstance(startup, dict):
            startup_overall = str(startup.get("overall", startup.get("status", "unknown")) or "unknown").upper()
        self._health_lbl.setText(f"API: {api_state} | Startup readiness: {startup_overall}")

        voice_tts = str(payload.get("voice_tts_backend", "unknown") or "unknown")
        voice_stt = str(payload.get("voice_stt_backend", "unknown") or "unknown")
        binding = str(payload.get("voice_binding", "") or "").strip()
        self._voice_lbl.setText(
            f"Voice: tts={voice_tts} | stt={voice_stt}" + (f" | {binding}" if binding else "")
        )

        route_evidence = str(payload.get("route_evidence", "") or "").strip()
        self._route_health_lbl.setText(
            f"Route evidence: {route_evidence or 'waiting for the next route preview'}"
        )

        envelope = payload.get("resource_envelope", {})
        if isinstance(envelope, dict):
            state = str(envelope.get("state", "unknown") or "unknown")
            detail = str(envelope.get("message", envelope.get("detail", "")) or "").strip()
            self._resource_lbl.setText(f"Resource envelope: {state}" + (f" | {detail}" if detail else ""))
        self._refresh_windows_ops_labels()

        local_runtime = payload.get("local_runtime", {})
        if isinstance(local_runtime, dict):
            configured_backend = self._configured_local_runtime_backend()
            live_backend = str(local_runtime.get("backend", configured_backend.lower()) or configured_backend).strip().upper()
            live_state = str(local_runtime.get("state", "unknown") or "unknown").strip().upper()
            live_detail = str(local_runtime.get("detail", "") or "").strip()
            self._windows_ops["runtime"] = (
                f"Configured local runtime: {configured_backend} | Live backend: {live_backend} | State: {live_state}"
                + (f" | {live_detail}" if live_detail else "")
            )
            self._refresh_windows_ops_labels()

    def set_instance_snapshot(self, payload: dict[str, object]) -> None:
        limits = payload.get("limits", {}) if isinstance(payload, dict) else {}
        configured = int(limits.get("configured", 0) or 0) if isinstance(limits, dict) else 0
        max_configured = int(limits.get("max_configured", 5) or 5) if isinstance(limits, dict) else 5
        active_runtime = int(limits.get("active_runtime", 0) or 0) if isinstance(limits, dict) else 0
        max_active_runtime = int(limits.get("max_active_runtime", 2) or 2) if isinstance(limits, dict) else 2
        active_instance = str(payload.get("active_instance", "-") or "-") if isinstance(payload, dict) else "-"
        self._instances_lbl.setText(
            f"Instances: active={active_instance} | configured {configured}/{max_configured} | runtime-active {active_runtime}/{max_active_runtime}"
        )

    def set_connector_inventory(self, items: list[dict[str, object]]) -> None:
        self._connector_inventory = [item for item in items if isinstance(item, dict)]
        current = self._connector_cb.currentText().strip().lower()
        self._connector_cb.blockSignals(True)
        self._connector_cb.clear()
        for item in self._connector_inventory:
            connector_id = str(item.get("id", "")).strip().lower()
            if connector_id:
                self._connector_cb.addItem(connector_id)
        if self._connector_cb.count() == 0:
            for connector_id in ("gmail", "calendar", "spotify", "youtube", "crm", "voip"):
                self._connector_cb.addItem(connector_id)
        idx = self._connector_cb.findText(current)
        self._connector_cb.setCurrentIndex(max(0, idx))
        self._connector_cb.blockSignals(False)
        self._sync_connector_controls()

    def _current_connector_payload(self) -> dict[str, object]:
        connector_id = self._connector_cb.currentText().strip().lower()
        return next(
            (
                item
                for item in self._connector_inventory
                if str(item.get("id", "")).strip().lower() == connector_id
            ),
            {},
        )

    def _sync_connector_controls(self) -> None:
        item = self._current_connector_payload()
        providers = item.get("providers", []) if isinstance(item.get("providers"), list) else []
        accounts = item.get("accounts", []) if isinstance(item.get("accounts"), list) else []
        secret_fields = item.get("secret_fields", []) if isinstance(item.get("secret_fields"), list) else []
        for combo, values, default_label in (
            (self._connector_provider, providers, "(provider)"),
            (self._connector_account, accounts, "(account)"),
        ):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(default_label, "")
            for value in values:
                if not isinstance(value, dict):
                    continue
                combo.addItem(str(value.get("label", value.get("id", "")) or value.get("id", "")), str(value.get("id", "")))
            combo.blockSignals(False)
        self._connector_secret_key.blockSignals(True)
        self._connector_secret_key.clear()
        self._connector_secret_key.addItem("(secret field)", "")
        for field in secret_fields:
            self._connector_secret_key.addItem(str(field), str(field))
        self._connector_secret_key.blockSignals(False)
        connector_id = str(item.get("id", self._connector_cb.currentText()) or self._connector_cb.currentText()).strip().lower()
        auth_kind = str(item.get("auth_kind", "unknown") or "unknown")
        auth_state = str(item.get("auth_state", "unknown") or "unknown").upper()
        source = str(item.get("source", "none") or "none").upper()
        detail = str(item.get("auth_detail", "") or "").strip()
        actions = [str(action) for action in item.get("actions_supported", []) if str(action).strip()]
        self._connector_state_lbl.setText(
            f"Connector: {connector_id or '-'} | Auth kind: {auth_kind} | Actions: {', '.join(actions) or 'none'}"
        )
        self._connector_auth_lbl.setText(f"Auth: {auth_state} | Source: {source}")
        self._connector_detail_lbl.setText(f"Detail: {detail or 'No connector detail available.'}")
        self._connector_secret_lbl.setText(
            "Secret fields: " + (", ".join(str(field) for field in secret_fields) if secret_fields else "none")
        )

    def _emit_connector_action(self, action: str) -> None:
        connector_id = self._connector_cb.currentText().strip().lower()
        if not connector_id:
            self.append_log("connector action ignored: choose a connector first")
            return
        resolved_action = "connect" if action == "save_secret" else "disconnect" if action == "clear_secret" else action
        self.connector_action_requested.emit(
            {
                "connector": connector_id,
                "action": resolved_action,
                "provider": str(self._connector_provider.currentData() or "").strip(),
                "account_id": str(self._connector_account.currentData() or "").strip(),
                "secret_key": str(self._connector_secret_key.currentData() or "").strip(),
                "secret_value": self._connector_secret_value.text().strip(),
            }
        )

    def _set_log_filter(self, value: str) -> None:
        self._log_filter = (value or "ALL").strip().upper() or "ALL"
        self._refresh_operator_logs()

    def _configured_local_runtime_backend(self) -> str:
        settings = load_app_settings() if _RUNTIME_SETTINGS_BACKEND else {}
        backend = str(
            settings.get("local_runtime_backend", os.environ.get("GUPPY_LOCAL_RUNTIME_BACKEND", "ollama"))
        ).strip().lower() or "ollama"
        return backend.upper()

    def _latest_runtime_artifact(self, *patterns: str) -> Path | None:
        candidates: list[Path] = []
        runtime_dir = _ROOT / "runtime"
        for pattern in patterns:
            candidates.extend(runtime_dir.glob(pattern))
        if not candidates:
            return None
        return max(candidates, key=lambda path: path.stat().st_mtime)

    def _build_windows_ops_snapshot(self) -> dict[str, str]:
        runtime_dir = _ROOT / "runtime"
        config_dir = _ROOT / "config"
        settings_path = runtime_dir / "app_settings.json"
        launcher_events = runtime_dir / "launcher_events.jsonl"
        venv_python = _ROOT / ".venv" / "Scripts" / "python.exe"
        supervisor_script = _ROOT / "bin" / "launch_api_supervised.bat"
        build_script = _ROOT / "build_executable.bat"
        repair_file = runtime_dir / "repair_token.txt"
        latest_bundle = self._latest_runtime_artifact("diagnostics_bundle_*.json", "diagnostics_*.json")
        latest_bundle_text = str(latest_bundle) if latest_bundle is not None else "none yet"
        install_bits: list[str] = []
        install_bits.append(f"Launcher python: {sys.executable}")
        install_bits.append(f"Repo python: {'present' if venv_python.exists() else 'missing'}")
        install_bits.append(f"Ollama CLI: {'found' if shutil.which('ollama') else 'missing'}")
        install_bits.append(f"Lemonade CLI: {'found' if shutil.which('lemonade') else 'missing'}")
        install_bits.append(f"Supervisor script: {'ready' if supervisor_script.exists() else 'missing'}")
        install_bits.append(f"Packager: {'ready' if build_script.exists() else 'missing'}")

        repair_hint = "keyring-backed first; file fallback present" if repair_file.exists() else "keyring-backed first; file fallback not present"
        return {
            "install": "Installed surface: " + " | ".join(install_bits),
            "runtime": f"Configured local runtime: {self._configured_local_runtime_backend()} | Live backend: waiting for first status poll",
            "paths": f"Data paths: runtime={runtime_dir} | config={config_dir} | settings={settings_path}",
            "repair": f"Repair path: {repair_hint} | API relaunch: {supervisor_script}",
            "update": (
                "Update path: python -m pip install -r requirements.txt | "
                "optional extras: python -m pip install -r requirements-optional.txt | "
                "daily launcher: python src/guppy/cli/launch.py launcher"
            ),
            "diagnostics": (
                f"Diagnostics: launcher log={launcher_events} | latest bundle={latest_bundle_text} | "
                "runtime check: python tools/verify_ollama_runtime.py --prompt ok"
            ),
        }

    def _refresh_windows_ops_labels(self) -> None:
        self._windows_install_lbl.setText(self._windows_ops.get("install", "Installed surface: unavailable"))
        self._windows_runtime_lbl.setText(self._windows_ops.get("runtime", "Configured local runtime: unavailable"))
        self._windows_paths_lbl.setText(self._windows_ops.get("paths", "Data paths: unavailable"))
        self._windows_repair_lbl.setText(self._windows_ops.get("repair", "Repair path: unavailable"))
        self._windows_update_lbl.setText(self._windows_ops.get("update", "Update path: unavailable"))
        self._windows_diagnostics_lbl.setText(self._windows_ops.get("diagnostics", "Diagnostics: unavailable"))

    def focus_operator_logs(self, log_filter: str = "ALL", note: str = "") -> None:
        target = (log_filter or "ALL").strip().upper() or "ALL"
        idx = self._filter_cb.findText(target)
        if idx >= 0:
            self._filter_cb.setCurrentIndex(idx)
        else:
            self._set_log_filter(target)
        if note:
            self.append_log(note)

    def focus_terminal(self, note: str = "") -> None:
        self._terminal_focus_pending = True
        if note:
            self._append_terminal_output(note)
        self._terminal_input.setFocus()

    def queue_terminal_recipe(self, commands: list[str], *, label: str) -> bool:
        return self._run_terminal_commands(commands, label=label)

    def _workflow_recipe(self) -> dict[str, object]:
        recipe_id = str(self._workflow_cb.currentData() or "")
        return next(
            (item for item in _WORKFLOW_RECIPES if str(item.get("id", "")) == recipe_id),
            _WORKFLOW_RECIPES[0] if _WORKFLOW_RECIPES else {},
        )

    def _workflow_commands(self) -> list[str]:
        recipe = self._workflow_recipe()
        commands = recipe.get("commands", [])
        if not isinstance(commands, list):
            return []
        return [str(item).strip() for item in commands if str(item).strip()]

    def _set_workflow_status(self, text: str, ok: bool = True) -> None:
        color = T.GREEN if ok else T.ERROR
        self._workflow_status_lbl.setText(text)
        self._workflow_status_lbl.setStyleSheet(
            f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )

    def _set_workflow_outcome(self, text: str, ok: bool = True) -> None:
        color = T.PRIMARY_DIM if ok else T.ERROR
        self._workflow_outcome_lbl.setText(f"Outcome: {text}")
        self._workflow_outcome_lbl.setStyleSheet(
            f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )

    def _set_workflow_evidence(self, text: str) -> None:
        self._workflow_evidence_lbl.setText(f"Evidence: {text}")

    def _sync_workflow_recipe(self) -> None:
        recipe = self._workflow_recipe()
        commands = self._workflow_commands()
        summary = str(recipe.get("summary", "") or "").strip()
        self._workflow_summary_lbl.setText(summary or "No workflow summary available.")
        if commands:
            rendered = "  |  ".join(f"{idx + 1}. {cmd}" for idx, cmd in enumerate(commands))
            self._workflow_steps_lbl.setText(rendered)
            self._workflow_next_step_lbl.setText(
                f"Next step: load the first command for a guided start, or run all {len(commands)} commands in the embedded terminal."
            )
            self._set_workflow_outcome(f"{str(recipe.get('title', 'WORKFLOW'))} is ready with {len(commands)} command(s).")
            self._set_workflow_evidence(
                f"{len(commands)} command(s) ready | shell status: {self._terminal_status_lbl.text().lower()} | operator logs will mirror warnings and failures."
            )
        else:
            self._workflow_steps_lbl.setText("No commands configured for this workflow.")
            self._workflow_next_step_lbl.setText("Next step: choose a workflow with at least one command.")
            self._set_workflow_outcome("No runnable commands are configured for this workflow.", ok=False)
            self._set_workflow_evidence("No runnable commands are available for this workflow.")

    def _load_workflow_recipe(self) -> None:
        recipe = self._workflow_recipe()
        commands = self._workflow_commands()
        if not commands:
            self._set_workflow_status("Workflow recipe is empty", ok=False)
            self._set_workflow_outcome("Nothing was loaded because this workflow has no commands.", ok=False)
            return
        title = str(recipe.get("title", "WORKFLOW")).strip() or "WORKFLOW"
        self._terminal_input.setText(commands[0])
        self._append_terminal_output(f"[workflow] {title} loaded ({len(commands)} commands)")
        for idx, cmd in enumerate(commands, start=1):
            self._append_terminal_output(f"[workflow:{idx}] {cmd}")
        self._terminal_input.setFocus()
        self._set_workflow_status(f"Loaded {title} into the terminal input", ok=True)
        self._set_workflow_outcome(f"Loaded the first command for {title}. Review it before you run the rest.")
        self._workflow_next_step_lbl.setText(
            f"Next step: review the first command, then press RUN or continue through the remaining {len(commands) - 1} command(s)."
        )
        self._set_workflow_evidence(
            f"{title} loaded | first command is in the terminal input | {max(0, len(commands) - 1)} command(s) remain after this guided step."
        )

    def _run_terminal_commands(self, commands: list[str], *, label: str) -> bool:
        cleaned = [str(item).strip() for item in commands if str(item).strip()]
        if not cleaned:
            self._append_terminal_output(f"[launcher] {label} has no commands to run")
            self._set_workflow_outcome(f"{label} did not start because no commands were available.", ok=False)
            return False
        if not self._ensure_terminal_process():
            self._set_workflow_status(f"{label} could not start the embedded shell", ok=False)
            self._set_workflow_outcome(f"{label} could not start because the embedded shell was unavailable.", ok=False)
            return False
        proc = self._terminal_process
        if proc is None or proc.stdin is None:
            self._append_terminal_output("[launcher] terminal stdin unavailable")
            self._set_workflow_status(f"{label} could not access terminal stdin", ok=False)
            self._set_workflow_outcome(f"{label} could not start because terminal input was unavailable.", ok=False)
            return False
        self._append_terminal_output(f"[workflow] running {label} ({len(cleaned)} commands)")
        try:
            for idx, command in enumerate(cleaned, start=1):
                self._append_terminal_output(f"> [{idx}/{len(cleaned)}] {command}")
                proc.stdin.write(command + "\n")
            proc.stdin.flush()
            self._terminal_status_lbl.setText(f"Shell running {label.lower()}")
            self._terminal_focus_pending = True
            self._set_workflow_outcome(f"{label} queued {len(cleaned)} command(s) in the embedded terminal.")
            self._set_workflow_evidence(
                f"{label} queued {len(cleaned)} command(s) | watch embedded terminal output and operator logs for pass/fail evidence."
            )
            return True
        except Exception as exc:
            self._append_terminal_output(f"[launcher] workflow run failed: {exc}")
            self._set_workflow_status(f"{label} failed: {exc}", ok=False)
            self._set_workflow_outcome(f"{label} failed before queueing all commands: {exc}", ok=False)
            self._set_workflow_evidence(f"{label} failed before queueing all commands. Check operator logs and terminal output.")
            return False

    def _run_workflow_recipe(self) -> None:
        recipe = self._workflow_recipe()
        title = str(recipe.get("title", "WORKFLOW")).strip() or "WORKFLOW"
        commands = self._workflow_commands()
        if self._run_terminal_commands(commands, label=title):
            self._set_workflow_status(f"Queued {title} in the embedded terminal", ok=True)
            self._workflow_next_step_lbl.setText(
                f"Next step: watch the embedded terminal and operator logs while {len(commands)} command(s) run."
            )

    def _append_terminal_output(self, text: str) -> None:
        current = self._terminal_output.toPlainText().splitlines()
        current.extend(str(text or "").splitlines() or [""])
        self._terminal_output.setPlainText("\n".join(current[-400:]))
        bar = self._terminal_output.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _ensure_terminal_process(self) -> bool:
        if self._terminal_process and self._terminal_process.poll() is None:
            return True
        try:
            self._terminal_process = subprocess.Popen(
                ["powershell", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-NoExit", "-Command", "-"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(_ROOT),
                bufsize=1,
            )
        except Exception as exc:
            self._terminal_status_lbl.setText(f"Shell failed: {exc}")
            self._append_terminal_output(f"[launcher] terminal start failed: {exc}")
            return False

        self._terminal_status_lbl.setText(f"Shell ready [pid={self._terminal_process.pid}]")
        self._append_terminal_output(f"[launcher] embedded PowerShell ready in {_ROOT}")
        self._start_terminal_reader(self._terminal_process.stdout, "stdout")
        self._start_terminal_reader(self._terminal_process.stderr, "stderr")
        return True

    def _start_terminal_reader(self, stream, stream_name: str) -> None:
        if stream is None:
            return

        def _reader() -> None:
            while True:
                try:
                    line = stream.readline()
                except Exception as exc:
                    self._terminal_queue.put(("stderr", f"[launcher] terminal reader failed: {exc}"))
                    break
                if line == "":
                    break
                self._terminal_queue.put((stream_name, line.rstrip("\n")))

        threading.Thread(target=_reader, daemon=True).start()

    def _submit_terminal_command(self) -> None:
        command = self._terminal_input.text().strip()
        if not command:
            return
        if not self._ensure_terminal_process():
            return
        proc = self._terminal_process
        if proc is None or proc.stdin is None:
            self._append_terminal_output("[launcher] terminal stdin unavailable")
            return
        self._append_terminal_output(f"> {command}")
        try:
            proc.stdin.write(command + "\n")
            proc.stdin.flush()
            self._terminal_status_lbl.setText("Shell running command")
            self._terminal_input.clear()
        except Exception as exc:
            self._append_terminal_output(f"[launcher] terminal write failed: {exc}")
            self._terminal_status_lbl.setText(f"Shell write failed: {exc}")

    def _drain_terminal_queue(self) -> None:
        drained = 0
        while drained < 80:
            try:
                stream_name, line = self._terminal_queue.get_nowait()
            except queue.Empty:
                break
            if line:
                prefix = "[stderr] " if stream_name == "stderr" else ""
                self._append_terminal_output(prefix + line)
                if self._terminal_focus_pending:
                    self._terminal_output.setFocus()
                    self._terminal_focus_pending = False
            drained += 1

        if self._terminal_process is not None and self._terminal_process.poll() is not None:
            code = self._terminal_process.returncode
            self._terminal_status_lbl.setText(f"Shell exited [{code}]")
            self._terminal_process = None

    def _stop_terminal_process(self) -> None:
        proc = self._terminal_process
        if proc is None or proc.poll() is not None:
            self._terminal_status_lbl.setText("Shell idle")
            return
        try:
            proc.terminate()
            self._append_terminal_output("[launcher] stop requested")
            self._terminal_status_lbl.setText("Shell stopping")
        except Exception as exc:
            self._append_terminal_output(f"[launcher] stop failed: {exc}")

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._stop_terminal_process()
        super().closeEvent(event)

    def _event_level(self, item: dict[str, object]) -> str:
        event = str(item.get("event", "") or "").lower()
        summary = json.dumps(item, ensure_ascii=True).lower()
        if "error" in event or "error" in summary or "failed" in summary:
            return "ERROR"
        if "warn" in event or "warning" in summary or "over_budget" in event:
            return "WARN"
        return "INFO"

    def _read_launcher_events(self) -> list[dict[str, object]]:
        path = _ROOT / "runtime" / "launcher_events.jsonl"
        if not path.exists():
            return []
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            return []
        items: list[dict[str, object]] = []
        for line in lines[-120:]:
            txt = line.strip()
            if not txt:
                continue
            try:
                obj = json.loads(txt)
            except Exception:
                continue
            if isinstance(obj, dict):
                items.append(obj)
        return items

    def _refresh_operator_logs(self) -> None:
        items = self._read_launcher_events()
        lines: list[str] = []
        for item in items:
            level = self._event_level(item)
            if self._log_filter != "ALL" and level != self._log_filter:
                continue
            ts = str(item.get("ts", ""))
            event = str(item.get("event", "event"))
            detail = ""
            if event in {"recovery_result", "recovery_error"}:
                detail = str(item.get("summary", ""))
            elif event == "auth_retry_result":
                detail = str(item.get("error", "ok"))
            elif event == "ui_poll_over_budget":
                detail = f"poll_ms={item.get('poll_ms', '?')}"
            elif event == "startup_phase_over_budget":
                detail = f"phase={item.get('phase', '?')} duration={item.get('duration_ms', '?')}ms"
            lines.append(f"[{level}] {ts} {event}" + (f" :: {detail}" if detail else ""))
        self._syslog.setPlainText(
            "\n".join(lines[-50:])
            if lines
            else "No operator log entries matched the current filter yet. Recovery runs, workflow actions, and launcher warnings will appear here."
        )
