"""
ui/launcher/components/agent_card.py
A status card for a single AI agent (Guppy / Merlin / Council).
Shows: coloured left-accent strip, name, status badge, last-seen, neural load %.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import tokens as T


class AgentCard(QFrame):
    def __init__(
        self,
        name: str,
        accent: str = T.PRIMARY,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._name = name
        self._accent = accent
        self._online = True

        self.setObjectName("agent_card")
        self.setStyleSheet(
            f"QFrame#agent_card {{"
            f"  background-color: {T.BG1};"
            f"  border-left: 2px solid {accent};"
            f"  border-top: none; border-right: none; border-bottom: none;"
            f"}}"
        )

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(12)

        # ── Left: name + status ───────────────────────────────────────────────
        info = QVBoxLayout()
        info.setSpacing(4)

        self._name_lbl = QLabel(name)
        self._name_lbl.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_HEAD}';"
            f"font-size: {T.FS_TITLE}pt; font-weight: bold; letter-spacing: 2px;"
        )

        badge_row = QHBoxLayout()
        badge_row.setSpacing(10)
        badge_row.setContentsMargins(0, 0, 0, 0)

        self._badge = QLabel("● READY")
        self._badge.setStyleSheet(
            f"color: {T.GREEN}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_SMALL}pt; letter-spacing: 1px;"
        )

        self._last_seen = QLabel("LAST SEEN: NOW")
        self._last_seen.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )

        badge_row.addWidget(self._badge)
        badge_row.addWidget(self._last_seen)
        badge_row.addStretch()

        info.addWidget(self._name_lbl)
        info.addLayout(badge_row)

        root.addLayout(info)
        root.addStretch()

        # ── Right: neural load or initialize button ───────────────────────────
        self._load_col = QVBoxLayout()
        self._load_col.setSpacing(2)
        self._load_col.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._load_label_lbl = QLabel("NEURAL LOAD")
        self._load_label_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        self._load_val = QLabel("—")
        self._load_val.setStyleSheet(
            f"color: {accent}; font-family: '{T.FF_HEAD}';"
            f"font-size: {T.FS_TITLE}pt; font-weight: bold;"
        )
        self._load_val.setAlignment(Qt.AlignmentFlag.AlignRight)

        self._btn_init = QPushButton("INITIALIZE")
        self._btn_init.setVisible(False)
        self._btn_init.setEnabled(False)
        self._btn_init.setToolTip("Launcher restart action is not wired yet. Use hub/operator controls.")
        self._btn_init.setStyleSheet(
            f"color: {T.ERROR}; border: 1px solid {T.ERROR};"
            f"font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; padding: 3px 10px;"
        )

        self._load_col.addWidget(self._load_label_lbl,
                                 alignment=Qt.AlignmentFlag.AlignRight)
        self._load_col.addWidget(self._load_val,
                                 alignment=Qt.AlignmentFlag.AlignRight)
        self._load_col.addWidget(self._btn_init,
                                 alignment=Qt.AlignmentFlag.AlignRight)

        root.addLayout(self._load_col)

    # ── Public API ────────────────────────────────────────────────────────────
    def update_status(
        self,
        online: bool,
        last_seen: str = "NOW",
        load_pct: float | None = None,
    ) -> None:
        self._online = online
        if online:
            self._badge.setText("● READY")
            self._badge.setStyleSheet(
                f"color: {T.GREEN}; font-family: '{T.FF_MONO}';"
                f"font-size: {T.FS_SMALL}pt; letter-spacing: 1px;"
            )
            self._load_label_lbl.setVisible(True)
            self._load_val.setVisible(True)
            self._btn_init.setVisible(False)
            self._load_val.setText(
                f"{load_pct:.0f}%" if load_pct is not None else "—"
            )
        else:
            self._badge.setText("● OFFLINE")
            self._badge.setStyleSheet(
                f"color: {T.ERROR}; font-family: '{T.FF_MONO}';"
                f"font-size: {T.FS_SMALL}pt; letter-spacing: 1px;"
            )
            self._load_label_lbl.setVisible(False)
            self._load_val.setVisible(False)
            self._btn_init.setVisible(True)

        self._last_seen.setText(f"LAST SEEN: {last_seen.upper()}")
        self.setWindowOpacity(1.0 if online else 0.7)
