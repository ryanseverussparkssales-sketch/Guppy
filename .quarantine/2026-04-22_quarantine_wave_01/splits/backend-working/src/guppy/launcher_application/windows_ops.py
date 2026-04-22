"""Typed planning helpers for launcher-driven Windows operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .workflows import get_workflow_spec


_WINDOWS_OPS_WORKFLOW_MAP = {
    "verify_runtime": "windows_verify_runtime",
    "update_runtime": "windows_update_runtime",
    "package_desktop": "windows_package_desktop",
    "release_dry_run": "windows_release_dry_run",
}


class WindowsOpsExecutionKind(StrEnum):
    """How the launcher executes a Windows operation."""

    TERMINAL_RECIPE = "terminal_recipe"
    SUBPROCESS = "subprocess"
    RECOVERY_CHAIN = "recovery_chain"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class WindowsOpsChainStep:
    """A queued recovery step and its delay from the request start."""

    name: str
    delay_ms: int = 0


@dataclass(frozen=True, slots=True)
class WindowsOpsPlan:
    """Pure planning metadata for a launcher Windows operation."""

    action: str
    label: str = ""
    execution_kind: WindowsOpsExecutionKind = WindowsOpsExecutionKind.UNSUPPORTED
    commands: tuple[str, ...] = ()
    changes: str = ""
    docs_hint: str = ""
    next_step: str = ""
    review_order: tuple[str, ...] = ()
    request_summary: str = ""
    syslog_message: str = ""
    workflow_id: str = ""
    chain_steps: tuple[WindowsOpsChainStep, ...] = field(default_factory=tuple)

    @property
    def is_queueable(self) -> bool:
        return self.execution_kind == WindowsOpsExecutionKind.TERMINAL_RECIPE

    @property
    def is_immediate(self) -> bool:
        return self.execution_kind in {
            WindowsOpsExecutionKind.SUBPROCESS,
            WindowsOpsExecutionKind.RECOVERY_CHAIN,
        }

    def to_payload(self) -> dict[str, object]:
        return {
            "label": self.label,
            "commands": list(self.commands),
            "changes": self.changes,
            "docs_hint": self.docs_hint,
            "next_step": self.next_step,
            "review_order": list(self.review_order),
            "execution_kind": self.execution_kind.value,
            "queueable": self.is_queueable,
            "immediate": self.is_immediate,
            "request_summary": self.request_summary,
            "syslog_message": self.syslog_message,
            "workflow_id": self.workflow_id,
            "chain_steps": [
                {"name": step.name, "delay_ms": step.delay_ms}
                for step in self.chain_steps
            ],
        }


def build_windows_ops_descriptor(action: str) -> WindowsOpsPlan:
    """Resolve an action into a typed Windows-ops plan."""

    target = str(action or "").strip().lower()
    workflow_id = _WINDOWS_OPS_WORKFLOW_MAP.get(target, "")
    spec = get_workflow_spec(workflow_id) if workflow_id else None
    if spec is not None:
        return WindowsOpsPlan(
            action=target,
            label=spec.title,
            execution_kind=WindowsOpsExecutionKind.TERMINAL_RECIPE,
            commands=tuple(
                item.command for item in spec.commands if str(item.command).strip()
            ),
            changes=spec.summary,
            docs_hint=spec.docs_hint,
            next_step=spec.next_step,
            review_order=tuple(spec.review_order),
            request_summary=f"{spec.title.title()} queued in App Mgmt terminal",
            syslog_message=f"{spec.title.lower()} queued",
            workflow_id=workflow_id,
        )
    if target == "start_supervised_api":
        return WindowsOpsPlan(
            action=target,
            label="START API",
            execution_kind=WindowsOpsExecutionKind.SUBPROCESS,
            changes=(
                "Launches the supervised API batch entry point and checks API "
                "reachability from the launcher."
            ),
            docs_hint="docs/PACKAGING.md",
            next_step=(
                "Confirm API reachability in App Mgmt and then run a launcher-driven "
                "verify pass."
            ),
            request_summary="Supervised API launch requested from App Mgmt",
            syslog_message="supervised api requested",
        )
    if target == "restart_runtime":
        return WindowsOpsPlan(
            action=target,
            label="WINDOWS RESTART",
            execution_kind=WindowsOpsExecutionKind.RECOVERY_CHAIN,
            changes="Restarts the daemon, then re-runs warmup and runtime audit checks automatically.",
            docs_hint="docs/TROUBLESHOOTING.md",
            next_step=(
                "Wait for warmup and audit follow-up events, then review runtime "
                "health in App Mgmt."
            ),
            request_summary="Windows restart queued: restart daemon -> warmup -> audit",
            syslog_message="windows restart requested",
            chain_steps=(
                WindowsOpsChainStep("restart_daemon", 0),
                WindowsOpsChainStep("warmup", 650),
                WindowsOpsChainStep("audit_runtime", 1400),
            ),
        )
    if target == "repair_runtime":
        return WindowsOpsPlan(
            action=target,
            label="WINDOWS REPAIR",
            execution_kind=WindowsOpsExecutionKind.RECOVERY_CHAIN,
            changes="Captures a health snapshot, refreshes startup state, and re-runs the runtime audit automatically.",
            docs_hint="docs/TROUBLESHOOTING.md",
            next_step=(
                "Review the repair outcome, then verify runtime readiness if the "
                "lane still looks stale."
            ),
            request_summary="Windows repair queued: snapshot -> warmup -> audit",
            syslog_message="windows repair requested",
            chain_steps=(
                WindowsOpsChainStep("health_snapshot", 0),
                WindowsOpsChainStep("warmup", 250),
                WindowsOpsChainStep("audit_runtime", 1000),
            ),
        )
    return WindowsOpsPlan(action=target)


def build_windows_ops_plan_payload(action: str) -> dict[str, object]:
    """Backward-compatible dict view used by current launcher callers."""

    return build_windows_ops_descriptor(action).to_payload()
