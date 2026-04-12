import sys, os, json, math, threading, time
import urllib.request
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QScrollArea, QLabel, QPushButton, QLineEdit, QFrame, QSizePolicy,
    QGraphicsOpacityEffect,
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QRectF, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import (QPainter, QColor, QPen, QFont, QRadialGradient,
                            QBrush, QPalette, QKeySequence, QShortcut)

from guppy_core import is_online, check_ollama, to_ollama_tools
from merlin_core import MERLIN_TOOLS, run_spell, get_merlin_startup_system
from guppy_theme import MERLIN_THEME as _MT, SHARED, now_str
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
    import anthropic
    _ANTH = True
except ImportError:
    _ANTH = False

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

# ── Palette (sourced from guppy_theme — edit theme.json to customize) ──────────
BG      = _MT.bg
BG2     = _MT.bg2
BG3     = _MT.bg3
GOLD    = _MT.accent
GOLD2   = "#e8c96a"    # lighter accent highlight
PURPLE  = "#7c3aed"    # Merlin's spell/magic colour — independent of theme
PURPLE2 = "#5b21b6"
TEXT    = _MT.text
DIM     = _MT.dim
BORDER  = _MT.border


# ── Worker ─────────────────────────────────────────────────────────────────────

class Worker(QThread):
    bubble = Signal(str, str, str)
    orb    = Signal(str)
    done   = Signal()

    def __init__(
        self,
        text,
        history,
        system,
        session_id,
        model="merlin",
        backup_model="",
        haiku_boost=False,
        api_key="",
        haiku_model="claude-haiku-4-5-20251001",
        haiku_boost_min_chars=180,
        save=True,
    ):
        super().__init__()
        self.text = text
        self.history = history
        self.system = system
        self.session_id = session_id
        self.model = model
        self.backup_model = backup_model
        self.haiku_boost = haiku_boost
        self.api_key = api_key
        self.haiku_model = haiku_model
        self.haiku_boost_min_chars = haiku_boost_min_chars
        self.save = save  # False for greeting/internal messages
        self._perf = {
            "tool_calls": 0,
            "tool_errors": 0,
            "fallback_used": False,
            "response_chars": 0,
            "boost_used": False,
            "boost_chars": 0,
            "model_used": "",
            "status": "ok",
            "error": "",
        }

    def run(self):
        started = time.perf_counter()
        request_id = f"{self.session_id}:{int(started * 1000)}:{id(self)}"
        _log_perf(
            "merlin",
            "request_started",
            session_id=self.session_id,
            request_id=request_id,
            mode="ollama_gemma_with_haiku_boost",
            input_chars=len(self.text or ""),
        )
        self.orb.emit("thinking")
        try:
            if _HB_OK: _write_act("merlin", "thinking")
            self.bubble.emit("Thinking through the next move", "thinking", "thinking_stream")
            self._merlin()
        except Exception as e:
            self._perf["status"] = "error"
            self._perf["error"] = str(e)
            self.bubble.emit(f"The spell misfired: {e}", "error", "error")
        finally:
            self._perf["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
            _log_perf(
                "merlin",
                "request_complete",
                session_id=self.session_id,
                request_id=request_id,
                mode="ollama_gemma_with_haiku_boost",
                input_chars=len(self.text or ""),
                tool_calls=self._perf["tool_calls"],
                tool_errors=self._perf["tool_errors"],
                response_chars=self._perf["response_chars"],
                fallback_used=self._perf["fallback_used"],
                boost_used=self._perf["boost_used"],
                boost_chars=self._perf["boost_chars"],
                model_used=self._perf["model_used"],
                status=self._perf["status"],
                error=self._perf["error"],
                latency_ms=self._perf["latency_ms"],
            )
            self.orb.emit("idle")
            if _HB_OK: _write_act("merlin", "idle")
            self.done.emit()

    def _merlin(self):
        self._merlin_ollama()

    def _merlin_ollama(self):
        active_model = self.model or "merlin"
        model_chain = [active_model]
        if self.backup_model and self.backup_model != active_model:
            model_chain.append(self.backup_model)

        selected_model = None
        last_err = ""
        for model_name in model_chain:
            ok, err = check_ollama(model_name)
            if ok:
                selected_model = model_name
                break
            last_err = err

        if not selected_model:
            self.bubble.emit(last_err or "No usable Merlin model is available.", "error", "error")
            return
        if selected_model != active_model:
            self._perf["fallback_used"] = True
            self.bubble.emit(
                f"Primary Merlin model unavailable; switched to backup ({selected_model}).",
                "spell_result",
                "spell_result",
            )
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
                "model": selected_model,
                "messages": all_msgs,
                "tools": ollama_tools,
                "stream": True,
                "options": {"temperature": 0.2, "top_p": 0.85, "top_k": 30}
            }).encode()
            req = urllib.request.Request(
                "http://localhost:11434/api/chat",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            # -- Streaming read -----------------------------------------------
            final_msg = {}
            accumulated_content = []  # Keep for final message reconstruction only
            first_token = True
            with urllib.request.urlopen(req, timeout=300) as r:
                for raw_line in r:
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    try:
                        chunk = json.loads(raw_line)
                    except Exception:
                        continue
                    msg_chunk = chunk.get("message", {})
                    token = msg_chunk.get("content", "")
                    if token:
                        if first_token:
                            self.orb.emit("speaking")
                            if _HB_OK: _write_act("merlin", "speaking")
                            first_token = False
                        # Process token immediately for UI, but keep minimal accumulation for final message
                        accumulated_content.append(token)
                        self.bubble.emit(token, "merlin_stream", "merlin")
                        # Clear accumulation periodically to prevent memory buildup
                        if len(accumulated_content) > 100:
                            accumulated_content = accumulated_content[-50:]  # Keep recent tokens only
                    if chunk.get("done", False):
                        final_msg = msg_chunk
                        final_msg["content"] = "".join(accumulated_content)
                        break

            reply_text = final_msg.get("content", "").strip()
            clean_msg = {"role": "assistant", "content": reply_text}
            tool_calls = final_msg.get("tool_calls", [])
            if tool_calls:
                clean_msg["tool_calls"] = tool_calls
            all_msgs.append(clean_msg)

            # -- Memory optimization: trim conversation history during tool loops --
            if len(all_msgs) > 60:
                # Keep system message, recent user message, and current assistant response
                system_msg = all_msgs[0] if all_msgs and all_msgs[0].get("role") == "system" else None
                user_msgs = [m for m in all_msgs[-10:] if m.get("role") == "user"]
                recent_assistant = [m for m in all_msgs[-5:] if m.get("role") == "assistant"]
                all_msgs[:] = ([system_msg] if system_msg else []) + user_msgs[-1:] + recent_assistant[-2:]

            if reply_text and _SAVE and self.save:
                _save_msg(self.session_id, "assistant", reply_text)

            if not tool_calls:
                boost_text = self._haiku_boost(reply_text)
                final_reply = reply_text
                if boost_text:
                    self._perf["boost_used"] = True
                    self._perf["boost_chars"] = len(boost_text)
                    self.bubble.emit("✦ Haiku boost engaged", "spell_result", "spell_result")
                    self.bubble.emit(boost_text, "merlin", "merlin")
                    final_reply = f"{reply_text}\n\n[Haiku boost]\n{boost_text}"
                    if _SAVE and self.save:
                        _save_msg(self.session_id, "assistant", f"[Haiku boost] {boost_text}")

                self._perf["response_chars"] += len(final_reply)

                # -- Smart history trim: keep pairs, prioritise recent --------
                self.history.append({"role": "user", "content": self.text})
                self.history.append({"role": "assistant", "content": final_reply})
                if len(self.history) > 50:
                    drop_idx = 0
                    for i, m in enumerate(self.history[:-2]):
                        if m.get("role") == "user":
                            nxt = self.history[i + 1] if i + 1 < len(self.history) else {}
                            if nxt.get("role") == "assistant":
                                drop_idx = i + 2
                                break
                    if drop_idx > 0:
                        self.history[:] = self.history[drop_idx:]
                    else:
                        self.history[:] = self.history[-50:]
                break

            # -- Tool calls ---------------------------------------------------
            for tc in tool_calls:
                self.orb.emit("thinking")
                self._perf["tool_calls"] += 1
                name = tc["function"]["name"]
                args = tc["function"].get("arguments", {})
                preview = ", ".join(f"{k}={repr(v)[:30]}" for k, v in args.items())
                if SHOW_BACKEND_DETAILS:
                    self.bubble.emit(f"⚗️  Casting: {name}({preview})", "spell", "spell")
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
                all_msgs.append({"role": "tool", "content": result_str})
        self._perf["model_used"] = selected_model

    def _haiku_boost(self, base_reply: str) -> str:
        """Optional Haiku pass to add a concise boost to Gemma's reply."""
        if not self.haiku_boost or not base_reply.strip() or not self.api_key or not is_online() or not _ANTH:
            return ""
        if len(base_reply.strip()) < max(0, int(self.haiku_boost_min_chars)):
            return ""
        try:
            client = anthropic.Anthropic(api_key=self.api_key)
            resp = client.messages.create(
                model=self.haiku_model,
                max_tokens=220,
                messages=[{
                    "role": "user",
                    "content": (
                        "You are assisting Merlin. Improve the reply below with a short boost: "
                        "1-3 concise sentences, no preamble, no markdown headings, no tool calls.\n\n"
                        f"User request: {self.text}\n"
                        f"Gemma draft: {base_reply}"
                    ),
                }],
            )
            return (resp.content[0].text or "").strip()
        except Exception:
            return ""
# ── Orb ────────────────────────────────────────────────────────────────────────

class Orb(QWidget):
    # Merlin palette: idle=deep indigo, thinking=amber, speaking=bright gold, listening=violet
    COLORS = {
        "idle":      QColor(80,  30, 160, 160),   # deep indigo
        "thinking":  QColor(210, 130,  20, 210),  # amber
        "speaking":  QColor(210, 170,  50, 230),  # bright gold
        "listening": QColor(140,  60, 220, 220),  # violet
    }

    def __init__(self):
        super().__init__()
        self.setMinimumSize(SHARED.orb_min_size, SHARED.orb_min_size)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.state = "idle"
        self.p = 0.0
        self.rings = []
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(16)

    def set_state(self, s):
        self.state = s
        if s in ("listening", "speaking"):
            self.rings = []

    def _tick(self):
        self.p += 0.016
        if self.state in ("listening", "speaking"):
            spd = 0.016 if self.state == "listening" else 0.025
            gap = 0.22  if self.state == "listening" else 0.12
            if not self.rings or self.rings[-1] > gap:
                self.rings.append(0.0)
            self.rings = [r + spd for r in self.rings if r < 1.0]
        self.update()

    def paintEvent(self, e):
        pr = QPainter(self)
        pr.setRenderHint(QPainter.RenderHint.Antialiasing)
        c  = self.rect().center()
        r  = min(self.width(), self.height()) * 0.28
        col = self.COLORS.get(self.state, self.COLORS["idle"])

        # Ambient glow
        g  = QRadialGradient(c, r * 2.4)
        gc = QColor(col)
        gc.setAlphaF(0.08 * (0.7 + 0.3 * math.sin(self.p * 1.6)))
        g.setColorAt(0, gc)
        g.setColorAt(1, QColor(0, 0, 0, 0))
        pr.setBrush(QBrush(g))
        pr.setPen(Qt.PenStyle.NoPen)
        pr.drawEllipse(c, r * 2.4, r * 2.4)

        # Ripple rings
        for ring in self.rings:
            rr = r + ring * r * 2.8
            rc = QColor(col)
            rc.setAlpha(int(190 * (1 - ring)))
            pr.setPen(QPen(rc, 1.4 * (1 - ring * 0.5)))
            pr.setBrush(Qt.BrushStyle.NoBrush)
            pr.drawEllipse(c, rr, rr)

        # Thinking arcs
        if self.state == "thinking":
            pr.save()
            pr.translate(c)
            ar = r * 1.55
            for i in range(3):
                ac = QColor(col)
                ac.setAlpha(150)
                pr.setPen(QPen(ac, 2.2))
                pr.setBrush(Qt.BrushStyle.NoBrush)
                pr.drawArc(QRectF(-ar, -ar, ar * 2, ar * 2),
                           int((self.p * 5729 + i * 120) * 16), int(85 * 16))
            pr.restore()

        # Core orb
        cp = 0.85 + 0.15 * math.sin(self.p * 2.0)
        if self.state == "speaking":
            cp = 0.78 + 0.22 * math.sin(self.p * 8)
        cr = r * cp
        cg = QRadialGradient(c.x() - cr * 0.3, c.y() - cr * 0.3, cr * 1.3)
        cc = QColor(col); cc.setAlphaF(0.95)
        ec = QColor(col); ec.setAlphaF(0.12)
        cg.setColorAt(0, cc)
        cg.setColorAt(0.6, ec)
        cg.setColorAt(1, QColor(10, 6, 18))
        pr.setBrush(QBrush(cg))
        pr.setPen(Qt.PenStyle.NoPen)
        pr.drawEllipse(c, cr, cr)

        # State label
        lc = QColor(col); lc.setAlphaF(0.45)
        pr.setPen(QPen(lc))
        f = QFont("Segoe UI", 7)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.5)
        pr.setFont(f)
        labels = {"idle": "IDLE", "thinking": "CASTING", "speaking": "SPEAKING", "listening": "LISTENING"}
        pr.drawText(QRectF(0, c.y() + r * 1.5, self.width(), 18),
                    Qt.AlignmentFlag.AlignHCenter, labels.get(self.state, ""))


