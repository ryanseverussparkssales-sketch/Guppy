"""Typed launcher-facing state contracts.

These dataclasses are intentionally light-weight so the launcher can move
incrementally from dict-shaped state to explicit contracts without forcing
immediate UI rewrites.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..runtime_application.contracts import RuntimeHealthSnapshot, StartupReadinessSnapshot
from ..workspace_governance.contracts import (
    ConnectorInventoryItem,
    WorkspaceGovernanceSnapshot,
    WorkspaceSummary,
)


class LauncherIntent(StrEnum):
    """Named launcher actions emitted by views and handled by app services."""

    REFRESH_STATE = "refresh_state"
    SELECT_WORKSPACE = "select_workspace"
    REFRESH_RUNTIME = "refresh_runtime"
    REFRESH_STARTUP_READINESS = "refresh_startup_readiness"
    REFRESH_CONNECTORS = "refresh_connectors"
    APPLY_WORKSPACE_GOVERNANCE = "apply_workspace_governance"
    LOAD_WORKFLOW = "load_workflow"
    RUN_WORKFLOW = "run_workflow"
    RUN_WINDOWS_VERIFY = "run_windows_verify"
    RUN_WINDOWS_UPDATE = "run_windows_update"
    RUN_WINDOWS_PACKAGE = "run_windows_package"
    RUN_WINDOWS_RELEASE_DRY_RUN = "run_windows_release_dry_run"
    VERIFY_CONNECTOR = "verify_connector"
    CONNECT_CONNECTOR = "connect_connector"
    RECONNECT_CONNECTOR = "reconnect_connector"
    DISCONNECT_CONNECTOR = "disconnect_connector"
    SAVE_CONNECTOR_SECRET = "save_connector_secret"
    CLEAR_CONNECTOR_SECRET = "clear_connector_secret"


@dataclass(slots=True)
class LauncherStateSnapshot:
    """Canonical launcher state shared across the major surfaces."""

    active_view: str = "home"
    active_workspace: WorkspaceSummary | None = None
    workspaces: tuple[WorkspaceSummary, ...] = ()
    workspace_governance: WorkspaceGovernanceSnapshot | None = None
    runtime_health: RuntimeHealthSnapshot | None = None
    startup_readiness: StartupReadinessSnapshot | None = None
    connector_inventory: tuple[ConnectorInventoryItem, ...] = ()
    models_status: dict[str, Any] = field(default_factory=dict)
    voices_status: dict[str, Any] = field(default_factory=dict)
    app_management_status: dict[str, Any] = field(default_factory=dict)
    status_message: str = ""
    busy: bool = False
    last_error: str = ""

    @classmethod
    def empty(cls) -> "LauncherStateSnapshot":
        return cls()

    @property
    def workspace_name(self) -> str:
        return self.active_workspace.name if self.active_workspace else ""

    @property
    def overall_runtime_state(self) -> str:
        if self.runtime_health is not None:
            return self.runtime_health.overall
        if self.startup_readiness is not None:
            return self.startup_readiness.overall
        return "UNKNOWN"
