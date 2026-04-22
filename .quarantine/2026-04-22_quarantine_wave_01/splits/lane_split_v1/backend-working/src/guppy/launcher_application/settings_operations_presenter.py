from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OperationsDensityState:
    header_scope_visible: bool
    details_button_text: str
    automation_summary_visible: bool
    workflow_evidence_visible: bool
    terminal_placeholder: str
    quick_fix_labels: dict[str, str]
    windows_action_labels: dict[str, str]
    automation_action_labels: dict[str, str]
    workflow_load_text: str
    workflow_run_text: str


def build_operations_density_state(width: int, details_visible: bool) -> OperationsDensityState:
    compact = width <= 1180
    tight = width <= 980
    if details_visible:
        details_button_text = "LESS ADVANCED" if not tight else "LESS"
    else:
        details_button_text = "ADVANCED" if not tight else "DETAILS"
    return OperationsDensityState(
        header_scope_visible=not tight,
        details_button_text=details_button_text,
        automation_summary_visible=not tight,
        workflow_evidence_visible=not tight,
        terminal_placeholder=(
            "Enter a PowerShell command"
            if tight
            else "Enter a PowerShell command to run inside the launcher terminal"
        ),
        quick_fix_labels={
            "health_snapshot": "SNAPSHOT",
            "warmup": "WARMUP",
            "restart_daemon": "RESTART" if compact else "RESTART DAEMON",
            "audit_runtime": "AUDIT" if compact else "AUDIT RUNTIME",
        },
        windows_action_labels={
            "release_dry_run": "DRY RUN" if compact else "RELEASE DRY RUN",
            "start_supervised_api": "START" if tight else "START API",
        },
        automation_action_labels={
            "verify_now": "VERIFY" if tight else "VERIFY NOW",
            "switch_builder_workspace": "BUILDER" if tight else "SWITCH TO BUILDER WORKSPACE",
            "queue_dry_run": "DRY RUN",
            "open_latest_report": "REFRESH" if tight else "REFRESH EVIDENCE PACK",
            "approve_latest_staged_task": "APPROVE" if tight else "APPROVE LATEST STAGED TASK",
            "run_validation": "VALIDATE" if tight else "RUN VALIDATION",
        },
        workflow_load_text="LOAD" if compact else "LOAD FIRST CMD",
        workflow_run_text="RUN" if compact else "RUN ALL",
    )
