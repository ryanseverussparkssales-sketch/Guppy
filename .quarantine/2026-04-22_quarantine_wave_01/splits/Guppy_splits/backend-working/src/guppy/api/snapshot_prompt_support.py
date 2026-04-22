"""Persona/prompt builder support for the runtime snapshot.

Extracted from server_runtime_snapshot.py as part of TR54 wave – prompt-assembly seam.
Owns the personalization bootstrap try/except and the thin prompt-builder delegates
that route to services_realtime.
"""
from __future__ import annotations

from typing import Any

from src.guppy.api import services_realtime

# -- Personalization bootstrap --------------------------------------------
try:
    from utils.personalization_config import (
        build_persona_prompt_overlay,
        ensure_personalization_scaffold,
        load_persona_config_with_diagnostics,
        load_provider_registry_with_diagnostics,
        load_voice_bindings_with_diagnostics,
    )
    PERSONALIZATION_BOOTSTRAP_AVAILABLE = True
except Exception:
    PERSONALIZATION_BOOTSTRAP_AVAILABLE = False

    def build_persona_prompt_overlay(  # type: ignore[misc]
        *,
        requested_persona: str = "",
        model_id: str = "",
        persona_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str]:
        del requested_persona, model_id, persona_config
        return {}, ""

    # Minimal stubs so callers behind PERSONALIZATION_BOOTSTRAP_AVAILABLE guards
    # never encounter NameError.  These are never invoked when the flag is False.
    def ensure_personalization_scaffold() -> dict[str, Any]:  # type: ignore[misc]  # pragma: no cover
        return {}

    def load_persona_config_with_diagnostics() -> tuple[dict[str, Any], list[Any]]:  # type: ignore[misc]  # pragma: no cover
        return {}, []

    def load_provider_registry_with_diagnostics() -> tuple[dict[str, Any], list[Any]]:  # type: ignore[misc]  # pragma: no cover
        return {}, []

    def load_voice_bindings_with_diagnostics() -> tuple[dict[str, Any], list[Any]]:  # type: ignore[misc]  # pragma: no cover
        return {}, []


# -- Prompt builder delegates ---------------------------------------------

def should_use_rich_chat_prompt_context(request: Any) -> bool:
    return services_realtime.should_use_rich_chat_prompt_context(request)


def should_use_rich_prompt_context(
    *,
    message: str,
    mode: str | None = None,
    history: Any = None,
) -> bool:
    return services_realtime.should_use_rich_prompt_context(
        message=message,
        mode=mode,
        history=history,
    )


def build_chat_system_prompt(
    module_owner: Any,
    *,
    message: str,
    session_id: str | None = None,
    mode: str | None = None,
    persona: str | None = None,
    model_id: str | None = None,
    history: Any = None,
) -> str:
    return services_realtime.build_chat_system_prompt(
        module_owner,
        message=message,
        session_id=session_id,
        mode=mode,
        persona=persona,
        model_id=model_id,
        history=history,
    )
