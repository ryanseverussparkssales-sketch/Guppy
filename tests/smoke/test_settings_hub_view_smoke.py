import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton
    from ui.launcher.views.settings_device_accounts_panel import SettingsDeviceAccountsPanel
    from ui.launcher.views.settings_hub_view import SettingsHubView
    from ui.launcher.views.settings_operations_panel import SettingsOperationsPanel
    from ui.launcher.views.settings_view import SettingsView
except Exception as exc:  # pragma: no cover
    QApplication = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


@unittest.skipIf(QApplication is None, f"PySide6 import failed: {IMPORT_ERROR}")
class SettingsHubViewSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_settings_hub_exposes_section_ownership_and_embeds_settings_view(self):
        settings_view = SettingsView()
        hub = SettingsHubView(settings_view, SettingsDeviceAccountsPanel(), SettingsOperationsPanel())

        labels = [label.text() for label in hub.findChildren(QLabel)]
        combined = "\n".join(text for text in labels if isinstance(text, str))

        self.assertIn("Settings Hub", combined)
        self.assertIn("CONFIGURATION", combined)
        self.assertIn("DIAGNOSTICS", combined)
        self.assertIn("RECOVERY", combined)
        self.assertIn("CONNECTORS", combined)
        self.assertIn("SYSTEM", combined)
        self.assertIn("TERMINAL", combined)
        self.assertIs(hub._settings_view, settings_view)

    def test_settings_hub_owner_buttons_emit_legacy_lane_signals(self):
        settings_view = SettingsView()
        hub = SettingsHubView(settings_view, SettingsDeviceAccountsPanel(), SettingsOperationsPanel())
        emissions = {
            "diagnostics": 0,
            "recovery": 0,
            "connectors": 0,
            "system": 0,
            "terminal": 0,
        }

        hub.open_diagnostics_requested.connect(lambda: emissions.__setitem__("diagnostics", emissions["diagnostics"] + 1))
        hub.open_recovery_requested.connect(lambda: emissions.__setitem__("recovery", emissions["recovery"] + 1))
        hub.open_connectors_requested.connect(lambda: emissions.__setitem__("connectors", emissions["connectors"] + 1))
        hub.open_system_requested.connect(lambda: emissions.__setitem__("system", emissions["system"] + 1))
        hub.open_terminal_requested.connect(lambda: emissions.__setitem__("terminal", emissions["terminal"] + 1))

        buttons = [button for button in hub.findChildren(QPushButton) if button.text() == "FOCUS SECTION"]

        self.assertEqual(len(buttons), 5)
        for button in buttons:
            button.click()

        self.assertEqual(emissions["diagnostics"], 1)
        self.assertEqual(emissions["recovery"], 1)
        self.assertEqual(emissions["connectors"], 1)
        self.assertEqual(emissions["system"], 1)
        self.assertEqual(emissions["terminal"], 1)
