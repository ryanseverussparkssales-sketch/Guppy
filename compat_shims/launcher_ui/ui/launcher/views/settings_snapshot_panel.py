from __future__ import annotations

import sys
from pathlib import Path

from src.guppy.launcher_application.app_mgmt_presenter import (
    build_automation_snapshot_state,
    build_status_snapshot_state,
    build_windows_ops_snapshot as presenter_build_windows_ops_snapshot,
)
from src.guppy.launcher_application.windows_ops_presenter import build_windows_ops_panel_state

from .. import tokens as T


def apply_recovery_status(owner, text: str, *, root: Path) -> None:
    message = (text or "Nothing needs attention right now.").strip() or "Nothing needs attention right now."
    owner._recovery_status.setText(message)
    owner._last_recovery_lbl.setText(f"Last recovery action: {message}")
    owner._windows_ops = _rebuild_windows_ops_snapshot(owner, root=root)
    refresh_windows_ops_labels(owner)


def apply_status_snapshot(owner, payload: dict[str, object], *, root: Path) -> None:
    owner._windows_ops = _rebuild_windows_ops_snapshot(owner, root=root)
    state = build_status_snapshot_state(
        payload,
        configured_backend=owner._configured_local_runtime_backend(),
        previous_windows_runtime=owner._windows_ops.get("runtime", ""),
    )
    owner._health_lbl.setText(state.health_text)
    owner._voice_lbl.setText(state.voice_text)
    owner._route_health_lbl.setText(state.route_health_text)
    owner._resource_lbl.setText(state.resource_text)
    refresh_windows_ops_labels(owner)
    if state.windows_runtime_text:
        owner._windows_ops["runtime"] = state.windows_runtime_text
        refresh_windows_ops_labels(owner)


def apply_automation_snapshot(owner, payload: dict[str, object]) -> None:
    state = build_automation_snapshot_state(payload)
    owner._automation_workspace_lbl.setText(state.workspace_text)
    owner._automation_queue_lbl.setText(state.queue_text)
    owner._automation_staged_lbl.setText(state.staged_text)
    owner._automation_result_lbl.setText(state.result_text)
    owner._automation_approval_lbl.setText(state.approval_text)
    owner._automation_report_lbl.setText(state.report_text)
    owner._automation_evidence_lbl.setText(state.evidence_text)
    owner._automation_stress_lbl.setText(state.stress_text)
    owner._automation_recent_lbl.setText(state.recent_text)
    owner._automation_validation_lbl.setText(state.validation_text)
    if state.status_text:
        set_automation_status(owner, state.status_text)


def set_automation_status(owner, text: str, ok: bool = True) -> None:
    color = T.STATUS_SUCCESS if ok else T.STATUS_ERROR
    message = (text or "Automation test lane ready").strip() or "Automation test lane ready"
    owner._automation_status_lbl.setText(message)
    owner._automation_status_lbl.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
    )


def build_windows_ops_snapshot(owner, *, root: Path) -> dict[str, str]:
    return presenter_build_windows_ops_snapshot(
        root,
        configured_backend=owner._configured_local_runtime_backend(),
        launcher_python=sys.executable,
    )


def refresh_windows_ops_labels(owner) -> None:
    state = build_windows_ops_panel_state(owner._windows_ops)
    owner._windows_install_lbl.setText(state.install_text)
    owner._windows_runtime_lbl.setText(state.runtime_text)
    owner._windows_paths_lbl.setText(state.paths_text)
    owner._windows_repair_lbl.setText(state.repair_text)
    owner._windows_update_lbl.setText(state.update_text)
    owner._windows_diagnostics_lbl.setText(state.diagnostics_text)
    owner._windows_entry_lbl.setText(state.entry_text)
    owner._windows_next_lbl.setText(state.next_text)
    owner._windows_service_lbl.setText(state.service_text)
    owner._windows_change_lbl.setText(state.changes_text)
    owner._windows_gate_lbl.setText(state.gate_text)
    owner._windows_gate_fix_lbl.setText(state.gate_followup_text)
    owner._windows_handoff_lbl.setText(state.handoff_text)


def refresh_windows_ops_snapshot(owner, *, root: Path) -> None:
    owner._windows_ops = _rebuild_windows_ops_snapshot(owner, root=root)
    refresh_windows_ops_labels(owner)


def _rebuild_windows_ops_snapshot(owner, *, root: Path) -> dict[str, str]:
    runtime_line = owner._windows_ops.get("runtime", "")
    snapshot = build_windows_ops_snapshot(owner, root=root)
    if runtime_line:
        snapshot["runtime"] = runtime_line
    return snapshot
