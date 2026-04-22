"""Main hub window composition and runtime tick loop."""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .agent_card import AgentCard
from .cards import ManagerCard
from .operator_card import OperatorCard
from .orchestration_card import OrchestrationCard
from .status_card import StatusSettingsCard
from .theme_config import ACNT, AGENTS, BG, BG2, BORD, DIM, TEXT


class HubWindow(QWidget):
    def __init__(
        self,
        manager,
        logger,
        load_settings,
        get_window_context,
        daemon_available: bool,
        psutil_module,
        runtime_dir,
        root_dir,
        python_executable: str,
        hb_stale_secs: int,
        operator,
        status_check_fns: dict,
        orchestration_fns: dict,
        parent=None,
    ):
        super().__init__(parent)
        self._mgr = manager
        self._logger = logger
        self._load_settings = load_settings
        self._get_window_context = get_window_context
        self._daemon_available = daemon_available
        self._psutil = psutil_module
        self._psutil_ok = psutil_module is not None
        self._runtime = runtime_dir
        self._root = root_dir
        self._python = python_executable
        self._hb_stale_secs = hb_stale_secs
        self._operator = operator
        self._status_check_fns = status_check_fns
        self._orchestration_fns = orchestration_fns

        self._cards = {}
        self._dragging = False
        self._drag_pos = QPoint()

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setStyleSheet(f"background:{BG}; border:2px solid {ACNT}44; border-radius:10px;")

        self._build_ui()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(8)

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

        self._mgr_card = ManagerCard(self._mgr, TEXT, self)
        lay.addWidget(self._mgr_card)

        for agent in AGENTS:
            card = AgentCard(
                agent=agent,
                root_dir=self._root,
                runtime_dir=self._runtime,
                python_executable=self._python,
                hb_stale_secs=self._hb_stale_secs,
                psutil_module=self._psutil,
                logger=self._logger,
                operator=self._operator,
                parent=self,
            )
            card.launch_requested.connect(self._on_launch)
            card.stop_requested.connect(self._on_stop)
            self._cards[agent["id"]] = card
            lay.addWidget(card)

        if self._operator is not None:
            self._operator_card = OperatorCard(self._operator, self)
            lay.addWidget(self._operator_card)
        else:
            self._operator_card = None

        controls = QHBoxLayout()
        controls.setSpacing(6)
        self._launch_all_btn = QPushButton(">> LAUNCH GUPPY")
        self._launch_all_btn.setFixedHeight(28)
        self._launch_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._launch_all_btn.setStyleSheet(
            f"QPushButton{{background:{BG2};color:{ACNT};"
            f"border:1px solid {ACNT}66;border-radius:6px;"
            "font-size:8px;font-weight:bold;letter-spacing:1px;}}"
            f"QPushButton:hover{{background:{ACNT}22;"
            f"border-color:{ACNT};color:{ACNT};}}"
            f"QPushButton:pressed{{background:{ACNT}33;}}"
        )
        self._launch_all_btn.clicked.connect(self._launch_primary)

        self._stop_all_btn = QPushButton("[] SLUMBER ALL")
        self._stop_all_btn.setFixedHeight(28)
        self._stop_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stop_all_btn.setStyleSheet(
            f"QPushButton{{background:{BG2};color:#c87050;"
            "border:1px solid #c8705055;border-radius:6px;"
            "font-size:8px;font-weight:bold;letter-spacing:1px;}}"
            "QPushButton:hover{background:#c8705022;border-color:#c87050;}"
            "QPushButton:pressed{background:#c8705033;}"
        )
        self._stop_all_btn.clicked.connect(self._stop_all)

        controls.addWidget(self._launch_all_btn)
        controls.addWidget(self._stop_all_btn)
        lay.addLayout(controls)

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
            "font-size:8px; font-family:'Consolas'; letter-spacing:1px;"
        )
        self._ram_lbl = QLabel("RAM  -  --%")
        self._ram_lbl.setStyleSheet(
            f"color:{DIM}; background:transparent; border:none; "
            "font-size:8px; font-family:'Consolas'; letter-spacing:1px;"
        )
        sys_lay.addWidget(self._cpu_lbl)
        sys_lay.addWidget(self._ram_lbl)
        sys_lay.addStretch()
        lay.addWidget(sys_frame)

        self._status_settings = StatusSettingsCard(
            load_app_settings_fn=self._load_settings,
            recommend_runtime_profile_fn=self._status_check_fns["recommend_runtime_profile"],
            check_api_server_fn=self._status_check_fns["check_api_server"],
            check_cloudflared_fn=self._status_check_fns["check_cloudflared"],
            check_auth_config_fn=self._status_check_fns["check_auth_config"],
            cloudflare_cert_paths_fn=self._status_check_fns["cloudflare_cert_paths"],
            is_set_fn=self._status_check_fns["is_set"],
            safe_int_fn=self._status_check_fns["safe_int"],
            parent=self,
        )
        lay.addWidget(self._status_settings)

        self._orchestration = OrchestrationCard(
            tail_agent_performance_fn=self._orchestration_fns["tail_agent_performance"],
            tail_session_events_fn=self._orchestration_fns["tail_session_events"],
            rolling_agent_stats_fn=self._orchestration_fns["rolling_agent_stats"],
            parse_iso_ts_fn=self._orchestration_fns["parse_iso_ts"],
            warm_ollama_model_fn=self._orchestration_fns["warm_ollama_model"],
            model_for_agent_fn=self._orchestration_fns["model_for_agent"],
            parent=self,
        )
        lay.addWidget(self._orchestration)

        close_btn = QPushButton("X  DISMISS")
        close_btn.setFixedHeight(22)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{DIM};"
            f"border:1px solid {BORD};border-radius:4px;"
            "font-size:7px;letter-spacing:1px;}}"
            f"QPushButton:hover{{color:{TEXT};border-color:{DIM};}}"
        )
        close_btn.clicked.connect(self.hide)
        lay.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _tick(self):
        running = [aid for aid, card in self._cards.items() if card.is_running()]

        if self._daemon_available:
            try:
                context = self._get_window_context()
                title = context.get("title", "No title")
                self._logger.debug(f"Window context: {title}")
            except Exception as exc:
                self._logger.warning(f"Failed to get window context: {exc}")
                title = "Sample Window Title"
        else:
            title = "Sample Window Title"

        self._mgr.update_context(title, running)
        rec = self._mgr._recommended_agent
        for aid, card in self._cards.items():
            card.set_recommended(aid == rec)
            card.tick()

        if self._operator_card is not None:
            self._operator_card.refresh()

        if self._psutil_ok:
            try:
                cpu = self._psutil.cpu_percent()
                ram = self._psutil.virtual_memory().percent
                cpu_col = "#c87050" if cpu > 80 else (ACNT if cpu > 50 else DIM)
                ram_col = "#c87050" if ram > 85 else (ACNT if ram > 65 else DIM)
                self._cpu_lbl.setText(f"CPU  -  {cpu:.0f}%")
                self._cpu_lbl.setStyleSheet(
                    f"color:{cpu_col}; background:transparent; border:none; "
                    "font-size:8px; font-family:'Consolas'; letter-spacing:1px;"
                )
                self._ram_lbl.setText(f"RAM  -  {ram:.0f}%")
                self._ram_lbl.setStyleSheet(
                    f"color:{ram_col}; background:transparent; border:none; "
                    "font-size:8px; font-family:'Consolas'; letter-spacing:1px;"
                )
            except Exception:
                self._cpu_lbl.setText("CPU  -  ERR")
                self._ram_lbl.setText("RAM  -  ERR")
        else:
            self._cpu_lbl.setText("CPU  -  N/A")
            self._ram_lbl.setText("RAM  -  N/A")

        self._status_settings.refresh()
        self._orchestration.refresh()

    def _on_launch(self, agent_id: str):
        if agent_id in self._cards:
            try:
                self._cards[agent_id].launch()
            except Exception as exc:
                self._logger.error(f"Error launching {agent_id}: {exc}")

    def _on_stop(self, agent_id: str):
        if agent_id in self._cards:
            try:
                self._cards[agent_id].stop()
            except Exception as exc:
                self._logger.error(f"Error stopping {agent_id}: {exc}")

    def _launch_primary(self):
        primary = "guppy"
        self._logger.info(f"Launching primary surface: {primary}")
        card = self._cards.get(primary)
        if card is not None and not card.is_running():
            card.launch()

    def _stop_all(self):
        self._logger.info("Stopping all agents...")
        for card in self._cards.values():
            if card.isVisible() and card.is_running():
                card.stop()

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
