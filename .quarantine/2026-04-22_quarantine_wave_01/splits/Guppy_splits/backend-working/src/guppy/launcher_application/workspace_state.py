"""Workspace snapshot helpers for the launcher application layer."""

from __future__ import annotations

from typing import Any


def enabled_workspace_names(snapshot: dict[str, Any] | None) -> list[str]:
    raw_snapshot = snapshot if isinstance(snapshot, dict) else {}
    names: list[str] = []
    for item in raw_snapshot.get("instances", []) if isinstance(raw_snapshot.get("instances", []), list) else []:
        if not isinstance(item, dict):
            continue
        if not bool(item.get("enabled", True)):
            continue
        name = str(item.get("name", "")).strip()
        if name and name not in names:
            names.append(name)
    return names


def resolve_active_instance_payload(
    snapshot: dict[str, Any] | None,
    active_name: str,
) -> dict[str, Any]:
    raw_snapshot = snapshot if isinstance(snapshot, dict) else {}
    items = raw_snapshot.get("instances", []) if isinstance(raw_snapshot.get("instances", []), list) else []
    active = str(active_name or "").strip()
    return next(
        (
            item
            for item in items
            if isinstance(item, dict) and str(item.get("name", "")).strip() == active
        ),
        {"name": active, "type": "user_instance"},
    )
