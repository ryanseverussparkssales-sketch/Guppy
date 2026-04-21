"""
ui/launcher/launcher_window.py
Main QMainWindow shell — assembles Sidebar, TopBar, StatusPanel,
the unified launcher stack, and the bottom system strip.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from queue import Empty, SimpleQueue
from pathlib import Path
import urllib.error
import urllib.request

import src.guppy.launcher_application as launcher_app
from src.guppy.launcher_application import (
    LauncherStateSnapshot,
    LibraryWorkflowController,
    apply_connector_action_feedback,
    apply_library_payload,
    apply_workspace_instance_switch,
    beta_release_dry_run_report_path,
    bootstrap_workspace_instance_switcher,
    build_launcher_state_snapshot,
    build_library_chat_submission,
    build_windows_ops_descriptor,
    build_windows_ops_plan,
    collect_windows_service_snapshot,
    connector_action_http_payload,
    connector_action_record,
    connector_action_status_label,
    complete_bootstrap_workspace_instance_switcher,
    drain_connector_action_events,
    default_windows_ops_event_id,
    connector_backend_available,
    delete_workspace_instance,
    enabled_workspace_names,
    execute_connector_action,
    execute_guided_connector_setup,
    fetch_connector_inventory,
    handle_connector_action_request,
    handle_connector_guided_link_request,
    load_workspace_instance_logs,
    perform_connector_action_request,
    refresh_workspace_instance_views,
    release_dry_run_gate_details,
    repo_python_path,
    resolve_active_instance_payload,
    save_workspace_connector_binding,
    save_instance_connector_binding,
    save_instance_governance,
    run_repo_python,
    run_connector_action_request,
    save_workspace_instance,
    snapshot_file_signature,
    select_workspace_instance,
    start_connector_action_async,
    start_connector_guided_link_async,
    summarize_release_dry_run_report,
    compose_library_aware_message,
    set_daily_activity,
    sync_right_tray,
    summarize_windows_recipe_result,
    sync_assistant_library_context,
    update_route_preview,
    windows_ops_artifact_refs,
    windows_ops_chain_changes,
    windows_ops_guidance,
    windows_service_snapshot_changes,
    workspace_default_purpose,
    workspace_first_run_recipe,
    workspace_onboarding_ready_message,
    workspace_role_label,
    write_windows_release_receipt,
    write_windows_release_summary,
)
from src.guppy.experience_config import (
    PersonalizationState,
    build_persona_options,
    ensure_personalization_scaffold,
    list_persona_choices,
    load_persona_config,
    load_voice_bindings,
    personalization_backend_available,
    resolve_voice_binding,
    voice_binding_summary,
    voice_option_choices,
)
from src.guppy.runtime_application import (
    RuntimeHealthSnapshot,
    route_evidence_summary,
    summarize_startup_readiness,
)
from src.guppy.workspace_governance import (
    instance_policy_backend_available,
    build_connector_action_request,
    build_connector_action_result,
    build_connector_inventory,
    set_instance_tool_permission_policy,
)

connector_inventory = fetch_connector_inventory

from src.guppy.launcher_application.tool_action_registry import get_home_starter_prompt as _registry_tool_prompt
from src.guppy.launcher_application.storage_io import (
    append_instance_log,
    append_jsonl,
    instance_logger_backend_available,
    read_instance_log_tail,
    read_json_dict,
    read_jsonl_tail,
    secret_store_client,
    secret_store_backend_available,
    write_json_atomic,
)
from src.guppy.launcher_application.recovery_coordination import (
    classify_recovery_summary,
    drain_recovery_events,
    format_recovery_summary,
    push_recovery_outcome,
    run_recovery_request,
    start_recovery_request,
    sync_recovery_outcome,
)
from src.guppy.launcher_application.automation_test_support import (
    build_automation_test_snapshot,
    display_repo_path,
    event_level,
    latest_stress_report_path,
    recent_launcher_event_summaries,
    write_user_test_evidence_pack,
    write_user_test_evidence_summary,
)
from src.guppy.launcher_application.automation_test_coordination import (
    approve_latest_builder_task,
    build_launcher_automation_test_snapshot,
    handle_automation_action_request,
    handle_builder_task_requested,
    preferred_builder_workspace_name,
    queue_builder_task as _queue_builder_task_fn,
    sync_launcher_automation_test_state,
    user_test_evidence_paths,
    write_launcher_automation_report,
    write_launcher_user_test_evidence_pack,
)
from src.guppy.launcher_application.launcher_event_log import log_launcher_event as _log_launcher_event_fn
from src.guppy.launcher_application.launcher_tools_coordination import (
    load_tool_states as _load_tool_states_fn,
    on_settings_saved as _on_settings_saved_fn,
    on_tool_hint_requested as _on_tool_hint_requested_fn,
    on_tool_management_requested as _on_tool_management_requested_fn,
    on_tool_state_changed as _on_tool_state_changed_fn,
    on_voice_bindings_changed as _on_voice_bindings_changed_fn,
)
from src.guppy.launcher_application.launcher_signal_personalization import (
    bootstrap_personalization_scaffold_worker as _bootstrap_personalization_scaffold_worker_fn,
    refresh_personalization_state as _refresh_personalization_state_fn,
    wire_signals as _wire_signals_fn,
)
from src.guppy.launcher_application.launcher_first_run import (
    on_first_run_action_requested as _on_first_run_action_requested_fn,
    refresh_first_run_banner as _refresh_first_run_banner_fn,
)
from src.guppy.launcher_application.first_run_wizard import FirstRunWizard
from src.guppy.launcher_application.status_poll import (
    build_launcher_status_poll_snapshot,
    fetch_api_status,
)
from src.guppy.launcher_application.launcher_shell_support import (
    QuickActionPlan,
    apply_quick_action_plan as _apply_quick_action_plan_fn,
    build_notification_badge_state,
    build_quick_action_plan,
    build_runtime_badge_state,
    on_home_starter_requested as _on_home_starter_requested_fn,
)
from src.guppy.launcher_application.launcher_command_flow import (
    apply_chat_context as _apply_chat_context_fn,
    assistant_model_id as _assistant_model_id_fn,
    build_shell_model_loadout_summary,
    chat_timeout_for_request,
    drain_assistant_events,
    finish_request_ui as _finish_request_ui_fn,
    handle_assistant_command,
    humanize_chat_error,
    initialize_embedded_agent as _initialize_embedded_agent_fn,
    on_agent_init_requested as _on_agent_init_requested_fn,
    on_cancel_assistant_request as _on_cancel_assistant_request_fn,
    on_chat_context_changed as _on_chat_context_changed_fn,
    on_model_selected as _on_model_selected_fn,
    on_runtime_settings_saved as _on_runtime_settings_saved_fn,
    required_local_model_for_mode,
    rotate_chat_session as _rotate_chat_session_fn,
    validate_mode_ready as _validate_mode_ready_fn,
)
from src.guppy.launcher_application.launcher_poll_orchestration import (
    complete_startup_phase as _complete_startup_phase_fn,
    orchestrate_status_poll,
    sync_topbar_model_context as _sync_topbar_model_context_fn,
)
from src.guppy.launcher_application.launcher_voice_strip import (
    build_sys_strip as _build_sys_strip_fn,
    ensure_voice_capture as _ensure_voice_capture_fn,
    on_mic_requested as _on_mic_requested_fn,
    update_sys_strip as _update_sys_strip_fn,
)
from src.guppy.launcher_application.workspace_snapshot_support import (
    build_local_instance_snapshot,
    default_governance_snapshot,
    fetch_connector_inventory_snapshot,
    fetch_instance_snapshot,
    instance_state_path,
    instances_config_path,
    load_instance_catalog,
    load_instance_history_from_logs,
)
from src.guppy.launcher_application.windows_ops_coordination import (
    WindowsOpsStateRecord,
    complete_windows_ops_terminal_recipe,
    persist_windows_ops_state,
)
from src.guppy.launcher_application.windows_ops_request_flow import (
    dispatch_windows_ops_request,
    start_windows_ops_chain_request,
    update_windows_ops_chain_request,
)
from src.guppy.launcher_application.tools_trace_adapter import LauncherToolsTraceAdapter

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.guppy.inference.router import resolve_ui_route
from . import tokens as T
from .stylesheet import SHEET
from .launcher_runtime_control_mixin import LauncherRuntimeControlMixin
from .launcher_windows_ops_mixin import LauncherWindowsOpsMixin
from .components import Sidebar, TopBar, StatusPanel
from .views import (
    AssistantView,
    InstanceManagerView,
    LibraryView,
    ToolsView,
    SettingsView,
    SettingsHubView,
    SettingsDeviceAccountsPanel,
    SettingsOperationsPanel,
    ModelsHubView,
    LocalLLMView,
    ModelsView,
    RuntimeRoutingView,
    VoicesView,
)

_PERSONALIZATION_BOOTSTRAP_AVAILABLE = personalization_backend_available()
_INSTANCE_LOGGER_AVAILABLE = instance_logger_backend_available()
_SECRET_STORE_AVAILABLE = secret_store_backend_available()
_secret_store = secret_store_client()
_INSTANCE_GOVERNANCE_BACKEND = instance_policy_backend_available()

_CONNECTOR_MANAGER_BACKEND = connector_backend_available()

try:
    from src.guppy.voice.voice import GuppyVoice
    _VOICE_CAPTURE_AVAILABLE = True
except Exception:
    GuppyVoice = None  # type: ignore[assignment]
    _VOICE_CAPTURE_AVAILABLE = False

_RUNTIME = Path(__file__).resolve().parent.parent.parent / "runtime"
_CONFIG = Path(__file__).resolve().parent.parent.parent / "config"
_COMMAND_START_TTL_SECONDS = float(os.environ.get("GUPPY_COMMAND_START_TTL_SECONDS", "20"))
_START_TIME = time.monotonic()
_AUTOMATION_TEST_VALIDATION_COMMAND = (
    ".venv\\Scripts\\python.exe -m pytest tests/unit/test_offhours_builder.py tests/unit/test_instance_controls.py -q"
)
_AUTOMATION_REPORT_PATH = _RUNTIME / "offhours_builder_report.json"
_HOME_VIEW_INDEX = 0
_WORKSPACES_VIEW_INDEX = 1
_LIBRARY_VIEW_INDEX = 2
_TOOLS_VIEW_INDEX = 3
_SETTINGS_VIEW_INDEX = 4
_SETTINGS_OPS_INDEX = 4
_SETTINGS_ALIAS_INDEX = 10
_MODELS_VIEW_INDEX = 5
_MODELS_LOCAL_ALIAS_INDEX = 6
_MODELS_LIBRARY_ALIAS_INDEX = 7
_MODELS_RUNTIME_ALIAS_INDEX = 8
_MODELS_VOICE_ALIAS_INDEX = 9
_START_DESTINATION_TO_TAB = {
    "home": _HOME_VIEW_INDEX,
    "workspaces": _WORKSPACES_VIEW_INDEX,
    "spaces": _WORKSPACES_VIEW_INDEX,
    "library": _LIBRARY_VIEW_INDEX,
    "tools": _TOOLS_VIEW_INDEX,
    "appmgmt": _SETTINGS_OPS_INDEX,
    "automation-test": _SETTINGS_OPS_INDEX,
    "local-llm": _MODELS_LOCAL_ALIAS_INDEX,
    "models": _MODELS_LIBRARY_ALIAS_INDEX,
    "runtime": _MODELS_RUNTIME_ALIAS_INDEX,
    "voice": _MODELS_VOICE_ALIAS_INDEX,
}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not write_json_atomic(path, payload):
        raise OSError(f"Atomic write failed for {path}")


class LauncherWindow(LauncherWindowsOpsMixin, LauncherRuntimeControlMixin, QMainWindow):
    assistant_event_queued = Signal()
    connector_action_event_queued = Signal()

    _MAX_DEFERRED_SYSLOG_PER_TICK = 24
    _MAX_ASSISTANT_EVENTS_PER_TICK = 12
    _MAX_RECOVERY_EVENTS_PER_TICK = 12

    @staticmethod
    def _event_level(item: dict[str, object]) -> str:
        return event_level(item)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Guppy  //  WORKSPACE_ASSISTANT")
        self.setMinimumSize(1120, 720)
        self.setStyleSheet(SHEET)
        self._last_command = ""
        self._last_recovery_signature = ""
        self._startup_logged_first_poll = False
        self._startup_first_poll_ok = False
        self._startup_budget_ms = int(os.environ.get("GUPPY_STARTUP_PHASE_WARN_MS", "3000"))
        self._startup_phase_started: dict[str, float] = {"window_init": time.monotonic()}
        self._startup_phase_durations_ms: dict[str, int] = {}
        self._startup_over_budget: list[str] = []
        self._last_poll_warn_ts = 0.0
        self._chat_session_id = f"launcher-{int(time.time())}"
        self._active_instance_name = "guppy-primary"
        self._instance_histories: dict[str, list[dict[str, str]]] = {}
        self._request_in_flight = False
        self._pending_chat_context: tuple[str, str] | None = None
        self._canceled_request_seqs: set[int] = set()
        self._active_request_seq: int = 0  # monotonic; only the latest response is shown
        self._api_bearer_token = ""
        self._api_token_source = "none"
        self._auth_self_check_ok = False
        self._auth_self_check_inflight = False
        self._auth_self_check_last_attempt = 0.0
        self._start_destination = str(os.environ.get("GUPPY_START_DESTINATION", "") or "").strip().lower()
        self._embedded_online: set[str] = set()
        self._assistant_events: SimpleQueue[tuple[str, str, int]] = SimpleQueue()
        self._recovery_events: SimpleQueue[dict[str, object]] = SimpleQueue()
        self._connector_action_events: SimpleQueue[dict[str, object]] = SimpleQueue()
        self._active_windows_ops_chain: dict[str, object] | None = None
        self._last_instance_snapshot: dict[str, object] = {}
        self._instance_snapshot_expires_at = 0.0
        self._last_connector_inventory_snapshot: list[dict[str, object]] = []
        self._connector_inventory_expires_at = 0.0
        self._last_instance_view_signature = ""
        self._last_connector_view_signature = ""
        self._last_library_context_signature = ""
        self._last_tools_context_signature = ""
        self._last_windows_snapshot_signature = ""
        self._tools_trace_adapter: LauncherToolsTraceAdapter | None = None
        self._launcher_state_snapshot = LauncherStateSnapshot.empty()
        self._runtime_health_snapshot = RuntimeHealthSnapshot()
        self._bootstrap_instance_refresh_pending = False
        self._bootstrap_instance_refresh_complete = False
        self._instance_snapshot_ttl_s = float(os.environ.get("GUPPY_INSTANCE_SNAPSHOT_TTL_S", "6.0"))
        self._connector_inventory_ttl_s = float(os.environ.get("GUPPY_CONNECTOR_INVENTORY_TTL_S", "15.0"))
        self._scaffold_created: dict[str, Path] = {}
        self._deferred_syslog: SimpleQueue[str] = SimpleQueue()
        self._active_library_context_items: list[dict[str, str]] = []
        self._status_poll_timer: QTimer | None = None
        self._launcher_voice = None
        self._mic_capture_active = False
        self._notification_badge_mtime = 0.0
        self._recovery_outcome_mtime = 0.0
        self._home_drawer_open = False
        self._log_launcher_event("startup_phase", phase="window_init_enter")

        self._build_ui()
        self._api_bearer_token = self._build_local_bearer_token()
        self._complete_startup_phase("build_ui", start_at=self._startup_phase_started["window_init"])
        self._log_launcher_event("startup_phase", phase="window_build_ui_complete")
        self._start_status_poll()
        self._complete_startup_phase("status_poll_start")
        self._log_launcher_event("startup_phase", phase="window_status_poll_started")
        self._load_tool_states()

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top bar ─────────────────────────────────────────────────────────
        self._topbar = TopBar(self)
        self._topbar.setFixedHeight(T.TOPBAR_H)
        root.addWidget(self._topbar)

        # ── Divider ──────────────────────────────────────────────────────────
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background: {T.BORDER};")
        root.addWidget(div)

        # ── Body row: Sidebar | Content | StatusPanel ────────────────────────
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._sidebar = Sidebar(self)
        body.addWidget(self._sidebar)

        # Thin vertical divider
        sdiv = QFrame()
        sdiv.setFixedWidth(1)
        sdiv.setStyleSheet(f"background: {T.BORDER};")
        body.addWidget(sdiv)

        # Content stack
        self._stack = QStackedWidget(self)
        self._assistant_view  = AssistantView(self)
        self._instance_manager_view = InstanceManagerView(self)
        self._library_view    = LibraryView(self)
        self._tools_view      = ToolsView(self)
        self._settings_view   = SettingsView(self)
        self._settings_device_accounts_panel = SettingsDeviceAccountsPanel(self)
        self._settings_operations_panel = SettingsOperationsPanel(self)
        self._settings_hub_view = SettingsHubView(
            self._settings_view,
            self._settings_device_accounts_panel,
            self._settings_operations_panel,
            self,
        )
        self._local_llm_view  = LocalLLMView(self)
        self._models_view     = ModelsView(self)
        self._runtime_view    = RuntimeRoutingView(self)
        self._voices_view     = VoicesView(self)
        self._models_hub_view = ModelsHubView(
            self._models_view,
            self._local_llm_view,
            self._voices_view,
            self,
        )

        for view in [
            self._assistant_view,
            self._instance_manager_view,
            self._library_view,
            self._tools_view,
            self._settings_hub_view,
            self._models_hub_view,
        ]:
            self._stack.addWidget(view)

        body.addWidget(self._stack, stretch=1)

        # Thin vertical divider
        self._status_divider = QFrame()
        self._status_divider.setFixedWidth(1)
        self._status_divider.setStyleSheet(f"background: {T.BORDER};")
        body.addWidget(self._status_divider)

        self._status_panel = StatusPanel(self)
        body.addWidget(self._status_panel)
        self._library_workflow = LibraryWorkflowController(
            assistant_view=self._assistant_view,
            status_panel=self._status_panel,
            get_active_items=lambda: list(self._active_library_context_items),
            set_active_items=lambda items: setattr(self, "_active_library_context_items", list(items)),
            get_active_instance_name=lambda: self._active_instance_name,
            get_library_view=lambda: getattr(self, "_library_view", None),
            refresh_library_surface=self._refresh_library_surface,
            on_tab_change=self._on_tab_change,
            set_daily_activity=self._set_daily_activity,
            log_launcher_event=self._log_launcher_event,
        )
        self._wire_tools_trace_adapter()

        root.addLayout(body, stretch=1)

        # ── Bottom system strip ──────────────────────────────────────────────
        self._sys_strip = self._build_sys_strip()
        root.addWidget(self._sys_strip)

        # ── Wire signals ─────────────────────────────────────────────────────
        self._wire_signals()
        self._assistant_view.set_session_id(self._chat_session_id)
        self._topbar.set_launcher_summary("AUTO / GUPPY / LIGHT [EDIT]")
        self._topbar.set_runtime_status(
            "STARTING",
            detail="Launcher is still collecting startup readiness and runtime health.",
            severity="info",
        )
        self._sidebar.set_collapsed(True)
        self._topbar.set_sidebar_collapsed(True)
        self._set_status_panel_visible(False)
        self._bootstrap_instance_switcher()
        self._refresh_personalization_state()
        self._refresh_first_run_banner()
        self._sync_automation_test_state()
        QTimer.singleShot(0, self._apply_start_destination)

        if _PERSONALIZATION_BOOTSTRAP_AVAILABLE:
            self._log_launcher_event("startup_phase", phase="personalization_scaffold_thread_start")
            threading.Thread(target=self._bootstrap_personalization_scaffold_worker, daemon=True).start()

    def _bootstrap_personalization_scaffold_worker(self) -> None:
        _bootstrap_personalization_scaffold_worker_fn(self)

    def _wire_signals(self) -> None:
        _wire_signals_fn(self, settings_view_index=_SETTINGS_VIEW_INDEX)

    def _wire_tools_trace_adapter(self) -> None:
        adapter = LauncherToolsTraceAdapter(
            _RUNTIME,
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
        self._refresh_tools_debug_surface()

    def _refresh_tools_debug_surface(self) -> None:
        refresh = getattr(self._tools_view, "refresh_debug_surface", None)
        if callable(refresh):
            refresh()

    def _drain_deferred_syslog(self) -> None:
        processed = 0
        while processed < self._MAX_DEFERRED_SYSLOG_PER_TICK:
            try:
                line = self._deferred_syslog.get_nowait()
            except Empty:
                break
            self._status_panel.append_syslog(line)
            processed += 1

    def _refresh_personalization_state(self, preferred_persona: str = "") -> None:
        _refresh_personalization_state_fn(
            self,
            preferred_persona=preferred_persona,
            personalization_available=_PERSONALIZATION_BOOTSTRAP_AVAILABLE,
        )

    def _update_route_preview(self, text: str = "") -> None:
        update_route_preview(self, text)
        self._sync_topbar_model_context()

    def _set_daily_activity(self, text: str) -> None:
        set_daily_activity(self, text)

    def _sync_right_tray(self, active_payload: dict[str, object]) -> None:
        sync_right_tray(self, active_payload)

    # ── Bottom strip ──────────────────────────────────────────────────────────
    def _build_sys_strip(self) -> QFrame:
        return _build_sys_strip_fn(self, tokens=T)

    def _update_sys_strip(self) -> None:
        _update_sys_strip_fn(self, runtime_path=_RUNTIME, start_time=_START_TIME, tokens=T)

    # ── Status polling ────────────────────────────────────────────────────────
    def _start_status_poll(self) -> None:
        self._status_poll_timer = QTimer(self)
        self._status_poll_timer.timeout.connect(self._poll_status)
        self._status_poll_timer.start(3000)
        QTimer.singleShot(0, self._poll_status)

    def _poll_status(self) -> None:
        orchestrate_status_poll(
            self,
            runtime_path=_RUNTIME,
            personalization_available=_PERSONALIZATION_BOOTSTRAP_AVAILABLE,
            start_time=_START_TIME,
        )

    def _complete_startup_phase(self, phase: str, start_at: float | None = None) -> None:
        _complete_startup_phase_fn(self, phase, start_at=start_at)

    def _sync_recovery_outcome(self) -> None:
        sync_recovery_outcome(self, runtime_path=_RUNTIME, read_jsonl_tail=read_jsonl_tail)

    def _sync_topbar_model_context(
        self,
        *,
        main_model: str = "",
        support_model: str = "",
    ) -> None:
        _sync_topbar_model_context_fn(self, main_model=main_model, support_model=support_model)

    @staticmethod
    def _classify_recovery_summary(summary: str, ok: bool, default: str = "") -> str:
        return classify_recovery_summary(summary, ok, default)

    @staticmethod
    def _format_recovery_summary(category: str, summary: str) -> str:
        return format_recovery_summary(category, summary)

    def _push_recovery_outcome(self, action: str, ok: bool, summary: str, category: str = "") -> str:
        return push_recovery_outcome(self, action, ok, summary, category)

    # ── Tab coordination ──────────────────────────────────────────────────────
    @staticmethod
    def _resolve_stack_index(index: int) -> int:
        if index <= _SETTINGS_VIEW_INDEX:
            return index
        if index == _SETTINGS_ALIAS_INDEX:
            return _SETTINGS_VIEW_INDEX
        if index in {
            _MODELS_LOCAL_ALIAS_INDEX,
            _MODELS_LIBRARY_ALIAS_INDEX,
            _MODELS_RUNTIME_ALIAS_INDEX,
            _MODELS_VOICE_ALIAS_INDEX,
        }:
            return _MODELS_VIEW_INDEX
        return index

    @staticmethod
    def _visible_nav_index(index: int) -> int:
        if index == _WORKSPACES_VIEW_INDEX:
            return _HOME_VIEW_INDEX
        if index in {_SETTINGS_VIEW_INDEX, _SETTINGS_ALIAS_INDEX}:
            return _SETTINGS_VIEW_INDEX
        if index in {
            _MODELS_VIEW_INDEX,
            _MODELS_LOCAL_ALIAS_INDEX,
            _MODELS_LIBRARY_ALIAS_INDEX,
            _MODELS_RUNTIME_ALIAS_INDEX,
            _MODELS_VOICE_ALIAS_INDEX,
        }:
            return _MODELS_LIBRARY_ALIAS_INDEX
        return index

    @staticmethod
    def _shell_model_loadout_summary(
        *,
        active_model: str = "",
        runtime_backend: str = "",
        settings_payload: dict[str, object] | None = None,
        environment: dict[str, str] | None = None,
    ) -> str:
        return build_shell_model_loadout_summary(
            active_model=active_model,
            runtime_backend=runtime_backend,
            settings_payload=settings_payload,
            environment=environment,
        )

    def _sync_shell_model_summary(
        self,
        *,
        active_model: str = "",
        runtime_backend: str = "",
    ) -> None:
        app_settings = read_json_dict(_RUNTIME / "app_settings.json")
        summary = self._shell_model_loadout_summary(
            active_model=active_model,
            runtime_backend=runtime_backend,
            settings_payload=app_settings if isinstance(app_settings, dict) else {},
            environment=dict(os.environ),
        )
        self._topbar.set_launcher_summary(summary)
        self._sync_topbar_model_context(main_model=active_model)

    def _on_tab_change(self, index: int) -> None:
        stack_index = self._resolve_stack_index(index)
        visible_nav_index = self._visible_nav_index(index)
        self._stack.setCurrentIndex(stack_index)
        self._topbar.set_active_tab(visible_nav_index)
        self._sidebar.set_active(visible_nav_index)
        if visible_nav_index == _MODELS_LIBRARY_ALIAS_INDEX:
            self._sync_shell_model_summary()
        if index in {_SETTINGS_OPS_INDEX, _SETTINGS_ALIAS_INDEX}:
            self._sync_automation_test_state()
        if visible_nav_index == _HOME_VIEW_INDEX and not self._sidebar.is_collapsed():
            self._sidebar.set_collapsed(True)
            self._topbar.set_sidebar_collapsed(True)
        self._set_status_panel_visible(stack_index != _HOME_VIEW_INDEX or self._home_drawer_open)

    def _apply_start_destination(self) -> None:
        target = self._start_destination
        if target not in _START_DESTINATION_TO_TAB:
            return
        target_index = _START_DESTINATION_TO_TAB[target]
        if target == "automation-test" and not hasattr(self, "_stack"):
            target_index = 3
        self._on_tab_change(target_index)
        if target == "automation-test":
            note = (
                "Test flow ready: use Settings & System to verify readiness, queue one safe check, review it, approve it, and run validation."
            )
            self._settings_hub_view.focus_automation_test(note=note)
            self._assistant_view.set_background_event(note)
            self._set_daily_activity("Test flow opened Setup & Health / Settings & System")
            self._status_panel.append_syslog("automation test start intent opened Settings & System")
        self._log_launcher_event("start_destination_applied", destination=target)

    def _set_status_panel_visible(self, visible: bool) -> None:
        self._status_divider.setVisible(visible)
        self._status_panel.setVisible(visible)
        self._topbar.set_drawer_open(visible)

    def _toggle_status_panel(self) -> None:
        if self._stack.currentIndex() == _HOME_VIEW_INDEX:
            self._home_drawer_open = not self._home_drawer_open
            self._set_status_panel_visible(self._home_drawer_open)
            return
        self._set_status_panel_visible(not self._status_panel.isVisible())

    def _toggle_sidebar(self) -> None:
        collapsed = not self._sidebar.is_collapsed()
        self._sidebar.set_collapsed(collapsed)
        self._topbar.set_sidebar_collapsed(collapsed)

    def _build_quick_action_plan(self, action: str) -> QuickActionPlan:
        return build_quick_action_plan(
            action=action,
            workspaces_view_index=_WORKSPACES_VIEW_INDEX,
            settings_ops_index=_SETTINGS_OPS_INDEX,
            runtime_parent=_RUNTIME.parent,
            last_command=self._last_command,
        )

    def _apply_quick_action_plan(self, plan: QuickActionPlan) -> bool:
        return _apply_quick_action_plan_fn(self, plan)

    def _instances_config_path(self) -> Path:
        return instances_config_path(_CONFIG)

    def _instance_state_path(self) -> Path:
        return instance_state_path(_RUNTIME)

    @staticmethod
    def _default_governance_snapshot(instance_type: str) -> dict[str, object]:
        return default_governance_snapshot(instance_type)

    def _local_instance_snapshot(self, *, include_workspace_details: bool = True) -> dict:
        return build_local_instance_snapshot(
            config_path=self._instances_config_path(),
            state_path=self._instance_state_path(),
            include_workspace_details=include_workspace_details,
        )

    def _fetch_instance_snapshot(self, *, force: bool = False) -> dict:
        return fetch_instance_snapshot(self, force=force)

    def _fetch_connector_inventory(self, *, force: bool = False) -> list[dict]:
        return fetch_connector_inventory_snapshot(self, force=force)

    def _load_instance_history_from_logs(self, name: str) -> list[dict[str, str]]:
        return load_instance_history_from_logs(
            name,
            instance_logger_available=_INSTANCE_LOGGER_AVAILABLE,
            log_reader=read_instance_log_tail,
        )

    def _load_instance_catalog(self, snapshot: dict | None = None) -> tuple[list[str], str]:
        return load_instance_catalog(self, snapshot=snapshot)

    def _refresh_instance_views(self, *, load_logs: bool = False, force: bool = False) -> None:
        refresh_workspace_instance_views(self, load_logs=load_logs, force=force)
        LauncherWindow._refresh_first_run_banner(self)

    def _refresh_first_run_banner(self) -> None:
        _refresh_first_run_banner_fn(self, wizard_factory=FirstRunWizard)

    def _on_first_run_action_requested(self, action: str) -> None:
        _on_first_run_action_requested_fn(
            self, action,
            settings_view_index=_SETTINGS_VIEW_INDEX,
            models_view_index=_MODELS_VIEW_INDEX,
        )

    def _build_launcher_state_snapshot(
        self,
        snapshot: dict,
        typed_connector_inventory,
        windows_snapshot: dict[str, str],
        runtime_health: RuntimeHealthSnapshot | None = None,
    ) -> LauncherStateSnapshot:
        return build_launcher_state_snapshot(
            snapshot,
            typed_connector_inventory if _CONNECTOR_MANAGER_BACKEND else (),
            windows_snapshot if isinstance(windows_snapshot, dict) else {},
            active_view="home",
            runtime_health=runtime_health,
        )

    def _sync_assistant_library_context(self, library_view) -> None:
        sync_assistant_library_context(self._assistant_view, library_view, self._active_library_context_items)

    def _ensure_library_workflow(self):
        workflow = getattr(self, "_library_workflow", None)
        if workflow is not None:
            return workflow
        workflow = LibraryWorkflowController(
            assistant_view=getattr(self, "_assistant_view", None),
            status_panel=getattr(self, "_status_panel", None),
            get_active_items=lambda: list(getattr(self, "_active_library_context_items", [])),
            set_active_items=lambda items: setattr(self, "_active_library_context_items", list(items)),
            get_active_instance_name=lambda: getattr(self, "_active_instance_name", "guppy-primary"),
            get_library_view=lambda: getattr(self, "_library_view", None),
            refresh_library_surface=lambda: self._refresh_library_surface(),
            on_tab_change=lambda index: self._on_tab_change(index),
            set_daily_activity=lambda text: self._set_daily_activity(text),
            log_launcher_event=lambda event, **fields: self._log_launcher_event(event, **fields),
        )
        setattr(self, "_library_workflow", workflow)
        return workflow

    @staticmethod
    def _compose_library_aware_message(cmd: str, active_items: list[dict[str, str]] | None) -> str:
        return compose_library_aware_message(cmd, active_items)

    def _on_library_context_requested(self, title: str, item_path: str, item_kind: str, prompt: str) -> None:
        self._ensure_library_workflow().handle_context_requested(title, item_path, item_kind, prompt)

    def _on_library_context_cleared(self) -> None:
        self._ensure_library_workflow().handle_context_cleared()

    def _on_library_context_focused(self, title: str) -> None:
        self._ensure_library_workflow().handle_context_focused(title)

    def _on_library_context_default_requested(self, title: str) -> None:
        self._ensure_library_workflow().handle_default_source_requested(title)

    def _on_library_context_opened(self, title: str) -> None:
        title_text = str(title or "").strip()
        self._on_tab_change(2)
        library_view = getattr(self, "_library_view", None)
        if library_view is not None and hasattr(library_view, "focus_search_query"):
            library_view.focus_search_query(title_text)
        self._set_daily_activity(f"Library opened for source: {title_text}")
        self._status_panel.append_syslog(f"library source opened: {title_text}")
        self._log_launcher_event("library_context_opened", title=title_text)

    def _on_library_context_removed(self, title: str) -> None:
        self._ensure_library_workflow().handle_context_removed(title)

    def _refresh_library_surface(self) -> None:
        snapshot = self._last_instance_snapshot if isinstance(self._last_instance_snapshot, dict) else {}
        active_payload = resolve_active_instance_payload(snapshot, self._active_instance_name)
        library_view = getattr(self, "_library_view", None)
        if library_view is not None and isinstance(active_payload, dict):
            apply_library_payload(self._assistant_view, library_view, self._active_library_context_items, active_payload, snapshot)

    def _on_library_root_requested(self, root_path: str, label: str) -> None:
        self._ensure_library_workflow().handle_root_requested(root_path, label)

    def _on_library_note_requested(self, title: str, summary: str) -> None:
        self._ensure_library_workflow().handle_note_requested(title, summary)

    def _on_library_note_updated(self, item_id: int, title: str, summary: str) -> None:
        self._ensure_library_workflow().handle_note_updated(item_id, title, summary)

    def _on_library_artifact_requested(self, title: str, item_path: str, summary: str) -> None:
        self._ensure_library_workflow().handle_artifact_requested(title, item_path, summary)

    def _on_library_artifact_updated(self, item_id: int, title: str, item_path: str, summary: str) -> None:
        self._ensure_library_workflow().handle_artifact_updated(item_id, title, item_path, summary)

    def _on_library_item_deleted(self, item_id: int, title: str) -> None:
        self._ensure_library_workflow().handle_item_deleted(item_id, title)

    def _on_assistant_reply_library_requested(self, content: str, attach_next: bool) -> None:
        self._ensure_library_workflow().handle_reply_saved(content, attach_next=attach_next)
    def _on_assistant_reply_artifact_requested(self, content: str) -> None:
        self._ensure_library_workflow().handle_reply_artifact_saved(content)
    def _on_latest_saved_output_attached(self, title: str, summary: str) -> None:
        self._ensure_library_workflow().handle_latest_output_attached(title, summary)
    def _on_active_context_refresh_requested(self, content: str, as_artifact: bool) -> None:
        workflow = self._ensure_library_workflow()
        if as_artifact:
            workflow.handle_reply_artifact_saved(content, attach_now=True)
        else:
            workflow.handle_reply_saved(content, attach_next=True)

    def _apply_instance_switch(self, target: str, *, announce: bool = True) -> None:
        apply_workspace_instance_switch(self, target, announce=announce)

    def _bootstrap_instance_switcher(self) -> None:
        bootstrap_workspace_instance_switcher(self, schedule_single_shot=QTimer.singleShot)

    def _complete_bootstrap_instance_switcher(self) -> None:
        complete_bootstrap_workspace_instance_switcher(
            self,
            schedule_single_shot=QTimer.singleShot,
            monotonic=time.monotonic,
            fetch_connector_inventory=connector_inventory,
        )

    def _snapshot_active_instance_history(self) -> None:
        if not self._active_instance_name:
            return
        self._instance_histories[self._active_instance_name] = self._assistant_view.recent_history(limit=200)

    def _on_instance_selected(self, name: str) -> None:
        select_workspace_instance(self, name, read_json_dict=read_json_dict, write_json=_write_json)

    def _on_instance_manager_refresh(self) -> None:
        launcher_app.refresh_workspace_instance_manager(self)

    def _on_instance_create_requested(self, payload: dict) -> None:
        save_workspace_instance(self, payload)

    def _on_instance_governance_save_requested(self, payload: dict) -> None:
        save_instance_governance(self, payload, backend_available=_INSTANCE_GOVERNANCE_BACKEND)

    def _on_instance_connector_binding_save_requested(self, payload: dict) -> None:
        save_instance_connector_binding(self, payload, backend_available=_CONNECTOR_MANAGER_BACKEND)

    def _perform_connector_action_request(self, payload: dict) -> dict:
        return perform_connector_action_request(self, payload, backend_available=_CONNECTOR_MANAGER_BACKEND)

    def _apply_connector_action_feedback(self, record: dict, *, refresh_after: bool = True) -> dict:
        return apply_connector_action_feedback(self, record, refresh_after=refresh_after)

    def _run_connector_action_request(self, payload: dict, *, refresh_after: bool = True) -> dict:
        return run_connector_action_request(
            self,
            payload,
            refresh_after=refresh_after,
            backend_available=_CONNECTOR_MANAGER_BACKEND,
        )

    def _start_connector_action_async(self, payload: dict, *, refresh_after: bool = True) -> None:
        start_connector_action_async(
            self,
            payload,
            refresh_after=refresh_after,
            backend_available=_CONNECTOR_MANAGER_BACKEND,
        )

    def _start_connector_guided_link_async(self, payload: dict) -> None:
        start_connector_guided_link_async(self, payload, backend_available=_CONNECTOR_MANAGER_BACKEND)

    def _drain_connector_action_events(self) -> None:
        drain_connector_action_events(self)

    def _on_connector_action_requested(self, payload: dict) -> None:
        handle_connector_action_request(self, payload, backend_available=_CONNECTOR_MANAGER_BACKEND)

    def _on_connector_guided_link_requested(self, payload: dict) -> None:
        handle_connector_guided_link_request(self, payload, backend_available=_CONNECTOR_MANAGER_BACKEND)

    def _on_instance_delete_requested(self, name: str) -> None:
        delete_workspace_instance(self, name)

    def _on_instance_logs_requested(self, name: str, quiet: bool = False) -> None:
        load_workspace_instance_logs(
            self,
            name,
            quiet=quiet,
            local_log_reader=read_instance_log_tail if _INSTANCE_LOGGER_AVAILABLE else None,
        )

    # ── Event handlers ────────────────────────────────────────────────────────
    def _on_settings_saved(self, settings: dict) -> None:
        _on_settings_saved_fn(self, settings)

    def _on_voice_bindings_changed(self, _bindings: dict) -> None:
        _on_voice_bindings_changed_fn(self)

    def _load_tool_states(self) -> None:
        _load_tool_states_fn(self)

    def _on_tool_state_changed(self, tool_key: str, enabled: bool) -> None:
        _on_tool_state_changed_fn(self, tool_key, enabled)

    def _log_launcher_event(self, event: str, **fields: object) -> None:
        _log_launcher_event_fn(event, runtime_path=_RUNTIME, start_time=_START_TIME, **fields)

    def _drain_assistant_events(self) -> None:
        drain_assistant_events(self, timer_single_shot=QTimer.singleShot)

    def _humanize_chat_error(self, raw: str) -> str:
        return humanize_chat_error(raw)

    @staticmethod
    def _chat_timeout_for_request(mode: str, command: str = "") -> float:
        return chat_timeout_for_request(mode, command)

    @staticmethod
    def _required_local_model_for_mode(mode: str) -> str | None:
        return required_local_model_for_mode(mode)

    @staticmethod
    def _assistant_model_id(mode: str, active_model: str = "") -> str:
        return _assistant_model_id_fn(mode, active_model)

    def _validate_mode_ready(self, mode: str) -> tuple[bool, str]:
        return _validate_mode_ready_fn(self, mode)

    def _rotate_chat_session(
        self,
        reason: str,
        mode: str = "",
        persona: str = "",
        instance: str = "",
        clear_live_history: bool = False,
    ) -> None:
        _rotate_chat_session_fn(
            self,
            reason,
            mode=mode,
            persona=persona,
            instance=instance,
            clear_live_history=clear_live_history,
        )

    def _on_chat_context_changed(self, mode: str, persona: str) -> None:
        _on_chat_context_changed_fn(self, mode, persona)

    def _apply_chat_context(self, mode: str, persona: str) -> None:
        _apply_chat_context_fn(self, mode, persona)

    def _finish_request_ui(self) -> None:
        _finish_request_ui_fn(self)

    def _on_cancel_assistant_request(self) -> None:
        _on_cancel_assistant_request_fn(self)

    def _drain_recovery_events(self) -> None:
        drain_recovery_events(self)

    def _on_tool_hint_requested(self, tool_key: str) -> None:
        _on_tool_hint_requested_fn(
            self,
            tool_key,
            settings_view_index=_SETTINGS_VIEW_INDEX,
            tool_prompt_fn=self._tool_prompt_for_home,
        )

    def _on_tool_management_requested(self, payload: dict) -> None:
        _on_tool_management_requested_fn(self, payload, settings_view_index=_SETTINGS_VIEW_INDEX)

    @staticmethod
    def _tool_prompt_for_home(tool_key: str) -> str:
        return _registry_tool_prompt(tool_key)

    def _available_instance_names(self) -> set[str]:
        snapshot = self._last_instance_snapshot if isinstance(self._last_instance_snapshot, dict) else {}
        items = snapshot.get("instances", []) if isinstance(snapshot, dict) else []
        return {
            str(item.get("name", "")).strip()
            for item in items
            if isinstance(item, dict) and bool(item.get("enabled", True)) and str(item.get("name", "")).strip()
        }

    def _preferred_builder_instance_name(self) -> str:
        snapshot = self._last_instance_snapshot if isinstance(self._last_instance_snapshot, dict) else {}
        return preferred_builder_workspace_name(self._active_instance_name, snapshot)

    def _user_test_evidence_path(self) -> Path:
        return user_test_evidence_paths(_RUNTIME)[0]

    def _user_test_evidence_summary_path(self) -> Path:
        return user_test_evidence_paths(_RUNTIME)[1]

    @staticmethod
    def _display_repo_path(path: Path | str | None) -> str:
        return display_repo_path(_RUNTIME.parent, path)

    @staticmethod
    def _latest_stress_report_path() -> Path | None:
        return latest_stress_report_path(_RUNTIME)

    def _recent_launcher_event_summaries(self, limit: int = 4) -> list[str]:
        return recent_launcher_event_summaries(_RUNTIME, limit=limit)

    @staticmethod
    def _write_user_test_evidence_summary(summary_path: Path, payload: dict[str, object]) -> str:
        return write_user_test_evidence_summary(summary_path, payload)

    def _write_user_test_evidence_pack(
        self,
        *,
        report_path: Path | None = None,
        status: str = "",
    ) -> dict[str, str]:
        return write_launcher_user_test_evidence_pack(
            self,
            report_path=report_path,
            status=status,
            runtime_dir=_RUNTIME,
            automation_report_path=_AUTOMATION_REPORT_PATH,
            validation_command=_AUTOMATION_TEST_VALIDATION_COMMAND,
        )

    def _automation_test_snapshot(
        self,
        *,
        report_path: Path | None = None,
        status: str = "",
        evidence_pack_path: str = "",
        stress_report_path: str = "",
        recent_events: str = "",
    ) -> dict[str, str]:
        return build_launcher_automation_test_snapshot(
            self,
            report_path=report_path,
            status=status,
            evidence_pack_path=evidence_pack_path,
            stress_report_path=stress_report_path,
            recent_events=recent_events,
            runtime_dir=_RUNTIME,
            automation_report_path=_AUTOMATION_REPORT_PATH,
            validation_command=_AUTOMATION_TEST_VALIDATION_COMMAND,
        )

    def _sync_automation_test_state(
        self,
        *,
        status: str = "",
        ok: bool = True,
        report_path: Path | None = None,
        persist: bool = False,
    ) -> None:
        sync_launcher_automation_test_state(
            self,
            status=status,
            ok=ok,
            report_path=report_path,
            persist=persist,
            runtime_dir=_RUNTIME,
            automation_report_path=_AUTOMATION_REPORT_PATH,
            validation_command=_AUTOMATION_TEST_VALIDATION_COMMAND,
        )

    def _queue_builder_task(
        self,
        *,
        template_id: str,
        target_ref: str,
        instance_name: str,
        announce_text: str,
    ) -> dict[str, object]:
        return _queue_builder_task_fn(
            self,
            template_id=template_id,
            target_ref=target_ref,
            instance_name=instance_name,
            announce_text=announce_text,
            automation_report_path=_AUTOMATION_REPORT_PATH,
        )

    def _write_automation_report(self) -> Path:
        return write_launcher_automation_report(
            self,
            automation_report_path=_AUTOMATION_REPORT_PATH,
            validation_command=_AUTOMATION_TEST_VALIDATION_COMMAND,
        )

    def _approve_latest_builder_task(self) -> dict[str, object]:
        return approve_latest_builder_task(self)

    def _on_builder_task_requested(self, payload: dict[str, object]) -> None:
        handle_builder_task_requested(
            self,
            payload,
            automation_report_path=_AUTOMATION_REPORT_PATH,
        )

    def _on_automation_action_requested(self, action: str) -> None:
        handle_automation_action_request(
            self,
            action,
            automation_report_path=_AUTOMATION_REPORT_PATH,
            validation_command=_AUTOMATION_TEST_VALIDATION_COMMAND,
        )

    def _initialize_embedded_agent(self, agent_id: str) -> tuple[bool, str]:
        return _initialize_embedded_agent_fn(self, agent_id)

    def _on_agent_init_requested(self, agent_id: str) -> None:
        _on_agent_init_requested_fn(self, agent_id)

    def _on_recovery_requested(self, action: str) -> None:
        start_recovery_request(self, action, thread_factory=threading.Thread)

    def _run_recovery_request(self, act: str) -> None:
        run_recovery_request(self, act)

    def _on_model_selected(self, model: str) -> None:
        _on_model_selected_fn(self, model, models_view_index=_MODELS_VIEW_INDEX)

    def _on_runtime_settings_saved(self, settings: dict) -> None:
        _on_runtime_settings_saved_fn(self, settings, models_view_index=_MODELS_VIEW_INDEX)

    def _on_search(self, query: str) -> None:
        if not query.strip():
            return
        self._on_tab_change(0)
        self._assistant_view.set_input_text(query)

    @staticmethod
    def _windows_ops_plan(action: str) -> dict[str, object]:
        return build_windows_ops_plan(action)

    @staticmethod
    def _windows_ops_recipe(action: str) -> tuple[str, list[str]]:
        plan = LauncherWindow._windows_ops_plan(action)
        return str(plan.get("label", "") or ""), [str(item) for item in plan.get("commands", []) if str(item).strip()]

    def _on_windows_ops_requested(self, action: str) -> None:
        dispatch_windows_ops_request(self, action, delayed_scheduler=QTimer.singleShot)

    def _on_home_starter_requested(self, starter_id: str, prompt: str) -> None:
        _on_home_starter_requested_fn(self, starter_id, prompt)

    def _on_assistant_command(self, command: str) -> None:
        handle_assistant_command(
            self,
            command,
            instance_logger_available=_INSTANCE_LOGGER_AVAILABLE,
            instance_log_appender=append_instance_log,
            library_chat_submission_builder=build_library_chat_submission,
            thread_factory=threading.Thread,
        )

    def _on_quick_action(self, action: str) -> None:
        plan = self._build_quick_action_plan(action)
        self._apply_quick_action_plan(plan)

    def _refresh_notification_badge(self) -> None:
        state = build_notification_badge_state(
            events_path=_RUNTIME / "launcher_events.jsonl",
            previous_mtime=self._notification_badge_mtime,
        )
        if not state.changed:
            return
        self._notification_badge_mtime = state.mtime
        self._topbar.set_notification_badge(state.count, severity=state.severity)

    def _ensure_voice_capture(self) -> tuple[bool, str]:
        return _ensure_voice_capture_fn(
            self,
            voice_capture_available=_VOICE_CAPTURE_AVAILABLE,
            voice_class=GuppyVoice,
        )

    def _on_mic_requested(self) -> None:
        _on_mic_requested_fn(self, thread_factory=threading.Thread)
