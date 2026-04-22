"""
ui/launcher/views/assistant_starter_support.py
Starter template, copy, and loading helpers for AssistantView.
"""
from __future__ import annotations

from typing import Any

from src.guppy.launcher_application.home_presenter import (
    build_home_starter_state,
    home_workspace_starter_templates,
)

from .assistant_context import (
    active_context_titles as context_active_context_titles,
    context_aware_starter_prompt as context_context_aware_starter_prompt,
    context_aware_starter_title as context_context_aware_starter_title,
)


def starter_templates(workspace_type: str) -> list[tuple[str, str, str, str]]:
    return [
        (item.starter_id, item.title, item.mode, item.prompt)
        for item in home_workspace_starter_templates(workspace_type)
    ]


def active_context_titles(items: list[dict[str, str]], limit: int = 2) -> list[str]:
    return context_active_context_titles(items, limit)


def context_aware_starter_title(items: list[dict[str, str]], starter_id: str, title: str) -> str:
    return context_context_aware_starter_title(items, starter_id, title)


def context_aware_starter_prompt(items: list[dict[str, str]], prompt: str) -> str:
    return context_context_aware_starter_prompt(items, prompt)


def refresh_starter_buttons(view: Any) -> None:
    for index, (starter_id, title, _mode, prompt) in enumerate(view._starter_templates()):
        button = view._starter_buttons.get(starter_id)
        if button is None:
            continue
        button.setText(context_aware_starter_title(view._active_context_items, starter_id, title))
        button.setToolTip(context_aware_starter_prompt(view._active_context_items, prompt))
        button.setStyleSheet(view._starter_button_style(primary=index == 0))


def load_starter_by_id(view: Any, starter_id: str) -> None:
    starter = build_home_starter_state(view._workspace_type, starter_id)
    titles = active_context_titles(view._active_context_items)
    if titles:
        joined_titles = ", ".join(titles)
        starter = type(starter)(
            starter_id=starter.starter_id,
            label=context_aware_starter_title(view._active_context_items, starter.starter_id, starter.label),
            mode=starter.mode,
            prompt=context_aware_starter_prompt(view._active_context_items, starter.prompt),
            background_event=f"{starter.background_event} Attached sources ready: {joined_titles}.",
            starter_summary=f"{starter.starter_summary} Attached sources: {joined_titles}.",
            status=starter.status,
        )
    load_starter(view, starter)


def load_starter(view: Any, starter: Any) -> None:
    view.set_input_text(starter.prompt)
    view.set_chat_context(starter.mode, view.selected_persona())
    view.set_background_event(starter.background_event)
    view._base_starter_summary = starter.starter_summary
    view._refresh_composer_guidance()
    view.set_status(starter.status)
    view._starters_expanded = False
    view._update_starter_visibility()
    view.starter_requested.emit(starter.starter_id, starter.prompt)
