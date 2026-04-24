"""Shell-side instance/workspace handler functions.

Each function takes *owner* (a ``LauncherWindow`` instance) as first argument
and delegates to the workspace instance workflow helpers, keeping the shell thin.
"""
from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QTimer

from src.guppy.launcher_application import (
    apply_workspace_instance_switch,
    bootstrap_workspace_instance_switcher,
    complete_bootstrap_workspace_instance_switcher,
    delete_workspace_instance,
    fetch_connector_inventory,
    load_workspace_instance_logs,
    refresh_workspace_instance_manager,
    save_instance_governance,
    save_workspace_instance,
    select_workspace_instance,
)
from src.guppy.launcher_application.storage_io import (
    instance_logger_backend_available,
    read_instance_log_tail,
    read_json_dict,
    write_json_atomic,
)
from src.guppy.workspace_governance import instance_policy_backend_available

_INSTANCE_GOVERNANCE_BACKEND = instance_policy_backend_available()
_INSTANCE_LOGGER_AVAILABLE = instance_logger_backend_available()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not write_json_atomic(path, payload):
        raise OSError(f"Atomic write failed for {path}")


# ── Instance switch ───────────────────────────────────────────────────────────

def apply_instance_switch(owner, target: str, *, announce: bool = True) -> None:
    apply_workspace_instance_switch(owner, target, announce=announce)


def bootstrap_instance_switcher(owner) -> None:
    bootstrap_workspace_instance_switcher(owner, schedule_single_shot=QTimer.singleShot)


def complete_bootstrap_instance_switcher(owner) -> None:
    complete_bootstrap_workspace_instance_switcher(
        owner,
        schedule_single_shot=QTimer.singleShot,
        monotonic=time.monotonic,
        fetch_connector_inventory=fetch_connector_inventory,
    )


def snapshot_active_instance_history(owner) -> None:
    if not owner._active_instance_name:
        return
    owner._instance_histories[owner._active_instance_name] = (
        owner._assistant_view.recent_history(limit=200)
    )


# ── Instance CRUD / lifecycle ─────────────────────────────────────────────────

def on_instance_selected(owner, name: str) -> None:
    select_workspace_instance(owner, name, read_json_dict=read_json_dict, write_json=_write_json)


def on_instance_manager_refresh(owner) -> None:
    refresh_workspace_instance_manager(owner)


def on_instance_create_requested(owner, payload: dict) -> None:
    save_workspace_instance(owner, payload)


def on_instance_governance_save_requested(owner, payload: dict) -> None:
    save_instance_governance(owner, payload, backend_available=_INSTANCE_GOVERNANCE_BACKEND)


def on_instance_delete_requested(owner, name: str) -> None:
    delete_workspace_instance(owner, name)


def on_instance_logs_requested(owner, name: str, quiet: bool = False) -> None:
    load_workspace_instance_logs(
        owner,
        name,
        quiet=quiet,
        local_log_reader=read_instance_log_tail if _INSTANCE_LOGGER_AVAILABLE else None,
    )
