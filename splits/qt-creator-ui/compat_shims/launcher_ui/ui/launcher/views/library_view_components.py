from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from .. import tokens as T


def mono_label(text: str, color: str = T.DIM, size: int = T.FS_SMALL, bold: bool = False) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {size}pt; letter-spacing: 1px;"
        + ("font-weight: bold;" if bold else "")
    )
    return label


def body_label(text: str, *, color: str = T.DIM, size: int = T.FS_SMALL) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(f"color: {color}; font-family: '{T.FF_BODY}'; font-size: {size}pt;")
    return label


def build_summary_card(title: str, text: str) -> tuple[QFrame, QLabel]:
    frame = QFrame()
    frame.setStyleSheet(
        "QFrame { background-color: rgba(255,255,255,0.68); border: 1px solid rgba(214,197,174,0.48); border-radius: 24px; }"
    )
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(8)
    layout.addWidget(mono_label(title, T.PRIMARY, T.FS_TINY, True))
    copy = body_label(text)
    layout.addWidget(copy)
    return frame, copy
