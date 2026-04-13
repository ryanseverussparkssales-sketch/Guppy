"""
council_ui.py — The Council: Guppy & Merlin in a shared terminal
================================================================
A single window where Ryan can address Guppy, Merlin, or both
simultaneously. Each agent runs in its own panel with its own history,
colour scheme, and voice.

Route toggle (bottom bar):
  🎩 GUPPY  — message goes to Guppy only
  ⚡ BOTH   — message goes to both agents simultaneously
  ✦ MERLIN  — message goes to Merlin only
"""

import sys, os, json, math, threading, time
import urllib.request
from datetime import datetime as _dt
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QScrollArea, QLabel, QPushButton, QLineEdit, QFrame, QSizePolicy,
    QGraphicsOpacityEffect,
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QRectF, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import (
    QPainter, QColor, QPen, QFont, QRadialGradient, QBrush, QPalette,
    QKeySequence, QShortcut,
)

from guppy_core import TOOLS, is_online, check_ollama, get_startup_system, run_tool, to_ollama_tools
from merlin_core import MERLIN_TOOLS, run_spell, get_merlin_startup_system
from inference_router import resolve_ui_route
from guppy_theme import GUPPY_THEME as _GT, MERLIN_THEME as _MT, SHARED, now_str
from debug_console import open_debug_console
from utils.env_bootstrap import load_env_file
from utils.runtime_profile import apply_runtime_profile, load_app_settings
from utils.settings_dialog import open_settings as _open_settings_dlg
from utils.telemetry_window import rolling_agent_snapshot, recent_agent_events
from utils.diagnostics_bundle import create_diagnostics_bundle
from ui.components.status_strip import StatusStrip
from ui.components.timeline_panel import TimelinePanel
from ui.components.startup_checklist import StartupChecklist
from ui.components.sparkline import Sparkline
from ui.components.command_palette import CommandPaletteDialog

try:
    from utils.agent_perf import log_agent_performance as _log_perf
except ImportError:
    def _log_perf(*_args, **_kwargs):
        return

load_env_file()
APP_SETTINGS = apply_runtime_profile()

SHOW_BACKEND_DETAILS = os.environ.get("GUPPY_SHOW_BACKEND_DETAILS", "0").strip().lower() in {"1", "true", "yes", "on"}
_COUNCIL_TOOL_BUDGET = int(os.environ.get("COUNCIL_TOOL_BUDGET", "6"))
_COUNCIL_MERLIN_TIMEOUT = int(os.environ.get("COUNCIL_MERLIN_TIMEOUT", "75"))
_COUNCIL_MERLIN_NUM_PREDICT = int(os.environ.get("COUNCIL_MERLIN_NUM_PREDICT", "320"))

FF_MONO = SHARED.font_family_mono
FS_BODY = SHARED.font_size
FS_SMALL = SHARED.font_size_small
FS_LABEL = SHARED.sidebar_label_font_size
FS_TS = SHARED.timestamp_font_size
CH_SM = SHARED.control_height_sm
CH_MD = SHARED.control_height_md
CH_LG = SHARED.control_height_lg

try:
    from guppy_memory import save_message as _save_msg
    _SAVE = True
except ImportError:
    _SAVE = False

try:
    from utils.heartbeat import start_heartbeat as _start_hb, stop_heartbeat as _stop_hb
    _HB_OK = True
except ImportError:
    _HB_OK = False


# ── Palette (sourced from guppy_theme — edit theme.json to customize) ──────────

BG      = "#06060e"
BAR     = "#0a0a14"
DIVIDER = "#1a1a2e"
TEXT    = _GT.text
DIM_TXT = _GT.dim

# Guppy (left)
G_ACC  = _GT.accent
G_DIM  = _GT.dim
G_BG   = _GT.bg
G_MSG  = _GT.bg2

# Merlin (right)
M_ACC  = _MT.accent
M_DIM  = _MT.dim
M_BG   = _MT.bg
M_MSG  = _MT.bg2


# ── Workers ────────────────────────────────────────────────────────────────────

