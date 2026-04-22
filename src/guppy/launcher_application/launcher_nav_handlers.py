"""src/guppy/launcher_application/launcher_nav_handlers.py

Navigation, tab-coordination, panel-visibility, shell-model-summary, and
quick-action handler functions extracted from LauncherWindow.

Each owner-bound function takes *owner* (a LauncherWindow instance) as its
first argument and delegates to UI attributes and other owner methods, keeping
the shell thin.
"""
from __future__ import annotations

import os
from pathlib import Path

from .launcher_command_flow import build_shell_model_loadout_summary
from .launcher_shell_support import (
    QuickActionPlan,
    build_notification_badge_state,
    build_quick_action_plan,
)
from .storage_io import read_json_dict

# ---------------------------------------------------------------------------
# View-index constants (canonical source; re-aliased in launcher_window.py)
# ---------------------------------------------------------------------------
HOME_VIEW_INDEX = 0
WORKSPACES_VIEW_INDEX = 1
LIBRARY_VIEW_INDEX = 2
TOOLS_VIEW_INDEX = 3
SETTINGS_VIEW_INDEX = 4
SETTINGS_OPS_INDEX = 4
SETTINGS_ALIAS_INDEX = 10
MODELS_VIEW_INDEX = 5
MODELS_LOCAL_ALIAS_INDEX = 6
MODELS_LIBRARY_ALIAS_INDEX = 7
MODELS_RUNTIME_ALIAS_INDEX = 8
MODELS_VOICE_ALIAS_INDEX = 9

_MODELS_ALIAS_INDICES: frozenset[int] = frozenset({
    MODELS_LOCAL_ALIAS_INDEX,
    MODELS_LIBRARY_ALIAS_INDEX,
    MODELS_RUNTIME_ALIAS_INDEX,
    MODELS_VOICE_ALIAS_INDEX,
})

START_DESTINATION_TO_TAB: dict[str, int] = {
    "home": HOME_VIEW_INDEX,
    "workspaces": WORKSPACES_VIEW_INDEX,
    "spaces": WORKSPACES_VIEW_INDEX,
    "library": LIBRARY_VIEW_INDEX,
    "tools": TOOLS_VIEW_INDEX,
    "appmgmt": SETTINGS_OPS_INDEX,
    "automation-test": SETTINGS_OPS_INDEX,
    "local-llm": MODELS_LOCAL_ALIAS_INDEX,
    "models": MODELS_LIBRARY_ALIAS_INDEX,
    "runtime": MODELS_RUNTIME_ALIAS_INDEX,
    "voice": MODELS_VOICE_ALIAS_INDEX,
}

# ---------------------------------------------------------------------------
# Pure helpers (no owner)
# ---------------------------------------------------------------------------

def resolve_stack_index(index: int) -> int:
    """Map a logical tab index to the real QStackedWidget page index."""
    if index <= SETTINGS_VIEW_INDEX:
        return index
    if index == SETTINGS_ALIAS_INDEX:
        return SETTINGS_VIEW_INDEX
    if index in _MODELS_ALIAS_INDICES:
        return MODELS_VIEW_INDEX
    return index


def visible_nav_index(index: int) -> int:
    """Map a logical tab index to the sidebar / top-bar highlight index."""
    if index == WORKSPACES_VIEW_INDEX:
        return HOME_VIEW_INDEX
    if index in {SETTINGS_VIEW_INDEX, SETTINGS_ALIAS_INDEX}:
        return SETTINGS_VIEW_INDEX
    if index in {MODELS_VIEW_INDEX} | _MODELS_ALIAS_INDICES:
        return MODELS_LIBRARY_ALIAS_INDEX
    return index


def build_quick_action_plan_for_owner(owner, action: str, *, runtime_parent: Path) -> QuickActionPlan:
    """Build a QuickActionPlan using the canonical nav index constants."""
    return build_quick_action_plan(
        action=action,
        workspaces_view_index=WORKSPACES_VIEW_INDEX,
        settings_ops_index=SETTINGS_OPS_INDEX,
        runtime_parent=runtime_parent,
        last_command=owner._last_command,
    )

