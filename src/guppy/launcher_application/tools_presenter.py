"""Pure presenter helpers for the launcher Tools surface."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from src.guppy.launcher_application.tool_action_registry import get_action_for_tool
from src.guppy.workspace_governance import connector_catalog


@dataclass(frozen=True, slots=True)
class ToolsSurfaceState:
    available_now: int
    setup_first: int
    restricted_here: int
    summary_line: str
    ownership_line: str
    planning_line: str
    guidance_line: str


def _tool_bucket(tool_key: str, state: str, *, dry_run: bool) -> str:
    normalized_state = str(state or "").strip().lower()
    if normalized_state == "restricted":
        return "restricted"
    if dry_run:
        return "setup_first"
    return "available_now"


def build_tools_surface_state(
    tool_rows: Iterable[Mapping[str, object]],
    tool_states: Mapping[str, str] | None,
) -> ToolsSurfaceState:
    states = dict(tool_states) if isinstance(tool_states, Mapping) else {}
    available_now = 0
    setup_first = 0
    restricted_here = 0
    connector_ready_now = 0

    for row in tool_rows:
        tool_key = str(row.get("key", "") or "").strip().lower()
        if not tool_key:
            continue
        entry = get_action_for_tool(tool_key)
        dry_run = entry.dry_run if entry is not None else bool(row.get("dry_run", False))
        category = entry.category if entry is not None else str(row.get("category", "") or "").strip().upper()
        bucket = _tool_bucket(tool_key, states.get(tool_key, "unknown"), dry_run=dry_run)
        if bucket == "restricted":
            restricted_here += 1
        elif bucket == "setup_first":
            setup_first += 1
        else:
            available_now += 1
            if category == "CONNECTOR":
                connector_ready_now += 1

    planned_labels = [
        str(spec.get("label", connector_id.replace("_", " ").title()) or connector_id.replace("_", " ").title())
        for connector_id, spec in connector_catalog().items()
        if str(spec.get("availability_status", "") or "").strip().lower() == "planned"
    ]
    planned_text = ", ".join(planned_labels)
    planning_line = (
        f"Planned adapter lanes: {planned_text}. They stay in Models until a real local adapter ships."
        if planned_text
        else "No planned adapter lanes are reserved in this build."
    )
    guidance_line = (
        f"{connector_ready_now} connector tools are usable right now."
        if connector_ready_now
        else "Connector actions depend on workspace binding plus machine sign-in readiness."
    )
    if setup_first:
        guidance_line += " Setup-first cards can be primed from Home, but they still need approval or setup before real execution."
    return ToolsSurfaceState(
        available_now=available_now,
        setup_first=setup_first,
        restricted_here=restricted_here,
        summary_line=(
            f"Available now: {available_now} | Set up first: {setup_first} | Restricted here: {restricted_here}"
        ),
        ownership_line=(
            "Settings connects accounts. Workspaces decides bindings. Tools runs the action for the active workspace."
        ),
        planning_line=planning_line,
        guidance_line=guidance_line,
    )


__all__ = ["ToolsSurfaceState", "build_tools_surface_state"]
