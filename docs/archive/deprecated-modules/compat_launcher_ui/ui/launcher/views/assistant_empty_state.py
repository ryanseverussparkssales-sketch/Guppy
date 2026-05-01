"""
assistant_empty_state.py
Empty-state widget builder and copy-update helpers for AssistantView.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from src.guppy.launcher_application.home_presenter import build_home_workspace_state

from .. import tokens as T


def build_empty_state(owner: Any) -> QFrame:
    frame = QFrame()
    frame.setObjectName("empty_state")
    frame.setStyleSheet(
        "QFrame#empty_state { background-color: rgba(255,250,243,0.78); border: 1px solid rgba(205,181,154,0.55); border-radius: 28px; }"
    )
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(10)

    owner._empty_state_title_lbl = QLabel(owner._empty_state_title_text)
    owner._empty_state_title_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    owner._empty_state_title_lbl.setStyleSheet(
        f"color: {T.TEXT}; font-family: '{T.FF_HEAD}'; font-size: 25pt; font-weight: 700;"
    )
    layout.addWidget(owner._empty_state_title_lbl)

    owner._empty_state_subtitle_lbl = QLabel(owner._empty_state_subtitle_text)
    owner._empty_state_subtitle_lbl.setWordWrap(True)
    owner._empty_state_subtitle_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    owner._empty_state_subtitle_lbl.setStyleSheet(
        f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_LABEL}pt;"
    )
    layout.addWidget(owner._empty_state_subtitle_lbl)

    owner._empty_state_recipe_lbl = QLabel(owner._empty_state_recipe_text)
    owner._empty_state_recipe_lbl.setWordWrap(True)
    owner._empty_state_recipe_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    owner._empty_state_recipe_lbl.setStyleSheet(
        f"color: {T.ACCENT_TEAL}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
    )
    layout.addWidget(owner._empty_state_recipe_lbl)
    return frame


def refresh_empty_state_copy(owner: Any) -> None:
    state = build_home_workspace_state(
        owner._workspace_name,
        workspace_type=owner._workspace_type,
        description=owner._workspace_purpose,
        mode=owner.selected_mode(),
        persona=owner.selected_persona(),
        voice="default",
        last_message="",
    )
    owner._base_empty_state_title = state.onboarding_title
    owner._base_empty_state_subtitle = state.onboarding_subtitle
    owner._base_empty_state_recipe = state.onboarding_recipe
    refresh_empty_state_guidance(owner)


def refresh_empty_state_guidance(owner: Any) -> None:
    title = owner._base_empty_state_title
    subtitle = owner._base_empty_state_subtitle
    recipe = owner._base_empty_state_recipe
    titles = owner._active_context_titles()
    if titles:
        joined = ", ".join(titles)
        subtitle = f"{subtitle} Library sources are already attached: {joined}."
        recipe = f"{recipe} Or ask the next thing using these attached sources: {joined}."
    owner._empty_state_title_text = title
    owner._empty_state_subtitle_text = subtitle
    owner._empty_state_recipe_text = recipe
    if hasattr(owner, "_empty_state_title_lbl"):
        owner._empty_state_title_lbl.setText(title)
    if hasattr(owner, "_empty_state_subtitle_lbl"):
        owner._empty_state_subtitle_lbl.setText(subtitle)
    if hasattr(owner, "_empty_state_recipe_lbl"):
        owner._empty_state_recipe_lbl.setText(recipe)
