"""
ui/launcher/components/status_panel.py
260-px right-side live-status panel with bar gauges, badge states,
event log, and sparkline.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import tokens as T
from .sparkline import Sparkline


def _mono(text: str, color: str = T.DIM, size: int = T.FS_TINY) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}';"
        f"font-size: {size}pt; letter-spacing: 1px;"
    )
    return lbl


def _kv(key: str, value: str, val_color: str = T.TEXT) -> QWidget:
    w = QWidget()
    w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 2, 0, 2)
    h.setSpacing(0)
    h.addWidget(_mono(key))
    h.addStretch()
    h.addWidget(_mono(value, color=val_color, size=T.FS_SMALL))
    return w


class _BadgeRow(QWidget):
    """Key + coloured badge label (ONLINE / NOMINAL / ERROR)."""

    _COLORS = {
        "ONLINE":  T.GREEN,
        "NOMINAL": T.PRIMARY,
        "ERROR":   T.ERROR,
        "STOPPED": T.DIM,
        "ACTIVE":  T.GREEN,
    }

    def __init__(self, key: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(0)
        row.addWidget(_mono(key))
        row.addStretch()
        self._badge = QLabel("—")
        self._badge.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
            f"border: 1px solid {T.BORDER}; padding: 0 4px;"
        )
        row.addWidget(self._badge)

    def set_badge(self, state: str) -> None:
        color = self._COLORS.get(state.upper(), T.DIM)
        self._badge.setText(state.upper())
        self._badge.setStyleSheet(
            f"color: {color}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
            f"border: 1px solid {color}; padding: 0 4px;"
        )


class _GaugeBar(QWidget):
    """Label + thin horizontal progress bar."""

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 4, 0, 0)
        col.setSpacing(2)

        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.addWidget(_mono(label))
        hdr.addStretch()
        self._val_lbl = _mono("—", T.PRIMARY, T.FS_TINY)
        hdr.addWidget(self._val_lbl)
        col.addLayout(hdr)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setFixedHeight(4)
        self._bar.setTextVisible(False)
        self._bar.setStyleSheet(
            f"QProgressBar {{"
            f"  background: {T.BORDER}; border: none; border-radius: 2px;"
            f"}}"
            f"QProgressBar::chunk {{"
            f"  background: {T.PRIMARY}; border-radius: 2px;"
            f"}}"
        )
        col.addWidget(self._bar)

    def set_value(self, pct: float, label: str = "") -> None:
        v = max(0, min(100, int(pct)))
        self._bar.setValue(v)
        self._val_lbl.setText(label or f"{v}%")

        # Color the chunk by severity
        if v >= 85:
            chunk_color = T.ERROR
        elif v >= 65:
            chunk_color = T.PRIMARY
        else:
            chunk_color = T.GREEN
        self._bar.setStyleSheet(
            f"QProgressBar {{ background: {T.BORDER}; border: none; border-radius: 2px; }}"
            f"QProgressBar::chunk {{ background: {chunk_color}; border-radius: 2px; }}"
        )


class StatusPanel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(T.STATUS_W)
        self.setObjectName("status_panel")
        self.setStyleSheet(
            f"QFrame#status_panel {{"
            f"  background-color: {T.BG1};"
            f"  border-left: 1px solid {T.BORDER};"
            f"}}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 20, 16, 16)
        outer.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = QLabel("LIVE STATUS")
        hdr.setStyleSheet(
            f"color: {T.PRIMARY}; font-family: '{T.FF_HEAD}';"
            f"font-size: {T.FS_SMALL}pt; font-weight: bold; letter-spacing: 4px;"
        )
        outer.addWidget(hdr)

        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background: {T.BORDER};")
        outer.addWidget(div)
        outer.addSpacing(10)

        # ── Scrollable status rows ────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._rows_layout = QVBoxLayout(content)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(2)

        # Badge rows for agent status
        self._b_guppy   = _BadgeRow("GUPPY")
        self._b_merlin  = _BadgeRow("MERLIN")
        self._b_daemon  = _BadgeRow("DAEMON")
        for w in [self._b_guppy, self._b_merlin, self._b_daemon]:
            self._rows_layout.addWidget(w)

        self._rows_layout.addSpacing(6)

        # Standard kv rows
        self._r_profile = _kv("PROFILE", "—")
        self._r_voice   = _kv("VOICE",   "—")
        self._r_wake    = _kv("WAKE",    "—")
        self._r_model   = _kv("MODEL",   "—", T.PRIMARY)
        self._r_latency = _kv("LATENCY", "—")

        for w in [self._r_profile, self._r_voice, self._r_wake,
                  self._r_model, self._r_latency]:
            self._rows_layout.addWidget(w)

        self._rows_layout.addSpacing(6)

        # Gauge bars
        self._g_latency = _GaugeBar("LATENCY")
        self._g_load    = _GaugeBar("CORE LOAD")
        self._g_mem     = _GaugeBar("MEMORY")
        for g in [self._g_latency, self._g_load, self._g_mem]:
            self._rows_layout.addWidget(g)

        self._rows_layout.addSpacing(6)

        # Last query
        lq_col = QVBoxLayout()
        lq_col.setSpacing(2)
        lq_col.setContentsMargins(0, 4, 0, 4)
        lq_col.addWidget(_mono("LAST QUERY"))
        self._last_query = _mono("—", color=T.TEXT, size=T.FS_SMALL)
        self._last_query.setWordWrap(True)
        lq_col.addWidget(self._last_query)
        self._rows_layout.addLayout(lq_col)
        self._rows_layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

        # ── Sparkline ─────────────────────────────────────────────────────────
        outer.addSpacing(8)
        spark_hdr = QHBoxLayout()
        spark_hdr.setContentsMargins(0, 0, 0, 4)
        spark_hdr.addWidget(_mono("NEURAL LOAD"))
        self._load_pct_lbl = _mono("—", color=T.PRIMARY, size=T.FS_SMALL)
        spark_hdr.addStretch()
        spark_hdr.addWidget(self._load_pct_lbl)
        outer.addLayout(spark_hdr)

        self._sparkline = Sparkline()
        outer.addWidget(self._sparkline)

        # ── Syslog ────────────────────────────────────────────────────────────
        outer.addSpacing(10)
        syslog_hdr = QWidget()
        syslog_hdr.setStyleSheet(
            f"background-color: {T.BG4}; border-top: 2px solid {T.PRIMARY};"
        )
        slog_layout = QVBoxLayout(syslog_hdr)
        slog_layout.setContentsMargins(8, 6, 8, 6)
        slog_layout.setSpacing(2)
        slog_title = _mono("SYSLOG_FEED", color=T.PRIMARY, size=T.FS_TINY)
        slog_title.setStyleSheet(
            slog_title.styleSheet() + "font-weight: bold; letter-spacing: 2px;"
        )
        slog_layout.addWidget(slog_title)
        self._syslog_lbl = QLabel("> System ready")
        self._syslog_lbl.setStyleSheet(
            f"color: rgba(229,226,225,0.5); font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt;"
        )
        self._syslog_lbl.setWordWrap(True)
        slog_layout.addWidget(self._syslog_lbl)

        self._recovery_lbl = QLabel("RECOVERY: IDLE")
        self._recovery_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        self._recovery_lbl.setWordWrap(True)
        slog_layout.addWidget(self._recovery_lbl)
        outer.addWidget(syslog_hdr)

    # ── Public API ────────────────────────────────────────────────────────────
    def update_status(self, data: dict) -> None:
        def _set_kv(widget: QWidget, value: str, val_color: str = T.TEXT) -> None:
            lbls = widget.findChildren(QLabel)
            if len(lbls) >= 2:
                lbls[1].setText(value.upper())
                lbls[1].setStyleSheet(
                    f"color: {val_color}; font-family: '{T.FF_MONO}';"
                    f"font-size: {T.FS_SMALL}pt; letter-spacing: 1px;"
                )

        # Badge states
        guppy_online = data.get("guppy_online", False)
        merlin_online = data.get("merlin_online", False)
        daemon_on = data.get("daemon", False)

        self._b_guppy.set_badge("ONLINE" if guppy_online else "ERROR")
        self._b_merlin.set_badge("ONLINE" if merlin_online else "NOMINAL")
        self._b_daemon.set_badge("ACTIVE" if daemon_on else "STOPPED")

        # KV rows
        _set_kv(self._r_profile, data.get("profile", "—"))
        _set_kv(self._r_voice, data.get("voice_engine", data.get("voice", "—")))
        _set_kv(self._r_wake, data.get("wake_word", "—"), T.PRIMARY)
        _set_kv(self._r_model, data.get("model", "—"), T.PRIMARY)

        raw_lat = data.get("latency", "—")
        _set_kv(self._r_latency, str(raw_lat) if raw_lat != "—" else "—")

        # Gauge bars
        try:
            lat_ms = float(raw_lat)
            # Map 0-5000ms → 0-100%
            self._g_latency.set_value(min(lat_ms / 50, 100), f"{lat_ms:.0f}ms")
        except (ValueError, TypeError):
            self._g_latency.set_value(0, "—")

        load = data.get("load_pct", data.get("cpu_load_pct", None))
        if load is not None:
            try:
                load_f = float(load)
                self._g_load.set_value(load_f, f"{load_f:.1f}%")
                self._load_pct_lbl.setText(f"{load_f:.1f}%")
                self._sparkline.push(load_f / 100.0)
            except (ValueError, TypeError):
                pass

        # Memory gauge — read from psutil if available, otherwise skip
        try:
            import psutil
            mem = psutil.virtual_memory()
            self._g_mem.set_value(mem.percent, f"{mem.percent:.0f}%")
        except Exception:
            pass

        self._last_query.setText(f'"{data.get("last_query", "—")}"')

    def append_syslog(self, line: str) -> None:
        existing = self._syslog_lbl.text()
        lines = existing.split("\n") + [f"> {line}"]
        self._syslog_lbl.setText("\n".join(lines[-4:]))

    def set_recovery_outcome(self, action: str, ok: bool, summary: str) -> None:
        state = "OK" if ok else "ERROR"
        color = T.GREEN if ok else T.ERROR
        text = f"RECOVERY: {action.upper()} {state}"
        if summary:
            text = f"{text} — {summary}"
        self._recovery_lbl.setText(text)
        self._recovery_lbl.setStyleSheet(
            f"color: {color}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
