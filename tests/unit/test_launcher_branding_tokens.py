import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QLabel
    from ui.launcher import tokens as T
    from ui.launcher.components.sidebar import Sidebar
    from ui.launcher.components.status_panel import StatusPanel
    from ui.launcher.components.topbar import TopBar
except Exception as exc:  # pragma: no cover
    QApplication = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


def _hex_to_rgb(value: str) -> tuple[float, float, float]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _linear_channel(channel: float) -> float:
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def _relative_luminance(value: str) -> float:
    red, green, blue = (_linear_channel(channel) for channel in _hex_to_rgb(value))
    return (0.2126 * red) + (0.7152 * green) + (0.0722 * blue)


def _contrast_ratio(foreground: str, background: str) -> float:
    lighter, darker = sorted(
        (_relative_luminance(foreground), _relative_luminance(background)),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


@unittest.skipIf(QApplication is None, f"PySide6 import failed: {IMPORT_ERROR}")
class LauncherBrandingTokenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_text_roles_meet_contrast_targets_on_warm_sand_surfaces(self) -> None:
        self.assertGreaterEqual(_contrast_ratio(T.TEXT, T.SURFACE_BASE), 7.0)
        self.assertGreaterEqual(_contrast_ratio(T.DIM, T.SURFACE_BASE), 4.5)
        self.assertGreaterEqual(_contrast_ratio(T.ACCENT_TEAL_TEXT, T.SAND_1), 4.5)
        self.assertGreaterEqual(_contrast_ratio(T.PRIMARY_DIM, T.SAND_1), 4.5)
        self.assertGreaterEqual(_contrast_ratio(T.ACCENT_ORANGE_TEXT, T.SAND_1), 4.5)

    def test_topbar_shells_use_high_opacity_readability_surfaces(self) -> None:
        topbar = TopBar()

        self.assertIn(T.SURFACE_ELEVATED_92, topbar._workspace_shell.styleSheet())
        self.assertIn(T.SURFACE_ELEVATED_92, topbar._summary_shell.styleSheet())
        self.assertIn(T.SURFACE_ELEVATED_88, topbar.findChild(type(topbar._workspace_shell), "topbar_system_shell").styleSheet())

    def test_sidebar_branding_uses_chip_backed_deck_label_and_deeper_teal(self) -> None:
        sidebar = Sidebar()
        first_active = sidebar._visible_items[0]

        self.assertIn("background-color", sidebar._deck.styleSheet())
        self.assertIn(T.ACCENT_TEAL_TEXT, sidebar._g_mark.styleSheet())
        sidebar.set_active(0)
        self.assertIn(T.ACCENT_TEAL_TEXT, first_active._btn.styleSheet())

    def test_status_panel_headers_and_media_labels_use_contrast_safe_styles(self) -> None:
        panel = StatusPanel()
        labels = {
            label.text(): label
            for label in panel.findChildren(QLabel)
        }

        self.assertIn(T.PRIMARY_DIM, labels["UTILITIES"].styleSheet())
        self.assertIn(T.PRIMARY_DIM, labels["MORE ACTIONS"].styleSheet())
        self.assertIn(T.PRIMARY_DIM, labels["OPTIONAL SPACES"].styleSheet())
        self.assertIn(T.SURFACE_ELEVATED_92, panel._media_title_lbl.styleSheet())
        self.assertIn(T.SURFACE_ELEVATED_88, panel._media_subtitle_lbl.styleSheet())


if __name__ == "__main__":
    unittest.main()
