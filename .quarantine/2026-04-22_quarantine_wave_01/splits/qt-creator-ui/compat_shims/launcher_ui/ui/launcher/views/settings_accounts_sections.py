"""
ui/launcher/views/settings_accounts_sections.py
Shared helpers extracted from settings_device_accounts_panel.py.
"""
from __future__ import annotations

from PySide6.QtWidgets import QLabel

from .. import tokens as T


def mono(text: str, color: str = T.DIM, size: int = T.FS_SMALL, bold: bool = False) -> QLabel:
    """Create a word-wrapped monospace label."""
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {size}pt; letter-spacing: 1px;"
        + (" font-weight: bold;" if bold else "")
    )
    return lbl


def connector_card_style(*, selected: bool, ready: bool, accent: str, wash: str) -> str:
    """Return the stylesheet string for a connector card button."""
    border = accent if selected else (T.GREEN if ready else T.BORDER)
    background = wash if selected else T.BG1
    text_color = T.TEXT if selected or ready else T.DIM
    return (
        f"QPushButton {{ background: {background}; color: {text_color}; border: 1px solid {border};"
        f" border-left: 6px solid {accent}; padding: 10px 12px; text-align: left;"
        f" font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        f"QPushButton:hover {{ border-color: {accent}; color: {T.TEXT}; background: {wash}; }}"
    )


def connector_grid_columns(width: int, viewport_width: int) -> int:
    """Return number of grid columns given effective panel width."""
    effective = max(width, viewport_width)
    if effective <= 900:
        return 1
    if effective <= 1280:
        return 2
    return 3
