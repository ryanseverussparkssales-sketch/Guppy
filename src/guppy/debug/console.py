"""
debug_console.py — Guppy / Merlin Debug & Emergency Console
============================================================
Open from any UI with Ctrl+D.

Tabs
----
  Status    — live dependency / service health check
  Memory    — SQLite table viewer + wipe
  Emergency — SAFE_MODE, TTS_ENABLED, kill worker, clear history, system prompt editor
  Voice     — test TTS speak and PTT record
  Logs      — rolling TOOL_LOG viewer (auto-refresh)
"""

import importlib
import sqlite3
import threading
from pathlib import Path

from src.guppy.paths import MEMORY_DB_PATH

try:
    from utils.db_utils import open_db as _open_db
    _DB_UTILS = True
except ImportError:
    _open_db = None  # type: ignore[assignment]
    _DB_UTILS = False


def _connect_db(path) -> sqlite3.Connection:
    if _DB_UTILS and _open_db is not None:
        return _open_db(path)
    return sqlite3.connect(str(path))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


# ── Palette ────────────────────────────────────────────────────────────────────

BG      = "#0b0b14"
BG2     = "#0f0f1c"
BORDER  = "#1e1e30"
TEXT    = "#d0d0e0"
DIM     = "#505068"
GREEN   = "#22c55e"
YELLOW  = "#eab308"
RED     = "#ef4444"
CYAN    = "#22d3ee"
PURPLE  = "#a855f7"

_BASE_STYLE = f"""
    QDialog, QWidget {{ background: {BG}; color: {TEXT}; }}
    QTabWidget::pane {{ border: 1px solid {BORDER}; background: {BG}; }}
    QTabBar::tab {{ background: {BG2}; color: {DIM}; padding: 6px 14px; border: 1px solid {BORDER}; border-bottom: none; }}
    QTabBar::tab:selected {{ color: {TEXT}; background: {BG}; border-bottom: 1px solid {BG}; }}
    QPushButton {{ background: {BG2}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 4px; padding: 5px 12px; }}
    QPushButton:hover {{ border-color: {CYAN}; color: {CYAN}; }}
    QPushButton:pressed {{ background: #1a1a2c; }}
    QLineEdit, QTextEdit {{ background: {BG2}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 3px; padding: 4px; }}
    QComboBox {{ background: {BG2}; color: {TEXT}; border: 1px solid {BORDER}; padding: 4px 8px; }}
    QComboBox QAbstractItemView {{ background: {BG2}; color: {TEXT}; selection-background-color: #1e1e30; }}
    QGroupBox {{ color: {DIM}; border: 1px solid {BORDER}; border-radius: 4px; margin-top: 8px; padding-top: 8px; }}
    QGroupBox::title {{ subcontrol-origin: margin; padding: 0 4px; }}
    QTableWidget {{ background: {BG2}; color: {TEXT}; gridline-color: {BORDER}; border: 1px solid {BORDER}; }}
    QTableWidget QHeaderView::section {{ background: {BG}; color: {DIM}; border: 1px solid {BORDER}; padding: 3px; }}
    QScrollBar:vertical {{ background: {BG}; width: 8px; }} QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; }}
"""


def _btn(label: str, color: str = TEXT) -> QPushButton:
    b = QPushButton(label)
    if color != TEXT:
        b.setStyleSheet(f"color: {color}; border-color: {color};")
    return b


def _label(text: str, color: str = DIM, bold: bool = False) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {color}; {'font-weight: bold;' if bold else ''}")
    return lbl


def _mono(widget):
    widget.setFont(QFont("Consolas", 9))
    return widget


# ── Status tab ─────────────────────────────────────────────────────────────────

def _check_import(name: str) -> tuple[bool, str]:
    try:
        importlib.import_module(name)
        return True, "OK"
    except ImportError as e:
        return False, str(e)


