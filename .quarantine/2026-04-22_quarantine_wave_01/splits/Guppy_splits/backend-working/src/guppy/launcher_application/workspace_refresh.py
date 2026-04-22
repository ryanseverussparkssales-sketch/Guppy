from __future__ import annotations

from src.guppy.launcher_application.library_workflow import (
    apply_library_payload,
    sync_assistant_library_context,
)
from src.guppy.launcher_application.state_builder import build_launcher_state_snapshot
from src.guppy.launcher_application.workspace_state import (
    enabled_workspace_names,
    resolve_active_instance_payload,
)
from src.guppy.launcher_application.instance_manager_presenter import workspace_role_label
from src.guppy.workspace_governance import build_connector_inventory


def load_instance_logs(owner, name: str, *, quiet: bool = False, local_log_reader=None) -> None:
    target = (name or owner._active_instance_name or "guppy-primary").strip()
    if not target:
        return
    entries: list[dict] = []
    try:
        payload = owner._http_json(
            f"/instances/{target}/logs?limit=80",
            method="GET",
            timeout=2.0,
            retry_auth_on_401=True,
            auth_retry_reason="instance_logs",
        )
        raw_entries = payload.get("entries", []) if isinstance(payload, dict) else []
        if isinstance(raw_entries, list):
            entries = [item for item in raw_entries if isinstance(item, dict)]
    except Exception:
        if callable(local_log_reader):
            entries = local_log_reader(target, limit=80)
    owner._instance_manager_view.set_logs(target, entries)
    if not quiet:
        owner._instance_manager_view.set_status(f"Loaded logs for {target}")


def refresh_instance_views(owner, *, load_logs: bool = False, force: bool = False) -> None:
    snapshot = owner._fetch_instance_snapshot(force=force)
    owner._last_instance_snapshot = snapshot
    connector_inventory_snapshot = owner._fetch_connector_inventory(force=force)
    typed_connector_inventory = build_connector_inventory(connector_inventory_snapshot)
    build_state_snapshot = getattr(owner, "_build_launcher_state_snapshot", None)
    windows_snapshot = owner._settings_hub_view.windows_ops_snapshot()
    runtime_health = getattr(owner, "_runtime_health_snapshot", None)
    if callable(build_state_snapshot):
        owner._launcher_state_snapshot = build_state_snapshot(
            snapshot,
            typed_connector_inventory,
            windows_snapshot,
            runtime_health,
        )
    else:
        owner._launcher_state_snapshot = build_launcher_state_snapshot(
            snapshot,
            typed_connector_inventory,
            windows_snapshot if isinstance(windows_snapshot, dict) else {},
            active_view="home",
            runtime_health=runtime_health,
        )
    instance_view_signature = owner._payload_signature(snapshot)
    connector_view_signature = owner._payload_signature(connector_inventory_snapshot)
    if force or instance_view_signature != owner._last_instance_view_signature:
        owner._instance_manager_view.set_instances(snapshot)
        owner._settings_hub_view.set_instance_snapshot(snapshot)
        owner._last_instance_view_signature = instance_view_signature
    if force or connector_view_signature != owner._last_connector_view_signature:
        owner._settings_hub_view.set_connector_inventory(connector_inventory_snapshot)
        owner._last_connector_view_signature = connector_view_signature
    enabled_names = enabled_workspace_names(snapshot) or [
        item.name for item in owner._launcher_state_snapshot.workspaces if item.name
    ]
    active = str(snapshot.get("active_instance", "")).strip() or owner._active_instance_name or "guppy-primary"
    if active not in enabled_names:
        enabled_names = enabled_names or [active]
        if active not in enabled_names:
            enabled_names.insert(0, active)
    stale_names = [name for name in owner._instance_histories.keys() if name not in enabled_names]
    for name in stale_names:
        owner._instance_histories.pop(name, None)
    if active != owner._active_instance_name and not owner._request_in_flight:
        owner._apply_instance_switch(active, announce=False)
    owner._topbar.set_instances(enabled_names, active_instance=active)
    active_payload = resolve_active_instance_payload(snapshot, active)
    if isinstance(active_payload, dict):
        library_view = getattr(owner, "_library_view", None)
        active_library_items = list(getattr(owner, "_active_library_context_items", []))
        library_context_signature = owner._payload_signature(
            {
                "active_instance": active,
                "active_payload": active_payload,
            }
        )
        if library_view is not None and (
            force or library_context_signature != getattr(owner, "_last_library_context_signature", "")
        ):
            apply_library_payload(owner._assistant_view, library_view, active_library_items, active_payload, snapshot)
            owner._last_library_context_signature = library_context_signature
        tools_context_signature = owner._payload_signature(
            {
                "active_instance": active,
                "active_payload": active_payload,
                "limits": snapshot.get("limits", {}) if isinstance(snapshot, dict) else {},
            }
        )
        if force or tools_context_signature != owner._last_tools_context_signature:
            owner._tools_view.set_instance_context(active_payload, snapshot)
            owner._last_tools_context_signature = tools_context_signature
        owner._sync_right_tray(active_payload)
        owner._assistant_view.set_active_instance(
            active,
            workspace_type=str(active_payload.get("type", "user_instance") or "user_instance"),
            description=str(active_payload.get("description", "") or ""),
            mode=str(active_payload.get("mode", "auto") or "auto"),
            persona=str(active_payload.get("persona", "guppy") or "guppy"),
            voice=str(active_payload.get("voice", "default") or "default"),
            last_message=str(active_payload.get("last_message", "") or ""),
        )
        sync_assistant_library_context(owner._assistant_view, library_view, active_library_items)
        role_label = workspace_role_label(str(active_payload.get("type", "user_instance") or "user_instance"))
        owner_role_label = getattr(owner, "_workspace_role_label", None)
        if callable(owner_role_label):
            role_label = owner_role_label(str(active_payload.get("type", "user_instance") or "user_instance"))
        owner._topbar.set_session(role_label)
    windows_snapshot_signature = owner._payload_signature(windows_snapshot)
    if force or windows_snapshot_signature != owner._last_windows_snapshot_signature:
        owner._settings_hub_view.set_windows_snapshot(windows_snapshot)
        owner._last_windows_snapshot_signature = windows_snapshot_signature
    if load_logs:
        owner._on_instance_logs_requested(active, quiet=True)
    owner._sync_automation_test_state()
