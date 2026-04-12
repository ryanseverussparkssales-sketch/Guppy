from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem
from guppy_theme import SHARED


class CommandPaletteDialog(QDialog):
    def __init__(self, commands, parent=None):
        super().__init__(parent)
        self._commands = list(commands or [])
        self.setWindowTitle("Command Palette")
        self.setModal(True)
        self.resize(560, 380)
        self.setStyleSheet(
            "QDialog{background:#090c14;color:#c9d3e6;}"
            f"QLineEdit{{background:#101522;color:#d8e4ff;border:1px solid #2c3852;border-radius:{SHARED.panel_radius}px;padding:6px;}}"
            f"QListWidget{{background:#0b101a;color:#c9d3e6;border:1px solid #1d283b;border-radius:{SHARED.panel_radius}px;}}"
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(SHARED.spacing_md, SHARED.spacing_md, SHARED.spacing_md, SHARED.spacing_md)
        lay.setSpacing(SHARED.spacing_sm)

        self._filter = QLineEdit()
        self._filter.setPlaceholderText("Type a command...")
        self._filter.textChanged.connect(self._refresh)
        lay.addWidget(self._filter)

        self._list = QListWidget()
        self._list.setFont(QFont(SHARED.font_family_mono, SHARED.font_size))
        self._list.itemActivated.connect(self._activate_item)
        lay.addWidget(self._list)

        self._refresh()
        self._filter.setFocus()

    def _refresh(self):
        query = self._filter.text().strip().lower()
        self._list.clear()
        for cmd in self._commands:
            name = str(cmd.get("name", "")).strip()
            if not name:
                continue
            if query and query not in name.lower():
                continue
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, cmd)
            self._list.addItem(item)
        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def _activate_item(self, item):
        cmd = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if isinstance(cmd, dict) and callable(cmd.get("action")):
            cmd["action"]()
        self.accept()
