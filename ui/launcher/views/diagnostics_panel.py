"""
diagnostics_panel.py

Lane: TR54-D5
Responsibilities:
  - Display LauncherDiagnosticsSnapshot.status_lines() as a color-coded table
  - Show last 5 recent events
  - Provide an Export JSON button
  - Embed in Settings > Support or any parent that calls collect_diagnostics()
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.launcher.diagnostics.launcher_diagnostics import (
    LauncherDiagnosticsSnapshot,
    collect_diagnostics,
    export_diagnostics_json,
)

logger = logging.getLogger("launcher.diagnostics.panel")

_SEVERITY_COLOR = {
    "ok": "#00C853",
    "warn": "#FFD600",
    "error": "#FF3D00",
}
_SEVERITY_DOT = {
    "ok": "●",
    "warn": "▲",
    "error": "✕",
}


def _row_widget(label: str, value: str, severity: str) -> QWidget:
    row = QWidget()
    row.setObjectName("diag_row")
    row.setStyleSheet(
        "QWidget#diag_row { background: transparent; border-bottom: 1px solid rgba(214,197,174,0.30); }"
    )
    hl = QHBoxLayout(row)
    hl.setContentsMargins(0, 6, 0, 6)
    hl.setSpacing(8)

    dot_color = _SEVERITY_COLOR.get(severity, "#73604F")
    dot_char = _SEVERITY_DOT.get(severity, "●")
    dot = QLabel(dot_char)
    dot.setFixedWidth(14)
    dot.setStyleSheet(f"color: {dot_color}; font-size: 9pt;")
    hl.addWidget(dot)

    lbl = QLabel(label)
    lbl.setFixedWidth(148)
    lbl.setStyleSheet("color: #73604F; font-family: 'Manrope'; font-size: 9pt;")
    hl.addWidget(lbl)

    val = QLabel(value)
    val.setWordWrap(True)
    val.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    val.setStyleSheet("color: #1B1C19; font-family: 'Manrope'; font-size: 9pt;")
    hl.addWidget(val)

    return row


def _event_label(evt: dict) -> str:
    phase = evt.get("phase") or evt.get("event") or ""
    ts = evt.get("ts") or evt.get("timestamp") or ""
    raw = evt.get("raw", "")
    if raw:
        return raw[:120]
    if phase:
        return f"{phase}  {ts}"[:120]
    return str(evt)[:120]


class DiagnosticsPanel(QFrame):
    """Read-only diagnostics display + export button."""

    export_requested = Signal(str)  # emits export path on success

    def __init__(
        self,
        runtime_dir: Path,
        *,
        active_instance: str = "",
        runtime_backend: str = "",
        export_dir: Optional[Path] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._runtime_dir = runtime_dir
        self._active_instance = active_instance
        self._runtime_backend = runtime_backend
        self._export_dir = export_dir or (runtime_dir / "exports")
        self._snapshot: Optional[LauncherDiagnosticsSnapshot] = None

        self.setObjectName("diagnostics_panel")
        self.setStyleSheet(
            "QFrame#diagnostics_panel {"
            "  background: rgba(245,243,238,0.90);"
            "  border: 1px solid rgba(214,197,174,0.55);"
            "  border-radius: 12px;"
            "}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(10)

        # Header row
        hdr = QHBoxLayout()
        hdr.setSpacing(8)
        title = QLabel("System Diagnostics")
        title.setStyleSheet(
            "color: #1B1C19; font-family: 'Noto Serif'; font-size: 13pt; font-weight: 700;"
        )
        hdr.addWidget(title)
        hdr.addStretch()

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #006A6A; border: 1px solid rgba(0,106,106,0.45);"
            " border-radius: 6px; padding: 3px 10px; font-family: 'Manrope'; font-size: 9pt; }"
            "QPushButton:hover { background: rgba(0,106,106,0.08); }"
        )
        self._refresh_btn.clicked.connect(self.refresh)
        hdr.addWidget(self._refresh_btn)

        self._export_btn = QPushButton("Export JSON")
        self._export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_btn.setStyleSheet(
            "QPushButton { background: #006A6A; color: #fff; border: none;"
            " border-radius: 6px; padding: 3px 10px; font-family: 'Manrope'; font-size: 9pt; }"
            "QPushButton:hover { background: #005252; }"
            "QPushButton:disabled { background: rgba(0,106,106,0.30); color: rgba(255,255,255,0.50); }"
        )
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._do_export)
        hdr.addWidget(self._export_btn)
        outer.addLayout(hdr)

        # Status rows (scrollable)
        self._status_area = QScrollArea()
        self._status_area.setWidgetResizable(True)
        self._status_area.setFrameShape(QFrame.Shape.NoFrame)
        self._status_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._status_area.setFixedHeight(220)
        self._status_container = QWidget()
        self._status_layout = QVBoxLayout(self._status_container)
        self._status_layout.setContentsMargins(0, 0, 0, 0)
        self._status_layout.setSpacing(0)
        self._status_layout.addStretch()
        self._status_area.setWidget(self._status_container)
        outer.addWidget(self._status_area)

        # Recent events section
        events_hdr = QLabel("Recent Events")
        events_hdr.setStyleSheet(
            "color: #73604F; font-family: 'Manrope'; font-size: 8pt; font-weight: 700; letter-spacing: 1px;"
        )
        outer.addWidget(events_hdr)

        self._events_lbl = QLabel("—")
        self._events_lbl.setWordWrap(True)
        self._events_lbl.setStyleSheet(
            "color: #1B1C19; font-family: 'JetBrains Mono'; font-size: 8pt;"
            " background: rgba(224,219,209,0.45); border-radius: 6px; padding: 6px 8px;"
        )
        outer.addWidget(self._events_lbl)

        self._collected_at_lbl = QLabel("")
        self._collected_at_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._collected_at_lbl.setStyleSheet(
            "color: rgba(115,96,79,0.60); font-family: 'Manrope'; font-size: 7pt;"
        )
        outer.addWidget(self._collected_at_lbl)

        self.refresh()

    def refresh(self) -> None:
        self._snapshot = collect_diagnostics(
            runtime_dir=self._runtime_dir,
            active_instance=self._active_instance,
            runtime_backend=self._runtime_backend,
        )
        self._render(self._snapshot)
        self._export_btn.setEnabled(True)

    def _render(self, snap: LauncherDiagnosticsSnapshot) -> None:
        # Clear old status rows (keep the trailing stretch)
        layout = self._status_layout
        while layout.count() > 1:
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for label, value, severity in snap.status_lines():
            layout.insertWidget(layout.count() - 1, _row_widget(label, value, severity))

        # Recent events (last 5)
        events = snap.recent_events[-5:] if snap.recent_events else []
        if events:
            lines = [_event_label(e) for e in reversed(events)]
            self._events_lbl.setText("\n".join(lines))
        else:
            self._events_lbl.setText("No events recorded yet.")

        self._collected_at_lbl.setText(f"Collected {snap.collected_at}")

    def _do_export(self) -> None:
        if self._snapshot is None:
            return
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = self._export_dir / f"guppy_diagnostics_{ts}.json"
        ok = export_diagnostics_json(self._snapshot, target)
        if ok:
            self._export_btn.setText("Exported ✓")
            self.export_requested.emit(str(target))
            logger.info("Diagnostics exported to %s", target)
        else:
            self._export_btn.setText("Export failed")
            logger.error("Diagnostics export failed")

    def update_context(
        self,
        *,
        active_instance: str = "",
        runtime_backend: str = "",
    ) -> None:
        self._active_instance = active_instance
        self._runtime_backend = runtime_backend
