"""Smoke test - PL-C3 hub clarity guarantees.

Verifies that all 5 hub views:
  1. Carry a QLabel with objectName="hub-purpose" (PL-C3 acceptance criterion)
  2. Have at least one interactive element (QPushButton or QLineEdit) with a tooltip
  3. Primary buttons have a minimum height of at least 36px

Run via: pytest tests/smoke/test_hub_clarity_smoke.py -v
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import (
        QApplication,
        QLabel,
        QLineEdit,
        QPushButton,
        QWidget,
    )
    from ui.launcher.views.assistant_view import AssistantView
    from ui.launcher.views.library_view import LibraryView
    from ui.launcher.views.models_hub_view import ModelsHubView
    from ui.launcher.views.settings_device_accounts_panel import SettingsDeviceAccountsPanel
    from ui.launcher.views.settings_hub_view import SettingsHubView
    from ui.launcher.views.settings_operations_panel import SettingsOperationsPanel
    from ui.launcher.views.settings_view import SettingsView
    from ui.launcher.views.tools_view import ToolsView
except Exception as exc:  # pragma: no cover
    QApplication = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


def _has_hub_purpose_label(widget: QWidget) -> bool:
    """Return True if widget tree contains a QLabel with objectName='hub-purpose'."""
    return any(label.objectName() == "hub-purpose" for label in widget.findChildren(QLabel))


def _tooltipped_buttons(widget: QWidget) -> list[QPushButton]:
    return [btn for btn in widget.findChildren(QPushButton) if btn.toolTip().strip()]


def _tooltipped_line_edits(widget: QWidget) -> list[QLineEdit]:
    return [line_edit for line_edit in widget.findChildren(QLineEdit) if line_edit.toolTip().strip()]


@unittest.skipIf(QApplication is None, f"PySide6 import failed: {IMPORT_ERROR}")
class HubPurposeLabelSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    # ------------------------------------------------------------------
    # HOME hub
    # ------------------------------------------------------------------

    def test_home_hub_has_purpose_label(self) -> None:
        widget = AssistantView()
        self.assertTrue(
            _has_hub_purpose_label(widget),
            "AssistantView (HOME hub) is missing a QLabel with objectName='hub-purpose'",
        )

    # ------------------------------------------------------------------
    # MODELS hub
    # ------------------------------------------------------------------

    def test_models_hub_has_purpose_label(self) -> None:
        hub = ModelsHubView(QWidget(), QWidget(), QWidget())
        self.assertTrue(
            _has_hub_purpose_label(hub),
            "ModelsHubView (MODELS hub) is missing a QLabel with objectName='hub-purpose'",
        )

    def test_models_hub_has_at_least_one_tooltip(self) -> None:
        hub = ModelsHubView(QWidget(), QWidget(), QWidget())
        tooltipped_widgets = [widget for widget in hub.findChildren(QWidget) if widget.toolTip().strip()]
        self.assertGreater(
            len(tooltipped_widgets),
            0,
            "ModelsHubView has no widgets with tooltips - add setToolTip() to primary interactive elements",
        )

    # ------------------------------------------------------------------
    # TOOLS hub
    # ------------------------------------------------------------------

    def test_tools_hub_has_purpose_label(self) -> None:
        widget = ToolsView()
        self.assertTrue(
            _has_hub_purpose_label(widget),
            "ToolsView (TOOLS hub) is missing a QLabel with objectName='hub-purpose'",
        )

    def test_tools_hub_has_at_least_two_tooltipped_elements(self) -> None:
        widget = ToolsView()
        count = len(_tooltipped_buttons(widget)) + len(_tooltipped_line_edits(widget))
        self.assertGreaterEqual(
            count,
            2,
            f"ToolsView has only {count} tooltipped interactive element(s); expected >=2",
        )

    def test_tools_hub_search_has_min_height(self) -> None:
        widget = ToolsView()
        search = widget.findChild(QLineEdit)
        self.assertIsNotNone(search, "ToolsView: expected a QLineEdit for search")
        self.assertGreaterEqual(
            search.minimumHeight(),
            36,
            f"ToolsView search box has minimumHeight={search.minimumHeight()}, expected >=36",
        )

    def test_tools_hub_details_button_has_min_height(self) -> None:
        widget = ToolsView()
        show_details = next(
            (btn for btn in widget.findChildren(QPushButton) if "DETAIL" in btn.text()),
            None,
        )
        self.assertIsNotNone(show_details, "ToolsView: SHOW DETAILS button not found")
        self.assertGreaterEqual(
            show_details.minimumHeight(),
            36,
            f"SHOW DETAILS button minimumHeight={show_details.minimumHeight()}, expected >=36",
        )

    def test_tools_hub_compact_mode_hides_type_tabs(self) -> None:
        widget = ToolsView()
        widget.resize(860, 900)
        widget._apply_density_mode(860)
        self.assertFalse(widget._type_tabs.isVisible())
        self.assertEqual(widget._details_btn.text(), "DETAILS")

    # ------------------------------------------------------------------
    # LIBRARY hub
    # ------------------------------------------------------------------

    def test_library_hub_has_purpose_label(self) -> None:
        widget = LibraryView()
        self.assertTrue(
            _has_hub_purpose_label(widget),
            "LibraryView (LIBRARY hub) is missing a QLabel with objectName='hub-purpose'",
        )

    def test_library_hub_has_tooltipped_buttons(self) -> None:
        widget = LibraryView()
        count = len(_tooltipped_buttons(widget))
        self.assertGreater(
            count,
            0,
            "LibraryView has no buttons with tooltips",
        )

    def test_library_hub_compact_mode_shortens_button_labels(self) -> None:
        widget = LibraryView()
        widget._apply_density_mode(880)
        self.assertEqual(widget._root_browse_btn.text(), "FOLDER")
        self.assertEqual(widget._artifact_browse_btn.text(), "FILE")
        self.assertEqual(widget._note_save_btn.text(), "SAVE NOTE")

    # ------------------------------------------------------------------
    # SETTINGS hub
    # ------------------------------------------------------------------

    def test_settings_hub_has_purpose_label(self) -> None:
        hub = SettingsHubView(SettingsView(), SettingsDeviceAccountsPanel(), SettingsOperationsPanel())
        self.assertTrue(
            _has_hub_purpose_label(hub),
            "SettingsHubView (SETTINGS hub) is missing a QLabel with objectName='hub-purpose'",
        )

    def test_settings_hub_tabs_have_tooltips(self) -> None:
        hub = SettingsHubView(SettingsView(), SettingsDeviceAccountsPanel(), SettingsOperationsPanel())
        tab_buttons = [
            btn
            for btn in hub.findChildren(QPushButton)
            if btn.text() in {"GENERAL", "CUSTOMIZATION", "PERFORMANCE", "ACCOUNTS", "PLUGINS", "BACKEND STATS", "HELP"}
        ]
        self.assertGreater(len(tab_buttons), 0, "No settings tab buttons found in SettingsHubView")
        for btn in tab_buttons:
            self.assertTrue(
                btn.toolTip().strip(),
                f"Settings tab button missing tooltip (signal: {btn.objectName()!r})",
            )

    def test_settings_hub_tab_buttons_have_min_height(self) -> None:
        hub = SettingsHubView(SettingsView(), SettingsDeviceAccountsPanel(), SettingsOperationsPanel())
        tab_buttons = [
            btn
            for btn in hub.findChildren(QPushButton)
            if btn.text() in {"GENERAL", "CUSTOMIZATION", "PERFORMANCE", "ACCOUNTS", "PLUGINS", "BACKEND STATS", "HELP"}
        ]
        for btn in tab_buttons:
            self.assertGreaterEqual(
                btn.minimumHeight(),
                36,
                f"Settings tab button minimumHeight={btn.minimumHeight()}, expected >=36",
            )

    def test_settings_hub_renders_requested_tab_labels(self) -> None:
        hub = SettingsHubView(SettingsView(), SettingsDeviceAccountsPanel(), SettingsOperationsPanel())
        labels = {btn.text() for btn in hub.findChildren(QPushButton)}
        self.assertTrue({"GENERAL", "CUSTOMIZATION", "PERFORMANCE", "ACCOUNTS", "PLUGINS", "BACKEND STATS", "HELP"}.issubset(labels))

    def test_settings_device_accounts_panel_compact_mode_reflows_and_shortens_actions(self) -> None:
        panel = SettingsDeviceAccountsPanel()
        panel.set_connector_inventory(
            [
                {
                    "id": "gmail",
                    "label": "Gmail",
                    "auth_state": "missing",
                    "auth_kind": "oauth_file_token",
                    "actions_supported": ["connect", "verify", "disconnect"],
                },
                {
                    "id": "spotify",
                    "label": "Spotify",
                    "auth_state": "ready",
                    "auth_kind": "api_key",
                    "actions_supported": ["verify", "disconnect"],
                },
                {
                    "id": "crm",
                    "label": "CRM",
                    "auth_state": "missing",
                    "auth_kind": "provider_secret",
                    "actions_supported": ["verify", "disconnect"],
                },
            ]
        )
        panel.resize(860, 900)
        panel._apply_density_mode(860)
        self.assertEqual(panel._connector_grid_columns(), 1)
        self.assertEqual(panel._connect_btn.text(), "SIGN IN")
