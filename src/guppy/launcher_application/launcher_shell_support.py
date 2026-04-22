from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

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


@dataclass(frozen=True)
class RuntimeBadgeState:
    label: str
    severity: str
    detail: str


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


def build_runtime_badge_state(
    *,
    api_status: Mapping[str, object] | None,
    runtime_overall: str = "",
    startup_summary: str = "",
    startup_first_poll_ok: bool,
    startup_over_budget: bool,
) -> RuntimeBadgeState:
    summary = str(startup_summary or "").strip()
    payload = dict(api_status) if isinstance(api_status, Mapping) else {}
    status = str(payload.get("status", "") or "").strip().lower()
    runtime_state = str(runtime_overall or "").strip().upper()

    if not startup_first_poll_ok:
        return RuntimeBadgeState(
            label="STARTING",
            severity="info",
            detail=summary or "Launcher is still collecting startup readiness and runtime health.",
        )

    if startup_over_budget:
        return RuntimeBadgeState(
            label="STARTUP WARN",
            severity="warn",
            detail=(summary + " | " if summary else "") + "Startup took longer than the current launcher budget.",
        )

    if status == "healthy" or runtime_state == "READY":
        return RuntimeBadgeState(
            label="READY",
            severity="ok",
            detail=summary or "Launcher, startup checks, and the selected runtime look ready.",
        )

    if status == "degraded" or runtime_state == "PARTIAL":
        return RuntimeBadgeState(
            label="CHECK",
            severity="warn",
            detail=summary or "Some startup or runtime checks still need attention.",
        )

    if status or runtime_state:
        return RuntimeBadgeState(
            label="ATTN",
            severity="error",
            detail=summary or f"Runtime state needs attention: {status or runtime_state.lower()}",
        )

    return RuntimeBadgeState(
        label="OFFLINE",
        severity="error",
        detail=summary or "The launcher cannot read current runtime status yet.",
    )


def apply_quick_action_plan(owner: Any, plan: Any) -> bool:
    """Execute a resolved quick action plan against the launcher window.

    Extracted from LauncherWindow._apply_quick_action_plan as part of TR54-B1 Wave 7.
    """
    toggle_sidebar = getattr(owner, "_toggle_sidebar", None)
    toggle_status = getattr(owner, "_toggle_status_panel", None)
    on_tab = getattr(owner, "_on_tab_change", None)
    settings_hub = getattr(owner, "_settings_hub_view", None)
    set_act = getattr(owner, "_set_daily_activity", None)
    status_panel = getattr(owner, "_status_panel", None)

    if getattr(plan, "toggle_sidebar", False):
        if callable(toggle_sidebar):
            toggle_sidebar()
        return True
    if getattr(plan, "toggle_drawer", False):
        if callable(toggle_status):
            toggle_status()
        return True
    if getattr(plan, "tab_index", None) is not None:
        if callable(on_tab):
            on_tab(plan.tab_index)
    if getattr(plan, "operator_logs_focus", None) is not None and settings_hub is not None:
        focus = getattr(settings_hub, "focus_operator_logs", None)
        if callable(focus):
            focus(plan.operator_logs_focus.level, note=plan.operator_logs_focus.note)
    if getattr(plan, "terminal_focus", None) is not None and settings_hub is not None:
        focus_term = getattr(settings_hub, "focus_terminal", None)
        if callable(focus_term):
            focus_term(note=plan.terminal_focus.note)
    if getattr(plan, "daily_activity", "") and callable(set_act):
        set_act(plan.daily_activity)
    if getattr(plan, "syslog", "") and status_panel is not None:
        status_panel.append_syslog(plan.syslog)
    if isinstance(getattr(plan, "launcher_event", None), dict):
        owner._log_launcher_event("quick_action", **plan.launcher_event)
    if getattr(plan, "unsupported_message", "") and status_panel is not None:
        status_panel.append_syslog(plan.unsupported_message)
        return False
    return True


def on_home_starter_requested(owner: Any, starter_id: str, prompt: str) -> None:
    """Handle a home starter card activation: switch to Home tab, seed the route preview, log.

    Extracted from LauncherWindow._on_home_starter_requested as part of TR54-B1 Wave 9.
    """
    tab_change = getattr(owner, "_on_tab_change", None)
    if callable(tab_change):
        tab_change(0)
    update_preview = getattr(owner, "_update_route_preview", None)
    if callable(update_preview):
        update_preview(prompt)
    set_activity = getattr(owner, "_set_daily_activity", None)
    if callable(set_activity):
        set_activity(f"Starter loaded: {starter_id}")
    status_panel = getattr(owner, "_status_panel", None)
    if status_panel is not None:
        status_panel.append_syslog(f"home starter loaded: {starter_id}")
    owner._log_launcher_event("home_starter_loaded", starter_id=starter_id)
