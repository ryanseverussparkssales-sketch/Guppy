"""
guppy_hub.py - Omnissiah Machine Spirit
=======================================
System tray machine spirit and unified controller for all Guppy agents.

  Left-click tray icon  -> show/hide Omnissiah panel
  Right-click tray icon -> context menu

Omnissiah panel:
  - Per-agent status cards (RUNNING / STOPPED, live uptime)
  - Launch / Stop per agent
  - Launch All / Stop All
  - Smart launch based on active window and system load
  - CPU + RAM readout (psutil)
  - Draggable, frameless, stays on top
"""

import os
import sys
import subprocess
import time
import threading
import logging
import socket
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Heartbeat reader (checks agent responsiveness)
_RUNTIME = Path(__file__).parent / 'runtime'
HB_STALE_SECS = 30   # seconds before an agent is considered stalled
from typing import Optional

from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QSystemTrayIcon, QMenu,
    QFrame, QStyle,
)
from PySide6.QtCore import (
    Qt, QTimer, QPoint, Signal, QObject, QThread,
)
from PySide6.QtGui import (
    QIcon, QPainter, QColor, QFont, QPen, QBrush,
    QRadialGradient, QAction, QPixmap,
)

try:
    import psutil
    PSUTIL_OK = True
except ImportError:
    PSUTIL_OK = False

try:
    import anthropic
    CLAUDE_OK = True
except ImportError:
    CLAUDE_OK = False

try:
    from guppy_daemon import get_daemon_manager, get_window_context
    _DAEMON_AVAILABLE = True
except ImportError:
    _DAEMON_AVAILABLE = False

try:
    from utils.env_bootstrap import load_env_file
    load_env_file()
except Exception:
    pass

logger = logging.getLogger("OmnissiahHub")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(asctime)s %(name)s: %(message)s", "%H:%M:%S"))
    logger.addHandler(handler)
    try:
        _RUNTIME.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(_RUNTIME / "hub.log", encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("[%(levelname)s] %(asctime)s %(name)s: %(message)s"))
        logger.addHandler(file_handler)
    except Exception:
        pass

# -- Resolve paths --------------------------------------------------------------
_HERE = Path(__file__).parent
_VENV_PYTHON = _HERE / ".venv" / "Scripts" / "python.exe"
PYTHON = str(_VENV_PYTHON) if _VENV_PYTHON.exists() else sys.executable

# -- Theme colours - Warhammer 40K / Knights Templar gothic martial -----------
BG   = "#080608"   # near-black, slight warm tint
BG2  = "#0d0a0e"   # panel backgrounds
BG3  = "#13101a"   # input/card backgrounds
BORD = "#2a1f3d"   # subtle border
TEXT = "#d8ccc0"   # warm parchment text
DIM  = "#5a4a6a"   # dimmed
ACNT = "#b8860b"   # dark gold / mechanicus brass
ACNT2= "#9a6e08"   # deeper brass
RED  = "#8b1a1a"   # anointed red
SILV = "#c0b8c8"   # silver/steel highlight

# -- Agent definitions ----------------------------------------------------------
AGENTS = [
    {"id": "guppy",   "label": "GUPPY",   "title": "Magos Administratum", "script": "guppy_ui.py",   "accent": "#00c8ff"},
    {"id": "merlin",  "label": "MERLIN",  "title": "Lexmechanic",         "script": "merlin_ui.py",  "accent": "#c9a84c"},
    {"id": "council", "label": "COUNCIL", "title": "Conclave of the Omnissiah", "script": "council_ui.py", "accent": "#8888ee"},
]


def _is_set(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def _safe_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)).strip())
    except Exception:
        return default


def _cloudflare_cert_paths() -> list[Path]:
    home = Path.home()
    return [
        home / ".cloudflared" / "cert.pem",
        home / ".cloudflare-warp" / "cert.pem",
        home / "cloudflare-warp" / "cert.pem",
    ]


