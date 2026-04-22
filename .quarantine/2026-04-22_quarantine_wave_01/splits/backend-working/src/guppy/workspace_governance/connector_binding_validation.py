"""Validation helpers for workspace connector binding API payloads."""

from __future__ import annotations

from typing import Any

from src.guppy.api._server_fragment_models import InstanceConnectorBindingRequest
from src.guppy.workspace_governance.connector_metadata import (
    list_connector_ids,
    provider_metadata,
    provider_spec,
)


def _normalize_token_list(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for raw in values or []:
        token = str(raw or "").strip().lower()
        if not token or token in seen:
            continue
        seen.add(token)
        deduped.append(token)
    return deduped


def validate_connector_binding_request(
    connector_id: str,
    request: InstanceConnectorBindingRequest,
) -> tuple[str | None, dict[str, Any]]:
    normalized_connector = str(connector_id or "").strip().lower()
    if normalized_connector not in set(list_connector_ids()):
        return (f"unknown connector: {normalized_connector}", {})

    normalized_provider = str(request.provider or "").strip().lower()
    providers = provider_metadata(normalized_connector)
    if providers and normalized_provider and normalized_provider not in providers:
        return (
            f"unknown provider '{normalized_provider}' for connector '{normalized_connector}'",
            {},
        )

    action_allow = _normalize_token_list(request.action_allow)
    action_block = _normalize_token_list(request.action_block)
    overlap = sorted(set(action_allow).intersection(action_block))
    if overlap:
        return (f"action_allow and action_block overlap: {', '.join(overlap)}", {})

    supported_actions: set[str] = set()
    if providers:
        if normalized_provider:
            supported_actions.update(
                str(action or "").strip().lower()
                for action in provider_spec(normalized_connector, normalized_provider).get("actions", [])
            )
        else:
            for provider_id in providers:
                supported_actions.update(
                    str(action or "").strip().lower()
                    for action in provider_spec(normalized_connector, provider_id).get("actions", [])
                )
    if supported_actions:
        invalid_actions = sorted(
            action for action in (set(action_allow) | set(action_block)) if action not in supported_actions
        )
        if invalid_actions:
            return (
                "unsupported connector actions: " + ", ".join(invalid_actions),
                {},
            )

    endpoint_allow = [str(item or "").strip() for item in request.endpoint_allow or []]
    endpoint_block = [str(item or "").strip() for item in request.endpoint_block or []]
    if any(not item for item in endpoint_allow + endpoint_block):
        return ("endpoint filters cannot contain empty values", {})

    payload = {
        "enabled": bool(request.enabled),
        "account_id": str(request.account_id or "").strip(),
        "provider": normalized_provider,
        "action_allow": action_allow,
        "action_block": action_block,
        "endpoint_allow": endpoint_allow,
        "endpoint_block": endpoint_block,
        "note": str(request.note or "").strip(),
    }
    return (None, payload)
