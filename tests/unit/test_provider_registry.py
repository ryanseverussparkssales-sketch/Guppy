from __future__ import annotations

from src.guppy.launcher_application.provider_registry import (
    get_example_prompt,
    get_next_step,
    get_provider,
)


def test_provider_registry_exposes_connect_and_connected_guidance() -> None:
    entry = get_provider("youtube")

    assert entry is not None
    assert "api key" in entry.connect_hint.lower()
    assert "find a youtube video" in entry.next_step_hint.lower()


def test_get_next_step_uses_connect_hint_until_connected() -> None:
    assert "api key" in get_next_step("youtube", is_connected=False).lower()
    assert "find a youtube video" in get_next_step("youtube", is_connected=True).lower()


def test_get_example_prompt_returns_plain_language_try_line() -> None:
    assert "try:" in get_example_prompt("crm").lower()
