"""
ui/launcher/views/advanced_view.py
ADVANCED tab — Merlin and Council surface cards with mode dropdowns
and "Open Interface" + "Deploy Surface" launch buttons.  Includes a live syslog feed.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
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


def _mono(text: str, color: str = T.DIM, size: int = T.FS_SMALL) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}';"
        f"font-size: {size}pt; letter-spacing: 1px;"
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
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

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
        title = QLabel("Advanced Surfaces")
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
        info_row.addWidget(_mono("SYSTEM ONLINE", T.PRIMARY, T.FS_TINY))
        info_row.addSpacing(12)
        info_row.addWidget(_mono("REF: GUP-ADV-01", T.DIM, T.FS_TINY))
        info_row.addStretch()
        layout.addLayout(info_row)
        layout.addSpacing(12)

        # ── Surface cards ─────────────────────────────────────────────────────
        cards_row = QHBoxLayout()
        cards_row.setSpacing(16)

        self._merlin_card = _SurfaceCard(
            name="Merlin",
            tagline="LOGIC_ORCHESTRATOR",
            description=(
                "The Merlin surface specialises in deep recursive reasoning and "
                "symbolic logic translation. Ideal for high-complexity architectural planning."
            ),
            accent=T.SECONDARY,
            mode_options=["Standard_Recursive", "Greedy_Heuristic", "Deterministic_Depth"],
            launch_script="merlin_ui.py",
        )
        self._council_card = _SurfaceCard(
            name="Council",
            tagline="CONSENSUS_ENGINE",
            description=(
                "The Council surface utilises multi-agent simulation to evaluate risk and "
                "ethical alignment across divergent future-state scenarios."
            ),
            accent=T.TERTIARY,
            mode_options=["Adversarial_Consensus", "Weighted_Average", "Plurality_Rule"],
            launch_script="council_ui.py",
        )

        cards_row.addWidget(self._merlin_card)
        cards_row.addWidget(self._council_card)
        layout.addLayout(cards_row)

        # ── Syslog terminal ───────────────────────────────────────────────────
        layout.addSpacing(12)
        term = QFrame()
        term.setObjectName("syslog_term")
        term.setStyleSheet(
            f"QFrame#syslog_term {{"
            f"  background-color: {T.BG0}; border: 1px solid {T.BORDER};"
            f"}}"
        )
        term_layout = QVBoxLayout(term)
        term_layout.setContentsMargins(16, 12, 16, 12)
        term_layout.setSpacing(4)

        term_hdr = QHBoxLayout()
        term_hdr.addWidget(_mono("REALTIME_STREAM_OUTPUT", T.DIM, T.FS_TINY))
        term_hdr.addStretch()
        term_hdr.addWidget(_mono("RAW_SOCKET_CONNECT_STABLE", T.BORDER, T.FS_TINY))
        term_layout.addLayout(term_hdr)

        self._syslog = QLabel("> SYSTEM READY")
        self._syslog.setStyleSheet(
            f"color: rgba(229,226,225,0.5); font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; line-height: 180%;"
        )
        self._syslog.setWordWrap(True)
        term_layout.addWidget(self._syslog)
        layout.addWidget(term)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

        # ── Ticker ────────────────────────────────────────────────────────────
        self._tick = 0
        timer = QTimer(self)
        timer.timeout.connect(self._tick_log)
        timer.start(5000)

    def _tick_log(self) -> None:
        import time
        ts = time.strftime("%H:%M:%S")
        msgs = [
            f"[{ts}] SYSCALL: HEARTBEAT_PING",
            f"[{ts}] BUFFER: cleared (4.1 KB)",
            f"[{ts}] UPLINK: stable @ 14ms",
            f"[{ts}] LISTENING_FOR_EVENTS...",
        ]
        self._tick = (self._tick + 1) % len(msgs)
        lines = self._syslog.text().split("\n") + [msgs[self._tick]]
        self._syslog.setText("\n".join(lines[-6:]))

    def append_log(self, line: str) -> None:
        lines = self._syslog.text().split("\n") + [f"> {line}"]
        self._syslog.setText("\n".join(lines[-6:]))
