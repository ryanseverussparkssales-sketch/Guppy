"""
guppy_ui.py — Main Guppy window (PySide6)
==========================================
Palette sourced from guppy_theme.py — edit theme.json to customize.
"""
import sys, os, json, math, threading, time
import urllib.request
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QScrollArea, QLabel, QPushButton, QLineEdit, QFrame, QSizePolicy,
    QGraphicsOpacityEffect,
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QRectF, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import (
    QPainter, QColor, QPen, QFont, QRadialGradient, QBrush,
    QPalette, QKeySequence, QShortcut,
)

from guppy_core import TOOLS, run_tool, is_online, check_ollama, get_startup_system, to_ollama_tools
from guppy_theme import GUPPY_THEME as T, SHARED, now_str
from debug_console import open_debug_console
from utils.env_bootstrap import load_env_file
from utils.telemetry_window import rolling_agent_snapshot, recent_agent_events
from utils.diagnostics_bundle import create_diagnostics_bundle
from ui.components.status_strip import StatusStrip
from ui.components.timeline_panel import TimelinePanel
from ui.components.startup_checklist import StartupChecklist
from ui.components.sparkline import Sparkline
from ui.components.command_palette import CommandPaletteDialog

load_env_file()

SHOW_BACKEND_DETAILS = os.environ.get("GUPPY_SHOW_BACKEND_DETAILS", "0").strip().lower() in {"1", "true", "yes", "on"}

FF_MONO = SHARED.font_family_mono
FS_BODY = SHARED.font_size
FS_SMALL = SHARED.font_size_small
FS_LABEL = SHARED.sidebar_label_font_size
FS_TITLE = SHARED.font_size_title
FS_TS = SHARED.timestamp_font_size
CH_SM = SHARED.control_height_sm
CH_MD = SHARED.control_height_md
CH_LG = SHARED.control_height_lg

try:
    from utils.agent_perf import log_agent_performance as _log_perf
except ImportError:
    def _log_perf(*_args, **_kwargs):
        return

try:
    from utils.session_logger import log_session_event as _log_session_event
except ImportError:
    def _log_session_event(*_args, **_kwargs):
        return

try:
    from guppy_daemon import get_daemon_manager
    _DAEMON_AVAILABLE = True
except ImportError:
    _DAEMON_AVAILABLE = False

try:
    from guppy_memory import save_message as _save_msg
    from datetime import datetime as _dt
    _SAVE = True
except ImportError:
    _SAVE = False

try:
    from utils.heartbeat import start_heartbeat as _start_hb, stop_heartbeat as _stop_hb, write_activity as _write_act, clear_activity as _clear_act
    _HB_OK = True
except ImportError:
    _HB_OK = False


# ── Worker ─────────────────────────────────────────────────────────────────────

