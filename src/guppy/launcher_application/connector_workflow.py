"""
src/guppy/launcher_application/connector_workflow.py

Connector lifecycle orchestration for the launcher.

SETTINGS OWNERSHIP CONTRACT
---------------------------
All connector setup and account actions (connect, verify, guided-link, etc.)
MUST originate from Settings > Device & Accounts or Settings > Operations.
The ``_reject_non_settings_owned_request`` guard enforces this at the
entry points of every externally-callable handler.  No connector action
bypasses Settings ownership.  Workspaces bind already-configured connectors;
they do NOT own connector setup or machine-level auth.
"""
from __future__ import annotations

import threading

from src.guppy.launcher_application.connector_dispatch import (
    connector_action_http_payload,
    connector_action_record,
    connector_action_status_label,
    execute_guided_connector_setup,
)
from src.guppy.launcher_application.services import (
    execute_connector_action,
    save_workspace_connector_binding,
)
from src.guppy.workspace_governance import (
    build_connector_action_request,
    build_connector_action_result,
    resolve_instance_permissions,
    set_instance_tool_permission_policy,
)

_SETTINGS_REQUEST_SOURCES = {
    "settings_device_accounts",
    "settings_operations_panel",
}


def _settings_owned_request_source(payload: dict) -> tuple[bool, str]:
    source = str(payload.get("request_source", "") or "").strip().lower()
    if not source:
        return False, "missing_request_source"
    return source in _SETTINGS_REQUEST_SOURCES, source


def _reject_non_settings_owned_request(owner, payload: dict, *, action: str) -> bool:
    allowed, source = _settings_owned_request_source(payload)
    if allowed:
        return False
    connector_id = str(payload.get("connector", "") or "").strip().lower()
    message = "Connector setup and account actions only run from Settings > Device & Accounts."
    owner._settings_hub_view.set_account_result(message, ok=False)
    owner._settings_hub_view.append_log(f"connector action rejected: {connector_id or 'unknown'} {action} from {source}")
    owner._status_panel.append_syslog(f"connector action rejected: {connector_id or 'unknown'} {action} from {source}")
    owner._log_launcher_event(
        "connector_action_rejected",
        connector=connector_id,
        action=action,
        request_source=source,
        reason="settings_owned_only",
    )
    return True


def save_instance_governance(owner, payload: dict, *, backend_available: bool) -> None:
    name = str(payload.get("name", "")).strip()
    if not name:
        owner._instance_manager_view.set_governance_status("Workspace name is required for governance save.", ok=False)
        return
    body = {
        "auth_mode": str(payload.get("auth_mode", "runtime_default") or "runtime_default"),
        "tool_allow": list(payload.get("tool_allow", []) or []),
        "tool_block": list(payload.get("tool_block", []) or []),
        "endpoint_allow": list(payload.get("endpoint_allow", []) or []),
        "endpoint_block": list(payload.get("endpoint_block", []) or []),
        "policy_note": str(payload.get("policy_note", "") or "").strip(),
    }
    try:
        owner._http_json(
            f"/instances/{name}/governance",
            method="POST",
            payload=body,
            timeout=3.0,
            retry_auth_on_401=True,
            auth_retry_reason="instance_governance_save",
        )
    except Exception as error:
        if not backend_available:
            owner._instance_manager_view.set_governance_status(f"Governance save failed: {error}", ok=False)
            owner._status_panel.append_syslog(f"workspace governance save failed: {error}")
            return
        try:
            instance_type = str(payload.get("instance_type", "user_instance") or "user_instance")
            resolved = resolve_instance_permissions(name, instance_type)
            set_instance_tool_permission_policy(
                name,
                {
                    "read": bool(resolved.get("read", False)),
                    "write": bool(resolved.get("write", False)),
                    "execute": bool(resolved.get("execute", False)),
                    "network": bool(resolved.get("network", False)),
                    **body,
                },
            )
        except Exception as local_error:
            owner._instance_manager_view.set_governance_status(f"Governance save failed: {local_error}", ok=False)
            owner._status_panel.append_syslog(f"workspace governance save failed: {local_error}")
            return
    owner._instance_manager_view.set_governance_status(f"Governance saved for {name}")
    owner._status_panel.append_syslog(f"workspace governance saved: {name}")
    owner._log_launcher_event("workspace_governance_saved", instance=name, auth_mode=body["auth_mode"])
    owner._refresh_instance_views(load_logs=True, force=True)


