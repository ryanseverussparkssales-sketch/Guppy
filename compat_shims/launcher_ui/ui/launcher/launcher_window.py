"""
ui/launcher/launcher_window.py
Main QMainWindow shell — assembles Sidebar, TopBar, StatusPanel,
the unified launcher stack, and the bottom system strip.
"""
from __future__ import annotations

import os
import threading
import time
import urllib
from queue import Empty, SimpleQueue
from pathlib import Path

from src.guppy.launcher_application import (
    LauncherStateSnapshot,
    build_launcher_state_snapshot,
    build_library_chat_submission,
    build_windows_ops_plan,
    connector_backend_available,
    fetch_connector_inventory,
    refresh_workspace_instance_views,
    set_daily_activity,
    sync_right_tray,
    update_route_preview,
)
from src.guppy.launcher_application import launcher_connector_handlers as _conn_handlers
from src.guppy.launcher_application import launcher_instance_handlers as _inst_handlers
from src.guppy.launcher_application import launcher_library_handlers as _lib_handlers
from src.guppy.launcher_application import launcher_nav_handlers as _nav_handlers
from src.guppy.experience_config import (
    personalization_backend_available,
)
from src.guppy.runtime_application import (
    RuntimeHealthSnapshot,
)


from src.guppy.launcher_application.tool_action_registry import get_home_starter_prompt as _registry_tool_prompt
from src.guppy.launcher_application.storage_io import (
    append_instance_log,
    instance_logger_backend_available,
    read_json_dict,
    read_instance_log_tail,
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
    display_repo_path,
    event_level,
    latest_stress_report_path,
    recent_launcher_event_summaries,
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
from src.guppy.launcher_application.launcher_shell_support import (
    QuickActionPlan,
    apply_quick_action_plan as _apply_quick_action_plan_fn,
    on_home_starter_requested as _on_home_starter_requested_fn,
)
from src.guppy.launcher_application.launcher_command_policy import humanize_chat_error
from src.guppy.launcher_application.launcher_command_flow import (
    apply_chat_context as _apply_chat_context_fn,
    assistant_model_id as _assistant_model_id_fn,
    build_shell_model_loadout_summary,
    chat_timeout_for_request,
    drain_assistant_events,
    finish_request_ui as _finish_request_ui_fn,
    handle_assistant_command,
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
from src.guppy.launcher_application.windows_ops_request_flow import (
    dispatch_windows_ops_request,
)
from src.guppy.launcher_application.tools_trace_adapter import LauncherToolsTraceAdapter

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import tokens as T
from . import launcher_window_action_methods as _action_methods
from . import launcher_window_core_methods as _core_methods
from . import launcher_window_delegate_methods as _delegate_methods
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
_SETTINGS_VIEW_INDEX = _nav_handlers.SETTINGS_VIEW_INDEX
_MODELS_VIEW_INDEX = _nav_handlers.MODELS_VIEW_INDEX
_HOME_VIEW_INDEX = _nav_handlers.HOME_VIEW_INDEX
_MODELS_LIBRARY_ALIAS_INDEX = _nav_handlers.MODELS_LIBRARY_ALIAS_INDEX
connector_inventory = fetch_connector_inventory


def _write_json(path: Path, payload: dict[str, object]) -> None:
    if not write_json_atomic(path, payload):
        raise OSError(f"Failed to write JSON payload to {path}")


class LauncherWindow(LauncherWindowsOpsMixin, LauncherRuntimeControlMixin, QMainWindow):
    assistant_event_queued = Signal()
    connector_action_event_queued = Signal()

    _MAX_DEFERRED_SYSLOG_PER_TICK = 24
    _MAX_ASSISTANT_EVENTS_PER_TICK = 12
    _MAX_RECOVERY_EVENTS_PER_TICK = 12

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
        div.setStyleSheet(f"background: {T.BORDER_SOFT};")
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
        sdiv.setStyleSheet(f"background: {T.BORDER_SOFT};")
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
        self._status_divider.setStyleSheet(f"background: {T.BORDER_SOFT};")
        body.addWidget(self._status_divider)

        self._status_panel = StatusPanel(self)
        body.addWidget(self._status_panel)
        _lib_handlers.ensure_library_workflow(self)
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

    
LauncherWindow._sync_assistant_library_context = _delegate_methods.sync_assistant_library_context
LauncherWindow._wire_tools_trace_adapter = _delegate_methods.wire_tools_trace_adapter
LauncherWindow._refresh_tools_debug_surface = _delegate_methods.refresh_tools_debug_surface
LauncherWindow._drain_deferred_syslog = _delegate_methods.drain_deferred_syslog
LauncherWindow._update_route_preview = _delegate_methods.update_route_preview_method
LauncherWindow._set_daily_activity = _delegate_methods.set_daily_activity_method
LauncherWindow._sync_right_tray = _delegate_methods.sync_right_tray_method
LauncherWindow._build_sys_strip = _delegate_methods.build_sys_strip
LauncherWindow._update_sys_strip = _delegate_methods.update_sys_strip
LauncherWindow._start_status_poll = _delegate_methods.start_status_poll
LauncherWindow._poll_status = _delegate_methods.poll_status
LauncherWindow._sync_recovery_outcome = _delegate_methods.sync_recovery_outcome_method
LauncherWindow._sync_shell_model_summary = _delegate_methods.sync_shell_model_summary
LauncherWindow._on_tab_change = _delegate_methods.on_tab_change
LauncherWindow._apply_start_destination = _delegate_methods.apply_start_destination
LauncherWindow._set_status_panel_visible = _delegate_methods.set_status_panel_visible
LauncherWindow._toggle_status_panel = _delegate_methods.toggle_status_panel
LauncherWindow._toggle_sidebar = _delegate_methods.toggle_sidebar
LauncherWindow._build_quick_action_plan = _delegate_methods.build_quick_action_plan
LauncherWindow._apply_quick_action_plan = _delegate_methods.apply_quick_action_plan
LauncherWindow._instances_config_path = _delegate_methods.instances_config_path_method
LauncherWindow._instance_state_path = _delegate_methods.instance_state_path_method
LauncherWindow._default_governance_snapshot = staticmethod(_delegate_methods.default_governance_snapshot_static)
LauncherWindow._local_instance_snapshot = _delegate_methods.local_instance_snapshot
LauncherWindow._fetch_instance_snapshot = _delegate_methods.fetch_instance_snapshot_method
LauncherWindow._fetch_connector_inventory = _delegate_methods.fetch_connector_inventory_method
LauncherWindow._load_instance_history_from_logs = _delegate_methods.load_instance_history_from_logs_method
LauncherWindow._load_instance_catalog = _delegate_methods.load_instance_catalog_method
LauncherWindow._refresh_instance_views = _delegate_methods.refresh_instance_views_method
LauncherWindow._ensure_library_workflow = _delegate_methods.ensure_library_workflow
LauncherWindow._compose_library_aware_message = staticmethod(_delegate_methods.compose_library_aware_message)
LauncherWindow._on_library_context_requested = _delegate_methods.on_library_context_requested
LauncherWindow._on_library_context_cleared = _delegate_methods.on_library_context_cleared
LauncherWindow._on_library_context_focused = _delegate_methods.on_library_context_focused
LauncherWindow._on_library_context_default_requested = _delegate_methods.on_library_context_default_requested
LauncherWindow._on_library_context_opened = _delegate_methods.on_library_context_opened
LauncherWindow._on_library_context_removed = _delegate_methods.on_library_context_removed
LauncherWindow._refresh_library_surface = _delegate_methods.refresh_library_surface
LauncherWindow._on_library_root_requested = _delegate_methods.on_library_root_requested
LauncherWindow._on_library_note_requested = _delegate_methods.on_library_note_requested
LauncherWindow._on_library_note_updated = _delegate_methods.on_library_note_updated
LauncherWindow._on_library_artifact_requested = _delegate_methods.on_library_artifact_requested
LauncherWindow._on_library_artifact_updated = _delegate_methods.on_library_artifact_updated
LauncherWindow._on_library_item_deleted = _delegate_methods.on_library_item_deleted
LauncherWindow._on_assistant_reply_library_requested = _delegate_methods.on_assistant_reply_library_requested
LauncherWindow._on_assistant_reply_artifact_requested = _delegate_methods.on_assistant_reply_artifact_requested
LauncherWindow._on_latest_saved_output_attached = _delegate_methods.on_latest_saved_output_attached
LauncherWindow._on_active_context_refresh_requested = _delegate_methods.on_active_context_refresh_requested
LauncherWindow._apply_instance_switch = _delegate_methods.apply_instance_switch
LauncherWindow._bootstrap_instance_switcher = _delegate_methods.bootstrap_instance_switcher
LauncherWindow._complete_bootstrap_instance_switcher = _delegate_methods.complete_bootstrap_instance_switcher
LauncherWindow._snapshot_active_instance_history = _delegate_methods.snapshot_active_instance_history
LauncherWindow._on_instance_selected = _delegate_methods.on_instance_selected
LauncherWindow._on_instance_manager_refresh = _delegate_methods.on_instance_manager_refresh
LauncherWindow._on_instance_create_requested = _delegate_methods.on_instance_create_requested
LauncherWindow._on_instance_governance_save_requested = _delegate_methods.on_instance_governance_save_requested
LauncherWindow._on_instance_connector_binding_save_requested = _delegate_methods.on_instance_connector_binding_save_requested
LauncherWindow._perform_connector_action_request = _delegate_methods.perform_connector_action_request
LauncherWindow._apply_connector_action_feedback = _delegate_methods.apply_connector_action_feedback
LauncherWindow._run_connector_action_request = _delegate_methods.run_connector_action_request
LauncherWindow._start_connector_action_async = _delegate_methods.start_connector_action_async
LauncherWindow._start_connector_guided_link_async = _delegate_methods.start_connector_guided_link_async
LauncherWindow._drain_connector_action_events = _delegate_methods.drain_connector_action_events
LauncherWindow._on_connector_action_requested = _delegate_methods.on_connector_action_requested
LauncherWindow._on_connector_guided_link_requested = _delegate_methods.on_connector_guided_link_requested
LauncherWindow._on_instance_delete_requested = _delegate_methods.on_instance_delete_requested
LauncherWindow._on_instance_logs_requested = _delegate_methods.on_instance_logs_requested
LauncherWindow._log_launcher_event = _delegate_methods.log_launcher_event
LauncherWindow._preferred_builder_instance_name = _delegate_methods.preferred_builder_instance_name
LauncherWindow._display_repo_path = staticmethod(_delegate_methods.display_repo_path_static)
LauncherWindow._event_level = staticmethod(_core_methods.event_level_static)
LauncherWindow._bootstrap_personalization_scaffold_worker = _core_methods.bootstrap_personalization_scaffold_worker
LauncherWindow._wire_signals = _core_methods.wire_signals
LauncherWindow._refresh_personalization_state = _core_methods.refresh_personalization_state
LauncherWindow._complete_startup_phase = _core_methods.complete_startup_phase
LauncherWindow._sync_topbar_model_context = _core_methods.sync_topbar_model_context
LauncherWindow._classify_recovery_summary = staticmethod(_core_methods.classify_recovery_summary_static)
LauncherWindow._format_recovery_summary = staticmethod(_core_methods.format_recovery_summary_static)
LauncherWindow._push_recovery_outcome = _core_methods.push_recovery_outcome_method
LauncherWindow._resolve_stack_index = staticmethod(_core_methods.resolve_stack_index_static)
LauncherWindow._visible_nav_index = staticmethod(_core_methods.visible_nav_index_static)
LauncherWindow._refresh_first_run_banner = _core_methods.refresh_first_run_banner
LauncherWindow._on_first_run_action_requested = _core_methods.on_first_run_action_requested
LauncherWindow._build_launcher_state_snapshot = _core_methods.build_launcher_state_snapshot_method
LauncherWindow._on_settings_saved = _core_methods.on_settings_saved
LauncherWindow._on_voice_bindings_changed = _core_methods.on_voice_bindings_changed
LauncherWindow._load_tool_states = _core_methods.load_tool_states
LauncherWindow._on_tool_state_changed = _core_methods.on_tool_state_changed
LauncherWindow._drain_assistant_events = _core_methods.drain_assistant_events_method
LauncherWindow._humanize_chat_error = _core_methods.humanize_chat_error_method
LauncherWindow._chat_timeout_for_request = staticmethod(_core_methods.chat_timeout_for_request_static)
LauncherWindow._required_local_model_for_mode = staticmethod(_core_methods.required_local_model_for_mode_static)
LauncherWindow._assistant_model_id = staticmethod(_core_methods.assistant_model_id_static)
LauncherWindow._validate_mode_ready = _core_methods.validate_mode_ready
LauncherWindow._rotate_chat_session = _core_methods.rotate_chat_session
LauncherWindow._on_chat_context_changed = _core_methods.on_chat_context_changed
LauncherWindow._apply_chat_context = _core_methods.apply_chat_context
LauncherWindow._finish_request_ui = _core_methods.finish_request_ui
LauncherWindow._on_cancel_assistant_request = _core_methods.on_cancel_assistant_request
LauncherWindow._drain_recovery_events = _core_methods.drain_recovery_events_method
LauncherWindow._on_tool_hint_requested = _core_methods.on_tool_hint_requested
LauncherWindow._on_tool_management_requested = _core_methods.on_tool_management_requested
LauncherWindow._initialize_embedded_agent = _core_methods.initialize_embedded_agent
LauncherWindow._on_agent_init_requested = _core_methods.on_agent_init_requested
LauncherWindow._on_model_selected = _core_methods.on_model_selected
LauncherWindow._on_runtime_settings_saved = _core_methods.on_runtime_settings_saved
LauncherWindow._shell_model_loadout_summary = staticmethod(build_shell_model_loadout_summary)
LauncherWindow._tool_prompt_for_home = staticmethod(_core_methods.tool_prompt_for_home_static)
LauncherWindow._available_instance_names = _action_methods.available_instance_names
LauncherWindow._user_test_evidence_path = _action_methods.user_test_evidence_path
LauncherWindow._user_test_evidence_summary_path = _action_methods.user_test_evidence_summary_path
LauncherWindow._latest_stress_report_path = staticmethod(_action_methods.latest_stress_report_path_static)
LauncherWindow._recent_launcher_event_summaries = _action_methods.recent_launcher_event_summaries_method
LauncherWindow._write_user_test_evidence_summary = staticmethod(_action_methods.write_user_test_evidence_summary_static)
LauncherWindow._write_user_test_evidence_pack = _action_methods.write_user_test_evidence_pack
LauncherWindow._automation_test_snapshot = _action_methods.automation_test_snapshot
LauncherWindow._sync_automation_test_state = _action_methods.sync_automation_test_state
LauncherWindow._queue_builder_task = _action_methods.queue_builder_task
LauncherWindow._write_automation_report = _action_methods.write_automation_report
LauncherWindow._approve_latest_builder_task = _action_methods.approve_latest_builder_task_method
LauncherWindow._on_builder_task_requested = _action_methods.on_builder_task_requested
LauncherWindow._on_automation_action_requested = _action_methods.on_automation_action_requested
LauncherWindow._on_recovery_requested = _action_methods.on_recovery_requested
LauncherWindow._run_recovery_request = _action_methods.run_recovery_request_method
LauncherWindow._on_search = _action_methods.on_search
LauncherWindow._windows_ops_plan = staticmethod(_action_methods.windows_ops_plan_static)
LauncherWindow._windows_ops_recipe = staticmethod(_action_methods.windows_ops_recipe_static)
LauncherWindow._on_windows_ops_requested = _action_methods.on_windows_ops_requested
LauncherWindow._on_home_starter_requested = _action_methods.on_home_starter_requested
LauncherWindow._on_assistant_command = _action_methods.on_assistant_command
LauncherWindow._on_quick_action = _action_methods.on_quick_action
LauncherWindow._refresh_notification_badge = _action_methods.refresh_notification_badge
LauncherWindow._ensure_voice_capture = _action_methods.ensure_voice_capture
LauncherWindow._on_mic_requested = _action_methods.on_mic_requested
LauncherWindow._launch_start_time = _START_TIME
