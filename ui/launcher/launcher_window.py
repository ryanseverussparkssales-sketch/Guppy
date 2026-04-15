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

try:
    from src.guppy.api.auth import create_access_token as _create_access_token
    _API_AUTH_HELPER = True
except Exception:
    _API_AUTH_HELPER = False

try:
    from utils import secret_store as _secret_store
    _SECRET_STORE_AVAILABLE = True
except Exception:
    _secret_store = None  # type: ignore[assignment]
    _SECRET_STORE_AVAILABLE = False

try:
    from utils.safe_io import read_json_dict, read_jsonl_tail as _safe_jsonl_tail
    _SAFE_IO = True
except Exception:
    _SAFE_IO = False

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

from inference_router import resolve_ui_route
from . import tokens as T
from .stylesheet import SHEET
from .components import Sidebar, TopBar, StatusPanel
from .views import (
    AssistantView,
    InstanceManagerView,
    ToolsView,
    SettingsView,
    AdvancedView,
    ModelsView,
    VoicesView,
)

try:
    from utils.personalization_config import (
        ensure_personalization_scaffold,
        list_persona_choices,
        load_persona_config,
        load_voice_bindings,
        resolve_voice_binding,
    )
    _PERSONALIZATION_BOOTSTRAP_AVAILABLE = True
except Exception:
    _PERSONALIZATION_BOOTSTRAP_AVAILABLE = False

    def list_persona_choices(_persona_config=None):
        return [{"id": "guppy", "name": "Guppy", "label": "Guppy [GLOBAL]"}]

    def load_persona_config():
        return {}

    def load_voice_bindings():
        return {}

    def resolve_voice_binding(*, persona_id: str = "", model_id: str = "", voice_bindings: dict | None = None):
        del persona_id, model_id, voice_bindings
        return {"engine": "EDGE TTS", "voice_id": "en-GB-RyanNeural", "source": "default"}

try:
    from utils.instance_logger import append_instance_log, read_instance_log_tail
    _INSTANCE_LOGGER_AVAILABLE = True
except Exception:
    _INSTANCE_LOGGER_AVAILABLE = False

    def append_instance_log(*_args, **_kwargs):
        return None

    def read_instance_log_tail(*_args, **_kwargs):
        return []

try:
    from src.guppy.voice.voice import GuppyVoice
    _VOICE_CAPTURE_AVAILABLE = True
except Exception:
    GuppyVoice = None  # type: ignore[assignment]
    _VOICE_CAPTURE_AVAILABLE = False

_RUNTIME = Path(__file__).resolve().parent.parent.parent / "runtime"
_CONFIG = Path(__file__).resolve().parent.parent.parent / "config"
_START_TIME = time.monotonic()


