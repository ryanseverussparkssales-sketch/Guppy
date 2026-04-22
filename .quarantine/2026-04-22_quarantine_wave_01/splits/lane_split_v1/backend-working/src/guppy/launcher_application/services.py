"""Launcher application services.

These helpers keep the live launcher importing through application seams
instead of reaching directly into lower-level governance modules.
"""

from __future__ import annotations

from typing import Any

from src.guppy.workspace_governance import (
    ConnectorActionRequest,
    ConnectorActionResult,
    ConnectorInventoryItem,
    build_connector_action_result,
    build_connector_inventory,
)

try:
    from utils.connector_manager import (
        connector_inventory as _connector_inventory,
        run_connector_action as _run_connector_action,
        save_workspace_connector_binding as _save_workspace_connector_binding,
        workspace_connector_inventory as _workspace_connector_inventory,
    )

    _CONNECTOR_BACKEND_AVAILABLE = True
except Exception:
    _CONNECTOR_BACKEND_AVAILABLE = False


def connector_backend_available() -> bool:
    return _CONNECTOR_BACKEND_AVAILABLE


def is_valid_repair_token(token: str) -> bool:
    """Return True if token is a non-empty lowercase-hex string no longer than 256 chars."""
    if not token or len(token) > 256:
        return False
    return all(ch in "0123456789abcdef" for ch in token.lower())


def fetch_connector_inventory() -> tuple[ConnectorInventoryItem, ...]:
    if not _CONNECTOR_BACKEND_AVAILABLE:
        return ()
    return build_connector_inventory(
        item
        for item in _connector_inventory()
        if isinstance(item, dict)
    )


def fetch_workspace_connector_inventory(workspace_name: str, *, config_path=None) -> list[dict[str, Any]]:
    if not _CONNECTOR_BACKEND_AVAILABLE:
        return []
    return [
        item
        for item in _workspace_connector_inventory(workspace_name, config_path=config_path)
        if isinstance(item, dict)
    ]


def save_workspace_connector_binding(
    workspace_name: str,
    connector_id: str,
    payload: dict[str, Any],
    *,
    config_path=None,
) -> None:
    if not _CONNECTOR_BACKEND_AVAILABLE:
        raise RuntimeError("connector manager unavailable")
    _save_workspace_connector_binding(workspace_name, connector_id, payload, config_path=config_path)


def execute_connector_action(request: ConnectorActionRequest) -> ConnectorActionResult:
    if not _CONNECTOR_BACKEND_AVAILABLE:
        return ConnectorActionResult(
            connector_id=request.connector_id,
            action=request.action,
            ok=False,
            summary="connector manager unavailable",
        )
    payload = _run_connector_action(
        request.connector_id,
        request.action,
        provider=request.provider,
        account_id=request.account_id,
        secret_key=request.secret_key,
        secret_value=request.secret_value,
    )
    result = build_connector_action_result(payload if isinstance(payload, dict) else {})
    if result.connector_id:
        return result
    return ConnectorActionResult(
        connector_id=request.connector_id,
        action=request.action,
        ok=result.ok,
        summary=result.summary,
        auth_state=result.auth_state,
        result_code=result.result_code,
        next_step=result.next_step,
        fix_target=result.fix_target,
        docs_hint=result.docs_hint,
        entry_point=result.entry_point,
        event_id=result.event_id,
        history=result.history,
        status=result.status,
    )
