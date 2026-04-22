from __future__ import annotations

import os
import sys
import time
from queue import Empty
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame

from src.guppy.launcher_application import (
    build_library_chat_submission,
    build_windows_ops_plan,
    refresh_workspace_instance_views,
    set_daily_activity,
    sync_right_tray,
    update_route_preview,
)
from src.guppy.launcher_application import launcher_connector_handlers as _conn_handlers
from src.guppy.launcher_application import launcher_instance_handlers as _inst_handlers
from src.guppy.launcher_application import launcher_library_handlers as _lib_handlers
from src.guppy.launcher_application import launcher_nav_handlers as _nav_handlers
from src.guppy.launcher_application.automation_test_coordination import (
    preferred_builder_workspace_name,
)
from src.guppy.launcher_application.automation_test_support import (
    display_repo_path,
)
from src.guppy.launcher_application.launcher_event_log import log_launcher_event as _log_launcher_event_fn
from src.guppy.launcher_application.launcher_command_policy import build_shell_model_loadout_summary
from src.guppy.launcher_application.launcher_shell_support import (
    QuickActionPlan,
    apply_quick_action_plan as _apply_quick_action_plan_fn,
)
from src.guppy.launcher_application.launcher_poll_orchestration import orchestrate_status_poll
from src.guppy.launcher_application.launcher_voice_strip import (
    build_sys_strip as _build_sys_strip_fn,
    update_sys_strip as _update_sys_strip_fn,
)
from src.guppy.launcher_application.recovery_coordination import (
    sync_recovery_outcome,
)
from src.guppy.launcher_application.storage_io import (
    instance_logger_backend_available,
    read_instance_log_tail,
    read_json_dict,
    read_jsonl_tail,
)
from src.guppy.launcher_application.tools_trace_adapter import LauncherToolsTraceAdapter
from src.guppy.launcher_application.workspace_snapshot_support import (
    build_local_instance_snapshot,
    fetch_connector_inventory_snapshot,
    fetch_instance_snapshot,
    load_instance_catalog,
    load_instance_history_from_logs,
)
from src.guppy.launcher_application.workspace_snapshot_support import (
    default_governance_snapshot,
    instance_state_path,
    instances_config_path,
)

from . import tokens as T

_INSTANCE_LOGGER_AVAILABLE = instance_logger_backend_available()
_PERSONALIZATION_BOOTSTRAP_AVAILABLE = False
_RUNTIME = Path(__file__).resolve().parent.parent.parent / "runtime"
_CONFIG = Path(__file__).resolve().parent.parent.parent / "config"


def _launcher_module():
    return (
        sys.modules.get("ui.launcher.launcher_window")
        or sys.modules.get("compat_shims.launcher_ui.ui.launcher.launcher_window")
    )


def _runtime_dir() -> Path:
    launcher_module = _launcher_module()
    runtime_dir = getattr(launcher_module, "_RUNTIME", _RUNTIME)
    return runtime_dir if isinstance(runtime_dir, Path) else Path(runtime_dir)


def _read_json_dict(path: Path) -> dict[str, object]:
    launcher_module = _launcher_module()
    read_json = getattr(launcher_module, "read_json_dict", read_json_dict)
    payload = read_json(path)
    return payload if isinstance(payload, dict) else {}


def wire_tools_trace_adapter(self) -> None:
    adapter = LauncherToolsTraceAdapter(
        _runtime_dir(),
        tool_state_path=self._tool_state_path(),
        live_tool_states_getter=self._tools_view.get_states,
        live_tool_statuses_getter=self._tools_view.current_tool_states,
    )
    self._tools_trace_adapter = adapter
    self._tools_view.trace_adapter = adapter
    self._tools_view.debug_backend = adapter
    self._tools_view.read_debug_snapshot = adapter.read_debug_snapshot
    self._tools_view.read_recent_tool_events = adapter.read_recent_tool_events
    self._tools_view.read_recent_launcher_events = adapter.read_recent_launcher_events
    refresh_tools_debug_surface(self)


def refresh_tools_debug_surface(self) -> None:
    refresh = getattr(self._tools_view, "refresh_debug_surface", None)
    if callable(refresh):
        refresh()


def drain_deferred_syslog(self) -> None:
    processed = 0
    while processed < self._MAX_DEFERRED_SYSLOG_PER_TICK:
        try:
            line = self._deferred_syslog.get_nowait()
        except Empty:
            break
        self._status_panel.append_syslog(line)
        processed += 1


def update_route_preview_method(self, text: str = "") -> None:
    update_route_preview(self, text)
    self._sync_topbar_model_context()


def set_daily_activity_method(self, text: str) -> None:
    set_daily_activity(self, text)


def sync_right_tray_method(self, active_payload: dict[str, object]) -> None:
    sync_right_tray(self, active_payload)


def build_sys_strip(self) -> QFrame:
    return _build_sys_strip_fn(self, tokens=T)