# ---------------------------------------------------------------------------
# Owner-bound helpers
# ---------------------------------------------------------------------------

def set_status_panel_visible(owner, visible: bool) -> None:
    owner_setter = getattr(owner, "_set_status_panel_visible", None)
    if callable(owner_setter):
        owner_setter(visible)
        return
    owner._status_divider.setVisible(visible)
    owner._status_panel.setVisible(visible)
    owner._topbar.set_drawer_open(visible)


def toggle_status_panel(owner) -> None:
    if owner._stack.currentIndex() == HOME_VIEW_INDEX:
        owner._home_drawer_open = not owner._home_drawer_open
        set_status_panel_visible(owner, owner._home_drawer_open)
        return
    set_status_panel_visible(owner, not owner._status_panel.isVisible())


def toggle_sidebar(owner) -> None:
    collapsed = not owner._sidebar.is_collapsed()
    owner._sidebar.set_collapsed(collapsed)
    owner._topbar.set_sidebar_collapsed(collapsed)


def sync_shell_model_summary(owner, *, runtime_path: Path, active_model: str = "", runtime_backend: str = "") -> None:
    app_settings = read_json_dict(runtime_path / "app_settings.json")
    summary = owner._shell_model_loadout_summary(
        active_model=active_model,
        runtime_backend=runtime_backend,
        settings_payload=app_settings if isinstance(app_settings, dict) else {},
        environment=dict(os.environ),
    )
    owner._topbar.set_launcher_summary(summary)
    owner._sync_topbar_model_context(main_model=active_model)


def on_tab_change(owner, index: int, *, runtime_path: Path) -> None:
    stack_index = resolve_stack_index(index)
    nav_idx = visible_nav_index(index)
    owner._stack.setCurrentIndex(stack_index)
    owner._topbar.set_active_tab(nav_idx)
    owner._sidebar.set_active(nav_idx)
    if nav_idx == MODELS_LIBRARY_ALIAS_INDEX:
        sync_shell_model_summary(owner, runtime_path=runtime_path)
    if index in {SETTINGS_OPS_INDEX, SETTINGS_ALIAS_INDEX}:
        owner._sync_automation_test_state()
    if nav_idx == HOME_VIEW_INDEX and not owner._sidebar.is_collapsed():
        owner._sidebar.set_collapsed(True)
        owner._topbar.set_sidebar_collapsed(True)
    set_status_panel_visible(owner, stack_index != HOME_VIEW_INDEX or owner._home_drawer_open)


def apply_start_destination(owner) -> None:
    target = owner._start_destination
    if target not in START_DESTINATION_TO_TAB:
        return
    target_index = START_DESTINATION_TO_TAB[target]
    if target == "automation-test" and not hasattr(owner, "_stack"):
        target_index = 3
    owner._on_tab_change(target_index)
    if target == "automation-test":
        note = (
            "Test flow ready: use Settings & System to verify readiness, queue one safe check, review it, approve it, and run validation."
        )
        owner._settings_hub_view.focus_automation_test(note=note)
        owner._assistant_view.set_background_event(note)
        owner._set_daily_activity("Test flow opened Setup & Health / Settings & System")
        owner._status_panel.append_syslog("automation test start intent opened Settings & System")
    owner._log_launcher_event("start_destination_applied", destination=target)


def refresh_notification_badge(owner, *, events_path: Path) -> None:
    state = build_notification_badge_state(
        events_path=events_path,
        previous_mtime=owner._notification_badge_mtime,
    )
    if not state.changed:
        return
    owner._notification_badge_mtime = state.mtime
    owner._topbar.set_notification_badge(state.count, severity=state.severity)


def on_search(owner, query: str) -> None:
    if not query.strip():
        return
    owner._on_tab_change(HOME_VIEW_INDEX)
    owner._assistant_view.set_input_text(query)


def on_quick_action(owner, action: str) -> None:
    plan = owner._build_quick_action_plan(action)
    owner._apply_quick_action_plan(plan)
