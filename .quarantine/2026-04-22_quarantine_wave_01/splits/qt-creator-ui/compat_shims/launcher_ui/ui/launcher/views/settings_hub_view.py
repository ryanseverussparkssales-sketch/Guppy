from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .. import tokens as T


_OUTER_MARGIN_X = 28
_OUTER_MARGIN_TOP = 22
_OUTER_MARGIN_BOTTOM = 26
_OUTER_SPACING = 14
_TAB_MIN_HEIGHT = 36
_CARD_RADIUS = 16


def _mono(text: str, color: str = T.DIM, size: int = T.FS_SMALL, bold: bool = False) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {size}pt; letter-spacing: 1px;"
        + (" font-weight: bold;" if bold else "")
    )
    return label


def _tab_button_style(active: bool) -> str:
    if active:
        return (
            f"QPushButton {{ background: {T.INK}; color: {T.BG}; border: 1px solid {T.INK}; "
            f"border-radius: 12px; padding: 8px 12px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        )
    return (
        f"QPushButton {{ background: {T.BG0}; color: {T.DIM}; border: 1px solid {T.BORDER}; "
        f"border-radius: 12px; padding: 8px 12px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        f"QPushButton:hover {{ color: {T.PRIMARY}; border-color: {T.PRIMARY}; }}"
    )


class _SettingsInfoPage(QWidget):
    def __init__(self, heading: str, detail: str, chips: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(_OUTER_SPACING)

        frame = QFrame()
        frame.setStyleSheet(f"QFrame {{ background: {T.BG0}; border: 1px solid {T.BORDER}; border-radius: {_CARD_RADIUS}px; }}")
        frame.setMinimumHeight(180)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(18, 14, 18, 14)
        frame_layout.setSpacing(10)
        frame_layout.addWidget(_mono(heading, T.PRIMARY, T.FS_TINY, True))
        frame_layout.addWidget(_mono(detail, T.TEXT, T.FS_SMALL))
        chips_row = QHBoxLayout()
        chips_row.setSpacing(8)
        for chip in chips:
            badge = QLabel(chip.upper())
            badge.setStyleSheet(
                f"color: {T.DIM}; background: {T.SURFACE_ELEVATED_92}; border: 1px solid {T.BORDER};"
                f" border-radius: 10px; padding: 4px 8px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
            )
            chips_row.addWidget(badge)
        chips_row.addStretch(1)
        frame_layout.addLayout(chips_row)
        layout.addWidget(frame)
        layout.addStretch(1)


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
        self._content_layout: QVBoxLayout | None = None
        self._content_title: QLabel | None = None
        self._content_note: QLabel | None = None
        self._tab_buttons: dict[str, QPushButton] = {}
        self._active_tab = "general"
        self._general_page = _SettingsInfoPage(
            "GENERAL",
            "Use this hub to tune behavior, connect vendors, and recover runtime health.",
            [
                "customization",
                "performance",
                "accounts",
                "backend stats",
            ],
        )
        self._help_page = _SettingsInfoPage(
            "HELP",
            "Model names stay in Models. Keys, vendors, and runtime operations stay in Settings.",
            [
                "accounts first",
                "backend stats for health",
                "customization for tone",
                "performance for speed",
            ],
        )
        embed_mode = getattr(self._settings_view, "set_embed_mode", None)
        if callable(embed_mode):
            embed_mode(True)
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
        outer.setContentsMargins(_OUTER_MARGIN_X, _OUTER_MARGIN_TOP, _OUTER_MARGIN_X, _OUTER_MARGIN_BOTTOM)
        outer.setSpacing(_OUTER_SPACING)

        title = QLabel("Settings")
        title.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_HEAD}'; font-size: 28pt; font-weight: 900; letter-spacing: -1px;"
        )
        outer.addWidget(title)

        purpose = QLabel("SETTINGS - Keep the assistant understandable, the vendors connected, and the runtime recoverable.")
        purpose.setObjectName("hub-purpose")
        purpose.setWordWrap(True)
        purpose.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        purpose.setToolTip("Settings owns assistant naming, defaults, accounts, plugins, backend diagnostics, and help.")
        outer.addWidget(purpose)
        outer.addWidget(
            _mono(
                "Use tabs to focus one settings lane at a time.",
                T.DIM,
                T.FS_SMALL,
            )
        )

        tabs_row = QHBoxLayout()
        tabs_row.setSpacing(8)
        for key, label, tooltip in [
            ("general", "General", "Plain-language home for the settings hub."),
            ("customization", "Customization", "Assistant naming and persona behavior."),
            ("performance", "Performance", "Runtime defaults and execution posture."),
            ("accounts", "Accounts", "Vendor sign-in, keys, and account linking."),
            ("plugins", "Plugins", "Connector and plugin inventory handled in the same clean settings surface."),
            ("backend_stats", "Backend Stats", "Diagnostics, recovery, terminal, and automation evidence."),
            ("help", "Help", "Explain what each settings area is for."),
        ]:
            button = QPushButton(label.upper())
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(_TAB_MIN_HEIGHT)
            button.setToolTip(tooltip)
            button.clicked.connect(lambda _=False, target=key: self._set_active_tab(target))
            self._tab_buttons[key] = button
            tabs_row.addWidget(button)
        tabs_row.addStretch(1)
        outer.addLayout(tabs_row)

        content_frame = QFrame()
        content_frame.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; border-radius: {_CARD_RADIUS + 2}px; }}")
        content_frame.setMinimumHeight(520)
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(22, 18, 22, 20)
        content_layout.setSpacing(10)
        self._content_title = QLabel("")
        self._content_title.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_HEAD}'; font-size: {T.FS_TITLE + 1}pt; font-weight: 800;"
        )
        self._content_note = _mono("", T.DIM, T.FS_SMALL)
        content_layout.addWidget(self._content_title)
        content_layout.addWidget(self._content_note)
        self._content_layout = content_layout
        outer.addWidget(content_frame, stretch=1)

        self._set_active_tab("general")

    def _clear_content(self) -> None:
        if self._content_layout is None:
            return
        while self._content_layout.count() > 2:
            item = self._content_layout.takeAt(2)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    def _configure_settings_section(self, section: str) -> None:
        shower = getattr(self._settings_view, "show_settings_section", None)
        if callable(shower):
            shower(section)

    def _set_active_tab(self, tab: str) -> None:
        self._active_tab = tab
        for key, button in self._tab_buttons.items():
            button.setStyleSheet(_tab_button_style(key == tab))

        configs = {
            "general": (
                "General",
                "Start here when you need to understand what Guppy is using and where to change it.",
                self._general_page,
                None,
            ),
            "customization": (
                "Customization",
                "Name the assistant, tune its behavior, and keep persona separate from model identity.",
                self._settings_view,
                "personas",
            ),
            "performance": (
                "Performance",
                "Set runtime defaults, daemon posture, and the everyday execution profile.",
                self._settings_view,
                "runtime",
            ),
            "accounts": (
                "Accounts",
                "Connect vendors, store keys, and verify account state in one place.",
                self._device_accounts_panel,
                None,
            ),
            "plugins": (
                "Plugins",
                "Use the same clean vendor inventory surface for plugin-style connectors and external integrations.",
                self._device_accounts_panel,
                None,
            ),
            "backend_stats": (
                "Backend Stats",
                "See runtime health, recovery state, automation evidence, and terminal workflows without hunting through nested panes.",
                self._operations_panel,
                None,
            ),
            "help": (
                "Help",
                "Quick explanations so every section reads clearly instead of relying on vague labels.",
                self._help_page,
                None,
            ),
        }
        title, note, widget, section = configs.get(tab, configs["general"])
        if self._content_title is not None:
            self._content_title.setText(title)
        if self._content_note is not None:
            self._content_note.setText(note)
        if section is not None:
            self._configure_settings_section(section)
        self._clear_content()
        if self._content_layout is not None:
            self._content_layout.addWidget(widget, stretch=1)

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
        del summary
        self._device_accounts_panel.set_connector_inventory(inventory)
        self._operations_panel.set_connector_inventory(inventory)

    def set_windows_snapshot(self, snapshot: dict[str, object]) -> None:
        self._device_accounts_panel.set_windows_snapshot(snapshot)

    def set_windows_ops_feedback(self, *args, **kwargs) -> None:
        self._operations_panel.set_windows_ops_feedback(*args, **kwargs)

    def set_recovery_status(self, text: str) -> None:
        self._operations_panel.set_recovery_status(text)

    def set_account_result(self, text: str, ok: bool = True) -> None:
        self._device_accounts_panel.set_account_result(text, ok=ok)

    def focus_connectors(
        self,
        connector_id: str = "",
        *,
        provider: str = "",
        account_id: str = "",
        note: str = "",
    ) -> None:
        self._set_active_tab("accounts")
        focus = getattr(self._device_accounts_panel, "focus_connector", None)
        if callable(focus):
            focus(
                connector_id,
                provider=provider,
                account_id=account_id,
                note=note,
            )
        self.open_connectors_requested.emit()

    def windows_ops_snapshot(self) -> dict[str, str]:
        return self._operations_panel.windows_ops_snapshot()

    def append_log(self, text: str) -> None:
        self._operations_panel.append_log(text)

    def focus_operator_logs(self, log_filter: str = "ALL", note: str = "") -> None:
        self._set_active_tab("backend_stats")
        self._operations_panel.focus_operator_logs(log_filter, note=note)
        self.open_diagnostics_requested.emit()

    def focus_terminal(self, note: str = "") -> None:
        self._set_active_tab("backend_stats")
        self._operations_panel.focus_terminal(note=note)
        self.open_terminal_requested.emit()

    def focus_automation_test(self, note: str = "") -> None:
        self._set_active_tab("backend_stats")
        self._operations_panel.focus_automation_test(note=note)
        self.open_diagnostics_requested.emit()

    def queue_terminal_recipe(
        self,
        commands: list[str],
        *,
        label: str = "",
        recipe_context: dict[str, object] | None = None,
    ) -> bool:
        self._set_active_tab("backend_stats")
        return self._operations_panel.queue_terminal_recipe(commands, label=label, recipe_context=recipe_context)

    def automation_status_text(self) -> str:
        label = getattr(self._operations_panel, "_automation_status_lbl", None)
        text_getter = getattr(label, "text", None)
        return str(text_getter() or "").strip() if callable(text_getter) else ""
