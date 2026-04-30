from __future__ import annotations

import importlib
import sqlite3
import threading
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QLineEdit,
)

from src.guppy.paths import MEMORY_DB_PATH

from ._ui import CYAN, DIM, GREEN, RED, TEXT, YELLOW, apply_mono, make_button, make_label
def _voice_objects(_pw):
    return []

def _record_voice_objects(_pw):
    return []

def _transcribe_voice_recording(_voice):
    return ""

try:
    from utils.db_utils import open_db as _open_db

    _DB_UTILS = True
except ImportError:
    _open_db = None  # type: ignore[assignment]
    _DB_UTILS = False


DB_PATH = MEMORY_DB_PATH
TABLES = {
    "facts": ["id", "category", "key", "value", "created", "updated"],
    "tasks": ["id", "task", "status", "due_date", "created"],
    "contacts": ["id", "name", "company", "email", "phone", "notes", "last_contact"],
    "conversations": ["id", "session_id", "role", "content", "timestamp"],
}


def _connect_db(path: Path) -> sqlite3.Connection:
    if _DB_UTILS and _open_db is not None:
        return _open_db(path)
    return sqlite3.connect(str(path))


def _check_import(name: str) -> tuple[bool, str]:
    try:
        importlib.import_module(name)
        return True, "OK"
    except ImportError as exc:
        return False, str(exc)


def _check_llamacpp(port: int = 8087) -> tuple[bool, str]:
    try:
        import json
        import urllib.request

        request = urllib.request.urlopen(f"http://localhost:{port}/v1/models", timeout=3)
        data = json.loads(request.read())
        models = [m.get("id", "?") for m in data.get("data", [])]
        return True, f"Running on port {port} — {', '.join(models[:4]) or 'no models'}"
    except Exception as exc:  # pragma: no cover - live environment dependent
        return False, str(exc)


def _check_gmail_token() -> tuple[bool, str]:
    token = Path.home() / ".guppy_gmail_token.json"
    if token.exists():
        return True, f"Token cached at {token}"
    return False, "No token - first run will open browser auth"


def _check_spotify_env() -> tuple[bool, str]:
    import os

    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
    if client_id and client_secret:
        return True, "Client ID + Secret set"

    missing: list[str] = []
    if not client_id:
        missing.append("SPOTIFY_CLIENT_ID")
    if not client_secret:
        missing.append("SPOTIFY_CLIENT_SECRET")
    return False, f"Missing: {', '.join(missing)}"


def _format_log_lines(entries: list[dict[str, object]]) -> str:
    if not entries:
        return "No tool calls recorded yet."

    lines: list[str] = []
    for entry in reversed(entries):
        timestamp = entry.get("time", "?")
        tool = entry.get("tool", "?")
        args = entry.get("args", "")
        result = entry.get("result", "")
        lines.append(f"[{timestamp}] {tool}({args})\n  -> {result}")
    return "\n\n".join(lines)


class StatusTab(QWidget):
    CHECKS = [
        ("llamacpp (hermes3:8087)", lambda: _check_llamacpp(8087)),
        ("llamacpp (hermes4:8086)", lambda: _check_llamacpp(8086)),
        ("edge-tts", lambda: _check_import("edge_tts")),
        ("sounddevice", lambda: _check_import("sounddevice")),
        ("SpeechRecognition", lambda: _check_import("speech_recognition")),
        ("spotipy", lambda: _check_import("spotipy")),
        ("Spotify API keys", _check_spotify_env),
        ("yt-dlp", lambda: _check_import("yt_dlp")),
        ("Google API libs", lambda: _check_import("googleapiclient")),
        ("Gmail token", _check_gmail_token),
        ("anthropic", lambda: _check_import("anthropic")),
        ("pyautogui", lambda: _check_import("pyautogui")),
    ]

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.addWidget(make_label("Dependency / Service Health", TEXT, bold=True))
        header.addStretch()
        refresh = make_button("Refresh")
        refresh.clicked.connect(self._run_checks)
        header.addWidget(refresh)
        layout.addLayout(header)

        self._rows = {}
        grid_box = QWidget()
        grid = QVBoxLayout(grid_box)
        grid.setSpacing(2)
        for name, _ in self.CHECKS:
            row = QHBoxLayout()
            row.addWidget(make_label(name, TEXT))
            row.addStretch()
            status = make_label("...")
            apply_mono(status)
            row.addWidget(status)
            self._rows[name] = status
            grid.addLayout(row)

        layout.addWidget(grid_box)
        layout.addStretch()
        QTimer.singleShot(200, self._run_checks)

    def _run_checks(self):
        def _worker():
            for name, fn in self.CHECKS:
                ok, message = fn()
                color = GREEN if ok else RED
                label = self._rows[name]
                label.setText(("OK - " if ok else "FAIL - ") + message)
                label.setStyleSheet(f"color: {color};")

        threading.Thread(target=_worker, daemon=True).start()


class MemoryTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        top = QHBoxLayout()
        self._combo = QComboBox()
        self._combo.addItems(list(TABLES.keys()))
        self._combo.currentTextChanged.connect(self._load)
        top.addWidget(make_label("Table:", TEXT))
        top.addWidget(self._combo)
        top.addStretch()
        self._count_lbl = make_label("")
        top.addWidget(self._count_lbl)
        refresh = make_button("Refresh")
        refresh.clicked.connect(lambda: self._load(self._combo.currentText()))
        top.addWidget(refresh)
        layout.addLayout(top)

        self._table = QTableWidget()
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        bottom = QHBoxLayout()
        bottom.addStretch()
        wipe = make_button("Wipe Table", RED)
        wipe.clicked.connect(self._wipe)
        bottom.addWidget(wipe)
        layout.addLayout(bottom)

        QTimer.singleShot(200, lambda: self._load("facts"))

    def _load(self, table: str):
        if not DB_PATH.exists():
            self._count_lbl.setText("DB not found")
            return

        cols = TABLES.get(table, ["*"])
        try:
            connection = _connect_db(DB_PATH)
            cursor = connection.execute(f"SELECT {', '.join(cols)} FROM {table}")
            rows = cursor.fetchall()
            connection.close()
        except Exception as exc:
            self._count_lbl.setText(f"Error: {exc}")
            return

        self._table.setColumnCount(len(cols))
        self._table.setHorizontalHeaderLabels(cols)
        self._table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for col_index, value in enumerate(row):
                item = QTableWidgetItem("" if value is None else str(value))
                self._table.setItem(row_index, col_index, item)
        self._table.resizeColumnsToContents()
        self._count_lbl.setText(f"{len(rows)} rows")

    def _wipe(self):
        table = self._combo.currentText()
        reply = QMessageBox.question(
            self,
            "Wipe Table",
            f"Delete ALL rows from '{table}'?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes or not DB_PATH.exists():
            return
        try:
            connection = _connect_db(DB_PATH)
            connection.execute(f"DELETE FROM {table}")
            connection.commit()
            connection.close()
            self._load(table)
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))


