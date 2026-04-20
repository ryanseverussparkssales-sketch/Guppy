from __future__ import annotations

import json
import os
import time
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