class Worker(QThread):
    bubble = Signal(str, str, str)
    orb    = Signal(str)
    done   = Signal()

    def __init__(
        self,
        text,
        history,
        mode,
        api_key,
        system,
        session_id,
        model="guppy",
        claude_model="claude-sonnet-4-6",
        claude_backup_model="claude-haiku-4-5-20251001",
        save=True,
    ):
        super().__init__()
        self.text       = text
        self.history    = history
        self.mode       = mode
        self.api_key    = api_key
        self.system     = system
        self.session_id = session_id
        self.model      = model
        self.claude_model = claude_model
        self.claude_backup_model = claude_backup_model
        self.save       = save   # False for internal/greeting messages
        self._perf = {
            "tool_calls": 0,
            "tool_errors": 0,
            "fallback_used": False,
            "response_chars": 0,
            "model_used": "",
            "status": "ok",
            "error": "",
        }

    @staticmethod
    def _model_pair_for_tier(tier: str) -> tuple[str, str]:
        if (tier or "").lower() == "haiku":
            return ("claude-haiku-4-5-20251001", "claude-sonnet-4-6")
        return ("claude-sonnet-4-6", "claude-haiku-4-5-20251001")

    def _route_auto_mode(self) -> tuple[str, str, str | None, str | None]:
        text = (self.text or "").strip()
        lower = text.lower()

        if not self.api_key or not is_online():
            return ("ollama", "local-only fallback (no key or offline)", None, None)

        selected_tier = "haiku" if "haiku" in (self.claude_model or "").lower() else "sonnet"
        force_sonnet = any(k in lower for k in (
            "superboost", "deep analysis", "architecture", "redesign",
            "production incident", "security review", "threat model",
        ))
        force_haiku = any(k in lower for k in (
            "upscale to haiku", "haiku pass", "quick cloud pass",
        ))

        if force_sonnet:
            model, backup = self._model_pair_for_tier("sonnet")
            return ("claude", "superboost trigger -> sonnet", model, backup)
        if force_haiku:
            model, backup = self._model_pair_for_tier("haiku")
            return ("claude", "haiku upscale trigger", model, backup)

        score = 0
        if len(text) >= 240:
            score += 1
        if len(text) >= 520:
            score += 1
        if len(text) >= 900:
            score += 1

        if any(k in lower for k in (
            "compare", "tradeoff", "plan", "strategy", "roadmap", "why",
            "design", "refactor", "multi-step", "root cause", "postmortem",
        )):
            score += 1
        if any(k in lower for k in (
            "security", "auth", "migration", "performance", "regression",
            "test matrix", "risk", "compliance", "incident",
        )):
            score += 2

        if score >= 4:
            model, backup = self._model_pair_for_tier("sonnet")
            return ("claude", "high-complexity route -> sonnet", model, backup)
        if score >= 2:
            model, backup = self._model_pair_for_tier(selected_tier)
            return ("claude", f"medium-complexity route -> {selected_tier}", model, backup)

        return ("ollama", "fast local route", None, None)

    def run(self):
        started = time.perf_counter()
        request_id = f"{self.session_id}:{int(started * 1000)}:{id(self)}"
        _log_perf(
            "guppy",
            "request_started",
            session_id=self.session_id,
            request_id=request_id,
            mode=self.mode,
            input_chars=len(self.text or ""),
        )
        self.orb.emit("thinking")
        if _HB_OK: _write_act("guppy", "thinking")
        try:
            route_mode = self.mode
            route_reason = "manual route"
            route_claude_model = None
            route_claude_backup = None
            if self.mode == "auto":
                route_mode, route_reason, route_claude_model, route_claude_backup = self._route_auto_mode()
                if route_mode == "claude":
                    route_tier = "Haiku" if "haiku" in (route_claude_model or "").lower() else "Sonnet"
                    self.bubble.emit(f"routing to Claude {route_tier}  •  {route_reason}", "thinking", "thinking_stream")
                else:
                    self.bubble.emit(f"routing to local model  •  {route_reason}", "thinking", "thinking_stream")
            else:
                self.bubble.emit(f"mode: {self.mode}", "thinking", "thinking_stream")
            if route_mode == "claude":
                self._claude(route_claude_model, route_claude_backup)
            else:
                self._ollama()
            self._perf["route"] = route_mode
            self._perf["route_reason"] = route_reason
        except Exception as e:
            self._perf["status"] = "error"
            self._perf["error"] = str(e)
            self.bubble.emit(f"Error: {e}", "error", "error")
        finally:
            self._perf["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
            _log_perf(
                "guppy",
                "request_complete",
                session_id=self.session_id,
                request_id=request_id,
                mode=self.mode,
                input_chars=len(self.text or ""),
                tool_calls=self._perf["tool_calls"],
                tool_errors=self._perf["tool_errors"],
                response_chars=self._perf["response_chars"],
                fallback_used=self._perf["fallback_used"],
                model_used=self._perf["model_used"],
                status=self._perf["status"],
                error=self._perf["error"],
                latency_ms=self._perf["latency_ms"],
            )
            self.orb.emit("idle")
            if _HB_OK: _write_act("guppy", "idle")
            self.done.emit()


    @staticmethod
    def _sanitise_history(msgs: list) -> list:
        """Remove any tool_result blocks that have no matching tool_use in the
        preceding assistant message.  Prevents Claude 400 errors on context trim."""
        valid_ids: set = set()
        clean = []
        for msg in msgs:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "assistant":
                if isinstance(content, list):
                    for block in content:
                        bid = getattr(block, "id", None) or (block.get("id") if isinstance(block, dict) else None)
                        btype = getattr(block, "type", None) or (block.get("type") if isinstance(block, dict) else None)
                        if btype == "tool_use" and bid:
                            valid_ids.add(bid)
                clean.append(msg)
            elif role == "user":
                if isinstance(content, list):
                    filtered = []
                    for block in content:
                        btype = block.get("type") if isinstance(block, dict) else None
                        bid   = block.get("tool_use_id") if isinstance(block, dict) else None
                        if btype == "tool_result" and bid not in valid_ids:
                            continue  # orphan — drop it
                        filtered.append(block)
                    if not filtered:
                        continue  # skip empty user messages
                    msg = dict(msg)
                    msg["content"] = filtered
                clean.append(msg)
            else:
                clean.append(msg)
        return clean
    def _claude(self, forced_model=None, forced_backup=None):
        import anthropic
        client = anthropic.Anthropic(api_key=self.api_key)
        active_model = (forced_model or self.claude_model or "claude-sonnet-4-6").strip()
        backup_model = (forced_backup if forced_backup is not None else self.claude_backup_model or "").strip()
        if _SAVE and self.save:
            _save_msg(self.session_id, "user", self.text)
        current_system = get_startup_system(session_id=self.session_id, query_context=self.text)
        # Sanitise incoming history before building msgs - removes any orphaned
        # tool_result blocks that may have been left by a previous trimmed turn.
        msgs = self._sanitise_history(self.history) + [{"role": "user", "content": self.text}]
        while True:
            self.bubble.emit("Thinking and planning response", "thinking", "thinking_stream")
            # Sanitise before every API call to handle multi-round tool loops
            msgs = self._sanitise_history(msgs)
            # Hard guard: if first message is purely tool_results with no prior assistant, drop it
            if msgs and isinstance(msgs[0].get("content"), list):
                all_tr = all(
                    isinstance(b, dict) and b.get("type") == "tool_result"
                    for b in msgs[0]["content"]
                )
                if all_tr:
                    msgs.pop(0)
            if not msgs:
                break
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
                        self._perf["fallback_used"] = True
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
                    self._perf["response_chars"] += len(b.text)
                    if _SAVE and self.save:
                        _save_msg(self.session_id, "assistant", b.text)
            tus = [b for b in resp.content if b.type == "tool_use"]
            if not tus or resp.stop_reason == "end_turn":
                break
            results = []
            for tu in tus:
                self.orb.emit("thinking")
                self._perf["tool_calls"] += 1
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
                if result_str.lower().startswith("error"):
                    self._perf["tool_errors"] += 1
                if SHOW_BACKEND_DETAILS:
                    self.bubble.emit(f"   ↳ {result_str[:200]}" + ("..." if len(result_str) > 200 else ""), "tool_result", "tool_result")
                elif result_str.lower().startswith("error"):
                    self.bubble.emit("Thinking step failed and recovered", "thinking", "thinking_stream")
                results.append({"type": "tool_result", "tool_use_id": tu.id, "content": result_str})
            msgs.append({"role": "user", "content": results})
        self._perf["model_used"] = active_model
        # Write back to shared history - sanitise first, then trim safely from front
        self.history.clear()
        self.history.extend(self._sanitise_history(msgs))
        # Trim: drop oldest messages from front without splitting tool-exchange pairs
        while len(self.history) > 40:
            drop_to = 1
            for i, m in enumerate(self.history[1:], 1):
                if m.get("role") == "user":
                    drop_to = i + 1
                    break
            self.history[:] = self.history[drop_to:]
        # Final sanitise after trim to catch any newly exposed orphans
        self.history[:] = self._sanitise_history(self.history)
    def _ollama(self):
        ok, err = check_ollama(self.model)
        if not ok:
            self.bubble.emit(err, "error", "error")
            return
        self._perf["model_used"] = self.model  # set once; stays even if no tool calls
        if _SAVE and self.save:
            _save_msg(self.session_id, "user", self.text)
        current_system = get_startup_system(session_id=self.session_id, query_context=self.text)
        all_msgs = (
            [{"role": "system", "content": current_system}]
            + self.history
            + [{"role": "user", "content": self.text}]
        )
        ollama_tools = to_ollama_tools(TOOLS)
        while True:
            self.bubble.emit("Generating response", "thinking", "thinking_stream")
            data = json.dumps({
                "model": self.model,
                "messages": all_msgs,
                "tools": ollama_tools,
                "stream": True,
                "keep_alive": "10m",
                "options": {"temperature": 1.0, "top_p": 0.95, "top_k": 40, "num_predict": 512},
            }).encode()
            req = urllib.request.Request(
                "http://localhost:11434/api/chat",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            full_content = ""
            final_message = {}
            with urllib.request.urlopen(req, timeout=120) as r:
                for raw_line in r:
                    line = raw_line.decode("utf-8").strip()
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    delta = chunk.get("message", {}).get("content") or ""
                    if delta:
                        full_content += delta
                        self.bubble.emit(delta, "guppy", "guppy_stream")
                    if chunk.get("done"):
                        final_message = chunk.get("message", {})
                        break
            msg = {**final_message, "content": full_content}
            all_msgs.append(msg)
            reply_text = full_content.strip()
            if reply_text:
                self._perf["response_chars"] += len(reply_text)
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
                self.orb.emit("thinking")
                self._perf["tool_calls"] += 1
                name = tc["function"]["name"]
                args = tc["function"]["arguments"]
                preview = ", ".join(f"{k}={repr(v)[:30]}" for k, v in args.items())
                if SHOW_BACKEND_DETAILS:
                    self.bubble.emit(f"⚙️  {name}({preview})", "tool", "tool")
                else:
                    key_arg = next(iter(args.values()), "") if args else ""
                    hint = f" → {str(key_arg)[:40]}" if key_arg else ""
                    self.bubble.emit(f"{name}{hint}", "thinking", "thinking_stream")
                result = run_tool(name, args)
                result_str = (
                    f"Screenshot saved: {result['path']} ({result['size']})"
                    if isinstance(result, dict) and result.get("_screenshot")
                    else str(result)
                )
                if result_str.lower().startswith("error"):
                    self._perf["tool_errors"] += 1
                if SHOW_BACKEND_DETAILS:
                    self.bubble.emit(f"   ↳ {result_str[:200]}" + ("..." if len(result_str) > 200 else ""), "tool_result", "tool_result")
                elif result_str.lower().startswith("error"):
                    self.bubble.emit(f"{name} failed, retrying", "thinking", "thinking_stream")
                else:
                    snippet = result_str[:60].replace("\n", " ")
                    self.bubble.emit(f"got result: {snippet}{'…' if len(result_str) > 60 else ''}", "thinking", "thinking_stream")
                all_msgs.append({"role": "tool", "content": result_str})
                
                # -- Memory optimization: trim conversation history during tool loops --
                if len(all_msgs) > 60:
                    # Keep system message, recent user message, and current assistant response
                    system_msg = all_msgs[0] if all_msgs and all_msgs[0].get("role") == "system" else None
                    user_msgs = [m for m in all_msgs[-10:] if m.get("role") == "user"]
                    recent_assistant = [m for m in all_msgs[-5:] if m.get("role") == "assistant"]
                    all_msgs[:] = ([system_msg] if system_msg else []) + user_msgs[-1:] + recent_assistant[-2:]
                self._perf["model_used"] = self.model


# ── Orb ────────────────────────────────────────────────────────────────────────

class Orb(QWidget):
    COLORS = {
        "idle":      QColor(20,  80,  200, 150),
        "thinking":  QColor(240, 160, 0,   200),
        "speaking":  QColor(255, 255, 255, 220),
        "listening": QColor(0,   200, 255, 220),
        "wake":      QColor(0,   180, 130, 100),  # dim teal — ambient wake listening
    }
    LABELS = {
        "idle": "IDLE", "thinking": "THINKING",
        "speaking": "SPEAKING", "listening": "LISTENING",
        "wake": "WAKE",
    }

    def __init__(self):
        super().__init__()
        self.setMinimumSize(SHARED.orb_min_size, SHARED.orb_min_size)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.state = "idle"
        self.p     = 0.0
        self.rings = []
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(16)

    def set_state(self, s: str):
        self.state = s
        if s in ("listening", "speaking"):
            self.rings = []

    def _tick(self):
        self.p += 0.016
        if self.state in ("listening", "speaking", "wake"):
            if self.state == "wake":
                spd, gap = 0.006, 0.55   # very slow, wide gap — ambient pulse
            elif self.state == "listening":
                spd, gap = 0.018, 0.20
            else:
                spd, gap = 0.030, 0.10
            if not self.rings or self.rings[-1] > gap:
                self.rings.append(0.0)
            self.rings = [r + spd for r in self.rings if r < 1.0]
        self.update()

    def paintEvent(self, _):
        p   = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c   = self.rect().center()
        r   = min(self.width(), self.height()) * 0.28
        col = self.COLORS.get(self.state, self.COLORS["idle"])

        # Ambient glow
        g  = QRadialGradient(c, r * 2.4)
        gc = QColor(col)
        gc.setAlphaF(0.07 * (0.7 + 0.3 * math.sin(self.p * 1.8)))
        g.setColorAt(0, gc)
        g.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(g))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(c, r * 2.4, r * 2.4)

        # Ripple rings
        for ring in self.rings:
            rr = r + ring * r * 2.8
            rc = QColor(col)
            rc.setAlpha(int(200 * (1 - ring)))
            p.setPen(QPen(rc, 1.5 * (1 - ring * 0.6)))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(c, rr, rr)

        # Thinking arcs
        if self.state == "thinking":
            p.save()
            p.translate(c)
            ar = r * 1.55
            for i in range(3):
                ac = QColor(col)
                ac.setAlpha(160)
                p.setPen(QPen(ac, 2.5))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawArc(
                    QRectF(-ar, -ar, ar * 2, ar * 2),
                    int((self.p * 5729 + i * 120) * 16),
                    int(80 * 16),
                )
            p.restore()

        # Core orb
        cp = 0.85 + 0.15 * math.sin(self.p * 2.2)
        if self.state == "speaking":
            cp = 0.8 + 0.2 * math.sin(self.p * 9)
        cr = r * cp
        cg = QRadialGradient(c.x() - cr * 0.3, c.y() - cr * 0.3, cr * 1.3)
        cc = QColor(col); cc.setAlphaF(0.95)
        ec = QColor(col); ec.setAlphaF(0.15)
        cg.setColorAt(0, cc)
        cg.setColorAt(0.6, ec)
        cg.setColorAt(1, QColor(7, 7, 15))
        p.setBrush(QBrush(cg))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(c, cr, cr)

        # State label
        lc = QColor(col)
        lc.setAlphaF(0.5)
        p.setPen(QPen(lc))
        f = QFont(SHARED.font_family, 7)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.5)
        p.setFont(f)
        p.drawText(
            QRectF(0, c.y() + r * 1.5, self.width(), 18),
            Qt.AlignmentFlag.AlignHCenter,
            self.LABELS.get(self.state, ""),
        )