class GuppyWorker(QThread):
    bubble = Signal(str, str, str)
    status = Signal(str)
    done   = Signal()

    def __init__(self, text, history, mode, api_key, system, session_id, save=True):
        super().__init__()
        self.text = text
        self.history = history
        self.mode = mode
        self.api_key = api_key
        self.system = system
        self.session_id = session_id
        self.save = save

    def run(self):
        started = time.perf_counter()
        request_id = f"{self.session_id}:{int(started * 1000)}:{id(self)}"
        req_status = "ok"
        route = "unknown"
        route_reason = ""
        task_type = "unknown"
        _log_perf(
            "council",
            "request_started",
            panel="guppy",
            session_id=self.session_id,
            request_id=request_id,
            mode=self.mode,
            input_chars=len(self.text or ""),
        )
        self.status.emit("thinking")
        try:
            self.bubble.emit("Thinking through context and next action", "thinking", "thinking_stream")
            decision = resolve_ui_route(
                user_text=self.text,
                mode=self.mode,
                voice_triggered=False,
                api_key_available=bool(self.api_key),
            )
            route = decision.get("route", "unknown")
            route_reason = decision.get("route_reason", "")
            task_type = decision.get("task_type", "unknown")

            executor = decision.get("executor")
            if executor == "error":
                raise RuntimeError(decision.get("error", "Unable to resolve route"))

            if decision.get("system_profile") == "merlin":
                system_override = get_merlin_startup_system(query_context=self.text)
            else:
                system_override = self.system

            if executor == "claude":
                self._claude(
                    forced_model=decision.get("model"),
                    forced_backup=decision.get("backup_model"),
                    system_override=system_override,
                )
            else:
                self._ollama(
                    system_override=system_override,
                    model_override=decision.get("model", "guppy"),
                )
        except Exception as e:
            req_status = "error"
            self.bubble.emit(f"Error: {e}", "error", "error")
        finally:
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            _log_perf(
                "council",
                "request_complete",
                panel="guppy",
                session_id=self.session_id,
                request_id=request_id,
                mode=self.mode,
                input_chars=len(self.text or ""),
                status=req_status,
                latency_ms=latency_ms,
                task_type=task_type,
                route=route,
                route_reason=route_reason,
            )
            self.status.emit("idle")
            self.done.emit()

    def _claude(self, forced_model=None, forced_backup=None, system_override=None):
        import anthropic
        client = anthropic.Anthropic(api_key=self.api_key)
        active_model = (forced_model or "claude-sonnet-4-6").strip()
        backup_model = (forced_backup or "").strip()
        current_system = system_override or self.system
        if _SAVE and self.save:
            _save_msg(self.session_id, "user", self.text)
        msgs = self.history + [{"role": "user", "content": self.text}]
        while True:
            self.bubble.emit("Thinking and planning response", "thinking", "thinking_stream")
            model_chain = [active_model]
            if backup_model and backup_model != active_model:
                model_chain.append(backup_model)

            resp = None
            last_err = None
            for model_name in model_chain:
                try:
                    resp = client.messages.create(
                        model=model_name,
                        max_tokens=4096,
                        system=current_system,
                        tools=TOOLS,
                        messages=msgs,
                    )
                    if model_name != active_model:
                        self.bubble.emit(
                            f"Primary Claude model unavailable; switched to backup ({model_name}).",
                            "tool_result",
                            "tool_result",
                        )
                        active_model = model_name
                    break
                except Exception as e:
                    last_err = e
            if resp is None:
                raise RuntimeError(f"Claude request failed on all configured models: {last_err}")
            msgs.append({"role": "assistant", "content": resp.content})
            for b in resp.content:
                if b.type == "text" and b.text.strip():
                    self.bubble.emit(b.text, "guppy", "guppy")
                    if _SAVE and self.save:
                        _save_msg(self.session_id, "assistant", b.text)
            tus = [b for b in resp.content if b.type == "tool_use"]
            if not tus or resp.stop_reason == "end_turn":
                break
            results = []
            for tu in tus:
                self.status.emit("thinking")
                preview = ", ".join(f"{k}={repr(v)[:30]}" for k, v in tu.input.items())
                if SHOW_BACKEND_DETAILS:
                    self.bubble.emit(f"⚙️  {tu.name}({preview})", "tool", "tool")
                else:
                    self.bubble.emit(f"Thinking step using {tu.name}", "thinking", "thinking_stream")
                result = run_tool(tu.name, tu.input)
                result_str = (
                    f"Screenshot saved: {result['path']} ({result['size']})"
                    if isinstance(result, dict) and result.get("_screenshot")
                    else str(result)
                )
                if SHOW_BACKEND_DETAILS:
                    self.bubble.emit(f"   ↳ {result_str[:300]}", "tool_result", "tool_result")
                elif result_str.lower().startswith("error"):
                    self.bubble.emit("Thinking step failed and recovered", "thinking", "thinking_stream")
                results.append({"type": "tool_result", "tool_use_id": tu.id, "content": result_str})
            msgs.append({"role": "user", "content": results})
        self.history.clear()
        self.history.extend(msgs)
        if len(self.history) > 40:
            self.history[:] = self.history[-40:]

    def _ollama(self, system_override=None, model_override="guppy"):
        active_model = model_override or "guppy"
        ok, err = check_ollama(active_model)
        if not ok:
            self.bubble.emit(err, "error", "error")
            return
        if _SAVE and self.save:
            _save_msg(self.session_id, "user", self.text)
        all_msgs = (
            [{"role": "system", "content": system_override or self.system}]
            + self.history
            + [{"role": "user", "content": self.text}]
        )
        ollama_tools = to_ollama_tools(TOOLS)
        while True:
            self.bubble.emit("Thinking through local model pass", "thinking", "thinking_stream")
            data = json.dumps({
                "model": active_model,
                "messages": all_msgs,
                "tools": ollama_tools,
                "stream": False,
                "options": {"temperature": 1.0, "top_p": 0.95, "top_k": 64},
            }).encode()
            req = urllib.request.Request(
                "http://localhost:11434/api/chat",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as r:
                resp = json.loads(r.read())
            msg = resp["message"]
            all_msgs.append(msg)
            reply_text = (msg.get("content") or "").strip()
            if reply_text:
                self.bubble.emit(reply_text, "guppy", "guppy")
                if _SAVE and self.save:
                    _save_msg(self.session_id, "assistant", reply_text)
            tool_calls = msg.get("tool_calls", [])
            if not tool_calls:
                self.history.append({"role": "user", "content": self.text})
                self.history.append({"role": "assistant", "content": reply_text})
                if len(self.history) > 40:
                    self.history[:] = self.history[-40:]
                break
            for tc in tool_calls:
                self.status.emit("thinking")
                name = tc["function"]["name"]
                args = tc["function"]["arguments"]
                preview = ", ".join(f"{k}={repr(v)[:30]}" for k, v in args.items())
                if SHOW_BACKEND_DETAILS:
                    self.bubble.emit(f"⚙️  {name}({preview})", "tool", "tool")
                else:
                    self.bubble.emit(f"Thinking step using {name}", "thinking", "thinking_stream")
                result = run_tool(name, args)
                result_str = (
                    f"Screenshot saved: {result['path']} ({result['size']})"
                    if isinstance(result, dict) and result.get("_screenshot")
                    else str(result)
                )
                if SHOW_BACKEND_DETAILS:
                    self.bubble.emit(f"   ↳ {result_str[:300]}", "tool_result", "tool_result")
                elif result_str.lower().startswith("error"):
                    self.bubble.emit("Thinking step failed and recovered", "thinking", "thinking_stream")
                all_msgs.append({"role": "tool", "content": result_str})


class MerlinWorker(QThread):

    bubble = Signal(str, str, str)
    status = Signal(str)
    done   = Signal()

    def __init__(self, text, history, system, session_id, save=True):
        super().__init__()
        self.text = text
        self.history = history
        self.system = system
        self.session_id = session_id
        self.save = save
        self._perf = {
            "tool_calls": 0,
            "tool_errors": 0,
            "tool_budget_hit": False,
            "model_used": "merlin",
            "task_type": "unknown",
            "route": "merlin_local",
            "route_reason": "council merlin panel",
        }

    def run(self):
        started = time.perf_counter()
        request_id = f"{self.session_id}:{int(started * 1000)}:{id(self)}"
        req_status = "ok"
        _log_perf(
            "council",
            "request_started",
            panel="merlin",
            session_id=self.session_id,
            request_id=request_id,
            mode="ollama",
            input_chars=len(self.text or ""),
        )
        self.status.emit("thinking")
        try:
            self.bubble.emit("Thinking through the next move", "thinking", "thinking_stream")
            self._merlin()
        except Exception as e:
            req_status = "error"
            self.bubble.emit(f"The spell misfired: {e}", "error", "error")
        finally:
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            _log_perf(
                "council",
                "request_complete",
                panel="merlin",
                session_id=self.session_id,
                request_id=request_id,
                mode="ollama",
                input_chars=len(self.text or ""),
                status=req_status,
                latency_ms=latency_ms,
                tool_calls=self._perf["tool_calls"],
                tool_errors=self._perf["tool_errors"],
                tool_budget_hit=self._perf["tool_budget_hit"],
                model_used=self._perf["model_used"],
                task_type=self._perf["task_type"],
                route=self._perf["route"],
                route_reason=self._perf["route_reason"],
            )
            self.status.emit("idle")
            self.done.emit()

    def _merlin(self):
        ok, err = check_ollama("merlin")
        if not ok:
            self.bubble.emit(err, "error", "error")
            return
        if _SAVE and self.save:
            _save_msg(self.session_id, "user", self.text)
        all_msgs = (
            [{"role": "system", "content": self.system}]
            + self.history
            + [{"role": "user", "content": self.text}]
        )
        ollama_tools = to_ollama_tools(MERLIN_TOOLS)
        while True:
            self.bubble.emit("Thinking through local model pass", "thinking", "thinking_stream")
            data = json.dumps({
                "model": "merlin",
                "messages": all_msgs,
                "tools": ollama_tools,
                "stream": False,
                "options": {
                    "temperature": 0.8,
                    "top_p": 0.9,
                    "top_k": 40,
                    "num_predict": _COUNCIL_MERLIN_NUM_PREDICT,
                },
            }).encode()
            req = urllib.request.Request(
                "http://localhost:11434/api/chat",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=_COUNCIL_MERLIN_TIMEOUT) as r:
                resp = json.loads(r.read())
            msg = resp["message"]
            all_msgs.append(msg)
            reply_text = (msg.get("content") or "").strip()
            if reply_text:
                self.bubble.emit(reply_text, "merlin", "merlin")
                if _SAVE and self.save:
                    _save_msg(self.session_id, "assistant", reply_text)
            tool_calls = msg.get("tool_calls", [])
            if not tool_calls:
                self.history.append({"role": "user", "content": self.text})
                self.history.append({"role": "assistant", "content": reply_text})
                if len(self.history) > 40:
                    self.history[:] = self.history[-40:]
                break
            for tc in tool_calls:
                if self._perf["tool_calls"] >= _COUNCIL_TOOL_BUDGET:
                    self._perf["tool_budget_hit"] = True
                    self.bubble.emit(
                        f"Tool budget reached ({_COUNCIL_TOOL_BUDGET}); returning best effort response.",
                        "spell_result",
                        "spell_result",
                    )
                    break
                self.status.emit("thinking")
                self._perf["tool_calls"] += 1
                name = tc["function"]["name"]
                args = tc["function"]["arguments"]
                preview = ", ".join(f"{k}={repr(v)[:30]}" for k, v in args.items())
                if SHOW_BACKEND_DETAILS:
                    self.bubble.emit(f"⚗️  {name}({preview})", "spell", "spell")
                else:
                    self.bubble.emit(f"Thinking step using {name}", "thinking", "thinking_stream")
                result = run_spell(name, args)
                result_str = str(result)
                if result_str.lower().startswith("error"):
                    self._perf["tool_errors"] += 1
                if SHOW_BACKEND_DETAILS:
                    self.bubble.emit(f"   ↳ {result_str[:300]}", "spell_result", "spell_result")
                elif result_str.lower().startswith("error"):
                    self.bubble.emit("Thinking step failed and recovered", "thinking", "thinking_stream")
                all_msgs.append({"role": "tool", "content": str(result)})
            if self._perf["tool_budget_hit"]:
                break


# ── Status dot ─────────────────────────────────────────────────────────────────

class StatusDot(QWidget):
    """Tiny animated indicator embedded in each panel header."""

    def __init__(self, accent: str):
        super().__init__()
        self.setFixedSize(10, 10)
        self._accent = QColor(accent)
        self.state = "idle"
        self._p = 0.0
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(50)

    def set_state(self, s: str):
        self.state = s
        self.update()

    def _tick(self):
        self._p += 0.1
        if self.state == "thinking":
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.state == "thinking":
            c = QColor(240, 160, 0, int(110 + 110 * abs(math.sin(self._p))))
        elif self.state == "speaking":
            c = QColor(180, 255, 180, 220)
        else:
            c = QColor(self._accent)
            c.setAlpha(80)
        p.setBrush(QBrush(c))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(1, 1, 8, 8)


# ── Chat panel ─────────────────────────────────────────────────────────────────

class ChatPanel(QWidget):
    """Reusable chat feed for one agent."""

    def __init__(self, title: str, subtitle: str, accent: str, bg: str, msg_bg: str, dim: str):
        super().__init__()
        self._accent  = accent
        self._msg_bg  = msg_bg
        self._bg      = bg
        self._dim     = dim
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header strip
        hdr = QWidget()
        hdr.setFixedHeight(42)
        hdr.setStyleSheet(f"background:#08080f; border-bottom:1px solid {dim}44;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 16, 0)
        hl.setSpacing(8)

        t_lbl = QLabel(title)
        tf = QFont("Segoe UI", 10, QFont.Weight.Bold)
        tf.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4)
        t_lbl.setFont(tf)
        t_lbl.setStyleSheet(f"color:{accent}; background:transparent;")

        s_lbl = QLabel(subtitle)
        sf = QFont("Segoe UI", 7)
        sf.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
        s_lbl.setFont(sf)
        s_lbl.setStyleSheet(f"color:{dim}; background:transparent;")

        self.dot = StatusDot(accent)

        hl.addWidget(t_lbl)
        hl.addWidget(s_lbl)
        hl.addStretch()
        hl.addWidget(self.dot)
        layout.addWidget(hdr)

        # Scroll area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(
            f"QScrollArea{{background:{bg};border:none;}}"
            f"QScrollBar:vertical{{background:{bg};width:3px;}}"
            f"QScrollBar::handle:vertical{{background:{dim}66;border-radius:1px;}}"
            f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}"
        )
        self._box = QWidget()
        self._box.setStyleSheet(f"background:{bg};")
        self._lay = QVBoxLayout(self._box)
        self._lay.setContentsMargins(12, 12, 12, 8)
        self._lay.setSpacing(4)
        self._lay.addStretch()
        self._think_label = None
        self.scroll.setWidget(self._box)
        layout.addWidget(self.scroll)

    def add_bubble(self, text: str, sender: str, style: str):
        if style == "thinking_stream":
            if self._think_label is not None:
                new_text = text.strip()
                current_text = getattr(self._think_label, "_text", self._think_label.text())
                if new_text and new_text not in current_text:
                    updated_text = f"{current_text}  •  {new_text}" if current_text else new_text
                    self._think_label._text = updated_text
                    self._think_label.setText(updated_text)
                QTimer.singleShot(20, lambda: self.scroll.verticalScrollBar().setValue(
                    self.scroll.verticalScrollBar().maximum()
                ))
                return
            style = "thinking"

        frame = QWidget()
        frame._sender = sender
        frame._text   = text
        frame._style  = style
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(0, 2, 0, 2)
        fl.setSpacing(3)

        S = {
            "guppy":        ("Guppy",            G_ACC,    G_MSG,    f"{G_ACC}33"),
            "merlin":       ("✦ Merlin",        M_ACC,    M_MSG,    f"{M_ACC}44"),
            "user":         ("You",              DIM_TXT,  "#0d0d14","#33333355"),
            "tool":         ("⚙️  Tool",         "#404060","#090910","#22222244"),
            "tool_result":  ("   ↳ Result",      "#303050","#060608","#11111133"),
            "spell":        ("⚗️  Spell",        "#7c3aed","#0a0612","#5522aa33"),
            "spell_result": ("   ↳ Omen",        "#4a3060","#080610","#22113322"),
            "thinking":     ("◌ Thinking",      DIM_TXT,   "#070710", "#22224466"),
            "error":        ("⚠️  Error",        "#ff4444","#1a0000","#ff000033"),
        }
        who_text, who_col, bg, border = S.get(style, S["guppy"])

        # Header row: sender + timestamp
        hdr = QWidget()
        hdr.setStyleSheet("background:transparent;")
        hrow = QHBoxLayout(hdr)
        hrow.setContentsMargins(0, 0, 0, 0)
        hrow.setSpacing(0)

        who = QLabel(who_text)
        wf = QFont(SHARED.font_family, FS_LABEL)
        wf.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
        who.setFont(wf)
        who.setStyleSheet(f"color:{who_col}; background:transparent;")
        hrow.addWidget(who)
        hrow.addStretch()

        if SHARED.show_timestamps:
            ts = QLabel(now_str())
            ts.setFont(QFont(SHARED.font_family, FS_TS))
            ts.setStyleSheet(f"color:{DIM_TXT}; background:transparent;")
            hrow.addWidget(ts)

        fl.addWidget(hdr)

        msg = QLabel(text)
        msg.setWordWrap(True)
        msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        msg.setFont(QFont(SHARED.font_family, SHARED.font_size))
        italic = "font-style:italic;" if style in ("spell", "spell_result", "tool", "tool_result", "thinking") else ""
        r = SHARED.bubble_radius
        msg.setStyleSheet(
            f"QLabel{{background:{bg};border-left:3px solid {border};"
            f"border-radius:{r}px;padding:9px 14px;color:{TEXT};{italic}}}"
        )
        msg._text = text

        fl.addWidget(msg)
        if style == "thinking":
            self._think_label = msg
        elif sender in ("guppy", "merlin"):
            self._think_label = None
        self._lay.insertWidget(self._lay.count() - 1, frame)

        # Fade-in animation
        eff = QGraphicsOpacityEffect(frame)
        frame.setGraphicsEffect(eff)
        eff.setOpacity(0.0)
        anim = QPropertyAnimation(eff, b"opacity", frame)
        anim.setDuration(300)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        frame._fade_anim = anim
        anim.finished.connect(lambda: setattr(frame, '_fade_anim', None))

        QTimer.singleShot(40, lambda: self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()
        ))

    def last_text(self, sender: str) -> str | None:
        for i in range(self._lay.count() - 1, -1, -1):
            item = self._lay.itemAt(i)
            w = item.widget() if item else None
            if w and getattr(w, "_sender", None) == sender:
                return getattr(w, "_text", None)
        return None

    def clear(self):
        while self._lay.count() > 1:
            item = self._lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


