"""Hub window shell helpers (system tray integration)."""
from __future__ import annotations

from typing import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .theme_config import ACNT, TEXT

_ROOT = Path(__file__).resolve().parents[3]
_DESKTOP_G_LOGO = _ROOT / "assets" / "desktop" / "guppy_launcher_icon.png"


def _tray_icon() -> QIcon:
    if _DESKTOP_G_LOGO.exists():
        icon = QIcon(str(_DESKTOP_G_LOGO))
        if not icon.isNull():
            return icon

    pixmap = QPixmap(16, 16)
    pixmap.fill(QColor(ACNT))
    painter = QPainter(pixmap)
    painter.setPen(QPen(QColor(TEXT), 1))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, ">>")
    painter.end()
    return QIcon(pixmap)


class SystemTray(QSystemTrayIcon):
    def __init__(self, window, app: QApplication, load_settings: Callable[[], dict]):
        super().__init__(_tray_icon(), app)
        self._window = window
        self._app = app
        self._load_settings = load_settings
        self._menu = QMenu()
        self.setToolTip("Omnissiah Machine Spirit")
        self._setup_menu()
        self.activated.connect(self._on_activated)

    def _setup_menu(self):
        self._menu.clear()

        launch_guppy_action = QAction("Launch Guppy", self)
        launch_guppy_action.triggered.connect(lambda: self._window._on_launch("guppy"))
        self._menu.addAction(launch_guppy_action)

        self._menu.addSeparator()

        show_action = QAction("Show Omnissiah", self)
        show_action.triggered.connect(self._window.show)
        self._menu.addAction(show_action)

        hide_action = QAction("Hide Omnissiah", self)
        hide_action.triggered.connect(self._window.hide)
        self._menu.addAction(hide_action)

        self._menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._app.quit)
        self._menu.addAction(quit_action)

        self.setContextMenu(self._menu)

    def _on_activated(self, reason):
        self._setup_menu()
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self._window.isVisible():
                self._window.hide()
            else:
                self._window.show()
