from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .. import tokens as T


def _label(text: str, color: str = T.DIM, size: int = T.FS_TINY, bold: bool = False) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}';"
        f"font-size: {size}pt; letter-spacing: 1px;"
        + ("font-weight: bold;" if bold else "")
    )
    return lbl


def _reply_action_button(icon_label: str, *, color: str, hover_border: str, tooltip: str) -> QPushButton:
    button = QPushButton(icon_label)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setToolTip(tooltip)
    button.setFixedSize(28, 28)
    button.setStyleSheet(
        f"QPushButton {{ background: rgba(255,255,255,0.92); color: {color}; border: 1px solid rgba(214,197,174,0.44);"
        f" border-radius: 9px; padding: 0; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        f"QPushButton:hover {{ border-color: {hover_border}; background: #ffffff; }}"
    )
    return button


def _build_system_row(text: str) -> QWidget:
    row_host = QWidget()
    row = QHBoxLayout(row_host)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(0)

    pill = QLabel(text)
    pill.setWordWrap(True)
    pill.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    pill.setStyleSheet(
        f"color: {T.DIM}; background-color: rgba(244,239,231,0.84); border: 1px solid rgba(214,197,174,0.62);"
        f"border-radius: 14px; padding: 6px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
    )
    row.addStretch()
    row.addWidget(pill)
    row.addStretch()
    return row_host


def _build_user_body(text: str, *, bubble_fg: str) -> QLabel:
    body = QLabel(text)
    body.setWordWrap(True)
    body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    body.setStyleSheet(
        f"color: {bubble_fg}; background: transparent; border: none;"
        f"font-family: '{T.FF_BODY}'; font-size: {T.FS_LABEL}pt; line-height: 1.4em;"
    )
    return body


def _build_assistant_body(text: str, *, bubble_fg: str) -> QTextBrowser:
    body = QTextBrowser()
    body.setOpenExternalLinks(False)
    body.setReadOnly(True)
    body.setUndoRedoEnabled(False)
    body.setMarkdown(text)
    body.setFrameStyle(0)
    body.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    body.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    body.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
    body.setStyleSheet(
        f"QTextBrowser {{ background: transparent; color: {bubble_fg}; border: none;"
        f" font-family: '{T.FF_BODY}'; font-size: {T.FS_LABEL}pt; line-height: 1.4em; padding: 0; }}"
    )
    body.document().setDocumentMargin(0)
    body.document().adjustSize()
    body_height = max(36, min(260, int(body.document().size().height()) + 10))
    body.setFixedHeight(body_height)
    return body


def _build_assistant_actions(
    text: str,
    *,
    on_reply_library: Callable[[str, bool], None],
    on_reply_artifact: Callable[[str], None],
) -> QHBoxLayout:
    actions = QHBoxLayout()
    actions.setSpacing(6)
    actions.addStretch()
    for icon_label, hover_text, attach_next in (
        ("\u267b", "Save this reply to Library", False),
        ("\U0001F4CE", "Attach this reply as source for the next turn", True),
    ):
        action_btn = _reply_action_button(
            icon_label,
            color=T.ACCENT_TEAL,
            hover_border="rgba(0,106,106,0.42)",
            tooltip=hover_text,
        )
        action_btn.clicked.connect(
            lambda _=False, content=text, should_attach=attach_next: on_reply_library(content, should_attach)
        )
        actions.addWidget(action_btn)
    artifact_btn = _reply_action_button(
        "\u2B22",
        color=T.ACCENT_ORANGE,
        hover_border="rgba(255,109,0,0.62)",
        tooltip="Save this reply as an artifact",
    )
    artifact_btn.clicked.connect(lambda _=False, content=text: on_reply_artifact(content))
    actions.addWidget(artifact_btn)
    return actions


def build_transcript_row(
    text: str,
    role: str,
    *,
    on_reply_library: Callable[[str, bool], None],
    on_reply_artifact: Callable[[str], None],
) -> QWidget:
    if role == "system":
        return _build_system_row(text)

    row_host = QWidget()
    row = QHBoxLayout(row_host)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(0)

    bubble = QFrame()
    bubble.setObjectName(f"bubble_{role}")
    bubble_bg = T.ACCENT_TEAL if role == "user" else "rgba(255,255,255,0.84)"
    bubble_fg = T.WHITE if role == "user" else T.TEXT
    border = "none" if role == "user" else "1px solid rgba(205,181,154,0.38)"
    bubble.setStyleSheet(
        f"QFrame#bubble_{role} {{ background-color: {bubble_bg}; border: {border}; border-top-left-radius: 24px; border-top-right-radius: 24px; border-bottom-left-radius: { '8px' if role == 'assistant' else '24px' }; border-bottom-right-radius: { '8px' if role == 'user' else '24px' }; }}"
    )
    bubble_layout = QVBoxLayout(bubble)
    bubble_layout.setContentsMargins(16, 12, 16, 11)
    bubble_layout.setSpacing(4)

    bubble_layout.addWidget(
        _label(
            "YOU" if role == "user" else "GUPPY",
            color="rgba(255,250,243,0.88)" if role == "user" else T.PRIMARY,
            size=T.FS_TINY,
            bold=True,
        )
    )

    if role == "assistant":
        bubble_layout.addWidget(_build_assistant_body(text, bubble_fg=bubble_fg))
        bubble_layout.addLayout(
            _build_assistant_actions(
                text,
                on_reply_library=on_reply_library,
                on_reply_artifact=on_reply_artifact,
            )
        )
    else:
        bubble_layout.addWidget(_build_user_body(text, bubble_fg=bubble_fg))

    bubble.setMaximumWidth(488 if role == "assistant" else 320)
    if role == "user":
        row.addStretch()
        row.addWidget(bubble)
    else:
        row.addWidget(bubble)
        row.addStretch()
    return row_host


def clear_transcript_layout(layout: QVBoxLayout) -> None:
    while layout.count() > 1:
        item = layout.takeAt(0)
        if item is None:
            continue
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
            continue
        nested = item.layout()
        if nested is None:
            continue
        while nested.count():
            nested_item = nested.takeAt(0)
            if nested_item is None:
                continue
            nested_widget = nested_item.widget()
            if nested_widget is not None:
                nested_widget.deleteLater()
