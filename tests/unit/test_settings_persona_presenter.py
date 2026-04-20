from __future__ import annotations

from src.guppy.launcher_application.settings_persona_presenter import (
    build_assignment_summary_text,
    build_persona_preview_text,
)


def test_build_assignment_summary_text_defaults_to_none() -> None:
    assert build_assignment_summary_text([], {}) == "Model bindings: none"


def test_build_assignment_summary_text_renders_persona_names() -> None:
    text = build_assignment_summary_text(
        [
            {"id": "main_guppy", "name": "Main Guppy"},
            {"id": "coach", "name": "Coach Guppy"},
        ],
        {
            "claude-sonnet-4-6": "coach",
            "guppy": "main_guppy",
        },
    )

    assert "claude-sonnet-4-6 -> Coach Guppy" in text
    assert "guppy -> Main Guppy" in text


def test_build_persona_preview_text_renders_scope_traits_and_prompt_preview() -> None:
    text = build_persona_preview_text(
        persona_name="Main Guppy",
        scope="model",
        model_text="guppy-fast",
        tone="coach",
        verbosity="medium",
        style="structured",
        teaching_enabled=True,
        socratic_bias=35,
        example_bias=60,
        prompt="You are Guppy. Stay practical and calm.",
    )

    assert "Persona: MAIN GUPPY" in text
    assert "Scope: MODEL -> guppy-fast" in text
    assert "Tone: COACH" in text
    assert "Teaching: ON (35 / 60)" in text
    assert "Prompt preview: You are Guppy. Stay practical and calm." in text
