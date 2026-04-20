"""Helpers for shaping bounded connector/tool readiness copy for launcher cards."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from utils.connector_manager import workspace_tool_readiness


_POLICY_FIX_HINTS = {
    "connector_unbound": "Fix in Workspaces: bind this connector to the active workspace.",
    "connector_action_blocked": "Fix in Workspaces: adjust connector action allow/block policy.",
    "connector_account_unavailable": "Fix in Workspaces: choose a valid connector account for this machine.",
    "connector_provider_unconfigured": "Fix in Workspaces or App Mgmt: choose a valid provider and verify host config.",
    "connector_host_auth_missing": "Fix in App Mgmt: connect or verify the machine-level connector auth.",
    "endpoint_block": "Fix in Workspaces: loosen the connector endpoint block filter if this is intentional.",
    "endpoint_allow": "Fix in Workspaces: expand the connector endpoint allow filter if this is intentional.",
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