class EmergencyTab(QWidget):
    def __init__(self, parent_win):
        super().__init__()
        self._pw = parent_win
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(self._build_flags_box())
        layout.addWidget(self._build_actions_box())
        layout.addWidget(self._build_system_prompt_box())

        nuke = make_button("WIPE ALL MEMORY (NUCLEAR)", RED)
        nuke.clicked.connect(self._nuke_memory)
        layout.addWidget(nuke)
        layout.addStretch()

        self._refresh_flags()
        self._load_system_prompt()

    def _build_flags_box(self) -> QGroupBox:
        flag_box = QGroupBox("Module Flags")
        flag_layout = QVBoxLayout(flag_box)

        self._safe_btn = make_button("SAFE MODE: OFF", YELLOW)
        self._safe_btn.setCheckable(True)
        self._safe_btn.clicked.connect(self._toggle_safe)
        flag_layout.addWidget(self._safe_btn)

        self._tts_btn = make_button("TTS: ON", GREEN)
        self._tts_btn.setCheckable(True)
        self._tts_btn.clicked.connect(self._toggle_tts)
        flag_layout.addWidget(self._tts_btn)

        self._local_btn = make_button("FORCE LOCAL: OFF", YELLOW)
        self._local_btn.setCheckable(True)
        self._local_btn.clicked.connect(self._toggle_local)
        flag_layout.addWidget(self._local_btn)
        return flag_box

    def _build_actions_box(self) -> QGroupBox:
        action_box = QGroupBox("Actions")
        action_layout = QVBoxLayout(action_box)

        kill = make_button("Kill Active Worker")
        kill.clicked.connect(self._kill_worker)
        action_layout.addWidget(kill)

        clear = make_button("Clear Chat History")
        clear.clicked.connect(self._clear_history)
        action_layout.addWidget(clear)

        reload_system = make_button("Reload System Prompt")
        reload_system.clicked.connect(self._reload_system)
        action_layout.addWidget(reload_system)
        return action_box

    def _build_system_prompt_box(self) -> QGroupBox:
        system_box = QGroupBox("Edit System Prompt (live)")
        system_layout = QVBoxLayout(system_box)

        self._sys_edit = apply_mono(QTextEdit())
        self._sys_edit.setFixedHeight(180)
        self._sys_edit.setPlaceholderText("System prompt loaded here...")
        system_layout.addWidget(self._sys_edit)

        apply_button = make_button("Apply")
        apply_button.clicked.connect(self._apply_system)
        system_layout.addWidget(apply_button)
        return system_box

    def _refresh_flags(self):
        try:
            import guppy_core

            safe_mode = guppy_core.SAFE_MODE
            self._safe_btn.setChecked(safe_mode)
            self._safe_btn.setText(f"SAFE MODE: {'ON' if safe_mode else 'OFF'}")
            self._safe_btn.setStyleSheet(f"color: {RED if safe_mode else YELLOW}; border-color: {RED if safe_mode else YELLOW};")
        except Exception:
            pass

        try:
            from src.guppy.voice import voice as guppy_voice

            tts_enabled = guppy_voice.TTS_ENABLED
            self._tts_btn.setChecked(not tts_enabled)
            self._tts_btn.setText(f"TTS: {'ON' if tts_enabled else 'MUTED'}")
            self._tts_btn.setStyleSheet(f"color: {GREEN if tts_enabled else RED}; border-color: {GREEN if tts_enabled else RED};")
        except Exception:
            pass

        try:
            if hasattr(self._pw, "_mode"):
                forced_local = getattr(self._pw, "_mode", "") == "llamacpp"
                self._local_btn.setChecked(forced_local)
                self._local_btn.setText(f"FORCE LOCAL: {'ON' if forced_local else 'OFF'}")
                self._local_btn.setStyleSheet(
                    f"color: {RED if forced_local else YELLOW}; border-color: {RED if forced_local else YELLOW};"
                )
        except Exception:
            pass

    def _toggle_safe(self):
        try:
            import guppy_core

            guppy_core.SAFE_MODE = not guppy_core.SAFE_MODE
            self._refresh_flags()
        except Exception as exc:
            QMessageBox.warning(self, "Error", str(exc))

    def _toggle_tts(self):
        try:
            from src.guppy.voice import voice as guppy_voice

            guppy_voice.TTS_ENABLED = not guppy_voice.TTS_ENABLED
            self._refresh_flags()
        except Exception as exc:
            QMessageBox.warning(self, "Error", str(exc))

    def _toggle_local(self):
        if not hasattr(self._pw, "_mode"):
            QMessageBox.information(self, "N/A", "Force Local only applies to Guppy/Council windows.")
            self._local_btn.setChecked(False)
            return
        try:
            current = getattr(self._pw, "_mode", "llamacpp")
            self._pw._mode = "llamacpp" if current != "llamacpp" else "claude"
            self._refresh_flags()
        except Exception as exc:
            QMessageBox.warning(self, "Error", str(exc))

    def _kill_worker(self):
        killed: list[str] = []
        for attr in ("_worker", "_g_worker", "_m_worker"):
            worker = getattr(self._pw, attr, None)
            if worker and worker.isRunning():
                worker.terminate()
                killed.append(attr)
        QMessageBox.information(
            self,
            "Kill Worker",
            f"Terminated: {', '.join(killed)}" if killed else "No active workers.",
        )

    def _clear_history(self):
        cleared: list[str] = []
        for attr in ("history", "_g_history", "_m_history"):
            if hasattr(self._pw, attr):
                setattr(self._pw, attr, [])
                cleared.append(attr)
        QMessageBox.information(
            self,
            "Clear History",
            f"Cleared: {', '.join(cleared)}" if cleared else "No history found.",
        )

    def _load_system_prompt(self):
        for attr in ("_system", "_g_system"):
            value = getattr(self._pw, attr, None)
            if value:
                self._sys_edit.setPlainText(value)
                return
        try:
            from guppy_core import SYSTEM

            self._sys_edit.setPlainText(SYSTEM)
        except Exception:
            pass

    def _reload_system(self):
        try:
            import guppy_core

            importlib.reload(guppy_core)
            for attr in ("_system", "_g_system"):
                if hasattr(self._pw, attr):
                    setattr(self._pw, attr, guppy_core.SYSTEM)
            self._sys_edit.setPlainText(guppy_core.SYSTEM)
            QMessageBox.information(self, "Reload", "System prompt reloaded from guppy_core.")
        except Exception as exc:
            QMessageBox.warning(self, "Error", str(exc))

    def _apply_system(self):
        new_system = self._sys_edit.toPlainText().strip()
        if not new_system:
            return
        applied: list[str] = []
        for attr in ("_system", "_g_system", "_m_system"):
            if hasattr(self._pw, attr):
                setattr(self._pw, attr, new_system)
                applied.append(attr)
        QMessageBox.information(
            self,
            "Applied",
            f"System prompt updated in: {', '.join(applied)}" if applied else "No system attr found on window.",
        )

    def _nuke_memory(self):
        reply = QMessageBox.question(
            self,
            "WIPE ALL MEMORY",
            "This will DELETE ALL rows from ALL tables in guppy_memory.db.\n\nThis CANNOT be undone. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        if not DB_PATH.exists():
            QMessageBox.information(self, "Done", "No DB found.")
            return
        try:
            connection = _connect_db(DB_PATH)
            for table in TABLES:
                connection.execute(f"DELETE FROM {table}")
            connection.commit()
            connection.close()
            QMessageBox.information(self, "Done", "All memory tables wiped.")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))


