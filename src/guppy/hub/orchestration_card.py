"""Runtime orchestration/routing card for hub window."""
from __future__ import annotations

import threading
from datetime import datetime, timezone

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from .theme_config import ACNT, BG2, DIM, SILV


class OrchestrationCard(QFrame):
    _REFRESH_INTERVAL = 2
    _WINDOW_SECONDS = 900

    def __init__(
        self,
        tail_agent_performance_fn,
        tail_session_events_fn,
        rolling_agent_stats_fn,
        parse_iso_ts_fn,
        warm_ollama_model_fn,
        model_for_agent_fn,
        parent=None,
    ):
        super().__init__(parent)
        self._tail_agent_performance = tail_agent_performance_fn
        self._tail_session_events = tail_session_events_fn
        self._rolling_agent_stats = rolling_agent_stats_fn
        self._parse_iso_ts = parse_iso_ts_fn
        self._warm_ollama_model = warm_ollama_model_fn
        self._model_for_agent = model_for_agent_fn

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
                ok, info = self._warm_ollama_model(model)
                with self._warm_lock:
                    self._warm_state[aid] = "warm" if ok else f"error:{info[:40]}"

        t = threading.Thread(target=_job, daemon=True)
        t.start()

    def _warm_all(self):
        targets = []
        seen = set()
        for aid in ("guppy",):
            model = self._model_for_agent(aid)
            if model and model not in seen:
                seen.add(model)
                targets.append((aid, model))
        self._warm_models_async(targets)

    def _warm_local_pair(self):
        targets = []
        for aid in ("guppy",):
            model = self._model_for_agent(aid)
            if model:
                targets.append((aid, model))
        self._warm_models_async(targets)

    def refresh(self):
        self._tick_counter += 1
        if self._tick_counter % self._REFRESH_INTERVAL:
            self._paint_warm_state_only()
            return

        perf_rows = self._tail_agent_performance(limit=900)
        session_rows = self._tail_session_events(limit=900)
        now = datetime.now(timezone.utc)
        by_agent = self._rolling_agent_stats(
            perf_rows,
            session_rows,
            window_seconds=self._WINDOW_SECONDS,
        )

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

            ts = self._parse_iso_ts(str(row.get("ts", "")))
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
