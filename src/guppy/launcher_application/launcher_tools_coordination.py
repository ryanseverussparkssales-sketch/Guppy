"""Tool state persistence and tool-panel action handlers.

Extracted from LauncherWindow as part of TR54-B1 (Wave 5).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.guppy.launcher_application.storage_io import read_json_dict


def load_tool_states(owner: Any) -> None:
    """Restore persisted tool enable/disable states into the tools view.

    Extracted from LauncherWindow._load_tool_states.
    """
    path_fn = getattr(owner, "_tool_state_path", None)
    if not callable(path_fn):
        return
    path: Path = path_fn()
    refresh = getattr(owner, "_refresh_tools_debug_surface", None)
    if not path.exists():
        if callable(refresh):
            refresh()
        return
    tools_view = getattr(owner, "_tools_view", None)
    status_panel = getattr(owner, "_status_panel", None)
    try:
        states = read_json_dict(path)
        if isinstance(states, dict) and tools_view is not None:
            tools_view.set_states({k: bool(v) for k, v in states.items()})
            if status_panel is not None:
                status_panel.append_syslog("tools state restored")
            owner._log_launcher_event("tools_state_restored", count=len(states))
    except Exception as e:
        if status_panel is not None:
            status_panel.append_syslog(f"tools state restore failed: {e}")
        owner._log_launcher_event("tools_state_restore_error", error=str(e))
    if callable(refresh):
        refresh()


def on_tool_state_changed(owner: Any, tool_key: str, enabled: bool) -> None:
    """Persist tool enable/disable state and refresh the debug surface.

    Extracted from LauncherWindow._on_tool_state_changed.
    """
    tools_view = getattr(owner, "_tools_view", None)
    states = tools_view.get_states() if tools_view is not None else {}
    status_panel = getattr(owner, "_status_panel", None)
    path_fn = getattr(owner, "_tool_state_path", None)
    try:
        if callable(path_fn):
            path: Path = path_fn()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(states, indent=2), encoding="utf-8")
        if status_panel is not None:
            status_panel.append_syslog(f"tool {tool_key} -> {'ON' if enabled else 'OFF'}")
        owner._log_launcher_event("tool_state_changed", tool=tool_key, enabled=enabled)
    except Exception as e:
        if status_panel is not None:
            status_panel.append_syslog(f"tool state save failed: {e}")
        owner._log_launcher_event("tool_state_save_error", tool=tool_key, enabled=enabled, error=str(e))
    refresh = getattr(owner, "_refresh_tools_debug_surface", None)
    if callable(refresh):
        refresh()


def on_tool_hint_requested(
    owner: Any,
    tool_key: str,
    *,
    settings_view_index: int,
    tool_prompt_fn: Any,
) -> None:
    """Handle a tool hint request: prime the Home input or surface a block message.

    Extracted from LauncherWindow._on_tool_hint_requested.
    """
    key = (tool_key or "").strip()
    if not key:
        return
    tools_view = getattr(owner, "_tools_view", None)
    states = tools_view.current_tool_states() if tools_view is not None else {}
    assistant_view = getattr(owner, "_assistant_view", None)
    status_panel = getattr(owner, "_status_panel", None)
    set_act = getattr(owner, "_set_daily_activity", None)
    on_tab = getattr(owner, "_on_tab_change", None)
    refresh = getattr(owner, "_refresh_tools_debug_surface", None)
    active_instance = getattr(owner, "_active_instance_name", "") or ""

    if states.get(key) == "restricted":
        owner._log_launcher_event(
            "tool_hint_blocked",
            tool=key,
            instance=active_instance,
            status=states.get(key, "unknown"),
        )
        message = (
            f"{key.replace('_', ' ')} is blocked in {active_instance}. "
            "Switch workspaces or review permissions in Agent Tools before you try again."
        )
        if assistant_view is not None:
            assistant_view.add_system_message(message)
        if callable(set_act):
            set_act(f"Workspace tool blocked: {key}")
        if status_panel is not None:
            status_panel.append_syslog(f"workspace tool blocked: {key}")
        if callable(refresh):
            refresh()
        return

    if callable(on_tab):
        on_tab(0)
    if assistant_view is not None:
        assistant_view.set_input_text(tool_prompt_fn(key))
    if callable(set_act):
        set_act(f"Workspace tool loaded into Home: {key}")
    if status_panel is not None:
        status_panel.append_syslog(f"workspace tool primed: {key}")
    owner._log_launcher_event(
        "tool_hint_requested",
        tool=key,
        instance=active_instance,
        status=states.get(key, "unknown"),
    )
    if callable(refresh):
        refresh()


def on_tool_management_requested(
    owner: Any,
    payload: dict[str, object],
    *,
    settings_view_index: int,
) -> None:
    """Redirect a tool management action to Settings and focus the connector panel.

    Extracted from LauncherWindow._on_tool_management_requested.
    """
    if not isinstance(payload, dict):
        return
    connector_id = str(payload.get("connector", "") or "").strip().lower()
    provider = str(payload.get("provider", "") or "").strip().lower()
    account_id = str(payload.get("account_id", "") or "").strip().lower()
    tool_key = str(payload.get("tool", "") or "").strip().lower()
    note = str(payload.get("note", "") or "").strip()

    on_tab = getattr(owner, "_on_tab_change", None)
    if callable(on_tab):
        on_tab(settings_view_index)

    settings_hub = getattr(owner, "_settings_hub_view", None)
    if settings_hub is not None:
        focus = getattr(settings_hub, "focus_connectors", None)
        if callable(focus):
            focus(connector_id, provider=provider, account_id=account_id, note=note)

    summary = f"Settings owns connector setup for {tool_key or connector_id or 'this tool'}."
    assistant_view = getattr(owner, "_assistant_view", None)
    if assistant_view is not None:
        assistant_view.add_system_message(summary)
    set_act = getattr(owner, "_set_daily_activity", None)
    if callable(set_act):
        set_act(summary)
    status_panel = getattr(owner, "_status_panel", None)
    if status_panel is not None:
        status_panel.append_syslog(f"tool management redirect: {tool_key or connector_id or 'unknown'}")
    owner._log_launcher_event(
        "tool_management_redirected",
        tool=tool_key,
        connector=connector_id,
        provider=provider,
        account_id=account_id,
        target=str(payload.get("destination", "") or "settings_device_accounts"),
    )


def on_settings_saved(owner: Any, settings: dict) -> None:
    """React to a settings save: apply to assistant view, refresh persona state, update activity.

    Extracted from LauncherWindow._on_settings_saved as part of TR54-B1 Wave 9.
    """
    profile = settings.get("runtime_profile", "standard")
    persona_name = str(settings.get("active_persona_name", "")).strip()
    assistant_view = getattr(owner, "_assistant_view", None)
    if assistant_view is not None:
        assistant_view.apply_settings(settings)
    refresh = getattr(owner, "_refresh_personalization_state", None)
    if callable(refresh):
        refresh(preferred_persona=str(settings.get("active_persona_id", "")).strip())
    detail = f"Settings saved for {str(profile).upper()} profile"
    if persona_name:
        detail += f" \u00b7 persona {persona_name}"
    set_activity = getattr(owner, "_set_daily_activity", None)
    if callable(set_activity):
        set_activity(detail)
    status_panel = getattr(owner, "_status_panel", None)
    if status_panel is not None:
        status_panel.append_syslog(detail.lower())


def on_voice_bindings_changed(owner: Any) -> None:
    """React to a voice bindings update: refresh persona state and log activity.

    Extracted from LauncherWindow._on_voice_bindings_changed as part of TR54-B1 Wave 9.
    """
    refresh = getattr(owner, "_refresh_personalization_state", None)
    if callable(refresh):
        refresh()
    set_activity = getattr(owner, "_set_daily_activity", None)
    if callable(set_activity):
        set_activity("Voice bindings updated")
    status_panel = getattr(owner, "_status_panel", None)
    if status_panel is not None:
        status_panel.append_syslog("voice bindings updated")
