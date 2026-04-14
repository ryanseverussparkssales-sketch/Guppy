"""
ui/launcher/views/advanced_view.py
APP MGMT tab — app-level recovery actions, diagnostics, and operator logs.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import tokens as T

_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _legacy_compat_enabled() -> bool:
    return os.environ.get("GUPPY_ENABLE_LEGACY_SURFACES", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _mono(text: str, color: str = T.DIM, size: int = T.FS_SMALL, bold: bool = False) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}';"
        f"font-size: {size}pt; letter-spacing: 1px;"
        + ("font-weight: bold;" if bold else "")
    )
    return lbl


class _SurfaceCard(QFrame):
    def __init__(
        self,
        name: str,
        tagline: str,
        description: str,
        accent: str,
        mode_options: list[str],
        launch_script: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._launch_script = launch_script
        self._name = name
        self._process: subprocess.Popen | None = None
        self._legacy_enabled = _legacy_compat_enabled()

        self.setObjectName("surface_card")
        self.setStyleSheet(
            f"QFrame#surface_card {{"
            f"  background-color: {T.BG1};"
            f"  border: 1px solid {T.BORDER};"
            f"}}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(0)

        # ── Accent bar ────────────────────────────────────────────────────────
        bar = QFrame()
        bar.setFixedHeight(2)
        bar.setStyleSheet(f"background: {accent}; border: none;")
        bar.setMaximumWidth(self.width())
        root.insertWidget(0, bar)
        root.addSpacing(16)

        # ── Header: name + icon ───────────────────────────────────────────────
        hdr = QHBoxLayout()
        name_lbl = QLabel(name.upper())
        name_lbl.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_HEAD}';"
            f"font-size: 22pt; font-weight: 900; letter-spacing: -1px;"
        )
        tag_lbl = QLabel(tagline)
        tag_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        hdr.addWidget(name_lbl)
        hdr.addStretch()
        root.addLayout(hdr)
        root.addWidget(tag_lbl)
        root.addSpacing(12)

        # ── Description ───────────────────────────────────────────────────────
        desc_lbl = QLabel(description)
        desc_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_BODY}';"
            f"font-size: {T.FS_BODY}pt; line-height: 160%;"
        )
        desc_lbl.setWordWrap(True)
        root.addWidget(desc_lbl)
        root.addSpacing(16)

        # ── Mode dropdown ─────────────────────────────────────────────────────
        mode_lbl = _mono("EXECUTION MODE", T.BORDER, T.FS_TINY)
        self._mode_cb = QComboBox()
        self._mode_cb.addItems(mode_options)
        self._mode_cb.setFixedWidth(200)
        root.addWidget(mode_lbl)
        root.addSpacing(4)
        root.addWidget(self._mode_cb)
        root.addSpacing(20)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        open_btn = QPushButton("OPEN INTERFACE  →")
        open_btn.setStyleSheet(
            f"QPushButton {{"
            f"  color: {accent}; border: 1px solid {accent};"
            f"  font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
            f"  letter-spacing: 2px; padding: 5px 16px;"
            f"}}"
            f"QPushButton:hover {{ background-color: {accent}; color: {T.BG}; }}"
        )
        open_btn.clicked.connect(self._launch)

        self._deploy_btn = QPushButton("DEPLOY SURFACE  ⬆")
        self._deploy_btn.setStyleSheet(
            f"QPushButton {{"
            f"  color: {T.DIM}; border: 1px solid {T.BORDER};"
            f"  font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
            f"  letter-spacing: 2px; padding: 5px 16px;"
            f"}}"
            f"QPushButton:hover {{ border-color: {accent}; color: {accent}; }}"
        )
        self._deploy_btn.clicked.connect(self._deploy)

        btn_row.addWidget(open_btn)
        btn_row.addWidget(self._deploy_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        # ── Deploy status label ───────────────────────────────────────────────
        self._deploy_status = _mono("", T.DIM, T.FS_TINY)
        root.addSpacing(6)
        root.addWidget(self._deploy_status)

        if not self._legacy_enabled:
            open_btn.setEnabled(False)
            self._deploy_btn.setEnabled(False)
            self._deploy_status.setText(
                "EMBEDDED-ONLY MODE: set GUPPY_ENABLE_LEGACY_SURFACES=1 to enable"
            )

        root.addStretch()

    def _launch(self) -> None:
        if not self._legacy_enabled:
            self._deploy_status.setText(
                "BLOCKED: embedded-only default flow (enable legacy compatibility to launch)"
            )
            return
        script = _ROOT / self._launch_script
        if not script.exists():
            self._deploy_status.setText(f"ERR: {self._launch_script} not found")
            return
        if self._process and self._process.poll() is None:
            self._deploy_status.setText(f"ALREADY RUNNING  [pid={self._process.pid}]")
            return
        try:
            self._process = subprocess.Popen([sys.executable, str(script)])
            self._deploy_status.setText(f"SURFACE OPEN  [pid={self._process.pid}]")
        except Exception as exc:
            self._deploy_status.setText(f"OPEN FAILED: {exc}")

    def _deploy(self) -> None:
        if not self._legacy_enabled:
            self._deploy_status.setText(
                "BLOCKED: embedded-only default flow (enable legacy compatibility to deploy)"
            )
            return
        script = _ROOT / self._launch_script
        if not script.exists():
            self._deploy_status.setText(f"ERR: {self._launch_script} not found")
            return
        if self._process and self._process.poll() is None:
            self._deploy_status.setText(f"ALREADY RUNNING  [pid={self._process.pid}]")
            return
        profile = self._mode_cb.currentText().lower()
        self._deploy_status.setText(f"DEPLOYING [{profile}]...")
        self._deploy_btn.setEnabled(False)
        try:
            self._process = subprocess.Popen(
                [sys.executable, str(script)],
                env={**os.environ, "GUPPY_DEPLOY_MODE": profile},
            )
            self._deploy_status.setText(
                f"SURFACE DEPLOYED  [{profile}] [pid={self._process.pid}]"
            )
        except Exception as exc:
            self._deploy_status.setText(f"DEPLOY FAILED: {exc}")
        finally:
            self._deploy_btn.setEnabled(True)

    @property
    def selected_mode(self) -> str:
        return self._mode_cb.currentText()


class AdvancedView(QWidget):
    recovery_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._diagnostics: dict[str, str] = {}
        self._log_filter = "ALL"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(20)

        # ── Page title ────────────────────────────────────────────────────────
        title_row = QHBoxLayout()
        title = QLabel("App Management")
        title.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_HEAD}';"
            f"font-size: 30pt; font-weight: 900; letter-spacing: -1px;"
        )
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)

        # sub-info
        info_row = QHBoxLayout()
        info_row.setSpacing(8)
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {T.PRIMARY}; font-size: {T.FS_TINY}pt;")
        info_row.addWidget(dot)
        info_row.addWidget(_mono("APP-LEVEL OPERATIONS ONLY", T.PRIMARY, T.FS_TINY))
        info_row.addSpacing(12)
        info_row.addWidget(_mono("RECOVERY · DIAGNOSTICS · OPERATOR LOGS", T.DIM, T.FS_TINY))
        info_row.addStretch()
        layout.addLayout(info_row)
        layout.addSpacing(12)

        boundary = QFrame()
        boundary.setStyleSheet(
            f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}"
        )
        boundary_layout = QVBoxLayout(boundary)
        boundary_layout.setContentsMargins(12, 10, 12, 10)
        boundary_layout.setSpacing(4)
        boundary_layout.addWidget(_mono("BOUNDARY", T.PRIMARY, T.FS_TINY, True))
        boundary_layout.addWidget(_mono("Restart, warmup, runtime audit, and diagnostics live here. Instance tool usage stays in AGENT TOOLS.", T.DIM, T.FS_SMALL))
        layout.addWidget(boundary)

        actions_frame = QFrame()
        actions_frame.setStyleSheet(
            f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}"
        )
        actions_layout = QVBoxLayout(actions_frame)
        actions_layout.setContentsMargins(16, 14, 16, 14)
        actions_layout.setSpacing(10)
        actions_layout.addWidget(_mono("RECOVERY ACTIONS", T.PRIMARY, T.FS_TINY, True))

        self._recovery_status = _mono("Recovery idle", T.DIM, T.FS_TINY)
        actions_layout.addWidget(self._recovery_status)

        action_row = QHBoxLayout()
        for label, action, accent in [
            ("SNAPSHOT", "health_snapshot", T.PRIMARY),
            ("WARMUP", "warmup", T.PRIMARY_DIM),
            ("RESTART DAEMON", "restart_daemon", T.ERROR),
            ("AUDIT RUNTIME", "audit_runtime", T.SECONDARY),
        ]:
            btn = QPushButton(label)
            btn.setStyleSheet(
                f"QPushButton {{ background: {T.BG0}; color: {accent}; border: 1px solid {accent};"
                f" padding: 5px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ background: {accent}; color: {T.BG}; }}"
            )
            btn.clicked.connect(lambda _=False, a=action: self.recovery_requested.emit(a))
            action_row.addWidget(btn)
        action_row.addStretch()
        actions_layout.addLayout(action_row)
        layout.addWidget(actions_frame)

        diag_frame = QFrame()
        diag_frame.setStyleSheet(
            f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}"
        )
        diag_layout = QVBoxLayout(diag_frame)
        diag_layout.setContentsMargins(16, 14, 16, 14)
        diag_layout.setSpacing(8)
        diag_layout.addWidget(_mono("SYSTEM HEALTH", T.PRIMARY, T.FS_TINY, True))
        self._health_lbl = _mono("API: unknown", T.DIM, T.FS_SMALL)
        self._instances_lbl = _mono("Instances: unknown", T.DIM, T.FS_SMALL)
        self._voice_lbl = _mono("Voice: unknown", T.DIM, T.FS_SMALL)
        self._resource_lbl = _mono("Resource envelope: unknown", T.DIM, T.FS_SMALL)
        self._last_recovery_lbl = _mono("Last recovery: idle", T.DIM, T.FS_SMALL)
        for widget in [
            self._health_lbl,
            self._instances_lbl,
            self._voice_lbl,
            self._resource_lbl,
            self._last_recovery_lbl,
        ]:
            widget.setWordWrap(True)
            diag_layout.addWidget(widget)
        layout.addWidget(diag_frame)

        term = QFrame()
        term.setObjectName("syslog_term")
        term.setStyleSheet(
            f"QFrame#syslog_term {{ background-color: {T.BG0}; border: 1px solid {T.BORDER}; }}"
        )
        term_layout = QVBoxLayout(term)
        term_layout.setContentsMargins(16, 12, 16, 12)
        term_layout.setSpacing(6)

        term_hdr = QHBoxLayout()
        term_hdr.addWidget(_mono("OPERATOR LOGS", T.DIM, T.FS_TINY))
        term_hdr.addStretch()
        self._filter_cb = QComboBox()
        self._filter_cb.addItems(["ALL", "WARN", "ERROR"])
        self._filter_cb.setStyleSheet(
            f"QComboBox {{ background: {T.BG1}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
            f" font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; padding: 2px 6px; }}"
        )
        self._filter_cb.currentTextChanged.connect(self._set_log_filter)
        term_hdr.addWidget(self._filter_cb)
        term_layout.addLayout(term_hdr)

        self._syslog = QPlainTextEdit()
        self._syslog.setReadOnly(True)
        self._syslog.setMinimumHeight(200)
        self._syslog.setStyleSheet(
            f"QPlainTextEdit {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
            f" font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        )
        term_layout.addWidget(self._syslog)
        layout.addWidget(term)

        if _legacy_compat_enabled():
            legacy_row = QHBoxLayout()
            legacy_row.setSpacing(16)
            self._merlin_card = _SurfaceCard(
                name="Merlin",
                tagline="LEGACY_COMPAT",
                description="Compatibility-only standalone launcher for direct Merlin surface testing.",
                accent=T.SECONDARY,
                mode_options=["Standard_Recursive", "Greedy_Heuristic", "Deterministic_Depth"],
                launch_script="merlin_ui.py",
            )
            self._council_card = _SurfaceCard(
                name="Council",
                tagline="LEGACY_COMPAT",
                description="Compatibility-only standalone launcher for Council surface testing.",
                accent=T.TERTIARY,
                mode_options=["Adversarial_Consensus", "Weighted_Average", "Plurality_Rule"],
                launch_script="council_ui.py",
            )
            legacy_row.addWidget(self._merlin_card)
            legacy_row.addWidget(self._council_card)
            layout.addWidget(_mono("LEGACY COMPATIBILITY SURFACES", T.DIM, T.FS_TINY, True))
            layout.addLayout(legacy_row)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

        timer = QTimer(self)
        timer.timeout.connect(self._refresh_operator_logs)
        timer.start(4000)
        self._refresh_operator_logs()

    def append_log(self, line: str) -> None:
        current = self._syslog.toPlainText().splitlines()
        current.append(f"> {line}")
        self._syslog.setPlainText("\n".join(current[-40:]))

    def set_recovery_status(self, text: str) -> None:
        msg = (text or "Recovery idle").strip() or "Recovery idle"
        self._recovery_status.setText(msg)
        self._last_recovery_lbl.setText(f"Last recovery: {msg}")

    def set_status_snapshot(self, payload: dict[str, object]) -> None:
        api_state = str(payload.get("status", "unknown") or "unknown").upper()
        startup = payload.get("startup_readiness", {})
        startup_overall = "unknown"
        if isinstance(startup, dict):
            startup_overall = str(startup.get("overall", startup.get("status", "unknown")) or "unknown").upper()
        self._health_lbl.setText(f"API: {api_state} · Startup readiness: {startup_overall}")

        voice_tts = str(payload.get("voice_tts_backend", "unknown") or "unknown")
        voice_stt = str(payload.get("voice_stt_backend", "unknown") or "unknown")
        self._voice_lbl.setText(f"Voice: tts={voice_tts} · stt={voice_stt}")

        envelope = payload.get("resource_envelope", {})
        if isinstance(envelope, dict):
            state = str(envelope.get("state", "unknown") or "unknown")
            detail = str(envelope.get("message", envelope.get("detail", "")) or "").strip()
            self._resource_lbl.setText(f"Resource envelope: {state}" + (f" · {detail}" if detail else ""))

    def set_instance_snapshot(self, payload: dict[str, object]) -> None:
        limits = payload.get("limits", {}) if isinstance(payload, dict) else {}
        configured = int(limits.get("configured", 0) or 0) if isinstance(limits, dict) else 0
        max_configured = int(limits.get("max_configured", 5) or 5) if isinstance(limits, dict) else 5
        active_runtime = int(limits.get("active_runtime", 0) or 0) if isinstance(limits, dict) else 0
        max_active_runtime = int(limits.get("max_active_runtime", 2) or 2) if isinstance(limits, dict) else 2
        active_instance = str(payload.get("active_instance", "—") or "—") if isinstance(payload, dict) else "—"
        self._instances_lbl.setText(
            f"Instances: active={active_instance} · configured {configured}/{max_configured} · runtime-active {active_runtime}/{max_active_runtime}"
        )

    def _set_log_filter(self, value: str) -> None:
        self._log_filter = (value or "ALL").strip().upper() or "ALL"
        self._refresh_operator_logs()

    def _event_level(self, item: dict[str, object]) -> str:
        event = str(item.get("event", "") or "").lower()
        summary = json.dumps(item, ensure_ascii=True).lower()
        if "error" in event or "error" in summary or "failed" in summary:
            return "ERROR"
        if "warn" in event or "warning" in summary or "over_budget" in event:
            return "WARN"
        return "INFO"

    def _read_launcher_events(self) -> list[dict[str, object]]:
        path = _ROOT / "runtime" / "launcher_events.jsonl"
        if not path.exists():
            return []
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            return []
        items: list[dict[str, object]] = []
        for line in lines[-120:]:
            txt = line.strip()
            if not txt:
                continue
            try:
                obj = json.loads(txt)
            except Exception:
                continue
            if isinstance(obj, dict):
                items.append(obj)
        return items

    def _refresh_operator_logs(self) -> None:
        items = self._read_launcher_events()
        lines: list[str] = []
        for item in items:
            level = self._event_level(item)
            if self._log_filter != "ALL" and level != self._log_filter:
                continue
            ts = str(item.get("ts", ""))
            event = str(item.get("event", "event"))
            detail = ""
            if event in {"recovery_result", "recovery_error"}:
                detail = str(item.get("summary", ""))
            elif event == "auth_retry_result":
                detail = str(item.get("error", "ok"))
            elif event == "ui_poll_over_budget":
                detail = f"poll_ms={item.get('poll_ms', '?')}"
            elif event == "startup_phase_over_budget":
                detail = f"phase={item.get('phase', '?')} duration={item.get('duration_ms', '?')}ms"
            lines.append(f"[{level}] {ts} {event}" + (f" :: {detail}" if detail else ""))
        self._syslog.setPlainText("\n".join(lines[-50:]) if lines else "No operator log entries matched the current filter.")
