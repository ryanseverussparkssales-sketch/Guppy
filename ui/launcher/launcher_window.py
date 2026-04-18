"""
ui/launcher/launcher_window.py
Main QMainWindow shell — assembles Sidebar, TopBar, StatusPanel,
the unified launcher stack, and the bottom system strip.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from queue import Empty, SimpleQueue
from datetime import datetime, timezone
from pathlib import Path
import urllib.error
import urllib.request

import src.guppy.launcher_application as launcher_app
from src.guppy.launcher_application import (
    LauncherStateSnapshot,
    LibraryWorkflowController,
    WindowsOpsExecutionKind,
    advance_windows_ops_chain,
    apply_connector_action_feedback,
    apply_library_payload,
    apply_workspace_instance_switch,
    beta_release_dry_run_report_path,
    bootstrap_workspace_instance_switcher,
    build_launcher_state_snapshot,
    build_library_chat_submission,
    build_windows_ops_descriptor,
    build_windows_ops_feedback_kwargs,
    build_windows_ops_plan,
    build_windows_ops_state_payload,
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
    fetch_workspace_connector_inventory,
    handle_connector_action_request,
    handle_connector_guided_link_request,
    load_workspace_instance_logs,
    normalize_windows_gate_details,
    normalize_windows_ops_artifacts,
    perform_connector_action_request,
    refresh_workspace_instance_views,
    release_dry_run_gate_details,
    release_review_order,
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
    start_windows_ops_chain,
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
    build_local_bearer_token,
    build_runtime_health_snapshot,
    build_runtime_health_view_payload,
    fetch_startup_readiness,
    route_evidence_summary,
    summarize_startup_readiness,
)
from src.guppy.workspace_governance import (
    instance_policy_backend_available,
    build_connector_action_request,
    build_connector_action_result,
    build_connector_inventory,
    resolve_instance_permissions,
    set_instance_tool_permission_policy,
)

try:
    from utils import secret_store as _secret_store
    _SECRET_STORE_AVAILABLE = True
except Exception:
    _secret_store = None  # type: ignore[assignment]
    _SECRET_STORE_AVAILABLE = False

from utils.safe_io import append_jsonl, read_json_dict, read_jsonl_tail, write_json_atomic

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
from .components import Sidebar, TopBar, StatusPanel
from .views import (
    AssistantView,
    InstanceManagerView,
    LibraryView,
    ToolsView,
    SettingsView,
    AdvancedView,
    MyPCView,
    LocalLLMView,
    ModelsView,
    RuntimeRoutingView,
    VoicesView,
)

_PERSONALIZATION_BOOTSTRAP_AVAILABLE = personalization_backend_available()

try:
    from utils.instance_logger import append_instance_log, read_instance_log_tail
    _INSTANCE_LOGGER_AVAILABLE = True
except Exception:
    _INSTANCE_LOGGER_AVAILABLE = False

    def append_instance_log(*_args, **_kwargs):
        return None

    def read_instance_log_tail(*_args, **_kwargs):
        return []

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
_START_TIME = time.monotonic()
_AUTOMATION_TEST_VALIDATION_COMMAND = (
    ".venv\\Scripts\\python.exe -m pytest tests/unit/test_offhours_builder.py tests/unit/test_instance_controls.py -q"
)
_AUTOMATION_REPORT_PATH = _RUNTIME / "offhours_builder_report.json"
_START_DESTINATION_TO_TAB = {
    "home": 0,
    "library": 2,
    "tools": 3,
    "appmgmt": 4,
    "automation-test": 4,
}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not write_json_atomic(path, payload):
        raise OSError(f"Atomic write failed for {path}")

class LauncherWindow(QMainWindow):
    assistant_event_queued = Signal()
    connector_action_event_queued = Signal()

    _MAX_DEFERRED_SYSLOG_PER_TICK = 24
    _MAX_ASSISTANT_EVENTS_PER_TICK = 12
    _MAX_RECOVERY_EVENTS_PER_TICK = 12

    @staticmethod
    def _event_level(item: dict[str, object]) -> str:
        event = str(item.get("event", "") or "").lower()
        summary = json.dumps(item, ensure_ascii=True).lower()
        if "error" in event or "error" in summary or "failed" in summary:
            return "ERROR"
        if "warn" in event or "warning" in summary or "over_budget" in event:
            return "WARN"
        return "INFO"

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Guppy AI  //  WORKSPACE_ASSISTANT")
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
        self._advanced_view   = AdvancedView(self)
        self._my_pc_view      = MyPCView(self)
        self._settings_view   = SettingsView(self)
        self._local_llm_view  = LocalLLMView(self)
        self._models_view     = ModelsView(self)
        self._runtime_view    = RuntimeRoutingView(self)
        self._voices_view     = VoicesView(self)
        self._advanced_view.attach_settings_panel(self._settings_view)

        for view in [
            self._assistant_view,
            self._instance_manager_view,
            self._library_view,
            self._tools_view,
            self._advanced_view,
            self._my_pc_view,
            self._local_llm_view,
            self._models_view,
            self._runtime_view,
            self._voices_view,
        ]:
            self._stack.addWidget(view)

        body.addWidget(self._stack, stretch=1)

        # Thin vertical divider
        sdiv2 = QFrame()
        sdiv2.setFixedWidth(1)
        sdiv2.setStyleSheet(f"background: {T.BORDER};")
        body.addWidget(sdiv2)

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

        root.addLayout(body, stretch=1)

        # ── Bottom system strip ──────────────────────────────────────────────
        self._sys_strip = self._build_sys_strip()
        root.addWidget(self._sys_strip)

        # ── Wire signals ─────────────────────────────────────────────────────
        self._sidebar.tab_changed.connect(self._on_tab_change)
        self._topbar.nav_requested.connect(self._on_tab_change)
        self._settings_view.settings_saved.connect(self._on_settings_saved)
        self._tools_view.tool_state_changed.connect(self._on_tool_state_changed)
        self._tools_view.tool_hint_requested.connect(self._on_tool_hint_requested)
        self._tools_view.builder_task_requested.connect(self._on_builder_task_requested)
        self._status_panel.tool_requested.connect(self._on_tool_hint_requested)
        self._advanced_view.recovery_requested.connect(self._on_recovery_requested)
        self._advanced_view.windows_ops_requested.connect(self._on_windows_ops_requested)
        self._advanced_view.connector_action_requested.connect(self._on_connector_action_requested)
        self._advanced_view.automation_action_requested.connect(self._on_automation_action_requested)
        self._my_pc_view.windows_ops_requested.connect(self._on_windows_ops_requested)
        self._my_pc_view.connector_action_requested.connect(self._on_connector_action_requested)
        self._my_pc_view.connector_guided_link_requested.connect(self._on_connector_guided_link_requested)
        self._advanced_view.terminal_recipe_finished.connect(self._on_terminal_recipe_finished)
        self._models_view.model_selected.connect(self._on_model_selected)
        self._runtime_view.model_selected.connect(self._on_model_selected)
        self._runtime_view.runtime_settings_saved.connect(self._on_runtime_settings_saved)
        self._voices_view.bindings_changed.connect(self._on_voice_bindings_changed)
        self._topbar.search_submitted.connect(self._on_search)
        self._topbar.quick_action.connect(self._on_quick_action)
        self._topbar.launcher_context_requested.connect(self._assistant_view.toggle_launcher_panel)
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
        self._assistant_view.active_context_library_requested.connect(self._on_library_context_opened)
        self._assistant_view.active_context_remove_requested.connect(self._on_library_context_removed)
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
        self._assistant_view.set_session_id(self._chat_session_id)
        self._topbar.set_launcher_summary("AUTO / GUPPY / LIGHT [EDIT]")
        self._bootstrap_instance_switcher()
        self._refresh_personalization_state()
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
            self._voices_view._load_assignment_options()
            self._voices_view._refresh_bindings_summary()
            self._assistant_view.set_runtime_facts(
                profile=self._assistant_view._cb_profile.currentText().strip().lower() or "standard",
                model=personalization_state.model_id,
                voice=personalization_state.voice_summary,
                latency="-",
                last_query=self._last_command or "-",
            )
            self._advanced_view.set_daily_context_runtime(self._assistant_view._runtime_facts.text())
        except Exception as exc:
            self._status_panel.append_syslog(f"personalization refresh failed: {exc}")

    def _update_route_preview(self, text: str = "") -> None:
        update_route_preview(self, text)

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
        data: dict = {}
        api_status: dict[str, object] = {}

        # Heartbeats
        data["guppy_online"]  = (_RUNTIME / "guppy.heartbeat").exists()

        # Guppy status
        gs = read_json_dict(_RUNTIME / "guppy.status")
        data["profile"]      = gs.get("runtime_profile", os.environ.get("GUPPY_RUNTIME_PROFILE", "standard"))
        data["daemon"]       = gs.get("daemon_running", data["guppy_online"])
        data["voice_engine"] = gs.get("tts_engine", os.environ.get("GUPPY_TTS_ENGINE", "edge"))
        data["model"]        = gs.get("active_model",  os.environ.get("GUPPY_LOCAL_MODEL", "guppy"))
        data["wake_word"]    = gs.get("wake_word",     os.environ.get("GUPPY_WAKE_WORD_ENABLED", "false"))
        data["latency"]      = gs.get("last_latency_ms", "—")
        data["last_query"]   = gs.get("last_query", "—")
        if data["last_query"] in {"", "—"} and self._last_command:
            data["last_query"] = self._last_command

        try:
            payload = self._http_json(
                "/status",
                method="GET",
                timeout=0.75,
                retry_auth_on_401=True,
                auth_retry_reason="status_poll",
            )
            if isinstance(payload, dict):
                api_status = payload
        except Exception:
            api_status = {}
        data["status"] = str(api_status.get("status", "healthy" if data["guppy_online"] else "degraded") or "unknown")

        voice_summary = str(data.get("voice_engine", data.get("voice", "edge")) or "edge")
        active_model_id = self._assistant_model_id(
            self._assistant_view.selected_mode(),
            str(data.get("model", "") or ""),
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

        self._status_panel.update_status(data)
        self._assistant_view.set_runtime_facts(
            profile=str(data.get("profile", "standard") or "standard"),
            model=active_model_id,
            voice=voice_summary,
            latency=str(data.get("latency", "-") or "-"),
            last_query=str(data.get("last_query", "-") or "-"),
        )

        # Update agent cards
        guppy_load  = gs.get("cpu_load_pct", 0)
        guppy_online = data["guppy_online"] or ("guppy" in self._embedded_online)

        self._status_panel.update_agent_status("guppy", guppy_online, "—", guppy_load)
        background_summary = (
            f"{self._active_instance_name} · {str(data.get('profile', 'standard')).upper()} · "
            f"GUPPY {'LIVE' if guppy_online else 'OFFLINE'}"
        )
        active_snapshot = self._last_instance_snapshot if isinstance(self._last_instance_snapshot, dict) else {}
        active_items = active_snapshot.get("instances", []) if isinstance(active_snapshot, dict) else []
        active_payload = next(
            (
                item
                for item in active_items
                if isinstance(item, dict) and str(item.get("name", "")).strip() == self._active_instance_name
            ),
            {},
        )
        active_type = str((active_payload or {}).get("type", "user_instance") or "user_instance")
        role = workspace_role_label(active_type)
        background_summary = f"{role.upper()} {'READY' if guppy_online else 'NEEDS ATTENTION'}"
        self._assistant_view.set_background_status(
            background_summary,
            healthy=guppy_online,
        )
        self._advanced_view.set_daily_context_recovery(
            f"Recovery: {'stable' if guppy_online else 'needs attention'}",
            ok=guppy_online,
        )
        runtime_health = build_runtime_health_snapshot(
            api_status,
            gs,
            voice_tts_backend=str(data.get("voice_engine", "edge") or "edge"),
            voice_stt_backend=str(gs.get("stt_backend", "unknown") or "unknown"),
        )
        self._runtime_health_snapshot = runtime_health
        self._models_view.set_status_snapshot(api_status)
        self._runtime_view.set_status_snapshot(api_status)
        self._advanced_view.set_status_snapshot(
            build_runtime_health_view_payload(
                runtime_health,
                status=str(data.get("status", "healthy") or "healthy"),
                voice_binding=voice_summary,
                route_evidence=self._assistant_view._route_facts.text(),
            )
        )
        windows_snapshot = self._advanced_view.windows_ops_snapshot()
        windows_snapshot_signature = self._payload_signature(windows_snapshot)
        if windows_snapshot_signature != self._last_windows_snapshot_signature:
            self._my_pc_view.set_windows_snapshot(windows_snapshot)
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
        path = _RUNTIME / "launcher_events.jsonl"
        if not path.exists():
            return
        try:
            mtime = path.stat().st_mtime
        except Exception:
            mtime = 0.0
        if mtime == self._recovery_outcome_mtime:
            return
        self._recovery_outcome_mtime = mtime
        events = read_jsonl_tail(path, limit=80)
        target = None
        for item in reversed(events):
            if item.get("event") in {"recovery_result", "recovery_error"}:
                target = item
                break
        if not target:
            return

        action = str(target.get("action", "recovery"))
        ok = bool(target.get("ok", False))
        summary = str(target.get("summary", target.get("error", "")))
        signature = f"{target.get('ts','')}|{target.get('event','')}|{action}|{ok}|{summary}"
        if signature == self._last_recovery_signature:
            return
        self._last_recovery_signature = signature
        self._status_panel.set_recovery_outcome(action, ok, summary)

    @staticmethod
    def _classify_recovery_summary(summary: str, ok: bool, default: str = "") -> str:
        text = (summary or "").lower()
        if "http 401" in text or "unauthorized" in text or "jwt_" in text:
            return "auth_failed"
        if (
            "network error" in text
            or "connection refused" in text
            or "not yet reachable" in text
            or "api unreachable" in text
        ):
            return "api_unreachable"
        if "stale" in text or "missing" in text or "offline" in text:
            return "runtime_stale"
        if default:
            return default
        return "recovery_ok" if ok else "recovery_error"

    @staticmethod
    def _format_recovery_summary(category: str, summary: str) -> str:
        text = (summary or "").strip()
        prefix = {
            "api_unreachable": "API unreachable",
            "auth_failed": "Auth failed",
            "runtime_stale": "Runtime stale",
        }.get(category, "")
        if not prefix:
            return text
        if not text:
            return prefix
        lowered = text.lower()
        if lowered.startswith(prefix.lower()):
            return text
        return f"{prefix}: {text}"

    def _push_recovery_outcome(self, action: str, ok: bool, summary: str, category: str = "") -> str:
        resolved_category = category or self._classify_recovery_summary(summary, ok)
        formatted = self._format_recovery_summary(resolved_category, summary)
        self._recovery_events.put({
            "kind": "outcome",
            "action": action,
            "ok": ok,
            "summary": formatted,
            "category": resolved_category,
        })
        self._log_launcher_event(
            "recovery_result" if ok else "recovery_error",
            action=action,
            ok=ok,
            category=resolved_category,
            summary=formatted,
        )
        return formatted

    # ── Tab coordination ──────────────────────────────────────────────────────
    def _on_tab_change(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        self._topbar.set_active_tab(index)
        self._sidebar.set_active(index)
        if index == 4:
            self._sync_automation_test_state()

    def _apply_start_destination(self) -> None:
        target = self._start_destination
        if target not in _START_DESTINATION_TO_TAB:
            return
        self._on_tab_change(_START_DESTINATION_TO_TAB[target])
        if target == "automation-test":
            note = (
                "Test flow ready: use Settings & System to verify readiness, queue one safe check, review it, approve it, and run validation."
            )
            self._advanced_view.focus_automation_test(note=note)
            self._assistant_view.set_background_event(note)
            self._set_daily_activity("Test flow opened Settings & System")
            self._status_panel.append_syslog("automation test start intent opened Settings & System")
        self._log_launcher_event("start_destination_applied", destination=target)

    def _instances_config_path(self) -> Path:
        return _CONFIG / "instances.json"

    def _instance_state_path(self) -> Path:
        return _RUNTIME / "instance_state.json"

    @staticmethod
    def _default_governance_snapshot(instance_type: str) -> dict[str, object]:
        kind = str(instance_type or "user_instance").strip().lower() or "user_instance"
        capabilities = {
            "user_instance": {"read": True, "write": True, "execute": True, "network": True},
            "builder_instance": {"read": True, "write": True, "execute": False, "network": True},
            "read_only_instance": {"read": True, "write": False, "execute": False, "network": False},
            "admin_instance": {"read": True, "write": True, "execute": True, "network": True},
        }.get(kind, {"read": True, "write": True, "execute": True, "network": True})
        return {
            "auth_mode": "runtime_default",
            "tool_allow": [],
            "tool_block": [],
            "endpoint_allow": [],
            "endpoint_block": [],
            "policy_note": "",
            "capabilities": capabilities,
        }

    def _local_instance_snapshot(self, *, include_workspace_details: bool = True) -> dict:
        config = read_json_dict(self._instances_config_path())
        state = read_json_dict(self._instance_state_path())
        items: list[dict[str, object]] = []
        warnings: list[str] = []
        raw_items = config.get("instances", []) if isinstance(config, dict) else []
        state_items = state.get("instances", {}) if isinstance(state, dict) else {}
        active = str(config.get("active_instance", state.get("active_instance", "guppy-primary")) if isinstance(config, dict) else "guppy-primary").strip() or "guppy-primary"
        for item in raw_items if isinstance(raw_items, list) else []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            instance_type = str(item.get("type", "user_instance") or "user_instance")
            runtime = state_items.get(name, {}) if isinstance(state_items, dict) else {}
            governance = self._default_governance_snapshot(instance_type)
            connectors: list[dict[str, object]] = []
            if include_workspace_details:
                resolved = resolve_instance_permissions(name, instance_type)
                if isinstance(resolved, dict) and resolved:
                    governance = {
                        "auth_mode": str(resolved.get("_auth_mode", "runtime_default") or "runtime_default"),
                        "tool_allow": list(resolved.get("_tool_allow", [])),
                        "tool_block": list(resolved.get("_tool_block", [])),
                        "endpoint_allow": list(resolved.get("_endpoint_allow", [])),
                        "endpoint_block": list(resolved.get("_endpoint_block", [])),
                        "policy_note": str(resolved.get("_policy_note", "") or ""),
                        "capabilities": {
                            "read": bool(resolved.get("read", False)),
                            "write": bool(resolved.get("write", False)),
                            "execute": bool(resolved.get("execute", False)),
                            "network": bool(resolved.get("network", False)),
                        },
                    }
                connectors = fetch_workspace_connector_inventory(name)
            items.append(
                {
                    "name": name,
                    "description": str(item.get("description", "")).strip(),
                    "mode": str(item.get("mode", "auto") or "auto"),
                    "persona": str(item.get("persona", "guppy") or "guppy"),
                    "voice": str(item.get("voice", "default") or "default"),
                    "type": instance_type,
                    "created_at": item.get("created_at"),
                    "enabled": bool(item.get("enabled", True)),
                    "status": str(runtime.get("status", "idle") or "idle"),
                    "last_message": str(runtime.get("last_message", "") or ""),
                    "last_updated": runtime.get("last_updated"),
                    "message_count": int(runtime.get("message_count", 0) or 0),
                    "model_currently_using": str(runtime.get("model_currently_using", item.get("mode", "auto")) or "auto"),
                    "governance": governance,
                    "connectors": connectors,
                }
            )
        if not items:
            items = [
                {
                    "name": "guppy-primary",
                    "description": "Primary foreground assistant instance",
                    "mode": "auto",
                    "persona": "guppy",
                    "voice": "default",
                    "type": "user_instance",
                    "created_at": None,
                    "enabled": True,
                    "status": "active",
                    "last_message": "",
                    "last_updated": None,
                    "message_count": 0,
                    "model_currently_using": "auto",
                    "governance": self._default_governance_snapshot("user_instance"),
                    "connectors": fetch_workspace_connector_inventory("guppy-primary") if include_workspace_details else [],
                }
            ]
            active = "guppy-primary"
        active_runtime = sum(
            1 for item in items if str(item.get("status", "idle")).strip().lower() in {"active", "running", "busy"}
        )
        if len(items) >= 5:
            warnings.append("configured instance cap reached (5 / 5)")
        if active_runtime >= 2:
            warnings.append("runtime-active instance cap reached (2 / 2)")
        return {
            "version": int(config.get("version", 1) or 1) if isinstance(config, dict) else 1,
            "active_instance": active,
            "instances": items,
            "limits": {
                "configured": len(items),
                "max_configured": 5,
                "active_runtime": active_runtime,
                "max_active_runtime": 2,
            },
            "warnings": warnings,
        }

    def _fetch_instance_snapshot(self, *, force: bool = False) -> dict:
        now = time.monotonic()
        if not force and self._last_instance_snapshot and now < self._instance_snapshot_expires_at:
            return self._last_instance_snapshot
        try:
            snapshot = self._http_json(
                "/instances",
                method="GET",
                timeout=1.2,
                retry_auth_on_401=True,
                auth_retry_reason="instances_list",
            )
        except Exception:
            snapshot = self._local_instance_snapshot()
        if isinstance(snapshot, dict) and snapshot:
            self._last_instance_snapshot = snapshot
            self._instance_snapshot_expires_at = now + max(2.0, self._instance_snapshot_ttl_s)
        return snapshot

    def _fetch_connector_inventory(self, *, force: bool = False) -> list[dict]:
        now = time.monotonic()
        if not force and self._last_connector_inventory_snapshot and now < self._connector_inventory_expires_at:
            return list(self._last_connector_inventory_snapshot)
        try:
            payload = self._http_json(
                "/connectors",
                method="GET",
                timeout=1.5,
                retry_auth_on_401=True,
                auth_retry_reason="connectors_list",
            )
            rows = payload.get("connectors", []) if isinstance(payload, dict) else []
            snapshot = [item for item in rows if isinstance(item, dict)]
        except Exception:
            snapshot = [item.raw for item in fetch_connector_inventory()]
        self._last_connector_inventory_snapshot = list(snapshot)
        self._connector_inventory_expires_at = now + max(3.0, self._connector_inventory_ttl_s)
        return snapshot

    def _load_instance_history_from_logs(self, name: str) -> list[dict[str, str]]:
        if not _INSTANCE_LOGGER_AVAILABLE:
            return []
        history: list[dict[str, str]] = []
        for item in read_instance_log_tail(name, limit=80):
            if not isinstance(item, dict):
                continue
            role = str(item.get("role", "")).strip().lower()
            message = str(item.get("message", item.get("response", ""))).strip()
            if role in {"user", "assistant"} and message:
                history.append({"role": role, "content": message})
        return history

    def _load_instance_catalog(self, snapshot: dict | None = None) -> tuple[list[str], str]:
        snapshot = snapshot if isinstance(snapshot, dict) and snapshot else self._local_instance_snapshot(include_workspace_details=False)
        if not isinstance(snapshot, dict) or not snapshot.get("instances"):
            snapshot = self._fetch_instance_snapshot(force=True)
        active = str(snapshot.get("active_instance", "")).strip()
        names: list[str] = []
        for item in snapshot.get("instances", []) if isinstance(snapshot, dict) else []:
            if not isinstance(item, dict):
                continue
            if not bool(item.get("enabled", True)):
                continue
            name = str(item.get("name", "")).strip()
            if name and name not in names:
                names.append(name)
        if not names:
            names = [active or "guppy-primary"]
        if active not in names:
            active = names[0]
        return names, active

    def _refresh_instance_views(self, *, load_logs: bool = False, force: bool = False) -> None:
        refresh_workspace_instance_views(self, load_logs=load_logs, force=force)

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
            fetch_connector_inventory=fetch_connector_inventory,
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

    def _tool_state_path(self) -> Path:
        return _RUNTIME / "launcher_tools_state.json"

    def _windows_ops_state_path(self) -> Path:
        return _RUNTIME / "windows_ops_state.json"

    def _windows_release_receipt_path(self) -> Path:
        return _RUNTIME / "windows_release_receipt.json"

    def _windows_release_summary_path(self) -> Path:
        return _RUNTIME / "windows_release_summary.md"

    @staticmethod
    def _default_windows_ops_event_id(action: str) -> str:
        return default_windows_ops_event_id(action)

    @staticmethod
    def _beta_release_dry_run_report_path() -> Path:
        return beta_release_dry_run_report_path(_RUNTIME)

    @staticmethod
    def _windows_ops_chain_steps(action: str) -> list[str]:
        descriptor = build_windows_ops_descriptor(action)
        return [step.name for step in descriptor.chain_steps if str(step.name).strip()]

    @staticmethod
    def _windows_ops_chain_changes(action: str) -> str:
        return windows_ops_chain_changes(action)

    @staticmethod
    def _repo_python_path() -> Path:
        return repo_python_path(_RUNTIME, fallback_executable=sys.executable)

    @staticmethod
    def _run_repo_python(args: list[str], *, timeout_s: float = 45.0) -> str:
        return run_repo_python(
            _RUNTIME,
            args,
            timeout_s=timeout_s,
            fallback_executable=sys.executable,
        )

    @staticmethod
    def _snapshot_file_signature(path: Path | None) -> dict[str, object]:
        return snapshot_file_signature(path)

    @staticmethod
    def _latest_runtime_artifact(*patterns: str) -> Path | None:
        return latest_runtime_artifact(_RUNTIME, *patterns)

    @staticmethod
    def _preferred_package_output() -> Path:
        return preferred_package_output(_RUNTIME)

    @staticmethod
    def _collect_windows_service_snapshot() -> dict[str, object]:
        return collect_windows_service_snapshot(_RUNTIME, fallback_executable=sys.executable)

    @staticmethod
    def _windows_service_snapshot_changes(before: dict[str, object], after: dict[str, object]) -> str:
        return windows_service_snapshot_changes(before, after)

    @staticmethod
    def _windows_ops_artifact_refs(action: str, snapshot: dict[str, object]) -> list[dict[str, object]]:
        return windows_ops_artifact_refs(action, snapshot)

    @staticmethod
    def _summarize_release_dry_run_report(report: dict[str, object]) -> dict[str, object]:
        return summarize_release_dry_run_report(report)

    def _release_dry_run_gate_details(self) -> dict[str, object]:
        return release_dry_run_gate_details(_RUNTIME)

    @staticmethod
    def _write_windows_release_summary(summary_path: Path, payload: dict[str, object]) -> str:
        return write_windows_release_summary(summary_path, payload)

    def _write_windows_release_receipt(
        self,
        action: str,
        summary: str,
        changes: str,
        *,
        ok: bool,
        commands: list[str] | None = None,
        event_id: str = "",
        steps_completed: int | None = None,
        steps_total: int | None = None,
        phase: str = "completed",
        next_step: str = "",
        fix_target: str = "",
        docs_hint: str = "",
        entry_point: str = "",
        artifacts: list[dict[str, object]] | None = None,
        gate_summary: str = "",
        gate_detail: str = "",
        gate_checks: list[dict[str, object]] | None = None,
        gate_required_files: list[dict[str, object]] | None = None,
        gate_failed_checks: list[str] | None = None,
        gate_missing_files: list[str] | None = None,
        gate_passed_checks: int | None = None,
        gate_total_checks: int | None = None,
        gate_recommendations: list[str] | None = None,
        gate_recommendation_details: list[dict[str, object]] | None = None,
    ) -> str:
        return write_windows_release_receipt(
            self._windows_ops_state_path(),
            self._windows_release_receipt_path(),
            self._windows_release_summary_path(),
            action,
            summary,
            changes,
            ok=ok,
            commands=commands,
            event_id=event_id,
            steps_completed=steps_completed,
            steps_total=steps_total,
            phase=phase,
            next_step=next_step,
            fix_target=fix_target,
            docs_hint=docs_hint,
            entry_point=entry_point,
            artifacts=artifacts,
            gate_summary=gate_summary,
            gate_detail=gate_detail,
            gate_checks=gate_checks,
            gate_required_files=gate_required_files,
            gate_failed_checks=gate_failed_checks,
            gate_missing_files=gate_missing_files,
            gate_passed_checks=gate_passed_checks,
            gate_total_checks=gate_total_checks,
            gate_recommendations=gate_recommendations,
            gate_recommendation_details=gate_recommendation_details,
        )

    @staticmethod
    def _windows_ops_guidance(action: str, *, ok: bool, phase: str = "completed") -> dict[str, str]:
        return windows_ops_guidance(action, ok=ok, phase=phase)

    @staticmethod
    def _summarize_windows_recipe_result(payload: dict[str, object]) -> tuple[str, str]:
        return summarize_windows_recipe_result(payload)

    def _record_windows_ops_state(
        self,
        action: str,
        summary: str,
        changes: str,
        *,
        ok: bool,
        commands: list[str] | None = None,
        event_id: str = "",
        steps_completed: int | None = None,
        steps_total: int | None = None,
        phase: str = "completed",
        next_step: str = "",
        fix_target: str = "",
        docs_hint: str = "",
        entry_point: str = "",
        artifacts: list[dict[str, object]] | None = None,
        gate_summary: str = "",
        gate_detail: str = "",
        gate_checks: list[dict[str, object]] | None = None,
        gate_required_files: list[dict[str, object]] | None = None,
        gate_failed_checks: list[str] | None = None,
        gate_missing_files: list[str] | None = None,
        gate_passed_checks: int | None = None,
        gate_total_checks: int | None = None,
        gate_recommendations: list[str] | None = None,
        gate_recommendation_details: list[dict[str, object]] | None = None,
    ) -> None:
        artifact_payload = normalize_windows_ops_artifacts(artifacts)
        release_receipt = ""
        release_summary = ""
        normalized_phase = str(phase or "completed").strip().lower() or "completed"
        resolved_event_id = str(event_id or "").strip()
        if normalized_phase != "queued" and not resolved_event_id:
            resolved_event_id = LauncherWindow._default_windows_ops_event_id(action)
        if normalized_phase != "queued":
            release_receipt = self._write_windows_release_receipt(
                action,
                summary,
                changes,
                ok=ok,
                commands=commands,
                event_id=resolved_event_id,
                steps_completed=steps_completed,
                steps_total=steps_total,
                phase=normalized_phase,
                next_step=next_step,
                fix_target=fix_target,
                docs_hint=docs_hint,
                entry_point=entry_point,
                artifacts=artifact_payload,
                gate_summary=gate_summary,
                gate_detail=gate_detail,
                gate_checks=gate_checks,
                gate_required_files=gate_required_files,
                gate_failed_checks=gate_failed_checks,
                gate_missing_files=gate_missing_files,
                gate_passed_checks=gate_passed_checks,
                gate_total_checks=gate_total_checks,
                gate_recommendations=gate_recommendations,
                gate_recommendation_details=gate_recommendation_details,
            )
            release_summary = str(self._windows_release_summary_path())
        payload = build_windows_ops_state_payload(
            action=action,
            ok=ok,
            summary=summary,
            changes=changes,
            commands=commands,
            event_id=resolved_event_id,
            steps_completed=steps_completed,
            steps_total=steps_total,
            phase=normalized_phase,
            next_step=next_step,
            fix_target=fix_target,
            docs_hint=docs_hint,
            entry_point=entry_point,
            artifacts=artifact_payload,
            release_receipt=release_receipt,
            release_summary=release_summary,
            gate_summary=gate_summary,
            gate_detail=gate_detail,
            gate_failed_checks=gate_failed_checks,
            gate_missing_files=gate_missing_files,
            gate_passed_checks=gate_passed_checks,
            gate_total_checks=gate_total_checks,
            gate_recommendations=gate_recommendations,
            gate_recommendation_details=gate_recommendation_details,
        )
        _write_json(self._windows_ops_state_path(), payload)
        feedback = build_windows_ops_feedback_kwargs(payload, review_order=release_review_order(action))
        self._advanced_view.set_windows_ops_feedback(
            str(action or "").strip().lower(),
            str(feedback.pop("summary", "") or ""),
            str(feedback.pop("changes", "") or ""),
            **feedback,
        )
        my_pc_view = getattr(self, "_my_pc_view", None)
        advanced_view = getattr(self, "_advanced_view", None)
        snapshot_getter = getattr(advanced_view, "windows_ops_snapshot", None)
        if my_pc_view is not None and hasattr(my_pc_view, "set_windows_snapshot") and callable(snapshot_getter):
            my_pc_view.set_windows_snapshot(snapshot_getter())

    def _start_windows_ops_chain(self, action: str) -> None:
        normalized = str(action or "").strip().lower()
        steps = self._windows_ops_chain_steps(normalized)
        self._active_windows_ops_chain = start_windows_ops_chain(
            normalized,
            steps,
            self._windows_ops_chain_changes(normalized),
        )

    def _update_windows_ops_chain(self, action: str, *, ok: bool, summary: str) -> bool:
        result = advance_windows_ops_chain(
            self._active_windows_ops_chain,
            action,
            ok=ok,
            summary=summary,
        )
        if not result.matched:
            return False
        self._active_windows_ops_chain = result.next_chain
        if not result.completed:
            return True
        parent_action = result.parent_action
        guidance = self._windows_ops_guidance(parent_action, ok=result.overall_ok, phase="completed")
        artifacts = self._windows_ops_artifact_refs(parent_action, self._collect_windows_service_snapshot())
        event_id = LauncherWindow._default_windows_ops_event_id(parent_action)
        self._record_windows_ops_state(
            parent_action,
            result.summary_text,
            result.change_text,
            ok=result.overall_ok,
            event_id=event_id,
            steps_completed=result.steps_completed,
            steps_total=result.steps_total,
            phase="completed",
            next_step=str(guidance.get("next_step", "") or ""),
            fix_target=str(guidance.get("fix_target", "") or ""),
            docs_hint=str(guidance.get("docs_hint", "") or ""),
            entry_point=str(guidance.get("entry_point", "") or ""),
            artifacts=artifacts,
        )
        self._log_launcher_event(
            "windows_ops_completed",
            action=parent_action,
            ok=result.overall_ok,
            steps_completed=result.steps_completed,
            steps_total=result.steps_total,
            summary=result.summary_text,
            event_id=event_id,
            next_step=str(guidance.get("next_step", "") or ""),
            fix_target=str(guidance.get("fix_target", "") or ""),
            artifacts=artifacts,
            release_receipt=str(self._windows_release_receipt_path()),
            release_summary=str(self._windows_release_summary_path()),
        )
        self._active_windows_ops_chain = None
        return True

    def _on_terminal_recipe_finished(self, payload: dict) -> None:
        if not isinstance(payload, dict):
            return
        if str(payload.get("kind", "") or "").strip().lower() != "windows_ops":
            return
        action = str(payload.get("action", "") or "").strip().lower()
        summary, changes = self._summarize_windows_recipe_result(payload)
        pre_snapshot = payload.get("pre_snapshot", {}) if isinstance(payload.get("pre_snapshot"), dict) else {}
        post_snapshot = self._collect_windows_service_snapshot()
        dynamic_changes = self._windows_service_snapshot_changes(pre_snapshot, post_snapshot)
        artifacts = self._windows_ops_artifact_refs(action, post_snapshot)
        gate_details = normalize_windows_gate_details(
            self._release_dry_run_gate_details() if action == "release_dry_run" else {}
        )
        if dynamic_changes:
            changes = f"{changes} | {dynamic_changes}" if changes else dynamic_changes
        gate_summary = str(gate_details.get("summary", "") or "").strip()
        gate_detail = str(gate_details.get("detail", "") or "").strip()
        gate_checks = [item for item in gate_details.get("checks", []) if isinstance(item, dict)]
        gate_required_files = [item for item in gate_details.get("required_files", []) if isinstance(item, dict)]
        gate_failed_checks = [str(item).strip() for item in gate_details.get("failed_checks", []) if str(item).strip()]
        gate_missing_files = [str(item).strip() for item in gate_details.get("missing_files", []) if str(item).strip()]
        gate_passed_checks = int(gate_details.get("passed_checks", 0) or 0) if gate_details.get("passed_checks") is not None else None
        gate_total_checks = int(gate_details.get("total_checks", 0) or 0) if gate_details.get("total_checks") is not None else None
        gate_recommendations = [str(item).strip() for item in gate_details.get("recommendations", []) if str(item).strip()]
        gate_recommendation_details = [item for item in gate_details.get("recommendation_details", []) if isinstance(item, dict)]
        if gate_detail:
            changes = f"{changes} | {gate_detail}" if changes else gate_detail
        ok = bool(payload.get("ok", False))
        guidance = self._windows_ops_guidance(action, ok=ok, phase="completed")
        event_id = str(payload.get("id", "") or "").strip()
        commands = [str(item).strip() for item in payload.get("commands", []) if str(item).strip()] if isinstance(payload.get("commands"), list) else []
        steps_completed = int(payload.get("steps_completed", 0) or 0)
        steps_total = int(payload.get("steps_total", 0) or 0)
        self._status_panel.append_syslog(summary)
        self._advanced_view.append_log(summary)
        self._set_daily_activity(summary)
        self._record_windows_ops_state(
            action,
            summary,
            changes,
            ok=ok,
            commands=commands,
            event_id=event_id,
            steps_completed=steps_completed,
            steps_total=steps_total,
            phase="completed",
            next_step=str(guidance.get("next_step", "") or ""),
            fix_target=str(guidance.get("fix_target", "") or ""),
            docs_hint=str(guidance.get("docs_hint", "") or ""),
            entry_point=str(guidance.get("entry_point", "") or ""),
            artifacts=artifacts,
            gate_summary=gate_summary,
            gate_detail=gate_detail,
            gate_checks=gate_checks,
            gate_required_files=gate_required_files,
            gate_failed_checks=gate_failed_checks,
            gate_missing_files=gate_missing_files,
            gate_passed_checks=gate_passed_checks,
            gate_total_checks=gate_total_checks,
            gate_recommendations=gate_recommendations,
            gate_recommendation_details=gate_recommendation_details,
        )
        self._log_launcher_event(
            "windows_ops_completed",
            action=action,
            ok=ok,
            steps_completed=steps_completed,
            steps_total=steps_total,
            summary=summary,
            event_id=event_id,
            next_step=str(guidance.get("next_step", "") or ""),
            fix_target=str(guidance.get("fix_target", "") or ""),
            artifacts=artifacts,
            release_receipt=str(self._windows_release_receipt_path()),
            release_summary=str(self._windows_release_summary_path()),
            gate_summary=gate_summary,
            gate_detail=gate_detail,
            gate_failed_checks=gate_failed_checks,
            gate_missing_files=gate_missing_files,
            gate_passed_checks=gate_passed_checks,
            gate_total_checks=gate_total_checks,
            gate_recommendations=gate_recommendations,
            gate_fix_target=str(gate_recommendation_details[0].get("fix_target", "") or "").strip() if gate_recommendation_details else "",
            gate_fix_docs=str(gate_recommendation_details[0].get("docs_hint", "") or "").strip() if gate_recommendation_details else "",
            gate_fix_command=str(gate_recommendation_details[0].get("entry_point", "") or "").strip() if gate_recommendation_details else "",
        )

    def _load_tool_states(self) -> None:
        path = self._tool_state_path()
        if not path.exists():
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
        processed = 0
        while processed < self._MAX_RECOVERY_EVENTS_PER_TICK:
            try:
                evt = self._recovery_events.get_nowait()
            except Empty:
                break
            kind = str(evt.get("kind", ""))
            if kind == "status":
                text = str(evt.get("text", ""))
                self._settings_view.set_recovery_status(text)
                self._advanced_view.set_recovery_status(text)
                self._set_daily_activity(text)
                self._assistant_view.set_recovery_summary(text, healthy="error" not in text.lower())
                self._advanced_view.set_daily_context_recovery(
                    self._assistant_view._recovery_summary.text(),
                    ok="error" not in text.lower(),
                )
            elif kind == "syslog":
                text = str(evt.get("text", ""))
                self._status_panel.append_syslog(text)
                self._advanced_view.append_log(text)
                self._set_daily_activity(text)
            elif kind == "outcome":
                action = str(evt.get("action", "recovery"))
                ok = bool(evt.get("ok", False))
                summary = str(evt.get("summary", ""))
                self._status_panel.set_recovery_outcome(action, ok, summary)
                self._advanced_view.set_recovery_status(f"{action}: {summary}")
                self._advanced_view.append_log(f"Recovery {action}: {summary}")
                self._set_daily_activity(f"Recovery {action}: {summary}")
                self._assistant_view.set_recovery_summary(f"{action}: {summary}", healthy=ok)
                self._advanced_view.set_daily_context_recovery(self._assistant_view._recovery_summary.text(), ok=ok)
                if self._update_windows_ops_chain(action, ok=ok, summary=summary):
                    processed += 1
                    continue
                recovery_changes = {
                    "health_snapshot": "Refreshed the launcher-visible health snapshot and operator evidence.",
                    "warmup": "Refreshed startup-readiness and runtime-freshness evidence.",
                    "restart_daemon": "Restarted the daemon and prepared the runtime for follow-up health checks.",
                    "audit_runtime": "Re-ran runtime audit evidence and refreshed diagnostics guidance.",
                }.get(action, "")
                if recovery_changes:
                    self._record_windows_ops_state(action, summary, recovery_changes, ok=ok)
            processed += 1

    def _on_tool_hint_requested(self, tool_key: str) -> None:
        key = (tool_key or "").strip()
        if not key:
            return
        states = self._tools_view.current_tool_states()
        if states.get(key) == "restricted":
            message = (
                f"{key.replace('_', ' ')} is blocked in {self._active_instance_name}. "
                "Switch workspaces or review permissions in Agent Tools before you try again."
            )
            self._assistant_view.add_system_message(message)
            self._set_daily_activity(f"Workspace tool blocked: {key}")
            self._status_panel.append_syslog(f"workspace tool blocked: {key}")
            return
        self._on_tab_change(0)
        self._assistant_view.set_input_text(self._tool_prompt_for_home(key))
        self._set_daily_activity(f"Workspace tool loaded into Home: {key}")
        self._status_panel.append_syslog(f"workspace tool primed: {key}")

    @staticmethod
    def _tool_prompt_for_home(tool_key: str) -> str:
        key = (tool_key or "").strip().lower()
        prompts = {
            "read_file": "Prime the read-file workspace tool for this task. Start by asking which file or folder Guppy should inspect, then confirm the exact read-only scope.",
            "screenshot": "Prime the screenshot workspace tool for this task. Ask what screen or app the user wants Guppy to inspect.",
            "query_instance": "Prime the cross-workspace query tool for this task. Ask which workspace Guppy should consult and what question to send.",
            "debug_console": "Prime the debug-console workspace tool for this task. Start by asking what runtime detail the user wants to inspect.",
            "run_python": "Prime the Python workspace tool for this task. Start by confirming the smallest safe snippet to run.",
            "write_file": "Prime the write-file workspace tool for this task. Start by asking what file should change, what outcome is expected, and what scope is safe.",
            "execute_command": "Prime the command workspace tool for this task. Start by asking which command should run, why it is needed, and what safe scope applies.",
            "outlook_slot": "Help me plan an Outlook tray slot for this workspace. Start by asking what inbox, follow-up, or mail view should live there.",
            "calendar_slot": "Help me plan a calendar tray slot for this workspace. Start by asking what schedule, agenda, or next event view should live there.",
            "rss_slot": "Help me plan an RSS tray slot for this workspace. Start by asking which feeds, sources, or watchlists should live there.",
            "add_slot": "Help me design a new tray slot for this workspace. Start by asking which app, API, or lightweight module should be added on the right side.",
        }
        return prompts.get(key, f"Prime the {key} workspace tool for this task: ")

    def _available_instance_names(self) -> set[str]:
        snapshot = self._last_instance_snapshot if isinstance(self._last_instance_snapshot, dict) else {}
        items = snapshot.get("instances", []) if isinstance(snapshot, dict) else []
        return {
            str(item.get("name", "")).strip()
            for item in items
            if isinstance(item, dict) and bool(item.get("enabled", True)) and str(item.get("name", "")).strip()
        }

    def _preferred_builder_instance_name(self) -> str:
        names = self._available_instance_names()
        if "builder-collab" in names:
            return "builder-collab"
        return self._active_instance_name or "guppy-primary"

    def _user_test_evidence_path(self) -> Path:
        return _RUNTIME / "user_test_evidence.json"

    def _user_test_evidence_summary_path(self) -> Path:
        return _RUNTIME / "user_test_evidence.md"

    @staticmethod
    def _display_repo_path(path: Path | str | None) -> str:
        if path is None:
            return ""
        target = Path(path) if not isinstance(path, Path) else path
        try:
            return str(target.resolve().relative_to(_RUNTIME.parent.resolve())).replace("\\", "/")
        except Exception:
            return str(target).replace("\\", "/")

    @staticmethod
    def _latest_stress_report_path() -> Path | None:
        candidates: list[Path] = []
        for folder in (_RUNTIME, _RUNTIME / "stress_reports"):
            if not folder.exists():
                continue
            candidates.extend(folder.glob("stress_report_*.json"))
        if not candidates:
            return None
        return max(candidates, key=lambda path: path.stat().st_mtime)

    def _recent_launcher_event_summaries(self, limit: int = 4) -> list[str]:
        items = read_jsonl_tail(_RUNTIME / "launcher_events.jsonl", limit=24)
        rendered: list[str] = []
        for item in reversed(items):
            if not isinstance(item, dict):
                continue
            level = LauncherWindow._event_level(item)
            event = str(item.get("event", "event") or "event").replace("_", " ").strip()
            detail = (
                str(item.get("summary", "") or "").strip()
                or str(item.get("status", "") or "").strip()
                or str(item.get("action", "") or "").strip()
                or str(item.get("instance", "") or "").strip()
                or str(item.get("destination", "") or "").strip()
                or str(item.get("command", "") or "").strip()
            )
            line = f"{level} {event}"
            if detail:
                snippet = detail[:88] + ("..." if len(detail) > 88 else "")
                line += f": {snippet}"
            rendered.append(line)
            if len(rendered) >= limit:
                break
        return rendered

    @staticmethod
    def _write_user_test_evidence_summary(summary_path: Path, payload: dict[str, object]) -> str:
        workspace = payload.get("active_workspace", {}) if isinstance(payload.get("active_workspace"), dict) else {}
        home = payload.get("home", {}) if isinstance(payload.get("home"), dict) else {}
        automation = payload.get("automation", {}) if isinstance(payload.get("automation"), dict) else {}
        windows_ops = payload.get("windows_ops", {}) if isinstance(payload.get("windows_ops"), dict) else {}
        recent_events = [
            str(item).strip()
            for item in payload.get("recent_operator_notes", [])
            if str(item).strip()
        ] if isinstance(payload.get("recent_operator_notes"), list) else []
        lines = [
            "# User Test Evidence Pack",
            "",
            f"Generated: {payload.get('generated_at', '')}",
            f"Active workspace: {workspace.get('name', payload.get('active_workspace_name', 'unknown'))}",
            f"Workspace role: {workspace.get('type', 'unknown')}",
            f"Preferred builder workspace: {payload.get('preferred_builder_workspace', '')}",
            f"Automation status: {automation.get('status', '')}",
            f"Builder report: {automation.get('builder_report_path', '')}",
            f"Evidence JSON: {payload.get('evidence_json_path', '')}",
            f"Latest stress run: {payload.get('latest_stress_report', '') or 'not recorded'}",
            "",
            "## Home",
            "",
            f"- Background activity: {home.get('background_event', '')}",
            f"- Workspace summary: {home.get('workspace_summary', '')}",
            f"- Runtime facts: {home.get('runtime_facts', '')}",
            f"- Route facts: {home.get('route_facts', '')}",
            "",
            "## Setup & Health",
            "",
            f"- Next step: {windows_ops.get('next', '')}",
            f"- Service status: {windows_ops.get('service', '')}",
            f"- Release check: {windows_ops.get('gate', '')}",
            "",
            "## Recent Operator Notes",
            "",
        ]
        if recent_events:
            lines.extend([f"- {item}" for item in recent_events])
        else:
            lines.append("- No recent launcher notes were recorded.")
        text = "\n".join(lines).strip() + "\n"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(text, encoding="utf-8")
        return text

    def _write_user_test_evidence_pack(
        self,
        *,
        report_path: Path | None = None,
        status: str = "",
    ) -> dict[str, str]:
        snapshot = self._last_instance_snapshot if isinstance(self._last_instance_snapshot, dict) else {}
        items = snapshot.get("instances", []) if isinstance(snapshot, dict) else []
        active_workspace = next(
            (
                item for item in items
                if isinstance(item, dict) and str(item.get("name", "")).strip() == self._active_instance_name
            ),
            {"name": self._active_instance_name or "guppy-primary", "type": "user_instance"},
        )
        windows_snapshot_getter = getattr(self._advanced_view, "windows_ops_snapshot", None)
        windows_snapshot = windows_snapshot_getter() if callable(windows_snapshot_getter) else {}
        stress_report = self._latest_stress_report_path()
        builder_report = Path(report_path) if isinstance(report_path, Path) else _AUTOMATION_REPORT_PATH
        def _label_text(attr_name: str) -> str:
            widget = getattr(self._assistant_view, attr_name, None)
            text_getter = getattr(widget, "text", None)
            if callable(text_getter):
                try:
                    return str(text_getter() or "").strip()
                except Exception:
                    return ""
            return ""
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "active_workspace_name": self._active_instance_name,
            "preferred_builder_workspace": self._preferred_builder_instance_name(),
            "active_workspace": active_workspace if isinstance(active_workspace, dict) else {},
            "home": {
                "background_event": _label_text("_background_event"),
                "workspace_summary": _label_text("_workspace_summary"),
                "runtime_facts": _label_text("_runtime_facts"),
                "route_facts": _label_text("_route_facts"),
                "recovery_summary": _label_text("_recovery_summary"),
            },
            "automation": {
                "status": str(status or getattr(getattr(self._advanced_view, "_automation_status_lbl", None), "text", lambda: "")() or "").strip(),
                "builder_report_path": self._display_repo_path(builder_report),
                "validation_command": _AUTOMATION_TEST_VALIDATION_COMMAND,
            },
            "windows_ops": windows_snapshot if isinstance(windows_snapshot, dict) else {},
            "latest_stress_report": self._display_repo_path(stress_report) if stress_report else "",
            "recent_operator_notes": self._recent_launcher_event_summaries(limit=5),
        }
        json_path = self._user_test_evidence_path()
        summary_path = self._user_test_evidence_summary_path()
        payload["evidence_json_path"] = self._display_repo_path(json_path)
        payload["evidence_summary_path"] = self._display_repo_path(summary_path)
        _write_json(json_path, payload)
        self._write_user_test_evidence_summary(summary_path, payload)
        return {
            "json_path": self._display_repo_path(json_path),
            "summary_path": self._display_repo_path(summary_path),
            "stress_report_path": self._display_repo_path(stress_report) if stress_report else "",
            "recent_events": "Recent operator notes: " + " | ".join(payload["recent_operator_notes"])
            if payload["recent_operator_notes"] else "Recent operator notes: no recent launcher notes recorded yet.",
        }

    def _automation_test_snapshot(
        self,
        *,
        report_path: Path | None = None,
        status: str = "",
        evidence_pack_path: str = "",
        stress_report_path: str = "",
        recent_events: str = "",
    ) -> dict[str, str]:
        from src.guppy.launcher_application.builder_workflow import QUEUE_PATH, RESULTS_PATH, METRICS_PATH, build_builder_report

        report = build_builder_report(queue_path=QUEUE_PATH, results_path=RESULTS_PATH, metrics_path=METRICS_PATH)
        queue_payload = read_json_dict(QUEUE_PATH)
        tasks = [
            item for item in queue_payload.get("tasks", [])
            if isinstance(item, dict)
        ] if isinstance(queue_payload, dict) else []
        counts = report.get("queue_counts", {}) if isinstance(report, dict) else {}
        pending = int(counts.get("pending", 0) or 0)
        running = int(counts.get("running", 0) or 0)
        awaiting = int(counts.get("awaiting_approval", 0) or 0)
        done = int(counts.get("done", 0) or 0)
        latest_pending = next(
            (
                item for item in reversed(tasks)
                if str(item.get("status", "")).strip() == "awaiting_approval"
                and isinstance(item.get("pending_approval"), dict)
            ),
            {},
        )
        latest_result = next(
            (
                item for item in reversed(report.get("recent_results", []))
                if isinstance(item, dict)
            ),
            {},
        )
        latest_staged_file = str(
            (latest_pending.get("pending_approval", {}) if isinstance(latest_pending, dict) else {}).get("staged_file", "")
        ).strip()
        latest_result_path = str(latest_result.get("output_file", "") or "").strip()
        if not latest_result_path:
            latest_done_task = next(
                (
                    item for item in reversed(tasks)
                    if str(item.get("status", "")).strip() == "done"
                ),
                {},
            )
            latest_result_path = str(latest_done_task.get("approved_output_file", "") or "").strip()
        preferred_builder = self._preferred_builder_instance_name()
        if preferred_builder == "builder-collab":
            workspace_line = (
                f"Workspace step: active={self._active_instance_name} | preferred=builder-collab | "
                "switch here before queueing if you want the default builder workspace."
            )
        else:
            workspace_line = (
                f"Workspace step: active={self._active_instance_name} | preferred={preferred_builder} | "
                "builder-collab is unavailable, so automation stays in the current workspace."
            )
        if latest_pending:
            approval_state = (
                "Latest approval: awaiting approval for "
                f"{str(latest_pending.get('title', latest_pending.get('id', 'builder task')))}"
            )
        elif latest_result_path:
            approval_state = f"Latest approval: most recent approved output is {latest_result_path}"
        else:
            approval_state = "Latest approval: no staged task is awaiting approval yet."
        if not evidence_pack_path:
            evidence_pack_path = self._display_repo_path(self._user_test_evidence_summary_path())
        if not stress_report_path:
            latest_stress = self._latest_stress_report_path()
            stress_report_path = self._display_repo_path(latest_stress) if latest_stress else ""
        if not recent_events:
            recent_items = self._recent_launcher_event_summaries(limit=4)
            recent_events = (
                "Recent operator notes: " + " | ".join(recent_items)
                if recent_items else
                "Recent operator notes: no recent launcher notes recorded yet."
            )
        return {
            "workspace": workspace_line,
            "queue_counts": (
                f"Queue counts: pending={pending} | running={running} | awaiting approval={awaiting} | done={done}"
            ),
            "staged_file": (
                f"Latest staged output: {latest_staged_file}"
                if latest_staged_file
                else "Latest staged output: nothing is waiting for approval yet."
            ),
            "result_path": (
                f"Latest result: {latest_result_path}"
                if latest_result_path
                else "Latest result: no approved builder output has been recorded yet."
            ),
            "approval_state": approval_state,
            "report_path": self._display_repo_path(report_path or _AUTOMATION_REPORT_PATH),
            "evidence_pack_path": evidence_pack_path,
            "stress_report_path": stress_report_path,
            "recent_events": recent_events,
            "validation_command": _AUTOMATION_TEST_VALIDATION_COMMAND,
            "status": str(status or "").strip(),
        }

    def _sync_automation_test_state(
        self,
        *,
        status: str = "",
        ok: bool = True,
        report_path: Path | None = None,
        persist: bool = False,
    ) -> None:
        evidence_bundle = self._write_user_test_evidence_pack(report_path=report_path, status=status) if persist else {}
        snapshot = self._automation_test_snapshot(
            report_path=report_path,
            status=status,
            evidence_pack_path=str(evidence_bundle.get("summary_path", "") or ""),
            stress_report_path=str(evidence_bundle.get("stress_report_path", "") or ""),
            recent_events=str(evidence_bundle.get("recent_events", "") or ""),
        )
        self._advanced_view.set_automation_snapshot(snapshot)
        if status:
            self._advanced_view.set_automation_status(status, ok=ok)

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
        from src.guppy.launcher_application.builder_workflow import QUEUE_PATH, RESULTS_PATH, METRICS_PATH, build_builder_report

        report = build_builder_report(queue_path=QUEUE_PATH, results_path=RESULTS_PATH, metrics_path=METRICS_PATH)
        payload = {
            **report,
            "active_workspace": self._active_instance_name,
            "preferred_builder_workspace": self._preferred_builder_instance_name(),
            "validation_command": _AUTOMATION_TEST_VALIDATION_COMMAND,
        }
        _AUTOMATION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        _AUTOMATION_REPORT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return _AUTOMATION_REPORT_PATH

    def _approve_latest_builder_task(self) -> dict[str, object]:
        from src.guppy.launcher_application.builder_workflow import QUEUE_PATH, RESULTS_PATH, METRICS_PATH, approve_builder_task

        queue_payload = read_json_dict(QUEUE_PATH)
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
            queue_path=QUEUE_PATH,
            results_path=RESULTS_PATH,
            metrics_path=METRICS_PATH,
            approved_by=self._active_instance_name or "launcher",
        )

    def _on_builder_task_requested(self, payload: dict[str, object]) -> None:
        try:
            template_id = str(payload.get("template_id", "")).strip()
            target_ref = str(payload.get("target_ref", "")).strip()
            instance_name = str(payload.get("instance_name", self._active_instance_name)).strip() or self._active_instance_name
            task = self._queue_builder_task(
                template_id=template_id,
                target_ref=target_ref,
                instance_name=instance_name,
                announce_text=f"Builder task queued for {instance_name}: {template_id}",
            )
            self._advanced_view.set_automation_status(
                f"Queued {task['title']} from Tools. Review staged output in Settings when it is ready."
            )
        except Exception as exc:
            self._tools_view.set_builder_status(f"Queue failed: {exc}", ok=False)
            self._advanced_view.set_automation_status(f"Queue failed: {exc}", ok=False)
            self._status_panel.append_syslog(f"builder task queue failed: {exc}")

    def _on_automation_action_requested(self, action: str) -> None:
        target = (action or "").strip().lower()
        if target == "verify_now":
            self._advanced_view.focus_automation_test(
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
            self._advanced_view.focus_automation_test(
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
            self._advanced_view.focus_automation_test(
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
            self._advanced_view.focus_operator_logs(
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
            queued = self._advanced_view.queue_terminal_recipe(
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

    def _api_base_url(self) -> str:
        port = os.environ.get("GUPPY_API_PORT", "8081").strip() or "8081"
        return f"http://127.0.0.1:{port}"

    def _build_local_bearer_token(self) -> str:
        token, token_source = build_local_bearer_token()
        self._api_token_source = token_source
        return token

    def _refresh_api_auth_state(self, reason: str) -> str:
        self._api_bearer_token = self._build_local_bearer_token()
        self._auth_self_check_ok = False
        self._auth_self_check_inflight = False
        self._auth_self_check_last_attempt = 0.0
        self._log_launcher_event(
            "auth_token_refreshed",
            reason=reason,
            token_source=self._api_token_source,
            has_token=bool(self._api_bearer_token),
        )
        return self._api_bearer_token

    @staticmethod
    def _is_unauthorized_error(error_text: str) -> bool:
        txt = (error_text or "").lower()
        return "http 401" in txt or "unauthorized" in txt

    @staticmethod
    def _extract_error_code(error_text: str) -> str:
        txt = (error_text or "").strip()
        match = re.search(r"\[([A-Za-z0-9_:-]+)\]", txt)
        return match.group(1) if match else ""

    def _read_repair_token(self) -> str:
        # Prefer OS credential store (same account, no file exposure).
        if _SECRET_STORE_AVAILABLE and _secret_store is not None:
            try:
                ks_token = _secret_store.get_secret("repair_token")
                if ks_token and launcher_app.is_valid_repair_token(ks_token):
                    return ks_token
            except Exception:
                pass
        # Fallback: file written by guppy_api.py when keyring is unavailable.
        tok_path = _RUNTIME / "repair_token.txt"
        try:
            if not tok_path.exists() or not tok_path.is_file():
                return ""
            token = tok_path.read_text(encoding="utf-8").strip()
        except Exception:
            return ""
        return token if launcher_app.is_valid_repair_token(token) else ""

    @staticmethod
    def _validate_repair_token(token: str) -> bool:
        return launcher_app.is_valid_repair_token(token)

    def _http_json(
        self,
        path: str,
        method: str = "GET",
        payload: dict | None = None,
        timeout: float = 8.0,
        retry_auth_on_401: bool = False,
        auth_retry_reason: str = "",
    ) -> dict:
        url = self._api_base_url() + path
        data = None
        headers = {"Accept": "application/json"}
        if self._api_bearer_token:
            headers["Authorization"] = f"Bearer {self._api_bearer_token}"
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if path == "/repair":
            repair_token = self._read_repair_token()
            if repair_token:
                headers["X-Repair-Token"] = repair_token
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as e:
            err_code = ""
            # On repair token rejection after restart or local desync, re-sync and retry once.
            if e.code == 403 and path == "/repair":
                try:
                    body = e.read().decode("utf-8", errors="replace")
                    parsed = json.loads(body) if body.strip() else {}
                    d = parsed.get("detail", "")
                    err_code = d.get("code", "") if isinstance(d, dict) else ""
                except Exception:
                    err_code = ""
                if err_code.startswith("repair_token_"):
                    refreshed = self._refresh_repair_token_from_api(timeout=timeout)
                    if refreshed:
                        headers["X-Repair-Token"] = refreshed
                        retry_req = urllib.request.Request(url, data=data, headers=headers, method=method)
                        try:
                            with urllib.request.urlopen(retry_req, timeout=timeout) as resp:
                                raw = resp.read().decode("utf-8", errors="replace")
                            self._log_launcher_event("repair_token_resynced", ok=True)
                            return json.loads(raw) if raw.strip() else {}
                        except Exception as retry_exc:
                            self._log_launcher_event(
                                "repair_token_resync_failed",
                                ok=False,
                                reason="retry_failed",
                                error=str(retry_exc),
                                auth_code=err_code,
                            )
                    else:
                        self._log_launcher_event(
                            "repair_token_resync_failed",
                            ok=False,
                            reason="invalid_or_missing_refresh_token",
                            auth_code=err_code,
                        )
            detail = ""
            try:
                body = e.read().decode("utf-8", errors="replace")
                parsed = json.loads(body) if body.strip() else {}
                d = parsed.get("detail", "") if isinstance(parsed, dict) else ""
                if isinstance(d, dict):
                    err_code = d.get("code", "")
                    msg = d.get("message", "")
                    detail = msg or err_code
                elif isinstance(d, str):
                    detail = d
            except Exception:
                detail = ""

            if e.code == 401 and retry_auth_on_401:
                refreshed = self._refresh_api_auth_state(auth_retry_reason or f"{path}_401")
                self._log_launcher_event(
                    "auth_retry",
                    path=path,
                    reason=auth_retry_reason or path,
                    auth_code=err_code,
                    has_token=bool(refreshed),
                )
                if refreshed:
                    retry_headers = dict(headers)
                    retry_headers["Authorization"] = f"Bearer {refreshed}"
                    retry_req = urllib.request.Request(url, data=data, headers=retry_headers, method=method)
                    try:
                        with urllib.request.urlopen(retry_req, timeout=timeout) as resp:
                            raw = resp.read().decode("utf-8", errors="replace")
                        self._log_launcher_event(
                            "auth_retry_result",
                            path=path,
                            reason=auth_retry_reason or path,
                            auth_code=err_code,
                            ok=True,
                        )
                        return json.loads(raw) if raw.strip() else {}
                    except Exception as retry_error:
                        self._log_launcher_event(
                            "auth_retry_result",
                            path=path,
                            reason=auth_retry_reason or path,
                            auth_code=err_code,
                            ok=False,
                            error=str(retry_error),
                        )
                        raise RuntimeError(str(retry_error)) from retry_error

            if detail:
                if err_code:
                    raise RuntimeError(f"HTTP {e.code} {e.reason} [{err_code}]: {detail}") from e
                raise RuntimeError(f"HTTP {e.code} {e.reason}: {detail}") from e
            raise RuntimeError(f"HTTP {e.code} {e.reason}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error: {e.reason}") from e

    def _refresh_repair_token_from_api(self, timeout: float = 4.0) -> str:
        """
        Call GET /repair-token/refresh to re-sync the repair token after an API restart.
        Returns the refreshed token string, or empty string on any failure.
        Only succeeds when called from localhost with a valid bearer token.
        """
        try:
            bearer = str(self._api_bearer_token or "").strip()
            if not bearer and hasattr(self, "_build_local_bearer_token"):
                try:
                    bearer = str(self._build_local_bearer_token() or "").strip()
                except Exception:
                    bearer = ""
            if bearer:
                self._api_bearer_token = bearer
            refresh_url = self._api_base_url() + "/repair-token/refresh"
            headers = {"Accept": "application/json"}
            if bearer:
                headers["Authorization"] = f"Bearer {bearer}"
            req = urllib.request.Request(
                refresh_url,
                headers=headers,
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            token = (json.loads(raw) if raw.strip() else {}).get("repair_token", "")
            return token if launcher_app.is_valid_repair_token(token) else ""
        except Exception:
            return ""

    @staticmethod
    def _payload_signature(payload: object) -> str:
        try:
            return json.dumps(
                payload,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
        except Exception:
            try:
                return str(payload)
            except Exception:
                return ""

    # ── Recovery helpers (direct — no API dependency) ─────────────────────────
    @staticmethod
    def _summarize_startup_readiness(snapshot: dict[str, object] | None) -> str:
        return summarize_startup_readiness(snapshot)

    def _startup_readiness_status(
        self,
        timeout: float = 1.5,
        *,
        deep: bool = False,
    ) -> tuple[str, str, dict[str, object]]:
        return fetch_startup_readiness(
            self._http_json,
            timeout=timeout,
            deep=deep,
            unauthorized_error=self._is_unauthorized_error,
        )

    def _api_reachable(self, timeout: float = 1.5) -> bool:
        state, _detail = self._api_reachability_status(timeout=timeout)
        return state == "reachable"

    def _api_reachability_status(self, timeout: float = 1.5) -> tuple[str, str]:
        state, detail, _snapshot = self._startup_readiness_status(timeout=timeout)
        return state, detail

    def _run_auth_self_check(self) -> None:
        try:
            payload = self._http_json(
                "/auth/self-check",
                method="GET",
                timeout=2.5,
                retry_auth_on_401=True,
                auth_retry_reason="auth_self_check",
            )
            ok = bool(payload.get("ok", False))
            self._log_launcher_event(
                "auth_self_check",
                ok=ok,
                mode=str(payload.get("mode", "unknown")),
                user_id=str(payload.get("user_id", "")),
                token_source=self._api_token_source,
            )
            self._auth_self_check_ok = ok
            if ok:
                self._status_panel.append_syslog("auth self-check: OK")
            else:
                self._status_panel.append_syslog("auth self-check: ERROR")
        except Exception as e:
            fallback_ok = False
            if "404" in str(e):
                try:
                    self._http_json(
                        "/status",
                        method="GET",
                        timeout=2.5,
                        retry_auth_on_401=True,
                        auth_retry_reason="auth_self_check_status_fallback",
                    )
                    fallback_ok = True
                except Exception:
                    fallback_ok = False
            if fallback_ok:
                self._auth_self_check_ok = True
                self._log_launcher_event(
                    "auth_self_check",
                    ok=True,
                    mode="status_fallback",
                    user_id="",
                    token_source=self._api_token_source,
                )
                self._status_panel.append_syslog("auth self-check: OK (status fallback)")
            else:
                self._auth_self_check_ok = False
                auth_code = self._extract_error_code(str(e))
                self._log_launcher_event(
                    "auth_self_check",
                    ok=False,
                    token_source=self._api_token_source,
                    auth_code=auth_code,
                    error=str(e),
                )
                if auth_code:
                    self._status_panel.append_syslog(f"auth self-check failed [{auth_code}]: {e}")
                else:
                    self._status_panel.append_syslog(f"auth self-check failed: {e}")
        finally:
            self._auth_self_check_inflight = False

    def _start_api_subprocess(self) -> tuple[bool, str]:
        """Launch guppy_api.py as a detached subprocess. Returns (started, msg)."""
        root = Path(__file__).resolve().parent.parent.parent
        script = root / "guppy_api.py"
        if not script.exists():
            return False, "guppy_api.py not found"
        venv_python = root / ".venv" / "Scripts" / "python.exe"
        python = str(venv_python) if venv_python.exists() else sys.executable
        flags = {}
        if sys.platform == "win32":
            flags["creationflags"] = subprocess.CREATE_NO_WINDOW
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
            startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
            flags["startupinfo"] = startupinfo
        try:
            subprocess.Popen([python, str(script)], cwd=str(root), **flags)
            # Give it a moment to publish backend-owned startup readiness.
            deadline = time.time() + 6.0
            while time.time() < deadline:
                time.sleep(0.5)
                state, detail = self._api_reachability_status(timeout=0.8)
                if state == "reachable":
                    return True, detail or "api started and published startup readiness"
                if state == "auth_failed":
                    return False, detail or "api requires refreshed auth"
            return False, "api process started but not yet reachable"
        except Exception as e:
            return False, str(e)

    def _start_supervised_api_subprocess(self) -> tuple[bool, str]:
        """Launch the supervised API batch entry point. Returns (started, msg)."""
        root = Path(__file__).resolve().parent.parent.parent
        script = root / "bin" / "launch_api_supervised.bat"
        if not script.exists():
            return False, "launch_api_supervised.bat not found"
        try:
            kwargs: dict[str, object] = {"cwd": str(root)}
            if sys.platform == "win32":
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
                startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
                kwargs["startupinfo"] = startupinfo
                subprocess.Popen(["cmd.exe", "/c", str(script)], **kwargs)
            else:
                subprocess.Popen([str(script)], **kwargs)
            deadline = time.time() + 8.0
            while time.time() < deadline:
                time.sleep(0.5)
                state, detail = self._api_reachability_status(timeout=0.8)
                if state == "reachable":
                    return True, detail or "supervised api started and published startup readiness"
                if state == "auth_failed":
                    return False, detail or "api requires refreshed auth"
            return False, "supervised api launcher started but the API is not yet reachable"
        except Exception as exc:
            return False, str(exc)

    def _ensure_api_reachable_for_command(self) -> tuple[bool, str]:
        state, detail = self._api_reachability_status(timeout=0.8)
        if state == "reachable":
            return True, detail or "api already reachable"
        started, detail = self._start_supervised_api_subprocess()
        if started:
            return True, detail
        fallback_started, fallback_detail = self._start_api_subprocess()
        if fallback_started:
            return True, fallback_detail
        return False, f"{detail}; fallback: {fallback_detail}"

    def _direct_warmup(self) -> dict:
        """Warmup: check freshness of key runtime files."""
        stale, fresh = [], []
        now = time.time()
        for name in ("guppy.status", "guppy.heartbeat"):
            p = _RUNTIME / name
            if not p.exists():
                stale.append(f"{name}=missing")
            elif now - p.stat().st_mtime > 300:
                stale.append(f"{name}=stale")
            else:
                fresh.append(name)
        ok = len(stale) == 0
        parts = []
        if fresh:
            parts.append(f"fresh: {', '.join(fresh)}")
        if stale:
            parts.append(f"stale/missing: {', '.join(stale)}")
        return {
            "ok": ok,
            "summary": "; ".join(parts) or "nothing to report",
            "category": "runtime_ready" if ok else "runtime_stale",
        }

    def _direct_audit_runtime(self) -> dict:
        """Audit: collect runtime status files into a diagnostics JSON."""
        bundle: dict = {"ts": datetime.now(timezone.utc).isoformat(), "files": {}}
        issues: list[str] = []
        for name in ("guppy.status", "resource_envelope.status.json", "logging_health_snapshot.json"):
            p = _RUNTIME / name
            if not p.exists():
                bundle["files"][name] = {"missing": True}
                issues.append(f"{name}=missing")
                continue
            try:
                bundle["files"][name] = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                bundle["files"][name] = {"error": "unreadable"}
                issues.append(f"{name}=unreadable")
        out = _RUNTIME / f"diagnostics_bundle_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        try:
            out.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
            summary = f"bundle written: {out.name}"
            if issues:
                summary = f"{summary}; runtime issues: {', '.join(issues)}"
            return {
                "ok": True,
                "summary": summary,
                "category": "runtime_stale" if issues else "runtime_ready",
            }
        except Exception as e:
            return {"ok": False, "summary": str(e), "category": "runtime_stale"}

    def _direct_health_snapshot(self) -> dict:
        """Health snapshot: read runtime status files directly."""
        results = {}
        for agent in ("guppy",):
            hb = _RUNTIME / f"{agent}.heartbeat"
            st = _RUNTIME / f"{agent}.status"
            results[agent] = {
                "heartbeat": hb.exists(),
                "status_age_s": round(time.time() - st.stat().st_mtime) if st.exists() else None,
            }
        ok = any(v["heartbeat"] for v in results.values())
        summary = "; ".join(
            f"{a}={'LIVE' if v['heartbeat'] else 'OFFLINE'}" for a, v in results.items()
        )
        return {
            "ok": ok,
            "summary": summary,
            "category": "runtime_ready" if ok else "runtime_stale",
        }

    def _on_recovery_requested(self, action: str) -> None:
        act = (action or "").strip().lower()
        self._recovery_events.put({"kind": "status", "text": f"Recovery: {act}..."})
        self._recovery_events.put({"kind": "syslog", "text": f"recovery: {act}"})
        self._log_launcher_event("recovery_requested", action=act)

        threading.Thread(target=self._run_recovery_request, args=(act,), daemon=True).start()

    def _run_recovery_request(self, act: str) -> None:
        """Run recovery work off the UI thread; enqueue UI updates for main-thread drain."""
        if not act:
            return

        try:
            # ── Try API path first ─────────────────────────────────────────────
            api_state, api_detail = self._api_reachability_status()
            if api_state == "reachable":
                if act == "health_snapshot":
                    status  = self._http_json("/status", method="GET")
                    startup = self._http_json("/startup/check?deep=true", method="GET")
                    status_state  = str(status.get("status", "unknown")).upper()
                    startup_state = str(startup.get("overall", "unknown")).upper()
                    summary = f"status={status_state} startup={startup_state}"
                    category = "runtime_ready"
                    if startup_state not in {"GO", "READY", "OK", "PASS"}:
                        category = "runtime_stale"
                    formatted = self._push_recovery_outcome("health_snapshot", category == "runtime_ready", summary, category)
                    msg = f"Snapshot {'OK' if category == 'runtime_ready' else 'ERROR'}: {formatted}"
                elif act in {"warmup", "restart_daemon", "audit_runtime"}:
                    result  = self._http_json("/repair", method="POST",
                                             payload={"action": act, "dry_run": False},
                                             timeout=12.0)
                    ok      = bool(result.get("ok", False))
                    summary = str(result.get("summary", "done"))
                    category = self._classify_recovery_summary(summary, ok, "recovery_ok" if ok else "recovery_error")
                    if act == "restart_daemon":
                        self._refresh_api_auth_state("restart_daemon_api")
                    formatted = self._push_recovery_outcome(act, ok, summary, category)
                    msg = f"Recovery {act}: {'OK' if ok else 'ERROR'} — {formatted}"
                else:
                    raise ValueError(f"unsupported action: {act}")

                self._recovery_events.put({"kind": "status", "text": msg})
                self._recovery_events.put({"kind": "syslog", "text": msg})
                return

            if api_state == "auth_failed":
                formatted = self._push_recovery_outcome(act, False, api_detail, "auth_failed")
                msg = f"Recovery {act}: ERROR — {formatted}"
                self._recovery_events.put({"kind": "status", "text": msg})
                self._recovery_events.put({"kind": "syslog", "text": msg})
                return

            # ── API not reachable — run directly ───────────────────────────────
            api_summary = self._format_recovery_summary("api_unreachable", api_detail or "running direct recovery")
            self._recovery_events.put({"kind": "syslog", "text": api_summary})

            if act == "health_snapshot":
                result = self._direct_health_snapshot()
            elif act == "warmup":
                result = self._direct_warmup()
            elif act == "restart_daemon":
                # restart_daemon means "bring the API (and daemon) up"
                self._recovery_events.put({"kind": "syslog", "text": "starting api server..."})
                started, detail = self._start_api_subprocess()
                result = {
                    "ok": started,
                    "summary": detail,
                    "category": "runtime_ready" if started else "api_unreachable",
                }
                self._refresh_api_auth_state("restart_daemon_direct")
            elif act == "audit_runtime":
                result = self._direct_audit_runtime()
            else:
                raise ValueError(f"unsupported action: {act}")

            ok      = bool(result.get("ok", False))
            summary = str(result.get("summary", "done"))
            category = str(result.get("category", "")) or self._classify_recovery_summary(summary, ok, "api_unreachable")
            formatted = self._push_recovery_outcome(act, ok, summary, category)
            msg     = f"Direct {act}: {'OK' if ok else 'ERROR'} — {formatted}"
            self._recovery_events.put({"kind": "status", "text": msg})
            self._recovery_events.put({"kind": "syslog", "text": msg})

        except Exception as e:
            formatted = self._push_recovery_outcome(act or "recovery", False, str(e))
            msg = f"Recovery {act} error: {formatted}"
            self._recovery_events.put({"kind": "status", "text": msg})
            self._recovery_events.put({"kind": "syslog", "text": msg})

    def _on_model_selected(self, model: str) -> None:
        self._status_panel.append_syslog(f"active model -> {model}")

        self._refresh_personalization_state()
        self._update_route_preview(self._last_command)

    def _on_runtime_settings_saved(self, settings: dict) -> None:
        backend = str(settings.get("local_runtime_backend", "ollama") or "ollama").strip().lower() or "ollama"
        self._status_panel.append_syslog(f"local runtime saved -> {backend}")
        self._refresh_personalization_state()
        self._update_route_preview(self._last_command)
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
        descriptor = build_windows_ops_descriptor(action)
        target = descriptor.action
        plan = self._windows_ops_plan(target)
        label = str(descriptor.label or plan.get("label", "") or "").strip()
        changes = str(descriptor.changes or plan.get("changes", "") or "").strip()
        if descriptor.execution_kind == WindowsOpsExecutionKind.TERMINAL_RECIPE:
            commands = list(descriptor.commands)
            if not commands:
                self._status_panel.append_syslog(f"windows ops unavailable: {action}")
                return
            guidance = self._windows_ops_guidance(target, ok=True, phase="queued")
            queued = self._advanced_view.queue_terminal_recipe(
                commands,
                label=label,
                recipe_context={
                    "kind": "windows_ops",
                    "action": target,
                    "changes": changes,
                    "pre_snapshot": self._collect_windows_service_snapshot(),
                },
            )
            if queued:
                summary = str(descriptor.request_summary or f"{label.title()} queued in Settings terminal")
                self._set_daily_activity(summary)
                self._status_panel.append_syslog(str(descriptor.syslog_message or f"{label.lower()} queued"))
                self._record_windows_ops_state(
                    target,
                    summary,
                    changes,
                    ok=True,
                    commands=commands,
                    phase="queued",
                    next_step=str(guidance.get("next_step", "") or ""),
                    fix_target=str(guidance.get("fix_target", "") or ""),
                    docs_hint=str(guidance.get("docs_hint", "") or ""),
                    entry_point=str(guidance.get("entry_point", "") or ""),
                )
                self._log_launcher_event(
                    "windows_ops_action",
                    action=target,
                    queued=True,
                    commands=len(commands),
                    next_step=str(guidance.get("next_step", "") or ""),
                    fix_target=str(guidance.get("fix_target", "") or ""),
                )
            else:
                summary = f"{label.title()} failed to queue"
                self._status_panel.append_syslog(f"{label.lower()} failed to queue")
                failed_guidance = self._windows_ops_guidance(target, ok=False, phase="queue_failed")
                self._record_windows_ops_state(
                    target,
                    summary,
                    changes or "No update commands were queued.",
                    ok=False,
                    commands=commands,
                    phase="queue_failed",
                    next_step=str(failed_guidance.get("next_step", "") or ""),
                    fix_target=str(failed_guidance.get("fix_target", "") or ""),
                    docs_hint=str(failed_guidance.get("docs_hint", "") or ""),
                    entry_point=str(failed_guidance.get("entry_point", "") or ""),
                )
                self._log_launcher_event(
                    "windows_ops_action",
                    action=target,
                    queued=False,
                    commands=len(commands),
                    next_step=str(failed_guidance.get("next_step", "") or ""),
                    fix_target=str(failed_guidance.get("fix_target", "") or ""),
                )
            return
        if descriptor.execution_kind == WindowsOpsExecutionKind.SUBPROCESS and target == "start_supervised_api":
            guidance = self._windows_ops_guidance(target, ok=True, phase="queued")
            summary = str(descriptor.request_summary or "Supervised API launch requested from Settings")
            self._status_panel.append_syslog(str(descriptor.syslog_message or "supervised api requested"))
            self._set_daily_activity(summary)
            self._record_windows_ops_state(
                target,
                summary,
                changes,
                ok=True,
                phase="queued",
                next_step=str(guidance.get("next_step", "") or ""),
                fix_target=str(guidance.get("fix_target", "") or ""),
                docs_hint=str(guidance.get("docs_hint", "") or ""),
                entry_point=str(guidance.get("entry_point", "") or ""),
            )
            self._log_launcher_event(
                "windows_ops_action",
                action=target,
                queued=True,
                next_step=str(guidance.get("next_step", "") or ""),
                fix_target=str(guidance.get("fix_target", "") or ""),
            )
            started, detail = self._start_supervised_api_subprocess()
            if started:
                self._refresh_api_auth_state("start_supervised_api")
            final_guidance = self._windows_ops_guidance(target, ok=started, phase="completed")
            final_summary = detail or ("supervised api started and reachable" if started else "supervised api did not become reachable")
            artifacts = self._windows_ops_artifact_refs(target, self._collect_windows_service_snapshot())
            event_id = LauncherWindow._default_windows_ops_event_id(target)
            self._record_windows_ops_state(
                target,
                final_summary,
                changes,
                ok=started,
                event_id=event_id,
                phase="completed",
                next_step=str(final_guidance.get("next_step", "") or ""),
                fix_target=str(final_guidance.get("fix_target", "") or ""),
                docs_hint=str(final_guidance.get("docs_hint", "") or ""),
                entry_point=str(final_guidance.get("entry_point", "") or ""),
                artifacts=artifacts,
            )
            self._log_launcher_event(
                "windows_ops_completed",
                action=target,
                ok=started,
                summary=final_summary,
                event_id=event_id,
                next_step=str(final_guidance.get("next_step", "") or ""),
                fix_target=str(final_guidance.get("fix_target", "") or ""),
                artifacts=artifacts,
                release_receipt=str(self._windows_release_receipt_path()),
                release_summary=str(self._windows_release_summary_path()),
            )
            self._status_panel.append_syslog(final_summary)
            self._advanced_view.append_log(final_summary)
            self._set_daily_activity(final_summary)
            return
        if descriptor.execution_kind == WindowsOpsExecutionKind.RECOVERY_CHAIN and target in {"restart_runtime", "repair_runtime"}:
            summary = str(descriptor.request_summary or f"{label.title()} queued")
            self._status_panel.append_syslog(str(descriptor.syslog_message or f"{label.lower()} requested"))
            self._set_daily_activity(summary)
            self._start_windows_ops_chain(target)
            guidance = self._windows_ops_guidance(target, ok=True, phase="queued")
            self._record_windows_ops_state(
                target,
                summary,
                changes,
                ok=True,
                steps_completed=0,
                steps_total=len(descriptor.chain_steps),
                phase="queued",
                next_step=str(guidance.get("next_step", "") or ""),
                fix_target=str(guidance.get("fix_target", "") or ""),
                docs_hint=str(guidance.get("docs_hint", "") or ""),
                entry_point=str(guidance.get("entry_point", "") or ""),
            )
            self._log_launcher_event(
                "windows_ops_action",
                action=target,
                queued=True,
                next_step=str(guidance.get("next_step", "") or ""),
                fix_target=str(guidance.get("fix_target", "") or ""),
            )
            for step in descriptor.chain_steps:
                if step.delay_ms <= 0:
                    self._on_recovery_requested(step.name)
                else:
                    QTimer.singleShot(step.delay_ms, lambda recovery_action=step.name: self._on_recovery_requested(recovery_action))
            return
        self._status_panel.append_syslog(f"windows ops unavailable: {action}")

    def _on_home_starter_requested(self, starter_id: str, prompt: str) -> None:
        self._on_tab_change(0)
        self._update_route_preview(prompt)
        self._set_daily_activity(f"Starter loaded: {starter_id}")
        self._status_panel.append_syslog(f"home starter loaded: {starter_id}")
        self._log_launcher_event("home_starter_loaded", starter_id=starter_id)

    def _on_assistant_command(self, command: str) -> None:
        cmd = (command or "").strip()
        if not cmd:
            return
        if getattr(self, "_request_in_flight", False):
            add_assistant = getattr(self._assistant_view, "add_assistant_message", None)
            if callable(add_assistant):
                add_assistant("A request is already in progress. Please wait for it to finish.")
            else:
                self._assistant_view.add_system_message("A request is already in progress. Please wait for it to finish.")
            return
        selected_mode = self._assistant_view.selected_mode()
        mode_ok, mode_err = LauncherWindow._validate_mode_ready(self, selected_mode)
        if not mode_ok:
            self._assistant_view.set_status("Ready")
            add_assistant = getattr(self._assistant_view, "add_assistant_message", None)
            if callable(add_assistant):
                add_assistant(mode_err)
            else:
                self._assistant_view.add_system_message(mode_err)
            self._status_panel.append_syslog(f"chat blocked: {mode_err}")
            return

        self._last_command = cmd
        instance_name = getattr(self, "_active_instance_name", "guppy-primary") or "guppy-primary"
        chat_context_getter = getattr(self._assistant_view, "chat_context", None)
        selected_persona = "guppy"
        if callable(chat_context_getter):
            try:
                _mode, selected_persona = chat_context_getter()
            except Exception:
                selected_persona = "guppy"
        route_updater = getattr(self, "_update_route_preview", None)
        if callable(route_updater):
            route_updater(cmd)
        # Increment before starting the worker so any in-flight response from
        # a prior command carries a stale sequence number and is dropped.
        self._active_request_seq += 1
        req_seq = self._active_request_seq
        self._request_in_flight = True
        history_getter = getattr(self._assistant_view, "recent_history", None)
        history = history_getter(limit=12) if callable(history_getter) else []
        active_library_items = list(getattr(self, "_active_library_context_items", []))
        library_submission = build_library_chat_submission(cmd, history, active_library_items)
        request_message = library_submission.request_message
        history = library_submission.history
        idempotency_key = f"launcher-{uuid.uuid4().hex}"
        if library_submission.context_notice:
            note_context_submission = getattr(self._assistant_view, "note_active_context_submission", None)
            if callable(note_context_submission):
                note_context_submission(library_submission.context_notice)
        self._assistant_view.add_user_message(cmd)
        if _INSTANCE_LOGGER_AVAILABLE:
            append_instance_log(
                instance_name,
                {
                    "role": "user",
                    "source_instance": instance_name,
                    "message": cmd,
                    "status": "submitted",
                    "model": selected_mode,
                },
            )
        set_in_flight = getattr(self._assistant_view, "set_request_in_flight", None)
        if callable(set_in_flight):
            set_in_flight(True)
        self._assistant_view.set_status(library_submission.status_text)
        if library_submission.background_event:
            self._assistant_view.set_background_event(library_submission.background_event)
        activity_setter = getattr(self, "_set_daily_activity", None)
        if callable(activity_setter):
            activity_setter(f"Working on: {cmd[:96]}")
        self._status_panel.append_syslog("command queued")
        self._log_launcher_event("command_submitted", command=cmd, seq=req_seq, idempotency_key=idempotency_key)
        request_timeout = LauncherWindow._chat_timeout_for_request(selected_mode, cmd)
        retry_timeout = max(request_timeout + 20.0, 60.0)

        def _worker() -> None:
            payload = {
                "message": request_message,
                "session_id": self._chat_session_id,
                "mode": selected_mode,
                "persona": selected_persona,
                "history": history,
                "idempotency_key": idempotency_key,
            }
            try:
                recovered_before_chat = False
                if not self._api_reachable(timeout=0.8):
                    recovered, recovery_detail = self._ensure_api_reachable_for_command()
                    recovered_before_chat = recovered
                    self._log_launcher_event(
                        "command_api_recovery",
                        seq=req_seq,
                        ok=recovered,
                        detail=recovery_detail,
                        idempotency_key=idempotency_key,
                    )
                    if not recovered:
                        raise RuntimeError(recovery_detail or "Could not reach the local API service.")
                primary_timeout = max(request_timeout, 30.0) if recovered_before_chat else request_timeout
                try:
                    resp = self._http_json(
                        "/chat",
                        method="POST",
                        payload=payload,
                        timeout=primary_timeout,
                        retry_auth_on_401=True,
                        auth_retry_reason="chat",
                    )
                except Exception as first_exc:
                    first_text = str(first_exc)
                    lowered = first_text.lower()
                    if "timed out" in lowered and recovered_before_chat:
                        self._log_launcher_event(
                            "command_recovery_warmup_timeout",
                            seq=req_seq,
                            timeout_s=primary_timeout,
                            idempotency_key=idempotency_key,
                        )
                        raise RuntimeError(
                            "The local API restarted, but the first reply is still warming up. Please retry now."
                        ) from first_exc
                    if "timed out" in lowered and primary_timeout < retry_timeout:
                        self._log_launcher_event(
                            "command_timeout_retry",
                            seq=req_seq,
                            timeout_s=primary_timeout,
                            retry_timeout_s=retry_timeout,
                            idempotency_key=idempotency_key,
                        )
                        resp = self._http_json(
                            "/chat",
                            method="POST",
                            payload=payload,
                            timeout=retry_timeout,
                            retry_auth_on_401=True,
                            auth_retry_reason="chat_timeout_retry",
                        )
                    elif any(token in lowered for token in ("10061", "connection refused", "actively refused")):
                        recovered, recovery_detail = self._ensure_api_reachable_for_command()
                        self._log_launcher_event(
                            "command_api_recovery",
                            seq=req_seq,
                            ok=recovered,
                            detail=recovery_detail,
                            phase="retry_after_refused",
                            idempotency_key=idempotency_key,
                        )
                        if recovered:
                            resp = self._http_json(
                                "/chat",
                                method="POST",
                                payload=payload,
                                timeout=retry_timeout,
                                retry_auth_on_401=True,
                                auth_retry_reason="chat_connection_retry",
                            )
                        else:
                            raise
                    else:
                        raise
                text = str(resp.get("response") or "").strip()
                if not text:
                    text = "No response payload received."
                if _INSTANCE_LOGGER_AVAILABLE:
                    append_instance_log(
                        instance_name,
                        {
                            "role": "assistant",
                            "source_instance": instance_name,
                            "message": text,
                            "status": "ok",
                            "model": selected_mode,
                        },
                    )
                self._assistant_events.put(("assistant", text, req_seq))
                emitter = getattr(self, "assistant_event_queued", None)
                if emitter is not None and hasattr(emitter, "emit"):
                    emitter.emit()
                self._log_launcher_event(
                    "command_response",
                    ok=True,
                    chars=len(text),
                    seq=req_seq,
                    idempotency_key=idempotency_key,
                )
            except Exception as e:
                err_text = str(e)
                if self._is_unauthorized_error(err_text):
                    auth_code = self._extract_error_code(err_text)
                    self._log_launcher_event(
                        "command_auth_error",
                        seq=req_seq,
                        auth_code=auth_code,
                        error=err_text,
                        idempotency_key=idempotency_key,
                    )
                    self._refresh_api_auth_state("chat_401")
                    try:
                        retry_resp = self._http_json(
                            "/chat",
                            method="POST",
                            payload=payload,
                            timeout=retry_timeout,
                            retry_auth_on_401=True,
                            auth_retry_reason="chat_retry",
                        )
                        retry_text = str(retry_resp.get("response") or "").strip()
                        if not retry_text:
                            retry_text = "No response payload received."
                        if _INSTANCE_LOGGER_AVAILABLE:
                            append_instance_log(
                                instance_name,
                                {
                                    "role": "assistant",
                                    "source_instance": instance_name,
                                    "message": retry_text,
                                    "status": "ok",
                                    "model": selected_mode,
                                },
                            )
                        self._assistant_events.put(("assistant", retry_text, req_seq))
                        emitter = getattr(self, "assistant_event_queued", None)
                        if emitter is not None and hasattr(emitter, "emit"):
                            emitter.emit()
                        self._log_launcher_event(
                            "command_response",
                            ok=True,
                            chars=len(retry_text),
                            seq=req_seq,
                            retried_after_401=True,
                            idempotency_key=idempotency_key,
                        )
                        return
                    except Exception as retry_error:
                        retry_auth_code = self._extract_error_code(str(retry_error))
                        if retry_auth_code:
                            self._log_launcher_event(
                                "command_auth_error",
                                seq=req_seq,
                                auth_code=retry_auth_code,
                                phase="retry",
                                error=str(retry_error),
                                idempotency_key=idempotency_key,
                            )
                        err_text = f"{err_text}; retry failed: {retry_error}"

                self._assistant_events.put(("error", err_text, req_seq))
                emitter = getattr(self, "assistant_event_queued", None)
                if emitter is not None and hasattr(emitter, "emit"):
                    emitter.emit()
                self._log_launcher_event(
                    "command_response",
                    ok=False,
                    error=err_text,
                    seq=req_seq,
                    idempotency_key=idempotency_key,
                )

        threading.Thread(target=_worker, daemon=True).start()

    def _on_quick_action(self, action: str) -> None:
        target = (action or "").strip().lower()
        if target == "notifications":
            self._on_tab_change(4)
            self._advanced_view.focus_operator_logs(
                "WARN",
                note="Top bar notifications opened launcher warnings and recovery events.",
            )
            self._set_daily_activity("Settings opened launcher warnings and recovery events")
            self._status_panel.append_syslog("Settings warnings opened from top bar")
            self._log_launcher_event("quick_action", action="notifications")
            return
        if target == "terminal":
            self._on_tab_change(4)
            note = "Top bar terminal opened operator logs"
            if self._last_command:
                note += f". Last command: {self._last_command}"
            self._advanced_view.focus_operator_logs("ALL", note=note)
            self._advanced_view.focus_terminal(
                note=f"[launcher] terminal opened from top bar. cwd={_RUNTIME.parent}"
            )
            self._set_daily_activity("Settings opened operator logs and workflow controls")
            self._status_panel.append_syslog("Settings terminal opened from top bar")
            self._log_launcher_event("quick_action", action="terminal", last_command=self._last_command)
            return
        self._status_panel.append_syslog(f"quick action unavailable: {action}")

    def _refresh_notification_badge(self) -> None:
        path = _RUNTIME / "launcher_events.jsonl"
        if not path.exists():
            self._topbar.set_notification_badge(0, severity="info")
            return
        try:
            mtime = path.stat().st_mtime
        except Exception:
            mtime = 0.0
        if mtime == self._notification_badge_mtime:
            return
        self._notification_badge_mtime = mtime
        events = read_jsonl_tail(path, limit=80)
        warn_count = 0
        error_count = 0
        for item in events:
            if not isinstance(item, dict):
                continue
            level = self._event_level(item)
            if level == "ERROR":
                error_count += 1
            elif level == "WARN":
                warn_count += 1
        severity = "error" if error_count else ("warn" if warn_count else "info")
        total = error_count + warn_count
        self._topbar.set_notification_badge(total, severity=severity)

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
