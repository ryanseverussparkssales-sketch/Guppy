import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from ui.launcher.components.sidebar import Sidebar
    from ui.launcher.components.topbar import TopBar
except Exception as exc:  # pragma: no cover
    QApplication = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


@unittest.skipIf(QApplication is None, f"PySide6 import failed: {IMPORT_ERROR}")
class LauncherNavChromeSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_sidebar_visible_hubs_match_five_hub_nav(self):
        sidebar = Sidebar()

        visible_labels = [item._label.text() for item in sidebar._visible_items]

        self.assertEqual(visible_labels, ["HOME", "MODELS", "TOOLS", "LIBRARY", "SETTINGS"])
        hidden_labels = [item._label.text() for item in sidebar._items if item not in sidebar._visible_items]
        self.assertIn("SPACES", hidden_labels)
        self.assertIn("LOCAL LLM", hidden_labels)
        self.assertIn("VOICE", hidden_labels)

    def test_topbar_visible_hubs_match_five_hub_nav_and_workspace_button_routes_to_manager(self):
        topbar = TopBar()
        requested: list[int] = []
        topbar.nav_requested.connect(requested.append)

        visible_nav = [btn.text() for btn in topbar._nav_btns if not btn.isHidden()]

        self.assertEqual(visible_nav, ["HOME", "MODELS", "TOOLS", "LIBRARY", "SETTINGS"])
        self.assertIn("WORKSPACES", [btn.text() for btn in topbar._nav_btns])
        self.assertEqual(topbar._workspace_nav_btn.text(), "SPACES")
        self.assertIn("MAIN MODEL:", topbar._summary_primary_lbl.full_text())

        topbar._workspace_nav_btn.click()

        self.assertEqual(requested, [1])

    def test_topbar_compacts_live_nav_when_shown_at_small_width(self):
        topbar = TopBar()
        topbar._apply_density_mode(980)

        visible_nav = [btn.text() for btn in topbar._nav_btns if not btn.isHidden()]

        self.assertEqual(visible_nav, [])
        self.assertFalse(topbar._search.isVisible())
        self.assertIn("MAIN MODEL:", topbar._summary_primary_lbl.full_text())
