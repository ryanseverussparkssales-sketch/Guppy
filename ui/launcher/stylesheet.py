"""
ui/launcher/stylesheet.py
Central QSS stylesheet for the OBSIDIAN launcher, built from design tokens.
Import SHEET and pass it to QApplication.setStyleSheet().
"""

from . import tokens as T

SHEET = f"""
* {{
    outline: none;
}}
QMainWindow, QWidget {{
    background-color: {T.BG};
    color: {T.TEXT};
    font-family: "{T.FF_BODY}";
    font-size: {T.FS_BODY}pt;
    border: none;
}}
QLabel {{
    background: transparent;
    color: {T.TEXT};
    border: none;
}}
QComboBox {{
    background-color: {T.BG0};
    color: {T.PRIMARY};
    border: 1px solid {T.BORDER};
    padding: 3px 8px;
    font-family: "{T.FF_MONO}";
    font-size: {T.FS_LABEL}pt;
    min-height: 26px;
}}
QComboBox:hover {{ border-color: {T.DIM}; }}
QComboBox:focus {{ border-color: {T.PRIMARY}; }}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox::down-arrow {{
    image: none;
    width: 0; height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {T.PRIMARY};
    margin-right: 6px;
}}
QComboBox QAbstractItemView {{
    background-color: {T.BG1};
    color: {T.TEXT};
    border: 1px solid {T.BORDER};
    selection-background-color: {T.BG3};
    selection-color: {T.PRIMARY};
    padding: 2px;
}}
QLineEdit {{
    background-color: {T.BG0};
    color: {T.PRIMARY};
    border: 1px solid {T.BORDER};
    padding: 3px 8px;
    font-family: "{T.FF_MONO}";
    font-size: {T.FS_LABEL}pt;
    min-height: 26px;
}}
QLineEdit:focus {{ border-color: {T.PRIMARY}; }}
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: {T.BG0};
    width: 4px;
    margin: 0;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {T.BORDER};
    border-radius: 2px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ height: 0; }}
QPushButton {{
    background-color: transparent;
    color: {T.PRIMARY};
    border: 1px solid {T.PRIMARY};
    padding: 4px 14px;
    font-family: "{T.FF_MONO}";
    font-size: {T.FS_SMALL}pt;
    letter-spacing: 1px;
    min-height: 26px;
}}
QPushButton:hover    {{ background-color: rgba(242,202,80,0.12); }}
QPushButton:pressed  {{ background-color: rgba(242,202,80,0.22); }}
QPushButton:disabled {{ color: {T.BORDER}; border-color: {T.BORDER}; }}
QCheckBox {{
    color: {T.TEXT};
    spacing: 8px;
    font-size: {T.FS_BODY}pt;
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    background-color: {T.BG3};
    border: 1px solid {T.BORDER};
}}
QCheckBox::indicator:checked {{
    background-color: {T.PRIMARY};
    border-color: {T.PRIMARY};
}}
QSplitter::handle {{ background-color: {T.BORDER}; width: 1px; }}
QToolTip {{
    background-color: {T.BG1};
    color: {T.TEXT};
    border: 1px solid {T.BORDER};
    padding: 4px 8px;
    font-size: {T.FS_SMALL}pt;
}}
"""
