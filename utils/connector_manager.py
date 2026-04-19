from __future__ import annotations

import json
import os
import time
from fnmatch import fnmatchcase
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

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
    return datetime.now(timezone.utc).isoformat()


def _load_state() -> dict[str, Any]:
    if not _CONNECTOR_STATE_PATH.exists():
        return {"version": 1, "connectors": {}}
    try:
        return json.loads(_CONNECTOR_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "connectors": {}}


def _save_state(payload: dict[str, Any]) -> None:
    _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    _CONNECTOR_STATE_PATH.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _integration_level(event_type: str, payload: dict[str, Any]) -> str:
    normalized_event = str(event_type or "").strip().lower()
    reason_code = str(payload.get("reason_code", "") or "").strip().lower()
    if payload.get("ok") is False or "error" in normalized_event or "failed" in normalized_event:
        return "error"
    if "policy_denied" in normalized_event or reason_code:
        return "warning"
    return "info"


def _new_event_id(prefix: str) -> str:
    normalized = str(prefix or "connector").strip().lower() or "connector"
    return f"{normalized}-{uuid4().hex[:10]}"


def _log_integration_event(event_type: str, payload: dict[str, Any], *, level: str | None = None) -> None:
    _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    ts = _now_iso()
    resolved_level = str(level or _integration_level(event_type, payload)).strip().lower() or "info"
    record = {
        "timestamp": ts,
        "ts": ts,
        "event_type": event_type,
        "event": event_type,
        "level": resolved_level,
        "payload": payload,
    }
    with _INTEGRATION_EVENTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")
    if _OPS_TELEMETRY_AVAILABLE:
        _log_operational_event("integration_events", str(event_type or "event"), payload, level=resolved_level)


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
    timeline: list[dict[str, Any]] = []
    for item in recent_events[-5:]:
        if not isinstance(item, dict):
            continue
        timeline.append(
            {
                "event_id": str(item.get("event_id", "") or "").strip(),
                "integration_event": str(item.get("integration_event", "") or "").strip(),
                "action": str(item.get("action", "") or "").strip(),
                "provider": str(item.get("provider", "") or "").strip(),
                "account_id": str(item.get("account_id", "") or "").strip(),
                "ok": bool(item.get("ok", False)),
                "summary": str(item.get("summary", "") or "").strip(),
                "at": str(item.get("at", "") or "").strip(),
                "result_code": str(item.get("result_code", "") or "").strip(),
                "next_step": str(item.get("next_step", "") or "").strip(),
                "fix_target": str(item.get("fix_target", "") or "").strip(),
            }
        )
    return timeline


def _history_payload(connector_id: str) -> dict[str, Any]:
    state = _load_state()
    rows = state.get("connectors", {}) if isinstance(state.get("connectors"), dict) else {}
    previous = rows.get(str(connector_id or "").strip().lower(), {})
    if not isinstance(previous, dict):
        previous = {}
    recent_events = previous.get("recent_events", [])
    if not isinstance(recent_events, list):
        recent_events = []
    last_action_record = previous.get("last_action_record", {})
    if not isinstance(last_action_record, dict):
        last_action_record = {}
    last_verify_record = previous.get("last_verify_record", {})
    if not isinstance(last_verify_record, dict):
        last_verify_record = {}
    recent_rows = [item for item in recent_events if isinstance(item, dict)][-5:]
    timeline = _history_timeline(recent_rows)
    recent_summary = " | ".join(
        f"{str(item.get('action', 'action') or 'action')}={'OK' if bool(item.get('ok', False)) else 'FAIL'}"
        + (f" ref={str(item.get('event_id', '') or '').strip()}" if str(item.get("event_id", "") or "").strip() else "")
        for item in timeline[-3:]
    )
    return {
        "last_verified_at": str(previous.get("last_verified_at", "") or ""),
        "last_verify_ok": bool(previous.get("last_verify_ok", False)),
        "last_verify_summary": str(previous.get("last_verify_summary", "") or ""),
        "last_verify_event_id": str(previous.get("last_verify_event_id", "") or ""),
        "last_action": str(previous.get("last_action", "") or ""),
        "last_action_at": str(previous.get("last_action_at", "") or ""),
        "last_action_ok": bool(previous.get("last_action_ok", False)),
        "last_result": str(previous.get("last_result", "") or ""),
        "last_event_id": str(previous.get("last_event_id", "") or ""),
        "last_action_record": last_action_record,
        "last_verify_record": last_verify_record,
        "recent_events": recent_rows,
        "timeline": timeline,
        "recent_summary": recent_summary,
    }


