from __future__ import annotations

from src.guppy.launcher_application.provider_registry import (
    get_example_prompt,
    get_next_step,
    get_provider,
    list_providers,
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


def test_planned_local_adapters_are_lookupable_without_polluting_onboarding_lists() -> None:
    anythingllm = get_provider("anythingllm_local")
    huggingface = get_provider("huggingface_local")

    assert anythingllm is not None
    assert anythingllm.availability_status == "planned"
    assert anythingllm.installation_status == "not_installed"
    assert anythingllm.verify_supported is False
    assert "not installed" in anythingllm.connect_hint.lower()

    assert huggingface is not None
    assert huggingface.availability_status == "planned"
    assert huggingface.installation_status == "not_installed"
    assert "hugging face" in huggingface.label.lower()

    visible_ids = {entry.id for entry in list_providers()}
    assert "anythingllm_local" not in visible_ids
    assert "huggingface_local" not in visible_ids
