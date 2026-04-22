from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from .. import tokens as T


def _label(text: str, color: str = T.DIM, size: int = T.FS_TINY, bold: bool = False) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}';"
        f"font-size: {size}pt; letter-spacing: 1px;"
        + ("font-weight: bold;" if bold else "")
    )
    return lbl


def _action_button(
    text: str,
    *,
    color: str,
    hover_border: str,
    hover_color: str | None = None,
) -> QPushButton:
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setFixedHeight(20)
    button.setStyleSheet(
        f"QPushButton {{ background: rgba(255,255,255,0.92); color: {color}; border: 1px solid rgba(214,197,174,0.44);"
        f" border-radius: 10px; padding: 0 8px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        f"QPushButton:hover {{ border-color: {hover_border};"
        + (f" color: {hover_color};" if hover_color else "")
        + " background: #ffffff; }}"
    )
    return button


def clear_active_context_row(row: QHBoxLayout) -> None:
    while row.count():
        row_item = row.takeAt(0)
        if row_item is None:
            continue
        widget = row_item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()


def populate_active_context_row(
    row: QHBoxLayout,
    *,
    items: list[dict[str, str]],
    primary_title: str,
    default_title: str,
    previewed_title: str,
    on_toggle_preview: Callable[[str], None],
    on_focus: Callable[[str], None],
    on_open_library: Callable[[str], None],
    on_remove: Callable[[str], None],
) -> None:
    for item in items:
        title = item["title"]
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background-color: rgba(255,250,243,0.92); border: 1px solid rgba(214,197,174,0.52); border-radius: 14px; }"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        top = QHBoxLayout()
        top.setSpacing(6)
        if title == primary_title:
            top.addWidget(_label("PRIMARY", T.PRIMARY, T.FS_TINY, True))
        if title == default_title:
            top.addWidget(_label("DEFAULT", T.SECONDARY, T.FS_TINY, True))
        top.addWidget(_label(item["kind"], T.SECONDARY, T.FS_TINY, True))
        if item.get("source_label"):
            top.addWidget(
                _label(
                    str(item.get("source_label") or "SAVED SOURCE").upper(),
                    T.PRIMARY,
                    T.FS_TINY,
                    True,
                )
            )
        top.addStretch()

        preview_btn = _action_button(
            "HIDE" if title == previewed_title else "PREVIEW",
            color=T.DIM,
            hover_border="rgba(205,181,154,0.62)",
        )
        preview_btn.clicked.connect(lambda _=False, current=title: on_toggle_preview(current))
        top.addWidget(preview_btn)

        if title != primary_title:
            focus_btn = _action_button(
            "MAKE PRIMARY",
            color=T.ACCENT_TEAL,
            hover_border="rgba(0,106,106,0.42)",
        )
            focus_btn.clicked.connect(lambda _=False, current=title: on_focus(current))
            top.addWidget(focus_btn)

        if title == primary_title:
            library_btn = _action_button(
                "OPEN IN LIBRARY",
                color=T.ACCENT_TEAL,
                hover_border="rgba(0,106,106,0.42)",
            )
            library_btn.clicked.connect(lambda _=False, current=title: on_open_library(current))
            top.addWidget(library_btn)

        remove_btn = _action_button(
            "REMOVE",
            color=T.DIM,
            hover_border="rgba(255,61,0,0.42)",
            hover_color=T.STATUS_ERROR,
        )
        remove_btn.clicked.connect(lambda _=False, current=title: on_remove(current))
        top.addWidget(remove_btn)

        layout.addLayout(top)

        title_lbl = QLabel(title)
        title_lbl.setWordWrap(True)
        title_lbl.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt; font-weight: 600;"
        )
        layout.addWidget(title_lbl)

        detail = str(item.get("detail", "") or "")
        if detail:
            detail_lbl = QLabel(detail)
            detail_lbl.setWordWrap(True)
            detail_lbl.setToolTip(detail)
            detail_lbl.setStyleSheet(
                f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_TINY}pt;"
            )
            detail_lbl.setVisible(title == previewed_title)
            layout.addWidget(detail_lbl)

        row.addWidget(card)
    row.addStretch()
