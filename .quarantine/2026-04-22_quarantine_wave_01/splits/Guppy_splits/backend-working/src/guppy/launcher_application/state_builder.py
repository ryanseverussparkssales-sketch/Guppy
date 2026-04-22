"""State-building helpers for the launcher application layer."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from src.guppy.runtime_application.contracts import RuntimeHealthSnapshot
from src.guppy.workspace_governance import ConnectorInventoryItem, build_workspace_summary

from .contracts import LauncherStateSnapshot
from .windows_ops import build_windows_ops_plan_payload


def build_launcher_state_snapshot(
    snapshot: dict[str, Any] | None,
    connector_inventory: Iterable[ConnectorInventoryItem] | None,
    windows_snapshot: dict[str, str] | None,
    *,
    active_view: str = "home",
    runtime_health: RuntimeHealthSnapshot | Mapping[str, Any] | None = None,
) -> LauncherStateSnapshot:
    raw_snapshot = snapshot if isinstance(snapshot, dict) else {}
    raw_windows = windows_snapshot if isinstance(windows_snapshot, dict) else {}
    items = raw_snapshot.get("instances", []) if isinstance(raw_snapshot.get("instances", []), list) else []
    active_name = str(raw_snapshot.get("active_instance", "") or "").strip()

    workspaces = tuple(
        build_workspace_summary(
            {
                **item,
                "instance_type": str(item.get("type", item.get("instance_type", "")) or ""),
                "status": "active" if str(item.get("name", "")).strip() == active_name else "ready",
                "active": str(item.get("name", "")).strip() == active_name,
            }
        )
        for item in items
        if isinstance(item, dict) and bool(item.get("enabled", True))
    )
    active_workspace = next((item for item in workspaces if item.active), None)
    typed_runtime_health = (
        runtime_health
        if isinstance(runtime_health, RuntimeHealthSnapshot)
        else RuntimeHealthSnapshot.from_mapping(runtime_health)
        if isinstance(runtime_health, Mapping)
        else RuntimeHealthSnapshot.from_mapping(
            {
                "startup_readiness": {
                    "overall": "READY" if str(raw_windows.get("service", "")).strip() else "UNKNOWN",
                    "checks": {},
                },
                "local_runtime": {},
                "voice_status": {},
                "daemon_available": True,
            }
        )
        if raw_windows
        else None
    )
    return LauncherStateSnapshot(
        active_view=active_view,
        active_workspace=active_workspace,
        workspaces=workspaces,
        runtime_health=typed_runtime_health,
        connector_inventory=tuple(connector_inventory or ()),
        app_management_status=dict(raw_windows),
        status_message=str(raw_windows.get("service", "") or "").strip(),
    )


def build_windows_ops_plan(action: str) -> dict[str, object]:
    return build_windows_ops_plan_payload(action)
