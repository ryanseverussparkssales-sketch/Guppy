"""
Debug console for supported desktop surfaces.

Open from any UI with Ctrl+D.
"""
from __future__ import annotations

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QTabWidget, QVBoxLayout

from ._tabs import EmergencyTab, LogsTab, MemoryTab, StatusTab, VoiceTab
from ._ui import BASE_STYLE, CYAN, make_button


class DebugConsole(QDialog):
    """Debug and emergency console. Pass the calling UI window as parent_win."""

    def __init__(self, parent_win=None):
        super().__init__(parent_win)
        self.setWindowTitle("Debug Console")
        self.setMinimumSize(680, 560)
        self.setStyleSheet(BASE_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        header = QHBoxLayout()
        title = QLabel("Guppy Debug & Emergency Console")
        title.setStyleSheet(f"color: {CYAN}; font-size: 13px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        tabs = QTabWidget()
        tabs.addTab(StatusTab(), "Status")
        tabs.addTab(MemoryTab(), "Memory")
        tabs.addTab(EmergencyTab(parent_win), "Emergency")
        tabs.addTab(VoiceTab(parent_win), "Voice")
        tabs.addTab(LogsTab(), "Logs")
        layout.addWidget(tabs)

        close = make_button("Close")
        close.clicked.connect(self.close)
        close.setFixedWidth(80)
        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(close)
        layout.addLayout(footer)

        QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(self.close)


def open_debug_console(parent_win=None):
    """Open or raise the debug console. Safe to call from any UI."""

    console = DebugConsole(parent_win)
    console.show()
    console.raise_()
    return console
