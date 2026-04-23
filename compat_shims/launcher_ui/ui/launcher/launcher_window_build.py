"""
launcher_window_build.py
UI construction for LauncherWindow — separated to keep the window class under the 550-line cap.
"""
from __future__ import annotations

import threading
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.guppy.launcher_application import launcher_library_handlers as _lib_handlers

from . import tokens as T
from .components import Sidebar, StatusPanel, TopBar
from .views import (
    AssistantView,
    InstanceManagerView,
    LibraryView,
    LocalLLMView,
    ModelsHubView,
    ModelsView,
    RuntimeRoutingView,
    SettingsDeviceAccountsPanel,
    SettingsHubView,
    SettingsOperationsPanel,
    SettingsView,
    ToolsView,
    VoicesView,
)


def build_launcher_window_ui(
    owner: Any,
    *,
    personalization_bootstrap_available: bool,
) -> None:
    central = QWidget(owner)
    owner.setCentralWidget(central)
    root = QVBoxLayout(central)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    owner._topbar = TopBar(owner)
    owner._topbar.setFixedHeight(T.TOPBAR_H)
    root.addWidget(owner._topbar)

    div = QFrame()
    div.setFixedHeight(1)
    div.setStyleSheet(f"background: {T.BORDER_SOFT};")
    root.addWidget(div)

    body = QHBoxLayout()
    body.setContentsMargins(0, 0, 0, 0)
    body.setSpacing(0)

    owner._sidebar = Sidebar(owner)
    body.addWidget(owner._sidebar)

    sdiv = QFrame()
    sdiv.setFixedWidth(1)
    sdiv.setStyleSheet(f"background: {T.BORDER_SOFT};")
    body.addWidget(sdiv)

    owner._stack = QStackedWidget(owner)
    owner._assistant_view = AssistantView(owner)
    owner._instance_manager_view = InstanceManagerView(owner)
    owner._library_view = LibraryView(owner)
    owner._tools_view = ToolsView(owner)
    owner._settings_view = SettingsView(owner)
    owner._settings_device_accounts_panel = SettingsDeviceAccountsPanel(owner)
    owner._settings_operations_panel = SettingsOperationsPanel(owner)
    owner._settings_hub_view = SettingsHubView(
        owner._settings_view,
        owner._settings_device_accounts_panel,
        owner._settings_operations_panel,
        owner,
    )
    owner._local_llm_view = LocalLLMView(owner)
    owner._models_view = ModelsView(owner)
    owner._runtime_view = RuntimeRoutingView(owner)
    owner._voices_view = VoicesView(owner)
    owner._models_hub_view = ModelsHubView(
        owner._models_view,
        owner._local_llm_view,
        owner._voices_view,
        owner,
    )

    for view in [
        owner._assistant_view,
        owner._instance_manager_view,
        owner._library_view,
        owner._tools_view,
        owner._settings_hub_view,
        owner._models_hub_view,
    ]:
        owner._stack.addWidget(view)

    body.addWidget(owner._stack, stretch=1)

    owner._status_divider = QFrame()
    owner._status_divider.setFixedWidth(1)
    owner._status_divider.setStyleSheet(f"background: {T.BORDER_SOFT};")
    body.addWidget(owner._status_divider)

    owner._status_panel = StatusPanel(owner)
    body.addWidget(owner._status_panel)
    _lib_handlers.ensure_library_workflow(owner)
    owner._wire_tools_trace_adapter()

    root.addLayout(body, stretch=1)

    owner._sys_strip = owner._build_sys_strip()
    root.addWidget(owner._sys_strip)

    owner._wire_signals()
    owner._assistant_view.set_session_id(owner._chat_session_id)
    owner._topbar.set_launcher_summary("AUTO / GUPPY / LIGHT [EDIT]")
    owner._topbar.set_runtime_status(
        "STARTING",
        detail="Launcher is still collecting startup readiness and runtime health.",
        severity="info",
    )
    owner._sidebar.set_collapsed(True)
    owner._topbar.set_sidebar_collapsed(True)
    owner._set_status_panel_visible(False)
    owner._bootstrap_instance_switcher()
    owner._refresh_personalization_state()
    owner._refresh_first_run_banner()
    owner._sync_automation_test_state()
    QTimer.singleShot(0, owner._apply_start_destination)

    if personalization_bootstrap_available:
        owner._log_launcher_event("startup_phase", phase="personalization_scaffold_thread_start")
        threading.Thread(target=owner._bootstrap_personalization_scaffold_worker, daemon=True).start()
