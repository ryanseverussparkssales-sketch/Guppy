from __future__ import annotations

from src.guppy.launcher_application.instance_manager_presenter import (
    workspace_first_run_recipe,
    workspace_onboarding_ready_message,
)
from src.guppy.launcher_application.local_instance_state import (
    local_delete_instance,
    local_upsert_instance,
)


def refresh_instance_manager(owner) -> None:
    owner._refresh_instance_views(load_logs=True, force=True)
    owner._instance_manager_view.set_status("Workspace state refreshed")


def save_workspace(owner, payload: dict) -> None:
    name = str(payload.get("name", "")).strip()
    workspace_type = str(payload.get("type", "user_instance") or "user_instance")
    if not name:
        owner._instance_manager_view.set_status("Workspace name is required", ok=False)
        return
    try:
        result = owner._http_json(
            "/instances",
            method="POST",
            payload=payload,
            timeout=3.0,
            retry_auth_on_401=True,
            auth_retry_reason="instance_create",
        )
    except Exception as error:
        try:
            result = {
                "action": local_upsert_instance(
                    owner._instances_config_path(),
                    owner._instance_state_path(),
                    payload,
                )
            }
            owner._status_panel.append_syslog(f"workspace save used local fallback: {name}")
        except Exception as local_error:
            message = str(local_error if str(local_error).strip() else error)
            if "instance limit reached" in message.lower():
                message = "Workspace limit reached (5 / 5). Delete a workspace or update an existing name."
            owner._instance_manager_view.set_status(f"Save failed: {message}", ok=False)
            owner._status_panel.append_syslog(f"workspace save failed: {message}")
            return
    action = str(result.get("action", "updated")).strip() or "updated"
    owner._refresh_instance_views(load_logs=True, force=True)
    if action == "created":
        owner._apply_instance_switch(name, announce=True)
        owner._refresh_instance_views(load_logs=True, force=True)
        recipe_builder = getattr(owner, "_workspace_first_run_recipe", None)
        onboarding_builder = getattr(owner, "_workspace_onboarding_ready_message", None)
        recipe = recipe_builder(workspace_type) if callable(recipe_builder) else workspace_first_run_recipe(workspace_type)
        onboarding_message = (
            onboarding_builder(name, workspace_type)
            if callable(onboarding_builder)
            else workspace_onboarding_ready_message(name, workspace_type)
        )
        add_system = getattr(getattr(owner, "_assistant_view", None), "add_system_message", None)
        if callable(add_system):
            add_system(onboarding_message)
        activity_setter = getattr(owner, "_set_daily_activity", None)
        if callable(activity_setter):
            activity_setter(f"Workspace ready: {name} | {recipe}")
        log_event = getattr(owner, "_log_launcher_event", None)
        if callable(log_event):
            log_event("workspace_onboarding_ready", instance=name, workspace_type=workspace_type, recipe=recipe)
        owner._instance_manager_view.set_status(f"Workspace {name} created. {recipe}")
        owner._status_panel.append_syslog(f"workspace {name} created. {recipe}")
        return
    owner._instance_manager_view.set_status(f"Workspace {name} {action}")
    owner._status_panel.append_syslog(f"workspace {name} {action}")


def delete_workspace(owner, name: str) -> None:
    target = (name or "").strip()
    if not target:
        return
    try:
        result = owner._http_json(
            f"/instances/{target}",
            method="DELETE",
            timeout=3.0,
            retry_auth_on_401=True,
            auth_retry_reason="instance_delete",
        )
    except Exception as error:
        try:
            result = {
                "active_instance": local_delete_instance(
                    owner._instances_config_path(),
                    owner._instance_state_path(),
                    target,
                )
            }
            owner._status_panel.append_syslog(f"workspace delete used local fallback: {target}")
        except Exception as local_error:
            message = str(local_error if str(local_error).strip() else error)
            owner._instance_manager_view.set_status(f"Delete failed: {message}", ok=False)
            owner._status_panel.append_syslog(f"workspace delete failed: {message}")
            return
    new_active = str(result.get("active_instance", owner._active_instance_name)).strip() or owner._active_instance_name
    if target == owner._active_instance_name:
        owner._apply_instance_switch(new_active, announce=False)
    owner._instance_histories.pop(target, None)
    owner._instance_manager_view.set_status(f"Workspace {target} deleted")
    owner._status_panel.append_syslog(f"workspace deleted: {target}")
    owner._refresh_instance_views(load_logs=True, force=True)
