"""
ui/launcher/launcher_window.py
Main QMainWindow shell — assembles Sidebar, TopBar, StatusPanel,
the 6-tab QStackedWidget, and the bottom system strip.
"""
from __future__ import annotations

import json
import os
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
    from guppy_api_auth import create_access_token as _create_access_token
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

from PySide6.QtCore import QTimer, Qt
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

_RUNTIME = Path(__file__).resolve().parent.parent.parent / "runtime"
_START_TIME = time.monotonic()


def _read_json(path: Path) -> dict:
    if _SAFE_IO:
        return read_json_dict(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


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
        self._active_request_seq: int = 0  # monotonic; only the latest response is shown
        self._api_bearer_token = ""
        self._api_token_source = "none"
        self._auth_self_check_ok = False
        self._auth_self_check_inflight = False
        self._auth_self_check_last_attempt = 0.0
        self._embedded_online: set[str] = set()
        self._assistant_events: SimpleQueue[tuple[str, str, int]] = SimpleQueue()
        self._recovery_events: SimpleQueue[dict[str, object]] = SimpleQueue()
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
        self._tools_view      = ToolsView(self)
        self._settings_view   = SettingsView(self)
        self._advanced_view   = AdvancedView(self)
        self._models_view     = ModelsView(self)
        self._voices_view     = VoicesView(self)

        for view in [
            self._assistant_view,
            self._tools_view,
            self._settings_view,
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
        self._settings_view.recovery_requested.connect(self._on_recovery_requested)
        self._models_view.model_selected.connect(self._on_model_selected)
        self._topbar.search_submitted.connect(self._on_search)
        self._topbar.quick_action.connect(self._on_quick_action)
        self._assistant_view.command_submitted.connect(self._on_assistant_command)
        self._status_panel.agent_init_requested.connect(self._on_agent_init_requested)

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
        self._sync_recovery_outcome()
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

    # ── Tab coordination ──────────────────────────────────────────────────────
    def _on_tab_change(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        self._topbar.set_active_tab(index)
        self._sidebar.set_active(index)

    # ── Event handlers ────────────────────────────────────────────────────────
    def _on_settings_saved(self, settings: dict) -> None:
        profile = settings.get("runtime_profile", "standard")
        self._assistant_view.apply_settings(settings)
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
            # Discard stale responses from superseded requests.
            if seq != self._active_request_seq:
                processed += 1
                continue
            if kind == "assistant":
                self._assistant_view.set_status("Ready")
                self._assistant_view.add_assistant_message(payload)
            elif kind == "error":
                self._assistant_view.set_status("Error")
                self._assistant_view.add_system_message(f"ERROR: {payload}")
                self._status_panel.append_syslog("chat error: see transcript/system message")
            processed += 1

    def _drain_recovery_events(self) -> None:
        processed = 0
        while processed < self._MAX_RECOVERY_EVENTS_PER_TICK:
            try:
                evt = self._recovery_events.get_nowait()
            except Empty:
                break
            kind = str(evt.get("kind", ""))
            if kind == "status":
                self._settings_view.set_recovery_status(str(evt.get("text", "")))
            elif kind == "syslog":
                self._status_panel.append_syslog(str(evt.get("text", "")))
            elif kind == "outcome":
                action = str(evt.get("action", "recovery"))
                ok = bool(evt.get("ok", False))
                summary = str(evt.get("summary", ""))
                self._status_panel.set_recovery_outcome(action, ok, summary)
            processed += 1

    def _initialize_embedded_agent(self, agent_id: str) -> tuple[bool, str]:
        aid = (agent_id or "").strip().lower()
        if aid not in {"guppy", "merlin", "council"}:
            return False, f"unknown agent: {agent_id}"
        self._embedded_online.add(aid)
        self._assistant_view.activate_agent(aid)
        self._assistant_view.add_system_message(f"{aid.upper()} embedded session initialized.")
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

    def _http_json(self, path: str, method: str = "GET", payload: dict | None = None, timeout: float = 8.0) -> dict:
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
            # On repair-token mismatch (API restart rotated token) — re-sync and retry once.
            if e.code == 403 and path == "/repair":
                try:
                    body = e.read().decode("utf-8", errors="replace")
                    parsed = json.loads(body) if body.strip() else {}
                    d = parsed.get("detail", "")
                    err_code = d.get("code", "") if isinstance(d, dict) else ""
                except Exception:
                    err_code = ""
                if err_code == "repair_token_mismatch":
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
                    code = d.get("code", "")
                    msg = d.get("message", "")
                    detail = f"{code}:{msg}".strip(":")
                elif isinstance(d, str):
                    detail = d
            except Exception:
                detail = ""
            if detail:
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
        try:
            self._http_json("/status", method="GET", timeout=timeout)
            return True
        except Exception:
            return False

    def _run_auth_self_check(self) -> None:
        try:
            payload = self._http_json("/auth/self-check", method="GET", timeout=2.5)
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
            self._auth_self_check_ok = False
            self._log_launcher_event(
                "auth_self_check",
                ok=False,
                token_source=self._api_token_source,
                error=str(e),
            )
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
        return {"ok": ok, "summary": "; ".join(parts) or "nothing to report"}

    def _direct_audit_runtime(self) -> dict:
        """Audit: collect runtime status files into a diagnostics JSON."""
        bundle: dict = {"ts": datetime.now(timezone.utc).isoformat(), "files": {}}
        for name in ("guppy.status", "merlin.status", "council.status",
                     "resource_envelope.status.json", "logging_health_snapshot.json"):
            p = _RUNTIME / name
            if not p.exists():
                bundle["files"][name] = {"missing": True}
                continue
            try:
                bundle["files"][name] = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                bundle["files"][name] = {"error": "unreadable"}
        out = _RUNTIME / f"diagnostics_bundle_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        try:
            out.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
            return {"ok": True, "summary": f"bundle written: {out.name}"}
        except Exception as e:
            return {"ok": False, "summary": str(e)}

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
        return {"ok": ok, "summary": summary}

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
            if self._api_reachable():
                if act == "health_snapshot":
                    status  = self._http_json("/status", method="GET")
                    startup = self._http_json("/startup/check?deep=true", method="GET")
                    status_state  = str(status.get("status", "unknown")).upper()
                    startup_state = str(startup.get("overall", "unknown")).upper()
                    summary = f"status={status_state} startup={startup_state}"
                    self._recovery_events.put({
                        "kind": "outcome",
                        "action": "health_snapshot",
                        "ok": True,
                        "summary": summary,
                    })
                    self._log_launcher_event("recovery_snapshot", status=status_state, startup=startup_state)
                    msg = f"Snapshot OK: {summary}"
                elif act in {"warmup", "restart_daemon", "audit_runtime"}:
                    result  = self._http_json("/repair", method="POST",
                                             payload={"action": act, "dry_run": False},
                                             timeout=12.0)
                    ok      = bool(result.get("ok", False))
                    summary = str(result.get("summary", "done"))
                    if act == "restart_daemon":
                        self._refresh_api_auth_state("restart_daemon_api")
                    self._recovery_events.put({
                        "kind": "outcome",
                        "action": act,
                        "ok": ok,
                        "summary": summary,
                    })
                    self._log_launcher_event("recovery_result", action=act, ok=ok, summary=summary)
                    msg = f"Recovery {act}: {'OK' if ok else 'ERROR'} — {summary}"
                else:
                    raise ValueError(f"unsupported action: {act}")

                self._recovery_events.put({"kind": "status", "text": msg})
                self._recovery_events.put({"kind": "syslog", "text": msg})
                return

            # ── API not reachable — run directly ───────────────────────────────
            self._recovery_events.put({"kind": "syslog", "text": "api down — running direct recovery"})

            if act == "health_snapshot":
                result = self._direct_health_snapshot()
            elif act == "warmup":
                result = self._direct_warmup()
            elif act == "restart_daemon":
                # restart_daemon means "bring the API (and daemon) up"
                self._recovery_events.put({"kind": "syslog", "text": "starting api server..."})
                started, detail = self._start_api_subprocess()
                result = {"ok": started, "summary": detail}
                self._refresh_api_auth_state("restart_daemon_direct")
            elif act == "audit_runtime":
                result = self._direct_audit_runtime()
            else:
                raise ValueError(f"unsupported action: {act}")

            ok      = bool(result.get("ok", False))
            summary = str(result.get("summary", "done"))
            msg     = f"Direct {act}: {'OK' if ok else 'ERROR'} — {summary}"
            self._recovery_events.put({"kind": "status", "text": msg})
            self._recovery_events.put({"kind": "syslog", "text": msg})
            self._recovery_events.put({
                "kind": "outcome",
                "action": act,
                "ok": ok,
                "summary": summary,
            })
            self._log_launcher_event("recovery_result", action=act, ok=ok, summary=summary)

        except Exception as e:
            msg = f"Recovery {act} error: {e}"
            self._recovery_events.put({"kind": "status", "text": msg})
            self._recovery_events.put({"kind": "syslog", "text": msg})
            self._recovery_events.put({
                "kind": "outcome",
                "action": act or "recovery",
                "ok": False,
                "summary": str(e),
            })
            self._log_launcher_event("recovery_error", action=act, error=str(e))

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
        self._last_command = cmd
        # Increment before starting the worker so any in-flight response from
        # a prior command carries a stale sequence number and is dropped.
        self._active_request_seq += 1
        req_seq = self._active_request_seq
        self._assistant_view.add_user_message(cmd)
        self._assistant_view.set_status("Processing...")
        self._status_panel.append_syslog("command queued")
        self._log_launcher_event("command_submitted", command=cmd, seq=req_seq)

        def _worker() -> None:
            try:
                resp = self._http_json(
                    "/chat",
                    method="POST",
                    payload={
                        "message": cmd,
                        "session_id": self._chat_session_id,
                        "mode": self._assistant_view.selected_mode(),
                    },
                    timeout=60.0,
                )
                text = str(resp.get("response") or "").strip()
                if not text:
                    text = "No response payload received."
                self._assistant_events.put(("assistant", text, req_seq))
                self._log_launcher_event("command_response", ok=True, chars=len(text), seq=req_seq)
            except Exception as e:
                err_text = str(e)
                if self._is_unauthorized_error(err_text):
                    self._refresh_api_auth_state("chat_401")
                    try:
                        retry_resp = self._http_json(
                            "/chat",
                            method="POST",
                            payload={
                                "message": cmd,
                                "session_id": self._chat_session_id,
                                "mode": self._assistant_view.selected_mode(),
                            },
                            timeout=60.0,
                        )
                        retry_text = str(retry_resp.get("response") or "").strip()
                        if not retry_text:
                            retry_text = "No response payload received."
                        self._assistant_events.put(("assistant", retry_text, req_seq))
                        self._log_launcher_event(
                            "command_response",
                            ok=True,
                            chars=len(retry_text),
                            seq=req_seq,
                            retried_after_401=True,
                        )
                        return
                    except Exception as retry_error:
                        err_text = f"{err_text}; retry failed: {retry_error}"

                self._assistant_events.put(("error", err_text, req_seq))
                self._log_launcher_event("command_response", ok=False, error=err_text, seq=req_seq)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_quick_action(self, action: str) -> None:
        self._status_panel.append_syslog(f"quick action unavailable: {action}")
