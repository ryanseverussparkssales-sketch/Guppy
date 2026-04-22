"""Onboarding presenter for guided connector setup (PL-C4).

Reads from provider_registry and connector_manager to surface
per-provider connection status, next steps, and summary copy.

No Qt dependency — pure data layer, safe to unit-test headlessly.
"""

from __future__ import annotations

from typing import Any

from src.guppy.launcher_application.provider_registry import (
    ProviderEntry,
    get_next_step,
    list_providers,
)


def _is_connected(connector_status: dict[str, Any]) -> bool:
    """Return True when the connector reports a ready or optional auth state."""
    state = str(connector_status.get("auth_state", "") or "").strip().lower()
    return state in {"ready", "optional"}


def get_onboarding_checklist(
    connector_inventory: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return per-provider onboarding status rows.

    Each row contains:
      id, label, description, is_connected, next_step, verify_supported
    """
    status_by_id: dict[str, dict[str, Any]] = {
        str(item.get("id", "") or "").strip().lower(): item
        for item in connector_inventory
        if isinstance(item, dict)
    }
    rows: list[dict[str, Any]] = []
    for entry in list_providers():
        status = status_by_id.get(entry.id, {})
        connected = _is_connected(status)
        rows.append(
            {
                "id": entry.id,
                "label": entry.label,
                "description": entry.description,
                "is_connected": connected,
                "next_step": get_next_step(entry.id, is_connected=connected),
                "verify_supported": entry.verify_supported,
            }
        )
    return rows


def get_first_unconfigured_provider(
    connector_inventory: list[dict[str, Any]],
) -> ProviderEntry | None:
    """Return the first provider that is not yet connected, or None."""
    status_by_id: dict[str, dict[str, Any]] = {
        str(item.get("id", "") or "").strip().lower(): item
        for item in connector_inventory
        if isinstance(item, dict)
    }
    for entry in list_providers():
        status = status_by_id.get(entry.id, {})
        if not _is_connected(status):
            return entry
    return None


def get_onboarding_summary(connector_inventory: list[dict[str, Any]]) -> str:
    """Return plain-language copy like 'You have 2 of 6 providers connected.'"""
    checklist = get_onboarding_checklist(connector_inventory)
    total = len(checklist)
    connected = sum(1 for row in checklist if row["is_connected"])
    if total == 0:
        return "No providers are registered yet."
    if connected == 0:
        return f"None of your {total} providers are connected yet — connect one to get started."
    if connected == total:
        return f"All {total} providers are connected. Guppy is fully set up."
    return f"You have {connected} of {total} providers connected."