# ── Main window ────────────────────────────────────────────────────────────────

class CouncilWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("The Council — Guppy & Merlin")
        self.resize(1400, 780)
        self.setMinimumSize(900, 550)
        self.setStyleSheet(f"background:{BG}; color:{TEXT}; font-family:'Segoe UI';")

        self._api_key    = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        self._mode       = "claude" if (is_online() and self._api_key) else "ollama"
        self._session_id = _dt.now().strftime("%Y%m%d_%H%M%S") if _SAVE else ""
        self._g_system   = get_startup_system()
        self._m_system   = get_merlin_startup_system()
        self._g_history: list = []
        self._m_history: list = []
        self._g_worker   = None
        self._m_worker   = None
        self._route      = "both"
        self._ptt_voice  = None
        self._g_voice    = None
        self._m_voice    = None
        self._g_last_persona_reply = ""
        self._m_last_persona_reply = ""
        self._tts_generation = 0
        self._status_strip = None
        self._startup_checklist = None
        self._timeline = None
        self._lat_spark = None
        self._queue_spark = None
        self._lat_points = []
        self._queue_points = []
        self._last_timeline_key = ""

        self._setup_voice()
        self._build()
        self._greet()
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(lambda: open_debug_console(self))
        QShortcut(QKeySequence("Ctrl+K"), self).activated.connect(self._open_command_palette)
        self._ui_tick = QTimer(self)
        self._ui_tick.timeout.connect(self._refresh_telemetry_panels)
        self._ui_tick.start(1800)
        self._cmd_timer = QTimer(self)
        self._cmd_timer.timeout.connect(self._poll_agent_commands)
        self._cmd_timer.start(2000)

    # ── Voice ──────────────────────────────────────────────────────────────────

    def _setup_voice(self):
        try:
            from guppy_voice import GuppyVoice, VoiceConfig
            self._g_voice = GuppyVoice(VoiceConfig(
                tts_voice=os.environ.get("GUPPY_TTS_VOICE", "bm_lewis"),
                tts_rate=os.environ.get("GUPPY_TTS_RATE", "+28%"),
                tts_pitch=os.environ.get("GUPPY_TTS_PITCH", "+12Hz"),
            ))
            self._m_voice = GuppyVoice(VoiceConfig(
                tts_voice=os.environ.get("MERLIN_TTS_VOICE", "bm_lewis"),
                tts_rate=os.environ.get("MERLIN_TTS_RATE", "-18%"),
                tts_pitch=os.environ.get("MERLIN_TTS_PITCH", "-14Hz"),
            ))
            self._ptt_voice = GuppyVoice(VoiceConfig())
        except Exception:
            pass

    # ── Layout ─────────────────────────────────────────────────────────────────

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        root_lay = QVBoxLayout(root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # Title strip
        title_bar = QWidget()
        title_bar.setFixedHeight(34)
        title_bar.setStyleSheet(f"background:#07070e; border-bottom:1px solid {DIVIDER};")
        tbl = QHBoxLayout(title_bar)
        tbl.setContentsMargins(20, 0, 20, 0)
        lbl = QLabel("THE COUNCIL")
        lf = QFont("Segoe UI", 9, QFont.Weight.Bold)
        lf.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 7)
        lbl.setFont(lf)
        lbl.setStyleSheet("color:#5a5a8a; background:transparent;")
        clr_btn = QPushButton("Clear All")
        clr_btn.setFixedHeight(CH_SM - 10)
        clr_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clr_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#4a4a70;border:1px solid #1a1a2e;"
            f"border-radius:3px;font-size:{FS_LABEL}px;padding:0 8px;}}"
            "QPushButton:hover{color:#9090c0;border-color:#3a3a5e;}"
        )
        clr_btn.clicked.connect(self._clear_all)
        cmd_btn = QPushButton("Commands")
        cmd_btn.setFixedHeight(CH_SM - 10)
        cmd_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cmd_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#4a4a70;border:1px solid #1a1a2e;"
            f"border-radius:3px;font-size:{FS_LABEL}px;padding:0 8px;}}"
            "QPushButton:hover{color:#a0a0d0;border-color:#4a4a6e;}"
        )
        cmd_btn.clicked.connect(self._open_command_palette)
        settings_btn = QPushButton("⚙ Settings")
        settings_btn.setFixedHeight(CH_SM - 10)
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#4a4a70;border:1px solid #1a1a2e;"
            f"border-radius:3px;font-size:{FS_LABEL}px;padding:0 8px;}}"
            "QPushButton:hover{color:#a0a0d0;border-color:#4a4a6e;}"
        )
        settings_btn.clicked.connect(self._open_runtime_settings)
        diag_btn = QPushButton("Diagnostics")
        diag_btn.setFixedHeight(CH_SM - 10)
        diag_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        diag_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#4a4a70;border:1px solid #1a1a2e;"
            f"border-radius:3px;font-size:{FS_LABEL}px;padding:0 8px;}}"
            "QPushButton:hover{color:#a0a0d0;border-color:#4a4a6e;}"
        )
        diag_btn.clicked.connect(self._collect_diagnostics)
        tbl.addWidget(lbl)
        tbl.addStretch()
        tbl.addWidget(settings_btn)
        tbl.addWidget(cmd_btn)
        tbl.addWidget(diag_btn)
        tbl.addWidget(clr_btn)
        root_lay.addWidget(title_bar)

        telem_wrap = QWidget()
        twl = QVBoxLayout(telem_wrap)
        twl.setContentsMargins(8, 8, 8, 6)
        twl.setSpacing(6)
        self._status_strip = StatusStrip(accent="#7777dd")
        twl.addWidget(self._status_strip)

        mini = QHBoxLayout()
        mini.setSpacing(6)
        self._startup_checklist = StartupChecklist(parent=self)
        self._startup_checklist.setMaximumWidth(220)
        mini.addWidget(self._startup_checklist)

        trend_wrap = QFrame()
        trend_wrap.setStyleSheet("QFrame{background:#0b0e16;border:1px solid #273246;border-radius:6px;}")
        trl = QVBoxLayout(trend_wrap)
        trl.setContentsMargins(8, 6, 8, 6)
        trl.setSpacing(4)
        lat_lbl = QLabel("COUNCIL LATENCY")
        lat_lbl.setStyleSheet(f"color:#8a93a4;background:transparent;font-family:{FF_MONO};font-size:{FS_LABEL}px;")
        trl.addWidget(lat_lbl)
        self._lat_spark = Sparkline(color="#92a8ff")
        trl.addWidget(self._lat_spark)
        q_lbl = QLabel("COUNCIL QUEUE")
        q_lbl.setStyleSheet(f"color:#8a93a4;background:transparent;font-family:{FF_MONO};font-size:{FS_LABEL}px;")
        trl.addWidget(q_lbl)
        self._queue_spark = Sparkline(color="#d9a94f")
        trl.addWidget(self._queue_spark)
        mini.addWidget(trend_wrap)

        self._timeline = TimelinePanel("COUNCIL EVENTS", self)
        self._timeline.setMaximumHeight(120)
        mini.addWidget(self._timeline, stretch=1)
        twl.addLayout(mini)
        root_lay.addWidget(telem_wrap)

        # Split panels
        panels = QWidget()
        pl = QHBoxLayout(panels)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(0)

        self._g_panel = ChatPanel("GUPPY",  "Chief of Staff", G_ACC, G_BG, G_MSG, G_DIM)
        self._m_panel = ChatPanel("MERLIN", "The Wizard",     M_ACC, M_BG, M_MSG, M_DIM)

        div = QFrame()
        div.setFrameShape(QFrame.Shape.VLine)
        div.setStyleSheet(f"color:{DIVIDER};")

        pl.addWidget(self._g_panel)
        pl.addWidget(div)
        pl.addWidget(self._m_panel)
        root_lay.addWidget(panels, stretch=1)

        # Input bar
        bar = QWidget()
        bar.setFixedHeight(60)
        bar.setStyleSheet(f"background:{BAR}; border-top:1px solid {DIVIDER};")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(14, 10, 14, 10)
        bl.setSpacing(7)

        self._rbtn: dict = {}
        for key, label, color in [
            ("guppy",  "GUPPY",    G_ACC),
            ("both",   "⚡ BOTH",   "#7777dd"),
            ("merlin", "✦ MERLIN", M_ACC),
        ]:
            b = QPushButton(label)
            b.setFixedHeight(CH_MD + 2)
            b.setFixedWidth(86)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setCheckable(True)
            b.setProperty("rcolor", color)
            b.clicked.connect(lambda _, k=key: self._set_route(k))
            self._rbtn[key] = b
            bl.addWidget(b)

        bl.addSpacing(4)

        self.inp = QLineEdit()
        self.inp.setPlaceholderText("Speak to the Council...")
        self.inp.setStyleSheet(
            "QLineEdit{background:#0d0d1a;color:#d8d8e8;"
            f"border:1px solid #1a1a2e;border-radius:6px;padding:0 14px;font-size:{FS_BODY}pt;}}"
            "QLineEdit:focus{border-color:#3a3a6e;}"
        )
        self.inp.returnPressed.connect(self._send)
        self.inp.textEdited.connect(self._on_user_typing)

        send_btn = QPushButton("▶")
        send_btn.setFixedSize(CH_LG - 4, CH_LG - 4)
        send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        send_btn.setStyleSheet(
            "QPushButton{background:#0d0d1a;color:#5050a0;"
            f"border:1px solid #2a2a4e;border-radius:6px;font-size:{FS_BODY + 3}pt;}}"
            "QPushButton:hover{background:#1a1a2e;color:#d8d8e8;}"
        )
        send_btn.clicked.connect(self._send)

        self._ptt_btn = QPushButton("🎤")
        self._ptt_btn.setFixedSize(CH_LG - 4, CH_LG - 4)
        self._ptt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ptt_btn.setStyleSheet(
            "QPushButton{background:#0d0d1a;color:#404060;"
            f"border:1px solid #1a1a2e;border-radius:6px;font-size:{FS_BODY + 3}pt;}}"
            "QPushButton:hover{color:#7070b0;}"
            "QPushButton:pressed{background:#1a1a3e;color:#a0a0ff;}"
        )
        self._ptt_btn.pressed.connect(self._ptt_start)
        self._ptt_btn.released.connect(self._ptt_stop)

        self._quiet_btn = QPushButton("🔊")
        self._quiet_btn.setFixedSize(CH_LG - 4, CH_LG - 4)
        self._quiet_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._quiet_btn.setToolTip("Toggle all voice output")
        self._quiet_btn.setStyleSheet(
            "QPushButton{background:#0d0d1a;color:#404060;"
            f"border:1px solid #1a1a2e;border-radius:6px;font-size:{FS_BODY + 3}pt;}}"
            "QPushButton:hover{color:#9090c0;}"
        )
        self._quiet_btn.clicked.connect(self._toggle_quiet)

        bl.addWidget(self.inp, stretch=1)
        bl.addWidget(send_btn)
        bl.addWidget(self._ptt_btn)
        bl.addWidget(self._quiet_btn)
        root_lay.addWidget(bar)

        self._set_route("both")

    # ── Routing ────────────────────────────────────────────────────────────────

    def _set_route(self, key: str):
        self._route = key
        colors = {"guppy": G_ACC, "both": "#7777dd", "merlin": M_ACC}
        for k, btn in self._rbtn.items():
            col = colors[k]
            if k == key:
                btn.setChecked(True)
                btn.setStyleSheet(
                    f"QPushButton{{background:{col}22;color:{col};"
                    f"border:1px solid {col};border-radius:4px;"
                    f"font-size:{FS_SMALL}px;font-weight:bold;}}"
                )
            else:
                btn.setChecked(False)
                btn.setStyleSheet(
                    "QPushButton{background:transparent;color:#404060;"
                    f"border:1px solid #1a1a2e;border-radius:4px;font-size:{FS_SMALL}px;}}"
                    "QPushButton:hover{color:#7070a0;border-color:#3a3a5e;}"
                )

    def _send(self):
        text = self.inp.text().strip()
        if text:
            self._stop_voice_output()
            self.inp.clear()
            self._dispatch(text)

    def _poll_agent_commands(self):
        """IPC poll: check runtime/council.cmd every 2 s."""
        cmd_path = Path("runtime") / "council.cmd"
        if not cmd_path.exists():
            return
        try:
            data = json.loads(cmd_path.read_text(encoding="utf-8"))
            cmd_path.unlink(missing_ok=True)
        except Exception:
            return

        cmd = data.get("cmd", "")
        if cmd == "nudge":
            self._g_panel.add_bubble("Hub nudge received.", "tool_result", "tool_result")
            self._m_panel.add_bubble("Hub nudge received.", "tool_result", "tool_result")
        elif cmd == "clear_history":
            self._g_history.clear()
            self._m_history.clear()
            self._g_panel.add_bubble("Council histories cleared by hub.", "tool_result", "tool_result")
        elif cmd == "reset_context":
            self._g_system = get_startup_system()
            self._m_system = get_merlin_startup_system()
            self._g_panel.add_bubble("Council contexts reset.", "tool_result", "tool_result")
        elif cmd == "ambient_offer":
            payload = data.get("payload", {}) if isinstance(data, dict) else {}
            preview = str(payload.get("preview", ""))[:180]
            self._g_panel.add_bubble(f"Ambient hint: {preview}", "tool_result", "tool_result")
        elif cmd == "reminder_fired":
            payload = data.get("payload", {}) if isinstance(data, dict) else {}
            msg = str(payload.get("message", "Reminder"))[:220]
            rid = str(payload.get("short_id", ""))
            suffix = f" (ID {rid})" if rid else ""
            self._g_panel.add_bubble(f"Reminder completed: {msg}{suffix}", "tool_result", "tool_result")
            self._m_panel.add_bubble(f"Reminder completed: {msg}{suffix}", "tool_result", "tool_result")
        elif cmd == "report_status":
            status_path = Path("runtime") / "council.status"
            try:
                status_path.write_text(
                    json.dumps({
                        "ts": _dt.now().isoformat(),
                        "mode": self._mode,
                        "route": self._route,
                        "g_history_len": len(self._g_history),
                        "m_history_len": len(self._m_history),
                        "g_busy": bool(self._g_worker and self._g_worker.isRunning()),
                        "m_busy": bool(self._m_worker and self._m_worker.isRunning()),
                    }),
                    encoding="utf-8",
                )
            except Exception:
                pass

    def _dispatch(self, text: str):
        self._stop_voice_output()
        if self._route in ("guppy", "both"):
            self._g_panel.add_bubble(text, "user", "user")
            self._run_guppy(text)
        if self._route in ("merlin", "both"):
            self._m_panel.add_bubble(text, "user", "user")
            self._run_merlin(text)

    # ── Agent runners ──────────────────────────────────────────────────────────

    def _run_guppy(self, text: str, save: bool = True):
        if self._g_worker and self._g_worker.isRunning():
            return
        w = GuppyWorker(
            text, self._g_history, self._mode,
            self._api_key, self._g_system, self._session_id,
            save=save,
        )
        w.bubble.connect(self._on_guppy_bubble)
        w.status.connect(self._g_panel.dot.set_state)
        w.done.connect(self._on_guppy_done)
        w.start()
        self._g_worker = w

    def _run_merlin(self, text: str, save: bool = True):
        if self._m_worker and self._m_worker.isRunning():
            return
        w = MerlinWorker(text, self._m_history, self._m_system, self._session_id, save=save)
        w.bubble.connect(self._on_merlin_bubble)
        w.status.connect(self._m_panel.dot.set_state)
        w.done.connect(self._on_merlin_done)
        w.start()
        self._m_worker = w

    def _on_guppy_bubble(self, text: str, sender: str, style: str):
        self._g_panel.add_bubble(text, sender, style)
        if sender == "guppy" and style == "guppy":
            self._g_last_persona_reply = text

    def _on_merlin_bubble(self, text: str, sender: str, style: str):
        self._m_panel.add_bubble(text, sender, style)
        if sender == "merlin" and style == "merlin":
            self._m_last_persona_reply = text

    def _on_guppy_done(self):
        if self._g_voice and self._g_last_persona_reply:
            token = self._tts_generation
            t = self._g_last_persona_reply
            threading.Thread(target=lambda: self._speak_if_current(self._g_voice, token, t), daemon=True).start()

    def _on_merlin_done(self):
        if self._m_voice and self._m_last_persona_reply:
            token = self._tts_generation
            t = self._m_last_persona_reply
            threading.Thread(target=lambda: self._speak_if_current(self._m_voice, token, t), daemon=True).start()

    def _speak_if_current(self, voice_obj, token: int, text: str):
        if token != self._tts_generation:
            return
        voice_obj.speak(text)

    def _stop_voice_output(self):
        self._tts_generation += 1
        for v in (self._g_voice, self._m_voice, self._ptt_voice):
            if not v:
                continue
            for method_name in ("stop_tts", "stop_speaking"):
                stop_fn = getattr(v, method_name, None)
                if callable(stop_fn):
                    try:
                        stop_fn()
                        break
                    except Exception:
                        continue

    def _on_user_typing(self, _text: str):
        self._stop_voice_output()

    # ── PTT ────────────────────────────────────────────────────────────────────

    def _ptt_start(self):
        if not self._ptt_voice:
            return
        self._ptt_btn.setStyleSheet(
            "QPushButton{background:#1a1a3e;color:#a0a0ff;"
            f"border:1px solid #5050aa;border-radius:6px;font-size:{FS_BODY + 3}pt;}}"
        )
        threading.Thread(target=self._listen_thread, daemon=True).start()

    def _listen_thread(self):
        res = self._ptt_voice.listen_once(timeout=30)
        QTimer.singleShot(0, self._ptt_restore_btn)
        if res.get("text"):
            QTimer.singleShot(0, lambda: self._dispatch(res["text"]))
        elif res.get("error"):
            QTimer.singleShot(0, lambda: self._g_panel.add_bubble(
                f"Voice error: {res['error']}", "error", "error"
            ))

    def _ptt_stop(self):
        if self._ptt_voice:
            self._ptt_voice.stop_listening()

    def _ptt_restore_btn(self):
        self._ptt_btn.setStyleSheet(
            "QPushButton{background:#0d0d1a;color:#404060;"
            f"border:1px solid #1a1a2e;border-radius:6px;font-size:{FS_BODY + 3}pt;}}"
            "QPushButton:hover{color:#7070b0;}"
            "QPushButton:pressed{background:#1a1a3e;color:#a0a0ff;}"
        )

    def _toggle_quiet(self):
        """Silence/un-silence all council voices simultaneously."""
        voices = [v for v in (self._g_voice, self._m_voice, self._ptt_voice) if v]
        if not voices:
            return
        # Use first voice as source of truth; sync the rest
        is_quiet = voices[0].toggle_quiet()
        for v in voices[1:]:
            v.set_quiet(is_quiet)
        if is_quiet:
            self._quiet_btn.setText("🔇")
            self._quiet_btn.setStyleSheet(
                "QPushButton{background:#0d0d1a;color:#ff6644;"
                f"border:1px solid #ff664455;border-radius:6px;font-size:{FS_BODY + 3}pt;}}"
                "QPushButton:hover{border-color:#ff6644;}"
            )
        else:
            self._quiet_btn.setText("🔊")
            self._quiet_btn.setStyleSheet(
                "QPushButton{background:#0d0d1a;color:#404060;"
                f"border:1px solid #1a1a2e;border-radius:6px;font-size:{FS_BODY + 3}pt;}}"
                "QPushButton:hover{color:#9090c0;}"
            )

    def _startup_self_check(self) -> dict:
        readiness = {}
        readiness["auth"] = "READY" if (self._api_key and self._api_key.startswith("sk-ant-")) else ("PARTIAL" if self._api_key else "MISSING")
        g_ok, _g_err = check_ollama("guppy")
        m_ok, _m_err = check_ollama("merlin")
        readiness["ollama"] = "READY" if (g_ok and m_ok) else ("PARTIAL" if (g_ok or m_ok) else "MISSING")
        readiness["voice"] = "READY" if (self._g_voice and self._m_voice and self._ptt_voice) else "MISSING"
        return readiness

    def _refresh_telemetry_panels(self):
        checks = self._startup_self_check()
        g = rolling_agent_snapshot("guppy", window_seconds=900)
        m = rolling_agent_snapshot("merlin", window_seconds=900)
        p95 = max(float(g.get("p95_ms", 0.0) or 0.0), float(m.get("p95_ms", 0.0) or 0.0))
        p99 = max(float(g.get("p99_ms", 0.0) or 0.0), float(m.get("p99_ms", 0.0) or 0.0))
        qd = int(g.get("queue_depth", 0) or 0) + int(m.get("queue_depth", 0) or 0)

        if self._status_strip:
            self._status_strip.set_summary(self._route, checks.get("auth", "MISSING"), checks.get("ollama", "MISSING"), checks.get("voice", "MISSING"))
            self._status_strip.set_latency(p95, p99, qd)
            g_backend = "none"
            m_backend = "none"
            if self._g_voice and hasattr(self._g_voice, "backend_status"):
                try:
                    g_backend = str(self._g_voice.backend_status().get("tts_backend", "none"))
                except Exception:
                    g_backend = "unknown"
            if self._m_voice and hasattr(self._m_voice, "backend_status"):
                try:
                    m_backend = str(self._m_voice.backend_status().get("tts_backend", "none"))
                except Exception:
                    m_backend = "unknown"
            self._status_strip.set_voice_detail(
                f"G:{g_backend}/M:{m_backend}",
                f"{os.environ.get('GUPPY_TTS_VOICE', '-')}/{os.environ.get('MERLIN_TTS_VOICE', '-')}",
            )
            incidents = []
            if checks.get("auth") != "READY":
                incidents.append({"text": "AUTH", "severity": "warn" if checks.get("auth") == "PARTIAL" else "error"})
            if checks.get("ollama") != "READY":
                incidents.append({"text": "OLLAMA", "severity": "warn" if checks.get("ollama") == "PARTIAL" else "error"})
            if checks.get("voice") != "READY":
                incidents.append({"text": "VOICE", "severity": "warn"})
            if qd > 0:
                incidents.append({"text": f"QUEUE {qd}", "severity": "warn"})
            self._status_strip.set_incidents(incidents)

        if self._startup_checklist:
            self._startup_checklist.set_checks(checks)

        gl = g.get("latencies", [])
        ml = m.get("latencies", [])
        merged = []
        if isinstance(gl, list):
            merged.extend([float(v) for v in gl if isinstance(v, (int, float))])
        if isinstance(ml, list):
            merged.extend([float(v) for v in ml if isinstance(v, (int, float))])
        if merged:
            self._lat_points = merged[-60:]
        if self._lat_spark:
            self._lat_spark.set_values(self._lat_points)
        self._queue_points.append(qd)
        self._queue_points = self._queue_points[-60:]
        if self._queue_spark:
            self._queue_spark.set_values(self._queue_points)

        if self._timeline:
            ge = recent_agent_events("guppy", limit=3)
            me = recent_agent_events("merlin", limit=3)
            mix = sorted((ge + me), key=lambda x: str(x.get("ts", "")))
            if mix:
                last = mix[-1]
                key = f"{last.get('ts','')}|{last.get('agent','')}|{last.get('event','')}|{last.get('request_id','')}"
                if key != self._last_timeline_key:
                    self._last_timeline_key = key
                    ts = str(last.get("ts", ""))[11:19] or "--:--:--"
                    self._timeline.add_event(ts, f"{last.get('agent','').upper()} {last.get('event','event')}")

    def _open_runtime_settings(self):
        theme = {
            "bg": BG, "bg3": DIVIDER, "text": TEXT, "dim": DIM_TXT,
            "border": DIVIDER, "accent": G_ACC,
            "font_family": FF_MONO, "font_size": FS_BODY,
        }
        merged = _open_settings_dlg(self, load_app_settings(), theme)
        if merged is not None:
            APP_SETTINGS.update(merged)
            profile = merged.get("runtime_profile", "standard")
            self._g_panel.add_bubble(
                f"Settings saved. Profile: {profile}.", "tool_result", "tool_result"
            )

    def _open_command_palette(self):
        commands = [
            {"name": "Open Settings", "action": self._open_runtime_settings},
            {"name": "Route: Guppy", "action": lambda: self._set_route("guppy")},
            {"name": "Route: Both", "action": lambda: self._set_route("both")},
            {"name": "Route: Merlin", "action": lambda: self._set_route("merlin")},
            {"name": "Toggle Quiet", "action": self._toggle_quiet},
            {"name": "Collect Diagnostics", "action": self._collect_diagnostics},
            {"name": "Clear All", "action": self._clear_all},
        ]
        dlg = CommandPaletteDialog(commands, self)
        dlg.exec()

    def _collect_diagnostics(self):
        path = create_diagnostics_bundle("council")
        self._g_panel.add_bubble(f"Diagnostics bundle created: {path}", "tool_result", "tool_result")
        if self._timeline:
            self._timeline.add_event(now_str(), "diagnostics bundle created")

    # ── Session summarization ──────────────────────────────────────────────────

    def _readable_histories(self) -> list[str]:
        """Flatten both agent histories into labelled plain-text lines."""
        lines = []
        for history, agent_label in [
            (self._g_history, "Guppy"),
            (self._m_history, "Merlin"),
        ]:
            for msg in history:
                role    = msg.get("role", "")
                content = msg.get("content", "")
                label   = "Ryan" if role == "user" else agent_label if role == "assistant" else None
                if label is None:
                    continue
                if isinstance(content, str):
                    snippet = content.strip()[:300]
                    if snippet:
                        lines.append(f"{label}: {snippet}")
                elif isinstance(content, list):
                    texts = []
                    for block in content:
                        if hasattr(block, "type") and block.type == "text":
                            texts.append(block.text.strip()[:300])
                        elif isinstance(block, dict) and block.get("type") == "text":
                            texts.append(block.get("text", "").strip()[:300])
                    joined = " ".join(texts).strip()
                    if joined:
                        lines.append(f"{label}: {joined[:300]}")
        return lines

    def _save_session_summary(self):
        """Summarise the current council session via Haiku. Fire-and-forget."""
        lines = self._readable_histories()
        if len(lines) < 4:
            return
        if not self._api_key or self._mode != "claude":
            return

        session_id  = self._session_id
        convo_text  = "\n".join(lines[:40])

        def _do():
            try:
                import anthropic
                from guppy_memory import save_session_summary
                client = anthropic.Anthropic(api_key=self._api_key)
                resp = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=350,
                    messages=[{
                        "role": "user",
                        "content": (
                            "This is a Council session where Ryan spoke with both Guppy "
                            "and Merlin. Summarise in 4-6 bullet points covering: decisions "
                            "made, facts about Ryan, tasks created, preferences expressed, "
                            "anything worth remembering. Use bullets starting with '•'.\n\n"
                            f"{convo_text}"
                        ),
                    }],
                )
                summary = resp.content[0].text.strip()
                save_session_summary(session_id, summary)
            except Exception as e:
                import logging
                logging.getLogger(__name__).debug(f"Council summary failed: {e}")

        threading.Thread(target=_do, daemon=True).start()

    def closeEvent(self, event):
        if _HB_OK: _stop_hb('council')
        self._save_session_summary()
        event.accept()

    # ── Misc ───────────────────────────────────────────────────────────────────

    def _clear_all(self):
        self._save_session_summary()
        if _SAVE:
            from datetime import datetime as _dt2
            self._session_id = _dt2.now().strftime("%Y%m%d_%H%M%S")
        self._g_history.clear()
        self._m_history.clear()
        self._g_panel.clear()
        self._m_panel.clear()

    def _greet(self):
        mode_desc = "Claude online" if self._mode == "claude" else "local model"
        self._run_guppy(
            f"Greet Master Ryan in one sentence. Running {mode_desc}. "
            "You are in the Council terminal alongside Merlin.",
            save=False,
        )
        self._run_merlin(
            "Greet your Apprentice Ryan in one sentence. "
            "You are in the Council terminal alongside Guppy. Keep it brief.",
            save=False,
        )


# ── Application bootstrap ──────────────────────────────────────────────────────

app = QApplication(sys.argv)
app.setStyle("Fusion")

pal = QPalette()
pal.setColor(QPalette.ColorRole.Window,          QColor(BG))
pal.setColor(QPalette.ColorRole.WindowText,      QColor(TEXT))
pal.setColor(QPalette.ColorRole.Base,            QColor("#0d0d1a"))
pal.setColor(QPalette.ColorRole.Text,            QColor(TEXT))
pal.setColor(QPalette.ColorRole.Button,          QColor(BAR))
pal.setColor(QPalette.ColorRole.ButtonText,      QColor(TEXT))
pal.setColor(QPalette.ColorRole.Highlight,       QColor("#3a3aaa"))
pal.setColor(QPalette.ColorRole.HighlightedText, QColor(BG))
app.setPalette(pal)

window = CouncilWindow()
window.show()
sys.exit(app.exec())