def _read_json(path: Path) -> dict:
    if _SAFE_IO:
        return read_json_dict(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _read_jsonl_tail(path: Path, limit: int = 50) -> list[dict]:
    if _SAFE_IO:
        return _safe_jsonl_tail(path, limit)
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    out: list[dict] = []
    for line in lines[-limit:]:
        txt = line.strip()
        if not txt:
            continue
        try:
            obj = json.loads(txt)
            if isinstance(obj, dict):
                out.append(obj)
        except Exception:
            continue
    return out


def _is_valid_repair_token(token: str) -> bool:
    """Return True if *token* is a non-empty hex string no longer than 256 chars."""
    if not token or len(token) > 256:
        return False
    return all(ch in "0123456789abcdef" for ch in token.lower())


class LauncherWindow(QMainWindow):
    assistant_event_queued = Signal()

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
        self.setWindowTitle("Guppy AI  //  COMMAND_INTERFACE")
        self.setMinimumSize(1120, 720)
        self.setStyleSheet(SHEET)
        self._last_command = ""
        self._last_recovery_signature = ""
        self._startup_logged_first_poll = False
        self._startup_first_poll_ok = False
        self._startup_budget_ms = int(os.environ.get("GUPPY_STARTUP_PHASE_WARN_MS", "750"))
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
        self._embedded_online: set[str] = set()
        self._assistant_events: SimpleQueue[tuple[str, str, int]] = SimpleQueue()
        self._recovery_events: SimpleQueue[dict[str, object]] = SimpleQueue()
        self._last_instance_snapshot: dict[str, object] = {}
        self._instance_snapshot_expires_at = 0.0
        self._instance_snapshot_ttl_s = float(os.environ.get("GUPPY_INSTANCE_SNAPSHOT_TTL_S", "6.0"))
        self._scaffold_created: dict[str, Path] = {}
        self._deferred_syslog: SimpleQueue[str] = SimpleQueue()
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
        self._tools_view      = ToolsView(self)
        self._advanced_view   = AdvancedView(self)
        self._settings_view   = SettingsView(self)
        self._models_view     = ModelsView(self)
        self._voices_view     = VoicesView(self)
        self._advanced_view.attach_settings_panel(self._settings_view)

        for view in [
            self._assistant_view,
            self._instance_manager_view,
            self._tools_view,
            self._advanced_view,
            self._models_view,
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
        self._models_view.model_selected.connect(self._on_model_selected)
        self._voices_view.bindings_changed.connect(self._on_voice_bindings_changed)
        self._topbar.search_submitted.connect(self._on_search)
        self._topbar.quick_action.connect(self._on_quick_action)
        self._topbar.launcher_context_requested.connect(self._assistant_view.toggle_launcher_panel)
        self._assistant_view.command_submitted.connect(self._on_assistant_command)
        self._assistant_view.starter_requested.connect(self._on_home_starter_requested)
        self._assistant_view.cancel_requested.connect(self._on_cancel_assistant_request)
        self._assistant_view.mic_requested.connect(self._on_mic_requested)
        self.assistant_event_queued.connect(self._drain_assistant_events)
        self._assistant_view.chat_context_changed.connect(self._on_chat_context_changed)
        self._assistant_view.launcher_summary_changed.connect(self._topbar.set_launcher_summary)
        self._instance_manager_view.refresh_requested.connect(self._on_instance_manager_refresh)
        self._instance_manager_view.activate_requested.connect(self._on_instance_selected)
        self._instance_manager_view.create_requested.connect(self._on_instance_create_requested)
        self._instance_manager_view.delete_requested.connect(self._on_instance_delete_requested)
        self._instance_manager_view.logs_requested.connect(self._on_instance_logs_requested)
        self._topbar.instance_selected.connect(self._on_instance_selected)
        self._status_panel.agent_init_requested.connect(self._on_agent_init_requested)
        self._assistant_view.set_session_id(self._chat_session_id)
        self._topbar.set_launcher_summary("AUTO / GUPPY / LIGHT [EDIT]")
        self._bootstrap_instance_switcher()
        self._refresh_personalization_state()

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

    @staticmethod
    def _voice_option_choices(voice_bindings: dict) -> list[tuple[str, str]]:
        options: list[tuple[str, str]] = [("Default", "default")]
        seen = {"default"}

        def _add_binding(engine: str, voice_id: str) -> None:
            value = f"{engine}:{voice_id}"
            if not engine or not voice_id or value in seen:
                return
            seen.add(value)
            options.append((f"{engine} / {voice_id}", value))

        defaults = voice_bindings.get("defaults", {}) if isinstance(voice_bindings, dict) else {}
        if isinstance(defaults, dict):
            _add_binding(str(defaults.get("engine", "")).strip(), str(defaults.get("voice_id", "")).strip())

        bindings = voice_bindings.get("bindings", {}) if isinstance(voice_bindings, dict) else {}
        if isinstance(bindings, dict):
            for mapping_key in ("by_persona", "by_model"):
                mapping = bindings.get(mapping_key, {})
                if not isinstance(mapping, dict):
                    continue
                for item in mapping.values():
                    if isinstance(item, dict):
                        _add_binding(str(item.get("engine", "")).strip(), str(item.get("voice_id", "")).strip())

        imports = voice_bindings.get("imports", []) if isinstance(voice_bindings, dict) else []
        if isinstance(imports, list):
            for item in imports:
                if not isinstance(item, dict):
                    continue
                _add_binding(str(item.get("engine", "")).strip(), str(item.get("voice_id", "")).strip())
        return options

    def _refresh_personalization_state(self, preferred_persona: str = "") -> None:
        try:
            persona_config = load_persona_config() if _PERSONALIZATION_BOOTSTRAP_AVAILABLE else {}
            voice_bindings = load_voice_bindings() if _PERSONALIZATION_BOOTSTRAP_AVAILABLE else {}
            persona_choices = list_persona_choices(persona_config)
            persona_options = [(item.get("name", item.get("id", "guppy")), item.get("id", "guppy")) for item in persona_choices]
            target_persona = preferred_persona or self._assistant_view.chat_context()[1]
            self._assistant_view.set_persona_options(persona_options, selected=target_persona)
            self._instance_manager_view.set_persona_options(persona_options, selected=target_persona)
            self._instance_manager_view.set_voice_options(self._voice_option_choices(voice_bindings), selected="default")
            self._voices_view._load_assignment_options()
            self._voices_view._refresh_bindings_summary()
            active_model_id = self._assistant_model_id(self._assistant_view.selected_mode())

            voice_choice = resolve_voice_binding(
                persona_id=self._assistant_view.chat_context()[1],
                model_id=active_model_id,
                voice_bindings=voice_bindings,
            )
            self._assistant_view.set_runtime_facts(
                profile=self._assistant_view._cb_profile.currentText().strip().lower() or "standard",
                model=active_model_id,
                voice=self._voice_binding_summary(voice_choice),
                latency="-",
                last_query=self._last_command or "-",
            )
            self._advanced_view.set_daily_context_runtime(self._assistant_view._runtime_facts.text())
        except Exception as exc:
            self._status_panel.append_syslog(f"personalization refresh failed: {exc}")

    def _update_route_preview(self, text: str = "") -> None:
        sample = (text or self._last_command or "").strip()
        if not sample:
            self._assistant_view.set_route_preview(reason="waiting for command")
            self._advanced_view.set_daily_context_route(self._assistant_view._route_facts.text())
            return
        mode, persona = self._assistant_view.chat_context()
        try:
            decision = resolve_ui_route(
                user_text=sample,
                mode=mode,
                api_key_available=bool((os.environ.get("ANTHROPIC_API_KEY", "") or "").strip()),
            )
            self._assistant_view.set_route_preview(
                task_type=str(decision.get("task_type", "unknown")),
                route=str(decision.get("route", "pending")),
                model=str(decision.get("model", "")),
                backup_model=str(decision.get("backup_model", "")),
                reason=str(decision.get("route_reason", "")),
                evidence=self._route_evidence_summary(decision),
            )
            self._advanced_view.set_daily_context_route(self._assistant_view._route_facts.text())
        except Exception as exc:
            self._assistant_view.set_route_preview(reason=f"preview failed: {exc}")
            self._advanced_view.set_daily_context_route(self._assistant_view._route_facts.text())

    def _set_daily_activity(self, text: str) -> None:
        self._assistant_view.set_background_event(text)
        self._advanced_view.set_daily_context_activity(text)

    def _sync_right_tray(self, active_payload: dict[str, object]) -> None:
        workspace_name = str(active_payload.get("name", self._active_instance_name) or self._active_instance_name)
        workspace_type = str(active_payload.get("type", "user_instance") or "user_instance")
        self._status_panel.set_workspace(workspace_name, workspace_type)
        self._status_panel.set_tool_states(self._tools_view.current_tool_states())
        description = str(
            active_payload.get("description", "") or self._workspace_default_purpose(workspace_type)
        ).strip()
        self._advanced_view.set_daily_context_workspace(
            f"Workspace: {self._workspace_role_label(workspace_type)}. {description}"
        )
        self._advanced_view.set_daily_context_runtime(self._assistant_view._runtime_facts.text())

    @staticmethod
    def _workspace_role_label(workspace_type: str) -> str:
        key = (workspace_type or "user_instance").strip().lower()
        return {
            "user_instance": "Daily assistant workspace",
            "builder_instance": "Builder collaborator workspace",
            "read_only_instance": "Read-only reference workspace",
            "admin_instance": "Operations workspace",
        }.get(key, key.replace("_", " ").strip().capitalize() or "Workspace")

    @staticmethod
    def _workspace_default_purpose(workspace_type: str) -> str:
        key = (workspace_type or "user_instance").strip().lower()
        return {
            "user_instance": "General help, recurring work, and quick tasks.",
            "builder_instance": "Planning, review, and low-risk builder collaboration.",
            "read_only_instance": "Safe research, source review, and reference work without writes.",
            "admin_instance": "Recovery, diagnostics, and guarded changes.",
        }.get(key, "Task-focused context for this workspace.")

    @staticmethod
    def _voice_binding_summary(choice: dict | None) -> str:
        payload = choice if isinstance(choice, dict) else {}
        engine = str(payload.get("engine", "edge")).strip() or "edge"
        source = str(payload.get("source", "default")).strip().lower() or "default"
        source_label = {
            "default": "default voice",
            "persona": "persona voice",
            "model": "model voice",
        }.get(source, "voice setting")
        readiness = "ready"
        if engine.upper() == "ELEVENLABS" and not (os.environ.get("ELEVENLABS_API_KEY", "") or "").strip():
            readiness = "needs API key"
        elif engine.upper() == "EDGE TTS":
            try:
                import importlib.util

                readiness = "ready" if importlib.util.find_spec("edge_tts") is not None else "preview dependency missing"
            except Exception:
                readiness = "ready"
        return f"{engine} from {source_label} ({readiness})"

    @staticmethod
    def _route_evidence_summary(decision: dict | None) -> str:
        payload = decision if isinstance(decision, dict) else {}
        route = str(payload.get("route", "") or "").strip().lower()
        latency = ""
        try:
            status = _read_json(_RUNTIME / "guppy.status")
            latency = str(status.get("last_latency_ms", "") or "").strip()
        except Exception:
            latency = ""
        if route in {"haiku", "sonnet", "opus"}:
            ready = (
                "cloud route configured"
                if bool((os.environ.get("ANTHROPIC_API_KEY", "") or "").strip())
                else "cloud route needs API key"
            )
        elif route == "local":
            ready = (
                "local launcher heartbeat detected"
                if (_RUNTIME / "guppy.heartbeat").exists()
                else "local launcher heartbeat not detected"
            )
        else:
            ready = "launcher route available"
        if latency and latency not in {"—", "-"}:
            return f"{ready}; launcher-wide last reply {latency} ms"
        return ready

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

        # Heartbeats
        data["guppy_online"]  = (_RUNTIME / "guppy.heartbeat").exists()

        # Guppy status
        gs = _read_json(_RUNTIME / "guppy.status")
        data["profile"]      = gs.get("runtime_profile", os.environ.get("GUPPY_RUNTIME_PROFILE", "standard"))
        data["daemon"]       = gs.get("daemon_running", data["guppy_online"])
        data["voice_engine"] = gs.get("tts_engine", os.environ.get("GUPPY_TTS_ENGINE", "edge"))
        data["model"]        = gs.get("active_model",  os.environ.get("GUPPY_LOCAL_MODEL", "guppy"))
        data["wake_word"]    = gs.get("wake_word",     os.environ.get("GUPPY_WAKE_WORD_ENABLED", "false"))
        data["latency"]      = gs.get("last_latency_ms", "—")
        data["last_query"]   = gs.get("last_query", "—")
        if data["last_query"] in {"", "—"} and self._last_command:
            data["last_query"] = self._last_command

        voice_summary = str(data.get("voice_engine", data.get("voice", "edge")) or "edge")
        active_model_id = self._assistant_model_id(
            self._assistant_view.selected_mode(),
            str(data.get("model", "") or ""),
        )
        try:
            if _PERSONALIZATION_BOOTSTRAP_AVAILABLE:
                voice_summary = self._voice_binding_summary(
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
        role = self._workspace_role_label(active_type)
        background_summary = f"{role.upper()} {'READY' if guppy_online else 'NEEDS ATTENTION'}"
        self._assistant_view.set_background_status(
            background_summary,
            healthy=guppy_online,
        )
        self._advanced_view.set_daily_context_recovery(
            f"Recovery: {'stable' if guppy_online else 'needs attention'}",
            ok=guppy_online,
        )
        self._advanced_view.set_status_snapshot(
            {
                "status": data.get("status", "healthy"),
                "startup_readiness": gs.get("startup_readiness", {}),
                "voice_tts_backend": data.get("voice_engine", "edge"),
                "voice_stt_backend": gs.get("stt_backend", "unknown"),
                "voice_binding": voice_summary,
                "route_evidence": self._assistant_view._route_facts.text(),
                "resource_envelope": gs.get("resource_envelope", {}),
            }
        )
        self._refresh_notification_badge()
        self._sync_recovery_outcome()
        # Avoid competing with an active chat turn for the periodic instance refresh.
        # The next idle poll will resync the workspace snapshot.
        if not self._request_in_flight:
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
            and self._api_reachable(timeout=0.2)
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
        events = _read_jsonl_tail(path, limit=80)
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

    def _instances_config_path(self) -> Path:
        return _CONFIG / "instances.json"

    def _instance_state_path(self) -> Path:
        return _RUNTIME / "instance_state.json"

    def _local_instance_snapshot(self) -> dict:
        config = _read_json(self._instances_config_path())
        state = _read_json(self._instance_state_path())
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
            runtime = state_items.get(name, {}) if isinstance(state_items, dict) else {}
            items.append(
                {
                    "name": name,
                    "description": str(item.get("description", "")).strip(),
                    "mode": str(item.get("mode", "auto") or "auto"),
                    "persona": str(item.get("persona", "guppy") or "guppy"),
                    "voice": str(item.get("voice", "default") or "default"),
                    "type": str(item.get("type", "user_instance") or "user_instance"),
                    "created_at": item.get("created_at"),
                    "enabled": bool(item.get("enabled", True)),
                    "status": str(runtime.get("status", "idle") or "idle"),
                    "last_message": str(runtime.get("last_message", "") or ""),
                    "last_updated": runtime.get("last_updated"),
                    "message_count": int(runtime.get("message_count", 0) or 0),
                    "model_currently_using": str(runtime.get("model_currently_using", item.get("mode", "auto")) or "auto"),
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

    def _load_instance_catalog(self) -> tuple[list[str], str]:
        snapshot = self._local_instance_snapshot()
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
        snapshot = self._fetch_instance_snapshot(force=force)
        self._last_instance_snapshot = snapshot
        self._instance_manager_view.set_instances(snapshot)
        items = snapshot.get("instances", []) if isinstance(snapshot, dict) else []
        enabled_names = [
            str(item.get("name", "")).strip()
            for item in items
            if isinstance(item, dict) and bool(item.get("enabled", True)) and str(item.get("name", "")).strip()
        ]
        active = str(snapshot.get("active_instance", "")).strip() or self._active_instance_name or "guppy-primary"
        if active not in enabled_names:
            enabled_names = enabled_names or [active]
            if active not in enabled_names:
                enabled_names.insert(0, active)
        stale_names = [name for name in self._instance_histories.keys() if name not in enabled_names]
        for name in stale_names:
            self._instance_histories.pop(name, None)
        if active != self._active_instance_name and not self._request_in_flight:
            self._apply_instance_switch(active, announce=False)
        self._topbar.set_instances(enabled_names, active_instance=active)
        active_payload = next(
            (
                item
                for item in items
                if isinstance(item, dict) and str(item.get("name", "")).strip() == active
            ),
            {"name": active, "type": "user_instance"},
        )
        if isinstance(active_payload, dict):
            self._tools_view.set_instance_context(active_payload, snapshot)
            self._sync_right_tray(active_payload)
            self._assistant_view.set_active_instance(
                active,
                workspace_type=str(active_payload.get("type", "user_instance") or "user_instance"),
                description=str(active_payload.get("description", "") or ""),
            )
            self._topbar.set_session(self._workspace_role_label(str(active_payload.get("type", "user_instance") or "user_instance")))
        self._advanced_view.set_instance_snapshot(snapshot)
        if load_logs:
            self._on_instance_logs_requested(active, quiet=True)

    def _apply_instance_switch(self, target: str, *, announce: bool = True) -> None:
        if not target:
            return
        if target == self._active_instance_name and not announce:
            self._assistant_view.set_active_instance(target)
            return
        self._snapshot_active_instance_history()
        self._active_instance_name = target
        history = self._instance_histories.get(target)
        if history is None or not history:
            history = self._load_instance_history_from_logs(target)
            self._instance_histories[target] = history
        self._assistant_view.restore_history(history)
        snapshot = self._last_instance_snapshot if isinstance(self._last_instance_snapshot, dict) else {}
        items = snapshot.get("instances", []) if isinstance(snapshot, dict) else []
        active_payload = next(
            (
                item
                for item in items
                if isinstance(item, dict) and str(item.get("name", "")).strip() == target
            ),
            {"name": target, "type": "user_instance"},
        )
        self._assistant_view.set_active_instance(
            target,
            workspace_type=str(active_payload.get("type", "user_instance") or "user_instance"),
            description=str(active_payload.get("description", "") or ""),
        )
        self._assistant_view.ensure_welcome_message()
        if isinstance(active_payload, dict):
            self._sync_right_tray(active_payload)
        self._topbar.set_active_instance(target)
        mode, persona = self._assistant_view.chat_context()
        self._rotate_chat_session("instance_switched", mode=mode, persona=persona, instance=target)
        self._topbar.set_session(self._workspace_role_label(str(active_payload.get("type", "user_instance") or "user_instance")))
        if announce:
            self._assistant_view.add_system_message(f"Switched to workspace {target}.")
            self._set_daily_activity(f"Workspace switched to {target}")
            self._status_panel.append_syslog(f"active workspace switched: {target}")
            self._instance_manager_view.set_status(f"Workspace switched to {target}")
            self._log_launcher_event("instance_switched", instance=target)

    def _bootstrap_instance_switcher(self) -> None:
        snapshot = self._local_instance_snapshot()
        names, active = self._load_instance_catalog()
        self._instance_histories = {}
        self._active_instance_name = active
        self._last_instance_snapshot = snapshot
        self._instance_snapshot_expires_at = time.monotonic() + max(2.0, self._instance_snapshot_ttl_s)
        self._topbar.set_instances(names, active_instance=active)
        self._rotate_chat_session("instance_bootstrap", instance=active)
        self._assistant_view.set_active_instance(active)
        self._assistant_view.ensure_welcome_message()
        self._set_daily_activity(f"Active workspace: {active}")
        self._instance_manager_view.set_instances(snapshot)
        self._advanced_view.set_instance_snapshot(snapshot)
        items = snapshot.get("instances", []) if isinstance(snapshot, dict) else []
        active_payload = next(
            (
                item
                for item in items
                if isinstance(item, dict) and str(item.get("name", "")).strip() == active
            ),
            {"name": active, "type": "user_instance"},
        )
        if isinstance(active_payload, dict):
            self._tools_view.set_instance_context(active_payload, snapshot)
            self._sync_right_tray(active_payload)
        self._set_daily_activity(f"Active workspace: {active}")
        QTimer.singleShot(0, self._refresh_instance_views)
        QTimer.singleShot(250, lambda target=active: self._on_instance_logs_requested(target, quiet=True))

    def _snapshot_active_instance_history(self) -> None:
        if not self._active_instance_name:
            return
        self._instance_histories[self._active_instance_name] = self._assistant_view.recent_history(limit=200)

    def _on_instance_selected(self, name: str) -> None:
        target = (name or "").strip()
        if not target or target == self._active_instance_name:
            return
        if self._request_in_flight:
            self._status_panel.append_syslog("instance switch blocked during active request")
            self._topbar.set_active_instance(self._active_instance_name)
            return
        try:
            self._http_json(
                f"/instances/{target}/activate",
                method="POST",
                payload={},
                timeout=2.0,
                retry_auth_on_401=True,
                auth_retry_reason="instance_activate",
            )
        except Exception:
            cfg = _read_json(self._instances_config_path())
            if isinstance(cfg, dict):
                cfg["active_instance"] = target
                _write_json(self._instances_config_path(), cfg)
            state = _read_json(self._instance_state_path())
            if isinstance(state, dict):
                state["active_instance"] = target
                entries = state.get("instances", {})
                if isinstance(entries, dict):
                    for key, item in entries.items():
                        if not isinstance(item, dict):
                            continue
                        item["status"] = "active" if key == target else "idle"
                _write_json(self._instance_state_path(), state)
        self._apply_instance_switch(target, announce=True)
        self._refresh_instance_views(load_logs=True, force=True)

    def _on_instance_manager_refresh(self) -> None:
        self._refresh_instance_views(load_logs=True, force=True)
        self._instance_manager_view.set_status("Workspace state refreshed")

    def _on_instance_create_requested(self, payload: dict) -> None:
        name = str(payload.get("name", "")).strip()
        if not name:
            self._instance_manager_view.set_status("Workspace name is required", ok=False)
            return
        try:
            result = self._http_json(
                "/instances",
                method="POST",
                payload=payload,
                timeout=3.0,
                retry_auth_on_401=True,
                auth_retry_reason="instance_create",
            )
        except Exception as e:
            message = str(e)
            if "instance limit reached" in message.lower():
                message = "Workspace limit reached (5 / 5). Delete a workspace or update an existing name."
            self._instance_manager_view.set_status(f"Save failed: {message}", ok=False)
            self._status_panel.append_syslog(f"workspace save failed: {message}")
            return
        action = str(result.get("action", "updated")).strip() or "updated"
        self._instance_manager_view.set_status(f"Workspace {name} {action}")
        self._status_panel.append_syslog(f"workspace {name} {action}")
        self._refresh_instance_views(load_logs=True, force=True)

    def _on_instance_delete_requested(self, name: str) -> None:
        target = (name or "").strip()
        if not target:
            return
        try:
            result = self._http_json(
                f"/instances/{target}",
                method="DELETE",
                timeout=3.0,
                retry_auth_on_401=True,
                auth_retry_reason="instance_delete",
            )
        except Exception as e:
            self._instance_manager_view.set_status(f"Delete failed: {e}", ok=False)
            self._status_panel.append_syslog(f"workspace delete failed: {e}")
            return
        new_active = str(result.get("active_instance", self._active_instance_name)).strip() or self._active_instance_name
        if target == self._active_instance_name:
            self._apply_instance_switch(new_active, announce=False)
        self._instance_histories.pop(target, None)
        self._instance_manager_view.set_status(f"Workspace {target} deleted")
        self._status_panel.append_syslog(f"workspace deleted: {target}")
        self._refresh_instance_views(load_logs=True, force=True)

    def _on_instance_logs_requested(self, name: str, quiet: bool = False) -> None:
        target = (name or self._active_instance_name or "guppy-primary").strip()
        if not target:
            return
        entries: list[dict] = []
        try:
            payload = self._http_json(
                f"/instances/{target}/logs?limit=80",
                method="GET",
                timeout=2.0,
                retry_auth_on_401=True,
                auth_retry_reason="instance_logs",
            )
            raw_entries = payload.get("entries", []) if isinstance(payload, dict) else []
            if isinstance(raw_entries, list):
                entries = [item for item in raw_entries if isinstance(item, dict)]
        except Exception:
            if _INSTANCE_LOGGER_AVAILABLE:
                entries = read_instance_log_tail(target, limit=80)
        self._instance_manager_view.set_logs(target, entries)
        if not quiet:
            self._instance_manager_view.set_status(f"Loaded logs for {target}")

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

    def _load_tool_states(self) -> None:
        path = self._tool_state_path()
        if not path.exists():
            return
        try:
            states = _read_json(path)
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
        if _SAFE_IO:
            from utils.safe_io import append_jsonl
            append_jsonl(_RUNTIME / "launcher_events.jsonl", record)
        else:
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

    def _on_builder_task_requested(self, payload: dict[str, object]) -> None:
        try:
            from utils.offhours_builder import enqueue_builder_task, render_builder_task

            template_id = str(payload.get("template_id", "")).strip()
            target_ref = str(payload.get("target_ref", "")).strip()
            instance_name = str(payload.get("instance_name", self._active_instance_name)).strip() or self._active_instance_name
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
            self._set_daily_activity(f"Builder task queued for {instance_name}: {task['template_id']}")
            self._status_panel.append_syslog(f"builder task queued: {task['id']}")
        except Exception as exc:
            self._tools_view.set_builder_status(f"Queue failed: {exc}", ok=False)
            self._status_panel.append_syslog(f"builder task queue failed: {exc}")

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
        env_token = os.environ.get("GUPPY_API_BEARER_TOKEN", "").strip()
        if env_token:
            self._api_token_source = "env_bearer_token"
            return env_token
        if not _API_AUTH_HELPER:
            self._api_token_source = "jwt_helper_unavailable"
            return ""
        try:
            token = _create_access_token({"sub": "launcher_local"})
            self._api_token_source = "jwt_helper"
            return token
        except Exception as e:
            self._api_token_source = f"jwt_helper_error:{type(e).__name__}"
            return ""

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
                if ks_token and _is_valid_repair_token(ks_token):
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
        return token if _is_valid_repair_token(token) else ""

    @staticmethod
    def _validate_repair_token(token: str) -> bool:
        """Backward-compatible alias; delegates to module-level _is_valid_repair_token."""
        return _is_valid_repair_token(token)

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
        Only succeeds when called from localhost (API enforces this).
        """
        try:
            refresh_url = self._api_base_url() + "/repair-token/refresh"
            req = urllib.request.Request(
                refresh_url,
                headers={"Accept": "application/json"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            token = (json.loads(raw) if raw.strip() else {}).get("repair_token", "")
            return token if _is_valid_repair_token(token) else ""
        except Exception:
            return ""

    # ── Recovery helpers (direct — no API dependency) ─────────────────────────
    def _api_reachable(self, timeout: float = 1.5) -> bool:
        state, _detail = self._api_reachability_status(timeout=timeout)
        return state == "reachable"

    def _api_reachability_status(self, timeout: float = 1.5) -> tuple[str, str]:
        try:
            self._http_json(
                "/status",
                method="GET",
                timeout=timeout,
                retry_auth_on_401=True,
                auth_retry_reason="status_poll",
            )
            return "reachable", ""
        except Exception as e:
            detail = str(e)
            if self._is_unauthorized_error(detail):
                return "auth_failed", detail
            return "unreachable", detail

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
        try:
            subprocess.Popen([python, str(script)], cwd=str(root), **flags)
            # Give it a moment to bind
            deadline = time.time() + 6.0
            while time.time() < deadline:
                time.sleep(0.5)
                if self._api_reachable(timeout=0.8):
                    return True, "api started and reachable"
            return False, "api process started but not yet reachable"
        except Exception as e:
            return False, str(e)

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
        self._status_panel.append_syslog(f"active model → {model}")

        self._refresh_personalization_state()
        self._update_route_preview(self._last_command)

    def _on_search(self, query: str) -> None:
        if not query.strip():
            return
        self._on_tab_change(0)
        self._assistant_view.set_input_text(query)

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
        idempotency_key = f"launcher-{uuid.uuid4().hex}"
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
        self._assistant_view.set_status("Processing...")
        activity_setter = getattr(self, "_set_daily_activity", None)
        if callable(activity_setter):
            activity_setter(f"Working on: {cmd[:96]}")
        self._status_panel.append_syslog("command queued")
        self._log_launcher_event("command_submitted", command=cmd, seq=req_seq, idempotency_key=idempotency_key)
        request_timeout = LauncherWindow._chat_timeout_for_request(selected_mode, cmd)
        retry_timeout = max(request_timeout + 20.0, 60.0)

        def _worker() -> None:
            payload = {
                "message": cmd,
                "session_id": self._chat_session_id,
                "mode": selected_mode,
                "persona": selected_persona,
                "history": history,
                "idempotency_key": idempotency_key,
            }
            try:
                try:
                    resp = self._http_json(
                        "/chat",
                        method="POST",
                        payload=payload,
                        timeout=request_timeout,
                        retry_auth_on_401=True,
                        auth_retry_reason="chat",
                    )
                except Exception as first_exc:
                    if "timed out" not in str(first_exc).lower():
                        raise
                    self._log_launcher_event(
                        "command_timeout_retry",
                        seq=req_seq,
                        timeout_s=request_timeout,
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
            self._on_tab_change(3)
            self._advanced_view.focus_operator_logs(
                "WARN",
                note="Top bar notifications opened launcher warnings and recovery events.",
            )
            self._set_daily_activity("App Mgmt opened launcher warnings and recovery events")
            self._status_panel.append_syslog("App Mgmt warnings opened from top bar")
            self._log_launcher_event("quick_action", action="notifications")
            return
        if target == "terminal":
            self._on_tab_change(3)
            note = "Top bar terminal opened operator logs"
            if self._last_command:
                note += f". Last command: {self._last_command}"
            self._advanced_view.focus_operator_logs("ALL", note=note)
            self._advanced_view.focus_terminal(
                note=f"[launcher] terminal opened from top bar. cwd={_RUNTIME.parent}"
            )
            self._set_daily_activity("App Mgmt terminal opened operator logs and workflow controls")
            self._status_panel.append_syslog("App Mgmt terminal opened from top bar")
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
        events = _read_jsonl_tail(path, limit=80)
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
