from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import tokens as T


def _mono(text: str, color: str = T.DIM, size: int = T.FS_SMALL, bold: bool = False) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {size}pt; letter-spacing: 1px;"
        + (" font-weight: bold;" if bold else "")
    )
    return label


class SettingsHubView(QWidget):
    open_diagnostics_requested = Signal()
    open_recovery_requested = Signal()
    open_connectors_requested = Signal()
    open_system_requested = Signal()
    open_terminal_requested = Signal()
    settings_saved = Signal(dict)
    recovery_requested = Signal(str)
    windows_ops_requested = Signal(str)
    connector_action_requested = Signal(dict)
    connector_guided_link_requested = Signal(dict)
    automation_action_requested = Signal(str)
    terminal_recipe_finished = Signal(dict)

    def __init__(
        self,
        settings_view: QWidget,
        device_accounts_panel: QWidget,
        operations_panel: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings_view = settings_view
        self._device_accounts_panel = device_accounts_panel
        self._operations_panel = operations_panel
        self._wire_child_signals()
        self._build_ui()

    def _wire_child_signals(self) -> None:
        settings_saved = getattr(self._settings_view, "settings_saved", None)
        if settings_saved is not None:
            settings_saved.connect(self.settings_saved.emit)
        recovery_requested = getattr(self._settings_view, "recovery_requested", None)
        if recovery_requested is not None:
            recovery_requested.connect(self.recovery_requested.emit)
        self._device_accounts_panel.windows_ops_requested.connect(self._relay_device_windows_action)
        self._device_accounts_panel.connector_action_requested.connect(self.connector_action_requested.emit)
        self._device_accounts_panel.connector_guided_link_requested.connect(self.connector_guided_link_requested.emit)
        self._operations_panel.recovery_requested.connect(self.recovery_requested.emit)
        self._operations_panel.windows_ops_requested.connect(self.windows_ops_requested.emit)
        self._operations_panel.connector_action_requested.connect(self.connector_action_requested.emit)
        self._operations_panel.automation_action_requested.connect(self.automation_action_requested.emit)
        self._operations_panel.terminal_recipe_finished.connect(self.terminal_recipe_finished.emit)

    def _relay_device_windows_action(self, action: str) -> None:
        normalized = {
            "supervised_api": "start_supervised_api",
            "restart_api": "restart_runtime",
            "repair": "repair_runtime",
        }.get(str(action or "").strip(), str(action or "").strip())
        if normalized:
            self.windows_ops_requested.emit(normalized)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Settings Hub")
        title.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_HEAD}'; font-size: 28pt; font-weight: 900; letter-spacing: -1px;"
        )
        layout.addWidget(title)
        purpose = QLabel("SETTINGS — Configure your assistant, API keys, connectors, and recovery options.")
        purpose.setObjectName("hub-purpose")
        purpose.setWordWrap(True)
        purpose.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        layout.addWidget(purpose)
        layout.addWidget(
            _mono(
                "Unified settings ownership: configuration, device accounts, diagnostics, recovery, connector workflows, system controls, and terminal operations now live here.",
                T.DIM,
                T.FS_SMALL,
            )
        )

        overview = QFrame()
        overview.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}")
        overview_layout = QVBoxLayout(overview)
        overview_layout.setContentsMargins(16, 14, 16, 14)
        overview_layout.setSpacing(10)
        overview_layout.addWidget(_mono("SECTION OWNERSHIP", T.PRIMARY, T.FS_TINY, True))
        overview_layout.addWidget(
            _mono(
                "This hub now owns the full launcher settings surface. The cards below are section shortcuts, not handoffs to legacy pages.",
                T.DIM,
                T.FS_SMALL,
            )
        )

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        cards = [
            (
                "Configuration",
                "Runtime defaults and Persona Builder stay embedded here as the canonical settings editor.",
                "Owned by Settings Hub",
                None,
            ),
            (
                "Diagnostics",
                "System status, operator logs, and automation evidence live in the operations lane below.",
                "Owned by Settings Hub",
                self.open_diagnostics_requested,
            ),
            (
                "Recovery",
                "Warmup, restart, audit, and recovery actions live in the operations lane below.",
                "Owned by Settings Hub",
                self.open_recovery_requested,
            ),
            (
                "Connectors",
                "Friendly account linking and connector inventory now live in this hub.",
                "Owned by Settings Hub",
                self.open_connectors_requested,
            ),
            (
                "System",
                "Desktop runtime, API state, and machine snapshots now live in this hub.",
                "Owned by Settings Hub",
                self.open_system_requested,
            ),
            (
                "Terminal",
                "Embedded terminal recipes and workflow loops now live in the operations lane below.",
                "Owned by Settings Hub",
                self.open_terminal_requested,
            ),
        ]
        for index, (heading, description, owner, signal) in enumerate(cards):
            grid.addWidget(self._build_section_card(heading, description, owner, signal), index // 2, index % 2)
        overview_layout.addLayout(grid)
        layout.addWidget(overview)

        configuration_frame = QFrame()
        configuration_frame.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}")
        configuration_layout = QVBoxLayout(configuration_frame)
        configuration_layout.setContentsMargins(16, 14, 16, 14)
        configuration_layout.setSpacing(10)
        configuration_layout.addWidget(_mono("CONFIGURATION", T.PRIMARY, T.FS_TINY, True))
        configuration_layout.addWidget(
            _mono(
                "This is the existing SettingsView, preserved as the canonical editor for runtime defaults and persona configuration.",
                T.DIM,
                T.FS_SMALL,
            )
        )
        configuration_layout.addWidget(self._settings_view)
        layout.addWidget(configuration_frame)

        device_frame = QFrame()
        device_frame.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}")
        device_layout = QVBoxLayout(device_frame)
        device_layout.setContentsMargins(16, 14, 16, 14)
        device_layout.setSpacing(10)
        device_layout.addWidget(_mono("DEVICE & ACCOUNTS", T.PRIMARY, T.FS_TINY, True))
        device_layout.addWidget(
            _mono(
                "Runtime health, machine state, connector guidance, and account linking now share the same settings home.",
                T.DIM,
                T.FS_SMALL,
            )
        )
        device_layout.addWidget(self._device_accounts_panel)
        layout.addWidget(device_frame)

        operations_frame = QFrame()
        operations_frame.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}")
        operations_layout = QVBoxLayout(operations_frame)
        operations_layout.setContentsMargins(16, 14, 16, 14)
        operations_layout.setSpacing(10)
        operations_layout.addWidget(_mono("OPERATIONS", T.PRIMARY, T.FS_TINY, True))
        operations_layout.addWidget(
            _mono(
                "Diagnostics, recovery, automation evidence, and terminal workflows remain intact but now belong to this hub instead of a separate page.",
                T.DIM,
                T.FS_SMALL,
            )
        )
        operations_layout.addWidget(self._operations_panel)
        layout.addWidget(operations_frame)
        layout.addStretch(1)

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _build_section_card(
        self,
        heading: str,
        description: str,
        owner: str,
        signal: Signal | None,
    ) -> QWidget:
        frame = QFrame()
        frame.setStyleSheet(f"QFrame {{ background: {T.BG0}; border: 1px solid {T.BORDER}; }}")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(_mono(heading.upper(), T.TEXT, T.FS_TINY, True))
        layout.addWidget(_mono(description, T.DIM, T.FS_SMALL))
        layout.addWidget(_mono(owner, T.PRIMARY_DIM, T.FS_TINY, True))
        if signal is not None:
            button = QPushButton("FOCUS SECTION")
            button.setToolTip(f"Scroll to the {heading} section in this hub")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(
                f"QPushButton {{ background: {T.BG0}; color: {T.PRIMARY}; border: 1px solid {T.PRIMARY};"
                f" padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ background: {T.PRIMARY}; color: {T.BG}; }}"
            )
            button.clicked.connect(signal.emit)
            layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignLeft)
        return frame

    def set_daily_context_activity(self, text: str) -> None:
        self._operations_panel.set_daily_context_activity(text)

    def set_daily_context_workspace(self, text: str) -> None:
        self._operations_panel.set_daily_context_workspace(text)

    def set_daily_context_runtime(self, text: str) -> None:
        self._operations_panel.set_daily_context_runtime(text)

    def set_daily_context_route(self, text: str) -> None:
        self._operations_panel.set_daily_context_route(text)

    def set_daily_context_recovery(self, text: str, ok: bool = True) -> None:
        self._operations_panel.set_daily_context_recovery(text, ok=ok)

    def set_status_snapshot(self, payload: dict[str, object]) -> None:
        self._operations_panel.set_status_snapshot(payload)

    def set_instance_snapshot(self, payload: dict[str, object]) -> None:
        self._operations_panel.set_instance_snapshot(payload)

    def set_automation_snapshot(self, payload: dict[str, object]) -> None:
        self._operations_panel.set_automation_snapshot(payload)

    def set_automation_status(self, status: str, ok: bool = True) -> None:
        self._operations_panel.set_automation_status(status, ok=ok)

    def set_connector_inventory(self, inventory: list[dict[str, object]], summary: str = "") -> None:
        self._device_accounts_panel.set_connector_inventory(inventory, summary)
        self._operations_panel.set_connector_inventory(inventory, summary)

    def set_windows_snapshot(self, snapshot: dict[str, object]) -> None:
        self._device_accounts_panel.set_windows_snapshot(snapshot)

    def set_windows_ops_feedback(self, *args, **kwargs) -> None:
        self._operations_panel.set_windows_ops_feedback(*args, **kwargs)

    def set_recovery_status(self, text: str) -> None:
        self._operations_panel.set_recovery_status(text)

    def set_account_result(self, text: str, ok: bool = True) -> None:
        self._device_accounts_panel.set_account_result(text, ok=ok)

    def windows_ops_snapshot(self) -> dict[str, str]:
        return self._operations_panel.windows_ops_snapshot()

    def append_log(self, text: str) -> None:
        self._operations_panel.append_log(text)

    def focus_operator_logs(self, log_filter: str = "ALL", note: str = "") -> None:
        self._operations_panel.focus_operator_logs(log_filter, note=note)
        self.open_diagnostics_requested.emit()

    def focus_terminal(self, note: str = "") -> None:
        self._operations_panel.focus_terminal(note=note)
        self.open_terminal_requested.emit()

    def focus_automation_test(self, note: str = "") -> None:
        self._operations_panel.focus_automation_test(note=note)
        self.open_diagnostics_requested.emit()

    def queue_terminal_recipe(
        self,
        commands: list[str],
        *,
        label: str = "",
        recipe_context: dict[str, object] | None = None,
    ) -> bool:
        return self._operations_panel.queue_terminal_recipe(commands, label=label, recipe_context=recipe_context)

    def automation_status_text(self) -> str:
        label = getattr(self._operations_panel, "_automation_status_lbl", None)
        text_getter = getattr(label, "text", None)
        return str(text_getter() or "").strip() if callable(text_getter) else ""