class VoiceTab(QWidget):
    def __init__(self, parent_win):
        super().__init__()
        self._pw = parent_win
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(self._build_tts_box())
        layout.addWidget(self._build_ptt_box())
        layout.addStretch()

    def _build_tts_box(self) -> QGroupBox:
        tts_box = QGroupBox("TTS Speak Test")
        tts_layout = QVBoxLayout(tts_box)
        self._tts_input = QLineEdit("Hello, Master Ryan. All systems nominal.")
        tts_layout.addWidget(self._tts_input)

        row = QHBoxLayout()
        for label, voice in _voice_objects(self._pw):
            button = make_button(f"Speak ({label})")
            button.clicked.connect(lambda _checked=False, current_voice=voice: self._speak(current_voice))
            row.addWidget(button)
        tts_layout.addLayout(row)

        self._tts_status = make_label("")
        tts_layout.addWidget(self._tts_status)
        return tts_box

    def _build_ptt_box(self) -> QGroupBox:
        ptt_box = QGroupBox("PTT Record Test")
        ptt_layout = QVBoxLayout(ptt_box)
        row = QHBoxLayout()

        for label, voice in _record_voice_objects(self._pw):
            button = make_button(f"Record 3s ({label})")
            button.clicked.connect(lambda _checked=False, current_voice=voice: self._record(current_voice))
            row.addWidget(button)
        ptt_layout.addLayout(row)

        self._ptt_result = apply_mono(QTextEdit())
        self._ptt_result.setFixedHeight(80)
        self._ptt_result.setReadOnly(True)
        self._ptt_result.setPlaceholderText("Transcribed text will appear here...")
        ptt_layout.addWidget(self._ptt_result)
        return ptt_box

    def _speak(self, voice):
        text = self._tts_input.text().strip() or "Test."
        self._tts_status.setText("Speaking...")
        self._tts_status.setStyleSheet(f"color: {CYAN};")

        def _go():
            voice.speak(text)
            self._tts_status.setText("Done.")
            self._tts_status.setStyleSheet(f"color: {GREEN};")

        threading.Thread(target=_go, daemon=True).start()

    def _record(self, voice):
        self._ptt_result.setPlainText("Recording... (3 s)")

        def _go():
            self._ptt_result.setPlainText(_transcribe_voice_recording(voice))

        threading.Thread(target=_go, daemon=True).start()


class LogsTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(make_label("Tool Call Log (last 50)", TEXT, bold=True))
        top.addStretch()
        clear_button = make_button("Clear")
        clear_button.clicked.connect(self._clear)
        top.addWidget(clear_button)
        layout.addLayout(top)

        self._log_view = apply_mono(QTextEdit())
        self._log_view.setReadOnly(True)
        layout.addWidget(self._log_view)

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
        self._log_view.setPlainText(_format_log_lines(log))

    def _clear(self):
        try:
            import guppy_core

            guppy_core.TOOL_LOG.clear()
            self._refresh()
        except Exception:
            pass
