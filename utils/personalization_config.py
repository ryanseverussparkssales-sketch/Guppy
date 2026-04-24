from __future__ import annotations

from pathlib import Path
from typing import Any

from src.guppy.experience_config.personalization_defaults import (
    DEFAULT_PERSONA_CONFIG,
    DEFAULT_PROVIDER_REGISTRY,
    DEFAULT_VOICE_BINDINGS,
    LOCAL_MODEL_IDS,
    MAIN_GUPPY_PERSONA_ID,
    MAIN_GUPPY_PROFILE_SUMMARY,
)
from src.guppy.experience_config.personalization_resolution import (
    build_persona_prompt_overlay as _service_build_persona_prompt_overlay,
    list_model_ids as _service_list_model_ids,
    list_persona_choices as _service_list_persona_choices,
    resolve_persona_profile as _service_resolve_persona_profile,
    resolve_voice_binding as _service_resolve_voice_binding,
)
from src.guppy.experience_config.personalization_storage import (
    deepcopy_json as _deepcopy_json,
    ensure_personalization_scaffold as _service_ensure_personalization_scaffold,
    load_json_with_diagnostics as _load_json_with_diagnostics,
    load_persona_config as _service_load_persona_config,
    load_persona_config_with_diagnostics as _service_load_persona_config_with_diagnostics,
    load_provider_registry as _service_load_provider_registry,
    load_provider_registry_with_diagnostics as _service_load_provider_registry_with_diagnostics,
    load_voice_bindings as _service_load_voice_bindings,
    load_voice_bindings_with_diagnostics as _service_load_voice_bindings_with_diagnostics,
    normalize_persona_config as _normalize_persona_config,
    normalize_provider_registry as _normalize_provider_registry,
    normalize_voice_bindings as _normalize_voice_bindings,
    read_json as _read_json,
    save_persona_config as _service_save_persona_config,
    save_provider_registry as _service_save_provider_registry,
    save_voice_bindings as _service_save_voice_bindings,
    unique_strings_in_order as _unique_strings_in_order,
    validate_all_personalization_configs as _service_validate_all_personalization_configs,
    validate_persona_config,
    validate_provider_registry,
    validate_voice_bindings,
    write_json as _write_json,
)


ROOT = Path(__file__).resolve().parent.parent
RUNTIME_DIR = ROOT / "runtime"

PERSONA_CONFIG_PATH = RUNTIME_DIR / "persona_config.json"
PROVIDER_REGISTRY_PATH = RUNTIME_DIR / "provider_registry.json"
VOICE_BINDINGS_PATH = RUNTIME_DIR / "voice_bindings.json"


def load_persona_config() -> dict[str, Any]:
    return _service_load_persona_config(PERSONA_CONFIG_PATH)


def load_provider_registry() -> dict[str, Any]:
    return _service_load_provider_registry(PROVIDER_REGISTRY_PATH)


def load_voice_bindings() -> dict[str, Any]:
    return _service_load_voice_bindings(VOICE_BINDINGS_PATH)


def load_persona_config_with_diagnostics() -> tuple[dict[str, Any], list[str]]:
    return _service_load_persona_config_with_diagnostics(PERSONA_CONFIG_PATH)


def load_provider_registry_with_diagnostics() -> tuple[dict[str, Any], list[str]]:
    return _service_load_provider_registry_with_diagnostics(PROVIDER_REGISTRY_PATH)


def load_voice_bindings_with_diagnostics() -> tuple[dict[str, Any], list[str]]:
    return _service_load_voice_bindings_with_diagnostics(VOICE_BINDINGS_PATH)


def save_persona_config(data: dict[str, Any]) -> Path:
    return _service_save_persona_config(PERSONA_CONFIG_PATH, data)


def save_provider_registry(data: dict[str, Any]) -> Path:
    return _service_save_provider_registry(PROVIDER_REGISTRY_PATH, data)


def save_voice_bindings(data: dict[str, Any]) -> Path:
    return _service_save_voice_bindings(VOICE_BINDINGS_PATH, data)


def ensure_personalization_scaffold() -> dict[str, Path]:
    return _service_ensure_personalization_scaffold(PERSONA_CONFIG_PATH, PROVIDER_REGISTRY_PATH, VOICE_BINDINGS_PATH)


def validate_all_personalization_configs() -> dict[str, list[str]]:
    return _service_validate_all_personalization_configs(PERSONA_CONFIG_PATH, PROVIDER_REGISTRY_PATH, VOICE_BINDINGS_PATH)


def list_model_ids(provider_registry: dict[str, Any] | None = None, *, include_local: bool = True) -> list[str]:
    registry = provider_registry if isinstance(provider_registry, dict) else load_provider_registry()
    return _service_list_model_ids(registry, include_local=include_local)


def list_persona_choices(persona_config: dict[str, Any] | None = None) -> list[dict[str, str]]:
    cfg = persona_config if isinstance(persona_config, dict) else load_persona_config()
    return _service_list_persona_choices(cfg)


def resolve_persona_profile(
    *,
    requested_persona: str = "",
    model_id: str = "",
    persona_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = persona_config if isinstance(persona_config, dict) else load_persona_config()
    return _service_resolve_persona_profile(
        requested_persona=requested_persona,
        model_id=model_id,
        persona_config=cfg,
    )


def build_persona_prompt_overlay(
    *,
    requested_persona: str = "",
    model_id: str = "",
    persona_config: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str]:
    cfg = persona_config if isinstance(persona_config, dict) else load_persona_config()
    return _service_build_persona_prompt_overlay(
        requested_persona=requested_persona,
        model_id=model_id,
        persona_config=cfg,
    )


def resolve_voice_binding(
    *,
    persona_id: str = "",
    model_id: str = "",
    voice_bindings: dict[str, Any] | None = None,
) -> dict[str, str]:
    bindings = voice_bindings if isinstance(voice_bindings, dict) else load_voice_bindings()
    return _service_resolve_voice_binding(
        persona_id=persona_id,
        model_id=model_id,
        voice_bindings=bindings,
    )
