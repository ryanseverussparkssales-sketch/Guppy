"""
ui/launcher/stylesheet.py
Global QSS for the launcher shell.
"""

from . import tokens as T

# Import Atoll Editorial fonts (Noto Serif, Manrope, JetBrains Mono)
FONTS = """
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif:ital@0;1&family=Manrope:wght@400;500;600;700&display=swap');
"""

SHEET = f"""
* {{
    outline: none;
}}
QMainWindow, QWidget {{
    background-color: {T.SURFACE_BASE};
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
    background-color: {T.SURFACE_ELEVATED};
    color: {T.TEXT};
    border: 2px solid {T.BORDER_SOFT};
    border-radius: 4px;
    padding: 6px 12px;
    font-family: "{T.FF_BODY}";
    font-size: {T.FS_LABEL}pt;
    min-height: 32px;
}}
QComboBox:hover {{ border-color: {T.ACCENT_TEAL}; background-color: rgba(0, 0, 0, 0.03); }}
QComboBox:focus {{ border-color: {T.ACCENT_TEAL}; background-color: {T.WHITE}; }}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox::down-arrow {{
    image: none;
    width: 0; height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid {T.ACCENT_TEAL};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {T.SURFACE_ELEVATED};
    color: {T.TEXT};
    border: 1px solid {T.BORDER_STRONG};
    selection-background-color: {T.BG1};
    selection-color: {T.TEXT};
    padding: 4px;
}}
QLineEdit {{
    background-color: {T.SURFACE_ELEVATED};
    color: {T.TEXT};
    border: 2px solid {T.BORDER_SOFT};
    border-radius: 4px;
    padding: 6px 12px;
    font-family: "{T.FF_BODY}";
    font-size: {T.FS_LABEL}pt;
    min-height: 32px;
}}
QLineEdit:focus {{ border-color: {T.ACCENT_TEAL}; background-color: {T.WHITE}; }}
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
    background: rgba(106,102,95,0.45);
    border-radius: 4px;
    min-height: 22px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ height: 0; }}
QPushButton {{
    background-color: {T.SURFACE_ELEVATED};
    color: {T.TEXT};
    border: 2px solid {T.BORDER_SOFT};
    border-radius: 4px;
    padding: 8px 16px;
    font-family: "{T.FF_BODY}";
    font-size: {T.FS_SMALL}pt;
    min-height: 32px;
}}
QPushButton:hover {{
    background-color: rgba(0, 0, 0, 0.05);
    border-color: {T.ACCENT_TEAL};
}}
QPushButton:focus, QPushButton:focus-visible {{
    background-color: {T.WHITE};
    border: 2px solid {T.ACCENT_TEAL};
    border-radius: 4px;
    padding: 8px 16px;
}}
QPushButton:pressed {{
    background-color: rgba(0, 106, 106, 0.1);
    border-color: {T.ACCENT_TEAL};
}}
QPushButton:disabled {{
    color: {T.BORDER_SOFT};
    border-color: {T.BORDER_SOFT};
    background-color: {T.SURFACE_ELEVATED_45};
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
    border: 1px solid {T.BORDER_SOFT};
    border-radius: 7px;
}}
QCheckBox::indicator:checked {{
    background-color: {T.ACCENT_TEAL};
    border-color: {T.ACCENT_TEAL};
}}
QSplitter::handle {{
    background-color: {T.BORDER_MID_35};
    width: 1px;
}}
QToolTip {{
    background-color: {T.SURFACE_ELEVATED};
    color: {T.TEXT};
    border: 1px solid {T.BORDER_STRONG};
    padding: 5px 8px;
    font-size: {T.FS_SMALL}pt;
}}
QTextBrowser, QPlainTextEdit {{
    background-color: {T.SURFACE_ELEVATED_72};
    color: {T.TEXT};
    border: 1px solid {T.BORDER_SOFT_58};
    border-radius: 18px;
}}
QLabel#hub-purpose {{
    font-family: "{T.FONT_SERIF}", "{T.FF_HEAD}", serif;
    font-size: {T.FS_BODY}pt;
    font-style: italic;
    color: {T.DIM};
    padding: 2px 0px 6px 0px;
}}
"""
