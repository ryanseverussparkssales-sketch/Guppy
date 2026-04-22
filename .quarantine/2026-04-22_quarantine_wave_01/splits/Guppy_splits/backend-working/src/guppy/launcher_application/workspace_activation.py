from __future__ import annotations

from collections.abc import Callable
import time

from src.guppy.launcher_application.library_workflow import (
    apply_library_payload,
    sync_assistant_library_context,
)
from src.guppy.launcher_application.instance_manager_presenter import workspace_role_label
from src.guppy.launcher_application.workspace_state import resolve_active_instance_payload


def apply_instance_switch(owner, target: str, *, announce: bool = True) -> None:
    if not target:
        return
    if target == owner._active_instance_name and not announce:
        owner._assistant_view.set_active_instance(target)
        return
    owner._snapshot_active_instance_history()
    owner._active_instance_name = target
    owner._active_library_context_items = []
    history = owner._instance_histories.get(target)
    if history is None or not history:
        history = owner._load_instance_history_from_logs(target)
        owner._instance_histories[target] = history
    owner._assistant_view.restore_history(history)
    snapshot = owner._last_instance_snapshot if isinstance(owner._last_instance_snapshot, dict) else {}
    active_payload = resolve_active_instance_payload(snapshot, target)
    owner._assistant_view.set_active_instance(
        target,
        workspace_type=str(active_payload.get("type", "user_instance") or "user_instance"),
        description=str(active_payload.get("description", "") or ""),
        mode=str(active_payload.get("mode", "auto") or "auto"),
        persona=str(active_payload.get("persona", "guppy") or "guppy"),
        voice=str(active_payload.get("voice", "default") or "default"),
        last_message=str(active_payload.get("last_message", "") or ""),
    )
    if isinstance(active_payload, dict):
        library_view = getattr(owner, "_library_view", None)
        apply_library_payload(owner._assistant_view, library_view, owner._active_library_context_items, active_payload, snapshot)
    owner._assistant_view.ensure_welcome_message()
    if isinstance(active_payload, dict):
        owner._sync_right_tray(active_payload)
    owner._topbar.set_active_instance(target)
    mode, persona = owner._assistant_view.chat_context()
    owner._rotate_chat_session("instance_switched", mode=mode, persona=persona, instance=target)
    owner._topbar.set_session(workspace_role_label(str(active_payload.get("type", "user_instance") or "user_instance")))
    if announce:
        owner._assistant_view.add_system_message(f"Switched to workspace {target}.")
        owner._set_daily_activity(f"Workspace switched to {target}")
        owner._status_panel.append_syslog(f"active workspace switched: {target}")
        owner._instance_manager_view.set_status(f"Workspace switched to {target}")
        owner._log_launcher_event("instance_switched", instance=target)
    owner._sync_automation_test_state()


def bootstrap_instance_switcher(owner, *, schedule_single_shot: Callable[[int, Callable[[], None]], None]) -> None:
    snapshot = owner._local_instance_snapshot(include_workspace_details=False)
    names, active = owner._load_instance_catalog(snapshot=snapshot)
    owner._instance_histories = {}
    owner._active_instance_name = active
    owner._active_library_context_items = []
    owner._last_instance_snapshot = snapshot
    owner._instance_snapshot_expires_at = time.monotonic() + 0.75
    owner._topbar.set_instances(names, active_instance=active)
    owner._rotate_chat_session("instance_bootstrap", instance=active)
    owner._instance_manager_view.set_instances(snapshot)
    owner._settings_hub_view.set_instance_snapshot(snapshot)
    owner._settings_hub_view.set_windows_snapshot(owner._settings_hub_view.windows_ops_snapshot())
    active_payload = resolve_active_instance_payload(snapshot, active)
    if isinstance(active_payload, dict):
        library_view = getattr(owner, "_library_view", None)
        apply_library_payload(owner._assistant_view, library_view, owner._active_library_context_items, active_payload, snapshot)
        owner._assistant_view.set_active_instance(
            active,
            workspace_type=str(active_payload.get("type", "user_instance") or "user_instance"),
            description=str(active_payload.get("description", "") or ""),
            mode=str(active_payload.get("mode", "auto") or "auto"),
            persona=str(active_payload.get("persona", "guppy") or "guppy"),
            voice=str(active_payload.get("voice", "default") or "default"),
            last_message=str(active_payload.get("last_message", "") or ""),
        )
        sync_assistant_library_context(owner._assistant_view, library_view, owner._active_library_context_items)
        owner._assistant_view.ensure_welcome_message()
        owner._sync_right_tray(active_payload)
    owner._set_daily_activity(f"Active workspace: {active}")
    owner._bootstrap_instance_refresh_pending = True
    owner._bootstrap_instance_refresh_complete = False
    schedule_single_shot(0, owner._complete_bootstrap_instance_switcher)


def complete_bootstrap_instance_switcher(owner, *, schedule_single_shot: Callable[[int, Callable[[], None]], None], monotonic: Callable[[], float], fetch_connector_inventory) -> None:
    if not owner._bootstrap_instance_refresh_pending:
        return
    owner._bootstrap_instance_refresh_pending = False
    active = owner._active_instance_name
    try:
        owner._last_instance_snapshot = owner._local_instance_snapshot(include_workspace_details=True)
        owner._instance_snapshot_expires_at = monotonic() + max(2.0, owner._instance_snapshot_ttl_s)
        owner._last_connector_inventory_snapshot = [item.raw for item in fetch_connector_inventory()]
        owner._connector_inventory_expires_at = monotonic() + max(3.0, owner._connector_inventory_ttl_s)
        owner._refresh_instance_views(force=False)
    finally:
        owner._bootstrap_instance_refresh_complete = True
    schedule_single_shot(150, lambda target=active: owner._on_instance_logs_requested(target, quiet=True))


def select_active_instance(
    owner,
    name: str,
    *,
    read_json_dict,
    write_json,
) -> None:
    target = (name or "").strip()
    if not target or target == owner._active_instance_name:
        return
    if owner._request_in_flight:
        owner._status_panel.append_syslog("instance switch blocked during active request")
        owner._topbar.set_active_instance(owner._active_instance_name)
        return
    try:
        owner._http_json(
            f"/instances/{target}/activate",
            method="POST",
            payload={},
            timeout=2.0,
            retry_auth_on_401=True,
            auth_retry_reason="instance_activate",
        )
    except Exception:
        cfg = read_json_dict(owner._instances_config_path())
        if isinstance(cfg, dict):
            cfg["active_instance"] = target
            write_json(owner._instances_config_path(), cfg)
        state = read_json_dict(owner._instance_state_path())
        if isinstance(state, dict):
            state["active_instance"] = target
            entries = state.get("instances", {})
            if isinstance(entries, dict):
                for key, item in entries.items():
                    if not isinstance(item, dict):
                        continue
                    item["status"] = "active" if key == target else "idle"
            write_json(owner._instance_state_path(), state)
    owner._apply_instance_switch(target, announce=True)
    owner._refresh_instance_views(load_logs=True, force=True)
