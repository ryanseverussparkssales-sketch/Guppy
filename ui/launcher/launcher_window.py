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
    build_launcher_automation_test_snapshot,
    preferred_builder_workspace_name,
    sync_launcher_automation_test_state,
    user_test_evidence_paths,
    write_launcher_automation_report,
    write_launcher_user_test_evidence_pack,
)
from src.guppy.launcher_application.first_run_wizard import FirstRunWizard
from src.guppy.launcher_application.status_poll import (
    build_launcher_status_poll_snapshot,
    fetch_api_status,
)
from src.guppy.launcher_application.launcher_shell_support import (
    QuickActionPlan,
    build_notification_badge_state,
    build_quick_action_plan,
    build_runtime_badge_state,
)
from src.guppy.launcher_application.launcher_command_flow import (
    build_shell_model_loadout_summary,
    derive_topbar_model_context,
    handle_assistant_command,
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
        try:
            self._scaffold_created = ensure_personalization_scaffold()
            if self._scaffold_created:
                created = ",".join(sorted(self._scaffold_created.keys()))
                self._deferred_syslog.put(f"personalization scaffold ready: {created}")
                self._log_launcher_event("personalization_scaffold_created", created=list(self._scaffold_created.keys()))
            self._log_launcher_event("startup_phase", phase="personalization_scaffold_thread_complete")
        except Exception as e:
            self._deferred_syslog.put(f"personalization scaffold failed: {e}")
            self._log_launcher_event("personalization_scaffold_error", error=str(e))
            self._log_launcher_event("startup_phase", phase="personalization_scaffold_thread_error", error=str(e))

    def _wire_signals(self) -> None:
        """Composition helper — all inter-widget signal connections in one named seam."""
        self._sidebar.tab_changed.connect(self._on_tab_change)
        self._topbar.nav_requested.connect(self._on_tab_change)
        self._settings_hub_view.open_diagnostics_requested.connect(lambda: self._on_tab_change(_SETTINGS_VIEW_INDEX))
        self._settings_hub_view.open_recovery_requested.connect(lambda: self._on_tab_change(_SETTINGS_VIEW_INDEX))
        self._settings_hub_view.open_terminal_requested.connect(lambda: self._on_tab_change(_SETTINGS_VIEW_INDEX))
        self._settings_hub_view.open_connectors_requested.connect(lambda: self._on_tab_change(_SETTINGS_VIEW_INDEX))
        self._settings_hub_view.open_system_requested.connect(lambda: self._on_tab_change(_SETTINGS_VIEW_INDEX))
        self._settings_view.settings_saved.connect(self._on_settings_saved)
        self._tools_view.tool_state_changed.connect(self._on_tool_state_changed)
        self._tools_view.tool_hint_requested.connect(self._on_tool_hint_requested)
        self._tools_view.tool_management_requested.connect(self._on_tool_management_requested)
        self._tools_view.builder_task_requested.connect(self._on_builder_task_requested)
        self._status_panel.tool_requested.connect(self._on_tool_hint_requested)
        self._settings_hub_view.recovery_requested.connect(self._on_recovery_requested)
        self._settings_hub_view.windows_ops_requested.connect(self._on_windows_ops_requested)
        self._settings_hub_view.connector_action_requested.connect(self._on_connector_action_requested)
        self._settings_hub_view.connector_guided_link_requested.connect(self._on_connector_guided_link_requested)
        self._settings_hub_view.automation_action_requested.connect(self._on_automation_action_requested)
        self._settings_hub_view.terminal_recipe_finished.connect(self._on_terminal_recipe_finished)
        self._models_hub_view.model_selected.connect(self._on_model_selected)
        self._models_hub_view.runtime_settings_saved.connect(self._on_runtime_settings_saved)
        self._models_hub_view.bindings_changed.connect(self._on_voice_bindings_changed)
        self._topbar.search_submitted.connect(self._on_search)
        self._topbar.quick_action.connect(self._on_quick_action)
        self._topbar.launcher_context_requested.connect(lambda: self._on_quick_action("toggle_drawer"))
        self._assistant_view.command_submitted.connect(self._on_assistant_command)
        self._assistant_view.starter_requested.connect(self._on_home_starter_requested)
        self._assistant_view.cancel_requested.connect(self._on_cancel_assistant_request)
        self._assistant_view.mic_requested.connect(self._on_mic_requested)
        self._assistant_view.assistant_reply_library_requested.connect(self._on_assistant_reply_library_requested)
        self._assistant_view.assistant_reply_artifact_requested.connect(self._on_assistant_reply_artifact_requested)
        self._assistant_view.latest_saved_output_attach_requested.connect(self._on_latest_saved_output_attached)
        self._assistant_view.latest_saved_output_library_requested.connect(self._on_library_context_opened)
        self._assistant_view.active_context_refresh_requested.connect(self._on_active_context_refresh_requested)
        self._assistant_view.active_context_clear_requested.connect(self._on_library_context_cleared)
        self._assistant_view.active_context_focus_requested.connect(self._on_library_context_focused)
        self._assistant_view.active_context_default_requested.connect(self._on_library_context_default_requested)
        self._assistant_view.active_context_library_requested.connect(self._on_library_context_opened)
        self._assistant_view.active_context_remove_requested.connect(self._on_library_context_removed)
        self._assistant_view.first_run_action_requested.connect(self._on_first_run_action_requested)
        self.assistant_event_queued.connect(self._drain_assistant_events)
        self.connector_action_event_queued.connect(self._drain_connector_action_events)
        self._assistant_view.chat_context_changed.connect(self._on_chat_context_changed)
        self._assistant_view.launcher_summary_changed.connect(self._topbar.set_launcher_summary)
        self._library_view.context_requested.connect(self._on_library_context_requested)
        self._library_view.approved_root_requested.connect(self._on_library_root_requested)
        self._library_view.note_requested.connect(self._on_library_note_requested)
        self._library_view.note_updated.connect(self._on_library_note_updated)
        self._library_view.artifact_requested.connect(self._on_library_artifact_requested)
        self._library_view.artifact_updated.connect(self._on_library_artifact_updated)
        self._library_view.library_item_delete_requested.connect(self._on_library_item_deleted)
        self._instance_manager_view.refresh_requested.connect(self._on_instance_manager_refresh)
        self._instance_manager_view.activate_requested.connect(self._on_instance_selected)
        self._instance_manager_view.create_requested.connect(self._on_instance_create_requested)
        self._instance_manager_view.governance_save_requested.connect(self._on_instance_governance_save_requested)
        self._instance_manager_view.connector_binding_save_requested.connect(self._on_instance_connector_binding_save_requested)
        self._instance_manager_view.delete_requested.connect(self._on_instance_delete_requested)
        self._instance_manager_view.logs_requested.connect(self._on_instance_logs_requested)
        self._topbar.instance_selected.connect(self._on_instance_selected)
        self._status_panel.agent_init_requested.connect(self._on_agent_init_requested)

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
        try:
            persona_config = load_persona_config() if _PERSONALIZATION_BOOTSTRAP_AVAILABLE else {}
            voice_bindings = load_voice_bindings() if _PERSONALIZATION_BOOTSTRAP_AVAILABLE else {}
            persona_choices = list_persona_choices(persona_config)
            target_persona = preferred_persona or self._assistant_view.chat_context()[1]
            active_model_id = self._assistant_model_id(self._assistant_view.selected_mode())
            voice_choice = resolve_voice_binding(
                persona_id=target_persona,
                model_id=active_model_id,
                voice_bindings=voice_bindings,
            )
            empty_state = PersonalizationState.empty()
            personalization_state = PersonalizationState(
                persona_options=build_persona_options(persona_choices) or empty_state.persona_options,
                voice_options=tuple(voice_option_choices(voice_bindings)) or empty_state.voice_options,
                voice_summary=voice_binding_summary(voice_choice),
                model_id=active_model_id,
                voice_choice=voice_choice if isinstance(voice_choice, dict) else {},
            )
            self._assistant_view.set_persona_options(list(personalization_state.persona_options), selected=target_persona)
            self._instance_manager_view.set_persona_options(list(personalization_state.persona_options), selected=target_persona)
            self._instance_manager_view.set_voice_options(list(personalization_state.voice_options), selected="default")
            self._models_hub_view.refresh_voice_assignments()
            self._assistant_view.set_runtime_facts(
                profile=self._assistant_view._cb_profile.currentText().strip().lower() or "standard",
                model=personalization_state.model_id,
                voice=personalization_state.voice_summary,
                latency="-",
                last_query=self._last_command or "-",
            )
            self._settings_hub_view.set_daily_context_runtime(self._assistant_view._runtime_facts.text())
        except Exception as exc:
            self._status_panel.append_syslog(f"personalization refresh failed: {exc}")

    def _update_route_preview(self, text: str = "") -> None:
        update_route_preview(self, text)
        self._sync_topbar_model_context()

    def _set_daily_activity(self, text: str) -> None:
        set_daily_activity(self, text)

    def _sync_right_tray(self, active_payload: dict[str, object]) -> None:
        sync_right_tray(self, active_payload)

    # ── Bottom strip ──────────────────────────────────────────────────────────
    def _build_sys_strip(self) -> QFrame:
        strip = QFrame()
        strip.setFixedHeight(26)
        strip.setObjectName("sys_strip")
        strip.setStyleSheet(
            f"QFrame#sys_strip {{"
            f"  background-color: {T.BG0};"
            f"  border-top: 1px solid {T.BORDER};"
            f"}}"
        )

        def _chip(text: str, color: str = T.DIM) -> QLabel:
            lbl = QLabel(text)
            lbl.setStyleSheet(
                f"color: {color}; font-family: '{T.FF_MONO}';"
                f"font-size: {T.FS_TINY}pt; letter-spacing: 1px; padding: 0 8px;"
            )
            return lbl

        def _sep() -> QFrame:
            f = QFrame()
            f.setFixedSize(1, 14)
            f.setStyleSheet(f"background: {T.BORDER};")
            return f

        row = QHBoxLayout(strip)
        row.setContentsMargins(12, 0, 12, 0)
        row.setSpacing(0)

        self._strip_uptime  = _chip("UPTIME: —")
        self._strip_cpu     = _chip("CPU: —")
        self._strip_mem     = _chip("MEM: —")
        self._strip_tokens  = _chip("BUFFER: — tok")
        self._strip_status  = _chip("STATUS: NOMINAL", T.GREEN)

        row.addWidget(self._strip_uptime)
        row.addWidget(_sep())
        row.addWidget(self._strip_cpu)
        row.addWidget(_sep())
        row.addWidget(self._strip_mem)
        row.addWidget(_sep())
        row.addWidget(self._strip_tokens)
        row.addStretch()
        row.addWidget(self._strip_status)

        return strip

    def _update_sys_strip(self) -> None:
        # Uptime
        elapsed = int(time.monotonic() - _START_TIME)
        h, m = divmod(elapsed // 60, 60)
        s = elapsed % 60
        self._strip_uptime.setText(f"UPTIME: {h:02d}:{m:02d}:{s:02d}")

        # CPU + MEM via psutil (optional)
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            self._strip_cpu.setText(f"CPU: {cpu:.0f}%")
            self._strip_mem.setText(f"MEM: {mem.percent:.0f}%")
            status_ok = cpu < 85 and mem.percent < 85
            self._strip_status.setText("STATUS: NOMINAL" if status_ok else "STATUS: HIGH LOAD")
            self._strip_status.setStyleSheet(
                f"color: {T.GREEN if status_ok else T.ERROR}; font-family: '{T.FF_MONO}';"
                f"font-size: {T.FS_TINY}pt; letter-spacing: 1px; padding: 0 8px;"
            )
        except Exception:
            pass  # psutil unavailable — uptime still shows

        # Token buffer from scorecard if available
        try:
            scorecard = _RUNTIME / "router_scorecard.jsonl"
            if scorecard.exists():
                lines = scorecard.read_text(encoding="utf-8").strip().splitlines()
                if lines:
                    last = json.loads(lines[-1])
                    tokens = last.get("input_tokens", last.get("total_tokens", "—"))
                    self._strip_tokens.setText(f"BUFFER: {tokens} tok")
        except Exception:
            pass

        # Startup summary for quick freeze-risk visibility.
        if not self._startup_first_poll_ok:
            self._strip_status.setText("STATUS: STARTING")
            self._strip_status.setStyleSheet(
                f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
                f"font-size: {T.FS_TINY}pt; letter-spacing: 1px; padding: 0 8px;"
            )
        elif self._startup_over_budget:
            self._strip_status.setText("STATUS: STARTUP WARN")
            self._strip_status.setStyleSheet(
                f"color: {T.ERROR}; font-family: '{T.FF_MONO}';"
                f"font-size: {T.FS_TINY}pt; letter-spacing: 1px; padding: 0 8px;"
            )

    # ── Status polling ────────────────────────────────────────────────────────
    def _start_status_poll(self) -> None:
        self._status_poll_timer = QTimer(self)
        self._status_poll_timer.timeout.connect(self._poll_status)
        self._status_poll_timer.start(3000)
        QTimer.singleShot(0, self._poll_status)

    def _poll_status(self) -> None:
        poll_t0 = time.monotonic()
        self._drain_deferred_syslog()
        self._drain_assistant_events()
        self._drain_recovery_events()
        self._update_sys_strip()

        # Heartbeats
        guppy_online = (_RUNTIME / "guppy.heartbeat").exists()

        # Guppy status
        gs = read_json_dict(_RUNTIME / "guppy.status")
        gs["guppy_online"] = guppy_online
        api_status = fetch_api_status(self._http_json)

        voice_summary = str(gs.get("tts_engine", os.environ.get("GUPPY_TTS_ENGINE", "edge")) or "edge")
        active_model_id = self._assistant_model_id(
            self._assistant_view.selected_mode(),
            str(gs.get("active_model", "") or ""),
        )
        try:
            if _PERSONALIZATION_BOOTSTRAP_AVAILABLE:
                voice_summary = voice_binding_summary(
                    resolve_voice_binding(
                        persona_id=self._assistant_view.chat_context()[1],
                        model_id=active_model_id,
                        voice_bindings=load_voice_bindings(),
                    )
                )
        except Exception:
            pass

        poll_snapshot = build_launcher_status_poll_snapshot(
            launcher_status=gs,
            api_status=api_status,
            environment=os.environ,
            active_instance_name=self._active_instance_name,
            last_instance_snapshot=self._last_instance_snapshot,
            embedded_online=self._embedded_online,
            fallback_last_query=self._last_command,
            voice_summary=voice_summary,
            route_evidence=self._assistant_view._route_facts.text(),
        )
        data = poll_snapshot.data

        self._status_panel.update_status(data)
        self._assistant_view.set_runtime_facts(
            profile=str(data.get("profile", "standard") or "standard"),
            model=active_model_id,
            voice=voice_summary,
            latency=str(data.get("latency", "-") or "-"),
            last_query=str(data.get("last_query", "-") or "-"),
        )
        self._settings_hub_view.set_daily_context_runtime(self._assistant_view._runtime_facts.text())
        self._settings_hub_view.set_daily_context_route(self._assistant_view._route_facts.text())
        self._sync_topbar_model_context(main_model=active_model_id)

        # Update agent cards
        guppy_load = poll_snapshot.guppy_load
        guppy_online = poll_snapshot.guppy_online

        self._status_panel.update_agent_status("guppy", guppy_online, "—", guppy_load)
        self._assistant_view.set_background_status(
            poll_snapshot.background_summary,
            healthy=guppy_online,
        )
        self._settings_hub_view.set_daily_context_recovery(
            f"Recovery: {'stable' if guppy_online else 'needs attention'}",
            ok=guppy_online,
        )
        runtime_health = poll_snapshot.runtime_health
        self._runtime_health_snapshot = runtime_health
        startup_summary = summarize_startup_readiness(
            poll_snapshot.api_status.get("startup_readiness", {})
        )
        runtime_badge = build_runtime_badge_state(
            api_status=poll_snapshot.api_status,
            runtime_overall=runtime_health.overall,
            startup_summary=startup_summary,
            startup_first_poll_ok=self._startup_first_poll_ok,
            startup_over_budget=bool(self._startup_over_budget),
        )
        self._topbar.set_runtime_status(
            runtime_badge.label,
            detail=runtime_badge.detail,
            severity=runtime_badge.severity,
        )
        self._models_hub_view.set_status_snapshot(poll_snapshot.api_status)
        self._settings_hub_view.set_status_snapshot(poll_snapshot.settings_status_snapshot)
        windows_snapshot = self._settings_hub_view.windows_ops_snapshot()
        windows_snapshot_signature = self._payload_signature(windows_snapshot)
        if windows_snapshot_signature != self._last_windows_snapshot_signature:
            self._settings_hub_view.set_windows_snapshot(windows_snapshot)
            self._last_windows_snapshot_signature = windows_snapshot_signature
        self._refresh_notification_badge()
        self._sync_recovery_outcome()
        # Avoid competing with an active chat turn for the periodic instance refresh.
        # The next idle poll will resync the workspace snapshot.
        if not self._request_in_flight and self._bootstrap_instance_refresh_complete:
            self._refresh_instance_views(load_logs=False)
        if not self._startup_logged_first_poll:
            self._startup_logged_first_poll = True
            self._startup_first_poll_ok = True
            self._complete_startup_phase("first_status_poll", start_at=self._startup_phase_started["window_init"])
            self._log_launcher_event("startup_phase", phase="first_status_poll_complete")
            if self._startup_over_budget:
                summary = ", ".join(self._startup_over_budget)
                self._status_panel.append_syslog(f"startup budget warning: {summary}")
            else:
                self._status_panel.append_syslog(
                    f"startup budget OK (<={self._startup_budget_ms}ms phases)"
                )

        if (
            not self._auth_self_check_ok
            and not self._auth_self_check_inflight
            and bool(api_status)
            and (time.monotonic() - self._auth_self_check_last_attempt) >= 5.0
        ):
            self._auth_self_check_inflight = True
            self._auth_self_check_last_attempt = time.monotonic()
            threading.Thread(target=self._run_auth_self_check, daemon=True).start()

        poll_ms = int((time.monotonic() - poll_t0) * 1000)
        if poll_ms > self._startup_budget_ms:
            now = time.monotonic()
            if now - self._last_poll_warn_ts > 10.0:
                self._last_poll_warn_ts = now
                self._log_launcher_event(
                    "ui_poll_over_budget",
                    poll_ms=poll_ms,
                    budget_ms=self._startup_budget_ms,
                )
                self._status_panel.append_syslog(
                    f"ui poll over budget: {poll_ms}ms (budget {self._startup_budget_ms}ms)"
                )

    def _complete_startup_phase(self, phase: str, start_at: float | None = None) -> None:
        started = start_at if start_at is not None else self._startup_phase_started.get(phase, time.monotonic())
        dur_ms = int((time.monotonic() - started) * 1000)
        self._startup_phase_durations_ms[phase] = dur_ms
        self._log_launcher_event(
            "startup_phase_duration",
            phase=phase,
            duration_ms=dur_ms,
            budget_ms=self._startup_budget_ms,
            over_budget=dur_ms > self._startup_budget_ms,
        )
        if dur_ms > self._startup_budget_ms:
            self._startup_over_budget.append(f"{phase}:{dur_ms}ms")
            self._log_launcher_event(
                "startup_phase_over_budget",
                phase=phase,
                duration_ms=dur_ms,
                budget_ms=self._startup_budget_ms,
            )
            self._status_panel.append_syslog(
                f"startup phase over budget: {phase}={dur_ms}ms"
            )

    def _sync_recovery_outcome(self) -> None:
        sync_recovery_outcome(self, runtime_path=_RUNTIME, read_jsonl_tail=read_jsonl_tail)

    def _sync_topbar_model_context(
        self,
        *,
        main_model: str = "",
        support_model: str = "",
    ) -> None:
        setter = getattr(self._topbar, "set_model_context", None)
        if not callable(setter):
            return
        route_text = str(getattr(self._assistant_view, "_route_facts", QLabel("")).text() if hasattr(self, "_assistant_view") else "")
        setter(
            **derive_topbar_model_context(
                route_text=route_text,
                runtime=self._runtime_health_snapshot.local_runtime,
                main_model=main_model,
                support_model=support_model,
            )
        )

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
        if plan.toggle_sidebar:
            self._toggle_sidebar()
            return True
        if plan.toggle_drawer:
            self._toggle_status_panel()
            return True
        if plan.tab_index is not None:
            self._on_tab_change(plan.tab_index)
        if plan.operator_logs_focus is not None:
            self._settings_hub_view.focus_operator_logs(
                plan.operator_logs_focus.level,
                note=plan.operator_logs_focus.note,
            )
        if plan.terminal_focus is not None:
            self._settings_hub_view.focus_terminal(note=plan.terminal_focus.note)
        if plan.daily_activity:
            self._set_daily_activity(plan.daily_activity)
        if plan.syslog:
            self._status_panel.append_syslog(plan.syslog)
        if isinstance(plan.launcher_event, dict):
            self._log_launcher_event("quick_action", **plan.launcher_event)
        if plan.unsupported_message:
            self._status_panel.append_syslog(plan.unsupported_message)
            return False
        return True

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
        assistant = getattr(self, "_assistant_view", None)
        if assistant is None or not hasattr(assistant, "set_first_run_status"):
            return
        wizard = FirstRunWizard(workspace_id=self._active_instance_name)
        if wizard.should_skip():
            assistant.set_first_run_status(visible=False)
            return

        checkpoint1 = wizard.state.get_status(1).value
        checkpoint2 = wizard.state.get_status(2).value
        checkpoint3 = wizard.state.get_status(3).value

        if checkpoint1 != "passed":
            summary = "Finish desktop install checks first."
            detail = "Open Settings to review install readiness, accounts, logs, and setup guidance before deeper model work."
        elif checkpoint2 != "passed":
            summary = "Choose and verify a local model runtime next."
            detail = "Open Models to confirm Ollama, LM Studio, or the local harness path, then come back here for a short test ask."
        else:
            summary = "Send one short test ask from Home to prove first success."
            detail = "The final checkpoint only closes after a real request verifier path succeeds, so keep this step honest."

        assistant.set_first_run_status(
            visible=True,
            summary=summary,
            detail=detail,
            install_status=checkpoint1,
            model_status=checkpoint2,
            request_status=checkpoint3,
        )

    def _on_first_run_action_requested(self, action: str) -> None:
        target = (action or "").strip().lower()
        if target == "settings":
            self._on_tab_change(_SETTINGS_VIEW_INDEX)
            self._set_daily_activity("First-run guidance opened Settings")
            return
        if target == "models":
            self._on_tab_change(_MODELS_VIEW_INDEX)
            self._set_daily_activity("First-run guidance opened Models")

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
        profile = settings.get("runtime_profile", "standard")
        persona_name = str(settings.get("active_persona_name", "")).strip()
        self._assistant_view.apply_settings(settings)
        self._refresh_personalization_state(preferred_persona=str(settings.get("active_persona_id", "")).strip())
        detail = f"Settings saved for {str(profile).upper()} profile"
        if persona_name:
            detail += f" · persona {persona_name}"
        self._set_daily_activity(detail)
        self._status_panel.append_syslog(detail.lower())

    def _on_voice_bindings_changed(self, _bindings: dict) -> None:
        self._refresh_personalization_state()
        self._set_daily_activity("Voice bindings updated")
        self._status_panel.append_syslog("voice bindings updated")

    def _load_tool_states(self) -> None:
        path = self._tool_state_path()
        if not path.exists():
            self._refresh_tools_debug_surface()
            return
        try:
            states = read_json_dict(path)
            if isinstance(states, dict):
                self._tools_view.set_states({k: bool(v) for k, v in states.items()})
                self._status_panel.append_syslog("tools state restored")
                self._log_launcher_event("tools_state_restored", count=len(states))
        except Exception as e:
            self._status_panel.append_syslog(f"tools state restore failed: {e}")
            self._log_launcher_event("tools_state_restore_error", error=str(e))
        self._refresh_tools_debug_surface()

    def _on_tool_state_changed(self, tool_key: str, enabled: bool) -> None:
        states = self._tools_view.get_states()
        try:
            path = self._tool_state_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(states, indent=2), encoding="utf-8")
            self._status_panel.append_syslog(
                f"tool {tool_key} -> {'ON' if enabled else 'OFF'}"
            )
            self._log_launcher_event(
                "tool_state_changed",
                tool=tool_key,
                enabled=enabled,
            )
        except Exception as e:
            self._status_panel.append_syslog(f"tool state save failed: {e}")
            self._log_launcher_event(
                "tool_state_save_error",
                tool=tool_key,
                enabled=enabled,
                error=str(e),
            )
        self._refresh_tools_debug_surface()

    def _log_launcher_event(self, event: str, **fields: object) -> None:
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "source": "launcher",
            "event": event,
            "uptime_s": round(time.monotonic() - _START_TIME, 3),
            **fields,
        }
        try:
            append_jsonl(_RUNTIME / "launcher_events.jsonl", record)
        except Exception:
            try:
                path = _RUNTIME / "launcher_events.jsonl"
                with path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=True) + "\n")
            except Exception:
                pass

    def _drain_assistant_events(self) -> None:
        processed = 0
        while processed < self._MAX_ASSISTANT_EVENTS_PER_TICK:
            try:
                kind, payload, seq = self._assistant_events.get_nowait()
            except Empty:
                break
            if kind == "voice_input":
                self._mic_capture_active = False
                self._assistant_view.set_mic_capture_state(False)
                text = str(payload or "").strip()
                if text:
                    self._set_daily_activity(f"Voice captured: {text[:72]}")
                    self._status_panel.append_syslog("voice capture ready")
                    self._on_assistant_command(text)
                else:
                    self._assistant_view.set_status("Ready")
                processed += 1
                continue
            if kind == "voice_error":
                self._mic_capture_active = False
                self._assistant_view.set_mic_capture_state(False)
                self._assistant_view.set_status("Ready")
                self._assistant_view.add_system_message(str(payload or "Voice capture failed."))
                self._status_panel.append_syslog(f"voice capture failed: {str(payload or '')[:120]}")
                processed += 1
                continue
            if seq in self._canceled_request_seqs:
                self._canceled_request_seqs.discard(seq)
                processed += 1
                continue
            # Discard stale responses from superseded requests.
            if seq != self._active_request_seq:
                processed += 1
                continue
            if kind == "assistant":
                self._assistant_view.set_status("Ready")
                self._finish_request_ui()
                self._assistant_view.add_assistant_message(payload)
                self._on_instance_logs_requested(self._active_instance_name, quiet=True)
            elif kind == "error":
                self._assistant_view.set_status("Error")
                self._finish_request_ui()
                self._assistant_view.add_assistant_message(self._humanize_chat_error(payload))
                QTimer.singleShot(2500, lambda: self._assistant_view.set_status("Ready"))
                self._status_panel.append_syslog(f"chat error: {payload[:120]}")
                self._on_instance_logs_requested(self._active_instance_name, quiet=True)
            processed += 1

    def _humanize_chat_error(self, raw: str) -> str:
        txt = (raw or "").strip()
        low = txt.lower()
        if "still warming up" in low or "restarted" in low and "retry now" in low:
            return "The local service restarted, but the first reply is still warming up. Please retry now."
        if "http 401" in low or "unauthorized" in low or "jwt_expired" in low:
            return "Authentication expired. Please retry now."
        if "http 403" in low:
            return "This action is not permitted right now."
        if "http 429" in low:
            return "Too many requests at once. Please wait a few seconds and retry."
        if "timed out" in low or "timeout" in low:
            return "The request timed out before a response was received. Please try again."
        if "network error" in low or "connection refused" in low:
            return "Could not reach the local API service. Check that the API is running, then retry."
        if ("local-only mode failed" in low or "local-only retry failed" in low
                or "ollama" in low and ("not running" in low or "unavailable" in low or "could not contact" in low)):
            return "Local model service is unavailable. Start Ollama or switch to Claude mode."
        if "ollama" in low and ("not running" in low or "unavailable" in low or "could not contact" in low):
            return "Local model service is unavailable. Start Ollama or switch to Claude mode."
        return "The assistant request failed. Please retry."

    @staticmethod
    def _chat_timeout_for_request(mode: str, command: str = "") -> float:
        m = (mode or "auto").strip().lower()
        base = 25.0 if m in {"claude", "auto", "teaching"} else 35.0 if m in {"local", "ollama", "code", "vault"} else 30.0
        text = (command or "").strip().lower()
        if not text:
            return base
        if any(
            token in text
            for token in (
                "diagnostic",
                "diagnose",
                "health check",
                "system check",
                "audit",
                "scan",
                "debug",
                "trace",
                "investigate",
            )
        ):
            return max(base, 60.0)
        if any(token in text for token in ("review", "triage", "analyze", "search the repo", "walk the codebase")):
            return max(base, 45.0)
        if len(text) > 220:
            return max(base, 45.0)
        return base

    @staticmethod
    def _required_local_model_for_mode(mode: str) -> str | None:
        m = (mode or "").strip().lower()
        if m in {"local", "ollama"}:
            return (os.environ.get("OLLAMA_MODEL", "guppy") or "guppy").strip()
        if m == "teaching":
            return (os.environ.get("GUPPY_LOCAL_TEACH_MODEL", "guppy-teach") or "guppy-teach").strip()
        if m == "code":
            return (os.environ.get("GUPPY_LOCAL_CODE_MODEL", "guppy-code") or "guppy-code").strip()
        if m == "vault":
            return (os.environ.get("GUPPY_LOCAL_VAULT_MODEL", "vault-scraper") or "vault-scraper").strip()
        return None

    @staticmethod
    def _assistant_model_id(mode: str, active_model: str = "") -> str:
        candidate = str(active_model or "").strip()
        if candidate and candidate not in {"-", "—"}:
            return candidate

        normalized_mode = (mode or "auto").strip().lower()
        if normalized_mode == "claude":
            return (
                os.environ.get("ANTHROPIC_HAIKU_MODEL", "claude-haiku-4-5-20251001")
                or "claude-haiku-4-5-20251001"
            ).strip()

        required_local = LauncherWindow._required_local_model_for_mode(normalized_mode)
        if required_local:
            return required_local

        return (os.environ.get("OLLAMA_MODEL", "guppy") or "guppy").strip()

    def _validate_mode_ready(self, mode: str) -> tuple[bool, str]:
        model = LauncherWindow._required_local_model_for_mode(mode)
        if not model:
            return True, ""
        try:
            from guppy_core.network_utils import check_ollama
            ok, err = check_ollama(model)
            if ok:
                return True, ""
            return False, f"{mode.upper()} mode requires local model '{model}'. {err.splitlines()[0]}"
        except Exception:
            return False, f"{mode.upper()} mode requires local model '{model}', but readiness could not be verified."

    def _rotate_chat_session(
        self,
        reason: str,
        mode: str = "",
        persona: str = "",
        instance: str = "",
        clear_live_history: bool = False,
    ) -> None:
        inst = (instance or self._active_instance_name or "guppy-primary").strip()
        suffix = f"-{inst}"
        if mode or persona:
            suffix += f"-{mode}-{persona}"
        self._chat_session_id = f"launcher-{int(time.time())}{suffix}"
        self._assistant_view.set_session_id(self._chat_session_id)
        if clear_live_history:
            self._assistant_view.reset_live_history()
        self._topbar.set_session(f"{inst} {self._chat_session_id[-8:]}")
        self._log_launcher_event(
            "chat_session_rotated",
            reason=reason,
            session_id=self._chat_session_id,
            instance=inst,
            mode=mode,
            persona=persona,
        )

    def _on_chat_context_changed(self, mode: str, persona: str) -> None:
        self._refresh_personalization_state(preferred_persona=persona)
        self._update_route_preview(self._last_command)
        if self._request_in_flight:
            self._pending_chat_context = (mode, persona)
            self._status_panel.append_syslog(f"chat context queued until current request completes: {persona}/{mode}")
            return
        self._apply_chat_context(mode, persona)

    def _apply_chat_context(self, mode: str, persona: str) -> None:
        self._rotate_chat_session(
            "context_changed",
            mode=mode,
            persona=persona,
            instance=self._active_instance_name,
            clear_live_history=True,
        )
        self._assistant_view.add_system_message(
            f"New chat session started for {persona.upper()} / {mode.upper()}."
        )
        self._status_panel.append_syslog(f"chat session rotated: {persona}/{mode}")
        self._update_route_preview(self._last_command)

    def _finish_request_ui(self) -> None:
        self._assistant_view.set_request_in_flight(False)
        self._request_in_flight = False
        if self._pending_chat_context:
            mode, persona = self._pending_chat_context
            self._pending_chat_context = None
            self._apply_chat_context(mode, persona)

    def _on_cancel_assistant_request(self) -> None:
        if not self._request_in_flight:
            return
        self._canceled_request_seqs.add(self._active_request_seq)
        self._finish_request_ui()
        self._assistant_view.set_status("Ready")
        self._assistant_view.add_system_message("Request canceled.")
        self._status_panel.append_syslog(f"request canceled: seq={self._active_request_seq}")
        self._log_launcher_event("command_canceled", seq=self._active_request_seq)

    def _drain_recovery_events(self) -> None:
        drain_recovery_events(self)

    def _on_tool_hint_requested(self, tool_key: str) -> None:
        key = (tool_key or "").strip()
        if not key:
            return
        states = self._tools_view.current_tool_states()
        if states.get(key) == "restricted":
            self._log_launcher_event(
                "tool_hint_blocked",
                tool=key,
                instance=self._active_instance_name,
                status=states.get(key, "unknown"),
            )
            message = (
                f"{key.replace('_', ' ')} is blocked in {self._active_instance_name}. "
                "Switch workspaces or review permissions in Agent Tools before you try again."
            )
            self._assistant_view.add_system_message(message)
            self._set_daily_activity(f"Workspace tool blocked: {key}")
            self._status_panel.append_syslog(f"workspace tool blocked: {key}")
            self._refresh_tools_debug_surface()
            return
        self._on_tab_change(0)
        self._assistant_view.set_input_text(self._tool_prompt_for_home(key))
        self._set_daily_activity(f"Workspace tool loaded into Home: {key}")
        self._status_panel.append_syslog(f"workspace tool primed: {key}")
        self._log_launcher_event(
            "tool_hint_requested",
            tool=key,
            instance=self._active_instance_name,
            status=states.get(key, "unknown"),
        )
        self._refresh_tools_debug_surface()

    def _on_tool_management_requested(self, payload: dict) -> None:
        if not isinstance(payload, dict):
            return
        connector_id = str(payload.get("connector", "") or "").strip().lower()
        provider = str(payload.get("provider", "") or "").strip().lower()
        account_id = str(payload.get("account_id", "") or "").strip().lower()
        tool_key = str(payload.get("tool", "") or "").strip().lower()
        note = str(payload.get("note", "") or "").strip()
        self._on_tab_change(_SETTINGS_VIEW_INDEX)
        focus = getattr(self._settings_hub_view, "focus_connectors", None)
        if callable(focus):
            focus(
                connector_id,
                provider=provider,
                account_id=account_id,
                note=note,
            )
        summary = f"Settings owns connector setup for {tool_key or connector_id or 'this tool'}."
        self._assistant_view.add_system_message(summary)
        self._set_daily_activity(summary)
        self._status_panel.append_syslog(f"tool management redirect: {tool_key or connector_id or 'unknown'}")
        self._log_launcher_event(
            "tool_management_redirected",
            tool=tool_key,
            connector=connector_id,
            provider=provider,
            account_id=account_id,
            target=str(payload.get('destination', '') or 'settings_device_accounts'),
        )

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
        from src.guppy.launcher_application.builder_workflow import enqueue_builder_task, render_builder_task

        task = render_builder_task(
            template_id,
            target_ref=target_ref,
            requested_by_instance=instance_name,
        )
        enqueue_builder_task(task)
        self._tools_view.set_builder_status(f"Queued {task['title']} for dry-run review")
        self._assistant_view.add_system_message(
            f"Queued local builder task: {task['title']} -> {task['output_file_path']}"
        )
        self._set_daily_activity(announce_text)
        self._status_panel.append_syslog(f"builder task queued: {task['id']}")
        self._sync_automation_test_state(
            status=f"Queued {task['title']} for dry-run review.",
            report_path=_AUTOMATION_REPORT_PATH,
            persist=True,
        )
        return task

    def _write_automation_report(self) -> Path:
        return write_launcher_automation_report(
            self,
            automation_report_path=_AUTOMATION_REPORT_PATH,
            validation_command=_AUTOMATION_TEST_VALIDATION_COMMAND,
        )

    def _approve_latest_builder_task(self) -> dict[str, object]:
        from src.guppy.launcher_application.builder_workflow import approve_builder_task, metrics_path, queue_path, results_path

        queue_file = queue_path()
        results_file = results_path()
        metrics_file = metrics_path()
        queue_payload = read_json_dict(queue_file)
        tasks = [
            item for item in queue_payload.get("tasks", [])
            if isinstance(item, dict)
        ] if isinstance(queue_payload, dict) else []
        pending_task = next(
            (
                item for item in reversed(tasks)
                if str(item.get("status", "")).strip() == "awaiting_approval"
                and isinstance(item.get("pending_approval"), dict)
            ),
            None,
        )
        if pending_task is None:
            raise ValueError("No staged builder task is awaiting approval.")
        return approve_builder_task(
            str(pending_task.get("id", "")).strip(),
            queue_path=queue_file,
            results_path=results_file,
            metrics_path=metrics_file,
            approved_by=self._active_instance_name or "launcher",
        )

    def _on_builder_task_requested(self, payload: dict[str, object]) -> None:
        try:
            template_id = str(payload.get("template_id", "")).strip()
            target_ref = str(payload.get("target_ref", "")).strip()
            instance_name = str(payload.get("instance_name", self._active_instance_name)).strip() or self._active_instance_name
            self._log_launcher_event(
                "tool_builder_task_requested",
                tool="builder_task",
                instance=instance_name,
                action=template_id,
                summary=target_ref,
            )
            task = self._queue_builder_task(
                template_id=template_id,
                target_ref=target_ref,
                instance_name=instance_name,
                announce_text=f"Builder task queued for {instance_name}: {template_id}",
            )
            self._settings_hub_view.set_automation_status(
                f"Queued {task['title']} from Tools. Review staged output in Settings when it is ready."
            )
        except Exception as exc:
            self._tools_view.set_builder_status(f"Queue failed: {exc}", ok=False)
            self._settings_hub_view.set_automation_status(f"Queue failed: {exc}", ok=False)
            self._status_panel.append_syslog(f"builder task queue failed: {exc}")
            self._log_launcher_event(
                "tool_builder_task_error",
                tool="builder_task",
                instance=self._active_instance_name,
                error=str(exc),
            )
        self._refresh_tools_debug_surface()

    def _on_automation_action_requested(self, action: str) -> None:
        target = (action or "").strip().lower()
        if target == "verify_now":
            self._settings_hub_view.focus_automation_test(
                note="VERIFY NOW queued runtime readiness checks in the Settings terminal."
            )
            self._on_windows_ops_requested("verify_runtime")
            self._sync_automation_test_state(
                status="VERIFY NOW queued runtime readiness checks in the embedded terminal.",
                persist=True,
            )
            return
        if target == "switch_builder_workspace":
            preferred = self._preferred_builder_instance_name()
            if preferred != "builder-collab":
                self._sync_automation_test_state(
                    status="builder-collab is unavailable, so the current workspace stays active.",
                    ok=False,
                    persist=True,
                )
                return
            if self._active_instance_name == "builder-collab":
                self._sync_automation_test_state(status="builder-collab is already active.", persist=True)
                return
            self._on_instance_selected("builder-collab")
            self._settings_hub_view.focus_automation_test(
                note="Builder workspace selected for automation dry runs."
            )
            self._sync_automation_test_state(status="Switched to builder-collab for automation testing.", persist=True)
            return
        if target == "queue_dry_run":
            instance_name = self._preferred_builder_instance_name()
            try:
                task = self._queue_builder_task(
                    template_id="regression_checklist",
                    target_ref="automation test launcher and approval flow",
                    instance_name=instance_name,
                    announce_text=f"Automation dry run queued for {instance_name}",
                )
            except Exception as exc:
                self._sync_automation_test_state(status=f"Queue failed: {exc}", ok=False, persist=True)
                self._status_panel.append_syslog(f"automation dry run queue failed: {exc}")
                return
            self._settings_hub_view.focus_automation_test(
                note=f"Dry run queued: {task['title']} -> {task['output_file_path']}"
            )
            return
        if target == "open_latest_report":
            path = self._write_automation_report()
            evidence_bundle = self._write_user_test_evidence_pack(
                report_path=path,
                status="Evidence pack refreshed for the guided tester lane.",
            )
            summary_path = str(evidence_bundle.get("summary_path", "") or "")
            self._settings_hub_view.focus_operator_logs(
                "ALL",
                note=f"Evidence pack refreshed: {summary_path or path}",
            )
            self._assistant_view.add_system_message(f"Evidence pack refreshed: {summary_path or path}")
            self._status_panel.append_syslog(f"automation evidence refreshed: {summary_path or path}")
            self._sync_automation_test_state(
                status=f"Evidence pack refreshed at {summary_path or path}",
                report_path=path,
                persist=True,
            )
            return
        if target == "approve_latest_staged_task":
            try:
                payload = self._approve_latest_builder_task()
            except Exception as exc:
                self._sync_automation_test_state(status=f"Approval failed: {exc}", ok=False, persist=True)
                self._status_panel.append_syslog(f"automation approval failed: {exc}")
                return
            output_file = str(payload.get("output_file", "") or "").strip()
            self._assistant_view.add_system_message(f"Approved staged builder output -> {output_file}")
            self._status_panel.append_syslog(f"automation approval complete: {output_file}")
            self._set_daily_activity("Approved staged automation test output")
            self._sync_automation_test_state(
                status=f"Approved latest staged task -> {output_file}",
                report_path=_AUTOMATION_REPORT_PATH,
                persist=True,
            )
            return
        if target == "run_validation":
            queued = self._settings_hub_view.queue_terminal_recipe(
                [_AUTOMATION_TEST_VALIDATION_COMMAND],
                label="AUTOMATION TEST VALIDATION",
                recipe_context={
                    "kind": "automation_test",
                    "action": "run_validation",
                    "changes": "Runs the focused builder validation suite after dry-run review or approval.",
                },
            )
            if queued:
                self._set_daily_activity("Automation validation queued in Settings terminal")
                self._status_panel.append_syslog("automation validation queued")
                self._sync_automation_test_state(
                    status="Focused automation validation queued in the embedded terminal.",
                    persist=True,
                )
            else:
                self._sync_automation_test_state(
                    status="Validation could not queue in the embedded terminal.",
                    ok=False,
                    persist=True,
                )
            return
        self._sync_automation_test_state(status=f"Automation action unavailable: {action}", ok=False, persist=True)

    def _initialize_embedded_agent(self, agent_id: str) -> tuple[bool, str]:
        aid = (agent_id or "").strip().lower()
        if aid != "guppy":
            return False, f"unknown agent: {agent_id}"
        self._embedded_online.add(aid)
        self._assistant_view.activate_agent(aid)
        self._assistant_view.add_system_message(f"{aid.upper()} embedded session initialized.")
        self._set_daily_activity(f"Embedded {aid.upper()} session initialized")
        return True, "embedded session active"

    def _on_agent_init_requested(self, agent_id: str) -> None:
        aid = (agent_id or "").strip().lower()
        if not aid:
            return
        self._stack.setCurrentIndex(0)
        self._sidebar.set_active(0)
        self._status_panel.append_syslog(f"init requested: {aid}")
        self._log_launcher_event("agent_init_requested", agent=aid)
        ok, summary = self._initialize_embedded_agent(aid)
        self._status_panel.append_syslog(
            f"init {aid}: {'OK' if ok else 'ERROR'} — {summary}"
        )
        self._log_launcher_event("agent_init_result", agent=aid, ok=ok, summary=summary)

    def _on_recovery_requested(self, action: str) -> None:
        start_recovery_request(self, action, thread_factory=threading.Thread)

    def _run_recovery_request(self, act: str) -> None:
        run_recovery_request(self, act)

    def _on_model_selected(self, model: str) -> None:
        self._status_panel.append_syslog(f"active model -> {model}")

        self._refresh_personalization_state()
        self._update_route_preview(self._last_command)
        if self._stack.currentIndex() == _MODELS_VIEW_INDEX:
            self._sync_shell_model_summary(active_model=model)

    def _on_runtime_settings_saved(self, settings: dict) -> None:
        backend = str(settings.get("local_runtime_backend", "ollama") or "ollama").strip().lower() or "ollama"
        self._status_panel.append_syslog(f"local runtime saved -> {backend}")
        self._refresh_personalization_state()
        self._update_route_preview(self._last_command)
        if self._stack.currentIndex() == _MODELS_VIEW_INDEX:
            self._sync_shell_model_summary(runtime_backend=backend)
        self._log_launcher_event("local_runtime_saved", backend=backend)

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
        self._on_tab_change(0)
        self._update_route_preview(prompt)
        self._set_daily_activity(f"Starter loaded: {starter_id}")
        self._status_panel.append_syslog(f"home starter loaded: {starter_id}")
        self._log_launcher_event("home_starter_loaded", starter_id=starter_id)

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
        if not _VOICE_CAPTURE_AVAILABLE or GuppyVoice is None:
            return False, "Voice capture backend is unavailable in this launcher build."
        if self._launcher_voice is not None:
            return True, "ok"
        try:
            self._launcher_voice = GuppyVoice()
            return True, "ok"
        except Exception as exc:
            self._launcher_voice = None
            return False, f"Voice capture failed to initialize: {exc}"

    def _on_mic_requested(self) -> None:
        if self._request_in_flight:
            self._assistant_view.add_system_message("A request is already in progress. Wait for it to finish before using push to talk.")
            return
        if self._mic_capture_active:
            voice = self._launcher_voice
            if voice is not None and hasattr(voice, "stop_listening"):
                try:
                    voice.stop_listening()
                except Exception:
                    pass
            self._set_daily_activity("Stopping push-to-talk capture...")
            self._status_panel.append_syslog("voice capture stop requested")
            return

        ok, summary = self._ensure_voice_capture()
        if not ok:
            self._assistant_view.add_system_message(summary)
            self._status_panel.append_syslog(f"voice capture unavailable: {summary}")
            return

        self._mic_capture_active = True
        self._assistant_view.set_mic_capture_state(True)
        self._set_daily_activity("Push-to-talk listening...")
        self._status_panel.append_syslog("voice capture started")
        self._log_launcher_event("voice_capture_started")

        def _worker() -> None:
            voice = self._launcher_voice
            if voice is None:
                self._assistant_events.put(("voice_error", "Voice capture backend was not available.", 0))
            else:
                try:
                    result = voice.listen_once(timeout=10)
                    text = str(result.get("text", "") or "").strip() if isinstance(result, dict) else ""
                    error = str(result.get("error", "") or "").strip() if isinstance(result, dict) else ""
                    if text:
                        self._assistant_events.put(("voice_input", text, 0))
                        self._log_launcher_event("voice_capture_result", ok=True, chars=len(text))
                    else:
                        self._assistant_events.put(("voice_error", error or "No speech captured.", 0))
                        self._log_launcher_event("voice_capture_result", ok=False, error=error or "no_speech")
                except Exception as exc:
                    self._assistant_events.put(("voice_error", f"Voice capture failed: {exc}", 0))
                    self._log_launcher_event("voice_capture_result", ok=False, error=str(exc))
            emitter = getattr(self, "assistant_event_queued", None)
            if emitter is not None and hasattr(emitter, "emit"):
                emitter.emit()

        threading.Thread(target=_worker, daemon=True).start()