# ── Main window ────────────────────────────────────────────────────────────────

class MerlinWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Merlin — The Sorcerer's Study")
        self.resize(1050, 720)
        self.setMinimumSize(800, 550)
        self.history   = []
        self._worker   = None
        self._voice    = None
        self._api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        self._haiku_model = os.environ.get("ANTHROPIC_HAIKU_MODEL", "claude-haiku-4-5-20251001").strip() or "claude-haiku-4-5-20251001"
        self._haiku_boost_enabled = os.environ.get("MERLIN_HAIKU_BOOST", "0").strip() in {"1", "true", "yes", "on"}
        self._haiku_boost_min_chars = int(os.environ.get("MERLIN_HAIKU_BOOST_MIN_CHARS", "180"))
        self._merlin_local_model = os.environ.get("MERLIN_LOCAL_MODEL", "merlin").strip() or "merlin"
        self._merlin_local_backup_model = os.environ.get("MERLIN_LOCAL_BACKUP_MODEL", "").strip()
        self._session_id = _dt.now().strftime("%Y%m%d_%H%M%S") if _SAVE else ""
        self._system   = get_merlin_startup_system()
        self._stream_label = None    # Live streaming bubble label
        self._think_label = None
        self._last_persona_reply = ""
        self._tts_generation = 0
        self._status_strip = None
        self._timeline = None
        self._startup_checklist = None
        self._lat_spark = None
        self._queue_spark = None
        self._lat_points = []
        self._queue_points = []
        self._last_timeline_key = ""
        self.setStyleSheet(f"background:{BG}; color:{TEXT}; font-family:'Segoe UI';")
        self._build()
        self._setup_voice()
        self._greet()
        if _HB_OK: _start_hb('merlin')
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(lambda: open_debug_console(self))
        QShortcut(QKeySequence("Ctrl+K"), self).activated.connect(self._open_command_palette)
        self._ui_tick = QTimer(self)
        self._ui_tick.timeout.connect(self._refresh_telemetry_panels)
        self._ui_tick.start(1800)
        self._log_event("ui_started", mode="local")

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── Left sidebar ───────────────────────────────────────────────────────
        left = QWidget()
        left.setFixedWidth(240)
        left.setStyleSheet(f"background:{BG2}; border-right:1px solid {BORDER};")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 16)
        ll.setSpacing(0)

        # ── Gradient header ────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(82)
        header.setStyleSheet(
            f"background: qlineargradient("
            f"x1:0, y1:0, x2:0, y2:1, "
            f"stop:0 {GOLD}2a, stop:0.6 {GOLD}0d, stop:1 {BG2});"
            f"border-bottom: 2px solid {GOLD}44;"
        )
        hl = QVBoxLayout(header)
        hl.setContentsMargins(0, 14, 0, 10)
        hl.setSpacing(3)

        t = QLabel("MERLIN")
        f = QFont(SHARED.font_family, FS_TITLE, QFont.Weight.Bold)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 7)
        t.setFont(f)
        t.setStyleSheet(f"color:{GOLD}; background:transparent;")
        t.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        s = QLabel("✦  The Sorcerer's Study  ✦")
        sf = QFont(SHARED.font_family, FS_LABEL)
        sf.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1)
        s.setFont(sf)
        s.setStyleSheet(f"color:{GOLD}66; background:transparent;")
        s.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        hl.addWidget(t)
        hl.addWidget(s)
        ll.addWidget(header)

        # Orb
        self.orb = Orb()
        ll.addWidget(self.orb, stretch=1)

        # Mode indicator
        self.mode_lbl = QLabel()
        self.mode_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.mode_lbl.setFixedHeight(CH_MD)
        self.mode_lbl.setStyleSheet(
            f"background:{BG3}; color:{GOLD}; border:1px solid {GOLD}44; "
            f"border-radius:4px; font-size:{FS_SMALL}px; letter-spacing:1px; "
            f"margin:0 12px; font-weight:bold;"
        )
        self._update_mode_label()
        ll.addWidget(self.mode_lbl)
        self.tier_btn = QPushButton()
        self.tier_btn.setFixedHeight(CH_SM)
        self.tier_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tier_btn.clicked.connect(self._toggle_merlin_tier)
        self._update_merlin_tier_btn()
        ll.addWidget(self.tier_btn)
        ll.addSpacing(10)

        # Section label
        sec = QLabel("QUICK SPELLS")
        sec.setFixedHeight(16)
        sec.setStyleSheet(
            f"color:{DIM}; background:transparent; font-size:{FS_LABEL}px; "
            f"letter-spacing:2px; margin:0 12px;"
        )
        ll.addWidget(sec)
        ll.addSpacing(4)

        # Quick spells
        quick_spells = [
            ("🔮  SCRY THE WEB",    lambda: self._quick("Search the web for: ")),
            ("📜  RESEARCH TOPIC",  lambda: self._quick("Research this for me: ")),
            ("🐛  DEBUG THIS CODE", lambda: self._quick("Help me debug this code: ")),
            ("📋  READ MY QUESTS",  lambda: self._quick("Show me my pending quests.")),
            ("📖  STUDY SESSION",   lambda: self._quick("Let's study: ")),
        ]
        for label, action in quick_spells:
            b = QPushButton(label)
            b.setFixedHeight(CH_MD)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton{{background:transparent;color:{DIM};"
                f"border:1px solid {BORDER};border-left:3px solid transparent;"
                f"border-radius:4px;font-size:{FS_BODY - 1}px;"
                f"margin:0 12px 4px 12px;text-align:left;padding-left:10px;}}"
                f"QPushButton:hover{{color:{TEXT};background:{GOLD}0d;"
                f"border-color:{GOLD}44;border-left-color:{GOLD};}}"
                f"QPushButton:pressed{{background:{GOLD}1a;"
                f"border-left-color:{GOLD};}}"
            )
            b.clicked.connect(action)
            ll.addWidget(b)

        ll.addSpacing(8)
        cb = QPushButton("✦  CLEAR THE SCROLL")
        cb.setFixedHeight(CH_SM)
        cb.setCursor(Qt.CursorShape.PointingHandCursor)
        cb.setStyleSheet(
            f"QPushButton{{background:transparent;color:{DIM};"
            f"border:1px solid {BORDER};border-radius:4px;"
            f"font-size:{FS_SMALL}px;margin:0 12px;letter-spacing:1px;}}"
            f"QPushButton:hover{{color:#ff6644;border-color:#ff664455;}}"
            f"QPushButton:pressed{{background:#ff664411;}}"
        )
        cb.clicked.connect(self._clear)
        ll.addWidget(cb)

        diag = QPushButton("⛭  DIAGNOSTICS")
        diag.setFixedHeight(CH_SM)
        diag.setCursor(Qt.CursorShape.PointingHandCursor)
        diag.setStyleSheet(
            f"QPushButton{{background:transparent;color:{DIM};"
            f"border:1px solid {BORDER};border-radius:4px;"
            f"font-size:{FS_SMALL}px;margin:6px 12px 0 12px;letter-spacing:1px;}}"
            f"QPushButton:hover{{color:{TEXT};border-color:{GOLD}55;background:{GOLD}11;}}"
            f"QPushButton:pressed{{background:{GOLD}22;}}"
        )
        diag.clicked.connect(self._collect_diagnostics)
        ll.addWidget(diag)

        palette_btn = QPushButton("⌘  COMMANDS")
        palette_btn.setFixedHeight(CH_SM)
        palette_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        palette_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{DIM};"
            f"border:1px solid {BORDER};border-radius:4px;"
            f"font-size:{FS_SMALL}px;margin:4px 12px 0 12px;letter-spacing:1px;}}"
            f"QPushButton:hover{{color:{TEXT};border-color:{GOLD}55;background:{GOLD}11;}}"
            f"QPushButton:pressed{{background:{GOLD}22;}}"
        )
        palette_btn.clicked.connect(self._open_command_palette)
        ll.addWidget(palette_btn)

        lay.addWidget(left)

        # ── Right chat pane ────────────────────────────────────────────────────
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        telem_wrap = QWidget()
        twl = QVBoxLayout(telem_wrap)
        twl.setContentsMargins(8, 8, 8, 6)
        twl.setSpacing(6)
        self._status_strip = StatusStrip(accent=GOLD)
        twl.addWidget(self._status_strip)

        mini = QHBoxLayout()
        mini.setSpacing(6)
        self._startup_checklist = StartupChecklist(parent=self)
        self._startup_checklist.setMaximumWidth(220)
        mini.addWidget(self._startup_checklist)

        trend_wrap = QFrame()
        trend_wrap.setStyleSheet(f"QFrame{{background:{BG2};border:1px solid {BORDER};border-radius:6px;}}")
        trl = QVBoxLayout(trend_wrap)
        trl.setContentsMargins(8, 6, 8, 6)
        trl.setSpacing(4)
        lat_lbl = QLabel("LATENCY TREND")
        lat_lbl.setStyleSheet(f"color:{DIM};background:transparent;font-family:{FF_MONO};font-size:{FS_LABEL}px;")
        trl.addWidget(lat_lbl)
        self._lat_spark = Sparkline(color="#d6b766")
        trl.addWidget(self._lat_spark)
        q_lbl = QLabel("QUEUE TREND")
        q_lbl.setStyleSheet(f"color:{DIM};background:transparent;font-family:{FF_MONO};font-size:{FS_LABEL}px;")
        trl.addWidget(q_lbl)
        self._queue_spark = Sparkline(color="#9b7ae8")
        trl.addWidget(self._queue_spark)
        mini.addWidget(trend_wrap)

        self._timeline = TimelinePanel("SPELL TIMELINE", self)
        self._timeline.setMaximumHeight(120)
        mini.addWidget(self._timeline, stretch=1)
        twl.addLayout(mini)
        rl.addWidget(telem_wrap)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(
            f"QScrollArea{{background:{BG};border:none;}}"
            f"QScrollBar:vertical{{background:{BG};width:3px;}}"
            f"QScrollBar::handle:vertical{{background:{BORDER};border-radius:1px;}}"
            f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}"
        )
        self.chat_box = QWidget()
        self.chat_box.setStyleSheet(f"background:{BG};")
        self.chat_lay = QVBoxLayout(self.chat_box)
        self.chat_lay.setContentsMargins(16, 16, 16, 8)
        self.chat_lay.setSpacing(6)
        self.chat_lay.addStretch()
        self.scroll.setWidget(self.chat_box)
        rl.addWidget(self.scroll)

        # Input bar
        bar = QWidget()
        bar.setFixedHeight(66)
        bar.setStyleSheet(f"background:{BG2}; border-top:2px solid {GOLD}33;")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(14, 12, 14, 12)
        bl.setSpacing(8)

        self.inp = QLineEdit()
        self.inp.setPlaceholderText("Speak thy query, Apprentice...")
        self.inp.setStyleSheet(
            f"QLineEdit{{background:{BG3};color:{TEXT};"
            f"border:1px solid {BORDER};border-radius:6px;"
            f"padding:0 14px;font-size:{FS_BODY}pt;}}"
            f"QLineEdit:focus{{border-color:{PURPLE}55;}}"
        )
        self.inp.returnPressed.connect(self._send)
        self.inp.textEdited.connect(self._on_user_typing)

        send = QPushButton("✦")
        send.setFixedSize(CH_LG, CH_LG)
        send.setCursor(Qt.CursorShape.PointingHandCursor)
        send.setStyleSheet(
            f"QPushButton{{background:{BG3};color:{GOLD};"
            f"border:2px solid {GOLD}55;border-radius:6px;font-size:{FS_BODY + 4}pt;}}"
            f"QPushButton:hover{{background:{GOLD}22;"
            f"border-color:{GOLD};color:{GOLD};}}"
            f"QPushButton:pressed{{background:{GOLD};color:{BG};}}"
        )
        send.clicked.connect(self._send)

        ptt = QPushButton("🎤")
        ptt.setFixedSize(CH_LG, CH_LG)
        ptt.setCursor(Qt.CursorShape.PointingHandCursor)
        ptt.setStyleSheet(
            f"QPushButton{{background:{BG3};color:{DIM};"
            f"border:1px solid {BORDER};border-radius:6px;font-size:{FS_BODY + 3}pt;}}"
            f"QPushButton:hover{{color:{TEXT};border-color:{PURPLE}44;}}"
            f"QPushButton:pressed{{background:{PURPLE}33;color:{GOLD};"
            f"border-color:{PURPLE};}}"
        )
        ptt.pressed.connect(self._ptt_start)
        ptt.released.connect(self._ptt_stop)

        self._quiet_btn = QPushButton("🔊")
        self._quiet_btn.setFixedSize(CH_LG, CH_LG)
        self._quiet_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._quiet_btn.setToolTip("Toggle voice output")
        self._quiet_btn.setStyleSheet(
            f"QPushButton{{background:{BG3};color:{DIM};"
            f"border:1px solid {BORDER};border-radius:6px;font-size:{FS_BODY + 3}pt;}}"
            f"QPushButton:hover{{color:{GOLD};border-color:{GOLD}44;}}"
            f"QPushButton:pressed{{background:{GOLD}22;}}"
        )
        self._quiet_btn.clicked.connect(self._toggle_quiet)

        bl.addWidget(self.inp)
        bl.addWidget(send)
        bl.addWidget(ptt)
        bl.addWidget(self._quiet_btn)
        rl.addWidget(bar)
        lay.addWidget(right)

    def _quick(self, text):
        self.inp.setText(text)
        self.inp.setFocus()

    def _update_mode_label(self):
        if self._haiku_boost_enabled and self._api_key and is_online() and _ANTH:
            self.mode_lbl.setText("◉  LOCAL MODEL  +  HAIKU BOOST")
        else:
            self.mode_lbl.setText("◉  LOCAL MODEL  —  ARCANA")

    def _update_merlin_tier_btn(self):
        if self._haiku_boost_enabled:
            self.tier_btn.setText("◌  HAIKU BOOST  ON")
            self.tier_btn.setStyleSheet(
                f"QPushButton{{background:#2b1f0f;color:#ffcc88;"
                f"border:1px solid #ffcc8866;border-radius:4px;"
                f"font-size:{FS_SMALL}px;letter-spacing:1px;margin:0 12px;font-weight:bold;}}"
                f"QPushButton:hover{{border-color:#ffcc88;background:#ffcc8811;}}"
            )
        else:
            self.tier_btn.setText("◌  HAIKU BOOST  OFF")
            self.tier_btn.setStyleSheet(
                f"QPushButton{{background:{BG3};color:{TEXT};"
                f"border:1px solid {BORDER}99;border-radius:4px;"
                f"font-size:{FS_SMALL}px;letter-spacing:1px;margin:0 12px;font-weight:bold;}}"
                f"QPushButton:hover{{border-color:{GOLD}66;background:{GOLD}11;}}"
            )

    def _toggle_merlin_tier(self):
        if not self._api_key or not is_online() or not _ANTH:
            self._bubble("Haiku boost requires ANTHROPIC_API_KEY and internet, Apprentice.", "error", "error")
            return
        self._haiku_boost_enabled = not self._haiku_boost_enabled
        self._update_merlin_tier_btn()
        self._update_mode_label()
        self._bubble(
            f"Haiku boost {'enabled' if self._haiku_boost_enabled else 'disabled'}.",
            "merlin",
            "merlin",
        )

    def _send(self):
        self._stop_voice_output()
        self._send_text(self.inp.text().strip())
        self.inp.clear()

    def _send_text(self, text):
        if not text or (self._worker and self._worker.isRunning()):
            return
        self._log_event("request_started", input_chars=len(text))
        self._stop_voice_output()
        self._stream_label = None
        self._think_label = None
        self._last_persona_reply = ""
        self._tts_generation += 1
        self._bubble(text, "user", "user")
        # Clean up previous worker if it exists
        if self._worker:
            self._worker.quit()
            self._worker.wait(1000)  # Wait up to 1 second for cleanup
        # Get system with query context for smart memory inclusion
        current_system = get_merlin_startup_system(query_context=text)
        w = Worker(
            text,
            self.history,
            current_system,
            self._session_id,
            model=self._merlin_local_model,
            backup_model=self._merlin_local_backup_model,
            haiku_boost=self._haiku_boost_enabled,
            api_key=self._api_key,
            haiku_model=self._haiku_model,
            haiku_boost_min_chars=self._haiku_boost_min_chars,
        )
        w.bubble.connect(self._bubble)
        w.orb.connect(self.orb.set_state)
        w.done.connect(self._on_done)
        w.start()
        self._worker = w

    def _setup_voice(self):
        try:
            from guppy_voice import GuppyVoice, VoiceConfig
            self._voice = GuppyVoice(VoiceConfig(
                tts_voice=os.environ.get("MERLIN_TTS_VOICE", "bm_lewis"),
                tts_rate=os.environ.get("MERLIN_TTS_RATE", "-18%"),
                tts_pitch=os.environ.get("MERLIN_TTS_PITCH", "-14Hz"),
            ))
        except Exception:
            self._voice = None

    def _on_done(self):
        self._log_event("request_finished", response_chars=len((self._last_persona_reply or "").strip()))
        self.orb.set_state("idle")
        self._stream_label = None  # Reset stream label for next response
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

    def _ptt_start(self):
        if not self._voice:
            return
        self.orb.set_state("listening")
        def _listen():
            res = self._voice.listen_once()
            if res.get("error"):
                QTimer.singleShot(0, lambda: self._bubble(f"Voice error: {res['error']}", "error", "error"))
                QTimer.singleShot(0, lambda: self.orb.set_state("idle"))
            elif res.get("text"):
                QTimer.singleShot(0, lambda: self._send_text(res["text"]))
            else:
                QTimer.singleShot(0, lambda: self.orb.set_state("idle"))
        threading.Thread(target=_listen, daemon=True).start()

    def _ptt_stop(self):
        if self._voice:
            self._voice.stop_listening()

    def _toggle_quiet(self):
        if not self._voice:
            return
        is_quiet = self._voice.toggle_quiet()
        if is_quiet:
            self._quiet_btn.setText("🔇")
            self._quiet_btn.setStyleSheet(
                f"QPushButton{{background:{BG3};color:#ff6644;"
                f"border:1px solid #ff664455;border-radius:6px;font-size:{FS_BODY + 3}pt;}}"
                f"QPushButton:hover{{border-color:#ff6644;}}"
            )
        else:
            self._quiet_btn.setText("🔊")
            self._quiet_btn.setStyleSheet(
                f"QPushButton{{background:{BG3};color:{DIM};"
                f"border:1px solid {BORDER};border-radius:6px;font-size:{FS_BODY + 3}pt;}}"
                f"QPushButton:hover{{color:{GOLD};}}"
            )
        self._log_event("quiet_mode_changed", quiet_mode=bool(is_quiet))

    def _log_event(self, event: str, level: str = "info", **fields):
        _log_session_event("merlin_ui", event, level=level, session_id=self._session_id, **fields)

    def _startup_self_check(self) -> dict:
        readiness = {}
        readiness["auth"] = "READY" if (self._api_key and self._api_key.startswith("sk-ant-")) else ("PARTIAL" if self._api_key else "MISSING")
        ok, _err = check_ollama(self._merlin_local_model or "merlin")
        readiness["ollama"] = "READY" if ok else "MISSING"
        readiness["voice"] = "READY" if self._voice else "MISSING"
        return readiness

    def _refresh_telemetry_panels(self):
        snap = rolling_agent_snapshot("merlin", window_seconds=900)
        checks = self._startup_self_check()
        qd = int(snap.get("queue_depth", 0) or 0)
        p95 = float(snap.get("p95_ms", 0.0) or 0.0)
        p99 = float(snap.get("p99_ms", 0.0) or 0.0)

        if self._status_strip:
            mode = "LOCAL+HAIKU" if self._haiku_boost_enabled else "LOCAL"
            self._status_strip.set_summary(mode, checks.get("auth", "MISSING"), checks.get("ollama", "MISSING"), checks.get("voice", "MISSING"))
            self._status_strip.set_latency(p95, p99, qd)
            tts_backend = "none"
            if self._voice and hasattr(self._voice, "backend_status"):
                try:
                    tts_backend = str(self._voice.backend_status().get("tts_backend", "none"))
                except Exception:
                    tts_backend = "unknown"
            self._status_strip.set_voice_detail(tts_backend, os.environ.get("MERLIN_TTS_VOICE", "-"))
            incidents = []
            if checks.get("auth") != "READY":
                incidents.append({"text": "AUTH", "severity": "warn" if checks.get("auth") == "PARTIAL" else "error"})
            if checks.get("ollama") != "READY":
                incidents.append({"text": "OLLAMA", "severity": "error"})
            if checks.get("voice") != "READY":
                incidents.append({"text": "VOICE", "severity": "warn"})
            if qd > 0:
                incidents.append({"text": f"QUEUE {qd}", "severity": "warn"})
            if p95 >= 5000:
                incidents.append({"text": "HIGH LAT", "severity": "error"})
            elif p95 >= 2500:
                incidents.append({"text": "LATENCY", "severity": "warn"})
            self._status_strip.set_incidents(incidents)

        if self._startup_checklist:
            self._startup_checklist.set_checks(checks)

        lat = snap.get("latencies", [])
        if isinstance(lat, list) and lat:
            self._lat_points = [float(v) for v in lat if isinstance(v, (int, float))][-60:]
        if self._lat_spark:
            self._lat_spark.set_values(self._lat_points)
        self._queue_points.append(qd)
        self._queue_points = self._queue_points[-60:]
        if self._queue_spark:
            self._queue_spark.set_values(self._queue_points)

        if self._timeline:
            events = recent_agent_events("merlin", limit=6)
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
            {"name": "Toggle Haiku Boost", "action": self._toggle_merlin_tier},
            {"name": "Hold To Talk", "action": self._ptt_start},
            {"name": "Toggle Quiet", "action": self._toggle_quiet},
            {"name": "Scry The Web", "action": lambda: self._quick("Search the web for: ")},
            {"name": "Research Topic", "action": lambda: self._quick("Research this for me: ")},
            {"name": "Debug Code", "action": lambda: self._quick("Help me debug this code: ")},
            {"name": "Read Quests", "action": lambda: self._quick("Show me my pending quests.")},
            {"name": "Collect Diagnostics", "action": self._collect_diagnostics},
            {"name": "Clear Scroll", "action": self._clear},
        ]
        dlg = CommandPaletteDialog(commands, self)
        dlg.exec()

    def _collect_diagnostics(self):
        path = create_diagnostics_bundle("merlin")
        self._bubble(f"Diagnostics bundle created: {path}", "merlin", "spell_result")
        self._log_event("diagnostics_bundle_created", path=str(path))
        if self._timeline:
            self._timeline.add_event(now_str(), "diagnostics bundle created")

    def _bubble(self, text, sender, style):
        """Add a message bubble. merlin_stream tokens append to the live bubble."""
        if style == "thinking_stream":
            if self._think_label is not None:
                new_text = text.strip()
                current_text = getattr(self._think_label, "_text", self._think_label.text())
                if new_text and new_text not in current_text:
                    updated_text = f"{current_text}  •  {new_text}" if current_text else new_text
                    self._think_label._text = updated_text
                    self._think_label.setText(updated_text)
                QTimer.singleShot(20, lambda: self.scroll.verticalScrollBar().setValue(
                    self.scroll.verticalScrollBar().maximum()))
                return
            style = "thinking"

        if style == "merlin_stream":
            if self._stream_label is not None:
                # Append token to existing bubble
                self._stream_label._text += text
                self._stream_label.setText(self._stream_label._text)
                QTimer.singleShot(50, lambda: self.scroll.verticalScrollBar().setValue(
                    self.scroll.verticalScrollBar().maximum()))
                return
            # First token: create a new bubble frame and store label ref
            style = "merlin"

        frame = QWidget()
        frame._sender = sender
        frame._text   = text
        frame._style  = style
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(12, 4, 12, 4)
        fl.setSpacing(3)

        S = {
            "merlin":       ("✦ Merlin",        GOLD,      BG2,       f"{GOLD}55"),
            "user":         (_MT.user_label,    DIM,       BG3,       f"{PURPLE}33"),
            "spell":        ("⚗️  Spell Cast",  PURPLE,    BG,        f"{PURPLE}44"),
            "spell_result": ("   ↳ Omen",       "#4a3060", BG,        "#22113322"),
            "thinking":     ("◌ Thinking",      DIM,       BG,        f"{BORDER}77"),
            "error":        ("⚡  Misfire",      "#ff4444", "#1a0000", "#ff000033"),
        }
        who_text, who_col, bg, border = S.get(style, S["merlin"])

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
            ts.setStyleSheet(f"color:{DIM}; background:transparent;")
            hrow.addWidget(ts)

        fl.addWidget(hdr)

        msg = QLabel(text)
        msg.setWordWrap(True)
        msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        msg.setFont(QFont(SHARED.font_family, SHARED.font_size))
        italic = "font-style:italic;" if style in ("spell", "spell_result", "thinking") else ""
        r = SHARED.bubble_radius
        msg.setStyleSheet(
            f"QLabel{{background:{bg};border-left:3px solid {border};"
            f"border-radius:{r}px;padding:9px 14px;color:{TEXT};{italic}}}"
        )
        # Store mutable text on the label for stream appending
        msg._text = text

        fl.addWidget(msg)

        if sender == "merlin" and style == "merlin":
            self._last_persona_reply = text
            self._think_label = None
        elif style == "thinking":
            self._think_label = msg

        self.chat_lay.insertWidget(self.chat_lay.count() - 1, frame)

        # Track stream label so tokens can append to it
        if sender == "merlin":
            self._stream_label = msg
            frame._stream_msg  = msg

        # Fade-in animation
        eff = QGraphicsOpacityEffect(frame)
        frame.setGraphicsEffect(eff)
        eff.setOpacity(0.0)
        anim = QPropertyAnimation(eff, b"opacity", frame)
        anim.setDuration(400)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        # Break reference cycle when animation completes
        anim.finished.connect(lambda: setattr(frame, '_fade_anim', None))
        anim.start()
        frame._fade_anim = anim

        QTimer.singleShot(50, lambda: self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()
        ))

    def _clear(self):
        self.history.clear()
        while self.chat_lay.count() > 1:
            item = self.chat_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _greet(self):
        prompt = (
            "Greet your Apprentice Ryan briefly — in character. "
            f"You are running on local model{' with optional Haiku boost' if self._haiku_boost_enabled else ''}. Keep it very short."
        )
        w = Worker(
            prompt,
            self.history,
            self._system,
            self._session_id,
            model=self._merlin_local_model,
            backup_model=self._merlin_local_backup_model,
            haiku_boost=self._haiku_boost_enabled,
            api_key=self._api_key,
            haiku_model=self._haiku_model,
            haiku_boost_min_chars=self._haiku_boost_min_chars,
            save=False,
        )
        w.bubble.connect(self._bubble)
        w.orb.connect(self.orb.set_state)
        w.done.connect(self._on_done)
        w.start()
        self._worker = w


    def closeEvent(self, event):
        if _HB_OK:
            _stop_hb("merlin")
            _clear_act("merlin")
        super().closeEvent(event)

# ── Application bootstrap ──────────────────────────────────────────────────────

app = QApplication(sys.argv)
app.setStyle("Fusion")

pal = QPalette()
pal.setColor(QPalette.ColorRole.Window,          QColor(BG))
pal.setColor(QPalette.ColorRole.WindowText,      QColor(TEXT))
pal.setColor(QPalette.ColorRole.Base,            QColor(BG3))
pal.setColor(QPalette.ColorRole.Text,            QColor(TEXT))
pal.setColor(QPalette.ColorRole.Button,          QColor(BG2))
pal.setColor(QPalette.ColorRole.ButtonText,      QColor(TEXT))
pal.setColor(QPalette.ColorRole.Highlight,       QColor(PURPLE))
pal.setColor(QPalette.ColorRole.HighlightedText, QColor(BG))
app.setPalette(pal)

window = MerlinWindow()
window.show()
sys.exit(app.exec())

