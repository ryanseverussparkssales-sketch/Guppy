"""Agent launcher/status card used by hub window."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from .theme_config import ACNT, BG2, BG3, BORD, DIM


class AgentCard(QFrame):
    launch_requested = Signal(str)
    stop_requested = Signal(str)

    _STABLE_UPTIME_SECS = 30

    def __init__(
        self,
        agent: dict,
        root_dir: Path,
        runtime_dir: Path,
        python_executable: str,
        hb_stale_secs: int,
        psutil_module,
        logger,
        operator=None,
        parent=None,
    ):
        super().__init__(parent)
        self._agent = agent
        self._root = root_dir
        self._runtime = runtime_dir
        self._python = python_executable
        self._hb_stale_secs = hb_stale_secs
        self._psutil = psutil_module
        self._psutil_ok = psutil_module is not None
        self._logger = logger
        self._operator = operator

        self._proc: Optional[subprocess.Popen] = None
        self._proc_log_handle = None
        self._start_time: Optional[float] = None
        self._recommended = False
        self._user_stopped = False
        self._crash_count = 0

        self.setObjectName("AgentCard")
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(2)

        top = QHBoxLayout()
        accent = self._agent["accent"]

        self._icon_lbl = QLabel(">>")
        self._icon_lbl.setStyleSheet(f"color:{accent}; background:transparent; border:none;")

        self._label_lbl = QLabel(self._agent["label"])
        label_font = QFont("Segoe UI", 8, QFont.Weight.Bold)
        label_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
        self._label_lbl.setFont(label_font)
        self._label_lbl.setStyleSheet(f"color:{accent}; background:transparent; border:none;")

        self._rec_lbl = QLabel("")
        self._rec_lbl.setStyleSheet("color:#ffaa44; background:transparent; border:none;")
        self._rec_lbl.setFont(QFont("Segoe UI", 7))

        subtitle = QLabel(self._agent["title"])
        subtitle.setStyleSheet(f"color:{DIM}; background:transparent; border:none;")
        subtitle.setFont(QFont("Segoe UI", 7))

        top.addWidget(self._icon_lbl)
        top.addWidget(self._label_lbl)
        top.addWidget(self._rec_lbl)
        top.addStretch()
        top.addWidget(subtitle)
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

        self._nudge_btn = QPushButton("~ NUDGE")
        self._nudge_btn.setFixedHeight(22)
        self._nudge_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._nudge_btn.setFont(QFont("Segoe UI", 7))
        self._nudge_btn.setVisible(False)
        self._nudge_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#8888ee;"
            "border:1px solid #8888ee55;border-radius:4px;"
            "font-size:8px;font-weight:bold;letter-spacing:1px;}"
            "QPushButton:hover{border-color:#8888ee;background:#8888ee22;}"
        )
        self._nudge_btn.clicked.connect(self._on_nudge)

        self._repair_btn = QPushButton("+ REPAIR")
        self._repair_btn.setFixedHeight(22)
        self._repair_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._repair_btn.setFont(QFont("Segoe UI", 7))
        self._repair_btn.setVisible(False)
        self._repair_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#6adfb8;"
            "border:1px solid #6adfb855;border-radius:4px;"
            "font-size:8px;font-weight:bold;letter-spacing:1px;}"
            "QPushButton:hover{border-color:#6adfb8;background:#6adfb822;}"
        )
        self._repair_btn.clicked.connect(self._on_repair)

        bot.addWidget(self._status_lbl)
        bot.addWidget(self._uptime_lbl)
        bot.addStretch()
        bot.addWidget(self._activity_lbl)
        bot.addWidget(self._nudge_btn)
        bot.addWidget(self._repair_btn)
        bot.addWidget(self._unstall_btn)
        bot.addWidget(self._btn)
        lay.addLayout(bot)

        self._update_style(running=False)

    def _update_style(self, running: bool, stalled: bool = False):
        accent = self._agent["accent"]
        if running and not stalled:
            self._status_lbl.setStyleSheet(
                f"color:{accent}; background:transparent; border:none; "
                "font-size:8px; font-weight:bold; letter-spacing:1px;"
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
                f"border:1px solid {accent}55;border-left:3px solid {accent};"
                "border-radius:6px;}}"
            )
            self._unstall_btn.setVisible(False)
            self._nudge_btn.setVisible(False)
            self._repair_btn.setVisible(False)
            return

        if running and stalled:
            amber = "#d4860a"
            self._status_lbl.setStyleSheet(
                f"color:{amber}; background:transparent; border:none; "
                "font-size:8px; font-weight:bold; letter-spacing:1px;"
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
                f"border:1px solid {amber}88;border-left:3px solid {amber};"
                "border-radius:6px;}}"
            )
            self._unstall_btn.setVisible(True)
            self._unstall_btn.setStyleSheet(
                "QPushButton{background:transparent;color:#d4860a;"
                "border:1px solid #d4860a88;border-radius:4px;"
                "font-size:8px;font-weight:bold;letter-spacing:1px;}"
                "QPushButton:hover{border-color:#d4860a;background:#d4860a22;}"
                "QPushButton:pressed{background:#d4860a33;}"
            )
            self._nudge_btn.setVisible(True)
            self._repair_btn.setVisible(False)
            return

        self._status_lbl.setStyleSheet(
            f"color:{DIM}; background:transparent; border:none; "
            "font-size:8px; letter-spacing:1px;"
        )
        self._status_lbl.setText("-- DORMANT")
        self._btn.setText(">> AWAKEN")
        self._btn.setStyleSheet(
            f"QPushButton{{background:{accent}1a;color:{accent}88;"
            f"border:1px solid {accent}44;border-radius:4px;"
            "font-size:8px;font-weight:bold;letter-spacing:1px;}}"
            f"QPushButton:hover{{background:{accent}33;color:{accent};"
            f"border-color:{accent};}}"
            f"QPushButton:pressed{{background:{accent}44;}}"
        )
        border = accent if self._recommended else BORD
        self.setStyleSheet(
            f"AgentCard{{background:{BG3};"
            f"border:1px solid {border}44;border-radius:6px;}}"
        )
        self._unstall_btn.setVisible(False)
        self._nudge_btn.setVisible(False)
        self._repair_btn.setVisible(self._crash_count >= 2)

    def _is_stalled(self) -> bool:
        if not self.is_running():
            return False
        hb_path = self._runtime / f"{self._agent['id']}.heartbeat"
        if not hb_path.exists():
            return False
        try:
            ts = float(hb_path.read_text(encoding="utf-8").strip())
            return (time.time() - ts) > self._hb_stale_secs
        except Exception as exc:
            self._logger.debug(f"heartbeat read failed for {self._agent['id']}: {exc}")
            return False

    def _get_activity(self) -> str:
        act_path = self._runtime / f"{self._agent['id']}.activity"
        if not act_path.exists():
            return "idle"
        try:
            return act_path.read_text(encoding="utf-8").strip() or "idle"
        except Exception as exc:
            self._logger.debug(f"activity read failed for {self._agent['id']}: {exc}")
            return "idle"

    def _detect_existing_process(self) -> bool:
        if not self._psutil_ok:
            return False
        script = self._agent["script"]
        try:
            for proc in self._psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    cmdline = proc.info.get("cmdline") or []
                    if any(script in arg for arg in cmdline):
                        self._proc = proc
                        if self._start_time is None:
                            self._start_time = proc.create_time()
                        return True
                except (self._psutil.NoSuchProcess, self._psutil.AccessDenied):
                    continue
        except Exception:
            return False
        return False

    def is_running(self) -> bool:
        if self._proc is None:
            self._detect_existing_process()
        if self._proc is None:
            return False
        if hasattr(self._proc, "poll"):
            return self._proc.poll() is None
        if not self._psutil_ok:
            return False
        try:
            return self._proc.is_running() and self._proc.status() != self._psutil.STATUS_ZOMBIE
        except Exception:
            return False

    def launch(self):
        if self.is_running():
            return

        self._user_stopped = False
        script_path = self._root / self._agent["script"]
        extra = {}
        if sys.platform == "win32":
            extra["creationflags"] = subprocess.CREATE_NO_WINDOW

        log_path = self._runtime / f"{self._agent['id']}.process.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._proc_log_handle = log_path.open("a", encoding="utf-8", errors="replace")
        self._proc_log_handle.write(
            f"\n[{time.strftime('%Y-%m-%dT%H:%M:%S')}] launch {script_path.name}\n"
        )
        self._proc_log_handle.flush()

        try:
            self._proc = subprocess.Popen(
                [self._python, str(script_path)],
                cwd=str(self._root),
                stdout=self._proc_log_handle,
                stderr=subprocess.STDOUT,
                **extra,
            )
        except Exception:
            try:
                self._proc_log_handle.close()
            except Exception:
                pass
            self._proc_log_handle = None
            raise

        self._start_time = time.time()
        self._update_style(running=True)
        self._uptime_lbl.setText("0s")
        if self._operator:
            self._operator.record_event(self._agent["id"], "launch", "user", "started")

    def _close_proc_log_handle(self) -> None:
        if self._proc_log_handle is None:
            return
        try:
            self._proc_log_handle.flush()
            self._proc_log_handle.close()
        except Exception:
            pass
        self._proc_log_handle = None

    def _tail_process_log(self, max_lines: int = 6) -> str:
        path = self._runtime / f"{self._agent['id']}.process.log"
        if not path.exists():
            return ""
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            tail = [line.strip() for line in lines[-max_lines:] if line.strip()]
            if not tail:
                return ""
            return " | ".join(tail)[-280:]
        except Exception:
            return ""

    def stop(self):
        if self._proc and self.is_running():
            self._user_stopped = True
            if hasattr(self._proc, "terminate"):
                self._proc.terminate()
            else:
                try:
                    self._proc.kill()
                except Exception:
                    pass
        self._proc = None
        self._close_proc_log_handle()
        self._start_time = None
        self._crash_count = 0
        self._update_style(running=False)
        self._uptime_lbl.setText("")
        if self._operator:
            self._operator.record_event(self._agent["id"], "stop", "user", "stopped")

    def _schedule_restart(self, delay_ms: int = 5000):
        if self._crash_count >= 3:
            self._logger.warning(f"{self._agent['id']} reached max restart attempts.")
            if self._operator:
                self._operator.record_event(self._agent["id"], "crash_max", "short_exit", "giving_up")
            return

        self._crash_count += 1
        self._status_lbl.setText(f"~~ RECALLING ({self._crash_count}/3)")
        self._status_lbl.setStyleSheet(
            f"color:{ACNT}; background:transparent; border:none; "
            "font-size:8px; letter-spacing:1px;"
        )
        if self._operator:
            self._operator.record_event(
                self._agent["id"],
                "crash",
                "short_exit",
                f"attempt:{self._crash_count}/3",
            )
        QTimer.singleShot(delay_ms, self.launch)

    def tick(self):
        alive = self.is_running()
        if alive and self._start_time:
            secs = int(time.time() - self._start_time)
            if secs < 60:
                self._uptime_lbl.setText(f"{secs}s")
            else:
                mins, secs_left = divmod(secs, 60)
                self._uptime_lbl.setText(f"{mins}m{secs_left:02d}s")

            stalled = self._is_stalled()
            activity = self._get_activity()
            act_map = {
                "thinking": ("⧖ THINKING", "#d4860a"),
                "speaking": ("◈ SPEAKING", "#6adfb8"),
                "listening": ("◎ LISTENING", "#8888ee"),
            }
            if activity in act_map and not stalled:
                text, color = act_map[activity]
                self._activity_lbl.setText(text)
                self._activity_lbl.setStyleSheet(
                    f"color:{color}; background:transparent; border:none; "
                    "font-size:7px; font-weight:bold; letter-spacing:1px;"
                )
            else:
                self._activity_lbl.setText("")
            self._update_style(running=True, stalled=stalled)
            return

        if not alive and self._proc is not None:
            uptime = time.time() - self._start_time if self._start_time else 0
            crash_tail = self._tail_process_log()
            self._proc = None
            self._close_proc_log_handle()
            self._start_time = None
            self._update_style(running=False)
            self._uptime_lbl.setText("")
            self._activity_lbl.setText("")
            if not self._user_stopped:
                if uptime >= self._STABLE_UPTIME_SECS:
                    self._logger.info(
                        f"{self._agent['id']} exited after {uptime:.0f}s "
                        "(user close assumed - no restart)."
                    )
                    self._crash_count = 0
                else:
                    tail_suffix = f" tail={crash_tail}" if crash_tail else ""
                    self._logger.warning(
                        f"{self._agent['id']} exited after {uptime:.0f}s "
                        f"(crash assumed - scheduling restart).{tail_suffix}"
                    )
                    if self._operator:
                        self._operator.record_event(
                            self._agent["id"],
                            "crash_excerpt",
                            "process_log_tail",
                            crash_tail or "no_tail",
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
            return
        self.launch_requested.emit(self._agent["id"])

    def _on_unstall(self):
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
        self._nudge_btn.setVisible(False)

        hb = self._runtime / f"{self._agent['id']}.heartbeat"
        act = self._runtime / f"{self._agent['id']}.activity"
        try:
            hb.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            act.unlink(missing_ok=True)
        except Exception:
            pass

        if self._operator:
            self._operator.record_event(self._agent["id"], "unstall", "user", "restarting")
        QTimer.singleShot(500, self.launch)

    def _on_nudge(self):
        if self._operator:
            self._operator.nudge_agent(self._agent["id"])

    def _on_repair(self):
        if self._operator:
            removed = self._operator.repair_agent(self._agent["id"])
            self._logger.info(f"Repair {self._agent['id']}: removed {removed}")
        self._crash_count = 0
        self._update_style(running=False)
