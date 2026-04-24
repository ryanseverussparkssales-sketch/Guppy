"""
launcher_shell_orchestrator.py

Extracted from: ui/launcher/launcher_window.py
Purpose: Orchestrate launcher shell UI assembly, navigation, and tab lifecycle
Lane: TR54-B1

Extracted Methods:
  - _build_ui() - Main layout assembly (topbar, sidebar, content stack, status panel)
  - _wire_signals() - Signal connection hub
  - _on_tab_change() - Tab navigation handler
  - _apply_start_destination() - Startup routing
  - _resolve_stack_index() - Stack index resolution
  - _visible_nav_index() - Navigation visibility logic
  - _shell_model_loadout_summary() - Model summary building
  - _sync_shell_model_summary() - Model summary sync
  - Navigation state management
  - _set_status_panel_visible() - Status panel visibility control
  - _toggle_status_panel() - Status panel toggle
  - _toggle_sidebar() - Sidebar toggle

Dependencies:
  - PySide6 (QWidget, QMainWindow, QStackedWidget, QVBoxLayout, QHBoxLayout)
  - ui.launcher.components (TopBar, Sidebar, StatusPanel)
  - ui.launcher.views (AssistantView, LibraryView, ToolsView, ModelsView, etc.)
  - ui.launcher.tokens (T) - design tokens
  - ui.launcher.stylesheet (SHEET) - stylesheets
  - src.guppy.launcher_application.launcher_nav_handlers - navigation logic
  - src.guppy.launcher_application.launcher_command_flow - model/mode utilities
  - src.guppy.launcher_application.launcher_shell_support - quick action utilities
"""

from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.guppy.launcher_application import launcher_nav_handlers as _nav_handlers
from src.guppy.launcher_application.launcher_command_flow import (
    build_shell_model_loadout_summary,
)
from src.guppy.launcher_application.launcher_shell_support import (
    apply_quick_action_plan as _apply_quick_action_plan_fn,
)

from .. import tokens as T
from ..stylesheet import SHEET
from ..components import Sidebar, TopBar, StatusPanel
from ..views import (
    AssistantView,
    InstanceManagerView,
    LibraryView,
    ToolsView,
    SettingsView,
    SettingsHubView,
    SettingsDeviceAccountsPanel,
    SettingsOperationsPanel,
    ModelsHubView,
    LocalLLMView,
    ModelsView,
    RuntimeRoutingView,
    VoicesView,
)


# Navigation view indices (from launcher_nav_handlers)
_SETTINGS_VIEW_INDEX = _nav_handlers.SETTINGS_VIEW_INDEX
_MODELS_VIEW_INDEX = _nav_handlers.MODELS_VIEW_INDEX


