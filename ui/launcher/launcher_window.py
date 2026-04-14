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
    from utils.personalization_config import ensure_personalization_scaffold
    _PERSONALIZATION_BOOTSTRAP_AVAILABLE = True
except Exception:
    _PERSONALIZATION_BOOTSTRAP_AVAILABLE = False

try:
    from utils.instance_logger import append_instance_log, read_instance_log_tail
    _INSTANCE_LOGGER_AVAILABLE = True
except Exception:
    _INSTANCE_LOGGER_AVAILABLE = False

    def append_instance_log(*_args, **_kwargs):
        return None

    def read_instance_log_tail(*_args, **_kwargs):
        return []

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
        self._scaffold_created: dict[str, Path] = {}
        self._deferred_syslog: SimpleQueue[str] = SimpleQueue()
        self._status_poll_timer: QTimer | None = None
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

        for view in [
            self._assistant_view,
            self._instance_manager_view,
            self._tools_view,
            self._advanced_view,
            self._settings_view,
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
        self._advanced_view.recovery_requested.connect(self._on_recovery_requested)
        self._models_view.model_selected.connect(self._on_model_selected)
        self._topbar.search_submitted.connect(self._on_search)
        self._topbar.quick_action.connect(self._on_quick_action)
        self._assistant_view.command_submitted.connect(self._on_assistant_command)
        self._assistant_view.cancel_requested.connect(self._on_cancel_assistant_request)
        self.assistant_event_queued.connect(self._drain_assistant_events)
        self._assistant_view.chat_context_changed.connect(self._on_chat_context_changed)
        self._instance_manager_view.refresh_requested.connect(self._on_instance_manager_refresh)
        self._instance_manager_view.activate_requested.connect(self._on_instance_selected)
        self._instance_manager_view.create_requested.connect(self._on_instance_create_requested)
        self._instance_manager_view.delete_requested.connect(self._on_instance_delete_requested)
        self._instance_manager_view.logs_requested.connect(self._on_instance_logs_requested)
        self._topbar.instance_selected.connect(self._on_instance_selected)
        self._status_panel.agent_init_requested.connect(self._on_agent_init_requested)
        self._assistant_view.set_session_id(self._chat_session_id)
        self._bootstrap_instance_switcher()

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
        self._poll_status()

    def _poll_status(self) -> None:
        poll_t0 = time.monotonic()
        self._drain_deferred_syslog()
        self._drain_assistant_events()
        self._drain_recovery_events()
        self._update_sys_strip()
        data: dict = {}

        # Heartbeats
        data["guppy_online"]  = (_RUNTIME / "guppy.heartbeat").exists()
        data["merlin_online"] = (_RUNTIME / "merlin.heartbeat").exists()

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

        self._status_panel.update_status(data)
        self._assistant_view.set_runtime_facts(
            profile=str(data.get("profile", "standard") or "standard"),
            model=str(data.get("model", "guppy") or "guppy"),
            voice=str(data.get("voice_engine", data.get("voice", "edge")) or "edge"),
            latency=str(data.get("latency", "—") or "—"),
            last_query=str(data.get("last_query", "—") or "—"),
        )

        # Update agent cards
        guppy_load  = gs.get("cpu_load_pct", 0)
        merlin_last = gs.get("last_seen", "—")

        ms = _read_json(_RUNTIME / "merlin.status")
        merlin_load = ms.get("cpu_load_pct", 0)

        cs = _read_json(_RUNTIME / "council.status")
        council_online = bool(cs.get("active", False))

        guppy_online = data["guppy_online"] or ("guppy" in self._embedded_online)
        merlin_online = data["merlin_online"] or ("merlin" in self._embedded_online)
        council_is_online = council_online or ("council" in self._embedded_online)

        self._status_panel.update_agent_status("guppy", guppy_online, "—", guppy_load)
        self._status_panel.update_agent_status("merlin", merlin_online, "—", merlin_load)
        self._status_panel.update_agent_status("council", council_is_online, "—", 0)
        background_summary = (
            f"{self._active_instance_name} · {str(data.get('profile', 'standard')).upper()} · "
            f"GUPPY {'LIVE' if guppy_online else 'OFFLINE'} · "
            f"MERLIN {'LIVE' if merlin_online else 'OFFLINE'}"
        )
        self._assistant_view.set_background_status(
            background_summary,
            healthy=guppy_online or merlin_online or council_is_online,
        )
        self._advanced_view.set_status_snapshot(
            {
                "status": data.get("status", "healthy"),
                "startup_readiness": gs.get("startup_readiness", {}),
                "voice_tts_backend": data.get("voice_engine", "edge"),
                "voice_stt_backend": gs.get("stt_backend", "unknown"),
                "resource_envelope": gs.get("resource_envelope", {}),
            }
        )
        self._sync_recovery_outcome()
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
            and self._api_reachable(timeout=1.0)
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

    def _fetch_instance_snapshot(self) -> dict:
        try:
            return self._http_json(
                "/instances",
                method="GET",
                timeout=1.2,
                retry_auth_on_401=True,
                auth_retry_reason="instances_list",
            )
        except Exception:
            return self._local_instance_snapshot()

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
        snapshot = self._fetch_instance_snapshot()
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

    def _refresh_instance_views(self, *, load_logs: bool = False) -> None:
        snapshot = self._fetch_instance_snapshot()
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
        for name in enabled_names:
            if name not in self._instance_histories:
                self._instance_histories[name] = self._load_instance_history_from_logs(name)
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
        self._assistant_view.set_active_instance(target)
        self._topbar.set_active_instance(target)
        mode, persona = self._assistant_view.chat_context()
        self._rotate_chat_session("instance_switched", mode=mode, persona=persona, instance=target)
        if announce:
            self._assistant_view.add_system_message(f"Switched active instance to {target}.")
            self._assistant_view.set_background_event(f"Active instance switched to {target}")
            self._status_panel.append_syslog(f"active instance switched: {target}")
            self._instance_manager_view.set_status(f"Active instance switched to {target}")
            self._log_launcher_event("instance_switched", instance=target)

    def _bootstrap_instance_switcher(self) -> None:
        names, active = self._load_instance_catalog()
        self._instance_histories = {name: self._load_instance_history_from_logs(name) for name in names}
        self._active_instance_name = active
        self._topbar.set_instances(names, active_instance=active)
        self._rotate_chat_session("instance_bootstrap", instance=active)
        self._assistant_view.set_active_instance(active)
        self._assistant_view.add_system_message(f"Active instance: {active}")
        self._refresh_instance_views(load_logs=True)

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
        self._refresh_instance_views(load_logs=True)

    def _on_instance_manager_refresh(self) -> None:
        self._refresh_instance_views(load_logs=True)
        self._instance_manager_view.set_status("Instance state refreshed")

    def _on_instance_create_requested(self, payload: dict) -> None:
        name = str(payload.get("name", "")).strip()
        if not name:
            self._instance_manager_view.set_status("Instance name is required", ok=False)
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
                message = "Configured-instance cap reached (5 / 5). Delete an instance or update an existing name."
            self._instance_manager_view.set_status(f"Save failed: {message}", ok=False)
            self._status_panel.append_syslog(f"instance save failed: {message}")
            return
        action = str(result.get("action", "updated")).strip() or "updated"
        self._instance_manager_view.set_status(f"Instance {name} {action}")
        self._status_panel.append_syslog(f"instance {name} {action}")
        self._refresh_instance_views(load_logs=True)

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
            self._status_panel.append_syslog(f"instance delete failed: {e}")
            return
        new_active = str(result.get("active_instance", self._active_instance_name)).strip() or self._active_instance_name
        if target == self._active_instance_name:
            self._apply_instance_switch(new_active, announce=False)
        self._instance_histories.pop(target, None)
        self._instance_manager_view.set_status(f"Instance {target} deleted")
        self._status_panel.append_syslog(f"instance deleted: {target}")
        self._refresh_instance_views(load_logs=True)

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
        self._assistant_view.apply_settings(settings)
        self._assistant_view.set_background_event(f"Settings saved for {str(profile).upper()} profile")
        self._status_panel.append_syslog(f"settings saved  profile={profile}")

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
    def _chat_timeout_for_mode(mode: str) -> float:
        m = (mode or "auto").strip().lower()
        if m in {"claude", "auto", "teaching"}:
            return 25.0
        if m in {"local", "ollama", "code", "vault"}:
            return 35.0
        return 30.0

    @staticmethod
    def _required_local_model_for_mode(mode: str) -> str | None:
        m = (mode or "").strip().lower()
        if m in {"local", "ollama"}:
            return (os.environ.get("OLLAMA_MODEL", "guppy") or "guppy").strip()
        if m == "code":
            return (os.environ.get("GUPPY_LOCAL_CODE_MODEL", "merlin-code") or "merlin-code").strip()
        if m == "vault":
            return (os.environ.get("GUPPY_LOCAL_VAULT_MODEL", "vault-scraper") or "vault-scraper").strip()
        return None

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
                self._assistant_view.set_background_event(text)
                self._assistant_view.set_recovery_summary(text, healthy="error" not in text.lower())
            elif kind == "syslog":
                text = str(evt.get("text", ""))
                self._status_panel.append_syslog(text)
                self._advanced_view.append_log(text)
                self._assistant_view.set_background_event(text)
            elif kind == "outcome":
                action = str(evt.get("action", "recovery"))
                ok = bool(evt.get("ok", False))
                summary = str(evt.get("summary", ""))
                self._status_panel.set_recovery_outcome(action, ok, summary)
                self._advanced_view.set_recovery_status(f"{action}: {summary}")
                self._advanced_view.append_log(f"Recovery {action}: {summary}")
                self._assistant_view.set_background_event(f"Recovery {action}: {summary}")
                self._assistant_view.set_recovery_summary(f"{action}: {summary}", healthy=ok)
            processed += 1

    def _on_tool_hint_requested(self, tool_key: str) -> None:
        key = (tool_key or "").strip()
        if not key:
            return
        self._on_tab_change(0)
        self._assistant_view.set_input_text(f"Use {key} for the active instance: ")
        self._assistant_view.set_background_event(f"Agent tool primed from Agent Tools: {key}")
        self._status_panel.append_syslog(f"agent tool primed: {key}")

    def _initialize_embedded_agent(self, agent_id: str) -> tuple[bool, str]:
        aid = (agent_id or "").strip().lower()
        if aid not in {"guppy", "merlin", "council"}:
            return False, f"unknown agent: {agent_id}"
        self._embedded_online.add(aid)
        self._assistant_view.activate_agent(aid)
        self._assistant_view.add_system_message(f"{aid.upper()} embedded session initialized.")
        self._assistant_view.set_background_event(f"Embedded {aid.upper()} session initialized")
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
                        except Exception:
                            pass
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
        for name in ("guppy.status", "merlin.status", "council.status",
                     "guppy.heartbeat", "merlin.heartbeat"):
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
        for name in ("guppy.status", "merlin.status", "council.status",
                     "resource_envelope.status.json", "logging_health_snapshot.json"):
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
        for agent in ("guppy", "merlin", "council"):
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

    def _on_search(self, query: str) -> None:
        if not query.strip():
            return
        self._stack.setCurrentIndex(0)
        self._sidebar.set_active(0)
        self._assistant_view.set_input_text(query)

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
        # Increment before starting the worker so any in-flight response from
        # a prior command carries a stale sequence number and is dropped.
        self._active_request_seq += 1
        req_seq = self._active_request_seq
        self._request_in_flight = True
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
        self._status_panel.append_syslog("command queued")
        self._log_launcher_event("command_submitted", command=cmd, seq=req_seq)
        request_timeout = LauncherWindow._chat_timeout_for_mode(selected_mode)
        history_getter = getattr(self._assistant_view, "recent_history", None)
        history = history_getter(limit=12) if callable(history_getter) else []

        def _worker() -> None:
            try:
                resp = self._http_json(
                    "/chat",
                    method="POST",
                    payload={
                        "message": cmd,
                        "session_id": self._chat_session_id,
                        "mode": selected_mode,
                        "history": history,
                    },
                    timeout=request_timeout,
                    retry_auth_on_401=True,
                    auth_retry_reason="chat",
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
                self._log_launcher_event("command_response", ok=True, chars=len(text), seq=req_seq)
            except Exception as e:
                err_text = str(e)
                if self._is_unauthorized_error(err_text):
                    auth_code = self._extract_error_code(err_text)
                    self._log_launcher_event(
                        "command_auth_error",
                        seq=req_seq,
                        auth_code=auth_code,
                        error=err_text,
                    )
                    self._refresh_api_auth_state("chat_401")
                    try:
                        retry_resp = self._http_json(
                            "/chat",
                            method="POST",
                            payload={
                                "message": cmd,
                                "session_id": self._chat_session_id,
                                "mode": selected_mode,
                                "history": history,
                            },
                            timeout=request_timeout,
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
                            )
                        err_text = f"{err_text}; retry failed: {retry_error}"

                self._assistant_events.put(("error", err_text, req_seq))
                emitter = getattr(self, "assistant_event_queued", None)
                if emitter is not None and hasattr(emitter, "emit"):
                    emitter.emit()
                self._log_launcher_event("command_response", ok=False, error=err_text, seq=req_seq)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_quick_action(self, action: str) -> None:
        self._status_panel.append_syslog(f"quick action unavailable: {action}")
