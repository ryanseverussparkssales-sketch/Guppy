"""
ui/launcher/views/models_panel_support.py
Card and column-header widget helpers extracted from models_sections.py.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .. import tokens as T


def _fmt_size(num_bytes: int) -> str:
    if not num_bytes:
        return "-"
    gb = num_bytes / (1024 ** 3)
    return f"{gb:.1f} GB" if gb >= 1 else f"{num_bytes / (1024 ** 2):.0f} MB"


def _model_use_hint(name: str, display: str, tier: str, context: str = "", note: str = "") -> str:
    joined = " ".join(str(part or "").lower() for part in (name, display, context, note))
    if "haiku" in joined or "fast" in joined:
        return "Good for quick everyday help and lighter tasks."
    if "sonnet" in joined:
        return "Good default for balanced quality and speed."
    if "opus" in joined:
        return "Good for the hardest writing and reasoning work."
    if "vault" in joined:
        return "Good for document lookup and extraction work."
    if "code" in joined or "coder" in joined or "merlin" in joined:
        return "Good for coding, repo work, and technical tasks."
    if "teach" in joined:
        return "Good for guided explanations and teaching-style help."
    if "small" in joined or "1b" in joined or "3b" in joined:
        return "Good for lighter local tasks and quick experiments."
    if "30b" in joined or "32b" in joined or "24b" in joined:
        return "Good for heavier work when you can trade speed for depth."
    return "Use this when it best fits the work you are doing."


class _ModelCard(QFrame):
    set_active = Signal(str)

    def __init__(
        self,
        name: str,
        display: str,
        tier: str,
        context: str = "-",
        note: str = "",
        size_bytes: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._model_name = name
        self._tier = tier
        self._is_active = False
        self._is_recommended = False
        self._search_text = " ".join(
            part.strip().lower()
            for part in [name, display, tier, context, note]
            if isinstance(part, str) and part.strip()
        )
        self.setObjectName("model_card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)
        top = QHBoxLayout()
        self._name_lbl = QLabel(display)
        self._name_lbl.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_HEAD}'; font-size: {T.FS_LABEL}pt; font-weight: bold;"
        )
        self._badge_lbl = QLabel(tier)
        top.addWidget(self._name_lbl)
        top.addStretch()
        top.addWidget(self._badge_lbl)
        layout.addLayout(top)
        self._id_lbl = QLabel(name)
        self._id_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
        )
        layout.addWidget(self._id_lbl)
        self._use_lbl = QLabel(_model_use_hint(name, display, tier, context, note))
        self._use_lbl.setWordWrap(True)
        self._use_lbl.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;"
        )
        layout.addWidget(self._use_lbl)
        meta = QHBoxLayout()
        meta.setSpacing(12)
        for text in (([_fmt_size(size_bytes)] if size_bytes else []) + ([context] if context else [])):
            chip = QLabel(text)
            chip.setStyleSheet(
                f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
            )
            meta.addWidget(chip)
        meta.addStretch()
        layout.addLayout(meta)
        layout.addSpacing(10)
        act = QHBoxLayout()
        self._status_lbl = QLabel("AVAILABLE")
        self._set_btn = QPushButton("USE THIS SESSION")
        self._set_btn.setFixedHeight(28)
        self._set_btn.setToolTip("Use this model for the current chat session")
        self._set_btn.clicked.connect(lambda: self.set_active.emit(self._model_name))
        act.addWidget(self._status_lbl)
        act.addStretch()
        act.addWidget(self._set_btn)
        layout.addLayout(act)
        self._apply_card_style()

    def _apply_card_style(self) -> None:
        border = T.ACCENT_ORANGE if self._is_recommended else T.BORDER_SOFT
        background = T.BG0 if self._is_recommended else T.BG1
        self.setStyleSheet(
            f"QFrame#model_card {{ background-color: {background}; border: 1px solid {border}; border-radius: 4px; }}"
        )
        badge_text = f"{self._tier} PICK" if self._is_recommended else self._tier
        badge_color = T.ACCENT_TEAL if self._tier == "LOCAL" else T.ACCENT_ORANGE
        badge_border = T.ACCENT_ORANGE if self._is_recommended else badge_color
        badge_fill = T.BG0 if self._is_recommended else "transparent"
        self._badge_lbl.setText(badge_text)
        self._badge_lbl.setStyleSheet(
            f"color: {badge_border}; background: {badge_fill}; font-family: '{T.FF_MONO}'; "
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px; padding: 1px 4px; border: 1px solid {badge_border}; border-radius: 3px;"
        )
        self._name_lbl.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_HEAD}'; font-size: {T.FS_LABEL}pt; "
            f"font-weight: {'800' if self._is_recommended else 'bold'};"
        )
        self._use_lbl.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt; "
            f"font-weight: {'bold' if self._is_recommended else 'normal'};"
        )
        status_color = T.ACCENT_ORANGE if self._is_active else T.STATUS_SUCCESS
        self._status_lbl.setStyleSheet(
            f"color: {status_color}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        button_border = T.ACCENT_ORANGE if self._is_recommended else T.BORDER_SOFT
        button_bg = T.BG0 if self._is_recommended else T.BG1
        button_color = T.ACCENT_ORANGE if self._is_recommended else T.TEXT
        self._set_btn.setStyleSheet(
            f"QPushButton {{ background-color: {button_bg}; color: {button_color}; border: 1px solid {button_border}; border-radius: 4px;"
            f"padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:disabled {{ color: {T.DIM}; border-color: {T.BORDER_SOFT}; }}"
        )

    def set_recommended(self, recommended: bool) -> None:
        self._is_recommended = recommended
        self._apply_card_style()

    def mark_active(self, active: bool) -> None:
        self._is_active = active
        self._status_lbl.setText("IN USE" if active else "AVAILABLE")
        self._set_btn.setEnabled(not active)
        self._apply_card_style()

    def matches_query(self, query: str) -> bool:
        needle = (query or "").strip().lower()
        return not needle or needle in self._search_text


class _ColumnHeader(QLabel):
    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; "
            f"letter-spacing: 2px; border-bottom: 1px solid {T.BORDER}; padding-bottom: 4px;"
        )