class LauncherShellOrchestrator:
    """Coordinates launcher shell UI assembly, navigation, and state management."""

    def __init__(self, window) -> None:
        """
        Initialize shell orchestrator.

        Args:
            window: Parent LauncherWindow instance
        """
        self.window = window
        self._status_panel_visible = False
        self._sidebar_collapsed = True
        self._last_tab_index = 0

    def build_ui(self) -> None:
        """
        Assemble main launcher UI layout.

        Layout structure:
          - Root (vertical): topbar | divider | body | system_strip
          - Body (horizontal): sidebar | divider | content_stack | divider | status_panel
          - Content stack: AssistantView, InstanceManager, Library, Tools, Settings Hub, Models Hub
        """
        central = QWidget(self.window)
        self.window.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top bar ─────────────────────────────────────────────────────────
        self.window._topbar = TopBar(self.window)
        self.window._topbar.setFixedHeight(T.TOPBAR_H)
        root.addWidget(self.window._topbar)

        # ── Divider ──────────────────────────────────────────────────────────
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background: {T.BORDER};")
        root.addWidget(div)

        # ── Body row: Sidebar | Content | StatusPanel ────────────────────────
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.window._sidebar = Sidebar(self.window)
        body.addWidget(self.window._sidebar)

        # Thin vertical divider
        sdiv = QFrame()
        sdiv.setFixedWidth(1)
        sdiv.setStyleSheet(f"background: {T.BORDER};")
        body.addWidget(sdiv)

        # Content stack - instantiate all view components
        self.window._stack = QStackedWidget(self.window)
        self.window._assistant_view = AssistantView(self.window)
        self.window._instance_manager_view = InstanceManagerView(self.window)
        self.window._library_view = LibraryView(self.window)
        self.window._tools_view = ToolsView(self.window)
        self.window._settings_view = SettingsView(self.window)
        self.window._settings_device_accounts_panel = SettingsDeviceAccountsPanel(self.window)
        self.window._settings_operations_panel = SettingsOperationsPanel(self.window)
        self.window._settings_hub_view = SettingsHubView(
            self.window._settings_view,
            self.window._settings_device_accounts_panel,
            self.window._settings_operations_panel,
            self.window,
        )
        self.window._local_llm_view = LocalLLMView(self.window)
        self.window._models_view = ModelsView(self.window)
        self.window._runtime_view = RuntimeRoutingView(self.window)
        self.window._voices_view = VoicesView(self.window)
        self.window._models_hub_view = ModelsHubView(
            self.window._models_view,
            self.window._local_llm_view,
            self.window._voices_view,
            self.window,
        )

        # Add views to stacked widget in order
        for view in [
            self.window._assistant_view,
            self.window._instance_manager_view,
            self.window._library_view,
            self.window._tools_view,
            self.window._settings_hub_view,
            self.window._models_hub_view,
        ]:
            self.window._stack.addWidget(view)

        body.addWidget(self.window._stack, stretch=1)

        # Thin vertical divider
        self.window._status_divider = QFrame()
        self.window._status_divider.setFixedWidth(1)
        self.window._status_divider.setStyleSheet(f"background: {T.BORDER};")
        body.addWidget(self.window._status_divider)

        # Status panel
        self.window._status_panel = StatusPanel(self.window)
        body.addWidget(self.window._status_panel)

        root.addLayout(body, stretch=1)

        # ── Bottom system strip ──────────────────────────────────────────────
        self.window._sys_strip = self.window._build_sys_strip()
        root.addWidget(self.window._sys_strip)

    def wire_navigation_signals(self) -> None:
        """Wire tab change and navigation signals."""
        # Tab change signal from sidebar
        if hasattr(self.window._sidebar, "tab_requested"):
            self.window._sidebar.tab_requested.connect(self.on_tab_change)

        # View-specific signals (delegated to window event handlers)
        if hasattr(self.window._assistant_view, "chat_context_requested"):
            self.window._assistant_view.chat_context_requested.connect(
                self.window._on_chat_context_changed
            )

    def apply_initial_state(self) -> None:
        """Apply initial window state after UI is built."""
        self.window._topbar.set_launcher_summary("AUTO / GUPPY / LIGHT [EDIT]")
        self.window._topbar.set_runtime_status(
            "STARTING",
            detail="Launcher is still collecting startup readiness and runtime health.",
            severity="info",
        )
        self.set_status_panel_visible(False)
        self.set_sidebar_collapsed(True)
        self.window._topbar.set_sidebar_collapsed(True)

        # Apply startup destination after layout is finalized
        QTimer.singleShot(0, self.apply_start_destination)

    def on_tab_change(self, index: int, runtime_path: Path) -> None:
        """
        Handle tab navigation.

        Args:
            index: View stack index (0=Home, 1=Instances, 2=Library, 3=Tools, 4=Settings, 5=Models)
            runtime_path: Path to runtime directory
        """
        _nav_handlers.on_tab_change(self.window, index, runtime_path=runtime_path)
        self._last_tab_index = index

    def apply_start_destination(self) -> None:
        """Apply startup destination (override via GUPPY_START_DESTINATION env var)."""
        _nav_handlers.apply_start_destination(self.window)

    @staticmethod
    def resolve_stack_index(index: int) -> int:
        """
        Resolve logical view index to stack widget index.

        Args:
            index: Logical view index

        Returns:
            Actual stack widget index
        """
        return _nav_handlers.resolve_stack_index(index)

    @staticmethod
    def visible_nav_index(index: int) -> int:
        """
        Get visible navigation index for a stack index.

        Args:
            index: Stack widget index

        Returns:
            Visible nav index
        """
        return _nav_handlers.visible_nav_index(index)

    @staticmethod
    def shell_model_loadout_summary(
        *,
        active_model: str = "",
        runtime_backend: str = "",
        settings_payload: dict[str, object] | None = None,
        environment: dict[str, str] | None = None,
    ) -> str:
        """
        Build human-readable model loadout summary for topbar.

        Args:
            active_model: Active model identifier
            runtime_backend: Runtime backend name
            settings_payload: Settings configuration dict
            environment: Environment variables dict

        Returns:
            Formatted summary string (e.g., "Claude 3.5 Sonnet / Guppy Desktop")
        """
        return build_shell_model_loadout_summary(
            active_model=active_model,
            runtime_backend=runtime_backend,
            settings_payload=settings_payload,
            environment=environment,
        )

    def sync_shell_model_summary(
        self, *, active_model: str = "", runtime_backend: str = "", runtime_path: Path | None = None
    ) -> None:
        """
        Sync model summary to topbar and update related UI.

        Args:
            active_model: Active model identifier
            runtime_backend: Runtime backend name
            runtime_path: Path to runtime directory (optional)
        """
        if runtime_path is None:
            return
        _nav_handlers.sync_shell_model_summary(
            self.window, runtime_path=runtime_path,
            active_model=active_model, runtime_backend=runtime_backend
        )

    def set_status_panel_visible(self, visible: bool) -> None:
        """
        Show/hide status panel.

        Args:
            visible: True to show, False to hide
        """
        if hasattr(self.window, "_status_panel"):
            self.window._status_panel.setVisible(visible)
        if hasattr(self.window, "_status_divider"):
            self.window._status_divider.setVisible(visible)
        self._status_panel_visible = visible

    def toggle_status_panel(self) -> None:
        """Toggle status panel visibility."""
        self.set_status_panel_visible(not self._status_panel_visible)

    def set_sidebar_collapsed(self, collapsed: bool) -> None:
        """
        Collapse/expand sidebar.

        Args:
            collapsed: True to collapse, False to expand
        """
        if hasattr(self.window, "_sidebar"):
            self.window._sidebar.set_collapsed(collapsed)
        self._sidebar_collapsed = collapsed

    def toggle_sidebar(self) -> None:
        """Toggle sidebar collapse state."""
        self.set_sidebar_collapsed(not self._sidebar_collapsed)

    def refresh_notification_badge(self) -> None:
        """Refresh notification badge count on sidebar."""
        if hasattr(self.window, "_sidebar") and callable(
            getattr(self.window._sidebar, "refresh_notification_badge", None)
        ):
            self.window._sidebar.refresh_notification_badge()
