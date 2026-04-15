"""
ui/launcher/stylesheet.py
Global QSS for the launcher shell.
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
QFrame {{
    background: transparent;
}}
QComboBox {{
    background-color: {T.BG0};
    color: {T.TEXT};
    border: 1px solid {T.BORDER};
    border-radius: 12px;
    padding: 5px 10px;
    font-family: "{T.FF_BODY}";
    font-size: {T.FS_LABEL}pt;
    min-height: 28px;
}}
QComboBox:hover {{ border-color: {T.PRIMARY}; }}
QComboBox:focus {{ border-color: {T.PRIMARY}; background-color: #ffffff; }}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox::down-arrow {{
    image: none;
    width: 0; height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid {T.PRIMARY};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {T.BG0};
    color: {T.TEXT};
    border: 1px solid {T.BORDER};
    selection-background-color: {T.BG1};
    selection-color: {T.TEXT};
    padding: 4px;
}}
QLineEdit {{
    background-color: {T.BG0};
    color: {T.TEXT};
    border: 1px solid {T.BORDER};
    border-radius: 14px;
    padding: 5px 10px;
    font-family: "{T.FF_BODY}";
    font-size: {T.FS_LABEL}pt;
    min-height: 28px;
}}
QLineEdit:focus {{ border-color: {T.PRIMARY}; background-color: #ffffff; }}
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {T.BORDER};
    border-radius: 4px;
    min-height: 22px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ height: 0; }}
QPushButton {{
    background-color: {T.BG0};
    color: {T.TEXT};
    border: 1px solid {T.BORDER};
    border-radius: 14px;
    padding: 6px 14px;
    font-family: "{T.FF_BODY}";
    font-size: {T.FS_SMALL}pt;
    min-height: 28px;
}}
QPushButton:hover {{
    background-color: rgba(255, 107, 61, 0.08);
    border-color: {T.PRIMARY};
}}
QPushButton:focus, QPushButton:focus-visible {{
    background-color: #ffffff;
    border: 2px solid {T.PRIMARY};
    border-radius: 14px;
    padding: 5px 13px;
}}
QPushButton:pressed {{
    background-color: rgba(255, 107, 61, 0.16);
}}
QPushButton:disabled {{
    color: {T.BORDER};
    border-color: {T.BORDER};
    background-color: rgba(255, 250, 243, 0.45);
}}
QCheckBox {{
    color: {T.TEXT};
    spacing: 8px;
    font-size: {T.FS_BODY}pt;
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    background-color: {T.BG0};
    border: 1px solid {T.BORDER};
    border-radius: 7px;
}}
QCheckBox::indicator:checked {{
    background-color: {T.PRIMARY};
    border-color: {T.PRIMARY};
}}
QSplitter::handle {{
    background-color: rgba(205, 181, 154, 0.35);
    width: 1px;
}}
QToolTip {{
    background-color: {T.BG0};
    color: {T.TEXT};
    border: 1px solid {T.BORDER};
    padding: 5px 8px;
    font-size: {T.FS_SMALL}pt;
}}
"""
