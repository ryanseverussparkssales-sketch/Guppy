"""Hub operator control panel widget."""
from __future__ import annotations

import os
import threading
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from .theme_config import ACNT, BG2, DIM, SILV, TEXT


class OperatorCard(QFrame):
    """Shows HubOperator insight and lifecycle controls."""

    def __init__(self, operator, parent=None):
        super().__init__(parent)
        self._op = operator
        self._lifecycle_log: list[str] = []
        self.setObjectName("OperatorCard")
        self._build_ui()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start(30_000)

        self._auto_analyze_enabled = os.environ.get("GUPPY_ENABLE_AGENT_REVIEW_HANDOFF", "0").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if self._auto_analyze_enabled:
            self._analyze_timer = QTimer(self)
            self._analyze_timer.timeout.connect(self._auto_analyze)
            self._analyze_timer.start(15 * 60 * 1000)
        else:
            self._analyze_timer = None

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(3)

        top = QHBoxLayout()
        title = QLabel("HUB OPERATOR")
        title.setStyleSheet(f"color:{ACNT}; background:transparent; border:none;")
        title.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        top.addWidget(title)
        top.addStretch()

        self._analyze_btn = QPushButton("◆ ANALYZE")
        self._analyze_btn.setFixedHeight(20)
        self._analyze_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._analyze_btn.setFont(QFont("Segoe UI", 7))
        self._analyze_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{ACNT};"
            f"border:1px solid {ACNT}66;border-radius:4px;"
            f"font-size:7px;font-weight:bold;letter-spacing:1px;}}"
            f"QPushButton:hover{{background:{ACNT}22;border-color:{ACNT};}}"
        )
        self._analyze_btn.clicked.connect(self._on_analyze)
        top.addWidget(self._analyze_btn)
        lay.addLayout(top)

        action_row = QHBoxLayout()
        self._offer_btn = QPushButton("TEST OFFER")
        self._offer_btn.setFixedHeight(20)
        self._offer_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._offer_btn.setFont(QFont("Segoe UI", 7))
        self._offer_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{SILV};"
            f"border:1px solid {SILV}66;border-radius:4px;"
            f"font-size:7px;font-weight:bold;letter-spacing:1px;}}"
            f"QPushButton:hover{{background:{SILV}22;border-color:{SILV};}}"
        )
        self._offer_btn.clicked.connect(self._send_test_offer)

        self._status_btn = QPushButton("STATUS SNAP")
        self._status_btn.setFixedHeight(20)
        self._status_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._status_btn.setFont(QFont("Segoe UI", 7))
        self._status_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{ACNT};"
            f"border:1px solid {ACNT}66;border-radius:4px;"
            f"font-size:7px;font-weight:bold;letter-spacing:1px;}}"
            f"QPushButton:hover{{background:{ACNT}22;border-color:{ACNT};}}"
        )
        self._status_btn.clicked.connect(self._request_status_snap)

        self._dry_run_btn = QPushButton("DRY RUN: OFF")
        self._dry_run_btn.setCheckable(True)
        self._dry_run_btn.setChecked(False)
        self._dry_run_btn.setFixedHeight(20)
        self._dry_run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dry_run_btn.setFont(QFont("Segoe UI", 7))
        self._dry_run_btn.toggled.connect(self._on_dry_run_toggled)
        self._on_dry_run_toggled(False)

        action_row.addWidget(self._offer_btn)
        action_row.addWidget(self._status_btn)
        action_row.addWidget(self._dry_run_btn)
        lay.addLayout(action_row)

        svc_start_row = QHBoxLayout()
        self._api_start_btn = QPushButton("START API")
        self._api_start_btn.clicked.connect(lambda: self._start_service("api"))
        self._cf_start_btn = QPushButton("START CF")
        self._cf_start_btn.clicked.connect(lambda: self._start_service("cloudflared"))
        self._ollama_start_btn = QPushButton("START OLLAMA")
        self._ollama_start_btn.clicked.connect(lambda: self._start_service("ollama"))
        for btn in (self._api_start_btn, self._cf_start_btn, self._ollama_start_btn):
            btn.setFixedHeight(20)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFont(QFont("Segoe UI", 7))
            btn.setStyleSheet(
                "QPushButton{background:transparent;color:#6adfb8;"
                "border:1px solid #6adfb866;border-radius:4px;font-size:7px;font-weight:bold;}"
                "QPushButton:hover{background:#6adfb822;border-color:#6adfb8;}"
            )
            svc_start_row.addWidget(btn)
        lay.addLayout(svc_start_row)

        svc_stop_row = QHBoxLayout()
        self._api_stop_btn = QPushButton("STOP API")
        self._api_stop_btn.clicked.connect(lambda: self._stop_service("api"))
        self._cf_stop_btn = QPushButton("STOP CF")
        self._cf_stop_btn.clicked.connect(lambda: self._stop_service("cloudflared"))
        self._ollama_stop_btn = QPushButton("STOP OLLAMA")
        self._ollama_stop_btn.clicked.connect(lambda: self._stop_service("ollama"))
        for btn in (self._api_stop_btn, self._cf_stop_btn, self._ollama_stop_btn):
            btn.setFixedHeight(20)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFont(QFont("Segoe UI", 7))
            btn.setStyleSheet(
                "QPushButton{background:transparent;color:#c87050;"
                "border:1px solid #c8705066;border-radius:4px;font-size:7px;font-weight:bold;}"
                "QPushButton:hover{background:#c8705022;border-color:#c87050;}"
            )
            svc_stop_row.addWidget(btn)
        lay.addLayout(svc_stop_row)

        svc_restart_row = QHBoxLayout()
        self._api_restart_btn = QPushButton("RESTART API")
        self._api_restart_btn.clicked.connect(lambda: self._restart_service("api"))
        self._cf_restart_btn = QPushButton("RESTART CF")
        self._cf_restart_btn.clicked.connect(lambda: self._restart_service("cloudflared"))
        self._ollama_restart_btn = QPushButton("RESTART OLLAMA")
        self._ollama_restart_btn.clicked.connect(lambda: self._restart_service("ollama"))
        restart_styles = {
            self._api_restart_btn: "#8ecae6",
            self._cf_restart_btn: "#ffd166",
            self._ollama_restart_btn: "#b8f2a6",
        }
        for btn, color in restart_styles.items():
            btn.setFixedHeight(20)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFont(QFont("Segoe UI", 7))
            btn.setStyleSheet(
                f"QPushButton{{background:transparent;color:{color};"
                f"border:1px solid {color}66;border-radius:4px;font-size:7px;font-weight:bold;}}"
                f"QPushButton:hover{{background:{color}22;border-color:{color};}}"
            )
            svc_restart_row.addWidget(btn)
        lay.addLayout(svc_restart_row)

        self._insight_lbl = QLabel("No analysis yet.")
        self._insight_lbl.setStyleSheet(f"color:{TEXT}; background:transparent; border:none;")
        self._insight_lbl.setFont(QFont("Consolas", 7))
        self._insight_lbl.setWordWrap(True)
        lay.addWidget(self._insight_lbl)

        self._health_lbl = QLabel("")
        self._health_lbl.setStyleSheet(f"color:{DIM}; background:transparent; border:none;")
        self._health_lbl.setFont(QFont("Consolas", 7))
        lay.addWidget(self._health_lbl)

        self._status_files_lbl = QLabel("")
        self._status_files_lbl.setStyleSheet(f"color:{DIM}; background:transparent; border:none;")
        self._status_files_lbl.setFont(QFont("Consolas", 7))
        self._status_files_lbl.setWordWrap(True)
        lay.addWidget(self._status_files_lbl)

        self._lifecycle_log_lbl = QLabel("Lifecycle log: idle")
        self._lifecycle_log_lbl.setStyleSheet(f"color:{DIM}; background:transparent; border:none;")
        self._lifecycle_log_lbl.setFont(QFont("Consolas", 7))
        self._lifecycle_log_lbl.setWordWrap(True)
        lay.addWidget(self._lifecycle_log_lbl)

        self.setStyleSheet(
            f"OperatorCard{{background:{BG2};"
            f"border:1px solid {ACNT}33;border-radius:6px;}}"
        )
        self.refresh()

    def _auto_analyze(self):
        if not self._op:
            return

        def _run():
            insight = self._op.analyze_patterns(force=False)
            if insight and insight != "No analysis yet.":
                self._insight_lbl.setText(
                    f"{insight[:160]}{'...' if len(insight) > 160 else ''}"
                )

        threading.Thread(target=_run, daemon=True).start()

    def _on_analyze(self):
        if not self._op:
            return
        self._analyze_btn.setEnabled(False)
        self._analyze_btn.setText("working...")

        def _run():
            insight = self._op.analyze_patterns(force=True)
            self._insight_lbl.setText(insight)
            self._analyze_btn.setEnabled(True)
            self._analyze_btn.setText("◆ ANALYZE")

        threading.Thread(target=_run, daemon=True).start()

    def _send_test_offer(self):
        if not self._op:
            return
        self._op.send_command(
            "guppy",
            "ambient_offer",
            {
                "type": "manual_test",
                "preview": "Manual ambient offer test from Hub Operator.",
                "length": 39,
            },
        )
        self._op.record_event("hub", "manual_ambient_offer", "operator_card", "sent")

    def _request_status_snap(self):
        if not self._op:
            return
        for aid in ("guppy", "merlin", "council"):
            self._op.send_command(aid, "report_status")

    def _on_dry_run_toggled(self, enabled: bool):
        if enabled:
            self._dry_run_btn.setText("DRY RUN: ON")
            self._dry_run_btn.setStyleSheet(
                "QPushButton{background:transparent;color:#ffd166;"
                "border:1px solid #ffd16688;border-radius:4px;font-size:7px;font-weight:bold;}"
                "QPushButton:hover{background:#ffd16622;border-color:#ffd166;}"
            )
            return

        self._dry_run_btn.setText("DRY RUN: OFF")
        self._dry_run_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#7a7a92;"
            "border:1px solid #7a7a9255;border-radius:4px;font-size:7px;font-weight:bold;}"
            "QPushButton:hover{background:#7a7a9222;border-color:#9a9ab2;}"
        )

    def _dry_run_enabled(self) -> bool:
        return bool(self._dry_run_btn.isChecked())

    def _start_service(self, service: str):
        if not self._op:
            return
        res = self._op.start_service(service, dry_run=self._dry_run_enabled())
        mode = "dry" if self._dry_run_enabled() else "live"
        self._append_lifecycle_log(f"start[{mode}] {service}: {res.get('status', '')}")

    def _stop_service(self, service: str):
        if not self._op:
            return
        res = self._op.stop_service(service, dry_run=self._dry_run_enabled())
        mode = "dry" if self._dry_run_enabled() else "live"
        self._append_lifecycle_log(f"stop[{mode}] {service}: {res.get('status', '')}")

    def _restart_service(self, service: str):
        if not self._op:
            return
        res = self._op.restart_service(service, dry_run=self._dry_run_enabled())
        mode = "dry" if self._dry_run_enabled() else "live"
        self._append_lifecycle_log(f"restart[{mode}] {service}: {res.get('status', '')}")

    def _append_lifecycle_log(self, line: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._lifecycle_log.append(f"[{ts}] {line}")
        self._lifecycle_log = self._lifecycle_log[-4:]
        self._lifecycle_log_lbl.setText("Lifecycle log: " + " | ".join(self._lifecycle_log))

    def refresh(self):
        if not self._op:
            self._health_lbl.setText("operator unavailable")
            return

        self._insight_lbl.setText(
            f"{self._op.last_insight[:160]}{'...' if len(self._op.last_insight) > 160 else ''}"
            if self._op.last_insight != "No analysis yet."
            else f"No analysis yet.  Last: {self._op.analysis_age_str}"
        )

        checks = self._op.full_system_check()
        segs = []
        for svc, res in checks.items():
            mark = "✓" if res["ok"] else "✗"
            col_tag = "#6adfb8" if res["ok"] else "#c87050"
            segs.append(f'<span style="color:{col_tag}">{mark} {svc.upper()}</span>')
        self._health_lbl.setText("  ".join(segs))

        snap = self._op.get_agent_status_snapshot()
        rows = []
        for aid in ("guppy", "merlin", "council"):
            info = snap.get(aid, {})
            if info.get("ok"):
                data = info.get("data", {})
                mode = data.get("mode") or data.get("route") or "-"
                busy = data.get("worker_busy")
                if busy is None:
                    busy = data.get("g_busy") or data.get("m_busy")
                rows.append(f"{aid}: ok mode={mode} busy={busy}")
            else:
                rows.append(f"{aid}: {info.get('status', 'missing')}")
        self._status_files_lbl.setText(" | ".join(rows))