# ── Main window ────────────────────────────────────────────────────────────────

class GuppyWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Guppy")
        self.resize(1050, 720)
        self.setMinimumSize(800, 550)
        self.history     = []
        self._worker     = None
        self._voice      = None
        self._api_key    = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        self._claude_model = (os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6").strip() or "claude-sonnet-4-6")
        self._claude_backup_model = os.environ.get("ANTHROPIC_BACKUP_MODEL", "claude-haiku-4-5-20251001").strip()
        self._claude_tier = "haiku" if "haiku" in self._claude_model.lower() else "sonnet"
        self._sync_claude_models()
        self._mode       = "auto"
        self._session_id = _dt.now().strftime("%Y%m%d_%H%M%S") if _SAVE else ""
        self._system     = get_startup_system()
        self._think_label = None
        self._stream_label = None
        self._last_persona_reply = ""
        self._tts_generation = 0
        self._status_lbl = None
        self._status_strip = None
        self._timeline = None
        self._startup_checklist = None
        self._lat_spark = None
        self._queue_spark = None
        self._lat_points = []
        self._queue_points = []
        self._last_timeline_key = ""
        self.setStyleSheet(
            f"background:{T.bg}; color:{T.text}; font-family:'{SHARED.font_family}';"
        )
        self._build()
        self._setup_voice()
        self._start_daemon()
        self._greet()
        self._check_api_key()
        self._startup_self_check()
        if _HB_OK: _start_hb('guppy')
        self._log_event("ui_started", mode=self._mode)
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(
            lambda: open_debug_console(self)
        )
        QShortcut(QKeySequence("Ctrl+K"), self).activated.connect(self._open_command_palette)
        self._ui_tick = QTimer(self)
        self._ui_tick.timeout.connect(self._refresh_telemetry_panels)
        self._ui_tick.start(1800)

    # ── Layout ─────────────────────────────────────────────────────────────────

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._build_sidebar())
        lay.addWidget(self._build_chat_pane())

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(SHARED.sidebar_width)
        sidebar.setStyleSheet(
            f"background:{T.bg2}; border-right:1px solid {T.border};"
        )
        ll = QVBoxLayout(sidebar)
        ll.setContentsMargins(0, 0, 0, 16)
        ll.setSpacing(0)

        # ── Gradient header ────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(82)
        header.setStyleSheet(
            f"background: qlineargradient("
            f"x1:0, y1:0, x2:0, y2:1, "
            f"stop:0 {T.accent}33, stop:0.6 {T.accent}11, stop:1 {T.bg2});"
            f"border-bottom: 2px solid {T.accent}44;"
        )
        hl = QVBoxLayout(header)
        hl.setContentsMargins(0, 14, 0, 10)
        hl.setSpacing(3)

        title = QLabel("GUPPY")
        tf = QFont(FF_MONO, FS_TITLE, QFont.Weight.Bold)
        tf.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 8)
        title.setFont(tf)
        title.setStyleSheet(f"color:{T.accent}; background:transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        sub = QLabel("▸  CHIEF OF STAFF  ◂")
        sf = QFont(FF_MONO, FS_TS)
        sf.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
        sub.setFont(sf)
        sub.setStyleSheet(f"color:{T.accent}77; background:transparent;")
        sub.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        hl.addWidget(title)
        hl.addWidget(sub)
        ll.addWidget(header)

        # ── Orb ────────────────────────────────────────────────────────────
        self.orb = Orb()
        ll.addWidget(self.orb, stretch=1)

        # ── Mode button ────────────────────────────────────────────────────
        self.mode_btn = QPushButton()
        self.mode_btn.setFixedHeight(CH_MD)
        self.mode_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mode_btn.clicked.connect(self._toggle_mode)
        self._update_mode_btn()
        ll.addWidget(self.mode_btn)
        self.claude_tier_btn = QPushButton()
        self.claude_tier_btn.setFixedHeight(CH_SM)
        self.claude_tier_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.claude_tier_btn.clicked.connect(self._toggle_claude_tier)
        self._update_claude_tier_btn()
        ll.addWidget(self.claude_tier_btn)
        ll.addSpacing(8)

        # ── PTT button ─────────────────────────────────────────────────────
        ptt = QPushButton("⬤  HOLD TO TALK")
        ptt.setFixedHeight(CH_LG + 4)
        ptt.setCursor(Qt.CursorShape.PointingHandCursor)
        ptt.setStyleSheet(
            f"QPushButton{{background:{T.bg3};color:{T.accent};"
            f"border:2px solid {T.accent}66;border-radius:6px;"
            f"font-family:{FF_MONO};font-size:{FS_BODY - 1}px;font-weight:bold;"
            f"letter-spacing:2px;margin:0 12px;}}"
            f"QPushButton:hover{{border-color:{T.accent};background:{T.accent}11;"
            f"color:{T.accent};}}"
            f"QPushButton:pressed{{background:{T.accent};color:{T.bg};"
            f"border-color:{T.accent};}}"
        )
        ptt.pressed.connect(self._ptt_start)
        ptt.released.connect(self._ptt_stop)
        ll.addWidget(ptt)
        ll.addSpacing(4)

        # ── Quiet mode toggle ──────────────────────────────────────────────
        self._quiet_btn = QPushButton("🔊  VOICE ON")
        self._quiet_btn.setFixedHeight(CH_SM + 2)
        self._quiet_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._quiet_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{T.dim};"
            f"border:1px solid {T.border};border-radius:4px;"
            f"font-family:{FF_MONO};font-size:{FS_SMALL}px;margin:0 12px;}}"
            f"QPushButton:hover{{color:{T.text};border-color:{T.accent}55;"
            f"background:{T.accent}0a;}}"
            f"QPushButton:pressed{{background:{T.accent}1a;}}"
        )
        self._quiet_btn.clicked.connect(self._toggle_quiet)
        ll.addWidget(self._quiet_btn)
        ll.addSpacing(4)

        # ── Wake word toggle ───────────────────────────────────────────────
        self._wake_btn = QPushButton("◎  WAKE WORD OFF")
        self._wake_btn.setFixedHeight(CH_SM + 2)
        self._wake_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._wake_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{T.dim};"
            f"border:1px solid {T.border};border-radius:4px;"
            f"font-family:{FF_MONO};font-size:{FS_SMALL}px;margin:0 12px;}}"
            f"QPushButton:hover{{color:{T.text};border-color:#00b48255;"
            f"background:#00b4820a;}}"
            f"QPushButton:pressed{{background:#00b48222;}}"
        )
        self._wake_btn.clicked.connect(self._toggle_wake_word)
        ll.addWidget(self._wake_btn)
        self._status_lbl = QLabel()
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setStyleSheet(
            f"color:{T.dim}; background:transparent; font-family:{FF_MONO};"
            f"font-size:{FS_LABEL}px; margin:2px 12px 0 12px;"
        )
        ll.addWidget(self._status_lbl)
        self._refresh_runtime_status_label()
        ll.addSpacing(10)

        # ── Section label ──────────────────────────────────────────────────
        sec = QLabel("QUICK ACCESS")
        sec.setFixedHeight(16)
        sec.setStyleSheet(
            f"color:{T.dim}; background:transparent; font-family:{FF_MONO};"
            f"font-size:{FS_LABEL}px; letter-spacing:2px; margin:0 12px;"
        )
        ll.addWidget(sec)
        ll.addSpacing(4)

        # ── Quick actions ──────────────────────────────────────────────────
        for label, action in [
            ("📧  GMAIL",        lambda: self._quick("Open Gmail inbox")),
            ("📚  KINDLE",       lambda: self._quick("Open Kindle")),
            ("📋  CALL REPORT",  lambda: self._quick("I need to create a call report")),
            ("📦  ORDER NOTE",   lambda: self._quick("I need to create an order note")),
        ]:
            b = QPushButton(label)
            b.setFixedHeight(CH_MD)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton{{background:transparent;color:{T.dim};"
                f"border:1px solid {T.border};border-left:3px solid transparent;"
                f"border-radius:4px;font-family:{FF_MONO};font-size:{FS_BODY - 1}px;"
                f"margin:0 12px 4px 12px;text-align:left;padding-left:10px;}}"
                f"QPushButton:hover{{color:{T.text};background:{T.accent}0d;"
                f"border-color:{T.accent}44;border-left-color:{T.accent};}}"
                f"QPushButton:pressed{{background:{T.accent}22;"
                f"border-left-color:{T.accent};}}"
            )
            b.clicked.connect(action)
            ll.addWidget(b)

        ll.addSpacing(8)

        clr = QPushButton("⟳  CLEAR SESSION")
        clr.setFixedHeight(CH_SM)
        clr.setCursor(Qt.CursorShape.PointingHandCursor)
        clr.setStyleSheet(
            f"QPushButton{{background:transparent;color:{T.dim};"
            f"border:1px solid {T.border};border-radius:4px;"
            f"font-family:{FF_MONO};font-size:{FS_SMALL}px;margin:0 12px;letter-spacing:1px;}}"
            f"QPushButton:hover{{color:#ff6644;border-color:#ff664455;}}"
            f"QPushButton:pressed{{background:#ff664411;}}"
        )
        clr.clicked.connect(self._clear)
        ll.addWidget(clr)

        diag = QPushButton("⛭  DIAGNOSTICS")
        diag.setFixedHeight(CH_SM)
        diag.setCursor(Qt.CursorShape.PointingHandCursor)
        diag.setStyleSheet(
            f"QPushButton{{background:transparent;color:{T.dim};"
            f"border:1px solid {T.border};border-radius:4px;"
            f"font-family:{FF_MONO};font-size:{FS_SMALL}px;margin:6px 12px 0 12px;letter-spacing:1px;}}"
            f"QPushButton:hover{{color:{T.text};border-color:{T.accent}55;background:{T.accent}10;}}"
            f"QPushButton:pressed{{background:{T.accent}20;}}"
        )
        diag.clicked.connect(self._collect_diagnostics)
        ll.addWidget(diag)

        palette_btn = QPushButton("⌘  COMMANDS")
        palette_btn.setFixedHeight(CH_SM)
        palette_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        palette_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{T.dim};"
            f"border:1px solid {T.border};border-radius:4px;"
            f"font-family:{FF_MONO};font-size:{FS_SMALL}px;margin:4px 12px 0 12px;letter-spacing:1px;}}"
            f"QPushButton:hover{{color:{T.text};border-color:{T.accent}55;background:{T.accent}10;}}"
            f"QPushButton:pressed{{background:{T.accent}20;}}"
        )
        palette_btn.clicked.connect(self._open_command_palette)
        ll.addWidget(palette_btn)

        return sidebar

    def _build_chat_pane(self) -> QWidget:
        pane = QWidget()
        rl = QVBoxLayout(pane)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        # Telemetry/status strip
        telem_wrap = QWidget()
        twl = QVBoxLayout(telem_wrap)
        twl.setContentsMargins(8, 8, 8, 6)
        twl.setSpacing(6)

        self._status_strip = StatusStrip(accent=T.accent)
        twl.addWidget(self._status_strip)

        mini = QHBoxLayout()
        mini.setSpacing(6)
        self._startup_checklist = StartupChecklist(parent=self)
        self._startup_checklist.setMaximumWidth(220)
        mini.addWidget(self._startup_checklist)

        trend_wrap = QFrame()
        trend_wrap.setStyleSheet(f"QFrame{{background:{T.bg2};border:1px solid {T.border};border-radius:6px;}}")
        trl = QVBoxLayout(trend_wrap)
        trl.setContentsMargins(8, 6, 8, 6)
        trl.setSpacing(4)
        lat_lbl = QLabel("LATENCY TREND")
        lat_lbl.setStyleSheet(f"color:{T.dim};background:transparent;font-family:{FF_MONO};font-size:{FS_LABEL}px;")
        trl.addWidget(lat_lbl)
        self._lat_spark = Sparkline(color="#7fb0ff")
        trl.addWidget(self._lat_spark)
        q_lbl = QLabel("QUEUE TREND")
        q_lbl.setStyleSheet(f"color:{T.dim};background:transparent;font-family:{FF_MONO};font-size:{FS_LABEL}px;")
        trl.addWidget(q_lbl)
        self._queue_spark = Sparkline(color="#d9a94f")
        trl.addWidget(self._queue_spark)
        mini.addWidget(trend_wrap)

        self._timeline = TimelinePanel("RECENT EVENTS", self)
        self._timeline.setMaximumHeight(120)
        mini.addWidget(self._timeline, stretch=1)
        twl.addLayout(mini)
        rl.addWidget(telem_wrap)

        # ── Scroll area ────────────────────────────────────────────────────
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(
            f"QScrollArea{{background:{T.bg};border:none;}}"
            f"QScrollBar:vertical{{background:{T.bg};width:3px;}}"
            f"QScrollBar::handle:vertical{{background:{T.border};border-radius:1px;}}"
            f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}"
        )
        self.chat_box = QWidget()
        self.chat_box.setStyleSheet(f"background:{T.bg};")
        self.chat_lay = QVBoxLayout(self.chat_box)
        self.chat_lay.setContentsMargins(16, 16, 16, 8)
        self.chat_lay.setSpacing(8)
        self.chat_lay.addStretch()
        self.scroll.setWidget(self.chat_box)
        rl.addWidget(self.scroll)

        # ── Input bar ──────────────────────────────────────────────────────
        bar = QWidget()
        bar.setFixedHeight(66)
        bar.setStyleSheet(
            f"background:{T.bg2}; border-top:2px solid {T.accent}33;"
        )
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(14, 12, 14, 12)
        bl.setSpacing(8)

        self.inp = QLineEdit()
        self.inp.setPlaceholderText("Transmit to Guppy, sir...")
        self.inp.setStyleSheet(
            f"QLineEdit{{background:{T.bg3};color:{T.text};"
            f"border:1px solid {T.border};border-radius:6px;"
            f"padding:0 14px;font-family:'{SHARED.font_family}';"
            f"font-size:{SHARED.font_size}pt;}}"
            f"QLineEdit:focus{{border-color:{T.accent}55;"
            f"background:{T.bg3};}}"
        )
        self.inp.returnPressed.connect(self._send)
        self.inp.textEdited.connect(self._on_user_typing)

        send = QPushButton("▶")
        send.setFixedSize(42, 42)
        send.setCursor(Qt.CursorShape.PointingHandCursor)
        send.setStyleSheet(
            f"QPushButton{{background:{T.bg3};color:{T.accent};"
            f"border:2px solid {T.accent}55;border-radius:6px;"
            f"font-size:{FS_BODY + 3}pt;font-weight:bold;}}"
            f"QPushButton:hover{{background:{T.accent}22;"
            f"border-color:{T.accent};color:{T.accent};}}"
            f"QPushButton:pressed{{background:{T.accent};color:{T.bg};"
            f"border-color:{T.accent};}}"
        )
        send.clicked.connect(self._send)

        bl.addWidget(self.inp)
        bl.addWidget(send)
        rl.addWidget(bar)

        return pane

    # ── Mode ───────────────────────────────────────────────────────────────────

    def _update_mode_btn(self):
        if self._mode == "claude":
            self.mode_btn.setText("◉  CLAUDE  ONLINE")
            self.mode_btn.setStyleSheet(
                f"QPushButton{{background:{T.bg3};color:{T.accent};"
                f"border:1px solid {T.accent}66;border-radius:4px;"
                f"font-family:{FF_MONO};font-size:{FS_SMALL}px;letter-spacing:2px;"
                f"margin:0 12px;font-weight:bold;}}"
                f"QPushButton:hover{{border-color:{T.accent};"
                f"background:{T.accent}11;}}"
            )
        elif self._mode == "auto":
            self.mode_btn.setText("◉  AUTO  ROUTE")
            self.mode_btn.setStyleSheet(
                f"QPushButton{{background:#0f1a2b;color:#8bc2ff;"
                f"border:1px solid #8bc2ff77;border-radius:4px;"
                f"font-family:{FF_MONO};font-size:{FS_SMALL}px;letter-spacing:2px;"
                f"margin:0 12px;font-weight:bold;}}"
                f"QPushButton:hover{{border-color:#8bc2ff;background:#8bc2ff12;}}"
            )
        else:
            self.mode_btn.setText("◉  LOCAL MODEL")
            self.mode_btn.setStyleSheet(
                f"QPushButton{{background:#001a0a;color:#00ff88;"
                f"border:1px solid #00ff8866;border-radius:4px;"
                f"font-family:{FF_MONO};font-size:{FS_SMALL}px;letter-spacing:2px;"
                f"margin:0 12px;font-weight:bold;}}"
                f"QPushButton:hover{{border-color:#00ff88;background:#00ff8811;}}"
            )

    def _sync_claude_models(self):
        """Keep primary/backup Claude model pairing aligned to selected tier."""
        if self._claude_tier == "haiku":
            self._claude_model = "claude-haiku-4-5-20251001"
            self._claude_backup_model = "claude-sonnet-4-6"
        else:
            self._claude_model = "claude-sonnet-4-6"
            self._claude_backup_model = "claude-haiku-4-5-20251001"

    def _update_claude_tier_btn(self):
        tier = "HAIKU" if self._claude_tier == "haiku" else "SONNET"
        if self._claude_tier == "haiku":
            self.claude_tier_btn.setText(f"◌  CLAUDE  {tier}  (CHEAPER)")
            self.claude_tier_btn.setStyleSheet(
                f"QPushButton{{background:#2b1f0f;color:#ffcc88;"
                f"border:1px solid #ffcc8866;border-radius:4px;"
                f"font-family:{FF_MONO};font-size:{FS_SMALL}px;letter-spacing:1px;"
                f"margin:0 12px;font-weight:bold;}}"
                f"QPushButton:hover{{border-color:#ffcc88;background:#ffcc8811;}}"
            )
        else:
            self.claude_tier_btn.setText(f"◌  CLAUDE  {tier}  (STRONGER)")
            self.claude_tier_btn.setStyleSheet(
                f"QPushButton{{background:{T.bg3};color:{T.text};"
                f"border:1px solid {T.border}99;border-radius:4px;"
                f"font-family:{FF_MONO};font-size:{FS_SMALL}px;letter-spacing:1px;"
                f"margin:0 12px;font-weight:bold;}}"
                f"QPushButton:hover{{border-color:{T.accent}88;background:{T.accent}11;}}"
            )

    def _toggle_claude_tier(self):
        if not self._api_key:
            self._bubble("No API key set for Claude model switching, sir.", "error", "error")
            return
        self._claude_tier = "haiku" if self._claude_tier == "sonnet" else "sonnet"
        self._sync_claude_models()
        self._update_claude_tier_btn()
        self._bubble(
            f"Claude tier set to {'Haiku' if self._claude_tier == 'haiku' else 'Sonnet'}.",
            "guppy", "guppy",
        )
        self._log_event("claude_tier_changed", tier=self._claude_tier)

    def _toggle_mode(self):
        cloud_ready = bool(self._api_key and is_online())
        order = ["ollama", "auto", "claude"]
        idx = order.index(self._mode) if self._mode in order else 0
        for step in range(1, len(order) + 1):
            candidate = order[(idx + step) % len(order)]
            if candidate == "claude" and not cloud_ready:
                continue
            self._mode = candidate
            break
        self._update_mode_btn()
        mode_desc = {
            "ollama": "Local model",
            "auto": "Auto route (local-first)",
            "claude": "Claude " + ("Haiku" if self._claude_tier == "haiku" else "Sonnet"),
        }
        self._bubble(
            f"Switched to {mode_desc.get(self._mode, 'Local model')}.",
            "guppy", "guppy",
        )
        self._log_event("mode_changed", mode=self._mode)
        self._refresh_runtime_status_label()

    # ── Voice ──────────────────────────────────────────────────────────────────

    def _log_event(self, event: str, level: str = "info", **fields):
        _log_session_event("ui", event, level=level, session_id=self._session_id, **fields)

    def _voice_status_payload(self) -> dict:
        if not self._voice:
            return {
                "tts_backend": "none",
                "stt_backend": "none",
                "wake_backend": "idle",
                "quiet_mode": False,
            }
        if hasattr(self._voice, "backend_status"):
            try:
                return self._voice.backend_status()
            except Exception:
                pass
        return {
            "tts_backend": "unknown",
            "stt_backend": "unknown",
            "wake_backend": "unknown",
            "quiet_mode": False,
        }

    def _refresh_runtime_status_label(self):
        if not self._status_lbl:
            return
        st = self._voice_status_payload()
        readiness = self._startup_self_check(emit=False)
        auth_state = readiness.get("auth", "MISSING")
        ollama_state = readiness.get("ollama", "MISSING")
        voice_state = readiness.get("voice", "MISSING")
        self._status_lbl.setText(
            f"MODE {self._mode.upper()}  |  STT {str(st.get('stt_backend', 'none')).upper()}  |  "
            f"TTS {str(st.get('tts_backend', 'none')).upper()}\n"
            f"AUTH {auth_state}  |  OLLAMA {ollama_state}  |  VOICE {voice_state}"
        )
        if self._status_strip:
            snap = rolling_agent_snapshot("guppy", window_seconds=900)
            qd = int(snap.get("queue_depth", 0) or 0)
            p95 = float(snap.get("p95_ms", 0.0) or 0.0)
            p99 = float(snap.get("p99_ms", 0.0) or 0.0)
            self._status_strip.set_summary(self._mode, auth_state, ollama_state, voice_state)
            self._status_strip.set_latency(p95, p99, qd)
            self._status_strip.set_voice_detail(
                str(st.get("tts_backend", "none")),
                os.environ.get("GUPPY_TTS_VOICE", "-"),
            )
            incidents = []
            if auth_state != "READY":
                incidents.append({"text": "AUTH", "severity": "warn" if auth_state == "PARTIAL" else "error"})
            if ollama_state != "READY":
                incidents.append({"text": "OLLAMA", "severity": "error"})
            if voice_state != "READY":
                incidents.append({"text": "VOICE", "severity": "warn"})
            if qd > 0:
                incidents.append({"text": f"QUEUE {qd}", "severity": "warn"})
            if p95 >= 5000:
                incidents.append({"text": "HIGH LAT", "severity": "error"})
            elif p95 >= 2500:
                incidents.append({"text": "LATENCY", "severity": "warn"})
            self._status_strip.set_incidents(incidents)
        if self._startup_checklist:
            self._startup_checklist.set_checks(readiness)

    def _refresh_telemetry_panels(self):
        self._refresh_runtime_status_label()
        snap = rolling_agent_snapshot("guppy", window_seconds=900)
        lat = snap.get("latencies", [])
        qd = int(snap.get("queue_depth", 0) or 0)
        if isinstance(lat, list) and lat:
            self._lat_points = [float(v) for v in lat if isinstance(v, (int, float))][-60:]
        if self._lat_spark:
            self._lat_spark.set_values(self._lat_points)
        self._queue_points.append(qd)
        self._queue_points = self._queue_points[-60:]
        if self._queue_spark:
            self._queue_spark.set_values(self._queue_points)

        if self._timeline:
            events = recent_agent_events("guppy", limit=6)
            if events:
                last = events[-1]
                key = f"{last.get('ts','')}|{last.get('event','')}|{last.get('request_id','')}"
                if key != self._last_timeline_key:
                    self._last_timeline_key = key
                    ts = str(last.get("ts", ""))[11:19] or "--:--:--"
                    evt = str(last.get("event", "event"))
                    mode = str(last.get("mode", ""))
                    self._timeline.add_event(ts, f"{evt} {mode}".strip())

    def _open_command_palette(self):
        commands = [
            {"name": "Toggle Mode", "action": self._toggle_mode},
            {"name": "Toggle Claude Tier", "action": self._toggle_claude_tier},
            {"name": "Hold To Talk", "action": self._ptt_start},
            {"name": "Toggle Quiet", "action": self._toggle_quiet},
            {"name": "Toggle Wake Word", "action": self._toggle_wake_word},
            {"name": "Open Gmail", "action": lambda: self._quick("Open Gmail inbox")},
            {"name": "Open Kindle", "action": lambda: self._quick("Open Kindle")},
            {"name": "Create Call Report", "action": lambda: self._quick("I need to create a call report")},
            {"name": "Create Order Note", "action": lambda: self._quick("I need to create an order note")},
            {"name": "Collect Diagnostics", "action": self._collect_diagnostics},
            {"name": "Clear Session", "action": self._clear},
        ]
        dlg = CommandPaletteDialog(commands, self)
        dlg.exec()

    def _collect_diagnostics(self):
        path = create_diagnostics_bundle("guppy")
        self._bubble(f"Diagnostics bundle created: {path}", "guppy", "tool_result")
        self._log_event("diagnostics_bundle_created", path=str(path))
        if self._timeline:
            self._timeline.add_event(now_str(), "diagnostics bundle created")

    def _startup_self_check(self, emit: bool = True) -> dict:
        readiness = {}
        readiness["auth"] = "READY" if (self._api_key and self._api_key.startswith("sk-ant-")) else ("PARTIAL" if self._api_key else "MISSING")

        ok, _err = check_ollama("guppy")
        readiness["ollama"] = "READY" if ok else "MISSING"

        st = self._voice_status_payload()
        stt = str(st.get("stt_backend", "none"))
        tts = str(st.get("tts_backend", "none"))
        readiness["voice"] = "READY" if stt != "none" and tts != "none" else ("PARTIAL" if stt != "none" or tts != "none" else "MISSING")

        if emit:
            self._log_event("startup_check", **readiness)
            if "MISSING" in readiness.values():
                self._bubble(
                    f"Startup check: AUTH {readiness['auth']}, OLLAMA {readiness['ollama']}, VOICE {readiness['voice']}.",
                    "error",
                    "error",
                )
        return readiness

    def _setup_voice(self):
        try:
            sys.path.insert(0, str(Path(__file__).parent))
            from guppy_voice import GuppyVoice, VoiceConfig
            self._voice = GuppyVoice(VoiceConfig(
                tts_voice=os.environ.get("GUPPY_TTS_VOICE", "bm_lewis"),
                tts_rate=os.environ.get("GUPPY_TTS_RATE", "+28%"),
                tts_pitch=os.environ.get("GUPPY_TTS_PITCH", "+12Hz"),
                stt_fallback="whisper",
                noise_reduction=True,
                min_silence_threshold=150,
                min_duration=0.3,
                max_duration=45.0,
            ))
            st = self._voice_status_payload()
            self._log_event("voice_ready", stt_backend=st.get("stt_backend"), tts_backend=st.get("tts_backend"))
            if bool(st.get("tts_fallback_active")):
                self._bubble(
                    "Voice note: using Windows SAPI fallback (robotic). Install/enable Kokoro for natural voice.",
                    "error",
                    "error",
                )
                self._log_event("voice_tts_fallback", level="warning", tts_backend=st.get("tts_backend"))
        except Exception:
            self._voice = None
            self._log_event("voice_unavailable", level="warning")
        self._refresh_runtime_status_label()

    def _ptt_start(self):
        if not self._voice:
            self._bubble("Voice subsystem unavailable; PTT cannot start.", "error", "error")
            self._log_event("ptt_unavailable", level="error")
            return
        if getattr(self, "_ptt_in_progress", False):
            return  # ignore duplicate press while already recording
        st = self._voice_status_payload()
        if str(st.get("stt_backend", "none")) == "none":
            self._bubble("No speech-to-text backend detected; PTT unavailable.", "error", "error")
            self._log_event("ptt_no_stt_backend", level="error")
            return
        self._ptt_in_progress = True
        self.orb.set_state("listening")
        self._log_event("ptt_started")
        def _listen():
            try:
                res = self._voice.listen_once()
                if res is None:
                    QTimer.singleShot(0, lambda: self.orb.set_state("idle"))
                    return
                if res.get("error"):
                    QTimer.singleShot(0, lambda: self._bubble(
                        f"Voice error: {res.get('error')}", "error", "error",
                    ))
                    self._log_event("ptt_error", level="error", error=str(res.get("error") or ""))
                    QTimer.singleShot(0, lambda: self.orb.set_state("idle"))
                elif res.get("text"):
                    self._log_event("ptt_transcribed", chars=len(str(res.get("text") or "")))
                    QTimer.singleShot(0, lambda: self._send_text(res.get("text")))
                else:
                    self._log_event("ptt_no_text", level="warning")
                    QTimer.singleShot(0, lambda: self.orb.set_state("idle"))
            finally:
                self._ptt_in_progress = False
        threading.Thread(target=_listen, daemon=True).start()

    def _ptt_stop(self):
        if self._voice:
            self._voice.stop_listening()

    def _toggle_wake_word(self):
        if not self._voice:
            return
        if self._voice.is_listening_for_wake_word:
            self._voice.stop_wake_word_detection()
            self.orb.set_state("idle")
            self._wake_btn.setText("◎  WAKE WORD OFF")
            self._wake_btn.setStyleSheet(
                f"QPushButton{{background:transparent;color:{T.dim};"
                f"border:1px solid {T.border};border-radius:4px;"
                f"font-family:{FF_MONO};font-size:{FS_SMALL}px;margin:0 12px;}}"
                f"QPushButton:hover{{color:{T.text};border-color:#00b48255;"
                f"background:#00b4820a;}}"
                f"QPushButton:pressed{{background:#00b48222;}}"
            )
            self._log_event("wake_word_disabled")
        else:
            self._voice.start_wake_word_detection(callback_function=self._on_wake_word)
            self.orb.set_state("wake")
            self._wake_btn.setText("◎  WAKE WORD ON")
            self._wake_btn.setStyleSheet(
                f"QPushButton{{background:#001a14;color:#00e6aa;"
                f"border:1px solid #00b48299;border-radius:4px;"
                f"font-family:{FF_MONO};font-size:{FS_SMALL}px;margin:0 12px;}}"
                f"QPushButton:hover{{border-color:#00b482;background:#00b48215;}}"
                f"QPushButton:pressed{{background:#00b48230;}}"
            )
            self._log_event("wake_word_enabled")
        self._refresh_runtime_status_label()

    def _on_wake_word(self, phrase: str):
        """Called from background thread — bounces to Qt thread."""
        QTimer.singleShot(0, self._trigger_wake_listen)

    def _trigger_wake_listen(self):
        """Qt thread: start a listen session immediately after wake word fires."""
        if not self._voice or (self._worker and self._worker.isRunning()):
            return
        self.orb.set_state("listening")
        def _listen():
            res = self._voice.listen_once(timeout=8)
            if isinstance(res, dict) and res.get("text"):
                text = res["text"]
                QTimer.singleShot(0, lambda: self._send_text(text))
            else:
                # Nothing heard — return to ambient wake state
                QTimer.singleShot(0, lambda: self.orb.set_state("wake"))
        threading.Thread(target=_listen, daemon=True).start()

    def _toggle_quiet(self):
        if not self._voice:
            return
        is_quiet = self._voice.toggle_quiet()
        if is_quiet:
            self._quiet_btn.setText("🔇  VOICE OFF")
            self._quiet_btn.setStyleSheet(
                f"QPushButton{{background:#1a0500;color:#ff6644;"
                f"border:1px solid #ff664466;border-radius:4px;"
                f"font-family:{FF_MONO};font-size:{FS_SMALL}px;margin:0 12px;}}"
                f"QPushButton:hover{{border-color:#ff6644;background:#ff664422;}}"
                f"QPushButton:pressed{{background:#ff664433;}}"
            )
        else:
            self._quiet_btn.setText("🔊  VOICE ON")
            self._quiet_btn.setStyleSheet(
                f"QPushButton{{background:transparent;color:{T.dim};"
                f"border:1px solid {T.border};border-radius:4px;"
                f"font-family:{FF_MONO};font-size:{FS_SMALL}px;margin:0 12px;}}"
                f"QPushButton:hover{{color:{T.text};border-color:{T.accent}55;"
                f"background:{T.accent}0a;}}"
                f"QPushButton:pressed{{background:{T.accent}1a;}}"
            )
        self._log_event("quiet_mode_changed", quiet_mode=bool(is_quiet))
        self._refresh_runtime_status_label()

    # ── Daemon ─────────────────────────────────────────────────────────────────

    def _start_daemon(self):
        if not _DAEMON_AVAILABLE:
            return
        try:
            get_daemon_manager().start()
        except Exception as e:
            print(f"Daemon start failed: {e}")

    # ── Chat ───────────────────────────────────────────────────────────────────

    def _quick(self, text: str):
        self.inp.setText(text)
        self._send()

    def _send(self):
        self._stop_voice_output()
        self._send_text(self.inp.text().strip())
        self.inp.clear()

    def _send_text(self, text: str):
        if not text or (self._worker and self._worker.isRunning()):
            return
        self._log_event("request_started", mode=self._mode, input_chars=len(text))
        self._stop_voice_output()
        self._think_label = None
        self._stream_label = None
        self._last_persona_reply = ""
        self._tts_generation += 1
        self._bubble(text, "user", "user")
        # Clean up previous worker if it exists
        if self._worker:
            self._worker.quit()
            self._worker.wait(1000)  # Wait up to 1 second for cleanup
        w = Worker(
            text, self.history, self._mode,
            self._api_key, self._system, self._session_id,
            claude_model=self._claude_model,
            claude_backup_model=self._claude_backup_model,
        )
        w.bubble.connect(self._bubble)
        w.orb.connect(self.orb.set_state)
        w.done.connect(self._on_done)
        w.start()
        self._worker = w

    def _on_done(self):
        perf = getattr(self._worker, "_perf", {}) if self._worker else {}
        self._log_event(
            "request_finished",
            mode=self._mode,
            response_chars=len((self._last_persona_reply or "").strip()),
            elapsed_ms=perf.get("latency_ms"),
            backend=perf.get("route"),
            model=perf.get("model_used") or None,
            fallback=perf.get("fallback_used") or None,
            status=perf.get("status") or None,
        )
        if not self._voice:
            return
        text = (self._last_persona_reply or "").strip()
        if not text:
            return
        token = self._tts_generation
        threading.Thread(target=lambda: self._speak_if_current(token, text), daemon=True).start()

    def _speak_if_current(self, token: int, text: str):
        if token != self._tts_generation:
            return
        self._voice.speak(text)
        # After speaking, restore orb to wake state if wake word detection is active
        if self._voice.is_listening_for_wake_word:
            QTimer.singleShot(0, lambda: self.orb.set_state("wake"))

    def _stop_voice_output(self):
        self._tts_generation += 1
        if not self._voice:
            return
        for method_name in ("stop_tts", "stop_speaking"):
            stop_fn = getattr(self._voice, method_name, None)
            if callable(stop_fn):
                try:
                    stop_fn()
                    break
                except Exception:
                    continue

    def _on_user_typing(self, _text: str):
        self._stop_voice_output()

    def _bubble(self, text: str, sender: str, style: str):
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

        _init_stream = False
        if style == "guppy_stream":
            if self._stream_label is not None:
                current_text = getattr(self._stream_label, "_text", self._stream_label.text())
                accumulated = current_text + text
                self._stream_label._text = accumulated
                self._stream_label.setText(accumulated)
                self._last_persona_reply = accumulated
                self._think_label = None
                QTimer.singleShot(20, lambda: self.scroll.verticalScrollBar().setValue(
                    self.scroll.verticalScrollBar().maximum()
                ))
                return
            # First chunk — fall through to create a guppy bubble
            style = "guppy"
            sender = "guppy"
            _init_stream = True

        frame = QWidget()
        frame._sender = sender
        frame._text   = text
        frame._style  = style
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(12, 4, 12, 4)
        fl.setSpacing(3)

        STYLES = {
            "guppy":       ("Guppy",       T.accent,  T.bg2,    f"{T.accent}55"),
            "user":        (T.user_label,   T.dim,     T.bg3,    f"{T.border}99"),
            "tool":        ("⚙️  Tool",      "#404060", T.bg,     "#22222244"),
            "tool_result": ("   ↳ Result",  "#303050", T.bg,     "#11111133"),
            "thinking":    ("◌ Thinking",    T.dim,      T.bg,     f"{T.border}66"),
            "error":       ("⚠️  Error",     "#ff4444", "#1a0000","#ff000033"),
        }
        who_text, who_col, bg, border = STYLES.get(style, STYLES["guppy"])

        # Header row: sender + timestamp
        hdr = QWidget()
        hdr.setStyleSheet("background:transparent;")
        hrow = QHBoxLayout(hdr)
        hrow.setContentsMargins(0, 0, 0, 0)
        hrow.setSpacing(0)

        who = QLabel(who_text)
        wf  = QFont(SHARED.font_family, FS_LABEL)
        wf.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
        who.setFont(wf)
        who.setStyleSheet(f"color:{who_col}; background:transparent;")
        hrow.addWidget(who)
        hrow.addStretch()

        if SHARED.show_timestamps:
            ts = QLabel(now_str())
            ts.setFont(QFont(SHARED.font_family, FS_TS))
            ts.setStyleSheet(f"color:{T.dim}; background:transparent;")
            hrow.addWidget(ts)

        fl.addWidget(hdr)

        # Message body
        msg = QLabel(text)
        msg.setWordWrap(True)
        msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        msg.setFont(QFont(SHARED.font_family, SHARED.font_size))
        italic = "font-style:italic;" if style in ("tool", "tool_result", "thinking") else ""
        r = SHARED.bubble_radius
        msg.setStyleSheet(
            f"QLabel{{background:{bg};border-left:3px solid {border};"
            f"border-radius:{r}px;padding:9px 14px;color:{T.text};{italic}}}"
        )
        msg._text = text
        fl.addWidget(msg)

        if sender == "guppy" and style == "guppy":
            self._last_persona_reply = text
            self._think_label = None
            if _init_stream:
                self._stream_label = msg
        elif style == "thinking":
            self._think_label = msg
        elif style == "error":
            self._log_event("ui_error", level="error", message=(text or "")[:400])

        self.chat_lay.insertWidget(self.chat_lay.count() - 1, frame)
        # Fade-in + grow-in animation
        natural_h = frame.sizeHint().height()
        if natural_h < 10:
            natural_h = 60  # fallback if sizeHint not ready yet
        frame.setMaximumHeight(0)
        eff = QGraphicsOpacityEffect(frame)
        frame.setGraphicsEffect(eff)
        eff.setOpacity(0.0)

        # Opacity animation
        anim_op = QPropertyAnimation(eff, b"opacity", frame)
        anim_op.setDuration(320)
        anim_op.setStartValue(0.0)
        anim_op.setEndValue(1.0)
        anim_op.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Height animation
        anim_h = QPropertyAnimation(frame, b"maximumHeight", frame)
        anim_h.setDuration(280)
        anim_h.setStartValue(0)
        anim_h.setEndValue(natural_h + 20)
        anim_h.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim_h.finished.connect(lambda: frame.setMaximumHeight(16777215))

        # Break reference cycle when animation completes
        anim_op.finished.connect(lambda: setattr(frame, '_fade_anim', None))
        anim_op.start()
        anim_h.start()
        frame._fade_anim = anim_op  # prevent GC
        frame._grow_anim = anim_h   # prevent GC

        QTimer.singleShot(50, lambda: self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()
        ))

    # ── Session summarization ──────────────────────────────────────────────────

    def _readable_history(self) -> list[str]:
        """Extract plain text lines from self.history for summarization.
        Handles both Claude (content-block objects) and Ollama (string) formats.
        Skips tool-use and tool-result entries.
        """
        lines = []
        for msg in self.history:
            role = msg.get("role", "")
            content = msg.get("content", "")
            label = "Ryan" if role == "user" else "Guppy" if role == "assistant" else None
            if label is None:
                continue

            if isinstance(content, str):
                snippet = content.strip()[:300]
                if snippet:
                    lines.append(f"{label}: {snippet}")
            elif isinstance(content, list):
                texts = []
                for block in content:
                    # Anthropic SDK object
                    if hasattr(block, "type") and block.type == "text":
                        texts.append(block.text.strip()[:300])
                    # Plain dict (Ollama or serialised)
                    elif isinstance(block, dict) and block.get("type") == "text":
                        texts.append(block.get("text", "").strip()[:300])
                joined = " ".join(texts).strip()
                if joined:
                    lines.append(f"{label}: {joined[:300]}")
        return lines

    def _save_session_summary(self):
        """Summarise the current session and persist it. Fire-and-forget."""
        lines = self._readable_history()
        # Need at least a couple of real exchanges to be worth summarising
        if len(lines) < 4:
            return
        if not self._api_key:
            return

        session_id = self._session_id
        convo_text = "\n".join(lines[:30])  # cap to avoid token waste

        def _do():
            try:
                import anthropic
                from guppy_memory import save_session_summary
                client = anthropic.Anthropic(api_key=self._api_key)
                resp = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=300,
                    messages=[{
                        "role": "user",
                        "content": (
                            "Summarise this conversation in 3–5 concise bullet points. "
                            "Focus on: decisions made, facts about Ryan, tasks created, "
                            "preferences expressed, and anything worth remembering next session. "
                            "Use bullet points starting with '•'.\n\n"
                            f"{convo_text}"
                        ),
                    }],
                )
                summary = resp.content[0].text.strip()
                save_session_summary(session_id, summary)
            except Exception as e:
                import logging
                logging.getLogger(__name__).debug(f"Session summary failed: {e}")

        threading.Thread(target=_do, daemon=True).start()

    def _clear(self):
        self._save_session_summary()
        # Start a fresh session so next messages aren't mixed with the old one
        if _SAVE:
            self._session_id = _dt.now().strftime("%Y%m%d_%H%M%S")
        self.history.clear()
        while self.chat_lay.count() > 1:
            item = self.chat_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def closeEvent(self, event):
        if _HB_OK: _stop_hb('guppy')
        if _HB_OK: _clear_act("guppy")
        """Summarise the session before the window closes."""
        self._save_session_summary()
        event.accept()

    def _check_api_key(self):
        if not self._api_key:
            QTimer.singleShot(400, lambda: self._bubble(
                "⚠️  ANTHROPIC_API_KEY is not set — running on local model.\n"
                "To enable Claude, add the key to launch_guppy.bat and restart.",
                "error", "error",
            ))
        elif not self._api_key.startswith("sk-ant-"):
            QTimer.singleShot(400, lambda: self._bubble(
                "⚠️  API key format looks unusual (expected sk-ant-…). "
                "Claude mode may fail — verify ANTHROPIC_API_KEY.",
                "error", "error",
            ))

    def _greet(self):
        mode_desc = {
            "claude": "Claude online",
            "auto": "Auto route (local-first)",
            "ollama": "local model",
        }
        text = (
            f"Greet Master Ryan briefly. Running "
            f"{mode_desc.get(self._mode, 'local model')}. "
            "Full PC control, Gmail, Kindle, call reports, order notes all ready."
        )
        # Internal bootstrap message — don't pollute the conversation DB
        if self._worker and self._worker.isRunning():
            return
        w = Worker(
            text, self.history, self._mode,
            self._api_key, self._system, self._session_id,
            claude_model=self._claude_model,
            claude_backup_model=self._claude_backup_model,
            save=False,
        )
        w.bubble.connect(self._bubble)
        w.orb.connect(self.orb.set_state)
        w.done.connect(self._on_done)
        w.start()
        self._worker = w


# ── Application bootstrap ──────────────────────────────────────────────────────

app = QApplication(sys.argv)
app.setStyle("Fusion")

pal = QPalette()
pal.setColor(QPalette.ColorRole.Window,          QColor(T.bg))
pal.setColor(QPalette.ColorRole.WindowText,      QColor(T.text))
pal.setColor(QPalette.ColorRole.Base,            QColor(T.bg2))
pal.setColor(QPalette.ColorRole.Text,            QColor(T.text))
pal.setColor(QPalette.ColorRole.Button,          QColor(T.bg2))
pal.setColor(QPalette.ColorRole.ButtonText,      QColor(T.text))
pal.setColor(QPalette.ColorRole.Highlight,       QColor(T.accent))
pal.setColor(QPalette.ColorRole.HighlightedText, QColor(T.bg))
app.setPalette(pal)

window = GuppyWindow()
window.show()
sys.exit(app.exec())