def _check_ollama() -> tuple[bool, str]:
    try:
        import urllib.request
        import json
        req = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
        data = json.loads(req.read())
        models = [m["name"] for m in data.get("models", [])]
        return True, f"Running — {', '.join(models[:6]) or 'no models'}"
    except Exception as e:
        return False, str(e)


def _check_gmail_token() -> tuple[bool, str]:
    token = Path.home() / ".guppy_gmail_token.json"
    if token.exists():
        return True, f"Token cached at {token}"
    return False, "No token — first run will open browser auth"


def _check_spotify_env() -> tuple[bool, str]:
    import os
    cid = os.environ.get("SPOTIFY_CLIENT_ID", "")
    sec = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
    if cid and sec:
        return True, "Client ID + Secret set"
    missing = []
    if not cid: missing.append("SPOTIFY_CLIENT_ID")
    if not sec: missing.append("SPOTIFY_CLIENT_SECRET")
    return False, f"Missing: {', '.join(missing)}"


class StatusTab(QWidget):
    CHECKS = [
        ("Ollama",             _check_ollama),
        ("edge-tts",          lambda: _check_import("edge_tts")),
        ("sounddevice",       lambda: _check_import("sounddevice")),
        ("SpeechRecognition", lambda: _check_import("speech_recognition")),
        ("spotipy",           lambda: _check_import("spotipy")),
        ("Spotify API keys",  _check_spotify_env),
        ("yt-dlp",            lambda: _check_import("yt_dlp")),
        ("Google API libs",   lambda: _check_import("googleapiclient")),
        ("Gmail token",       _check_gmail_token),
        ("anthropic",         lambda: _check_import("anthropic")),
        ("pyautogui",         lambda: _check_import("pyautogui")),
    ]

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setSpacing(4)

        top = QHBoxLayout()
        top.addWidget(_label("Dependency / Service Health", TEXT, bold=True))
        top.addStretch()
        refresh = _btn("Refresh")
        refresh.clicked.connect(self._run_checks)
        top.addWidget(refresh)
        lay.addLayout(top)

        self._rows: dict[str, QLabel] = {}
        grid_box = QWidget()
        grid = QVBoxLayout(grid_box)
        grid.setSpacing(2)
        for name, _ in self.CHECKS:
            row = QHBoxLayout()
            row.addWidget(_label(name, TEXT))
            row.addStretch()
            status = QLabel("...")
            status.setStyleSheet(f"color: {DIM};")
            status.setFont(QFont("Consolas", 9))
            row.addWidget(status)
            self._rows[name] = status
            grid.addLayout(row)

        lay.addWidget(grid_box)
        lay.addStretch()
        QTimer.singleShot(200, self._run_checks)

    def _run_checks(self):
        def _worker():
            for name, fn in self.CHECKS:
                ok, msg = fn()
                color = GREEN if ok else RED
                label = self._rows[name]
                label.setText(("OK — " if ok else "FAIL — ") + msg)
                label.setStyleSheet(f"color: {color};")
        threading.Thread(target=_worker, daemon=True).start()


# ── Memory tab ─────────────────────────────────────────────────────────────────

DB_PATH = MEMORY_DB_PATH

TABLES = {
    "facts":         ["id", "category", "key", "value", "created", "updated"],
    "tasks":         ["id", "task", "status", "due_date", "created"],
    "contacts":      ["id", "name", "company", "email", "phone", "notes", "last_contact"],
    "conversations": ["id", "session_id", "role", "content", "timestamp"],
}