def update_sys_strip(self) -> None:
    start_time = getattr(self, "_launch_start_time", 0.0)
    _update_sys_strip_fn(self, runtime_path=_runtime_dir(), start_time=start_time, tokens=T)


def start_status_poll(self) -> None:
    self._status_poll_timer = QTimer(self)
    self._status_poll_timer.timeout.connect(self._poll_status)
    self._status_poll_timer.start(3000)
    QTimer.singleShot(0, self._poll_status)


def poll_status(self) -> None:
    start_time = getattr(self, "_launch_start_time", 0.0)
    orchestrate_status_poll(
        self,
        runtime_path=_runtime_dir(),
        personalization_available=_PERSONALIZATION_BOOTSTRAP_AVAILABLE,
        start_time=start_time,
    )


def sync_recovery_outcome_method(self) -> None:
    sync_recovery_outcome(self, runtime_path=_runtime_dir(), read_jsonl_tail=read_jsonl_tail)


def sync_shell_model_summary(self, *, active_model: str = "", runtime_backend: str = "") -> None:
    app_settings = _read_json_dict(_runtime_dir() / "app_settings.json")
    summary = build_shell_model_loadout_summary(
        active_model=active_model,
        runtime_backend=runtime_backend,
        settings_payload=app_settings,
        environment=dict(os.environ),
    )
    self._topbar.set_launcher_summary(summary)
    self._sync_topbar_model_context(main_model=active_model)


def on_tab_change(self, index: int) -> None:
    _nav_handlers.on_tab_change(self, index, runtime_path=_runtime_dir())


def apply_start_destination(self) -> None:
    _nav_handlers.apply_start_destination(self)


def set_status_panel_visible(self, visible: bool) -> None:
    _nav_handlers.set_status_panel_visible(self, visible)


def toggle_status_panel(self) -> None:
    _nav_handlers.toggle_status_panel(self)


def toggle_sidebar(self) -> None:
    _nav_handlers.toggle_sidebar(self)


def build_quick_action_plan(self, action: str) -> QuickActionPlan:
    return _nav_handlers.build_quick_action_plan_for_owner(self, action, runtime_parent=_runtime_dir().parent)


def apply_quick_action_plan(self, plan: QuickActionPlan) -> bool:
    return _apply_quick_action_plan_fn(self, plan)


def instances_config_path_method(self) -> Path:
    return instances_config_path(_CONFIG)


def instance_state_path_method(self) -> Path:
    return instance_state_path(_runtime_dir())


def default_governance_snapshot_static(instance_type: str) -> dict[str, object]:
    return default_governance_snapshot(instance_type)


def local_instance_snapshot(self, *, include_workspace_details: bool = True) -> dict:
    return build_local_instance_snapshot(
        config_path=self._instances_config_path(),
        state_path=self._instance_state_path(),
        include_workspace_details=include_workspace_details,
    )


def fetch_instance_snapshot_method(self, *, force: bool = False) -> dict:
    return fetch_instance_snapshot(self, force=force)


def fetch_connector_inventory_method(self, *, force: bool = False) -> list[dict]:
    return fetch_connector_inventory_snapshot(self, force=force)


def load_instance_history_from_logs_method(self, name: str) -> list[dict[str, str]]:
    return load_instance_history_from_logs(
        name,
        instance_logger_available=_INSTANCE_LOGGER_AVAILABLE,
        log_reader=read_instance_log_tail,
    )


def load_instance_catalog_method(self, snapshot: dict | None = None) -> tuple[list[str], str]:
    return load_instance_catalog(self, snapshot=snapshot)


def refresh_instance_views_method(self, *, load_logs: bool = False, force: bool = False) -> None:
    refresh_workspace_instance_views(self, load_logs=load_logs, force=force)
    refresh_banner = getattr(self, "_refresh_first_run_banner", None)
    if callable(refresh_banner):
        refresh_banner()


def sync_assistant_library_context(self, library_view) -> None:
    _lib_handlers.sync_assistant_library_context(self, library_view)


def ensure_library_workflow(self):
    return _lib_handlers.ensure_library_workflow(self)


def compose_library_aware_message(cmd: str, active_items: list[dict[str, str]] | None) -> str:
    return _lib_handlers.compose_library_aware_message(cmd, active_items)


def on_library_context_requested(self, title: str, item_path: str, item_kind: str, prompt: str) -> None:
    _lib_handlers.on_library_context_requested(self, title, item_path, item_kind, prompt)


def on_library_context_cleared(self) -> None:
    _lib_handlers.on_library_context_cleared(self)


def on_library_context_focused(self, title: str) -> None:
    _lib_handlers.on_library_context_focused(self, title)


def on_library_context_default_requested(self, title: str) -> None:
    _lib_handlers.on_library_context_default_requested(self, title)


def on_library_context_opened(self, title: str) -> None:
    _lib_handlers.on_library_context_opened(self, title)