def connector_id_for_tool(tool_name: str) -> str:
    return _governance_connector_id_for_tool(tool_name)


def connector_action_for_tool(tool_name: str) -> str:
    return _governance_connector_action_for_tool(tool_name)


def connector_status(connector_id: str, *, provider: str = "") -> dict[str, Any]:
    payload = _governance_build_connector_status(connector_id, provider=provider)
    _record_auth_state(payload)
    return payload


def _record_auth_state(payload: dict[str, Any]) -> None:
    connector_id = str(payload.get("id", "")).strip().lower()
    if not connector_id:
        return
    state = _load_state()
    connectors = state.get("connectors", {}) if isinstance(state.get("connectors"), dict) else {}
    previous = connectors.get(connector_id, {}) if isinstance(connectors.get(connector_id), dict) else {}
    next_state = str(payload.get("auth_state", "missing"))
    if str(previous.get("auth_state", "")) != next_state:
        _log_integration_event(
            "connector.auth_state_changed",
            {
                "connector": connector_id,
                "from": str(previous.get("auth_state", "unknown")),
                "to": next_state,
                "detail": str(payload.get("auth_detail", "")),
            },
        )
    connectors[connector_id] = {
        **previous,
        "auth_state": next_state,
        "auth_detail": str(payload.get("auth_detail", "")),
        "source": str(payload.get("source", "none")),
        "last_seen_at": _now_iso(),
    }
    state["connectors"] = connectors
    _save_state(state)


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
    if bool(binding.get("_exists", False)):
        return bool(binding.get("enabled", False)), False
    if str(workspace_name or "").strip().lower() == "guppy-primary":
        return True, True
    return False, False


