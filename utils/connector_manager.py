from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.guppy.launcher_application.connector_action_service import run_connector_action as _service_run_connector_action
from src.guppy.launcher_application.connector_state_service import (
    integration_level as _service_integration_level,
    load_state as _service_load_state,
    log_connector_policy_denial as _service_log_connector_policy_denial,
    log_integration_event as _service_log_integration_event,
    new_event_id as _service_new_event_id,
    now_iso as _service_now_iso,
    record_auth_state as _service_record_auth_state,
    save_state as _service_save_state,
)
from src.guppy.workspace_governance import (
    build_connector_guidance as _governance_build_connector_guidance,
    build_connector_status as _governance_build_connector_status,
    clear_machine_secret as _governance_clear_machine_secret,
    connector_action_for_tool as _governance_connector_action_for_tool,
    connector_catalog as _governance_connector_catalog,
    connector_id_for_tool as _governance_connector_id_for_tool,
    keyring_key as _governance_keyring_key,
    list_connector_ids as _governance_list_connector_ids,
    provider_environment_fields as _governance_provider_environment_fields,
    provider_metadata as _governance_provider_metadata,
    read_machine_secret as _governance_read_machine_secret,
    select_account_row as _governance_select_account_row,
    select_provider_row as _governance_select_provider_row,
    secret_field_meta as _governance_secret_field_meta,
    token_path_for_gmail_account as _governance_token_path_for_gmail_account,
    validate_secret_value as _governance_validate_secret_value,
    write_machine_secret as _governance_write_machine_secret,
)
from utils.connector_bindings import (
    list_workspace_connector_bindings,
    resolve_workspace_connector_binding,
    set_workspace_connector_binding,
)
from utils.connector_action_history import finalize_action_result, record_action_result
from utils import connector_workspace

try:
    from utils.operational_telemetry import log_operational_event as _log_operational_event
    _OPS_TELEMETRY_AVAILABLE = True
except Exception:
    _OPS_TELEMETRY_AVAILABLE = False

    def _log_operational_event(stream: str, event: str, payload: dict[str, Any], level: str = "info") -> None:
        del stream, event, payload, level
        return


_ROOT = Path(__file__).resolve().parent.parent
_RUNTIME_DIR = _ROOT / "runtime"
_CONNECTOR_STATE_PATH = _RUNTIME_DIR / "connector_state.json"
_INTEGRATION_EVENTS_PATH = _RUNTIME_DIR / "integration_events.jsonl"
_POLICY_DENIAL_DEDUPE_TTL_S = 10.0
_RECENT_POLICY_DENIALS: dict[str, float] = {}

_CONNECTOR_IDS = _governance_list_connector_ids()
_CONNECTOR_CATALOG = _governance_connector_catalog()
_CRM_PROVIDER_ENV = {
    provider_id: list(fields)
    for provider_id, fields in _governance_provider_environment_fields("crm").items()
}
_VOIP_PROVIDER_ENV = {
    provider_id: list(fields)
    for provider_id, fields in _governance_provider_environment_fields("voip").items()
}
_CRM_PROVIDER_META = _governance_provider_metadata("crm")
_VOIP_PROVIDER_META = _governance_provider_metadata("voip")


def _now_iso() -> str:
    return _service_now_iso()


def _load_state() -> dict[str, Any]:
    return _service_load_state(_CONNECTOR_STATE_PATH)


def _save_state(payload: dict[str, Any]) -> None:
    _service_save_state(_RUNTIME_DIR, _CONNECTOR_STATE_PATH, payload)


def _integration_level(event_type: str, payload: dict[str, Any]) -> str:
    return _service_integration_level(event_type, payload)


def _new_event_id(prefix: str) -> str:
    return _service_new_event_id(prefix)


def _log_integration_event(event_type: str, payload: dict[str, Any], *, level: str | None = None) -> None:
    _service_log_integration_event(
        _RUNTIME_DIR,
        _INTEGRATION_EVENTS_PATH,
        event_type,
        payload,
        level=level,
        log_operational_event_fn=(
            lambda stream, event, event_payload, event_level: _log_operational_event(
                stream, event, event_payload, level=event_level
            )
        )
        if _OPS_TELEMETRY_AVAILABLE
        else None,
    )


def _keyring_key(secret_key: str) -> str:
    return _governance_keyring_key(secret_key)