class MemoryTab(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setSpacing(6)

        top = QHBoxLayout()
        self._combo = QComboBox()
        self._combo.addItems(list(TABLES.keys()))
        self._combo.currentTextChanged.connect(self._load)
        top.addWidget(_label("Table:", TEXT))
        top.addWidget(self._combo)
        top.addStretch()
        self._count_lbl = _label("", DIM)
        top.addWidget(self._count_lbl)
        refresh = _btn("Refresh")
        refresh.clicked.connect(lambda: self._load(self._combo.currentText()))
        top.addWidget(refresh)
        lay.addLayout(top)

        self._table = QTableWidget()
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self._table)

        bot = QHBoxLayout()
        bot.addStretch()
        wipe = _btn("Wipe Table", RED)
        wipe.clicked.connect(self._wipe)
        bot.addWidget(wipe)
        lay.addLayout(bot)

        QTimer.singleShot(200, lambda: self._load("facts"))

    def _load(self, table: str):
        if not DB_PATH.exists():
            self._count_lbl.setText("DB not found")
            return
        cols = TABLES.get(table, ["*"])
        try:
            con = _connect_db(DB_PATH)
            cur = con.execute(f"SELECT {', '.join(cols)} FROM {table}")
            rows = cur.fetchall()
            con.close()
        except Exception as e:
            self._count_lbl.setText(f"Error: {e}")
            return

        self._table.setColumnCount(len(cols))
        self._table.setHorizontalHeaderLabels(cols)
        self._table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                item = QTableWidgetItem(str(val) if val is not None else "")
                self._table.setItem(r, c, item)
        self._table.resizeColumnsToContents()
        self._count_lbl.setText(f"{len(rows)} rows")

    def _wipe(self):
        table = self._combo.currentText()
        reply = QMessageBox.question(
            self, "Wipe Table",
            f"Delete ALL rows from '{table}'?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        if not DB_PATH.exists():
            return
        try:
            con = _connect_db(DB_PATH)
            con.execute(f"DELETE FROM {table}")
            con.commit()
            con.close()
            self._load(table)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


# ── Emergency tab ──────────────────────────────────────────────────────────────

class EmergencyTab(QWidget):
    def __init__(self, parent_win):
        super().__init__()
        self._pw = parent_win
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        # ── Flags ─────────────────────────────────────────────────────────────
        flag_box = QGroupBox("Module Flags")
        flag_lay = QVBoxLayout(flag_box)

        self._safe_btn = _btn("SAFE MODE: OFF", YELLOW)
        self._safe_btn.setCheckable(True)
        self._safe_btn.clicked.connect(self._toggle_safe)
        flag_lay.addWidget(self._safe_btn)

        self._tts_btn = _btn("TTS: ON", GREEN)
        self._tts_btn.setCheckable(True)
        self._tts_btn.clicked.connect(self._toggle_tts)
        flag_lay.addWidget(self._tts_btn)

        self._local_btn = _btn("FORCE LOCAL: OFF", YELLOW)
        self._local_btn.setCheckable(True)
        self._local_btn.clicked.connect(self._toggle_local)
        flag_lay.addWidget(self._local_btn)

        lay.addWidget(flag_box)

        # ── Actions ───────────────────────────────────────────────────────────
        act_box = QGroupBox("Actions")
        act_lay = QVBoxLayout(act_box)

        kill = _btn("Kill Active Worker")
        kill.clicked.connect(self._kill_worker)
        act_lay.addWidget(kill)

        clear = _btn("Clear Chat History")
        clear.clicked.connect(self._clear_history)
        act_lay.addWidget(clear)

        reload_sys = _btn("Reload System Prompt")
        reload_sys.clicked.connect(self._reload_system)
        act_lay.addWidget(reload_sys)

        lay.addWidget(act_box)

        # ── System prompt editor ──────────────────────────────────────────────
        sys_box = QGroupBox("Edit System Prompt (live)")
        sys_lay = QVBoxLayout(sys_box)
        self._sys_edit = _mono(QTextEdit())
        self._sys_edit.setFixedHeight(180)
        self._sys_edit.setPlaceholderText("System prompt loaded here…")
        sys_lay.addWidget(self._sys_edit)
        apply_btn = _btn("Apply")
        apply_btn.clicked.connect(self._apply_system)
        sys_lay.addWidget(apply_btn)
        lay.addWidget(sys_box)

        # ── Nuclear ───────────────────────────────────────────────────────────
        nuke = _btn("WIPE ALL MEMORY (NUCLEAR)", RED)
        nuke.clicked.connect(self._nuke_memory)
        lay.addWidget(nuke)

        lay.addStretch()
        self._refresh_flags()
        self._load_system_prompt()

    # ── Flag helpers ──────────────────────────────────────────────────────────

    def _refresh_flags(self):
        try:
            import guppy_core
            safe = guppy_core.SAFE_MODE
            self._safe_btn.setChecked(safe)
            self._safe_btn.setText(f"SAFE MODE: {'ON' if safe else 'OFF'}")
            self._safe_btn.setStyleSheet(f"color: {RED if safe else YELLOW}; border-color: {RED if safe else YELLOW};")
        except Exception:
            pass

        try:
            from src.guppy.voice import voice as guppy_voice
            tts = guppy_voice.TTS_ENABLED
            self._tts_btn.setChecked(not tts)
            self._tts_btn.setText(f"TTS: {'ON' if tts else 'MUTED'}")
            self._tts_btn.setStyleSheet(f"color: {GREEN if tts else RED}; border-color: {GREEN if tts else RED};")
        except Exception:
            pass

        try:
            if hasattr(self._pw, "_mode"):
                forced = getattr(self._pw, "_mode", "") == "ollama"
                self._local_btn.setChecked(forced)
                self._local_btn.setText(f"FORCE LOCAL: {'ON' if forced else 'OFF'}")
                self._local_btn.setStyleSheet(f"color: {RED if forced else YELLOW}; border-color: {RED if forced else YELLOW};")
        except Exception:
            pass

    def _toggle_safe(self):
        try:
            import guppy_core
            guppy_core.SAFE_MODE = not guppy_core.SAFE_MODE
            self._refresh_flags()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _toggle_tts(self):
        try:
            from src.guppy.voice import voice as guppy_voice
            guppy_voice.TTS_ENABLED = not guppy_voice.TTS_ENABLED
            # Mirror into voice objects if parent has them
            for attr in ("_voice", "_g_voice", "_m_voice"):
                v = getattr(self._pw, attr, None)
                if v and hasattr(v, "cfg"):
                    pass  # TTS_ENABLED is module-level; the speak() check handles it
            self._refresh_flags()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _toggle_local(self):
        if not hasattr(self._pw, "_mode"):
            QMessageBox.information(self, "N/A", "Force Local only applies to Guppy/Council windows.")
            self._local_btn.setChecked(False)
            return
        try:
            current = getattr(self._pw, "_mode", "ollama")
            new_mode = "ollama" if current != "ollama" else "claude"
            self._pw._mode = new_mode
            self._refresh_flags()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    # ── Action helpers ────────────────────────────────────────────────────────

    def _kill_worker(self):
        killed = []
        for attr in ("_worker", "_g_worker", "_m_worker"):
            w = getattr(self._pw, attr, None)
            if w and w.isRunning():
                w.terminate()
                killed.append(attr)
        QMessageBox.information(self, "Kill Worker",
                                f"Terminated: {', '.join(killed)}" if killed else "No active workers.")

    def _clear_history(self):
        cleared = []
        for attr in ("history", "_g_history", "_m_history"):
            if hasattr(self._pw, attr):
                setattr(self._pw, attr, [])
                cleared.append(attr)
        QMessageBox.information(self, "Clear History",
                                f"Cleared: {', '.join(cleared)}" if cleared else "No history found.")

    def _load_system_prompt(self):
        for attr in ("_system", "_g_system"):
            val = getattr(self._pw, attr, None)
            if val:
                self._sys_edit.setPlainText(val)
                return
        try:
            from guppy_core import SYSTEM
            self._sys_edit.setPlainText(SYSTEM)
        except Exception:
            pass

    def _reload_system(self):
        try:
            import guppy_core
            import importlib
            importlib.reload(guppy_core)
            for attr in ("_system", "_g_system"):
                if hasattr(self._pw, attr):
                    setattr(self._pw, attr, guppy_core.SYSTEM)
            self._sys_edit.setPlainText(guppy_core.SYSTEM)
            QMessageBox.information(self, "Reload", "System prompt reloaded from guppy_core.")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _apply_system(self):
        new_sys = self._sys_edit.toPlainText().strip()
        if not new_sys:
            return
        applied = []
        for attr in ("_system", "_g_system", "_m_system"):
            if hasattr(self._pw, attr):
                setattr(self._pw, attr, new_sys)
                applied.append(attr)
        QMessageBox.information(self, "Applied",
                                f"System prompt updated in: {', '.join(applied)}" if applied else "No system attr found on window.")

    def _nuke_memory(self):
        reply = QMessageBox.question(
            self, "WIPE ALL MEMORY",
            "This will DELETE ALL rows from ALL tables in guppy_memory.db.\n\n"
            "This CANNOT be undone. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        if not DB_PATH.exists():
            QMessageBox.information(self, "Done", "No DB found.")
            return
        try:
            con = _connect_db(DB_PATH)
            for tbl in TABLES:
                con.execute(f"DELETE FROM {tbl}")
            con.commit()
            con.close()
            QMessageBox.information(self, "Done", "All memory tables wiped.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


# ── Voice Test tab ─────────────────────────────────────────────────────────────

class VoiceTab(QWidget):
    def __init__(self, parent_win):
        super().__init__()
        self._pw = parent_win
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        # TTS test
        tts_box = QGroupBox("TTS Speak Test")
        tts_lay = QVBoxLayout(tts_box)
        self._tts_input = QLineEdit("Hello, Master Ryan. All systems nominal.")
        tts_lay.addWidget(self._tts_input)

        row = QHBoxLayout()
        for label, attr in [("Guppy Voice", "_voice"), ("Guppy Voice", "_g_voice"), ("Merlin Voice", "_m_voice")]:
            v = getattr(self._pw, attr, None)
            if v:
                b = _btn(f"Speak ({label})")
                b.clicked.connect(lambda _, voice=v: self._speak(voice))
                row.addWidget(b)
        tts_lay.addLayout(row)
        self._tts_status = _label("", DIM)
        tts_lay.addWidget(self._tts_status)
        lay.addWidget(tts_box)

        # PTT test
        ptt_box = QGroupBox("PTT Record Test")
        ptt_lay = QVBoxLayout(ptt_box)
        ptt_row = QHBoxLayout()

        for label, attr in [("Guppy", "_voice"), ("Guppy", "_g_voice"), ("Merlin", "_m_voice")]:
            v = getattr(self._pw, attr, None)
            if v:
                b = _btn(f"Record 3s ({label})")
                b.clicked.connect(lambda _, voice=v: self._record(voice))
                ptt_row.addWidget(b)
        ptt_lay.addLayout(ptt_row)
        self._ptt_result = _mono(QTextEdit())
        self._ptt_result.setFixedHeight(80)
        self._ptt_result.setReadOnly(True)
        self._ptt_result.setPlaceholderText("Transcribed text will appear here…")
        ptt_lay.addWidget(self._ptt_result)
        lay.addWidget(ptt_box)
        lay.addStretch()

    def _speak(self, voice):
        text = self._tts_input.text().strip() or "Test."
        self._tts_status.setText("Speaking…")
        self._tts_status.setStyleSheet(f"color: {CYAN};")

        def _go():
            voice.speak(text)
            self._tts_status.setText("Done.")
            self._tts_status.setStyleSheet(f"color: {GREEN};")

        threading.Thread(target=_go, daemon=True).start()

    def _record(self, voice):
        self._ptt_result.setPlainText("Recording… (3 s)")

        def _go():
            import time
            voice.listen_once.__func__ if hasattr(voice.listen_once, "__func__") else None
            voice._listening.set()
            import threading as _t
            rec = _t.Thread(target=voice._record_worker, daemon=True)
            rec.start()
            time.sleep(3)
            voice.stop_listening()
            import queue as _q, numpy as np, tempfile, os, soundfile as sf, speech_recognition as sr
            chunks = []
            while not voice._record_q.empty():
                try:
                    chunks.append(voice._record_q.get_nowait())
                except Exception:
                    break
            if not chunks:
                self._ptt_result.setPlainText("No audio captured.")
                return
            try:
                audio = np.concatenate(chunks, axis=0)
                tmpfd, tmp_path = tempfile.mkstemp(suffix=".wav")
                os.close(tmpfd)
                sf.write(tmp_path, audio, voice.cfg.samplerate)
                recognizer = sr.Recognizer()
                with sr.AudioFile(tmp_path) as src:
                    audio_data = recognizer.record(src)
                try:
                    text = recognizer.recognize_google(audio_data)
                    self._ptt_result.setPlainText(f"Heard: {text}")
                except sr.UnknownValueError:
                    self._ptt_result.setPlainText("Could not understand audio.")
                except Exception as e:
                    self._ptt_result.setPlainText(f"Error: {e}")
                finally:
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
            except Exception as e:
                self._ptt_result.setPlainText(f"Processing error: {e}")

        threading.Thread(target=_go, daemon=True).start()


# ── Logs tab ───────────────────────────────────────────────────────────────────

class LogsTab(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(_label("Tool Call Log (last 50)", TEXT, bold=True))
        top.addStretch()
        self._clear_btn = _btn("Clear")
        self._clear_btn.clicked.connect(self._clear)
        top.addWidget(self._clear_btn)
        lay.addLayout(top)

        self._log_view = _mono(QTextEdit())
        self._log_view.setReadOnly(True)
        lay.addWidget(self._log_view)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(1500)
        self._refresh()

    def _refresh(self):
        try:
            import guppy_core
            log = list(guppy_core.TOOL_LOG)
        except Exception:
            return
        if not log:
            self._log_view.setPlainText("No tool calls recorded yet.")
            return
        lines = []
        for entry in reversed(log):
            t    = entry.get("time", "?")
            tool = entry.get("tool", "?")
            args = entry.get("args", "")
            res  = entry.get("result", "")
            lines.append(f"[{t}] {tool}({args})\n  → {res}")
        self._log_view.setPlainText("\n\n".join(lines))

    def _clear(self):
        try:
            import guppy_core
            guppy_core.TOOL_LOG.clear()
            self._refresh()
        except Exception:
            pass


# ── Main DebugConsole dialog ───────────────────────────────────────────────────

class DebugConsole(QDialog):
    """Debug and emergency console. Pass the calling UI window as parent_win."""

    def __init__(self, parent_win=None):
        super().__init__(parent_win)
        self.setWindowTitle("Debug Console")
        self.setMinimumSize(680, 560)
        self.setStyleSheet(_BASE_STYLE)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)

        header = QHBoxLayout()
        title = QLabel("Guppy / Merlin — Debug & Emergency Console")
        title.setStyleSheet(f"color: {CYAN}; font-size: 13px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        lay.addLayout(header)

        tabs = QTabWidget()
        tabs.addTab(StatusTab(),                  "Status")
        tabs.addTab(MemoryTab(),                  "Memory")
        tabs.addTab(EmergencyTab(parent_win),     "Emergency")
        tabs.addTab(VoiceTab(parent_win),         "Voice")
        tabs.addTab(LogsTab(),                    "Logs")
        lay.addWidget(tabs)

        close = _btn("Close")
        close.clicked.connect(self.close)
        close.setFixedWidth(80)
        bot = QHBoxLayout()
        bot.addStretch()
        bot.addWidget(close)
        lay.addLayout(bot)

        # Ctrl+W also closes
        QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(self.close)


# ── Convenience function ───────────────────────────────────────────────────────

def open_debug_console(parent_win=None):
    """Open (or raise) the debug console. Safe to call from any UI."""
    console = DebugConsole(parent_win)
    console.show()
    console.raise_()
    return console