def workspace_connector_inventory(
    workspace_name: str,
    *,
    config_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    workspace = str(workspace_name or "").strip()
    rows: list[dict[str, Any]] = []
    for connector_id in _CONNECTOR_IDS:
        binding = resolve_workspace_connector_binding(workspace, connector_id, config_path=config_path)
        enabled, inherited = _effective_binding_enabled(workspace, binding)
        provider = str(binding.get("provider", "") or "")
        item = connector_status(connector_id, provider=provider)
        history = _history_payload(connector_id)
        selected_account = str(binding.get("account_id", "") or "").strip().lower()
        available_accounts = {
            str(account.get("id", "")).strip().lower()
            for account in item.get("accounts", [])
            if isinstance(account, dict) and str(account.get("id", "")).strip()
        }
        available_providers = {
            str(provider_row.get("id", "")).strip().lower()
            for provider_row in item.get("providers", [])
            if isinstance(provider_row, dict) and str(provider_row.get("id", "")).strip()
        }
        provider_valid = not provider or provider in available_providers
        account_valid = not selected_account or selected_account in available_accounts
        host_ready = str(item.get("auth_state", "missing") or "missing") in {"ready", "optional"}
        validation_state = (
            "unbound"
            if not enabled
            else "provider_required"
            if available_providers and not provider
            else "provider_invalid"
            if not provider_valid
            else "account_invalid"
            if not account_valid
            else "host_auth_missing"
            if not host_ready
            else "ready"
        )
        validation_message = (
            "Workspace is not bound to this connector yet."
            if validation_state == "unbound"
            else "Choose a provider from the machine inventory before you save this binding."
            if validation_state == "provider_required"
            else f"Saved provider {provider} is not available on this machine."
            if validation_state == "provider_invalid"
            else f"Saved account {selected_account} is not available on this machine."
            if validation_state == "account_invalid"
            else str(item.get("auth_detail", "") or "Host auth is not ready for this connector.")
            if validation_state == "host_auth_missing"
            else "Workspace binding matches the current machine inventory."
        )
        item["binding"] = {
            "enabled": enabled,
            "inherited": inherited,
            "account_id": str(binding.get("account_id", "") or ""),
            "provider": provider,
            "action_allow": list(binding.get("action_allow", [])),
            "action_block": list(binding.get("action_block", [])),
            "endpoint_allow": list(binding.get("endpoint_allow", [])),
            "endpoint_block": list(binding.get("endpoint_block", [])),
            "note": str(binding.get("note", "") or ""),
        }
        item["history"] = history
        item.update(history)
        item["binding_validation"] = {
            "state": validation_state,
            "message": validation_message,
            "provider_valid": provider_valid,
            "account_valid": account_valid,
            "host_ready": host_ready,
        }
        rows.append(item)
    return rows


def get_workspace_connector_context(
    tool_name: str,
    workspace_name: str,
    *,
    metadata: dict[str, Any] | None = None,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    details = metadata if isinstance(metadata, dict) else {}
    connector_id = connector_id_for_tool(tool_name)
    if not connector_id:
        return {
            "connector_id": "",
            "action_id": "",
            "binding_enabled": True,
            "binding_inherited": True,
            "binding": {},
            "status": {},
            "account_id": "",
            "provider": "",
        }
    binding = resolve_workspace_connector_binding(workspace_name, connector_id, config_path=config_path)
    binding_enabled, inherited = _effective_binding_enabled(workspace_name, binding)
    explicit_account = str(details.get("account") or details.get("account_id") or "").strip().lower()
    explicit_provider = str(details.get("provider") or "").strip().lower()
    account_id = explicit_account or str(binding.get("account_id", "") or "").strip().lower()
    provider = explicit_provider or str(binding.get("provider", "") or "").strip().lower()
    status = connector_status(connector_id, provider=provider)
    return {
        "connector_id": connector_id,
        "action_id": connector_action_for_tool(tool_name),
        "binding_enabled": binding_enabled,
        "binding_inherited": inherited,
        "binding": binding,
        "status": status,
        "account_id": account_id,
        "provider": provider,
    }


def evaluate_workspace_connector_policy(
    tool_name: str,
    workspace_name: str,
    *,
    metadata: dict[str, Any] | None = None,
    endpoint: str = "",
    config_path: str | Path | None = None,
) -> tuple[bool, str, dict[str, Any]]:
    context = get_workspace_connector_context(tool_name, workspace_name, metadata=metadata, config_path=config_path)
    connector_id = str(context.get("connector_id", "") or "")
    if not connector_id:
        return True, "", context

    binding = context.get("binding", {}) if isinstance(context.get("binding"), dict) else {}
    status = context.get("status", {}) if isinstance(context.get("status"), dict) else {}
    action_id = str(context.get("action_id", "default") or "default")
    account_id = str(context.get("account_id", "") or "")
    provider = str(context.get("provider", "") or "")
    normalized_endpoint = str(endpoint or "").strip().lower()
    binding_enabled = bool(context.get("binding_enabled", False))

    if not binding_enabled:
        return False, f"Workspace {workspace_name} is not bound to connector {connector_id}", {
            **context,
            "reason_code": "connector_unbound",
        }

    action_allow = [str(item) for item in binding.get("action_allow", []) if str(item).strip()]
    action_block = [str(item) for item in binding.get("action_block", []) if str(item).strip()]
    if action_allow and action_id not in action_allow:
        return False, f"Connector action {action_id} is outside the workspace action allow list for {connector_id}", {
            **context,
            "reason_code": "connector_action_blocked",
        }
    if action_id in action_block:
        return False, f"Connector action {action_id} is blocked for {connector_id} in workspace {workspace_name}", {
            **context,
            "reason_code": "connector_action_blocked",
        }

    endpoint_block = [str(item) for item in binding.get("endpoint_block", []) if str(item).strip()]
    endpoint_allow = [str(item) for item in binding.get("endpoint_allow", []) if str(item).strip()]

    def _matches_endpoint_pattern(value: str, pattern: str) -> bool:
        candidate = str(pattern or "").strip().lower()
        if not candidate:
            return False
        if any(token in candidate for token in ("*", "?", "[")):
            return fnmatchcase(value, candidate)
        return value.startswith(candidate)

    if normalized_endpoint and endpoint_block and any(_matches_endpoint_pattern(normalized_endpoint, pattern) for pattern in endpoint_block):
        return False, f"Connector endpoint {normalized_endpoint} is blocked for {connector_id} in workspace {workspace_name}", {
            **context,
            "reason_code": "endpoint_block",
        }
    if normalized_endpoint and endpoint_allow:
        matches_allow = any(_matches_endpoint_pattern(normalized_endpoint, pattern) for pattern in endpoint_allow)
        if not matches_allow:
            return False, f"Connector endpoint {normalized_endpoint} is outside the workspace connector filters for {connector_id}", {
                **context,
                "reason_code": "endpoint_allow",
            }

    available_accounts = {
        str(item.get("id", "")).strip().lower()
        for item in status.get("accounts", [])
        if isinstance(item, dict) and str(item.get("id", "")).strip()
    }
    if account_id and available_accounts and account_id not in available_accounts:
        return False, f"Connector account {account_id} is not available for {connector_id} on this host", {
            **context,
            "reason_code": "connector_account_unavailable",
        }

    available_providers = {
        str(item.get("id", "")).strip().lower()
        for item in status.get("providers", [])
        if isinstance(item, dict) and str(item.get("id", "")).strip()
    }
    if available_providers and not provider:
        return False, f"Connector {connector_id} requires an explicit provider selection for workspace {workspace_name}", {
            **context,
            "reason_code": "connector_provider_unconfigured",
        }
    if provider and available_providers and provider not in available_providers:
        return False, f"Connector provider {provider} is not configured for {connector_id}", {
            **context,
            "reason_code": "connector_provider_unconfigured",
        }

    auth_state = str(status.get("auth_state", "missing") or "missing")
    if auth_state == "missing":
        return False, f"Connector {connector_id} host auth is not ready: {str(status.get('auth_detail', '') or 'missing credentials')}", {
            **context,
            "reason_code": "connector_host_auth_missing",
        }

    return True, "", {**context, "reason_code": ""}


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
    state = _load_state()
    connectors = state.get("connectors", {}) if isinstance(state.get("connectors"), dict) else {}
    previous = connectors.get(connector_id, {}) if isinstance(connectors.get(connector_id), dict) else {}
    status_payload = status if isinstance(status, dict) else {}
    selected_provider = str(provider or "").strip().lower()
    selected_provider_row = _selected_provider_row(status_payload, provider=selected_provider)
    guidance_payload = guidance if isinstance(guidance, dict) else _connector_guidance(
        status_payload,
        provider=provider,
        account_id=account_id,
    )
    event_id = _new_event_id(f"{connector_id}-{action}")
    action_record = {
        "event_id": event_id,
        "integration_event": f"connector.{action}",
        "action": action,
        "connector": connector_id,
        "provider": selected_provider,
        "account_id": str(account_id or "").strip().lower(),
        "secret_key": str(secret_key or "").strip(),
        "ok": bool(ok),
        "summary": summary,
        "at": _now_iso(),
        "auth_state": str(status_payload.get("auth_state", "") or ""),
        "auth_detail": str(status_payload.get("auth_detail", "") or ""),
        "missing_fields": list(selected_provider_row.get("missing_fields", [])) if isinstance(selected_provider_row, dict) else [],
        "result_code": str(guidance_payload.get("result_code", "") or ""),
        "next_step": str(guidance_payload.get("next_step", "") or ""),
        "fix_target": str(guidance_payload.get("fix_target", "") or ""),
        "provider_auth_state": str(selected_provider_row.get("auth_state", "") or ""),
        "verify_check_summary": str(selected_provider_row.get("verify_check_summary", "") or ""),
    }
    recent_events = previous.get("recent_events", [])
    if not isinstance(recent_events, list):
        recent_events = []
    recent_events = [item for item in recent_events if isinstance(item, dict)][-4:] + [action_record]
    next_payload = {
        **previous,
        "last_action": action,
        "last_action_at": str(action_record.get("at", "") or ""),
        "last_action_ok": bool(ok),
        "last_result": summary,
        "last_event_id": event_id,
        "last_action_record": action_record,
        "recent_events": recent_events,
        "last_verify_ok": bool(ok) if action == "verify" else bool(previous.get("last_verify_ok", False)),
        "last_verified_at": str(action_record.get("at", "") or "") if action == "verify" else str(previous.get("last_verified_at", "") or ""),
        "last_verify_summary": summary if action == "verify" else str(previous.get("last_verify_summary", "") or ""),
        "last_verify_event_id": event_id if action == "verify" else str(previous.get("last_verify_event_id", "") or ""),
        "last_verify_record": action_record if action == "verify" else previous.get("last_verify_record", {}),
    }
    connectors[connector_id] = next_payload
    state["connectors"] = connectors
    _save_state(state)
    _log_integration_event(
        f"connector.{action}",
        {
            "event_id": event_id,
            "connector": connector_id,
            "action": action,
            "provider": selected_provider,
            "account_id": str(account_id or "").strip().lower(),
            "secret_key": str(secret_key or "").strip(),
            "auth_state": str(status_payload.get("auth_state", "") or ""),
            "ok": ok,
            "summary": summary,
            "result_code": str(guidance_payload.get("result_code", "") or ""),
            "next_step": str(guidance_payload.get("next_step", "") or ""),
            "fix_target": str(guidance_payload.get("fix_target", "") or ""),
            "provider_auth_state": str(selected_provider_row.get("auth_state", "") or ""),
            "verify_check_summary": str(selected_provider_row.get("verify_check_summary", "") or ""),
        },
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
    status_payload = status if isinstance(status, dict) else {}
    guidance = _connector_guidance(status_payload, provider=provider, account_id=account_id)
    _record_action_result(
        connector_id,
        action,
        ok=ok,
        summary=summary,
        provider=provider,
        account_id=account_id,
        secret_key=secret_key,
        status=status_payload,
        guidance=guidance,
    )
    history = _history_payload(connector_id)
    last_action_record = history.get("last_action_record", {}) if isinstance(history.get("last_action_record"), dict) else {}
    return {
        "ok": ok,
        "summary": summary,
        "status": status_payload,
        "history": history,
        "event_id": str(last_action_record.get("event_id", history.get("last_event_id", "")) or ""),
        "result_code": str(guidance.get("result_code", "") or ""),
        "next_step": str(guidance.get("next_step", "") or ""),
        "fix_target": str(guidance.get("fix_target", "") or ""),
    }


def run_connector_action(
    connector_id: str,
    action: str,
    *,
    provider: str = "",
    account_id: str = "",
    secret_key: str = "",
    secret_value: str = "",
) -> dict[str, Any]:
    normalized_connector = str(connector_id or "").strip().lower()
    normalized_action = str(action or "").strip().lower()
    summary = ""
    ok = True

    if normalized_action == "verify":
        status = connector_status(normalized_connector, provider=provider)
        if normalized_connector in {"crm", "voip"} and str(provider or "").strip():
            selected_provider = _selected_provider_row(status, provider=str(provider or "").strip().lower())
            verify_summary = str(selected_provider.get("verify_summary", "") or "").strip()
            selected_state = str(selected_provider.get("auth_state", status.get("auth_state", "missing")) or status.get("auth_state", "missing"))
            detail = str(selected_provider.get("scope_detail", "") or selected_provider.get("auth_detail", "") or "").strip()
            summary = verify_summary or f"{status.get('label', normalized_connector)} verify: {selected_state}"
            if detail:
                summary += f" | {detail}"
            ok = selected_state in {"ready", "optional"}
        else:
            summary = f"{status.get('label', normalized_connector)} verify: {status.get('auth_state', 'unknown')} | {status.get('auth_detail', '')}"
            ok = str(status.get("auth_state", "missing")) in {"ready", "optional"}
        return _finalize_action_result(
            normalized_connector,
            normalized_action,
            ok=ok,
            summary=summary,
            provider=provider,
            account_id=account_id,
            secret_key=secret_key,
            status=status,
        )

    if normalized_connector in {"youtube", "crm", "voip"} and normalized_action == "connect":
        connector_status_payload = connector_status(normalized_connector, provider=provider)
        provider_rows = connector_status_payload.get("providers", []) if isinstance(connector_status_payload.get("providers"), list) else []
        selected_provider = _selected_provider_row(connector_status_payload, provider=str(provider or "").strip().lower())
        if provider_rows and not selected_provider:
            ok = False
            summary = f"{normalized_connector} connect requires choosing a provider first."
            status = connector_status(normalized_connector, provider=provider)
            return _finalize_action_result(
                normalized_connector,
                normalized_action,
                ok=ok,
                summary=summary,
                provider=provider,
                account_id=account_id,
                secret_key=secret_key,
                status=status,
            )
        required_fields = list(selected_provider.get("required_fields", [])) if isinstance(selected_provider, dict) else []
        next_field = selected_provider.get("next_field", {}) if isinstance(selected_provider.get("next_field"), dict) else {}
        resolved_secret_key = str(secret_key or "").strip()
        if not resolved_secret_key and isinstance(next_field, dict):
            resolved_secret_key = str(next_field.get("key", "") or "").strip()
        if not resolved_secret_key and len(required_fields) == 1:
            resolved_secret_key = str(required_fields[0] or "").strip()
        if not resolved_secret_key or not secret_value:
            ok = False
            missing_text = ", ".join(required_fields) or "a secret key and value"
            summary = f"{normalized_connector} connect requires {missing_text}."
        else:
            valid, validation_error = _validate_secret_value(resolved_secret_key, secret_value)
            if not valid:
                ok = False
                summary = validation_error
            else:
                stored = write_machine_secret(resolved_secret_key, secret_value)
                ok = bool(stored)
                refreshed = connector_status(normalized_connector, provider=provider)
                refreshed_provider = next(
                    (
                        row for row in refreshed.get("providers", [])
                        if isinstance(row, dict) and str(row.get("id", "")).strip().lower() == str(provider or "").strip().lower()
                    ),
                    {},
                )
                remaining = list(refreshed_provider.get("missing_fields", [])) if isinstance(refreshed_provider, dict) else []
                field_meta = _secret_field_meta(resolved_secret_key)
                field_label = str(field_meta.get("label", resolved_secret_key) or resolved_secret_key)
                provider_label = str(refreshed_provider.get("label", provider or normalized_connector) or provider or normalized_connector)
                if stored:
                    summary = f"Saved {field_label} for {provider_label}."
                    if remaining:
                        next_label = str(_secret_field_meta(remaining[0]).get("label", remaining[0]) or remaining[0])
                        summary += f" Next required field: {next_label}."
                    else:
                        summary += " All required fields are present; run verify to confirm readiness."
                else:
                    summary = f"Could not persist {field_label} for {provider_label}; environment fallback remains unchanged."
        status = connector_status(normalized_connector, provider=provider)
        return _finalize_action_result(
            normalized_connector,
            normalized_action,
            ok=ok,
            summary=summary,
            provider=provider,
            account_id=account_id,
            secret_key=resolved_secret_key,
            status=status,
        )

    if normalized_connector in {"youtube", "crm", "voip"} and normalized_action == "disconnect":
        connector_status_payload = connector_status(normalized_connector, provider=provider)
        selected_provider = _selected_provider_row(connector_status_payload, provider=str(provider or "").strip().lower())
        required_fields = list(selected_provider.get("required_fields", [])) if isinstance(selected_provider, dict) else []
        keys_to_clear = [str(secret_key).strip()] if str(secret_key or "").strip() else [str(item) for item in required_fields if str(item).strip()]
        if not keys_to_clear:
            ok = False
            summary = f"{normalized_connector} disconnect requires a provider secret to clear."
        else:
            cleared_any = False
            still_present: list[str] = []
            for item in keys_to_clear:
                cleared_any = clear_machine_secret(item) or cleared_any
                if os.environ.get(item, "").strip():
                    still_present.append(item)
            summary = (
                f"Cleared {len(keys_to_clear)} stored secret(s) for {normalized_connector}."
                if cleared_any and not still_present
                else f"Cleared {len(keys_to_clear)} stored secret(s) for {normalized_connector}, but env values are still present for {', '.join(still_present)}."
                if cleared_any and still_present
                else f"No stored secrets were cleared for {normalized_connector}."
            )
        status = connector_status(normalized_connector, provider=provider)
        return _finalize_action_result(
            normalized_connector,
            normalized_action,
            ok=ok,
            summary=summary,
            provider=provider,
            account_id=account_id,
            secret_key=secret_key,
            status=status,
        )

    try:
        if normalized_connector == "gmail":
            from src.guppy.tools.media import gmail_unread_count
            target_account = str(account_id or "main").strip().lower() or "main"
            if normalized_action == "disconnect":
                token_path = _token_path_for_gmail_account(target_account)
                if token_path.exists():
                    token_path.unlink()
                    summary = f"Removed cached Gmail token for account {target_account}."
                else:
                    summary = f"No cached Gmail token found for account {target_account}."
            else:
                if normalized_action == "reconnect":
                    token_path = _token_path_for_gmail_account(target_account)
                    if token_path.exists():
                        token_path.unlink()
                count, err = gmail_unread_count(target_account)
                summary = err or f"Gmail account {target_account} verified with {count} unread message(s)."
                ok = not bool(err)
        elif normalized_connector == "calendar":
            from src.guppy.tools.media import calendar_events
            token_path = Path.home() / ".guppy_calendar_token.json"
            if normalized_action == "disconnect":
                if token_path.exists():
                    token_path.unlink()
                    summary = "Removed cached Calendar token."
                else:
                    summary = "No cached Calendar token found."
            else:
                if normalized_action == "reconnect" and token_path.exists():
                    token_path.unlink()
                result = calendar_events(days=1, max_results=1, calendar_id="primary")
                summary = result.splitlines()[0] if result else "Calendar connect completed."
                lowered = summary.lower()
                ok = not any(token in lowered for token in ("error", "failed", "missing", "not found"))
        elif normalized_connector == "spotify":
            from src.guppy.tools.media import spotify_current
            token_path = Path.home() / ".guppy_spotify_token"
            if normalized_action == "disconnect":
                if token_path.exists():
                    token_path.unlink()
                    summary = "Removed cached Spotify token."
                else:
                    summary = "No cached Spotify token found."
            else:
                if normalized_action == "reconnect" and token_path.exists():
                    token_path.unlink()
                result = spotify_current()
                summary = result.splitlines()[0] if result else "Spotify connect completed."
                lowered = summary.lower()
                ok = not any(token in lowered for token in ("requires spotify api", "error", "failed", "missing", "not found"))
        else:
            ok = False
            summary = f"Action {normalized_action} is not supported for connector {normalized_connector}."
    except Exception as exc:
        ok = False
        summary = f"{normalized_connector} {normalized_action} failed: {exc}"

    status = connector_status(normalized_connector, provider=provider)
    return _finalize_action_result(
        normalized_connector,
        normalized_action,
        ok=ok,
        summary=summary,
        provider=provider,
        account_id=account_id,
        secret_key=secret_key,
        status=status,
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
    signature = "|".join(
        [
            str(connector_id or "").strip().lower(),
            str(workspace_name or "").strip().lower(),
            str(reason_code or "").strip().lower(),
            str(reason or "").strip(),
        ]
    )
    now = time.monotonic()
    previous = _RECENT_POLICY_DENIALS.get(signature, 0.0)
    if previous and (now - previous) < _POLICY_DENIAL_DEDUPE_TTL_S:
        return
    _RECENT_POLICY_DENIALS[signature] = now
    _log_integration_event(
        "connector.policy_denied",
        {
            "connector": str(connector_id or "").strip().lower(),
            "workspace": str(workspace_name or "").strip(),
            "reason_code": str(reason_code or "").strip(),
            "reason": str(reason or "").strip(),
        },
        level="warning",
    )