def on_library_context_removed(self, title: str) -> None:
    _lib_handlers.on_library_context_removed(self, title)


def refresh_library_surface(self) -> None:
    _lib_handlers.refresh_library_surface(self)


def on_library_root_requested(self, root_path: str, label: str) -> None:
    _lib_handlers.on_library_root_requested(self, root_path, label)


def on_library_note_requested(self, title: str, summary: str) -> None:
    _lib_handlers.on_library_note_requested(self, title, summary)


def on_library_note_updated(self, item_id: int, title: str, summary: str) -> None:
    _lib_handlers.on_library_note_updated(self, item_id, title, summary)


def on_library_artifact_requested(self, title: str, item_path: str, summary: str) -> None:
    _lib_handlers.on_library_artifact_requested(self, title, item_path, summary)


def on_library_artifact_updated(self, item_id: int, title: str, item_path: str, summary: str) -> None:
    _lib_handlers.on_library_artifact_updated(self, item_id, title, item_path, summary)


def on_library_item_deleted(self, item_id: int, title: str) -> None:
    _lib_handlers.on_library_item_deleted(self, item_id, title)


def on_assistant_reply_library_requested(self, content: str, attach_next: bool) -> None:
    _lib_handlers.on_assistant_reply_library_requested(self, content, attach_next)


def on_assistant_reply_artifact_requested(self, content: str) -> None:
    _lib_handlers.on_assistant_reply_artifact_requested(self, content)


def on_latest_saved_output_attached(self, title: str, summary: str) -> None:
    _lib_handlers.on_latest_saved_output_attached(self, title, summary)


def on_active_context_refresh_requested(self, content: str, as_artifact: bool) -> None:
    _lib_handlers.on_active_context_refresh_requested(self, content, as_artifact)


def apply_instance_switch(self, target: str, *, announce: bool = True) -> None:
    _inst_handlers.apply_instance_switch(self, target, announce=announce)


def bootstrap_instance_switcher(self) -> None:
    _inst_handlers.bootstrap_instance_switcher(self)


def complete_bootstrap_instance_switcher(self) -> None:
    _inst_handlers.complete_bootstrap_instance_switcher(self)


def snapshot_active_instance_history(self) -> None:
    _inst_handlers.snapshot_active_instance_history(self)


def on_instance_selected(self, name: str) -> None:
    _inst_handlers.on_instance_selected(self, name)


def on_instance_manager_refresh(self) -> None:
    _inst_handlers.on_instance_manager_refresh(self)


def on_instance_create_requested(self, payload: dict) -> None:
    _inst_handlers.on_instance_create_requested(self, payload)


def on_instance_governance_save_requested(self, payload: dict) -> None:
    _inst_handlers.on_instance_governance_save_requested(self, payload)


def on_instance_connector_binding_save_requested(self, payload: dict) -> None:
    _conn_handlers.on_instance_connector_binding_save_requested(self, payload)


def perform_connector_action_request(self, payload: dict) -> dict:
    return _conn_handlers.perform_request(self, payload)


def apply_connector_action_feedback(self, record: dict, *, refresh_after: bool = True) -> dict:
    return _conn_handlers.apply_feedback(self, record, refresh_after=refresh_after)


def run_connector_action_request(self, payload: dict, *, refresh_after: bool = True) -> dict:
    return _conn_handlers.run_request(self, payload, refresh_after=refresh_after)


def start_connector_action_async(self, payload: dict, *, refresh_after: bool = True) -> None:
    _conn_handlers.start_async(self, payload, refresh_after=refresh_after)


def start_connector_guided_link_async(self, payload: dict) -> None:
    _conn_handlers.start_guided_link_async(self, payload)


def drain_connector_action_events(self) -> None:
    _conn_handlers.drain_events(self)


def on_connector_action_requested(self, payload: dict) -> None:
    _conn_handlers.on_action_requested(self, payload)


def on_connector_guided_link_requested(self, payload: dict) -> None:
    _conn_handlers.on_guided_link_requested(self, payload)


def on_instance_delete_requested(self, name: str) -> None:
    _inst_handlers.on_instance_delete_requested(self, name)


def on_instance_logs_requested(self, name: str, quiet: bool = False) -> None:
    _inst_handlers.on_instance_logs_requested(self, name, quiet=quiet)


def log_launcher_event(self, event: str, **fields: object) -> None:
    _log_launcher_event_fn(event, runtime_path=_RUNTIME, start_time=getattr(self, "_launch_start_time", 0.0), **fields)


def preferred_builder_instance_name(self) -> str:
    snapshot = self._last_instance_snapshot if isinstance(self._last_instance_snapshot, dict) else {}
    return preferred_builder_workspace_name(self._active_instance_name, snapshot)


def display_repo_path_static(path: Path | str | None) -> str:
    return display_repo_path(_RUNTIME.parent, path)
