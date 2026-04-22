"""
ui/launcher/components/status_panel.py
Right-side workspace drawer for daily context, primary actions, and optional extras.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import tokens as T


def _mono(text: str, color: str = T.DIM, size: int = T.FS_TINY, bold: bool = False) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}';"
        f"font-size: {size}pt; letter-spacing: 1px;"
        + ("font-weight: bold;" if bold else "")
    )
    return lbl


def _workspace_kind_label(workspace_type: str) -> str:
    key = str(workspace_type or "").strip().lower()
    return {
        "user_instance": "DAILY",
        "builder_instance": "BUILDER",
        "read_only_instance": "REFERENCE",
        "admin_instance": "OPS",
    }.get(key, key.replace("_", " ").strip().upper() or "WORKSPACE")


_PRIMARY_TRAY_TOOLS: list[tuple[str, str, str]] = [
    ("read_file", "READ", "Read files in the active workspace"),
    ("screenshot", "SHOT", "Inspect a screenshot or visual surface"),
    ("query_instance", "ASK", "Ask another workspace a bounded question"),
    ("debug_console", "DEBUG", "Inspect safe runtime details"),
]

_SECONDARY_TRAY_TOOLS: list[tuple[str, str, str]] = [
    ("run_python", "PY", "Run a bounded Python snippet"),
    ("write_file", "WF", "Prepare a write-file task"),
    ("execute_command", "CMD", "Prepare a workspace command"),
]

_TRAY_SPACES: list[tuple[str, str, str]] = [
    ("outlook_slot", "OUTLOOK", "Reserve this tray space for mail and follow-up workflows"),
    ("calendar_slot", "CAL", "Reserve this tray space for calendar and schedule workflows"),
    ("rss_slot", "RSS", "Reserve this tray space for feeds, headlines, or watchlists"),
    ("add_slot", "+ ADD", "Create another tray slot for a user app, API, or module"),
]


class StatusPanel(QFrame):
    agent_init_requested = Signal(str)
    tool_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tool_buttons: dict[str, QPushButton] = {}
        self._secondary_tool_keys: set[str] = set()
        self._space_buttons: dict[str, QPushButton] = {}
        self._last_activity = "Workspace ready"
        self._extras_visible = False
        self.setFixedWidth(T.STATUS_W)
        self.setObjectName("status_panel")
        self.setStyleSheet(
            "QFrame#status_panel {"
            f" background-color: {T.SURFACE_ELEVATED_88};"
            f" border-left: 1px solid {T.BORDER_SOFT_68};"
            "}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 14, 10, 10)
        outer.setSpacing(10)

        title_row = QHBoxLayout()
        title = QLabel("WORKSPACE")
        title.setStyleSheet(
            f"color: {T.ACCENT_TEAL}; font-family: '{T.FF_HEAD}';"
            f"font-size: {T.FS_TITLE}pt; font-weight: bold;"
        )
        title_row.addWidget(title)
        title_row.addStretch()
        self._extras_btn = QPushButton("MORE OPTIONS")
        self._extras_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._extras_btn.setToolTip("Show additional workspace actions and optional spaces")
        self._extras_btn.setAccessibleName("More workspace options")
        self._extras_btn.setAccessibleDescription("Shows additional actions and optional spaces")
        self._extras_btn.setStyleSheet(
            f"QPushButton {{ background: {T.SURFACE_ELEVATED_92}; color: {T.DIM}; border: 1px solid {T.BORDER_SOFT_60};"
            f" border-radius: 14px; padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: {T.ACCENT_TEAL}; color: {T.ACCENT_TEAL}; background: {T.WHITE}; }}"
        )
        self._extras_btn.clicked.connect(self._toggle_extras)
        title_row.addWidget(self._extras_btn)
        outer.addLayout(title_row)

        self._workspace_lbl = _mono("GUPPY-PRIMARY / DAILY", T.TEXT, T.FS_TINY, True)
        self._tray_status_lbl = _mono("READY", T.STATUS_SUCCESS, T.FS_TINY, True)
        self._activity_lbl = _mono("Latest: Workspace ready", T.DIM, T.FS_TINY)
        self._activity_lbl.setWordWrap(True)
        self._activity_lbl.setStyleSheet(
            f"color: {T.TEXT_DIM_72}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        outer.addWidget(self._workspace_lbl)
        outer.addWidget(self._tray_status_lbl)
        outer.addWidget(self._activity_lbl)

        tools_frame = QFrame()
        tools_frame.setObjectName("drawer_actions")
        tools_frame.setStyleSheet(
            "QFrame#drawer_actions {"
            f" background-color: {T.SURFACE_ELEVATED_88};"
            f" border: 1px solid {T.BORDER_SOFT_60};"
            " border-radius: 24px;"
            "}"
        )
        tools_layout = QVBoxLayout(tools_frame)
        tools_layout.setContentsMargins(10, 10, 10, 8)
        tools_layout.setSpacing(6)
        tools_layout.addWidget(_mono("UTILITIES", T.ACCENT_TEAL, T.FS_TINY, True))

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        for index, (tool_key, short_label, tooltip) in enumerate(_PRIMARY_TRAY_TOOLS):
            btn = QPushButton(short_label)
            btn.setFixedSize(72, 36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(tooltip)
            btn.setStyleSheet(self._tool_button_style(True))
            btn.clicked.connect(lambda _=False, key=tool_key: self.tool_requested.emit(key))
            self._tool_buttons[tool_key] = btn
            grid.addWidget(btn, index // 2, index % 2)
        tools_layout.addLayout(grid)

        self._tool_hint_lbl = _mono(
            "Files, screenshots, quick questions, and debug stay here.",
            T.DIM,
            T.FS_TINY,
        )
        self._tool_hint_lbl.setWordWrap(True)
        tools_layout.addWidget(self._tool_hint_lbl)
        outer.addWidget(tools_frame)

        self._extras_host = QWidget()
        extras_layout = QVBoxLayout(self._extras_host)
        extras_layout.setContentsMargins(0, 0, 0, 0)
        extras_layout.setSpacing(10)

        spaces_frame = QFrame()
        spaces_frame.setObjectName("drawer_secondary_actions")
        spaces_frame.setStyleSheet(
            "QFrame#drawer_secondary_actions {"
            f" background-color: {T.SURFACE_ELEVATED_88};"
            f" border: 1px solid {T.BORDER_SOFT_60};"
            " border-radius: 24px;"
            "}"
        )
        spaces_layout = QVBoxLayout(spaces_frame)
        spaces_layout.setContentsMargins(10, 10, 10, 8)
        spaces_layout.setSpacing(6)

        spaces_head = QHBoxLayout()
        spaces_head.addWidget(_mono("MORE ACTIONS", T.ACCENT_TEAL, T.FS_TINY, True))
        spaces_head.addStretch()
        spaces_head.addWidget(_mono("WRITE / CODE / SHELL", T.DIM, T.FS_TINY))
        spaces_layout.addLayout(spaces_head)

        self._spaces_summary_lbl = _mono(
            "Open these only when you need to write or run code.",
            T.DIM,
            T.FS_TINY,
        )
        self._spaces_summary_lbl.setWordWrap(True)
        spaces_layout.addWidget(self._spaces_summary_lbl)

        slots_grid = QGridLayout()
        slots_grid.setContentsMargins(0, 0, 0, 0)
        slots_grid.setHorizontalSpacing(8)
        slots_grid.setVerticalSpacing(8)
        for index, (tool_key, label, tooltip) in enumerate(_SECONDARY_TRAY_TOOLS):
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(tooltip)
            btn.setFixedHeight(34)
            btn.setStyleSheet(self._space_button_style())
            btn.clicked.connect(lambda _=False, key=tool_key: self.tool_requested.emit(key))
            self._tool_buttons[tool_key] = btn
            self._secondary_tool_keys.add(tool_key)
            slots_grid.addWidget(btn, 0, index)
        for index, (slot_key, label, tooltip) in enumerate(_TRAY_SPACES):
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(tooltip)
            btn.setFixedHeight(32)
            btn.setStyleSheet(self._space_button_style())
            btn.clicked.connect(lambda _=False, key=slot_key: self.tool_requested.emit(key))
            self._space_buttons[slot_key] = btn
            slots_grid.addWidget(btn, 1 + (index // 2), index % 2)
        spaces_layout.addLayout(slots_grid)
        extras_layout.addWidget(spaces_frame)

        media_frame = QFrame()
        media_frame.setObjectName("media_dock")
        media_frame.setStyleSheet(
            "QFrame#media_dock {"
            f" background-color: {T.SURFACE_ELEVATED_88};"
            f" border: 1px solid {T.BORDER_SOFT_60};"
            " border-radius: 24px;"
            "}"
        )
        media_layout = QVBoxLayout(media_frame)
        media_layout.setContentsMargins(12, 12, 12, 12)
        media_layout.setSpacing(8)

        media_top = QHBoxLayout()
        media_top.addWidget(_mono("OPTIONAL SPACES", T.ACCENT_TEAL, T.FS_TINY, True))
        media_top.addStretch()
        media_top.addWidget(_mono("MEDIA / FOLLOW-UP", T.DIM, T.FS_TINY))
        media_layout.addLayout(media_top)

        artwork = QFrame()
        artwork.setFixedHeight(118)
        artwork.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {T.ART_RED}, stop:0.35 {T.ART_GOLD}, stop:0.7 {T.ART_PINK}, stop:1 {T.ART_BLUE});"
            "border: none; border-radius: 20px;"
        )
        art_layout = QVBoxLayout(artwork)
        art_layout.setContentsMargins(14, 10, 14, 10)
        art_layout.setSpacing(5)
        optional_lbl = _mono("OPTIONAL", T.INK, T.FS_TINY, True)
        optional_lbl.setStyleSheet(
            f"color: {T.INK}; background-color: {T.SURFACE_ELEVATED_92};"
            f" border-radius: 9px; padding: 2px 8px; font-family: '{T.FF_MONO}';"
            f" font-size: {T.FS_TINY}pt; letter-spacing: 1px; font-weight: bold;"
        )
        art_layout.addWidget(optional_lbl)
        self._media_title_lbl = QLabel("Keep the daily path light")
        self._media_title_lbl.setStyleSheet(
            f"color: {T.INK}; background-color: {T.SURFACE_ELEVATED_92};"
            f" border-radius: 12px; padding: 3px 8px; font-family: '{T.FF_HEAD}';"
            " font-size: 15pt; font-weight: bold;"
        )
        art_layout.addWidget(self._media_title_lbl)
        self._media_subtitle_lbl = _mono(
            "Use this drawer for media, calendar, mail, or extra workflow spaces only when they help.",
            T.TEXT,
            T.FS_SMALL,
        )
        self._media_subtitle_lbl.setWordWrap(True)
        self._media_subtitle_lbl.setStyleSheet(
            f"color: {T.TEXT}; background-color: {T.SURFACE_ELEVATED_88};"
            f" border-radius: 12px; padding: 4px 8px; font-family: '{T.FF_MONO}';"
            f" font-size: {T.FS_SMALL}pt; letter-spacing: 1px;"
        )
        art_layout.addWidget(self._media_subtitle_lbl)
        art_gesture = QLabel("// calm / focus / context")
        art_gesture.setStyleSheet(
            f"color: {T.INK}; background-color: {T.SURFACE_ELEVATED_88};"
            f" border-radius: 9px; padding: 2px 8px; font-family: '{T.FF_MONO}'; font-size: 9pt; letter-spacing: 2px;"
        )
        art_layout.addWidget(art_gesture)
        media_layout.addWidget(artwork)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        for label in ("PREV", "PLAY", "NEXT"):
            btn = QPushButton(label)
            btn.setEnabled(False)
            btn.setStyleSheet(
                "QPushButton {"
                f" background: {T.SURFACE_ELEVATED_92};"
                f" color: {T.TEXT_DIM_78};"
                f" border: 1px solid {T.BORDER_MID_30};"
                " border-radius: 14px;"
                f" padding: 7px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
                "}"
            )
            controls.addWidget(btn)
        media_layout.addLayout(controls)
        extras_layout.addWidget(media_frame)
        self._extras_host.setVisible(False)
        outer.addWidget(self._extras_host)
        outer.addStretch()

    @staticmethod
    def _tool_button_style(enabled: bool) -> str:
        if enabled:
            return (
                f"QPushButton {{ background: {T.SURFACE_ELEVATED_92}; color: {T.TEXT}; border: 1px solid {T.BORDER_MID_30};"
                f" border-radius: 15px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; font-weight: bold; }}"
                f"QPushButton:hover {{ border-color: {T.ACCENT_TEAL}; color: {T.ACCENT_TEAL}; background: {T.WHITE}; }}"
            )
        return (
            "QPushButton {"
            f" background: {T.SURFACE_ELEVATED_78};"
            f" color: {T.BORDER_STRONG};"
            f" border: 1px solid {T.BORDER_MID_22};"
            f" border-radius: 15px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; font-weight: bold;"
            "}"
        )

    @staticmethod
    def _space_button_style() -> str:
        return (
            f"QPushButton {{ background: {T.SURFACE_ELEVATED_92}; color: {T.TEXT}; border: 1px solid {T.BORDER_MID_30};"
            f" border-radius: 14px; padding: 0 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: {T.ACCENT_TEAL}; color: {T.ACCENT_TEAL}; background: {T.WHITE}; }}"
        )

    def set_workspace(self, name: str, workspace_type: str = "") -> None:
        workspace_name = (name or "guppy-primary").strip().upper()
        label = _workspace_kind_label(workspace_type)
        self._workspace_lbl.setText(f"WORKSPACE / {workspace_name} / {label}")

    def _toggle_extras(self) -> None:
        self._extras_visible = not self._extras_visible
        self._extras_host.setVisible(self._extras_visible)
        self._extras_btn.setText("LESS OPTIONS" if self._extras_visible else "MORE OPTIONS")
        self._extras_btn.setToolTip(
            "Hide additional workspace actions and optional spaces"
            if self._extras_visible
            else "Show additional workspace actions and optional spaces"
        )

    def set_tool_states(self, states: dict[str, str]) -> None:
        for tool_key, button in self._tool_buttons.items():
            ready = str(states.get(tool_key, "ready")).strip().lower() == "ready"
            button.setEnabled(ready)
            if tool_key in self._secondary_tool_keys:
                button.setStyleSheet(self._space_button_style() if ready else self._tool_button_style(False))
            else:
                button.setStyleSheet(self._tool_button_style(ready))

    def update_status(self, data: dict) -> None:
        model = str(data.get("model", "guppy") or "guppy").strip().upper()
        query = str(data.get("last_query", "") or "").strip()
        if query in {"-", "—"}:
            query = ""
        self._tray_status_lbl.setText(f"READY / {model}")
        if query:
            self._activity_lbl.setText(f"Latest: {query[:88]}")

    def append_syslog(self, line: str) -> None:
        self._last_activity = (line or "Workspace ready").strip() or "Workspace ready"
        self._activity_lbl.setText(f"Latest: {self._last_activity}")

    def update_agent_status(self, agent: str, online: bool, last_seen: str = "-", load_pct: float | None = None) -> None:
        del agent, last_seen, load_pct
        if online:
            self._tray_status_lbl.setText("LOCAL READY")
            self._tray_status_lbl.setStyleSheet(
                f"color: {T.GREEN}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px; font-weight: bold;"
            )
            return
        self._tray_status_lbl.setText("LOCAL OFFLINE")
        self._tray_status_lbl.setStyleSheet(
            f"color: {T.ERROR}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px; font-weight: bold;"
        )

    def set_recovery_outcome(self, action: str, ok: bool, summary: str) -> None:
        state = "OK" if ok else "ERROR"
        color = T.GREEN if ok else T.ERROR
        message = f"Latest: {action.upper()} {state}"
        if summary:
            message = f"{message} / {summary}"
        self._activity_lbl.setText(message)
        self._tray_status_lbl.setStyleSheet(
            f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px; font-weight: bold;"
        )