def _check_api_server(port: int = 8080) -> str:
    """Return LIVE if something is accepting on localhost:port, else DOWN."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return "LIVE"
    except OSError:
        return "DOWN"


def _check_cloudflared() -> str:
    """Return RUNNING if a cloudflared process is found, else STOPPED."""
    if not PSUTIL_OK:
        return "UNKNOWN"
    try:
        for proc in psutil.process_iter(["name"]):
            if "cloudflared" in (proc.info.get("name") or "").lower():
                return "RUNNING"
    except Exception:
        pass
    return "STOPPED"


def _check_auth_config() -> str:
    """Return CONFIGURED / PARTIAL / DEV based on JWT + Turnstile env vars."""
    _dev_jwt = {"", "dev-secret-key-change-in-production"}
    _dev_ts  = {"", "dev-turnstile-secret"}
    jwt_ok = os.environ.get("GUPPY_JWT_SECRET", "") not in _dev_jwt
    ts_ok  = os.environ.get("TURNSTILE_SECRET", "") not in _dev_ts
    if jwt_ok and ts_ok:
        return "CONFIGURED"
    if jwt_ok or ts_ok:
        return "PARTIAL"
    return "DEV MODE"


def _model_for_agent(agent_id: str) -> str:
    if agent_id == "guppy":
        return (os.environ.get("OLLAMA_MODEL", "guppy") or "guppy").strip()
    if agent_id == "merlin":
        return (os.environ.get("MERLIN_LOCAL_MODEL", "merlin") or "merlin").strip()
    if agent_id == "council":
        return (os.environ.get("COUNCIL_LOCAL_MODEL") or os.environ.get("MERLIN_LOCAL_MODEL", "merlin") or "merlin").strip()
    return ""


def _tail_agent_performance(limit: int = 200) -> list[dict]:
    path = _RUNTIME / "agent_performance.jsonl"
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    out = []
    for line in lines[-max(20, int(limit)):]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                out.append(row)
        except Exception:
            continue
    return out


def _tail_session_events(limit: int = 200) -> list[dict]:
    path = _RUNTIME / "session_events.jsonl"
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    out = []
    for line in lines[-max(20, int(limit)):]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                out.append(row)
        except Exception:
            continue
    return out


def _pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = max(0.0, min(1.0, q)) * (len(ordered) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(ordered) - 1)
    frac = rank - lo
    return float(ordered[lo] * (1.0 - frac) + ordered[hi] * frac)


def _rolling_agent_stats(perf_rows: list[dict], session_rows: list[dict], window_seconds: int = 900) -> dict[str, dict]:
    now = datetime.now(timezone.utc)
    stats = {
        aid: {
            "latest": {},
            "latencies": [],
            "inflight": 0,
            "seen_start_ids": set(),
            "seen_complete_ids": set(),
        }
        for aid in ("guppy", "merlin", "council_guppy", "council_merlin")
    }

    cutoff = now.timestamp() - max(60, int(window_seconds))

    for row in perf_rows:
        aid = str(row.get("agent", "")).strip().lower()
        if aid == "council":
            panel = str(row.get("panel", "")).strip().lower()
            if panel in {"guppy", "merlin"}:
                aid = f"council_{panel}"
        if aid not in stats:
            continue
        ts = _parse_iso_ts(str(row.get("ts", "")))
        if ts is None or ts.timestamp() < cutoff:
            continue

        stats[aid]["latest"] = row
        evt = str(row.get("event", "")).strip().lower()
        req_id = str(row.get("request_id", "")).strip()

        if evt == "request_started":
            if req_id:
                stats[aid]["seen_start_ids"].add(req_id)
            else:
                stats[aid]["inflight"] += 1

        if evt == "request_complete":
            if isinstance(row.get("latency_ms"), (int, float)):
                stats[aid]["latencies"].append(float(row.get("latency_ms")))
            if req_id:
                stats[aid]["seen_complete_ids"].add(req_id)
            else:
                stats[aid]["inflight"] = max(0, stats[aid]["inflight"] - 1)

    # Use UI session events as a fallback queue signal for Guppy when request IDs are missing.
    for row in session_rows:
        aid = "guppy" if str(row.get("source", "")).strip().lower() == "ui" else ""
        if aid not in stats:
            continue
        ts = _parse_iso_ts(str(row.get("ts", "")))
        if ts is None or ts.timestamp() < cutoff:
            continue
        evt = str(row.get("event", "")).strip().lower()
        if evt == "request_started":
            stats[aid]["inflight"] += 1
        elif evt == "request_finished":
            stats[aid]["inflight"] = max(0, stats[aid]["inflight"] - 1)

    out = {}
    for aid, payload in stats.items():
        started = payload["seen_start_ids"]
        completed = payload["seen_complete_ids"]
        id_inflight = len(started - completed)
        queue_depth = max(0, payload["inflight"] + id_inflight)
        lats = payload["latencies"]
        out[aid] = {
            "latest": payload["latest"],
            "queue_depth": queue_depth,
            "p95_ms": round(_pct(lats, 0.95), 1) if lats else 0.0,
            "p99_ms": round(_pct(lats, 0.99), 1) if lats else 0.0,
            "samples": len(lats),
        }
    return out


def _parse_iso_ts(value: str | None) -> Optional[datetime]:
    if not value:
        return None
    try:
        norm = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(norm)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _warm_ollama_model(model: str, keep_alive: str = "20m") -> tuple[bool, str]:
    payload = {
        "model": model,
        "prompt": "warmup",
        "stream": False,
        "keep_alive": keep_alive,
        "options": {"num_predict": 1},
    }
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
        if body.get("error"):
            return False, str(body.get("error"))
        return True, "warm"
    except Exception as e:
        return False, str(e)


# ==============================================================================
# HubManager - AI routing brain
# ==============================================================================
class HubManager(QObject):
    """Determines which agent to recommend based on window context and load."""

    recommendation_changed = Signal(str, str)   # (agent_id, reason)

    def __init__(self):
        super().__init__()
        self._mode = "claude" if (CLAUDE_OK and os.environ.get("ANTHROPIC_API_KEY")) else "ollama"
        self._context_summary    = "No context available"
        self._recommendation_summary = "Standing by."
        self._recommended_agent  = "guppy"
        self._auto_last_action   = "Idle"
        logger.info(f"HubManager initialized with mode: {self.mode}")

    @property
    def mode(self) -> str:
        if not CLAUDE_OK:
            return "DISABLED"
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "CLAUDE"
        return "OLLAMA"

    def recommend(self, title: str, running_agents: list[str]) -> str:
        """Pick best agent for current window title."""
        t = title.lower()
        if any(k in t for k in ("merlin", "wizard", "magic")):
            rec = "merlin"
        elif any(k in t for k in ("council", "joint")):
            rec = "council"
        else:
            rec = "guppy"
        logger.debug(f"Recommending {rec} for '{title}'")
        return rec

    def ask(self, prompt: str) -> str:
        """Send a question to Claude or fallback."""
        if os.environ.get("ANTHROPIC_API_KEY") and CLAUDE_OK:
            try:
                client = anthropic.Anthropic()
                msg = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=512,
                    messages=[{"role": "user", "content": prompt}],
                )
                return msg.content[0].text if msg.content else "No response from Omnissiah."
            except Exception as e:
                return f"Omnissiah error: {e}"
        return "Claude unavailable: ANTHROPIC_API_KEY not set."

    def update_context(self, title: str, running: list[str]):
        self._context_summary = title or "No context"
        rec = self.recommend(title, running)
        self._recommended_agent = rec
        self._recommendation_summary = f"Recommended: {rec}"
        self.recommendation_changed.emit(rec, self._recommendation_summary)


# ==============================================================================
# GlowOrb - pulsing G orb (no external image files needed)
# ==============================================================================
class GlowOrb(QWidget):
    """
    state: 'idle' | 'running' | 'pulse_on' | 'pulse_off'
    Draws a glowing G orb. No external image files needed.
    """
    def __init__(self, size=28, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.state  = "idle"
        self._alpha = 180
        self._dir   = 1
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._pulse)

    def set_state(self, state: str):
        self.state = state
        if state in ("pulse_on", "pulse_off", "running"):
            self._timer.start(60)
        else:
            self._timer.stop()
        self.update()

    def _pulse(self):
        self._alpha += self._dir * 12
        if self._alpha >= 255:
            self._alpha = 255; self._dir = -1
        elif self._alpha <= 80:
            self._alpha = 80;  self._dir =  1
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy, r = self.width()//2, self.height()//2, self.width()//2 - 2

        accent = QColor(ACNT)
        glow   = QColor(ACNT)
        glow.setAlpha(self._alpha if self.state != "idle" else 120)

        # Glow ring
        pen = QPen(glow, 2)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(cx - r, cy - r, r*2, r*2)

        # Fill gradient
        grad = QRadialGradient(cx, cy, r)
        inner = QColor(BG3)
        inner.setAlpha(220)
        grad.setColorAt(0.0, inner)
        grad.setColorAt(1.0, QColor(ACNT2 if self.state != "idle" else BG2))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(cx - r+1, cy - r+1, (r-1)*2, (r-1)*2)

        # "G" letter
        p.setPen(QPen(accent if self.state != "idle" else QColor(DIM), 1))
        font = QFont("Segoe UI", r - 4, QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "G")


# ==============================================================================
# ManagerCard - UI card for HubManager
# ==============================================================================
class ManagerCard(QFrame):
    def __init__(self, manager: HubManager, parent=None):
        super().__init__(parent)
        self._mgr = manager
        self.setObjectName("ManagerCard")
        self._build_ui()
        manager.recommendation_changed.connect(self._on_rec)

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(2)

        top = QHBoxLayout()
        icon_lbl = QLabel(">>")
        icon_lbl.setStyleSheet(f"color:{ACNT}; background:transparent; border:none;")
        lbl = QLabel("OMNISSIAH")
        lbl.setStyleSheet(f"color:{ACNT}; background:transparent; border:none;")
        lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        sub = QLabel("Omnissiah's Vigil")
        sub.setStyleSheet(f"color:{DIM}; background:transparent; border:none;")
        sub.setFont(QFont("Segoe UI", 7))
        top.addWidget(icon_lbl)
        top.addWidget(lbl)
        top.addWidget(sub)
        top.addStretch()
        lay.addLayout(top)

        self._mode_lbl = QLabel(self._mgr.mode)
        self._mode_lbl.setStyleSheet(f"color:{DIM}; background:transparent; border:none;")
        self._mode_lbl.setFont(QFont("Segoe UI", 7))
        lay.addWidget(self._mode_lbl)

        self._rec_lbl = QLabel(self._mgr._recommendation_summary)
        self._rec_lbl.setStyleSheet(f"color:{TEXT}; background:transparent; border:none;")
        self._rec_lbl.setFont(QFont("Segoe UI", 7))
        lay.addWidget(self._rec_lbl)

        self._ctx_lbl = QLabel(self._mgr._context_summary)
        self._ctx_lbl.setStyleSheet(f"color:{DIM}; background:transparent; border:none;")
        self._ctx_lbl.setFont(QFont("Segoe UI", 7))
        self._ctx_lbl.setWordWrap(True)
        lay.addWidget(self._ctx_lbl)

        self._update_style()

    def _update_style(self):
        active = self._mgr.mode not in ("DISABLED",)
        col = ACNT if active else DIM
        self.setStyleSheet(
            f"ManagerCard{{background:{BG2};"
            f"border:1px solid {col}44;border-radius:6px;}}"
        )

    def _on_rec(self, agent_id: str, reason: str):
        self._rec_lbl.setText(reason)
        self._ctx_lbl.setText(self._mgr._context_summary)
        self._mode_lbl.setText(self._mgr.mode)
        self._update_style()

    def refresh(self):
        self._mode_lbl.setText(self._mgr.mode)
        self._rec_lbl.setText(self._mgr._recommendation_summary)
        self._ctx_lbl.setText(self._mgr._context_summary)


# ==============================================================================
# StatusSettingsCard - Account/login/customization view
# ==============================================================================
class StatusSettingsCard(QFrame):
    _REMOTE_CHECK_INTERVAL = 5  # refresh() calls between live checks

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StatusSettingsCard")
        self._refresh_counter = 0
        self._remote_cache = ("DOWN", "STOPPED", "DEV MODE")  # api, tunnel, auth
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(2)

        title = QLabel("SYSTEM STATUS / SETTINGS")
        title.setStyleSheet(f"color:{ACNT}; background:transparent; border:none;")
        title.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        lay.addWidget(title)

        self._accounts_lbl = QLabel("")
        self._accounts_lbl.setStyleSheet(f"color:{TEXT}; background:transparent; border:none;")
        self._accounts_lbl.setFont(QFont("Consolas", 7))
        self._accounts_lbl.setWordWrap(True)
        lay.addWidget(self._accounts_lbl)

        self._remote_lbl = QLabel("")
        self._remote_lbl.setStyleSheet(f"color:{TEXT}; background:transparent; border:none;")
        self._remote_lbl.setFont(QFont("Consolas", 7))
        self._remote_lbl.setWordWrap(True)
        lay.addWidget(self._remote_lbl)

        self._settings_lbl = QLabel("")
        self._settings_lbl.setStyleSheet(f"color:{DIM}; background:transparent; border:none;")
        self._settings_lbl.setFont(QFont("Consolas", 7))
        self._settings_lbl.setWordWrap(True)
        lay.addWidget(self._settings_lbl)

        self.setStyleSheet(
            f"StatusSettingsCard{{background:{BG2};"
            f"border:1px solid {ACNT}33;border-radius:6px;}}"
        )
        self.refresh()

    def refresh(self):
        # ── Credentials / backends (cheap, every tick) ──────────────────────
        gmail_creds = os.environ.get("GMAIL_CREDENTIALS_PATH", "").strip()
        gmail_ok = bool(gmail_creds and Path(gmail_creds).exists())
        cf_ok = any(p.exists() for p in _cloudflare_cert_paths())

        try:
            from kokoro import KPipeline as _KP  # noqa: F401
            tts_backend = "KOKORO"
        except Exception:
            tts_backend = "SAPI"

        try:
            from faster_whisper import WhisperModel as _WM  # noqa: F401
            stt_backend = "WHISPER"
        except Exception:
            try:
                import speech_recognition as _sr  # noqa: F401
                stt_backend = "GOOGLE"
            except Exception:
                stt_backend = "NONE"

        accounts = [
            f"Claude: {'READY' if _is_set('ANTHROPIC_API_KEY') else 'MISSING'}",
            f"Spotify: {'READY' if (_is_set('SPOTIFY_CLIENT_ID') and _is_set('SPOTIFY_CLIENT_SECRET')) else 'MISSING'}",
            f"Gmail Creds: {'READY' if gmail_ok else 'MISSING'}",
            f"Cloudflare Cert: {'READY' if cf_ok else 'MISSING'}",
            f"Voice TTS: {tts_backend}",
            f"Voice STT: {stt_backend}",
        ]
        self._accounts_lbl.setText(" | ".join(accounts))

        # ── Remote / Phase-3 health (throttled: check every 5 ticks) ────────
        self._refresh_counter += 1
        if self._refresh_counter >= self._REMOTE_CHECK_INTERVAL:
            self._refresh_counter = 0
            api_state    = _check_api_server()
            tunnel_state = _check_cloudflared()
            auth_state   = _check_auth_config()
            self._remote_cache = (api_state, tunnel_state, auth_state)
        else:
            api_state, tunnel_state, auth_state = self._remote_cache

        remote = [
            f"API Server: {api_state}",
            f"CF Tunnel: {tunnel_state}",
            f"Auth: {auth_state}",
        ]
        self._remote_lbl.setText(" | ".join(remote))

        # ── Model settings (cheap, every tick) ──────────────────────────────
        settings = [
            f"ANTHROPIC_MODEL={os.environ.get('ANTHROPIC_MODEL', 'claude-sonnet-4-6')}",
            f"ANTHROPIC_BACKUP_MODEL={os.environ.get('ANTHROPIC_BACKUP_MODEL', 'claude-haiku-4-5-20251001')}",
            f"OLLAMA_MODEL={os.environ.get('OLLAMA_MODEL', 'guppy')}",
            f"MERLIN_LOCAL_MODEL={os.environ.get('MERLIN_LOCAL_MODEL', 'merlin')}",
            f"MERLIN_HAIKU_BOOST={os.environ.get('MERLIN_HAIKU_BOOST', '0')}",
            f"MERLIN_HAIKU_BOOST_MIN_CHARS={_safe_int('MERLIN_HAIKU_BOOST_MIN_CHARS', 180)}",
        ]
        self._settings_lbl.setText(" | ".join(settings))


# ==============================================================================
# OrchestrationCard - live routing/latency panel + warmup controls
# ==============================================================================
class OrchestrationCard(QFrame):
    _REFRESH_INTERVAL = 2
    _WINDOW_SECONDS = 900

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("OrchestrationCard")
        self._tick_counter = 0
        self._rows = {}
        self._row_order = []
        self._last_queue_depth = {}
        self._warm_state = {}
        self._warm_lock = threading.Lock()
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(3)

        title = QLabel("ORCHESTRATION / ROUTING")
        title.setStyleSheet(f"color:{ACNT}; background:transparent; border:none;")
        title.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        lay.addWidget(title)

        row_defs = (
            ("guppy", "GUPPY"),
            ("merlin", "MERLIN"),
            ("council_guppy", "COUNCIL:G"),
            ("council_merlin", "COUNCIL:M"),
        )
        for aid, label in row_defs:
            row = QLabel(f"{label:<8} route=idle p95=- p99=- qd=0 status=-")
            row.setStyleSheet(f"color:{DIM}; background:transparent; border:none;")
            row.setFont(QFont("Consolas", 7))
            self._rows[aid] = row
            self._row_order.append((aid, label))
            lay.addWidget(row)

        self._warm_lbl = QLabel("Warmup: idle")
        self._warm_lbl.setStyleSheet(f"color:{DIM}; background:transparent; border:none;")
        self._warm_lbl.setFont(QFont("Consolas", 7))
        lay.addWidget(self._warm_lbl)

        btns = QHBoxLayout()
        self._warm_all_btn = QPushButton("WARM ALL")
        self._warm_all_btn.setFixedHeight(22)
        self._warm_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._warm_all_btn.setFont(QFont("Segoe UI", 7))
        self._warm_all_btn.clicked.connect(self._warm_all)
        self._warm_all_btn.setStyleSheet(
            f"QPushButton{{background:{BG2};color:{ACNT};"
            f"border:1px solid {ACNT}66;border-radius:4px;"
            f"font-size:8px;font-weight:bold;letter-spacing:1px;}}"
            f"QPushButton:hover{{background:{ACNT}22;border-color:{ACNT};}}"
        )

        self._warm_local_btn = QPushButton("WARM G+M")
        self._warm_local_btn.setFixedHeight(22)
        self._warm_local_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._warm_local_btn.setFont(QFont("Segoe UI", 7))
        self._warm_local_btn.clicked.connect(self._warm_local_pair)
        self._warm_local_btn.setStyleSheet(
            f"QPushButton{{background:{BG2};color:{SILV};"
            f"border:1px solid {SILV}55;border-radius:4px;"
            f"font-size:8px;font-weight:bold;letter-spacing:1px;}}"
            f"QPushButton:hover{{background:{SILV}22;border-color:{SILV};}}"
        )

        btns.addWidget(self._warm_all_btn)
        btns.addWidget(self._warm_local_btn)
        lay.addLayout(btns)

        self.setStyleSheet(
            f"OrchestrationCard{{background:{BG2};"
            f"border:1px solid {ACNT}33;border-radius:6px;}}"
        )

    def _warm_models_async(self, targets: list[tuple[str, str]]):
        if not targets:
            return

        with self._warm_lock:
            for aid, model in targets:
                self._warm_state[aid] = f"warming:{model}"

        def _job():
            for aid, model in targets:
                ok, info = _warm_ollama_model(model)
                with self._warm_lock:
                    self._warm_state[aid] = "warm" if ok else f"error:{info[:40]}"

        t = threading.Thread(target=_job, daemon=True)
        t.start()

    def _warm_all(self):
        targets = []
        seen = set()
        for aid in ("guppy", "merlin", "council"):
            model = _model_for_agent(aid)
            if model and model not in seen:
                seen.add(model)
                targets.append((aid, model))
        self._warm_models_async(targets)

    def _warm_local_pair(self):
        targets = []
        for aid in ("guppy", "merlin"):
            model = _model_for_agent(aid)
            if model:
                targets.append((aid, model))
        self._warm_models_async(targets)

    def refresh(self):
        self._tick_counter += 1
        if self._tick_counter % self._REFRESH_INTERVAL:
            self._paint_warm_state_only()
            return

        perf_rows = _tail_agent_performance(limit=900)
        session_rows = _tail_session_events(limit=900)
        now = datetime.now(timezone.utc)
        by_agent = _rolling_agent_stats(perf_rows, session_rows, window_seconds=self._WINDOW_SECONDS)

        for aid, label in self._row_order:
            lbl = self._rows[aid]
            row_stats = by_agent.get(aid, {})
            row = row_stats.get("latest", {})
            route = str(row.get("mode", "idle"))[:18]
            p95 = row_stats.get("p95_ms", 0.0)
            p99 = row_stats.get("p99_ms", 0.0)
            p95_s = f"{p95:.0f}ms" if p95 else "-"
            p99_s = f"{p99:.0f}ms" if p99 else "-"
            qd = int(row_stats.get("queue_depth", 0) or 0)
            prev_qd = int(self._last_queue_depth.get(aid, qd))
            if qd > prev_qd:
                qd_arrow = "↑"
            elif qd < prev_qd:
                qd_arrow = "↓"
            else:
                qd_arrow = "→"
            status = str(row.get("status", "-")).upper()[:6]

            ts = _parse_iso_ts(str(row.get("ts", "")))
            age_s = "-"
            if ts is not None:
                age_s = f"{max(0, int((now - ts).total_seconds()))}s"

            color = DIM
            if status == "OK" and qd == 0:
                color = "#6adfb8"
            elif qd > 0:
                color = ACNT
            elif status == "ERROR":
                color = "#c87050"

            lbl.setText(
                f"{label:<10} route={route:<12} p95={p95_s:<6} p99={p99_s:<6} "
                f"qd={qd:<2}{qd_arrow} age={age_s:<4} {status}"
            )
            lbl.setStyleSheet(f"color:{color}; background:transparent; border:none;")
            self._last_queue_depth[aid] = qd

        self._paint_warm_state_only()

    def _paint_warm_state_only(self):
        with self._warm_lock:
            if not self._warm_state:
                self._warm_lbl.setText("Warmup: idle")
                self._warm_lbl.setStyleSheet(f"color:{DIM}; background:transparent; border:none;")
                return
            segs = [f"{aid}:{state}" for aid, state in sorted(self._warm_state.items())]

        txt = "Warmup: " + " | ".join(segs)
        col = DIM
        if "error:" in txt:
            col = "#c87050"
        elif "warming:" in txt:
            col = ACNT
        elif "warm" in txt:
            col = "#6adfb8"
        self._warm_lbl.setText(txt)
        self._warm_lbl.setStyleSheet(f"color:{col}; background:transparent; border:none;")


# ==============================================================================
# AgentCard - UI card per agent
# ==============================================================================
class AgentCard(QFrame):
    launch_requested = Signal(str)
    stop_requested   = Signal(str)

    def __init__(self, agent: dict, parent=None):
        super().__init__(parent)
        self._agent  = agent
        self._proc: Optional[subprocess.Popen] = None
        self._start_time: Optional[float] = None
        self._recommended = False
        self._user_stopped = False
        self._crash_count = 0
        self.setObjectName("AgentCard")
        self._build_ui()

    # -- UI -----------------------------------------------------------------
    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(2)

        top = QHBoxLayout()
        ac  = self._agent["accent"]

        self._icon_lbl = QLabel(">>")
        self._icon_lbl.setStyleSheet(f"color:{ac}; background:transparent; border:none;")

        self._label_lbl = QLabel(self._agent["label"])
        lf = QFont("Segoe UI", 8, QFont.Weight.Bold)
        lf.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
        self._label_lbl.setFont(lf)
        self._label_lbl.setStyleSheet(f"color:{ac}; background:transparent; border:none;")

        self._rec_lbl = QLabel("")
        self._rec_lbl.setStyleSheet("color:#ffaa44; background:transparent; border:none;")
        self._rec_lbl.setFont(QFont("Segoe UI", 7))

        sub = QLabel(self._agent["title"])
        sub.setStyleSheet(f"color:{DIM}; background:transparent; border:none;")
        sub.setFont(QFont("Segoe UI", 7))

        top.addWidget(self._icon_lbl)
        top.addWidget(self._label_lbl)
        top.addWidget(self._rec_lbl)
        top.addStretch()
        top.addWidget(sub)
        lay.addLayout(top)

        bot = QHBoxLayout()
        self._status_lbl = QLabel("STOPPED")
        self._status_lbl.setStyleSheet(f"color:{DIM}; background:transparent; border:none;")
        self._status_lbl.setFont(QFont("Segoe UI", 7))

        self._uptime_lbl = QLabel("")
        self._uptime_lbl.setStyleSheet(f"color:{DIM}; background:transparent; border:none;")
        self._uptime_lbl.setFont(QFont("Segoe UI", 7))
        self._activity_lbl = QLabel("")
        self._activity_lbl.setStyleSheet(f"color:{DIM}; background:transparent; border:none;")
        self._activity_lbl.setFont(QFont("Segoe UI", 7))

        self._btn = QPushButton("AWAKEN")
        self._btn.setFixedHeight(22)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setFont(QFont("Segoe UI", 7))
        self._btn.clicked.connect(self._on_btn)

        self._unstall_btn = QPushButton("⚡  UNSTALL")
        self._unstall_btn.setFixedHeight(22)
        self._unstall_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._unstall_btn.setFont(QFont("Segoe UI", 7))
        self._unstall_btn.setVisible(False)
        self._unstall_btn.clicked.connect(self._on_unstall)

        bot.addWidget(self._status_lbl)
        bot.addWidget(self._uptime_lbl)
        bot.addStretch()
        bot.addWidget(self._activity_lbl)
        bot.addWidget(self._unstall_btn)
        bot.addWidget(self._btn)
        lay.addLayout(bot)

        self._update_style(running=False)

    # -- Style helpers ----------------------------------------------------
    def _update_style(self, running: bool, stalled: bool = False):
        ac = self._agent["accent"]
        if running and not stalled:
            self._status_lbl.setStyleSheet(
                f"color:{ac}; background:transparent; border:none; "
                f"font-size:8px; font-weight:bold; letter-spacing:1px;"
            )
            self._status_lbl.setText(">> ANOINTED")
            self._btn.setText("[] SLUMBER")
            self._btn.setStyleSheet(
                "QPushButton{background:transparent;color:#c87050;"
                "border:1px solid #c8705055;border-radius:4px;"
                "font-size:8px;font-weight:bold;letter-spacing:1px;}"
                "QPushButton:hover{border-color:#c87050;background:#c8705022;}"
                "QPushButton:pressed{background:#c8705033;}"
            )
            self.setStyleSheet(
                f"AgentCard{{background:{BG2};"
                f"border:1px solid {ac}55;border-left:3px solid {ac};"
                f"border-radius:6px;}}"
            )
            self._unstall_btn.setVisible(False)
        elif running and stalled:
            # Process alive but heartbeat stale - agent is frozen/stalled
            AMBER = "#d4860a"
            self._status_lbl.setStyleSheet(
                f"color:{AMBER}; background:transparent; border:none; "
                f"font-size:8px; font-weight:bold; letter-spacing:1px;"
            )
            self._status_lbl.setText("!! STALLED")
            self._btn.setText("[] SLUMBER")
            self._btn.setStyleSheet(
                "QPushButton{background:transparent;color:#c87050;"
                "border:1px solid #c8705055;border-radius:4px;"
                "font-size:8px;font-weight:bold;letter-spacing:1px;}"
                "QPushButton:hover{border-color:#c87050;background:#c8705022;}"
                "QPushButton:pressed{background:#c8705033;}"
            )
            self.setStyleSheet(
                f"AgentCard{{background:{BG2};"
                f"border:1px solid {AMBER}88;border-left:3px solid {AMBER};"
                f"border-radius:6px;}}"
            )
            self._unstall_btn.setVisible(True)
            self._unstall_btn.setStyleSheet(
                "QPushButton{background:transparent;color:#d4860a;"
                "border:1px solid #d4860a88;border-radius:4px;"
                "font-size:8px;font-weight:bold;letter-spacing:1px;}"
                "QPushButton:hover{border-color:#d4860a;background:#d4860a22;}"
                "QPushButton:pressed{background:#d4860a33;}"
            )
        else:
            self._status_lbl.setStyleSheet(
                f"color:{DIM}; background:transparent; border:none; "
                f"font-size:8px; letter-spacing:1px;"
            )
            self._status_lbl.setText("-- DORMANT")
            self._btn.setText(">> AWAKEN")
            self._btn.setStyleSheet(
                f"QPushButton{{background:{ac}1a;color:{ac}88;"
                f"border:1px solid {ac}44;border-radius:4px;"
                f"font-size:8px;font-weight:bold;letter-spacing:1px;}}"
                f"QPushButton:hover{{background:{ac}33;color:{ac};"
                f"border-color:{ac};}}"
                f"QPushButton:pressed{{background:{ac}44;}}"
            )
            border = ac if self._recommended else BORD
            self.setStyleSheet(
                f"AgentCard{{background:{BG3};"
                f"border:1px solid {border}44;border-radius:6px;}}"
            )
            self._unstall_btn.setVisible(False)
    def _is_stalled(self) -> bool:
        """Return True if the process is alive but its heartbeat file is stale."""
        if not self.is_running():
            return False
        hb = _RUNTIME / f"{self._agent['id']}.heartbeat"
        if not hb.exists():
            return False   # no heartbeat file yet - agent may not have started writing
        try:
            ts = float(hb.read_text(encoding="utf-8").strip())
            return (time.time() - ts) > HB_STALE_SECS
        except Exception:
            return False

    def _get_activity(self) -> str:
        """Read the activity state file written by the agent. Returns: thinking/speaking/idle."""
        act_file = _RUNTIME / f"{self._agent['id']}.activity"
        if not act_file.exists():
            return "idle"
        try:
            return act_file.read_text(encoding="utf-8").strip() or "idle"
        except Exception:
            return "idle"

    def _detect_existing_process(self) -> bool:
        """
        Scan running processes for one launched with our script name.
        Attaches self._proc as a psutil.Process so is_running() works.
        Only called when self._proc is None (hub didn't launch the agent).
        """
        if not PSUTIL_OK:
            return False
        script = self._agent["script"]   # e.g. guppy_ui.py
        try:
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    cmdline = proc.info.get("cmdline") or []
                    if any(script in arg for arg in cmdline):
                        self._proc = proc
                        if self._start_time is None:
                            self._start_time = proc.create_time()
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        return False

    def is_running(self) -> bool:
        if self._proc is None:
            self._detect_existing_process()
        if self._proc is None:
            return False
        # subprocess.Popen has poll(); psutil.Process has is_running()
        if hasattr(self._proc, "poll"):
            return self._proc.poll() is None
        try:
            return self._proc.is_running() and self._proc.status() != psutil.STATUS_ZOMBIE
        except Exception:
            return False

    def launch(self):
        if self.is_running():
            return
        self._user_stopped = False
        # Do NOT reset _crash_count here - reset only happens after a stable run
        # or after a deliberate stop(). Resetting on every launch broke the cap.
        script = _HERE / self._agent["script"]
        self._proc = subprocess.Popen(
            [PYTHON, str(script)],
            cwd=str(_HERE),
        )
        self._start_time = time.time()
        self._update_style(running=True)
        self._uptime_lbl.setText("0s")

    def stop(self):
        if self._proc and self.is_running():
            self._user_stopped = True
            if hasattr(self._proc, "terminate"): self._proc.terminate()
            else:
                try: self._proc.kill()
                except Exception: pass
        self._proc = None
        self._start_time = None
        self._crash_count = 0  # Deliberate stop - reset so next launch gets full attempts
        self._update_style(running=False)
        self._uptime_lbl.setText("")

    def _schedule_restart(self, delay_ms: int = 5000):
        if self._crash_count >= 3:
            logger.warning(f"{self._agent['id']} reached max restart attempts.")
            return
        self._crash_count += 1
        self._status_lbl.setText(f"~~ RECALLING ({self._crash_count}/3)")
        self._status_lbl.setStyleSheet(
            f"color:{ACNT}; background:transparent; border:none; "
            f"font-size:8px; letter-spacing:1px;"
        )
        QTimer.singleShot(delay_ms, self.launch)

    # Processes that exit after running at least this long are assumed to have
    # been closed intentionally by the user - don't auto-restart them.
    _STABLE_UPTIME_SECS = 30

    def tick(self):
        """Called by HubWindow timer - refresh running state & uptime."""
        alive = self.is_running()
        if alive and self._start_time:
            secs = int(time.time() - self._start_time)
            if secs < 60:
                self._uptime_lbl.setText(f"{secs}s")
            else:
                m, s = divmod(secs, 60)
                self._uptime_lbl.setText(f"{m}m{s:02d}s")
            stalled = self._is_stalled()
            # -- Activity state display -----------------------------------
            act = self._get_activity()
            act_map = {
                "thinking":  ("⧖ THINKING",  "#d4860a"),
                "speaking":  ("◈ SPEAKING",  "#6adfb8"),
                "listening": ("◎ LISTENING", "#8888ee"),
            }
            if act in act_map and not stalled:
                lbl, col = act_map[act]
                self._activity_lbl.setText(lbl)
                self._activity_lbl.setStyleSheet(
                    f"color:{col}; background:transparent; border:none; "
                    f"font-size:7px; font-weight:bold; letter-spacing:1px;"
                )
            else:
                self._activity_lbl.setText("")
            self._update_style(running=True, stalled=stalled)
        elif not alive and self._proc is not None:
            uptime = time.time() - self._start_time if self._start_time else 0
            self._proc = None
            self._start_time = None
            self._update_style(running=False)
            self._uptime_lbl.setText("")
            self._activity_lbl.setText("")
            if not self._user_stopped:
                if uptime >= self._STABLE_UPTIME_SECS:
                    # Ran long enough to be intentional - user closed the window.
                    # Reset crash count so next manual launch gets fresh attempts.
                    logger.info(
                        f"{self._agent['id']} exited after {uptime:.0f}s "
                        f"(user close assumed - no restart)."
                    )
                    self._crash_count = 0
                else:
                    # Died within startup window - likely a real crash.
                    logger.warning(
                        f"{self._agent['id']} exited after {uptime:.0f}s "
                        f"(crash assumed - scheduling restart)."
                    )
                    self._schedule_restart()

    def set_recommended(self, is_rec: bool):
        self._recommended = is_rec
        self._rec_lbl.setText("*" if is_rec else "")
        if not self.is_running():
            self._update_style(running=False)

    def _on_btn(self):
        if self.is_running():
            self.stop_requested.emit(self._agent["id"])
        else:
            self.launch_requested.emit(self._agent["id"])


    def _on_unstall(self):
        """Kill a stalled process and restart it immediately."""
        if self._proc is not None:
            try:
                if hasattr(self._proc, "terminate"):
                    self._proc.terminate()
                else:
                    self._proc.kill()
            except Exception:
                pass
        self._proc = None
        self._start_time = None
        self._crash_count = 0
        self._unstall_btn.setVisible(False)
        hb = _RUNTIME / f"{self._agent['id']}.heartbeat"
        try: hb.unlink(missing_ok=True)
        except Exception: pass
        act = _RUNTIME / f"{self._agent['id']}.activity"
        try: act.unlink(missing_ok=True)
        except Exception: pass
        QTimer.singleShot(500, self.launch)

# ==============================================================================
# HubWindow - Main application window
# ==============================================================================
class HubWindow(QWidget):
    def __init__(self, manager: HubManager, parent=None):
        super().__init__(parent)
        self._mgr = manager
        self._cards = {}
        self._dragging = False
        self._drag_pos = QPoint()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setStyleSheet(
            f"background:{BG}; border:2px solid {ACNT}44; border-radius:10px;"
        )
        self._build_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)  # tick every second

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(8)

        # -- Gothic title header --------------------------------------------
        hdr = QWidget()
        hdr.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f"stop:0 {ACNT}33,stop:1 {BG2});"
            f"border:1px solid {ACNT}44; border-radius:6px;"
        )
        hdr.setFixedHeight(52)
        hdr_lay = QVBoxLayout(hdr)
        hdr_lay.setContentsMargins(8, 6, 8, 6)
        hdr_lay.setSpacing(2)

        title_lbl = QLabel("*  OMNISSIAH")
        title_font = QFont("Segoe UI", 14, QFont.Weight.Bold)
        title_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4)
        title_lbl.setFont(title_font)
        title_lbl.setStyleSheet(f"color:{ACNT}; background:transparent; border:none;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        sub_lbl = QLabel("MECHANICUS CONTROL HUB")
        sub_font = QFont("Segoe UI", 6)
        sub_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3)
        sub_lbl.setFont(sub_font)
        sub_lbl.setStyleSheet(f"color:{ACNT}66; background:transparent; border:none;")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        hdr_lay.addWidget(title_lbl)
        hdr_lay.addWidget(sub_lbl)
        lay.addWidget(hdr)

        # Manager card at top
        self._mgr_card = ManagerCard(self._mgr, self)
        lay.addWidget(self._mgr_card)

        # Agent cards
        for agent in AGENTS:
            card = AgentCard(agent, self)
            card.launch_requested.connect(self._on_launch)
            card.stop_requested.connect(self._on_stop)
            self._cards[agent["id"]] = card
            lay.addWidget(card)

        controls = QHBoxLayout()
        controls.setSpacing(6)
        self._launch_all_btn = QPushButton(">> AWAKEN ALL")
        self._launch_all_btn.setFixedHeight(28)
        self._launch_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._launch_all_btn.setStyleSheet(
            f"QPushButton{{background:{BG2};color:{ACNT};"
            f"border:1px solid {ACNT}66;border-radius:6px;"
            f"font-size:8px;font-weight:bold;letter-spacing:1px;}}"
            f"QPushButton:hover{{background:{ACNT}22;"
            f"border-color:{ACNT};color:{ACNT};}}"
            f"QPushButton:pressed{{background:{ACNT}33;}}"
        )
        self._launch_all_btn.clicked.connect(self._launch_all)

        self._stop_all_btn = QPushButton("[] SLUMBER ALL")
        self._stop_all_btn.setFixedHeight(28)
        self._stop_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stop_all_btn.setStyleSheet(
            f"QPushButton{{background:{BG2};color:#c87050;"
            f"border:1px solid #c8705055;border-radius:6px;"
            f"font-size:8px;font-weight:bold;letter-spacing:1px;}}"
            f"QPushButton:hover{{background:#c8705022;"
            f"border-color:#c87050;}}"
            f"QPushButton:pressed{{background:#c8705033;}}"
        )
        self._stop_all_btn.clicked.connect(self._stop_all)

        controls.addWidget(self._launch_all_btn)
        controls.addWidget(self._stop_all_btn)
        lay.addLayout(controls)

        # System info
        sys_frame = QFrame(self)
        sys_frame.setStyleSheet(
            f"QFrame{{background:{BG2}; border:1px solid {ACNT}33; border-radius:6px;}}"
        )
        sys_lay = QHBoxLayout(sys_frame)
        sys_lay.setContentsMargins(10, 5, 10, 5)
        sys_lay.setSpacing(12)

        self._cpu_lbl = QLabel("CPU  -  --%")
        self._cpu_lbl.setStyleSheet(
            f"color:{DIM}; background:transparent; border:none; "
            f"font-size:8px; font-family:'Consolas'; letter-spacing:1px;"
        )
        self._ram_lbl = QLabel("RAM  -  --%")
        self._ram_lbl.setStyleSheet(
            f"color:{DIM}; background:transparent; border:none; "
            f"font-size:8px; font-family:'Consolas'; letter-spacing:1px;"
        )
        sys_lay.addWidget(self._cpu_lbl)
        sys_lay.addWidget(self._ram_lbl)
        sys_lay.addStretch()
        lay.addWidget(sys_frame)

        # Status/settings summary
        self._status_settings = StatusSettingsCard(self)
        lay.addWidget(self._status_settings)

        # Runtime orchestration summary
        self._orchestration = OrchestrationCard(self)
        lay.addWidget(self._orchestration)

        # Close button
        close_btn = QPushButton("X  DISMISS")
        close_btn.setFixedHeight(22)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{DIM};"
            f"border:1px solid {BORD};border-radius:4px;"
            f"font-size:7px;letter-spacing:1px;}}"
            f"QPushButton:hover{{color:{TEXT};border-color:{DIM};}}"
        )
        close_btn.clicked.connect(self.hide)
        lay.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _tick(self):
        # Update agent statuses
        running = [aid for aid, card in self._cards.items() if card.is_running()]
        # Update context
        if _DAEMON_AVAILABLE:
            try:
                context = get_window_context()
                title = context.get('title', 'No title')
                logger.debug(f"Window context: {title}")
            except Exception as e:
                logger.warning(f"Failed to get window context: {e}")
                title = "Sample Window Title"
        else:
            title = "Sample Window Title"
        self._mgr.update_context(title, running)
        rec = self._mgr._recommended_agent
        for aid, card in self._cards.items():
            card.set_recommended(aid == rec)
            card.tick()

        # Update system info
        if PSUTIL_OK:
            try:
                cpu = psutil.cpu_percent()
                ram = psutil.virtual_memory().percent
                cpu_col = "#c87050" if cpu > 80 else (ACNT if cpu > 50 else DIM)
                ram_col = "#c87050" if ram > 85 else (ACNT if ram > 65 else DIM)
                self._cpu_lbl.setText(f"CPU  -  {cpu:.0f}%")
                self._cpu_lbl.setStyleSheet(
                    f"color:{cpu_col}; background:transparent; border:none; "
                    f"font-size:8px; font-family:'Consolas'; letter-spacing:1px;"
                )
                self._ram_lbl.setText(f"RAM  -  {ram:.0f}%")
                self._ram_lbl.setStyleSheet(
                    f"color:{ram_col}; background:transparent; border:none; "
                    f"font-size:8px; font-family:'Consolas'; letter-spacing:1px;"
                )
            except Exception:
                self._cpu_lbl.setText("CPU  -  ERR")
                self._ram_lbl.setText("RAM  -  ERR")
        else:
            self._cpu_lbl.setText("CPU  -  N/A")
            self._ram_lbl.setText("RAM  -  N/A")

        # Refresh status/settings card
        self._status_settings.refresh()
        self._orchestration.refresh()

    def _on_launch(self, agent_id: str):
        if agent_id in self._cards:
            try:
                self._cards[agent_id].launch()
            except Exception as e:
                logger.error(f"Error launching {agent_id}: {e}")

    def _on_stop(self, agent_id: str):
        if agent_id in self._cards:
            try:
                self._cards[agent_id].stop()
            except Exception as e:
                logger.error(f"Error stopping {agent_id}: {e}")

    def _launch_all(self):
        logger.info("Launching all agents...")
        for card in self._cards.values():
            if not card.is_running():
                card.launch()

    def _stop_all(self):
        logger.info("Stopping all agents...")
        for card in self._cards.values():
            if card.is_running():
                card.stop()

    # Draggable window
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._dragging = False
        event.accept()


# ==============================================================================
# System Tray
# ==============================================================================
class SystemTray(QSystemTrayIcon):
    def __init__(self, window: HubWindow, app: QApplication):
        # Create a simple cog icon
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor(ACNT))  # Purple background
        painter = QPainter(pixmap)
        painter.setPen(QPen(QColor(TEXT), 1))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, ">>")
        painter.end()
        icon = QIcon(pixmap)
        super().__init__(icon, app)
        self._window = window
        self._app = app
        self.setToolTip("Omnissiah Machine Spirit")
        self._setup_menu()
        self.activated.connect(self._on_activated)

    def _setup_menu(self):
        menu = QMenu()
        show_action = QAction("Show Omnissiah", self)
        show_action.triggered.connect(self._window.show)
        menu.addAction(show_action)

        hide_action = QAction("Hide Omnissiah", self)
        hide_action.triggered.connect(self._window.hide)
        menu.addAction(hide_action)

        menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._app.quit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self._window.isVisible():
                self._window.hide()
            else:
                self._window.show()


# ==============================================================================
# Main Application
# ==============================================================================
def main():
    logger.info("Omnissiah starting...")
    try:
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)  # Keep running in tray

        manager = HubManager()
        window = HubWindow(manager)
        tray = SystemTray(window, app)

        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("System tray unavailable; showing Omnissiah window instead.")
            window.show()
            app.setQuitOnLastWindowClosed(True)
        else:
            tray.show()
            window.hide()  # Start hidden

        logger.info("Omnissiah ready.")
        return app.exec()
    except Exception as e:
        logger.error(f"Omnissiah failed to start: {e}")
        raise


if __name__ == "__main__":
    sys.exit(main())

