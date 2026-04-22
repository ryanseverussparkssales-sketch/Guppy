"""Pure helpers for building typed workspace and connector seams."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .contracts import (
    ConnectorActionRequest,
    ConnectorActionResult,
    ConnectorInventoryItem,
    WorkspaceGovernanceSnapshot,
    WorkspaceSummary,
)
from .connector_metadata import connector_spec


def build_workspace_summary(payload: Mapping[str, Any] | None) -> WorkspaceSummary:
    return WorkspaceSummary.from_mapping(payload)


def _normalize_inventory_row(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    connector_id = str(data.get("id") or data.get("connector") or data.get("connector_id") or "").strip().lower()
    spec = connector_spec(connector_id)
    if not spec:
        return data
    data.setdefault("id", connector_id)
    data.setdefault("label", str(spec.get("label", connector_id.replace("_", " ").title()) or connector_id.replace("_", " ").title()))
    data.setdefault("auth_kind", str(spec.get("auth_kind", "") or ""))
    if not isinstance(data.get("supported_actions"), (list, tuple, set)):
        data["supported_actions"] = list(spec.get("actions_supported", ()))
    if not isinstance(data.get("secret_fields"), (list, tuple, set)):
        data["secret_fields"] = list(spec.get("secret_fields", ()))

    availability_status = str(data.get("availability_status") or spec.get("availability_status") or "available").strip().lower()
    installation_status = str(data.get("installation_status") or spec.get("installation_status") or "installed").strip().lower()
    data["availability_status"] = availability_status
    data["installation_status"] = installation_status

    auth_state = str(data.get("auth_state", "") or "").strip().lower()
    default_auth_state = str(spec.get("default_auth_state", "") or "").strip().lower()
    synthesize_planned = availability_status == "planned" and installation_status == "not_installed" and auth_state in {
        "",
        "unknown",
        "missing",
    }
    if synthesize_planned:
        auth_state = default_auth_state or "planned"
        data["auth_state"] = auth_state
    elif default_auth_state and auth_state in {"", "unknown"}:
        auth_state = default_auth_state
        data["auth_state"] = auth_state

    if auth_state == "planned":
        data["enabled"] = bool(data.get("enabled", False))
        if not str(data.get("auth_detail", "") or "").strip():
            data["auth_detail"] = str(spec.get("default_auth_detail", "") or "").strip()
        if not str(data.get("summary", data.get("setup_summary", "")) or "").strip():
            data["summary"] = str(spec.get("default_summary", "") or "").strip()
        if not str(data.get("note", "") or "").strip():
            data["note"] = str(spec.get("default_note", "") or "").strip()
        if not str(data.get("result_code", "") or "").strip():
            data["result_code"] = str(spec.get("default_result_code", "planned_not_installed") or "planned_not_installed")
        if not str(data.get("next_step", "") or "").strip():
            data["next_step"] = str(spec.get("default_next_step", "") or "").strip()
        if not str(data.get("fix_target", "") or "").strip():
            data["fix_target"] = str(spec.get("default_fix_target", "") or "").strip()

    return data


def build_connector_inventory(payload: Iterable[Mapping[str, Any]] | None) -> tuple[ConnectorInventoryItem, ...]:
    if payload is None:
        return ()
    return tuple(ConnectorInventoryItem.from_mapping(_normalize_inventory_row(item)) for item in payload)


def build_connector_action_request(
    connector_id: str,
    action: str,
    *,
    provider: str = "",
    account_id: str = "",
    secret_key: str = "",
    secret_value: str = "",
    workspace_name: str = "",
) -> ConnectorActionRequest:
    return ConnectorActionRequest(
        connector_id=str(connector_id or "").strip().lower(),
        action=str(action or "").strip().lower(),
        provider=str(provider or "").strip().lower(),
        account_id=str(account_id or "").strip().lower(),
        secret_key=str(secret_key or "").strip(),
        secret_value=str(secret_value or "").strip(),
        workspace_name=str(workspace_name or "").strip(),
    )


def build_connector_action_result(payload: Mapping[str, Any] | None) -> ConnectorActionResult:
    return ConnectorActionResult.from_mapping(payload)


def _as_string_tuple(values: object) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple, set)):
        return ()
    return tuple(str(item).strip() for item in values if str(item).strip())


def summarize_connector_readiness(items: Iterable[ConnectorInventoryItem]) -> tuple[str, str]:
    rows = tuple(items)
    if not rows:
        return "UNKNOWN", "No connector inventory loaded."
    ready = sum(1 for item in rows if item.auth_state == "ready")
    partial = sum(1 for item in rows if item.auth_state == "partial")
    missing = sum(1 for item in rows if item.auth_state == "missing")
    planned = sum(1 for item in rows if item.auth_state == "planned")
    if ready == len(rows):
        state = "READY"
    elif planned == len(rows):
        state = "PLANNED"
    elif ready or partial or planned:
        state = "PARTIAL"
    elif missing == len(rows):
        state = "MISSING"
    else:
        state = "UNKNOWN"
    summary = f"{ready}/{len(rows)} ready, {partial} partial, {missing} missing"
    if planned:
        summary += f", {planned} planned."
    else:
        summary += "."
    return state, summary


def build_workspace_governance_snapshot(
    workspace_payload: Mapping[str, Any] | None,
    *,
    connectors_payload: Iterable[Mapping[str, Any]] | None = None,
    governance_payload: Mapping[str, Any] | None = None,
) -> WorkspaceGovernanceSnapshot:
    workspace = build_workspace_summary(workspace_payload)
    connectors = build_connector_inventory(connectors_payload)
    governance = dict(governance_payload) if isinstance(governance_payload, Mapping) else {}
    readiness_state, readiness_summary = summarize_connector_readiness(connectors)
    tool_allow = governance.get("tool_allow", ())
    tool_block = governance.get("tool_block", ())
    endpoint_allow = governance.get("endpoint_allow", ())
    endpoint_block = governance.get("endpoint_block", ())
    auth_mode = str(governance.get("auth_mode") or workspace.auth_mode).strip()
    policy_reason = str(governance.get("policy_reason") or governance.get("reason") or "").strip()
    policy_reason_code = str(governance.get("policy_reason_code") or governance.get("reason_code") or "").strip()
    policy_state = "blocked" if policy_reason else str(governance.get("policy_state") or "ready").strip().lower()
    operator_hint = str(governance.get("operator_hint") or governance.get("next_step") or "").strip()
    note = str(governance.get("note") or workspace.note).strip()
    return WorkspaceGovernanceSnapshot(
        workspace=workspace,
        connectors=connectors,
        policy_state=policy_state,
        readiness_state=readiness_state,
        readiness_summary=readiness_summary,
        policy_reason=policy_reason,
        policy_reason_code=policy_reason_code,
        auth_mode=auth_mode,
        tool_allow=_as_string_tuple(tool_allow),
        tool_block=_as_string_tuple(tool_block),
        endpoint_allow=_as_string_tuple(endpoint_allow),
        endpoint_block=_as_string_tuple(endpoint_block),
        operator_hint=operator_hint,
        note=note,
        metadata=governance,
    )
