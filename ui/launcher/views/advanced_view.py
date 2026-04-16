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
from uuid import uuid4

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
_TERMINAL_RECIPE_MARKER = "__GUPPY_RECIPE__|"

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


def _service_purpose(connector_id: str) -> str:
    return {
        "gmail": "Email",
        "calendar": "Calendar",
        "spotify": "Music",
        "youtube": "Video tools",
        "crm": "Customer records",
        "voip": "Calling",
    }.get(str(connector_id or "").strip().lower(), "Connected service")


def _friendly_auth_state(auth_state: str) -> str:
    normalized = str(auth_state or "").strip().lower()
    return {
        "ready": "Connected",
        "optional": "Optional",
        "partial": "Almost ready",
        "missing": "Needs setup",
    }.get(normalized, "Needs setup")


def _clean_guidance_text(text: str) -> str:
    cleaned = str(text or "").strip()
    replacements = (
        ("App Mgmt:", ""),
        ("Workspaces >", ""),
        ("App Mgmt >", ""),
    )
    for old, new in replacements:
        cleaned = cleaned.replace(old, new)
    return " ".join(cleaned.split())


def _pipe_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for segment in [part.strip() for part in str(text or "").split("|") if part.strip()]:
        if ":" in segment:
            label, value = segment.split(":", 1)
            fields[label.strip().lower()] = value.strip()
    return fields