def read_machine_secret(secret_key: str, *, fallback: str | None = None) -> str:
    return _governance_read_machine_secret(secret_key, fallback=fallback)


def write_machine_secret(secret_key: str, value: str) -> bool:
    return _governance_write_machine_secret(secret_key, value)


def clear_machine_secret(secret_key: str) -> bool:
    return _governance_clear_machine_secret(secret_key)


def _secret_field_meta(secret_key: str) -> dict[str, Any]:
    return _governance_secret_field_meta(secret_key)


def secret_field_meta(secret_key: str) -> dict[str, Any]:
    return dict(_governance_secret_field_meta(secret_key))


def _validate_secret_value(secret_key: str, value: str) -> tuple[bool, str]:
    return _governance_validate_secret_value(secret_key, value)


_selected_provider_row = _governance_select_provider_row
_selected_account_row = _governance_select_account_row
_connector_guidance = _governance_build_connector_guidance
_token_path_for_gmail_account = _governance_token_path_for_gmail_account


def _history_timeline(recent_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return connector_workspace.history_timeline(recent_events)


def _history_payload(connector_id: str) -> dict[str, Any]:
    return connector_workspace.history_payload(connector_id, load_state=_load_state)


def connector_id_for_tool(tool_name: str) -> str:
    return _governance_connector_id_for_tool(tool_name)


def connector_action_for_tool(tool_name: str) -> str:
    return _governance_connector_action_for_tool(tool_name)


def connector_status(connector_id: str, *, provider: str = "") -> dict[str, Any]:
    payload = _governance_build_connector_status(connector_id, provider=provider)
    _record_auth_state(payload)
    return payload


def _record_auth_state(payload: dict[str, Any]) -> None:
    _service_record_auth_state(
        payload,
        load_state_fn=_load_state,
        save_state_fn=_save_state,
        log_event_fn=_log_integration_event,
        now_iso_fn=_now_iso,
    )


def connector_inventory() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for connector_id in _CONNECTOR_IDS:
        item = connector_status(connector_id)
        history = _history_payload(connector_id)
        item["history"] = history
        item.update(history)
        rows.append(item)
    return rows


def _effective_binding_enabled(workspace_name: str, binding: dict[str, Any]) -> tuple[bool, bool]:
    return connector_workspace.effective_binding_enabled(workspace_name, binding)


def _binding_validation_payload(
    workspace_name: str,
    binding: dict[str, Any],
    status: dict[str, Any],
    *,
    enabled: bool,
    inherited: bool,
    provider: str,
    account_id: str,
) -> dict[str, Any]:
    return connector_workspace.binding_validation_payload(
        workspace_name,
        binding,
        status,
        enabled=enabled,
        inherited=inherited,
        provider=provider,
        account_id=account_id,
    )


def _history_summary_line(history: dict[str, Any]) -> str:
    return connector_workspace.history_summary_line(history)


def _readiness_evidence_payload(
    connector_id: str,
    status: dict[str, Any],
    history: dict[str, Any],
    validation: dict[str, Any],
    *,
    action_id: str,
    provider: str,
    account_id: str,
) -> dict[str, Any]:
    return connector_workspace.readiness_evidence_payload(
        connector_id,
        status,
        history,
        validation,
        action_id=action_id,
        provider=provider,
        account_id=account_id,
        connector_guidance=_connector_guidance,
    )


def workspace_connector_inventory(
    workspace_name: str,
    *,
    config_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    return connector_workspace.workspace_connector_inventory(
        workspace_name,
        connector_ids=_CONNECTOR_IDS,
        resolve_workspace_connector_binding=resolve_workspace_connector_binding,
        connector_status=connector_status,
        history_payload_fn=_history_payload,
        binding_validation_payload_fn=_binding_validation_payload,
        readiness_evidence_payload_fn=_readiness_evidence_payload,
        config_path=config_path,
    )


def workspace_tool_readiness(
    tool_name: str,
    workspace_name: str,
    *,
    metadata: dict[str, Any] | None = None,
    endpoint: str = "",
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    return connector_workspace.workspace_tool_readiness(
        tool_name,
        workspace_name,
        get_workspace_connector_context_fn=get_workspace_connector_context,
        history_payload_fn=_history_payload,
        binding_validation_payload_fn=_binding_validation_payload,
        readiness_evidence_payload_fn=_readiness_evidence_payload,
        metadata=metadata,
        endpoint=endpoint,
        config_path=config_path,
    )


def get_workspace_connector_context(
    tool_name: str,
    workspace_name: str,
    *,
    metadata: dict[str, Any] | None = None,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    return connector_workspace.get_workspace_connector_context(
        tool_name,
        workspace_name,
        connector_id_for_tool=connector_id_for_tool,
        connector_action_for_tool=connector_action_for_tool,
        resolve_workspace_connector_binding=resolve_workspace_connector_binding,
        connector_status=connector_status,
        metadata=metadata,
        config_path=config_path,
    )


def evaluate_workspace_connector_policy(
    tool_name: str,
    workspace_name: str,
    *,
    metadata: dict[str, Any] | None = None,
    endpoint: str = "",
    config_path: str | Path | None = None,
) -> tuple[bool, str, dict[str, Any]]:
    return connector_workspace.evaluate_workspace_connector_policy(
        tool_name,
        workspace_name,
        get_workspace_connector_context_fn=get_workspace_connector_context,
        metadata=metadata,
        endpoint=endpoint,
        config_path=config_path,
    )


def _record_action_result(
    connector_id: str,
    action: str,
    *,
    ok: bool,
    summary: str,
    provider: str = "",
    account_id: str = "",
    secret_key: str = "",
    status: dict[str, Any] | None = None,
    guidance: dict[str, Any] | None = None,
) -> None:
    record_action_result(
        connector_id,
        action,
        ok=ok,
        summary=summary,
        provider=provider,
        account_id=account_id,
        secret_key=secret_key,
        status=status,
        guidance=guidance,
        load_state=_load_state,
        save_state=_save_state,
        now_iso=_now_iso,
        new_event_id=_new_event_id,
        log_integration_event=_log_integration_event,
        selected_provider_row=_selected_provider_row,
        connector_guidance=_connector_guidance,
    )


def _finalize_action_result(
    connector_id: str,
    action: str,
    *,
    ok: bool,
    summary: str,
    provider: str = "",
    account_id: str = "",
    secret_key: str = "",
    status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return finalize_action_result(
        connector_id,
        action,
        ok=ok,
        summary=summary,
        provider=provider,
        account_id=account_id,
        secret_key=secret_key,
        status=status,
        connector_guidance=_connector_guidance,
        record_action_result_fn=_record_action_result,
        history_payload_fn=_history_payload,
    )


def run_connector_action(
    connector_id: str,
    action: str,
    *,
    provider: str = "",
    account_id: str = "",
    secret_key: str = "",
    secret_value: str = "",
) -> dict[str, Any]:
    return _service_run_connector_action(
        connector_id,
        action,
        provider=provider,
        account_id=account_id,
        secret_key=secret_key,
        secret_value=secret_value,
        connector_status_fn=connector_status,
        selected_provider_row_fn=_selected_provider_row,
        validate_secret_value_fn=_validate_secret_value,
        write_machine_secret_fn=write_machine_secret,
        clear_machine_secret_fn=clear_machine_secret,
        secret_field_meta_fn=_secret_field_meta,
        finalize_action_result_fn=_finalize_action_result,
        token_path_for_gmail_account_fn=_token_path_for_gmail_account,
        env=os.environ,
    )


def save_workspace_connector_binding(
    workspace_name: str,
    connector_id: str,
    payload: dict[str, Any],
    *,
    config_path: str | Path | None = None,
) -> Path:
    path = set_workspace_connector_binding(workspace_name, connector_id, payload, config_path=config_path)
    _log_integration_event(
        "workspace.connector_binding_saved",
        {
            "workspace": str(workspace_name or "").strip(),
            "connector": str(connector_id or "").strip().lower(),
            "enabled": bool(payload.get("enabled", False)),
        },
    )
    return path


def workspace_binding_map(
    workspace_name: str,
    *,
    config_path: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    return list_workspace_connector_bindings(workspace_name, config_path=config_path)


def log_connector_policy_denial(
    connector_id: str,
    workspace_name: str,
    reason_code: str,
    reason: str,
) -> None:
    _service_log_connector_policy_denial(
        connector_id,
        workspace_name,
        reason_code,
        reason,
        recent_denials=_RECENT_POLICY_DENIALS,
        dedupe_ttl_s=_POLICY_DENIAL_DEDUPE_TTL_S,
        log_event_fn=lambda event_type, payload: _log_integration_event(event_type, payload, level="warning"),
    )