def save_instance_connector_binding(owner, payload: dict, *, backend_available: bool) -> None:
    name = str(payload.get("name", "")).strip()
    connector_id = str(payload.get("connector", "")).strip().lower()
    if not name or not connector_id:
        owner._instance_manager_view.set_connector_binding_status("Workspace and connector are required for save.", ok=False)
        return
    body = {
        "enabled": bool(payload.get("enabled", False)),
        "account_id": str(payload.get("account_id", "") or "").strip().lower(),
        "provider": str(payload.get("provider", "") or "").strip().lower(),
        "action_allow": list(payload.get("action_allow", []) or []),
        "action_block": list(payload.get("action_block", []) or []),
        "endpoint_allow": list(payload.get("endpoint_allow", []) or []),
        "endpoint_block": list(payload.get("endpoint_block", []) or []),
        "note": str(payload.get("note", "") or "").strip(),
    }
    try:
        owner._http_json(
            f"/instances/{name}/connectors/{connector_id}",
            method="POST",
            payload=body,
            timeout=3.0,
            retry_auth_on_401=True,
            auth_retry_reason="instance_connector_binding_save",
        )
    except Exception as error:
        if not backend_available:
            owner._instance_manager_view.set_connector_binding_status(f"Connector binding save failed: {error}", ok=False)
            owner._status_panel.append_syslog(f"connector binding save failed: {error}")
            return
        try:
            save_workspace_connector_binding(name, connector_id, body)
        except Exception as local_error:
            owner._instance_manager_view.set_connector_binding_status(f"Connector binding save failed: {local_error}", ok=False)
            owner._status_panel.append_syslog(f"connector binding save failed: {local_error}")
            return
    owner._instance_manager_view.set_connector_binding_status(f"Connector binding saved for {name} / {connector_id}")
    owner._status_panel.append_syslog(f"connector binding saved: {name} / {connector_id}")
    owner._log_launcher_event("workspace_connector_binding_saved", instance=name, connector=connector_id)
    owner._refresh_instance_views(load_logs=False, force=True)


def perform_connector_action_request(owner, payload: dict, *, backend_available: bool) -> dict:
    connector_id = str(payload.get("connector", "")).strip().lower()
    action = str(payload.get("action", "")).strip().lower()
    if not connector_id or not action:
        return {}
    request = build_connector_action_request(
        connector_id,
        action,
        provider=str(payload.get("provider", "") or "").strip().lower(),
        account_id=str(payload.get("account_id", "") or "").strip().lower(),
        secret_key=str(payload.get("secret_key", "") or "").strip(),
        secret_value=str(payload.get("secret_value", "") or "").strip(),
        workspace_name=str(owner._active_instance_name or "").strip(),
    )
    try:
        result = owner._http_json(
            f"/connectors/{connector_id}/{action}",
            method="POST",
            payload=connector_action_http_payload(request),
            timeout=6.0,
            retry_auth_on_401=True,
            auth_retry_reason="connector_action",
        )
        typed_result = build_connector_action_result(
            {
                **(result if isinstance(result, dict) else {}),
                "connector": connector_id,
                "action": action,
            }
        )
    except Exception as error:
        if not backend_available:
            owner._settings_hub_view.append_log(f"connector action failed: {error}")
            return {}
        typed_result = execute_connector_action(request)
    return connector_action_record(request, typed_result)


def apply_connector_action_feedback(owner, record: dict, *, refresh_after: bool = True) -> dict:
    if not isinstance(record, dict) or not record:
        return {}
    connector_id = str(record.get("connector", "") or "").strip().lower()
    action = str(record.get("action", "") or "").strip().lower()
    ok = bool(record.get("ok", False))
    summary = str(record.get("summary", "") or "").strip()
    next_step = str(record.get("next_step", "") or "").strip()
    result_code = str(record.get("result_code", "") or "").strip()
    fix_target = str(record.get("fix_target", "") or "").strip()
    event_id = str(record.get("event_id", "") or "").strip()
    status = record.get("status", {}) if isinstance(record.get("status"), dict) else {}
    owner._settings_hub_view.append_log(summary)
    if next_step:
        owner._settings_hub_view.append_log("next step: " + next_step + (f" | fix in: {fix_target}" if fix_target else ""))
    owner._settings_hub_view.set_account_result(
        summary + (f" | Next: {next_step}" if next_step else ""),
        ok=ok,
    )
    owner._status_panel.append_syslog(summary)
    owner._set_daily_activity(summary)
    owner._log_launcher_event(
        "connector_action_result",
        connector=connector_id,
        action=action,
        ok=ok,
        summary=summary,
        provider=str(record.get("provider", "") or "").strip().lower(),
        account_id=str(record.get("account_id", "") or "").strip().lower(),
        event_id=event_id,
        integration_event=str(record.get("integration_event", "") or "").strip(),
        auth_state=str(status.get("auth_state", "") or ""),
        result_code=result_code,
        next_step=next_step,
        fix_target=fix_target,
    )
    if refresh_after:
        owner._refresh_instance_views(load_logs=False, force=True)
    return record


