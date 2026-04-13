"""
guppy_launcher.py
Unified OBSIDIAN / COMMAND_INTERFACE entry point.
Launches the PySide6 multi-surface launcher in place of the separate
guppy_ui.py / merlin_ui.py / council_ui.py windows.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from ui.launcher import LauncherWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Guppy AI")
    app.setApplicationDisplayName("COMMAND_INTERFACE")
    app.setApplicationVersion("5.0")

    # High-DPI
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    window = LauncherWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
