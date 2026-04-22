"""
ui/launcher/components/topbar.py
Premium top navigation / header bar.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QResizeEvent, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .. import tokens as T


class _ElidedLabel(QLabel):
    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = ""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setText(text)

    def setText(self, text: str) -> None:  # type: ignore[override]
        self._full_text = str(text or "")
        self._apply_text()

    def resizeEvent(self, event: QResizeEvent) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._apply_text()

    def full_text(self) -> str:
        return self._full_text

    def _apply_text(self) -> None:
        width = max(self.width() - 4, 72)
        rendered = self.fontMetrics().elidedText(
            self._full_text,
            Qt.TextElideMode.ElideRight,
            width,
        )
        super().setText(rendered)
        self.setToolTip(self._full_text)


class TopBar(QFrame):
    search_submitted = Signal(str)
    quick_action = Signal(str)
    instance_selected = Signal(str)
    nav_requested = Signal(int)
    launcher_context_requested = Signal()

    _NAV_TABS = [
        ("HOME", 0, frozenset({0}), True),
        ("MODELS", 5, frozenset({5, 6, 7, 8, 9}), True),
        ("TOOLS", 3, frozenset({3}), True),
        ("LIBRARY", 2, frozenset({2}), True),
        ("SETTINGS", 4, frozenset({4}), True),
        ("WORKSPACES", 1, frozenset({1}), False),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._active_tab_index = 0
        self._notif_count = 0
        self._notif_severity = "info"
        self._drawer_open = False
        self._sidebar_collapsed = False
        self.setFixedHeight(T.TOPBAR_H)
        self.setObjectName("topbar")
        self.setStyleSheet(
            f"QFrame#topbar {{ background: {T.GRADIENT_SAND};"
            f" border-bottom: 1px solid {T.BORDER_SOFT_60}; }}"
        )

        row = QHBoxLayout(self)
        self._row = row
        row.setContentsMargins(16, 8, 16, 8)
        row.setSpacing(8)

        brand_col = QVBoxLayout()
        brand_col.setSpacing(1)
        title = QLabel("Editorial\nIntelligence")
        title.setStyleSheet(
            f"color: {T.ACCENT_TEAL}; font-family: '{T.FONT_SERIF}'; font-size: {T.FS_TITLE + 2}pt;"
            " font-style: italic; font-weight: 600; letter-spacing: 0px;"
        )
        self._brand_title = title
        self._session_lbl = _ElidedLabel("daily path for chat, files, and workspace context")
        self._session_lbl.setStyleSheet(
            f"color: {T.TEXT_DIM_72}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;"
        )
        brand_col.addWidget(title)
        brand_col.addWidget(self._session_lbl)
        brand_col.setContentsMargins(0, 0, 0, 0)
        self._brand_col = brand_col
        row.addLayout(brand_col)

        self._sidebar_btn = QPushButton("=")
        self._sidebar_btn.setFixedSize(32, 32)
        self._sidebar_btn.setToolTip("Toggle navigation")
        self._sidebar_btn.setAccessibleName("Toggle navigation")
        self._sidebar_btn.setAccessibleDescription("Shows or hides the left navigation rail")
        self._sidebar_btn.setStyleSheet(self._icon_button_style(T.BG0, T.TEXT))
        self._sidebar_btn.clicked.connect(lambda: self.quick_action.emit("toggle_sidebar"))
        row.addWidget(self._sidebar_btn)

        self._nav_btns: list[QPushButton] = []
        self._nav_specs = list(self._NAV_TABS)
        for label, idx, _active_tabs, visible in self._nav_specs:
            btn = QPushButton(label, self)
            btn.setFixedHeight(28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, i=idx: self._on_nav(i))
            btn.setStyleSheet(self._nav_style(False))
            self._nav_btns.append(btn)
            if visible:
                row.addWidget(btn)
            else:
                btn.hide()

        row.addStretch()

        workspace_shell = QFrame()
        self._workspace_shell = workspace_shell
        workspace_shell.setStyleSheet(
            f"background-color: {T.SURFACE_BASE_88};"
            f" border: 1px solid {T.BORDER_SOFT_58};"
            " border-radius: 18px;"
        )
        workspace_row = QHBoxLayout(workspace_shell)
        workspace_row.setContentsMargins(8, 4, 8, 4)
        workspace_row.setSpacing(4)
        inst_lbl = QLabel("SESSION")
        inst_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        self._instance_lbl = inst_lbl
        self._instance_cb = QComboBox()
        self._instance_cb.setMinimumWidth(128)
        self._instance_cb.setMaximumWidth(150)
        self._instance_cb.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
        self._instance_cb.currentTextChanged.connect(self._on_instance_selected)
        self._workspace_nav_btn = QPushButton("WORKSPACES")
        self._workspace_nav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._workspace_nav_btn.setFixedHeight(28)
        self._workspace_nav_btn.setToolTip("Open workspace setup, governance, and saved workspace management.")
        self._workspace_nav_btn.setAccessibleName("Open workspaces")
        self._workspace_nav_btn.setAccessibleDescription("Opens the Workspaces hub from the workspace controls area")
        self._workspace_nav_btn.clicked.connect(lambda: self._on_nav(1))
        self._workspace_nav_btn.setStyleSheet(self._nav_style(False))
        workspace_row.addWidget(inst_lbl)
        workspace_row.addWidget(self._instance_cb)
        workspace_row.addWidget(self._workspace_nav_btn)
        self._workspace_shell.setToolTip("Current session and workspace controls.")
        row.addWidget(workspace_shell)

        summary_shell = QFrame()
        self._summary_shell = summary_shell
        summary_shell.setStyleSheet(
            f"background-color: {T.SURFACE_BASE_88};"
            f" border: 1px solid {T.BORDER_SOFT_58};"
            " border-radius: 18px;"
        )
        summary_row = QHBoxLayout(summary_shell)
        summary_row.setContentsMargins(8, 4, 8, 4)
        summary_row.setSpacing(6)
        summary_copy = QVBoxLayout()
        summary_copy.setContentsMargins(0, 0, 0, 0)
        summary_copy.setSpacing(0)
        self._summary_primary_lbl = _ElidedLabel("ACTIVE MODEL: GUPPY")
        self._summary_primary_lbl.setStyleSheet(
            f"color: {T.INK}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px; font-weight: bold;"
        )
        self._summary_secondary_lbl = _ElidedLabel("CHAT LANE: AUTO / LIGHT")
        self._summary_secondary_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;"
        )
        summary_copy.addWidget(self._summary_primary_lbl)
        summary_copy.addWidget(self._summary_secondary_lbl)
        summary_row.addLayout(summary_copy, 1)
        self._launcher_summary_btn = QPushButton("CONTEXT")
        self._launcher_summary_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._launcher_summary_btn.setToolTip("Open Home context and chat controls for this workspace.")
        self._launcher_summary_btn.setAccessibleName("Open chat context controls")
        self._launcher_summary_btn.setAccessibleDescription("Opens Home context and chat controls for the active workspace")
        self._launcher_summary_btn.setMinimumWidth(56)
        self._launcher_summary_btn.setFixedHeight(28)
        self._launcher_summary_btn.setStyleSheet(
            f"QPushButton {{ background-color: {T.SURFACE_BASE_90}; color: {T.TEXT};"
            f" border: 1px solid {T.BORDER_SOFT_72}; border-radius: 14px; padding: 5px 10px;"
            f" font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px; text-align: center; }}"
            f"QPushButton:hover {{ border-color: {T.TERTIARY}; color: {T.INK}; background-color: {T.WHITE}; }}"
        )
        self._launcher_summary_btn.clicked.connect(self.launcher_context_requested.emit)
        summary_row.addWidget(self._launcher_summary_btn)
        self._summary_shell.setToolTip("Active model and chat lane summary for this session.")
        row.addWidget(summary_shell)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search knowledge library...")
        self._search.setToolTip("Search home context, files, and library items")
        self._search.setAccessibleName("Search launcher content")
        self._search.setAccessibleDescription("Searches home context, files, and library")
        self._search.setMinimumWidth(146)
        self._search.setMaximumWidth(210)
        self._search.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._search.setFixedHeight(34)
        self._search.returnPressed.connect(lambda: self.search_submitted.emit(self._search.text()))
        row.addWidget(self._search)

        system_shell = QFrame()
        system_shell.setObjectName("topbar_system_shell")
        system_shell.setStyleSheet(
            f"QFrame#topbar_system_shell {{ background-color: {T.SURFACE_BASE_88};"
            f" border: 1px solid {T.BORDER_SOFT_58}; border-radius: 18px; }}"
        )
        system_row = QHBoxLayout(system_shell)
        system_row.setContentsMargins(4, 3, 4, 3)
        system_row.setSpacing(3)

        self._runtime_chip = QLabel("STARTING")
        self._runtime_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._runtime_chip.setMinimumWidth(72)
        self._runtime_chip.setFixedHeight(26)
        self._runtime_chip.setToolTip("Launcher is still collecting startup readiness and runtime health.")
        self._runtime_chip.setAccessibleName("Launcher runtime status")
        self._runtime_chip.setAccessibleDescription("Shows current launcher startup and runtime readiness")
        self._apply_runtime_chip_style("info")
        system_row.addWidget(self._runtime_chip)

        notif_wrap = QWidget()
        notif_wrap.setFixedSize(40, 32)
        notif_layout = QVBoxLayout(notif_wrap)
        notif_layout.setContentsMargins(0, 0, 0, 0)
        notif_layout.setSpacing(0)
        self._notif_btn = QPushButton("NOTIF")
        self._notif_btn.setFixedSize(40, 32)
        self._notif_btn.setToolTip("Open launcher warnings and recovery events in Settings.")
        self._notif_btn.setAccessibleName("Notifications")
        self._notif_btn.setAccessibleDescription("Opens warnings and recovery events")
        self._notif_btn.clicked.connect(lambda: self.quick_action.emit("notifications"))
        self._notif_btn.setStyleSheet(self._icon_button_style(T.BG0, T.TEXT))
        notif_layout.addWidget(self._notif_btn)
        self._notif_badge = QLabel("")
        self._notif_badge.setParent(notif_wrap)
        self._notif_badge.setFixedHeight(16)
        self._notif_badge.setMinimumWidth(16)
        self._notif_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._notif_badge.move(18, 0)
        self._notif_badge.hide()
        self._apply_notif_style()

        self._term_btn = QPushButton("SET")
        self._term_btn.setFixedSize(40, 32)
        self._term_btn.setToolTip("Open logs and recent command activity in Settings.")
        self._term_btn.setAccessibleName("Open logs")
        self._term_btn.setAccessibleDescription("Opens logs and recent command activity")
        self._term_btn.setStyleSheet(self._icon_button_style(T.BG0, T.TEXT))
        self._term_btn.clicked.connect(lambda: self.quick_action.emit("terminal"))

        self._drawer_btn = QPushButton(">")
        self._drawer_btn.setFixedSize(32, 32)
        self._drawer_btn.setToolTip("Toggle workspace drawer")
        self._drawer_btn.setAccessibleName("Toggle workspace drawer")
        self._drawer_btn.setAccessibleDescription("Shows or hides the workspace drawer")
        self._drawer_btn.setStyleSheet(self._icon_button_style(T.BG0, T.TEXT))
        self._drawer_btn.clicked.connect(lambda: self.quick_action.emit("toggle_drawer"))

        system_row.addWidget(notif_wrap)
        system_row.addWidget(self._term_btn)
        system_row.addWidget(self._drawer_btn)
        self._drawer_btn.hide()
        row.addWidget(system_shell)

        self.set_active_tab(0)
        self.set_instances(["guppy-primary"], active_instance="guppy-primary")
        self.set_launcher_summary("AUTO / GUPPY / LIGHT")

    def _apply_runtime_chip_style(self, severity: str) -> None:
        palette = {
            "ok": (T.STATUS_SUCCESS, "rgba(0,200,83,0.12)"),
            "warn": (T.STATUS_WARNING, "rgba(255,214,0,0.12)"),
            "error": (T.STATUS_ERROR, "rgba(255,61,0,0.12)"),
            "info": (T.ACCENT_TEAL, "rgba(0,106,106,0.10)"),
        }
        text_color, bg_color = palette.get((severity or "info").strip().lower(), palette["info"])
        self._runtime_chip.setStyleSheet(
            f"color: {text_color}; background-color: {bg_color};"
            f" border: 1px solid {T.BORDER_SOFT_68}; border-radius: 8px;"
            f" padding: 0 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px; font-weight: 700;"
        )

    @staticmethod
    def _nav_style(active: bool) -> str:
        if active:
            return (
                f"QPushButton {{ background-color: transparent; color: {T.ACCENT_TEAL}; border: none;"
                f" border-bottom: 3px solid {T.ACCENT_TEAL}; border-radius: 0px;"
                f" padding: 0 8px; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt; font-weight: 600; }}"
            )
        return (
            f"QPushButton {{ background-color: transparent; color: {T.DIM}; border: none;"
            f" border-bottom: 2px solid transparent; border-radius: 0px;"
            f" padding: 0 8px; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt; font-weight: 500; }}"
            f"QPushButton:hover {{ color: {T.TEXT}; border-bottom-color: {T.ACCENT_TEAL}; }}"
        )

    @staticmethod
    def _icon_button_style(bg: str, color: str) -> str:
        return (
            f"QPushButton {{ background-color: {bg}; color: {color}; border: 2px solid {T.BORDER_SOFT};"
            f" border-radius: 4px; font-family: '{T.FF_BODY}'; font-size: {T.FS_TINY}pt; font-weight: 600; }}"
            f"QPushButton:hover {{ border-color: {T.ACCENT_TEAL}; color: {T.ACCENT_TEAL}; background-color: rgba(0,0,0,0.03); }}"
        )

    def _on_nav(self, tab_index: int) -> None:
        self.set_active_tab(tab_index)
        self.nav_requested.emit(tab_index)

    def set_active_tab(self, tab_index: int) -> None:
        self._active_tab_index = int(tab_index)
        for btn, (_, _idx, active_tabs, _visible) in zip(self._nav_btns, self._nav_specs):
            btn.setStyleSheet(self._nav_style(tab_index in active_tabs))
        self._workspace_nav_btn.setStyleSheet(self._nav_style(tab_index == 1))
        if self.isVisible():
            self._apply_density_mode(self.width())

    def set_session(self, text: str) -> None:
        clean = (text or "daily workspace assistant").strip() or "daily workspace assistant"
        self._session_lbl.setText(clean.lower())

    def set_launcher_summary(self, text: str) -> None:
        summary = (text or "AUTO / GUPPY / LIGHT").strip() or "AUTO / GUPPY / LIGHT"
        summary = summary.replace("[EDIT]", "").replace("[OPEN]", "OPEN").strip()
        summary = summary.replace("HOME /", "").strip(" /")
        parts = [part.strip() for part in summary.split("/") if part.strip()]
        if len(parts) >= 3:
            primary = f"ACTIVE MODEL: {parts[1]}"
            secondary = f"CHAT LANE: {parts[0]} / {' / '.join(parts[2:])}"
        elif len(parts) == 2:
            primary = f"ACTIVE MODEL: {parts[0]}"
            secondary = f"SECONDARY: {parts[1]}"
        else:
            primary = f"ACTIVE MODEL: {summary or 'GUPPY'}"
            secondary = "SECONDARY: READY"
        self._summary_primary_lbl.setText(primary.upper())
        self._summary_secondary_lbl.setText(secondary.upper())
        self._launcher_summary_btn.setToolTip(f"Home context: {summary}" if summary else "Home context")

    def set_model_context(
        self,
        *,
        main_model: str = "",
        support_model: str = "",
        backend: str = "",
        route: str = "",
    ) -> None:
        primary = f"ACTIVE MODEL: {(main_model or 'guppy').strip() or 'guppy'}".upper()
        secondary_parts: list[str] = []
        if support_model:
            secondary_parts.append(f"SUB: {str(support_model).strip().upper()}")
        if route:
            secondary_parts.append(f"ROUTE: {str(route).strip().upper()}")
        if backend:
            secondary_parts.append(f"ENGINE: {str(backend).strip().upper()}")
        secondary = " | ".join(secondary_parts) if secondary_parts else self._summary_secondary_lbl.full_text()
        self._summary_primary_lbl.setText(primary)
        self._summary_secondary_lbl.setText(secondary or "SECONDARY: READY")

    def set_notification_badge(self, count: int, severity: str = "info") -> None:
        self._notif_count = max(0, int(count or 0))
        self._notif_severity = (severity or "info").strip().lower() or "info"
        self._apply_notif_style()

    def set_runtime_status(self, label: str, *, detail: str = "", severity: str = "info") -> None:
        text = (label or "STATUS").strip().upper() or "STATUS"
        tooltip = (detail or text).strip() or text
        self._runtime_chip.setText(text)
        self._runtime_chip.setToolTip(tooltip)
        self._runtime_chip.setAccessibleDescription(tooltip)
        self._apply_runtime_chip_style(severity)

    def _apply_notif_style(self) -> None:
        btn_color = T.TEXT
        badge_color = T.TERTIARY
        if self._notif_severity == "error":
            btn_color = T.ERROR
            badge_color = T.ERROR
        elif self._notif_severity == "warn":
            btn_color = T.PRIMARY
            badge_color = T.PRIMARY

        self._notif_btn.setStyleSheet(self._icon_button_style(T.BG0, btn_color))
        if self._notif_count <= 0:
            self._notif_badge.hide()
            return

        text = "99+" if self._notif_count > 99 else str(self._notif_count)
        width = 24 if len(text) > 2 else 16
        self._notif_badge.setFixedWidth(width)
        self._notif_badge.move(max(10, 32 - width), 0)
        self._notif_badge.setText(text)
        self._notif_badge.setStyleSheet(
            f"background-color: {badge_color}; color: white; border-radius: 8px;"
            f"font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; padding: 0 2px;"
        )
        self._notif_badge.show()

    def set_instances(self, instances: list[str], active_instance: str = "") -> None:
        names = [str(item).strip() for item in instances if str(item).strip()]
        if not names:
            names = ["guppy-primary"]
        target = (active_instance or "").strip() or names[0]

        self._instance_cb.blockSignals(True)
        self._instance_cb.clear()
        self._instance_cb.addItems(names)
        if target in names:
            self._instance_cb.setCurrentText(target)
        else:
            self._instance_cb.setCurrentIndex(0)
        self._instance_cb.blockSignals(False)

    def set_active_instance(self, name: str) -> None:
        target = (name or "").strip()
        if not target:
            return
        idx = self._instance_cb.findText(target)
        if idx >= 0 and idx != self._instance_cb.currentIndex():
            self._instance_cb.blockSignals(True)
            self._instance_cb.setCurrentIndex(idx)
            self._instance_cb.blockSignals(False)

    def _on_instance_selected(self, name: str) -> None:
        target = (name or "").strip()
        if target:
            self.instance_selected.emit(target)

    def set_drawer_open(self, open_state: bool) -> None:
        self._drawer_open = bool(open_state)
        self._drawer_btn.setText("<" if self._drawer_open else ">")

    def set_sidebar_collapsed(self, collapsed: bool) -> None:
        self._sidebar_collapsed = bool(collapsed)
        self._sidebar_btn.setText(">" if self._sidebar_collapsed else "=")

    def showEvent(self, event: QShowEvent) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._apply_density_mode(self.width())

    def resizeEvent(self, event: QResizeEvent) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self.isVisible():
            self._apply_density_mode(event.size().width())

    def _apply_density_mode(self, width: int) -> None:
        width = max(int(width or 0), 0)
        compact = width < 1360
        tight = width < 1140
        ultra = width < 860
        allow_search = self._active_tab_index in {0, 2}
        show_brand = width >= 1520 and not self._sidebar_collapsed

        for btn, (_label, idx, _active_tabs, visible) in zip(self._nav_btns, self._nav_specs):
            if not visible:
                btn.hide()
                continue
            if not compact:
                btn.show()
                continue
            btn.setVisible(not tight and idx == self._active_tab_index)

        self._brand_title.setVisible(show_brand)
        self._session_lbl.setVisible(show_brand and not compact)
        self._instance_lbl.setVisible(not tight)
        self._instance_cb.setMaximumWidth(150 if not compact else 122)
        self._workspace_shell.setVisible(not tight)
        self._workspace_nav_btn.setVisible(not ultra)
        self._workspace_nav_btn.setText("WORKSPACES" if not tight else "OPEN")
        self._summary_secondary_lbl.setVisible(not ultra)
        self._launcher_summary_btn.setVisible(not tight)
        self._launcher_summary_btn.setText("CONTEXT" if not compact else "CTX")
        self._search.setVisible(not tight and allow_search)
        self._search.setMaximumWidth(260 if not compact else 170)
        self._search.setPlaceholderText("Search knowledge library..." if not compact else "Search")
        self._runtime_chip.setMinimumWidth(72 if not tight else 58)
        self._runtime_chip.setVisible(not ultra)
        self._drawer_btn.setVisible(False)