class AdvancedView(QWidget):
    recovery_requested = Signal(str)
    windows_ops_requested = Signal(str)
    connector_action_requested = Signal(dict)
    terminal_recipe_finished = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._diagnostics: dict[str, str] = {}
        self._log_filter = "ALL"
        self._details_visible = False
        self._terminal_queue: queue.SimpleQueue[tuple[str, str]] = queue.SimpleQueue()
        self._terminal_process: subprocess.Popen[str] | None = None
        self._terminal_focus_pending = False
        self._terminal_recipes: dict[str, dict[str, object]] = {}
        self._windows_ops: dict[str, str] = self._build_windows_ops_snapshot()
        self._connector_inventory: list[dict[str, object]] = []
        self._detail_frames: list[QFrame] = []
        self._detail_widgets: list[QWidget] = []

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
        title = QLabel("Setup & Health")
        title.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_HEAD}';"
            f"font-size: 30pt; font-weight: 900; letter-spacing: -1px;"
        )
        title_row.addWidget(title)
        title_row.addStretch()
        self._details_btn = QPushButton("SHOW DETAILS")
        self._details_btn.setStyleSheet(
            f"QPushButton {{ background: {T.BG0}; color: {T.DIM}; border: 1px solid {T.BORDER};"
            f" padding: 5px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: {T.PRIMARY}; color: {T.PRIMARY}; }}"
        )
        self._details_btn.clicked.connect(self._toggle_details)
        title_row.addWidget(self._details_btn)
        layout.addLayout(title_row)

        # sub-info
        info_row = QHBoxLayout()
        info_row.setSpacing(8)
        dot = QLabel("*")
        dot.setStyleSheet(f"color: {T.PRIMARY}; font-size: {T.FS_TINY}pt;")
        info_row.addWidget(dot)
        info_row.addWidget(_mono("SETUP + RECOVERY", T.PRIMARY, T.FS_TINY))
        info_row.addSpacing(12)
        info_row.addWidget(_mono("HEALTH / RECOVERY / SETTINGS / DESKTOP RUNTIME", T.DIM, T.FS_TINY))
        info_row.addStretch()
        layout.addLayout(info_row)
        layout.addSpacing(12)

        self._boundary_frame = QFrame()
        self._boundary_frame.setStyleSheet(
            f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}"
        )
        boundary_layout = QVBoxLayout(self._boundary_frame)
        boundary_layout.setContentsMargins(12, 10, 12, 10)
        boundary_layout.setSpacing(4)
        boundary_layout.addWidget(_mono("BOUNDARY", T.PRIMARY, T.FS_TINY, True))
        boundary_layout.addWidget(_mono("Open this tab for app-wide recovery, diagnostics, settings, workflow loops, operator logs, and the Home context that no longer lives above the chat. Workspace task tools now live in the right tray.", T.DIM, T.FS_SMALL))
        layout.addWidget(self._boundary_frame)
        self._detail_frames.append(self._boundary_frame)

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
                "Home stays focused on conversation. This page keeps setup, health, and recovery in one place.",
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
            f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}"
        )
        actions_layout = QVBoxLayout(actions_frame)
        actions_layout.setContentsMargins(16, 14, 16, 14)
        actions_layout.setSpacing(10)
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
        windows_ops_layout.setContentsMargins(16, 14, 16, 14)
        windows_ops_layout.setSpacing(8)
        windows_ops_layout.addWidget(_mono("DESKTOP RUNTIME", T.PRIMARY, T.FS_TINY, True))
        windows_ops_layout.addWidget(
            _mono(
                "See what is installed, which local AI runtime is active, and what to try next if something needs repair.",
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
        windows_actions = QHBoxLayout()
        for label, action, accent in [
            ("VERIFY", "verify_runtime", T.PRIMARY),
            ("UPDATE", "update_runtime", T.PRIMARY_DIM),
            ("PACKAGE", "package_desktop", T.SECONDARY),
            ("RELEASE DRY RUN", "release_dry_run", T.PRIMARY),
            ("SUPERVISED API", "start_supervised_api", T.PRIMARY_DIM),
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
        connectors_layout.setContentsMargins(16, 14, 16, 14)
        connectors_layout.setSpacing(8)
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

        self._workflow_frame = QFrame()
        self._workflow_frame.setStyleSheet(
            f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}"
        )
        workflow_layout = QVBoxLayout(self._workflow_frame)
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
        layout.addWidget(self._workflow_frame)
        self._detail_frames.append(self._workflow_frame)

        self._operator_logs_frame = QFrame()
        self._operator_logs_frame.setObjectName("syslog_term")
        self._operator_logs_frame.setStyleSheet(
            f"QFrame#syslog_term {{ background-color: {T.BG0}; border: 1px solid {T.BORDER}; }}"
        )
        term_layout = QVBoxLayout(self._operator_logs_frame)
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
        layout.addWidget(self._operator_logs_frame)
        self._detail_frames.append(self._operator_logs_frame)

        self._terminal_frame = QFrame()
        self._terminal_frame.setObjectName("embedded_terminal")
        self._terminal_frame.setStyleSheet(
            f"QFrame#embedded_terminal {{ background-color: {T.BG0}; border: 1px solid {T.BORDER}; }}"
        )
        terminal_layout = QVBoxLayout(self._terminal_frame)
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
        layout.addWidget(self._terminal_frame)
        self._detail_frames.append(self._terminal_frame)

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
        self._detail_widgets.extend(
            [
                self._daily_route_lbl,
                self._route_health_lbl,
                self._resource_lbl,
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

    def attach_settings_panel(self, widget: QWidget) -> None:
        while self._settings_host.count():
            item = self._settings_host.takeAt(0)
            if item is None:
                continue
            child = item.widget()
            if child is not None:
                child.setParent(None)
        self._settings_host.addWidget(widget)

    def _toggle_details(self) -> None:
        self._details_visible = not self._details_visible
        self._sync_detail_visibility()

    def _sync_detail_visibility(self) -> None:
        for frame in self._detail_frames:
            frame.setVisible(self._details_visible)
        for widget in self._detail_widgets:
            widget.setVisible(self._details_visible)
        self._details_btn.setText("HIDE DETAILS" if self._details_visible else "SHOW DETAILS")

    def append_log(self, line: str) -> None:
        current = self._syslog.toPlainText().splitlines()
        current.append(f"> {line}")
        self._syslog.setPlainText("\n".join(current[-40:]))

    def set_recovery_status(self, text: str) -> None:
        msg = (text or "Nothing needs attention right now.").strip() or "Nothing needs attention right now."
        self._recovery_status.setText(msg)
        self._last_recovery_lbl.setText(f"Last recovery action: {msg}")
        runtime_line = self._windows_ops.get("runtime", "")
        self._windows_ops = self._build_windows_ops_snapshot()
        if runtime_line:
            self._windows_ops["runtime"] = runtime_line
        self._refresh_windows_ops_labels()

    def set_daily_context_activity(self, text: str) -> None:
        msg = (text or "launcher ready").strip() or "launcher ready"
        self._daily_activity_lbl.setText(f"Recent activity: {msg}")

    def set_daily_context_workspace(self, text: str) -> None:
        msg = (text or "workspace context unavailable").strip() or "workspace context unavailable"
        self._daily_workspace_lbl.setText(msg)

    def set_daily_context_runtime(self, text: str) -> None:
        msg = (text or "runtime details unavailable").strip() or "runtime details unavailable"
        self._daily_runtime_lbl.setText(msg if ":" in msg else f"Ready now: {msg}")

    def set_daily_context_route(self, text: str) -> None:
        msg = (text or "route preview unavailable").strip() or "route preview unavailable"
        self._daily_route_lbl.setText(msg)

    def set_daily_context_recovery(self, text: str, ok: bool = True) -> None:
        msg = (text or "Recovery: all clear").strip() or "Recovery: all clear"
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
        self._health_lbl.setText(f"API health: {api_state} | Startup readiness: {startup_overall}")

        voice_tts = str(payload.get("voice_tts_backend", "unknown") or "unknown")
        voice_stt = str(payload.get("voice_stt_backend", "unknown") or "unknown")
        binding = str(payload.get("voice_binding", "") or "").strip()
        self._voice_lbl.setText(
            f"Voice services: tts={voice_tts} | stt={voice_stt}" + (f" | {binding}" if binding else "")
        )

        route_evidence = str(payload.get("route_evidence", "") or "").strip()
        self._route_health_lbl.setText(
            f"Why the next route was chosen: {route_evidence or 'waiting for the next route preview'}"
        )

        envelope = payload.get("resource_envelope", {})
        if isinstance(envelope, dict):
            state = str(envelope.get("state", "unknown") or "unknown")
            detail = str(envelope.get("message", envelope.get("detail", "")) or "").strip()
            self._resource_lbl.setText(f"System headroom: {state}" + (f" | {detail}" if detail else ""))
        self._refresh_windows_ops_labels()

        local_runtime = payload.get("local_runtime", {})
        if isinstance(local_runtime, dict):
            configured_backend = self._configured_local_runtime_backend()
            live_backend = str(local_runtime.get("backend", configured_backend.lower()) or configured_backend).strip().upper()
            live_state = str(local_runtime.get("state", "unknown") or "unknown").strip().upper()
            live_detail = str(local_runtime.get("detail", "") or "").strip()
            self._windows_ops["runtime"] = (
                f"Local AI runtime: {configured_backend} | Live backend: {live_backend} | Status: {live_state}"
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
            f"Workspaces: active={active_instance} | configured {configured}/{max_configured} | live {active_runtime}/{max_active_runtime}"
        )

    @staticmethod
    def _selector_label(item: dict[str, object], *, fallback: str) -> str:
        label = str(item.get("label", item.get("id", fallback)) or fallback).strip() or fallback
        auth_state = str(item.get("auth_state", "") or "").strip().upper()
        if auth_state:
            label += f" [{auth_state}]"
        return label

    @staticmethod
    def _history_line(history: dict[str, object]) -> str:
        last_action = str(history.get("last_action", "") or "").strip()
        last_action_at = str(history.get("last_action_at", "") or "").strip()
        last_result = str(history.get("last_result", "") or "").strip()
        last_event_id = str(history.get("last_event_id", "") or "").strip()
        if not last_action:
            return "History: no connector action has been recorded yet."
        summary = f"History: last {last_action}"
        if last_action_at:
            summary += f" @ {last_action_at}"
        if last_result:
            summary += f" | {last_result}"
        if last_event_id:
            summary += f" | Ref: {last_event_id}"
        return summary

    @staticmethod
    def _recent_history_line(history: dict[str, object]) -> str:
        recent_summary = str(history.get("recent_summary", "") or "").strip()
        if recent_summary:
            return "Recent attempts: " + recent_summary
        timeline = [item for item in history.get("timeline", []) if isinstance(item, dict)] if isinstance(history.get("timeline"), list) else []
        if not timeline:
            return "Recent attempts: none recorded yet."
        rendered: list[str] = []
        for item in timeline[-3:]:
            action = str(item.get("action", "action") or "action").strip()
            state = "OK" if bool(item.get("ok", False)) else "FAIL"
            ref = str(item.get("event_id", "") or "").strip()
            text = f"{action}={state}"
            if ref:
                text += f" ref={ref}"
            rendered.append(text)
        return "Recent attempts: " + " | ".join(rendered)

    def _connector_action_validation(
        self,
        *,
        item: dict[str, object],
        action: str,
        provider_payload: dict[str, object],
        selected_secret_key: str,
        secret_value: str,
    ) -> str:
        connector_id = str(item.get("id", self._connector_cb.currentText()) or self._connector_cb.currentText()).strip().lower()
        providers = [row for row in item.get("providers", []) if isinstance(row, dict)] if isinstance(item.get("providers"), list) else []
        if providers and not provider_payload:
            return "Choose a provider from the connector inventory before running this action."
        if action in {"connect", "save_secret"}:
            field_details = [
                row for row in provider_payload.get("field_details", [])
                if isinstance(row, dict)
            ] if isinstance(provider_payload.get("field_details"), list) else []
            needs_secret = bool(field_details) or self._connector_secret_key.count() > 1
            if needs_secret and not selected_secret_key:
                return "Choose which provider field you want to save before continuing."
            if selected_secret_key and not secret_value:
                selected_field = next(
                    (
                        row for row in field_details
                        if str(row.get("key", "")).strip() == selected_secret_key
                    ),
                    {},
                )
                field_label = str(selected_field.get("label", selected_secret_key) or selected_secret_key).strip() or selected_secret_key
                return f"Enter a value for {field_label} before saving it."
        if action == "reconnect" and connector_id in {"crm", "voip", "youtube"}:
            return f"{connector_id} does not expose reconnect in this guided secret flow."
        return ""

    def set_connector_inventory(self, items: list[dict[str, object]]) -> None:
        self._connector_inventory = [item for item in items if isinstance(item, dict)]
        current = str(self._connector_cb.currentData() or self._connector_cb.currentText() or "").strip().lower()
        self._connector_cb.blockSignals(True)
        self._connector_cb.clear()
        for item in self._connector_inventory:
            connector_id = str(item.get("id", "")).strip().lower()
            label = str(item.get("label", connector_id.title()) or connector_id.title())
            if connector_id:
                self._connector_cb.addItem(label, connector_id)
        if self._connector_cb.count() == 0:
            for connector_id, label in (
                ("gmail", "Gmail"),
                ("calendar", "Calendar"),
                ("spotify", "Spotify"),
                ("youtube", "YouTube"),
                ("crm", "CRM"),
                ("voip", "VoIP"),
            ):
                self._connector_cb.addItem(label, connector_id)
        idx = self._connector_cb.findData(current)
        self._connector_cb.setCurrentIndex(max(0, idx))
        self._connector_cb.blockSignals(False)
        self._sync_connector_controls()

    def _current_connector_payload(self) -> dict[str, object]:
        connector_id = str(self._connector_cb.currentData() or self._connector_cb.currentText() or "").strip().lower()
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
        providers = [row for row in item.get("providers", []) if isinstance(row, dict)] if isinstance(item.get("providers"), list) else []
        accounts = [row for row in item.get("accounts", []) if isinstance(row, dict)] if isinstance(item.get("accounts"), list) else []
        history = item.get("history", {}) if isinstance(item.get("history"), dict) else {}
        scope = item.get("scope_telemetry", {}) if isinstance(item.get("scope_telemetry"), dict) else {}
        previous_provider = str(self._connector_provider.currentData() or "").strip().lower()
        previous_account = str(self._connector_account.currentData() or "").strip().lower()
        selected_provider_payload = next(
            (row for row in providers if str(row.get("id", "")).strip().lower() == previous_provider),
            providers[0] if providers else {},
        )
        provider_field_details = [
            row for row in selected_provider_payload.get("field_details", [])
            if isinstance(row, dict)
        ] if isinstance(selected_provider_payload, dict) and isinstance(selected_provider_payload.get("field_details"), list) else []
        provider_secret_fields = [
            str(row.get("key", "")).strip()
            for row in provider_field_details
            if str(row.get("key", "")).strip()
        ] or (list(selected_provider_payload.get("required_fields", [])) if isinstance(selected_provider_payload, dict) else [])
        secret_fields = provider_secret_fields or (
            item.get("secret_fields", []) if isinstance(item.get("secret_fields"), list) else []
        )
        for combo, values, default_label in (
            (self._connector_provider, providers, "(provider)"),
            (self._connector_account, accounts, "(account)"),
        ):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(default_label, "")
            for value in values:
                combo.addItem(self._selector_label(value, fallback=default_label), str(value.get("id", "")))
            target = previous_provider if combo is self._connector_provider else previous_account
            idx = combo.findData(target)
            if not target and values:
                combo.setCurrentIndex(1)
            else:
                combo.setCurrentIndex(0 if idx < 0 else idx)
            combo.blockSignals(False)
        self._connector_secret_key.blockSignals(True)
        previous_secret_key = str(self._connector_secret_key.currentData() or "").strip()
        self._connector_secret_key.clear()
        self._connector_secret_key.addItem("(secret field)", "")
        for field in secret_fields:
            self._connector_secret_key.addItem(str(field), str(field))
        secret_idx = self._connector_secret_key.findData(previous_secret_key)
        default_secret_key = str(selected_provider_payload.get("next_field", {}).get("key", "") or "").strip() if isinstance(selected_provider_payload, dict) else ""
        if default_secret_key:
            secret_idx = self._connector_secret_key.findData(default_secret_key)
        if not previous_secret_key and secret_fields:
            self._connector_secret_key.setCurrentIndex(1)
        else:
            self._connector_secret_key.setCurrentIndex(0 if secret_idx < 0 else secret_idx)
        self._connector_secret_key.blockSignals(False)
        selected_provider = str(self._connector_provider.currentData() or "").strip().lower()
        if selected_provider and selected_provider != previous_provider:
            matching_provider = next(
                (row for row in providers if str(row.get("id", "")).strip().lower() == selected_provider),
                {},
            )
            matching_field_details = [
                row for row in matching_provider.get("field_details", [])
                if isinstance(row, dict)
            ] if isinstance(matching_provider, dict) and isinstance(matching_provider.get("field_details"), list) else []
            secret_fields = [
                str(row.get("key", "")).strip()
                for row in matching_field_details
                if str(row.get("key", "")).strip()
            ] or (list(matching_provider.get("required_fields", [])) if isinstance(matching_provider, dict) else secret_fields)
            self._connector_secret_key.blockSignals(True)
            self._connector_secret_key.clear()
            self._connector_secret_key.addItem("(secret field)", "")
            for field in secret_fields or (item.get("secret_fields", []) if isinstance(item.get("secret_fields"), list) else []):
                self._connector_secret_key.addItem(str(field), str(field))
            default_secret_key = str(matching_provider.get("next_field", {}).get("key", "") or "").strip() if isinstance(matching_provider, dict) else ""
            default_idx = self._connector_secret_key.findData(default_secret_key)
            if default_idx > 0:
                self._connector_secret_key.setCurrentIndex(default_idx)
            elif self._connector_secret_key.count() > 1:
                self._connector_secret_key.setCurrentIndex(1)
            self._connector_secret_key.blockSignals(False)
        connector_id = str(item.get("id", self._connector_cb.currentText()) or self._connector_cb.currentText()).strip().lower()
        auth_kind = str(item.get("auth_kind", "unknown") or "unknown")
        auth_state = str(item.get("auth_state", "unknown") or "unknown").upper()
        source = str(item.get("source", "none") or "none").upper()
        detail = str(item.get("auth_detail", "") or "").strip()
        actions = [str(action) for action in item.get("actions_supported", []) if str(action).strip()]
        selected_provider_payload = next(
            (
                row
                for row in providers
                if str(row.get("id", "")).strip().lower() == str(self._connector_provider.currentData() or "").strip().lower()
            ),
            {},
        )
        provider_field_details = [
            row for row in selected_provider_payload.get("field_details", [])
            if isinstance(row, dict)
        ] if isinstance(selected_provider_payload, dict) and isinstance(selected_provider_payload.get("field_details"), list) else []
        selected_account_payload = next(
            (
                row
                for row in accounts
                if str(row.get("id", "")).strip().lower() == str(self._connector_account.currentData() or "").strip().lower()
            ),
            {},
        )
        selected_secret_key = str(self._connector_secret_key.currentData() or "").strip()
        selected_field_detail = next(
            (
                row
                for row in provider_field_details
                if str(row.get("key", "")).strip() == selected_secret_key
            ),
            {},
        )
        connector_label = str(item.get("label", connector_id or "Service") or connector_id or "Service")
        purpose = _service_purpose(connector_id)
        self._connector_state_lbl.setText(f"{connector_label} helps with {purpose.lower()} on this PC.")
        self._connector_auth_lbl.setText(f"Connection status: {_friendly_auth_state(auth_state)}")
        self._connector_detail_lbl.setText(
            _clean_guidance_text(detail or f"Choose {connector_label} to see how to connect it.")
        )
        validation_bits: list[str] = []
        if providers:
            if selected_provider_payload:
                validation_bits.append(str(selected_provider_payload.get("auth_detail", "") or "").strip())
                setup_summary = str(selected_provider_payload.get("setup_summary", "") or "").strip()
                if setup_summary:
                    validation_bits.append(setup_summary)
                verify_summary = str(selected_provider_payload.get("verify_summary", "") or "").strip()
                if verify_summary:
                    validation_bits.append(verify_summary)
                verify_check_summary = str(selected_provider_payload.get("verify_check_summary", "") or "").strip()
                if verify_check_summary:
                    validation_bits.append("Checks: " + verify_check_summary)
            else:
                validation_bits.append("Choose a provider before you save or verify this connector.")
        if accounts:
            if selected_account_payload:
                validation_bits.append(str(selected_account_payload.get("auth_detail", "") or "").strip())
            else:
                validation_bits.append("Choose which account you want to use on this PC.")
        if not validation_bits:
            validation_bits.append(detail or "This service is ready to review.")
        self._connector_validation_lbl.setText(
            "What to do next: " + " | ".join(_clean_guidance_text(bit) for bit in validation_bits if bit)
        )
        endpoint_prefixes = [str(item) for item in scope.get("endpoint_prefixes", []) if str(item).strip()]
        scope_summary = str(scope.get("summary", "") or "").strip()
        selected_scope = str(selected_provider_payload.get("scope_label", "") or selected_account_payload.get("label", "") or "").strip()
        rendered_scope = selected_scope or scope_summary or "No explicit scope guidance is available."
        provider_scope_detail = str(selected_provider_payload.get("scope_detail", "") or "").strip()
        if provider_scope_detail:
            rendered_scope += f" | {provider_scope_detail}"
        if endpoint_prefixes:
            rendered_scope += f" | {len(endpoint_prefixes[:3])} machine actions available"
        self._connector_scope_lbl.setText(f"What it can help with: {_clean_guidance_text(rendered_scope)}")
        if provider_field_details:
            present_count = len([row for row in provider_field_details if bool(row.get("present", False))])
            total_count = len(provider_field_details)
            next_field = selected_provider_payload.get("next_field", {}) if isinstance(selected_provider_payload, dict) else {}
            next_label = str(next_field.get("label", next_field.get("key", "")) or next_field.get("key", "")).strip()
            next_hint = str(next_field.get("validation_hint", "") or next_field.get("input_hint", "") or "").strip()
            setup_text = f"Saved details: {present_count}/{total_count} ready"
            if next_label and present_count < total_count:
                setup_text += f" | Next: add {next_label}"
            if next_hint:
                setup_text += f" | {next_hint}"
            self._connector_setup_lbl.setText(setup_text)
        elif secret_fields:
            self._connector_setup_lbl.setText(
                "Saved details: choose the detail you want to save, then test the connection."
            )
        else:
            self._connector_setup_lbl.setText(
                "Saved details: this service mostly uses account selection or browser sign-in."
            )
        next_step = str(selected_provider_payload.get("next_step", "") or item.get("next_step", "") or "").strip()
        fix_target = str(selected_provider_payload.get("fix_target", "") or item.get("fix_target", "") or "").strip()
        if next_step:
            self._connector_next_step_lbl.setText(
                "Next step: " + _clean_guidance_text(next_step) + (f" | Change it in {fix_target}" if fix_target else "")
            )
        else:
            self._connector_next_step_lbl.setText("Next step: choose a service or test the current connection.")
        self._connector_history_lbl.setText(self._history_line(history))
        self._connector_recent_lbl.setText(self._recent_history_line(history))
        if provider_field_details:
            field_summary = ", ".join(
                f"{str(row.get('label', row.get('key', 'field')))}={'READY' if bool(row.get('present', False)) else 'MISSING'}"
                for row in provider_field_details
            )
            self._connector_secret_lbl.setText("Saved details: " + (field_summary or "none"))
        else:
            self._connector_secret_lbl.setText(
                "Saved details: " + (", ".join(str(field) for field in secret_fields) if secret_fields else "none")
            )
        placeholder = "secret value for API-key or provider-backed connectors"
        masked = True
        if selected_field_detail:
            placeholder = str(
                selected_field_detail.get("placeholder")
                or selected_field_detail.get("input_hint")
                or placeholder
            ).strip() or placeholder
            masked = bool(selected_field_detail.get("masked", True))
        self._connector_secret_value.setPlaceholderText(placeholder)
        self._connector_secret_value.setEchoMode(
            QLineEdit.EchoMode.Password if masked and bool(selected_secret_key) else QLineEdit.EchoMode.Normal
        )
        supported = set(actions)
        provider_required = bool(providers)
        provider_selected = bool(selected_provider_payload) or not provider_required
        if auth_kind == "api_key":
            self._connector_action_buttons["verify"].setText("TEST KEY")
            self._connector_action_buttons["connect"].setText("SAVE KEY")
            self._connector_action_buttons["reconnect"].setText("RECONNECT")
            self._connector_action_buttons["disconnect"].setText("REMOVE KEY")
        elif auth_kind == "oauth_file_token":
            self._connector_action_buttons["verify"].setText("CHECK SIGN-IN")
            self._connector_action_buttons["connect"].setText("SIGN IN")
            self._connector_action_buttons["reconnect"].setText("SIGN IN AGAIN")
            self._connector_action_buttons["disconnect"].setText("REMOVE SIGN-IN")
        elif auth_kind in {"provider_secret", "oauth_secret"}:
            self._connector_action_buttons["verify"].setText("CHECK SETUP")
            self._connector_action_buttons["connect"].setText("SAVE DETAILS")
            self._connector_action_buttons["reconnect"].setText("RECONNECT")
            self._connector_action_buttons["disconnect"].setText("CLEAR DETAILS")
        else:
            self._connector_action_buttons["verify"].setText("VERIFY")
            self._connector_action_buttons["connect"].setText("CONNECT")
            self._connector_action_buttons["reconnect"].setText("RECONNECT")
            self._connector_action_buttons["disconnect"].setText("DISCONNECT")
        for action_name, button in self._connector_action_buttons.items():
            resolved_action = "connect" if action_name == "save_secret" else "disconnect" if action_name == "clear_secret" else action_name
            enabled = resolved_action in supported
            if action_name in {"save_secret", "clear_secret"}:
                enabled = enabled and self._connector_secret_key.count() > 1
            enabled = enabled and provider_selected
            if auth_kind == "api_key" and action_name in {"connect", "reconnect"}:
                button.setVisible(False)
            elif auth_kind == "provider_secret" and action_name == "reconnect":
                button.setVisible(False)
            else:
                button.setVisible(True)
            button.setEnabled(enabled)
            if enabled:
                button.setToolTip("")
            elif provider_required and not provider_selected:
                button.setToolTip("Choose a provider from the inventory before running connector actions.")
            else:
                button.setToolTip(f"{connector_id or 'connector'} does not support {resolved_action}.")

    def _emit_connector_action(self, action: str) -> None:
        connector_id = str(self._connector_cb.currentData() or self._connector_cb.currentText() or "").strip().lower()
        if not connector_id:
            self.append_log("connector action ignored: choose a connector first")
            return
        resolved_action = "connect" if action == "save_secret" else "disconnect" if action == "clear_secret" else action
        item = self._current_connector_payload()
        provider_payload = next(
            (
                row
                for row in item.get("providers", [])
                if isinstance(row, dict) and str(row.get("id", "")).strip().lower() == str(self._connector_provider.currentData() or "").strip().lower()
            ),
            {},
        ) if isinstance(item.get("providers"), list) else {}
        selected_secret_key = str(self._connector_secret_key.currentData() or "").strip()
        secret_value = self._connector_secret_value.text().strip()
        validation_error = self._connector_action_validation(
            item=item,
            action=action,
            provider_payload=provider_payload,
            selected_secret_key=selected_secret_key,
            secret_value=secret_value,
        )
        if validation_error:
            self.append_log(f"connector action blocked: {validation_error}")
            return
        self.connector_action_requested.emit(
            {
                "connector": connector_id,
                "action": resolved_action,
                "provider": str(self._connector_provider.currentData() or "").strip(),
                "account_id": str(self._connector_account.currentData() or "").strip(),
                "secret_key": selected_secret_key,
                "secret_value": secret_value,
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

    @staticmethod
    def _artifact_display_path(path: str) -> str:
        raw = str(path or "").strip()
        if not raw:
            return ""
        target = Path(raw)
        try:
            return str(target.resolve().relative_to(_ROOT)).replace("\\", "/")
        except Exception:
            return raw.replace("\\", "/")

    @classmethod
    def _windows_handoff_line(
        cls,
        artifacts: list[dict[str, object]] | None,
        *,
        receipt_path: str = "",
        summary_path: str = "",
    ) -> str:
        rendered: list[str] = []
        receipt = cls._artifact_display_path(receipt_path)
        if receipt:
            rendered.append(f"receipt={receipt}")
        summary = cls._artifact_display_path(summary_path)
        if summary:
            rendered.append(f"summary={summary}")
        for item in artifacts or []:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", "") or item.get("id", "") or "artifact").strip()
            path = cls._artifact_display_path(str(item.get("path", "") or ""))
            if not path:
                continue
            rendered.append(f"{label}={path}")
        if not rendered:
            return "Files to share: run VERIFY, UPDATE, PACKAGE, or RELEASE DRY RUN to create reports and handoff files."
        return "Files to share: " + " | ".join(rendered[:4])

    def _build_windows_ops_snapshot(self) -> dict[str, str]:
        runtime_dir = _ROOT / "runtime"
        config_dir = _ROOT / "config"
        settings_path = runtime_dir / "app_settings.json"
        launcher_events = runtime_dir / "launcher_events.jsonl"
        state_path = runtime_dir / "windows_ops_state.json"
        venv_python = _ROOT / ".venv" / "Scripts" / "python.exe"
        supervisor_script = _ROOT / "bin" / "launch_api_supervised.bat"
        build_script = _ROOT / "bin" / "build_executable.bat"
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
        state_payload: dict[str, object] = {}
        if state_path.exists():
            try:
                parsed = json.loads(state_path.read_text(encoding="utf-8"))
                state_payload = parsed if isinstance(parsed, dict) else {}
            except Exception:
                state_payload = {}
        last_action = str(state_payload.get("action", "") or "").strip()
        last_timestamp = str(state_payload.get("timestamp", "") or "").strip()
        last_summary = str(state_payload.get("summary", "") or "").strip()
        last_changes = str(state_payload.get("changes", "") or "").strip()
        last_phase = str(state_payload.get("phase", "") or "").strip().lower()
        last_event_id = str(state_payload.get("event_id", "") or "").strip()
        next_step = str(state_payload.get("next_step", "") or "").strip()
        fix_target = str(state_payload.get("fix_target", "") or "").strip()
        docs_hint = str(state_payload.get("docs_hint", "") or "").strip()
        entry_point = str(state_payload.get("entry_point", "") or "").strip()
        steps_completed = state_payload.get("steps_completed")
        steps_total = state_payload.get("steps_total")
        ok = bool(state_payload.get("ok", False))
        artifacts = [item for item in state_payload.get("artifacts", []) if isinstance(item, dict)] if isinstance(state_payload.get("artifacts"), list) else []
        receipt_path = str(state_payload.get("release_receipt", "") or "").strip()
        summary_path = str(state_payload.get("release_summary", "") or "").strip()
        gate_summary = str(state_payload.get("gate_summary", "") or "").strip()
        gate_detail = str(state_payload.get("gate_detail", "") or "").strip()
        gate_recommendations = [str(item).strip() for item in state_payload.get("gate_recommendations", []) if str(item).strip()] if isinstance(state_payload.get("gate_recommendations"), list) else []
        gate_recommendation_details = [item for item in state_payload.get("gate_recommendation_details", []) if isinstance(item, dict)] if isinstance(state_payload.get("gate_recommendation_details"), list) else []
        primary_gate_fix = gate_recommendation_details[0] if gate_recommendation_details else {}
        step_text = (
            f" | Steps: {int(steps_completed or 0)}/{int(steps_total or 0)}"
            if steps_completed is not None and steps_total is not None
            else ""
        )
        phase_text = f" | Phase: {last_phase}" if last_phase else ""
        ref_text = f" | Ref: {last_event_id}" if last_event_id else ""
        return {
            "install": "Installed on this PC: " + " | ".join(install_bits),
            "runtime": f"Local AI runtime: {self._configured_local_runtime_backend()} | Live backend: waiting for first status poll",
            "paths": f"Data locations: runtime={runtime_dir} | config={config_dir} | settings={settings_path}",
            "repair": f"Repair help: {repair_hint} | API relaunch: {supervisor_script}",
            "update": (
                "Update steps: python -m pip install -r requirements.txt | "
                "optional extras: python -m pip install -r requirements-optional.txt | "
                "postflight: python tools/validate_build_checks.py + python tools/verify_ollama_runtime.py --prompt ok | "
                "daily launcher: python src/guppy/cli/launch.py launcher"
            ),
            "diagnostics": (
                f"Diagnostics: launcher log={launcher_events} | latest bundle={latest_bundle_text} | "
                "runtime check: python tools/verify_ollama_runtime.py --prompt ok"
            ),
            "entry": (
                "Useful entry points: launcher=python src/guppy/cli/launch.py launcher | "
                "package=bin/build_executable.bat --no-clean | "
                f"supervisor={supervisor_script}"
            ),
            "next": (
                "Recommended next step: "
                + (
                    next_step
                    + (f" | Fix in: {fix_target}" if fix_target else "")
                    + (f" | Doc: {docs_hint}" if docs_hint else "")
                    + (f" | Command: {entry_point}" if entry_point else "")
                )
                if next_step
                else "Recommended next step: choose VERIFY, UPDATE, PACKAGE, RELEASE DRY RUN, SUPERVISED API, RESTART, or REPAIR."
            ),
            "service": (
                f"Recent service action: {last_action} @ {last_timestamp} | {'OK' if ok else 'CHECK'} | {last_summary}{phase_text}{step_text}{ref_text}"
                if last_action
                else "Recent service action: none recorded yet"
            ),
            "changes": f"Recent changes: {last_changes or 'No service summary recorded yet.'}",
            "gate": "Release check: " + (
                gate_summary + (f" | {gate_detail}" if gate_detail else "")
                if gate_summary
                else "no dry-run result recorded yet."
            ),
            "gate_fix": "Fix first: " + (
                (
                    str(primary_gate_fix.get("text", "") or "").strip()
                    + (f" | Fix in: {str(primary_gate_fix.get('fix_target', '') or '').strip()}" if str(primary_gate_fix.get("fix_target", "") or "").strip() else "")
                    + (f" | Doc: {str(primary_gate_fix.get('docs_hint', '') or '').strip()}" if str(primary_gate_fix.get("docs_hint", "") or "").strip() else "")
                    + (f" | Cmd: {str(primary_gate_fix.get('entry_point', '') or '').strip()}" if str(primary_gate_fix.get("entry_point", "") or "").strip() else "")
                )
                if primary_gate_fix
                else " | ".join(gate_recommendations[:2])
                if gate_recommendations
                else "no release-check recommendations recorded yet."
            ),
            "handoff": self._windows_handoff_line(artifacts, receipt_path=receipt_path, summary_path=summary_path),
        }

    def _refresh_windows_ops_labels(self) -> None:
        install_raw = str(self._windows_ops.get("install", "") or "")
        runtime_raw = str(self._windows_ops.get("runtime", "") or "")
        next_raw = str(self._windows_ops.get("next", "") or "")
        service_raw = str(self._windows_ops.get("service", "") or "")
        change_raw = str(self._windows_ops.get("changes", "") or "")
        gate_raw = str(self._windows_ops.get("gate", "") or "")
        gate_fix_raw = str(self._windows_ops.get("gate_fix", "") or "")
        handoff_raw = str(self._windows_ops.get("handoff", "") or "")
        install_bits = []
        if "Ollama CLI: found" in install_raw:
            install_bits.append("Ollama")
        if "Lemonade CLI: found" in install_raw:
            install_bits.append("Lemonade")
        if "Supervisor script: ready" in install_raw:
            install_bits.append("supervised launch")
        if "Packager: ready" in install_raw:
            install_bits.append("desktop packaging")
        runtime_fields = _pipe_fields(runtime_raw)
        configured = runtime_fields.get("local ai runtime", "local ai")
        live_backend = runtime_fields.get("live backend", configured)
        state = runtime_fields.get("status", "unknown").lower()

        self._windows_install_lbl.setText(
            "Installed on this PC: " + (", ".join(install_bits) if install_bits else "Core launcher tools found.")
        )
        if state == "ready":
            self._windows_runtime_lbl.setText(f"Local AI runtime: {live_backend.title()} is connected and ready.")
        elif state == "unknown":
            self._windows_runtime_lbl.setText(f"Local AI runtime: {configured.title()} is selected, but it has not been confirmed yet.")
        else:
            self._windows_runtime_lbl.setText(f"Local AI runtime: {configured.title()} needs attention.")
        self._windows_paths_lbl.setText("Data locations: runtime, config, and settings are available on this PC.")
        self._windows_repair_lbl.setText("Repair help: Use Repair if sign-in, startup, or local runtime checks fail.")
        self._windows_update_lbl.setText("Update path: Update refreshes dependencies, then runs the built-in post-update checks.")
        self._windows_diagnostics_lbl.setText("Diagnostics: launcher logs and the latest diagnostic bundle are available for troubleshooting.")
        self._windows_entry_lbl.setText("Useful actions: Package makes a shareable desktop build, and Supervised API restarts the background service safely.")
        self._windows_next_lbl.setText(next_raw or "Recommended next step: unavailable")
        self._windows_service_lbl.setText(service_raw or "Recent service action: unavailable")
        self._windows_change_lbl.setText(change_raw or "Recent changes: unavailable")
        self._windows_gate_lbl.setText(gate_raw or "Release check: unavailable")
        self._windows_gate_fix_lbl.setText(gate_fix_raw or "Fix first: unavailable")
        self._windows_handoff_lbl.setText(handoff_raw or "Files to share: unavailable")

    def refresh_windows_ops_snapshot(self) -> None:
        runtime_line = self._windows_ops.get("runtime", "")
        self._windows_ops = self._build_windows_ops_snapshot()
        if runtime_line:
            self._windows_ops["runtime"] = runtime_line
        self._refresh_windows_ops_labels()

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
    ) -> None:
        self._windows_ops["service"] = (
            f"Recent service action: {action} | {'OK' if ok else 'CHECK'} | {summary}"
        )
        self._windows_ops["changes"] = f"Recent changes: {changes}"
        self._windows_ops["gate"] = "Release check: " + (
            str(gate_summary or "").strip() + (f" | {str(gate_detail or '').strip()}" if str(gate_detail or "").strip() else "")
            if str(gate_summary or "").strip()
            else "no dry-run result recorded yet."
        )
        rendered_recommendations = [str(item).strip() for item in (gate_recommendations or []) if str(item).strip()]
        rendered_recommendation_details = [item for item in (gate_recommendation_details or []) if isinstance(item, dict)] 
        primary_gate_fix = rendered_recommendation_details[0] if rendered_recommendation_details else {}
        self._windows_ops["gate_fix"] = "Fix first: " + (
            (
                str(primary_gate_fix.get("text", "") or "").strip()
                + (f" | Fix in: {str(primary_gate_fix.get('fix_target', '') or '').strip()}" if str(primary_gate_fix.get("fix_target", "") or "").strip() else "")
                + (f" | Doc: {str(primary_gate_fix.get('docs_hint', '') or '').strip()}" if str(primary_gate_fix.get("docs_hint", "") or "").strip() else "")
                + (f" | Cmd: {str(primary_gate_fix.get('entry_point', '') or '').strip()}" if str(primary_gate_fix.get("entry_point", "") or "").strip() else "")
            )
            if primary_gate_fix
            else " | ".join(rendered_recommendations[:2])
            if rendered_recommendations
            else "no release-check recommendations recorded yet."
        )
        self._windows_ops["handoff"] = self._windows_handoff_line(artifacts, receipt_path=receipt_path, summary_path=summary_path)
        if next_step:
            self._windows_ops["next"] = (
                "Recommended next step: "
                + next_step
                + (f" | Fix in: {fix_target}" if fix_target else "")
                + (f" | Doc: {docs_hint}" if docs_hint else "")
                + (f" | Command: {entry_point}" if entry_point else "")
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
        if not self._details_visible:
            self._details_visible = True
            self._sync_detail_visibility()
        self._terminal_focus_pending = True
        if note:
            self._append_terminal_output(note)
        self._terminal_input.setFocus()

    def queue_terminal_recipe(
        self,
        commands: list[str],
        *,
        label: str,
        recipe_context: dict[str, object] | None = None,
    ) -> bool:
        return self._run_terminal_commands(commands, label=label, recipe_context=recipe_context)

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

    @staticmethod
    def _recipe_marker(*parts: object) -> str:
        cleaned = [str(part).replace("|", "/").strip() for part in parts]
        return _TERMINAL_RECIPE_MARKER + "|".join(cleaned)

    def _build_tracked_recipe_commands(
        self,
        commands: list[str],
        *,
        label: str,
        recipe_context: dict[str, object],
    ) -> tuple[str, list[str]]:
        recipe_id = f"recipe-{uuid4().hex[:10]}"
        cleaned = [str(item).strip() for item in commands if str(item).strip()]
        context = dict(recipe_context)
        context.update(
            {
                "id": recipe_id,
                "label": label,
                "commands": cleaned,
                "steps_total": len(cleaned),
                "steps_completed": 0,
                "step_results": [],
            }
        )
        self._terminal_recipes[recipe_id] = context
        wrapped: list[str] = [
            f'Write-Output "{self._recipe_marker("start", recipe_id, len(cleaned), label)}"',
            "$global:GuppyRecipeStop = 0",
        ]
        for idx, command in enumerate(cleaned, start=1):
            escaped = command.replace("'", "''")
            wrapped.append(
                "if ($global:GuppyRecipeStop -ne 0) "
                "{ "
                f'Write-Output "{self._recipe_marker("step", recipe_id, idx, "skipped")}"'
                " } else { "
                f"Invoke-Expression '{escaped}'; "
                "$code = if ($LASTEXITCODE -ne $null) { [int]$LASTEXITCODE } elseif ($?) { 0 } else { 1 }; "
                f'Write-Output "{self._recipe_marker("step", recipe_id, idx)}|$code"; '
                "if ($code -ne 0) { $global:GuppyRecipeStop = $code }"
                " }"
            )
        wrapped.append(f'Write-Output "{self._recipe_marker("end", recipe_id)}|$global:GuppyRecipeStop"')
        wrapped.append("Remove-Variable GuppyRecipeStop -Scope Global -ErrorAction SilentlyContinue")
        return recipe_id, wrapped

    def _handle_terminal_recipe_marker(self, line: str) -> bool:
        if not str(line).startswith(_TERMINAL_RECIPE_MARKER):
            return False
        payload = str(line)[len(_TERMINAL_RECIPE_MARKER):]
        parts = payload.split("|")
        if len(parts) < 2:
            return True
        marker_type = str(parts[0]).strip().lower()
        recipe_id = str(parts[1]).strip()
        recipe = self._terminal_recipes.get(recipe_id, {})
        if marker_type == "start":
            label = str(recipe.get("label", parts[3] if len(parts) > 3 else "recipe") or "recipe")
            steps_total = int(parts[2]) if len(parts) > 2 and str(parts[2]).isdigit() else int(recipe.get("steps_total", 0) or 0)
            recipe["steps_total"] = steps_total
            recipe["steps_completed"] = 0
            self._terminal_recipes[recipe_id] = recipe
            self._terminal_status_lbl.setText(f"Shell running {label.lower()}")
            return True
        if marker_type == "step":
            idx = int(parts[2]) if len(parts) > 2 and str(parts[2]).isdigit() else 0
            result = str(parts[3]).strip().lower() if len(parts) > 3 else ""
            code = 0 if result == "skipped" else int(parts[4]) if len(parts) > 4 and str(parts[4]).lstrip("-").isdigit() else int(parts[3]) if len(parts) > 3 and str(parts[3]).lstrip("-").isdigit() else 0
            step_results = recipe.get("step_results", [])
            if not isinstance(step_results, list):
                step_results = []
            command_list = recipe.get("commands", [])
            command_text = str(command_list[idx - 1]) if isinstance(command_list, list) and 0 < idx <= len(command_list) else ""
            step_results.append(
                {
                    "index": idx,
                    "exit_code": code,
                    "ok": result != "skipped" and code == 0,
                    "skipped": result == "skipped",
                    "command": command_text,
                }
            )
            recipe["step_results"] = step_results
            recipe["steps_completed"] = len(step_results)
            self._terminal_recipes[recipe_id] = recipe
            return True
        if marker_type == "end":
            final_code = int(parts[2]) if len(parts) > 2 and str(parts[2]).lstrip("-").isdigit() else 0
            step_results = recipe.get("step_results", [])
            if not isinstance(step_results, list):
                step_results = []
            total = int(recipe.get("steps_total", len(step_results)) or len(step_results))
            completed = len([item for item in step_results if isinstance(item, dict) and not bool(item.get("skipped", False))])
            failed_steps = [
                item for item in step_results
                if isinstance(item, dict) and not bool(item.get("ok", False)) and not bool(item.get("skipped", False))
            ]
            ok = final_code == 0 and not failed_steps and completed == total
            label = str(recipe.get("label", "recipe") or "recipe")
            summary = (
                f"{label} completed {completed}/{total} step(s) successfully."
                if ok
                else f"{label} stopped after {completed}/{total} successful step(s)."
            )
            if failed_steps:
                failed = failed_steps[0]
                summary += f" Failed step {int(failed.get('index', 0) or 0)}: {str(failed.get('command', '') or '').strip()}"
            payload_out = {
                **recipe,
                "id": recipe_id,
                "ok": ok,
                "final_exit_code": final_code,
                "summary": summary,
                "steps_completed": completed,
                "steps_total": total,
                "failed_steps": failed_steps,
            }
            if self._terminal_process is not None and self._terminal_process.poll() is None:
                self._terminal_status_lbl.setText(f"Shell ready [pid={self._terminal_process.pid}]")
            else:
                self._terminal_status_lbl.setText("Shell idle")
            self._terminal_recipes.pop(recipe_id, None)
            self.terminal_recipe_finished.emit(payload_out)
            return True
        return True

    def _run_terminal_commands(
        self,
        commands: list[str],
        *,
        label: str,
        recipe_context: dict[str, object] | None = None,
    ) -> bool:
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
        rendered_commands = cleaned
        if isinstance(recipe_context, dict):
            _recipe_id, rendered_commands = self._build_tracked_recipe_commands(cleaned, label=label, recipe_context=recipe_context)
        self._append_terminal_output(f"[workflow] running {label} ({len(cleaned)} commands)")
        try:
            for idx, command in enumerate(cleaned, start=1):
                self._append_terminal_output(f"> [{idx}/{len(cleaned)}] {command}")
            for command in rendered_commands:
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
                if self._handle_terminal_recipe_marker(line):
                    drained += 1
                    continue
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
            elif event == "connector_action_result":
                connector = str(item.get("connector", "") or "").strip() or "connector"
                action = str(item.get("action", "") or "").strip() or "action"
                result = "OK" if bool(item.get("ok", False)) else "FAIL"
                ref = str(item.get("event_id", "") or "").strip()
                provider = str(item.get("provider", "") or "").strip()
                account_id = str(item.get("account_id", "") or "").strip()
                summary = str(item.get("summary", "") or "").strip()
                result_code = str(item.get("result_code", "") or "").strip()
                next_step = str(item.get("next_step", "") or "").strip()
                bits = [f"{connector}.{action}", result]
                if ref:
                    bits.append(f"ref={ref}")
                if result_code:
                    bits.append(f"code={result_code}")
                if provider:
                    bits.append(f"provider={provider}")
                if account_id:
                    bits.append(f"account={account_id}")
                detail = " | ".join(bits)
                if summary:
                    detail += f" | {summary}"
                if next_step:
                    detail += f" | next={next_step}"
            elif event in {"windows_ops_action", "windows_ops_completed"}:
                action = str(item.get("action", "") or "").strip() or "windows_ops"
                queued = item.get("queued")
                ok = item.get("ok")
                steps_completed = str(item.get("steps_completed", "") or "").strip()
                steps_total = str(item.get("steps_total", "") or "").strip()
                summary = str(item.get("summary", "") or "").strip()
                event_id = str(item.get("event_id", "") or "").strip()
                next_step = str(item.get("next_step", "") or "").strip()
                fix_target = str(item.get("fix_target", "") or "").strip()
                gate_summary = str(item.get("gate_summary", "") or "").strip()
                gate_detail = str(item.get("gate_detail", "") or "").strip()
                gate_failed_checks = [str(row).strip() for row in item.get("gate_failed_checks", []) if str(row).strip()] if isinstance(item.get("gate_failed_checks"), list) else []
                gate_missing_files = [str(row).strip() for row in item.get("gate_missing_files", []) if str(row).strip()] if isinstance(item.get("gate_missing_files"), list) else []
                gate_passed_checks = str(item.get("gate_passed_checks", "") or "").strip()
                gate_total_checks = str(item.get("gate_total_checks", "") or "").strip()
                gate_recommendations = [str(row).strip() for row in item.get("gate_recommendations", []) if str(row).strip()] if isinstance(item.get("gate_recommendations"), list) else []
                gate_recommendation_details = [row for row in item.get("gate_recommendation_details", []) if isinstance(row, dict)] if isinstance(item.get("gate_recommendation_details"), list) else []
                bits = [action]
                if queued is not None:
                    bits.append("QUEUED" if bool(queued) else "QUEUE_FAIL")
                if ok is not None:
                    bits.append("OK" if bool(ok) else "FAIL")
                if steps_completed and steps_total:
                    bits.append(f"steps={steps_completed}/{steps_total}")
                if event_id:
                    bits.append(f"ref={event_id}")
                if fix_target:
                    bits.append(f"fix={fix_target}")
                receipt_path = self._artifact_display_path(str(item.get("release_receipt", "") or ""))
                summary_path = self._artifact_display_path(str(item.get("release_summary", "") or ""))
                artifacts = [row for row in item.get("artifacts", []) if isinstance(row, dict)] if isinstance(item.get("artifacts"), list) else []
                artifact_refs = []
                for artifact in artifacts[:3]:
                    label = str(artifact.get("id", "") or artifact.get("label", "") or "artifact").strip()
                    path = self._artifact_display_path(str(artifact.get("path", "") or ""))
                    if label and path:
                        artifact_refs.append(f"{label}={path}")
                detail = " | ".join(bits)
                if summary:
                    detail += f" | {summary}"
                if next_step:
                    detail += f" | next={next_step}"
                if gate_summary:
                    detail += f" | gate={gate_summary}"
                    if gate_detail:
                        detail += f" | gate_detail={gate_detail}"
                    if gate_passed_checks and gate_total_checks:
                        detail += f" | gate_checks={gate_passed_checks}/{gate_total_checks}"
                    if gate_failed_checks:
                        detail += f" | gate_failed={','.join(gate_failed_checks[:3])}"
                    if gate_missing_files:
                        rendered_missing = ",".join(Path(path).name or path for path in gate_missing_files[:3])
                        detail += f" | gate_missing={rendered_missing}"
                    if gate_recommendations:
                        detail += f" | gate_fix={'; '.join(gate_recommendations[:2])}"
                    if gate_recommendation_details:
                        first_fix = gate_recommendation_details[0]
                        fix_target = str(first_fix.get("fix_target", "") or "").strip()
                        fix_docs = str(first_fix.get("docs_hint", "") or "").strip()
                        fix_command = str(first_fix.get("entry_point", "") or "").strip()
                        if fix_target:
                            detail += f" | gate_fix_target={fix_target}"
                        if fix_docs:
                            detail += f" | gate_fix_doc={fix_docs}"
                        if fix_command:
                            detail += f" | gate_fix_cmd={fix_command}"
                if receipt_path:
                    detail += f" | receipt={receipt_path}"
                if summary_path:
                    detail += f" | summary={summary_path}"
                if artifact_refs:
                    detail += f" | handoff={', '.join(artifact_refs)}"
            lines.append(f"[{level}] {ts} {event}" + (f" :: {detail}" if detail else ""))
        self._syslog.setPlainText(
            "\n".join(lines[-50:])
            if lines
            else "No operator log entries matched the current filter yet. Recovery runs, workflow actions, and launcher warnings will appear here."
        )
