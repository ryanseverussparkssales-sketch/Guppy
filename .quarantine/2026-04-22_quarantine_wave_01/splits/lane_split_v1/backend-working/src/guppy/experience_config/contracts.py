"""Typed contracts for the experience-config domain.

Experience-config owns persona, provider, voice, and runtime-profile state —
everything the user can tune about how Guppy presents and responds.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PersonalizationState:
    """Snapshot of resolved personalization state for the launcher UI."""

    persona_options: tuple[tuple[str, str], ...]
    voice_options: tuple[tuple[str, str], ...]
    voice_summary: str
    model_id: str
    voice_choice: dict = field(default_factory=dict)

    @classmethod
    def empty(cls) -> PersonalizationState:
        return cls(
            persona_options=(("Guppy", "guppy"),),
            voice_options=(("Default", "default"),),
            voice_summary="default voice",
            model_id="",
        )
