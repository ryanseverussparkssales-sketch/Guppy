from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.guppy.launcher_application.automation_test_support import event_level
from src.guppy.launcher_application.storage_io import read_jsonl_tail


@dataclass(frozen=True)
class OperatorLogsFocusPlan:
    level: str
    note: str = ""


@dataclass(frozen=True)
class TerminalFocusPlan:
    note: str = ""


@dataclass(frozen=True)
class QuickActionPlan:
    action: str
    toggle_sidebar: bool = False
    toggle_drawer: bool = False
    tab_index: int | None = None
    daily_activity: str = ""
    syslog: str = ""
    launcher_event: dict[str, object] | None = None
    operator_logs_focus: OperatorLogsFocusPlan | None = None
    terminal_focus: TerminalFocusPlan | None = None
    unsupported_message: str = ""


@dataclass(frozen=True)
class NotificationBadgeState:
    count: int
    severity: str
    mtime: float
    changed: bool


def build_quick_action_plan(
    *,
    action: str,
    workspaces_view_index: int,
    settings_ops_index: int,
    runtime_parent: Path,
    last_command: str = "",
) -> QuickActionPlan:
    target = (action or "").strip().lower()
    if target == "toggle_sidebar":
        return QuickActionPlan(action=target, toggle_sidebar=True)
    if target == "toggle_drawer":
        return QuickActionPlan(action=target, toggle_drawer=True)
    if target == "workspaces":
        return QuickActionPlan(
            action=target,
            tab_index=workspaces_view_index,
            daily_activity="Workspace manager opened from the Home context controls",
            syslog="workspace manager opened from top bar",
            launcher_event={"action": "workspaces"},
        )
    if target == "notifications":
        return QuickActionPlan(
            action=target,
            tab_index=settings_ops_index,
            operator_logs_focus=OperatorLogsFocusPlan(
                level="WARN",
                note="Top bar notifications opened launcher warnings and recovery events.",
            ),
            daily_activity="Settings opened launcher warnings and recovery events",
            syslog="Settings warnings opened from top bar",
            launcher_event={"action": "notifications"},
        )
    if target == "terminal":
        note = "Top bar terminal opened operator logs"
        if last_command:
            note += f". Last command: {last_command}"
        return QuickActionPlan(
            action=target,
            tab_index=settings_ops_index,
            operator_logs_focus=OperatorLogsFocusPlan(level="ALL", note=note),
            terminal_focus=TerminalFocusPlan(
                note=f"[launcher] terminal opened from top bar. cwd={runtime_parent}"
            ),
            daily_activity="Settings opened operator logs and workflow controls",
            syslog="Settings terminal opened from top bar",
            launcher_event={"action": "terminal", "last_command": last_command},
        )
    return QuickActionPlan(action=target, unsupported_message=f"quick action unavailable: {action}")


def build_notification_badge_state(
    *,
    events_path: Path,
    previous_mtime: float,
    limit: int = 80,
) -> NotificationBadgeState:
    if not events_path.exists():
        return NotificationBadgeState(count=0, severity="info", mtime=0.0, changed=True)
    try:
        mtime = events_path.stat().st_mtime
    except Exception:
        mtime = 0.0
    if mtime == previous_mtime:
        return NotificationBadgeState(count=0, severity="info", mtime=mtime, changed=False)
    warn_count = 0
    error_count = 0
    for item in read_jsonl_tail(events_path, limit=limit):
        if not isinstance(item, dict):
            continue
        level = event_level(item)
        if level == "ERROR":
            error_count += 1
        elif level == "WARN":
            warn_count += 1
    severity = "error" if error_count else ("warn" if warn_count else "info")
    return NotificationBadgeState(
        count=error_count + warn_count,
        severity=severity,
        mtime=mtime,
        changed=True,
    )
