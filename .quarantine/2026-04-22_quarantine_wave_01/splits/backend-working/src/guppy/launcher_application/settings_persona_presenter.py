"""Pure presentation helpers for Settings persona summary and preview copy."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def build_assignment_summary_text(
    persona_items: Sequence[Mapping[str, Any]],
    by_model: Mapping[str, object] | None,
) -> str:
    if not isinstance(by_model, Mapping) or not by_model:
        return "Model bindings: none"
    persona_names = {
        str(item.get("id", "")).strip(): str(item.get("name", item.get("id", ""))).strip()
        for item in persona_items
    }
    parts = [
        f"{model} -> {persona_names.get(str(persona_id), str(persona_id))}"
        for model, persona_id in sorted(by_model.items())
    ]
    return "Model bindings: " + " | ".join(parts)


def build_persona_preview_text(
    *,
    persona_name: str,
    scope: str,
    model_text: str,
    tone: str,
    verbosity: str,
    style: str,
    teaching_enabled: bool,
    socratic_bias: int,
    example_bias: int,
    prompt: str,
) -> str:
    normalized_scope = str(scope or "GLOBAL").strip().upper() or "GLOBAL"
    scope_line = f"Scope: {normalized_scope}" + (
        f" -> {model_text.strip()}" if normalized_scope == "MODEL" and model_text.strip() else ""
    )
    prompt_preview = prompt[:220] + ("..." if len(prompt) > 220 else "")
    return (
        " | ".join(
            [
                f"Assistant: {(persona_name.strip() or 'Untitled').upper()}",
                scope_line,
                f"Tone: {str(tone or 'BUTLER').strip().upper()}",
                f"Verbosity: {str(verbosity or 'MEDIUM').strip().upper()}",
                f"Style: {str(style or 'DIRECT').strip().upper()}",
                f"Teaching: {'ON' if teaching_enabled else 'OFF'} ({socratic_bias} / {example_bias})",
            ]
        )
        + f"\nPrompt preview: {prompt_preview}"
    )
