from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QPushButton

BG = "#0b0b14"
BG2 = "#0f0f1c"
BORDER = "#1e1e30"
TEXT = "#d0d0e0"
DIM = "#505068"
GREEN = "#22c55e"
YELLOW = "#eab308"
RED = "#ef4444"
CYAN = "#22d3ee"

BASE_STYLE = f"""
    QDialog, QWidget {{ background: {BG}; color: {TEXT}; }}
    QTabWidget::pane {{ border: 1px solid {BORDER}; background: {BG}; }}
    QTabBar::tab {{ background: {BG2}; color: {DIM}; padding: 6px 14px; border: 1px solid {BORDER}; border-bottom: none; }}
    QTabBar::tab:selected {{ color: {TEXT}; background: {BG}; border-bottom: 1px solid {BG}; }}
    QPushButton {{ background: {BG2}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 4px; padding: 5px 12px; }}
    QPushButton:hover {{ border-color: {CYAN}; color: {CYAN}; }}
    QPushButton:pressed {{ background: #1a1a2c; }}
    QLineEdit, QTextEdit {{ background: {BG2}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 3px; padding: 4px; }}
    QComboBox {{ background: {BG2}; color: {TEXT}; border: 1px solid {BORDER}; padding: 4px 8px; }}
    QComboBox QAbstractItemView {{ background: {BG2}; color: {TEXT}; selection-background-color: #1e1e30; }}
    QGroupBox {{ color: {DIM}; border: 1px solid {BORDER}; border-radius: 4px; margin-top: 8px; padding-top: 8px; }}
    QGroupBox::title {{ subcontrol-origin: margin; padding: 0 4px; }}
    QTableWidget {{ background: {BG2}; color: {TEXT}; gridline-color: {BORDER}; border: 1px solid {BORDER}; }}
    QTableWidget QHeaderView::section {{ background: {BG}; color: {DIM}; border: 1px solid {BORDER}; padding: 3px; }}
    QScrollBar:vertical {{ background: {BG}; width: 8px; }}
    QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; }}
"""


def make_button(label: str, color: str = TEXT) -> QPushButton:
    button = QPushButton(label)
    if color != TEXT:
        button.setStyleSheet(f"color: {color}; border-color: {color};")
    return button


def make_label(text: str, color: str = DIM, *, bold: bool = False) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(f"color: {color}; {'font-weight: bold;' if bold else ''}")
    return label


def apply_mono(widget):
    widget.setFont(QFont("Consolas", 9))
    return widget
