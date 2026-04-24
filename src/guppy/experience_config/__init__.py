"""Experience-config domain seam.

Owns persona, provider, voice, and runtime-profile configuration — the things
users tune about how Guppy presents and responds.  New persona/voice logic
should land here instead of in utils/personalization_config.py.
"""
from .contracts import PersonalizationState
from .presenter import build_persona_options, voice_binding_summary, voice_option_choices
from .services import (
    apply_runtime_settings_to_env,
    apply_runtime_profile,
    configured_local_runtime_backend,
    ensure_personalization_scaffold,
    get_runtime_envelope_config,
    list_model_ids,
    list_persona_choices,
    load_persona_config,
    load_persona_config_with_diagnostics,
    load_provider_registry,
    load_runtime_settings,
    load_voice_bindings,
    personalization_backend_available,
    recommend_runtime_profile,
    resolve_voice_binding,
    runtime_settings_backend_available,
    save_persona_config,
    save_provider_registry,
    save_runtime_settings,
    save_voice_bindings,
    validate_persona_config,
    validate_provider_registry,
    validate_voice_bindings,
)

__all__ = [
    "PersonalizationState",
    "apply_runtime_settings_to_env",
    "apply_runtime_profile",
    "build_persona_options",
    "configured_local_runtime_backend",
    "ensure_personalization_scaffold",
    "get_runtime_envelope_config",
    "list_model_ids",
    "list_persona_choices",
    "load_persona_config",
    "load_persona_config_with_diagnostics",
    "load_provider_registry",
    "load_runtime_settings",
    "load_voice_bindings",
    "personalization_backend_available",
    "recommend_runtime_profile",
    "resolve_voice_binding",
    "runtime_settings_backend_available",
    "save_persona_config",
    "save_provider_registry",
    "save_runtime_settings",
    "save_voice_bindings",
    "validate_persona_config",
    "validate_provider_registry",
    "validate_voice_bindings",
    "voice_binding_summary",
    "voice_option_choices",
]
