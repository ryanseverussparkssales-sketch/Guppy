"""
ui/launcher/launcher_window.py
Main QMainWindow shell — assembles Sidebar, TopBar, StatusPanel,
the 6-tab QStackedWidget, and the bottom system strip.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
import urllib.request

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
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_jsonl_tail(path: Path, limit: int = 50) -> list[dict]:
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


class LauncherWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Guppy AI  //  COMMAND_INTERFACE")
        self.setMinimumSize(1120, 720)
        self.setStyleSheet(SHEET)
        self._last_command = ""
        self._last_recovery_signature = ""
        self._scaffold_created: dict[str, object] = {}

        self._build_ui()
        self._start_status_poll()

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
        self._settings_view.recovery_requested.connect(self._on_recovery_requested)
        self._models_view.model_selected.connect(self._on_model_selected)
        self._topbar.search_submitted.connect(self._on_search)
        self._topbar.quick_action.connect(self._on_quick_action)
        self._assistant_view.command_submitted.connect(self._on_assistant_command)

        if _PERSONALIZATION_BOOTSTRAP_AVAILABLE:
            try:
                self._scaffold_created = ensure_personalization_scaffold()
                if self._scaffold_created:
                    created = ",".join(sorted(self._scaffold_created.keys()))
                    self._status_panel.append_syslog(f"personalization scaffold ready: {created}")
                    self._log_launcher_event("personalization_scaffold_created", created=list(self._scaffold_created.keys()))
            except Exception as e:
                self._status_panel.append_syslog(f"personalization scaffold failed: {e}")
                self._log_launcher_event("personalization_scaffold_error", error=str(e))

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

    # ── Status polling ────────────────────────────────────────────────────────
    def _start_status_poll(self) -> None:
        timer = QTimer(self)
        timer.timeout.connect(self._poll_status)
        timer.start(3000)
        self._poll_status()

    def _poll_status(self) -> None:
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

        self._assistant_view.update_agent_status(
            "guppy",   data["guppy_online"],  "—", guppy_load
        )
        self._assistant_view.update_agent_status(
            "merlin",  data["merlin_online"],  "—", merlin_load
        )
        self._assistant_view.update_agent_status(
            "council", council_online, "—", 0
        )
        self._sync_recovery_outcome()

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

    def _log_launcher_event(self, event: str, **fields: object) -> None:
        try:
            path = _RUNTIME / "launcher_events.jsonl"
            record = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "source": "launcher",
                "event": event,
                **fields,
            }
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=True) + "\n")
        except Exception:
            pass

    def _api_base_url(self) -> str:
        port = os.environ.get("GUPPY_API_PORT", "8081").strip() or "8081"
        return f"http://127.0.0.1:{port}"

    def _http_json(self, path: str, method: str = "GET", payload: dict | None = None, timeout: float = 8.0) -> dict:
        url = self._api_base_url() + path
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw.strip() else {}

    def _on_recovery_requested(self, action: str) -> None:
        act = (action or "").strip().lower()
        self._settings_view.set_recovery_status(f"Recovery: {act}...")
        self._status_panel.append_syslog(f"recovery requested: {act}")
        self._log_launcher_event("recovery_requested", action=act)

        try:
            if act == "health_snapshot":
                status = self._http_json("/status", method="GET")
                startup = self._http_json("/startup/check?deep=true", method="GET")
                status_state = str(status.get("status", "unknown")).upper()
                startup_state = str(startup.get("overall", "unknown")).upper()
                msg = f"Snapshot OK: STATUS={status_state} STARTUP={startup_state}"
                self._settings_view.set_recovery_status(msg)
                self._status_panel.append_syslog(msg)
                self._status_panel.set_recovery_outcome("health_snapshot", True, f"status={status_state} startup={startup_state}")
                self._log_launcher_event(
                    "recovery_snapshot",
                    status=status_state,
                    startup=startup_state,
                )
                return

            repair_map = {
                "warmup": "warmup",
                "restart_daemon": "restart_daemon",
                "audit_runtime": "audit_runtime",
            }
            if act not in repair_map:
                raise ValueError(f"unsupported recovery action: {act}")

            result = self._http_json(
                "/repair",
                method="POST",
                payload={"action": repair_map[act], "dry_run": False},
                timeout=12.0,
            )
            ok = bool(result.get("ok", False))
            summary = str(result.get("summary", "done"))
            state = "OK" if ok else "ERROR"
            msg = f"Recovery {act}: {state} — {summary}"
            self._settings_view.set_recovery_status(msg)
            self._status_panel.append_syslog(msg)
            self._status_panel.set_recovery_outcome(act, ok, summary)
            self._log_launcher_event("recovery_result", action=act, ok=ok, summary=summary)
        except Exception as e:
            msg = f"Recovery {act} failed: {e}"
            self._settings_view.set_recovery_status(msg)
            self._status_panel.append_syslog(msg)
            self._status_panel.set_recovery_outcome(act or "recovery", False, str(e))
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
        self._status_panel.append_syslog(f"command queued: {cmd[:80]}")
        self._log_launcher_event("command_submitted", command=cmd)

    def _on_quick_action(self, action: str) -> None:
        self._status_panel.append_syslog(f"quick action unavailable: {action}")
