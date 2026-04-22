"""
ui/launcher/views/tools_view.py
TOOLS tab - workspace-scoped actions, file helpers, and capability notes.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import tokens as T
from ..components import BuilderTaskPanel
from src.guppy.launcher_application.tools_presenter import build_tools_surface_state
from .tools_trace_panel import ToolsTracePanel
from .tools_view_cards import (
    INSTANCE_TOOL_CATALOG,
    ToolCard,
    mono_label,
    workspace_type_label,
)


class ToolsView(QWidget):
    tool_state_changed = Signal(str, bool)
    tool_hint_requested = Signal(str)
    tool_management_requested = Signal(dict)
    builder_task_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tool_cards: dict[str, ToolCard] = {}
        self._tool_states: dict[str, bool] = {}
        self._tool_card_order: list[str] = []
        self._instance_name = "guppy-primary"
        self._instance_type = "user_instance"
        self._details_visible = False
        self.trace_adapter = None
        self.debug_backend = None
        self.read_debug_snapshot = None
        self.read_recent_tool_events = None
        self.read_recent_launcher_events = None
        self._scroll: QScrollArea | None = None
        self._limits: dict[str, int] = {
            "configured": 1,
            "max_configured": 5,
            "active_runtime": 1,
            "max_active_runtime": 2,
        }

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        self._scroll = scroll
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        scroll.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(20)

        self._build_header(layout)
        self._build_section_tabs(layout)
        filters = self._build_filters()
        self._banner = self._build_boundary_banner()

        self._builder_panel = BuilderTaskPanel()
        self._builder_panel.queue_requested.connect(self.builder_task_requested.emit)
        self._register_scroll_proxy(self._builder_panel)

        self._cards_host = QWidget()
        self._cards_layout = QGridLayout(self._cards_host)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setHorizontalSpacing(12)
        self._cards_layout.setVerticalSpacing(12)
        self._populate_cards()
        self._cards_host.setVisible(True)
        self._register_scroll_proxy(self._cards_host)
        self._trace_panel = ToolsTracePanel()
        self._trace_panel.set_tool_options(self._tool_card_order)
        self._trace_panel.tool_selected.connect(self._on_trace_tool_selected)
        self._register_scroll_proxy(self._trace_panel)

        self._empty_state_lbl = mono_label(
            "No tools match this filter yet. Clear the search or choose another category to keep working.",
            T.DIM,
            T.FS_SMALL,
        )
        self._empty_state_lbl.setWordWrap(True)
        self._empty_state_lbl.setVisible(False)

        self._quick_layout.addWidget(self._builder_panel)
        self._quick_layout.addWidget(self._boundary_lbl)
        self._quick_layout.addWidget(self._execution_lbl)
        self._quick_layout.addWidget(self._trace_panel)
        self._quick_layout.addWidget(self._banner)
        self._quick_layout.addStretch()

        self._catalog_layout.addLayout(filters)
        self._catalog_layout.addWidget(self._cards_host)
        self._catalog_layout.addWidget(self._empty_state_lbl)
        self._catalog_layout.addStretch()

        layout.addStretch()
        self._register_scroll_proxy(content)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self.set_instance_context({}, {})
        self._sync_detail_visibility()

    def _build_header(self, layout: QVBoxLayout) -> None:
        title = QLabel("Tools")
        title.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_HEAD}'; font-size: 26pt; font-weight: 900;"
        )
        title_row = QHBoxLayout()
        title_row.addWidget(title)
        title_row.addStretch()
        self._details_btn = QPushButton("SHOW DETAILS")
        self._details_btn.setToolTip("Show or hide governance details and permission explanations for each tool")
        self._details_btn.setMinimumHeight(36)
        self._details_btn.setStyleSheet(
            f"QPushButton {{ background: {T.BG0}; color: {T.DIM}; border: 1px solid {T.BORDER};"
            f" padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: {T.ACCENT_TEAL}; color: {T.ACCENT_TEAL}; }}"
        )
        self._details_btn.clicked.connect(self._toggle_details)
        title_row.addWidget(self._details_btn)
        layout.addLayout(title_row)
        _purpose = QLabel("TOOLS — Run workspace actions like reading files, writing code, and connecting to accounts.")
        _purpose.setObjectName("hub-purpose")
        _purpose.setWordWrap(True)
        _purpose.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        layout.addWidget(_purpose)
        layout.addWidget(
            mono_label(
                "Use the workspace drawer for the fastest path. Open a tool card when you need file help, study support, coding support, or connector context.",
                T.DIM,
                T.FS_SMALL,
            )
        )

        self._context_lbl = mono_label("WORKSPACE: GUPPY-PRIMARY | DAILY", T.ACCENT_TEAL, T.FS_TINY, True)
        self._limits_lbl = mono_label("Slots in use: 1 / 5 | Live now: 1 / 2", T.DIM, T.FS_TINY)
        layout.addWidget(self._context_lbl)
        layout.addWidget(self._limits_lbl)
        self._availability_lbl = mono_label("Available now: 0 | Set up first: 0 | Restricted here: 0", T.PRIMARY_DIM, T.FS_SMALL, True)
        self._availability_lbl.setWordWrap(True)
        layout.addWidget(self._availability_lbl)
        self._ownership_lbl = mono_label(
            "Settings connects accounts. Workspaces decides bindings. Tools runs the action for the active workspace.",
            T.DIM,
            T.FS_SMALL,
        )
        self._ownership_lbl.setWordWrap(True)
        layout.addWidget(self._ownership_lbl)
        self._planning_lbl = mono_label(
            "Planned adapter lanes stay in Models until a real local adapter ships.",
            T.DIM,
            T.FS_SMALL,
        )
        self._planning_lbl.setWordWrap(True)
        layout.addWidget(self._planning_lbl)
        self._boundary_lbl = mono_label(
            "Open Settings > Device & Accounts to connect, verify, reconnect, remove, or disable connector access. Stay here when you want task-level actions for the active workspace.",
            T.DIM,
            T.FS_SMALL,
        )
        self._boundary_lbl.setWordWrap(True)
        layout.addWidget(self._boundary_lbl)
        self._execution_lbl = mono_label(
            "Show details only when you want permission and sign-in checks.",
            T.DIM,
            T.FS_SMALL,
        )
        self._execution_lbl.setWordWrap(True)
        layout.addWidget(self._execution_lbl)

    def _build_section_tabs(self, layout: QVBoxLayout) -> None:
        self._sections = QTabWidget()
        self._sections.setDocumentMode(True)
        self._sections.setStyleSheet(
            f"QTabWidget::pane {{ border: 1px solid {T.BORDER_SOFT}; background: rgba(255,255,255,0.42); }}"
            f"QTabBar::tab {{ background: rgba(255,255,255,0.86); color: {T.DIM}; border: 1px solid {T.BORDER_SOFT}; border-radius: 3px;"
            f" padding: 4px 8px; margin-right: 4px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QTabBar::tab:selected {{ color: {T.TEXT}; border-color: {T.ACCENT_ORANGE}; background: rgba(255,109,0,0.12); }}"
        )
        self._quick_tab = QWidget()
        self._quick_layout = QVBoxLayout(self._quick_tab)
        self._quick_layout.setContentsMargins(14, 14, 14, 14)
        self._quick_layout.setSpacing(14)
        self._catalog_tab = QWidget()
        self._catalog_layout = QVBoxLayout(self._catalog_tab)
        self._catalog_layout.setContentsMargins(14, 14, 14, 14)
        self._catalog_layout.setSpacing(14)
        self._sections.addTab(self._quick_tab, "Quick")
        self._sections.addTab(self._catalog_tab, "Tools")
        layout.addWidget(self._sections)

    def _build_filters(self) -> QHBoxLayout:
        filters = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Find a workspace tool...")
        self._search.setToolTip("Type a keyword to filter workspace tools by name or description")
        self._search.setMinimumHeight(36)
        self._search.setStyleSheet(
            f"QLineEdit {{ background: {T.BG0}; border: 1px solid {T.BORDER_SOFT}; border-radius: 4px; color: {T.TEXT};"
            f" font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; padding: 4px 8px; }}"
            f"QLineEdit:focus {{ border-color: {T.ACCENT_TEAL}; }}"
        )
        self._search.textChanged.connect(self._apply_filters)

        self._filter_cb = QComboBox()
        self._filter_cb.addItems(["ALL", "READ", "WRITE", "CODE", "QUERY", "DEBUG", "RESTRICTED"])
        self._filter_cb.setToolTip("Filter tools by permission category")
        self._filter_cb.setMinimumHeight(36)
        self._filter_cb.currentTextChanged.connect(self._apply_filters)

        self._type_tabs = QTabWidget()
        self._type_tabs.setDocumentMode(True)
        self._type_tabs.setMaximumHeight(34)
        self._type_tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: none; }}"
            f"QTabBar::tab {{ background: rgba(255,255,255,0.86); color: {T.DIM}; border: 1px solid {T.BORDER};"
            f" padding: 3px 8px; margin-right: 4px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QTabBar::tab:selected {{ color: {T.INK}; border-color: {T.ACCENT_ORANGE}; background: rgba(255,109,0,0.12); }}"
        )
        for label in ("All", "Read", "Write", "Code", "Connect", "Restricted"):
            self._type_tabs.addTab(QWidget(), label)
        self._type_tabs.currentChanged.connect(self._apply_type_tab_filter)

        filters.addWidget(self._search, stretch=1)
        filters.addWidget(self._type_tabs)
        return filters

    def _build_boundary_banner(self) -> QFrame:
        banner = QFrame()
        banner.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}")
        banner_layout = QVBoxLayout(banner)
        banner_layout.setContentsMargins(16, 14, 16, 14)
        banner_layout.setSpacing(8)
        banner_layout.addWidget(mono_label("BOUNDARY", T.ACCENT_ORANGE, T.FS_TINY, True))
        banner_layout.addWidget(
            mono_label(
                "The workspace drawer is the fast path. This page stays useful when you want richer task context, workspace-safe file actions, or deeper access notes.",
                T.DIM,
                T.FS_SMALL,
            )
        )
        self._tray_notice_lbl = mono_label(
            "Use the workspace drawer or tray for common moves. Show details when you want the longer access explanation.",
            T.DIM,
            T.FS_SMALL,
        )
        self._tray_notice_lbl.setWordWrap(True)
        banner_layout.addWidget(self._tray_notice_lbl)
        return banner

    def _populate_cards(self) -> None:
        for tool in INSTANCE_TOOL_CATALOG:
            card = ToolCard(tool)
            card.hint_requested.connect(self.tool_hint_requested.emit)
            card.manage_requested.connect(self.tool_management_requested.emit)
            self._tool_cards[card.tool_key] = card
            self._tool_card_order.append(card.tool_key)
            self._register_scroll_proxy(card)

    def eventFilter(self, watched: object, event: object) -> bool:
        if (
            self._scroll is not None
            and isinstance(watched, QWidget)
            and isinstance(event, QEvent)
            and event.type() == QEvent.Type.Wheel
            and not isinstance(watched, (QComboBox, QLineEdit, QPlainTextEdit))
        ):
            bar = self._scroll.verticalScrollBar()
            if bar.maximum() > 0:
                wheel_event = event
                pixel_delta = wheel_event.pixelDelta().y()
                if pixel_delta:
                    delta = pixel_delta
                else:
                    steps = wheel_event.angleDelta().y() / 120.0
                    delta = int(steps * max(36, bar.singleStep()))
                if delta:
                    bar.setValue(bar.value() - delta)
                    wheel_event.accept()
                    return True
        return super().eventFilter(watched, event)

    def _register_scroll_proxy(self, widget: QWidget) -> None:
        widget.installEventFilter(self)
        for child in widget.findChildren(QWidget):
            if not isinstance(child, (QComboBox, QLineEdit, QPlainTextEdit)):
                child.installEventFilter(self)

    def set_instance_context(self, instance: dict[str, object], snapshot: dict[str, object] | None = None) -> None:
        name = str(instance.get("name", self._instance_name) or self._instance_name).strip() or "guppy-primary"
        instance_type = str(instance.get("type", self._instance_type) or self._instance_type).strip() or "user_instance"
        self._instance_name = name
        self._instance_type = instance_type

        limits = snapshot.get("limits", {}) if isinstance(snapshot, dict) else {}
        if isinstance(limits, dict):
            self._limits = {
                "configured": int(limits.get("configured", self._limits["configured"]) or self._limits["configured"]),
                "max_configured": int(limits.get("max_configured", self._limits["max_configured"]) or self._limits["max_configured"]),
                "active_runtime": int(limits.get("active_runtime", self._limits["active_runtime"]) or self._limits["active_runtime"]),
                "max_active_runtime": int(limits.get("max_active_runtime", self._limits["max_active_runtime"]) or self._limits["max_active_runtime"]),
            }

        self._context_lbl.setText(f"WORKSPACE: {name.upper()} | {workspace_type_label(instance_type).upper()}")
        limits_text = (
            f"Slots in use: {self._limits['configured']} / {self._limits['max_configured']} | "
            f"Live now: {self._limits['active_runtime']} / {self._limits['max_active_runtime']}"
        )
        if self._limits["configured"] >= self._limits["max_configured"]:
            limits_text += " | CONFIG CAP REACHED"
        if self._limits["active_runtime"] >= self._limits["max_active_runtime"]:
            limits_text += " | COLLABORATOR CAP REACHED"
        self._limits_lbl.setText(limits_text)
        self._boundary_lbl.setText(
            f"Use the workspace drawer for fast moves in {name}. Open Settings > Device & Accounts to connect, verify, reconnect, remove, or disable connector access."
        )
        self._tray_notice_lbl.setText(
            f"{name} can launch common actions from the workspace drawer or tray. This page keeps richer task context and optional access detail."
        )
        self._execution_lbl.setText(
            f"{name} can only use tools that match its workspace role and sign-in state. Show details for the exact rules."
        )
        self._builder_panel.set_instance_context(name, instance_type)
        for card in self._tool_cards.values():
            card.apply_context(name, instance_type)
            card.set_details_visible(self._details_visible)
        self._refresh_surface_summary()
        self._apply_filters()
        self.refresh_debug_surface()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._apply_density_mode(event.size().width())
        self._relayout_cards()

    def set_builder_status(self, text: str, ok: bool = True) -> None:
        self._builder_panel.set_status(text, ok=ok)

    def _apply_filters(self) -> None:
        category = self._filter_cb.currentText().strip().upper()
        query = self._search.text().strip().lower()
        visible_keys: list[str] = []
        for key in self._tool_card_order:
            card = self._tool_cards[key]
            matches_query = not query or query in card.search_blob
            matches_category = (
                category == "ALL"
                or (category == "RESTRICTED" and card.state == "restricted")
                or card.category == category
            )
            visible = matches_query and matches_category
            card.setVisible(visible)
            if visible:
                visible_keys.append(key)

        visible_cards = len(visible_keys)
        self._empty_state_lbl.setVisible(visible_cards == 0)
        self._cards_host.setVisible(visible_cards > 0)
        self._relayout_cards(visible_keys)

    def _tool_grid_columns(self) -> int:
        if self._scroll is None:
            available_width = self.width()
        else:
            viewport = self._scroll.viewport()
            available_width = viewport.width() if viewport is not None else self.width()
        if available_width <= 820:
            return 1
        if available_width <= 1320:
            return 2
        return 3

    def _relayout_cards(self, visible_keys: list[str] | None = None) -> None:
        if visible_keys is None:
            visible_keys = [key for key in self._tool_card_order if self._tool_cards[key].isVisible()]

        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(self._cards_host)

        columns = max(1, self._tool_grid_columns())
        for column in range(max(3, columns)):
            self._cards_layout.setColumnStretch(column, 0)
        for column in range(columns):
            self._cards_layout.setColumnStretch(column, 1)

        for index, key in enumerate(visible_keys):
            row = index // columns
            column = index % columns
            self._cards_layout.addWidget(self._tool_cards[key], row, column)

    def _toggle_details(self) -> None:
        self._details_visible = not self._details_visible
        self._sync_detail_visibility()

    def _sync_detail_visibility(self) -> None:
        self._banner.setVisible(self._details_visible)
        self._execution_lbl.setVisible(self._details_visible)
        self._details_btn.setText("HIDE DETAILS" if self._details_visible else "SHOW DETAILS")
        for card in self._tool_cards.values():
            card.set_details_visible(self._details_visible)
        self.refresh_debug_surface()
        if self.isVisible():
            self._apply_density_mode(self.width())

    def _apply_density_mode(self, width: int) -> None:
        compact = width <= 1100
        tight = width <= 900
        self._search.setPlaceholderText("Search tools" if compact else "Find a workspace tool...")
        if not self._details_visible:
            self._details_btn.setText("DETAILS" if tight else "SHOW DETAILS")
        self._type_tabs.setVisible(not tight)
        self._boundary_lbl.setVisible(not tight)

    def _apply_type_tab_filter(self, index: int) -> None:
        mapping = {
            0: "ALL",
            1: "READ",
            2: "WRITE",
            3: "CODE",
            4: "CONNECTOR",
            5: "RESTRICTED",
        }
        target = mapping.get(index, "ALL")
        filter_index = self._filter_cb.findText(target)
        self._filter_cb.setCurrentIndex(0 if filter_index < 0 else filter_index)

    def get_states(self) -> dict[str, bool]:
        return dict(self._tool_states)

    def set_states(self, states: dict[str, bool]) -> None:
        self._tool_states = {str(k): bool(v) for k, v in states.items()}
        self.refresh_debug_surface()

    def current_tool_states(self) -> dict[str, str]:
        return {key: card.state for key, card in self._tool_cards.items()}

    def _refresh_surface_summary(self) -> None:
        state = build_tools_surface_state(
            INSTANCE_TOOL_CATALOG,
            {key: card.state for key, card in self._tool_cards.items()},
        )
        self._availability_lbl.setText(state.summary_line)
        self._ownership_lbl.setText(state.ownership_line)
        self._planning_lbl.setText(state.planning_line)
        self._execution_lbl.setText(
            f"{state.guidance_line} Show details when you want the exact permission and sign-in evidence."
        )

    def refresh_debug_surface(self) -> None:
        self._trace_panel.set_tool_options(self._tool_card_order)
        snapshot: dict[str, object] = {}
        selected_tool = self._trace_panel.selected_tool()
        reader = self.read_debug_snapshot if callable(self.read_debug_snapshot) else None
        if reader is not None:
            try:
                snapshot = reader(tool_key=selected_tool or None, limit=8)
            except Exception:
                snapshot = {}
        tool_debug = self._tool_cards[selected_tool].debug_evidence if selected_tool in self._tool_cards else None
        self._trace_panel.set_snapshot(snapshot, instance_name=self._instance_name, tool_debug=tool_debug)

    def _on_trace_tool_selected(self, _tool_key: str) -> None:
        self.refresh_debug_surface()
