"""Service helpers for experience-config persistence and runtime preferences."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.guppy.experience_config.personalization_defaults import (
    DEFAULT_ASSISTANT_NAME,
    DEFAULT_PERSONA_CONFIG,
)

_FALLBACK_PERSONA_CONFIG: dict[str, Any] = {
    "version": 1,
    "default_persona_id": "main_guppy",
    "personas": [
        {
            "id": "main_guppy",
            "name": DEFAULT_ASSISTANT_NAME,
            "scope": "global",
            "system_prompt": "",
            "traits": {"tone": "butler", "verbosity": "medium", "response_style": "direct"},
            "teaching": {"enabled": True, "socratic_bias": 35, "example_bias": 60},
        }
    ],
    "assignments": {"global": "main_guppy", "by_model": {}},
}
_FALLBACK_VOICE_BINDINGS: dict[str, Any] = {
    "version": 1,
    "defaults": {"engine": "EDGE TTS", "voice_id": "en-GB-RyanNeural"},
    "bindings": {"by_model": {}, "by_persona": {}},
    "imports": [],
}
_FALLBACK_RUNTIME_SETTINGS: dict[str, Any] = {
    "runtime_profile": "standard",
    "enable_daemon": True,
    "enable_voice": True,
    "wake_word_default": False,
    "default_mode": "auto",
    "local_runtime_backend": "ollama",
    "lemonade_base_url": "http://localhost:13305/api/v1",
    "lmstudio_base_url": "http://127.0.0.1:1234/v1",
    "local_harness_base_url": "http://127.0.0.1:8001",
    "lemonade_fast_model": "",
    "lemonade_complex_model": "",
    "lemonade_teach_model": "",
    "lemonade_code_model": "",
    "lemonade_vault_model": "",
    "local_main_model": "",
    "local_sub_model_a": "",
    "local_sub_model_b": "",
}

try:
    from utils.runtime_profile import (
        apply_settings_to_env as _apply_settings_to_env,
        load_app_settings as _load_app_settings,
        recommend_runtime_profile as _recommend_runtime_profile,
        save_app_settings as _save_app_settings,
    )

    _RUNTIME_SETTINGS_BACKEND = True
except Exception:
    _RUNTIME_SETTINGS_BACKEND = False

    def _load_app_settings() -> dict[str, Any]:
        return dict(_FALLBACK_RUNTIME_SETTINGS)

    def _save_app_settings(_settings: dict[str, Any]) -> Path | None:
        return None

    def _apply_settings_to_env(settings: dict[str, Any]) -> dict[str, Any]:
        merged = dict(_FALLBACK_RUNTIME_SETTINGS)
        merged.update(settings if isinstance(settings, dict) else {})
        return merged

    def _recommend_runtime_profile() -> dict[str, Any]:
        return {"profile": "standard"}


try:
    from utils.personalization_config import (
        ensure_personalization_scaffold as _ensure_personalization_scaffold,
        list_model_ids as _list_model_ids,
        list_persona_choices as _list_persona_choices,
        load_persona_config as _load_persona_config,
        load_persona_config_with_diagnostics as _load_persona_config_with_diagnostics,
        load_provider_registry as _load_provider_registry,
        load_voice_bindings as _load_voice_bindings,
        resolve_voice_binding as _resolve_voice_binding,
        save_persona_config as _save_persona_config,
        save_provider_registry as _save_provider_registry,
        save_voice_bindings as _save_voice_bindings,
        validate_persona_config as _validate_persona_config,
        validate_provider_registry as _validate_provider_registry,
        validate_voice_bindings as _validate_voice_bindings,
    )

    _PERSONALIZATION_BACKEND = True
except Exception:
    _PERSONALIZATION_BACKEND = False

    def _ensure_personalization_scaffold() -> dict[str, Path]:
        return {}

    def _list_model_ids(_provider_registry=None, include_local: bool = True) -> list[str]:
        if include_local:
            return ["guppy", "guppy-fast", "guppy-code", "guppy-teach", "vault-scraper"]
        return []

    def _list_persona_choices(_persona_config=None) -> list[dict[str, str]]:
        default_persona = DEFAULT_PERSONA_CONFIG["personas"][0]
        name = str(default_persona.get("name", DEFAULT_ASSISTANT_NAME) or DEFAULT_ASSISTANT_NAME)
        return [{"id": "main_guppy", "name": name, "scope": "global", "model": "", "label": f"{name} [GLOBAL]"}]

    def _load_persona_config() -> dict[str, Any]:
        return dict(_FALLBACK_PERSONA_CONFIG)

    def _load_persona_config_with_diagnostics() -> tuple[dict[str, Any], list[str]]:
        return dict(_FALLBACK_PERSONA_CONFIG), []

    def _load_provider_registry() -> dict[str, Any]:
        return {}

    def _load_voice_bindings() -> dict[str, Any]:
        return dict(_FALLBACK_VOICE_BINDINGS)

    def _save_persona_config(_payload: dict[str, Any]) -> Path | None:
        return None

    def _save_provider_registry(_payload: dict[str, Any]) -> Path | None:
        return None

    def _save_voice_bindings(_payload: dict[str, Any]) -> Path | None:
        return None

    def _validate_persona_config(_payload: dict[str, Any]) -> list[str]:
        return []

    def _validate_provider_registry(_payload: dict[str, Any]) -> list[str]:
        return []

    def _validate_voice_bindings(_payload: dict[str, Any]) -> list[str]:
        return []

    def _resolve_voice_binding(*, persona_id: str = "", model_id: str = "", voice_bindings: dict | None = None) -> dict[str, str]:
        del persona_id, model_id, voice_bindings
        return {"engine": "EDGE TTS", "voice_id": "en-GB-RyanNeural", "source": "default"}


def runtime_settings_backend_available() -> bool:
    return _RUNTIME_SETTINGS_BACKEND


def personalization_backend_available() -> bool:
    return _PERSONALIZATION_BACKEND


def load_runtime_settings() -> dict[str, Any]:
    settings = _load_app_settings() if _RUNTIME_SETTINGS_BACKEND else dict(_FALLBACK_RUNTIME_SETTINGS)
    return settings if isinstance(settings, dict) else dict(_FALLBACK_RUNTIME_SETTINGS)


def save_runtime_settings(settings: dict[str, Any]) -> Path | None:
    payload = settings if isinstance(settings, dict) else {}
    return _save_app_settings(payload)


def apply_runtime_settings_to_env(settings: dict[str, Any]) -> dict[str, Any]:
    payload = settings if isinstance(settings, dict) else {}
    merged = _apply_settings_to_env(payload)
    return merged if isinstance(merged, dict) else load_runtime_settings()


def recommend_runtime_profile() -> dict[str, Any]:
    recommendation = _recommend_runtime_profile()
    return recommendation if isinstance(recommendation, dict) else {"profile": "standard"}


def configured_local_runtime_backend(settings: dict[str, Any] | None = None) -> str:
    payload = settings if isinstance(settings, dict) else load_runtime_settings()
    backend = str(
        payload.get("local_runtime_backend", os.environ.get("GUPPY_LOCAL_RUNTIME_BACKEND", "ollama"))
    ).strip().lower() or "ollama"
    return backend.upper()


def ensure_personalization_scaffold() -> dict[str, Path]:
    created = _ensure_personalization_scaffold()
    return created if isinstance(created, dict) else {}


def list_model_ids(provider_registry: dict[str, Any] | None = None, *, include_local: bool = True) -> list[str]:
    model_ids = _list_model_ids(provider_registry, include_local=include_local)
    return [str(model_id).strip() for model_id in model_ids if str(model_id).strip()]


def list_persona_choices(persona_config: dict[str, Any] | None = None) -> list[dict[str, str]]:
    choices = _list_persona_choices(persona_config)
    return choices if isinstance(choices, list) else _list_persona_choices(None)


def load_persona_config() -> dict[str, Any]:
    config = _load_persona_config()
    return config if isinstance(config, dict) else dict(_FALLBACK_PERSONA_CONFIG)


def load_persona_config_with_diagnostics() -> tuple[dict[str, Any], list[str]]:
    config, diagnostics = _load_persona_config_with_diagnostics()
    safe_config = config if isinstance(config, dict) else dict(_FALLBACK_PERSONA_CONFIG)
    safe_diagnostics = diagnostics if isinstance(diagnostics, list) else []
    return safe_config, safe_diagnostics


def load_provider_registry() -> dict[str, Any]:
    registry = _load_provider_registry()
    return registry if isinstance(registry, dict) else {}


def save_provider_registry(payload: dict[str, Any]) -> Path | None:
    data = payload if isinstance(payload, dict) else {}
    return _save_provider_registry(data)


def validate_provider_registry(payload: dict[str, Any]) -> list[str]:
    data = payload if isinstance(payload, dict) else {}
    errors = _validate_provider_registry(data)
    return errors if isinstance(errors, list) else []


def save_persona_config(payload: dict[str, Any]) -> Path | None:
    data = payload if isinstance(payload, dict) else {}
    return _save_persona_config(data)


def validate_persona_config(payload: dict[str, Any]) -> list[str]:
    data = payload if isinstance(payload, dict) else {}
    errors = _validate_persona_config(data)
    return errors if isinstance(errors, list) else []


def load_voice_bindings() -> dict[str, Any]:
    bindings = _load_voice_bindings()
    return bindings if isinstance(bindings, dict) else dict(_FALLBACK_VOICE_BINDINGS)


def save_voice_bindings(payload: dict[str, Any]) -> Path | None:
    data = payload if isinstance(payload, dict) else {}
    return _save_voice_bindings(data)


def validate_voice_bindings(payload: dict[str, Any]) -> list[str]:
    data = payload if isinstance(payload, dict) else {}
    errors = _validate_voice_bindings(data)
    return errors if isinstance(errors, list) else []


def resolve_voice_binding(*, persona_id: str = "", model_id: str = "", voice_bindings: dict | None = None) -> dict[str, str]:
    resolved = _resolve_voice_binding(persona_id=persona_id, model_id=model_id, voice_bindings=voice_bindings)
    return resolved if isinstance(resolved, dict) else {"engine": "EDGE TTS", "voice_id": "en-GB-RyanNeural", "source": "default"}


try:
    from utils.runtime_profile import get_runtime_envelope_config as _get_runtime_envelope_config

    _RUNTIME_ENVELOPE_BACKEND = True
except Exception:
    _RUNTIME_ENVELOPE_BACKEND = False

    def _get_runtime_envelope_config(profile: str | None = None) -> dict[str, Any]:  # type: ignore[misc]
        active = (profile or os.environ.get("GUPPY_RUNTIME_PROFILE", "standard") or "standard").strip().lower()
        return {
            "profile": active,
            "cpu_max_pct": float(os.environ.get("GUPPY_ENVELOPE_CPU_MAX_PCT", "80")),
            "ram_max_pct": float(os.environ.get("GUPPY_ENVELOPE_RAM_MAX_PCT", "88")),
            "check_interval_s": int(os.environ.get("GUPPY_ENVELOPE_CHECK_S", "60")),
        }


def get_runtime_envelope_config(profile: str | None = None) -> dict[str, Any]:
    """Return runtime envelope limits for the given profile."""
    config = _get_runtime_envelope_config(profile)
    return config if isinstance(config, dict) else {"profile": "standard"}


def apply_runtime_profile() -> dict[str, Any]:
    """Load runtime settings and apply them to env. Returns the merged settings dict."""
    settings = load_runtime_settings()
    return apply_runtime_settings_to_env(settings)