def run_connector_action_request(owner, payload: dict, *, refresh_after: bool = True, backend_available: bool) -> dict:
    record = perform_connector_action_request(owner, payload, backend_available=backend_available)
    return apply_connector_action_feedback(owner, record, refresh_after=refresh_after)


def start_connector_action_async(owner, payload: dict, *, refresh_after: bool = True, backend_available: bool) -> None:
    connector_id = str(payload.get("connector", "") or "").strip().lower()
    action = str(payload.get("action", "") or "").strip().lower()
    if not connector_id or not action:
        return
    action_label = connector_action_status_label(action)
    owner._settings_hub_view.set_account_result(action_label, ok=True)
    owner._settings_hub_view.append_log(f"{connector_id} {action} requested")
    owner._status_panel.append_syslog(f"{connector_id} {action} requested")

    def _worker() -> None:
        record = perform_connector_action_request(owner, payload, backend_available=backend_available)
        owner._connector_action_events.put({"kind": "single", "record": record, "refresh_after": refresh_after})
        emitter = getattr(owner, "connector_action_event_queued", None)
        if emitter is not None and hasattr(emitter, "emit"):
            emitter.emit()

    threading.Thread(target=_worker, daemon=True).start()


def start_connector_guided_link_async(owner, payload: dict, *, backend_available: bool) -> None:
    connector_id = str(payload.get("connector", "") or "").strip().lower()
    provider = str(payload.get("provider", "") or "").strip().lower()
    account_id = str(payload.get("account_id", "") or "").strip().lower()
    secrets = [item for item in payload.get("secrets", []) if isinstance(item, dict)]
    verify_after = bool(payload.get("verify_after", True))
    owner._settings_hub_view.set_account_result("Saving details and checking the connection...", ok=True)
    owner._settings_hub_view.append_log(f"{connector_id} guided setup requested")
    owner._status_panel.append_syslog(f"{connector_id} guided setup requested")

    def _worker() -> None:
        records = execute_guided_connector_setup(
            connector_id=connector_id,
            provider=provider,
            account_id=account_id,
            secrets=secrets,
            verify_after=verify_after,
            performer=lambda action_payload: perform_connector_action_request(
                owner,
                action_payload,
                backend_available=backend_available,
            ),
        )
        owner._connector_action_events.put({"kind": "batch", "records": records, "refresh_after": True})
        emitter = getattr(owner, "connector_action_event_queued", None)
        if emitter is not None and hasattr(emitter, "emit"):
            emitter.emit()

    threading.Thread(target=_worker, daemon=True).start()


def drain_connector_action_events(owner) -> None:
    while True:
        try:
            payload = owner._connector_action_events.get_nowait()
        except Exception as error:
            if error.__class__.__name__ == "Empty":
                break
            raise
        kind = str(payload.get("kind", "single") or "single").strip().lower()
        if kind == "batch":
            records = [item for item in payload.get("records", []) if isinstance(item, dict)]
            for index, record in enumerate(records):
                apply_connector_action_feedback(
                    owner,
                    record,
                    refresh_after=bool(payload.get("refresh_after", False)) and index == len(records) - 1,
                )
        else:
            record = payload.get("record", {}) if isinstance(payload.get("record"), dict) else {}
            apply_connector_action_feedback(owner, record, refresh_after=bool(payload.get("refresh_after", False)))


def handle_connector_action_request(owner, payload: dict, *, backend_available: bool) -> None:
    action = str(payload.get("action", "") or "").strip().lower()
    if _reject_non_settings_owned_request(owner, payload, action=action):
        return
    start_connector_action_async(owner, payload, refresh_after=True, backend_available=backend_available)


def handle_connector_guided_link_request(owner, payload: dict, *, backend_available: bool) -> None:
    if _reject_non_settings_owned_request(owner, payload, action="guided_link"):
        return
    connector_id = str(payload.get("connector", "")).strip().lower()
    if not connector_id:
        owner._settings_hub_view.set_account_result("Choose a connector before saving details.", ok=False)
        return
    secrets = [item for item in payload.get("secrets", []) if isinstance(item, dict)]
    if not secrets:
        owner._settings_hub_view.set_account_result("Add an API key or account details before saving.", ok=False)
        return
    start_connector_guided_link_async(owner, payload, backend_available=backend_available)
