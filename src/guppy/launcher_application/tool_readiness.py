"""Helpers for shaping bounded connector/tool readiness copy for launcher cards."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.guppy.workspace_governance.connector_metadata import connector_id_for_tool
from utils.connector_manager import workspace_tool_readiness


_POLICY_FIX_HINTS = {
    "connector_unbound": "Fix in Workspaces: bind this connector to the active workspace.",
    "connector_action_blocked": "Fix in Workspaces: adjust connector action allow/block policy.",
    "connector_account_unavailable": "Fix in App Mgmt: choose a valid connector account for this machine before you bind it in Workspaces.",
    "connector_provider_unconfigured": "Fix in App Mgmt: choose a valid provider and verify host config before you bind it in Workspaces.",
    "connector_host_auth_missing": "Fix in App Mgmt: connect or verify the machine-level connector auth.",
    "endpoint_block": "Fix in Workspaces: loosen the connector endpoint block filter if this is intentional.",
    "endpoint_allow": "Fix in Workspaces: expand the connector endpoint allow filter if this is intentional.",
}

_SETTINGS_OWNED_REASON_CODES = {
    "connector_account_unavailable",
    "connector_provider_unconfigured",
    "connector_host_auth_missing",
}


def read_workspace_tool_readiness(
    tool_name: str,
    workspace_name: str,
    *,
    metadata: dict[str, Any] | None = None,
    endpoint: str = "",
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    return workspace_tool_readiness(
        tool_name,
        workspace_name,
        metadata=metadata,
        endpoint=endpoint,
        config_path=config_path,
    )


def tool_policy_fix_hint(policy_reason_code: str, readiness_payload: Mapping[str, object] | None = None) -> str:
    hint = _POLICY_FIX_HINTS.get(str(policy_reason_code or "").strip().lower(), "")
    if hint:
        return hint
    readiness = readiness_payload if isinstance(readiness_payload, Mapping) else {}
    next_step = str(readiness.get("next_step", "") or "").strip()
    fix_target = str(readiness.get("fix_target", "") or "").strip()
    if next_step and fix_target:
        return f"{next_step} Fix in: {fix_target}."
    if next_step:
        return next_step
    return ""


def tool_readiness_summary(readiness_payload: Mapping[str, object] | None) -> str:
    readiness = readiness_payload if isinstance(readiness_payload, Mapping) else {}
    summary = str(readiness.get("summary", "") or "").strip()
    if summary:
        return summary
    label = str(readiness.get("label", "") or "").strip()
    if label:
        return "Evidence: " + label
    return "Evidence: no connector-specific readiness details are available."


def tool_readiness_debug_fields(readiness_payload: Mapping[str, object] | None) -> dict[str, Any]:
    readiness = readiness_payload if isinstance(readiness_payload, Mapping) else {}
    return {
        "readiness_state": str(readiness.get("state", "") or "").strip(),
        "readiness_label": str(readiness.get("label", "") or "").strip(),
        "readiness_summary": str(readiness.get("summary", "") or "").strip(),
        "readiness_history_summary": str(readiness.get("history_summary", "") or "").strip(),
        "readiness_result_code": str(readiness.get("result_code", "") or "").strip(),
        "readiness_next_step": str(readiness.get("next_step", "") or "").strip(),
        "readiness_fix_target": str(readiness.get("fix_target", "") or "").strip(),
        "readiness_auth_state": str(readiness.get("auth_state", "") or "").strip(),
        "readiness_auth_source": str(readiness.get("auth_source", "") or "").strip(),
    }


def tool_settings_route(
    tool_name: str,
    policy_reason_code: str,
    readiness_payload: Mapping[str, object] | None = None,
) -> dict[str, str]:
    """Return a Settings-owned remediation route for blocked connector tools.

    Tools may surface a bounded redirect into Settings > Device & Accounts when the
    blocked state is caused by machine auth, provider setup, or account inventory.
    Workspace-only binding/policy fixes intentionally stay textual because those are
    not Settings-owned remediation lanes.
    """

    connector_id = str(connector_id_for_tool(tool_name) or "").strip().lower()
    if not connector_id:
        return {}
    readiness = readiness_payload if isinstance(readiness_payload, Mapping) else {}
    normalized_code = str(policy_reason_code or "").strip().lower()
    fix_target = str(readiness.get("fix_target", "") or "").strip()
    next_step = str(readiness.get("next_step", "") or "").strip()
    fix_target_lower = fix_target.lower()
    is_settings_fix = (
        normalized_code in _SETTINGS_OWNED_REASON_CODES
        or "app mgmt" in fix_target_lower
        or fix_target_lower.startswith("settings")
    )
    if not is_settings_fix:
        return {}
    note = next_step or _POLICY_FIX_HINTS.get(normalized_code, "")
    if note and "settings" not in note.lower() and "app mgmt" not in note.lower():
        note = f"{note} Open Settings > Device & Accounts to continue."
    return {
        "connector": connector_id,
        "tool": str(tool_name or "").strip().lower(),
        "destination": "settings_device_accounts",
        "button_label": "OPEN APP MGMT",
        "destination_label": "Settings > Device & Accounts",
        "note": note,
        "fix_target": fix_target,
    }
