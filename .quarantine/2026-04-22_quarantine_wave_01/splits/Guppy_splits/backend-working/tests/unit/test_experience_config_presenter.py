from __future__ import annotations

from unittest.mock import patch

from src.guppy import experience_config
from src.guppy.experience_config import (
    PersonalizationState,
    apply_runtime_settings_to_env,
    build_persona_options,
    configured_local_runtime_backend,
    ensure_personalization_scaffold,
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
    voice_binding_summary,
    voice_option_choices,
)
from src.guppy.experience_config import presenter as experience_presenter
from src.guppy.experience_config import services as experience_services


def test_voice_option_choices_collects_normalized_unique_bindings() -> None:
    options = voice_option_choices(
        {
            "defaults": {"engine": " EDGE TTS ", "voice_id": " guide "},
            "bindings": {
                "by_persona": {
                    "builder": {"engine": "EDGE TTS", "voice_id": "guide"},
                    "coach": {"engine": "ELEVENLABS", "voice_id": "persona-voice"},
                    "ignored": [],
                },
                "by_model": {
                    "fast": {"engine": "WINDOWS SAPI", "voice_id": "model-voice"},
                    "blank": {"engine": "", "voice_id": "missing"},
                },
            },
            "imports": [
                {"engine": "KOKORO", "voice_id": "import-voice"},
                {"engine": "KOKORO", "voice_id": "import-voice"},
                {"engine": "EDGE TTS", "voice_id": "guide"},
                "ignored",
            ],
        }
    )

    assert options == [
        ("Default", "default"),
        ("EDGE TTS / guide", "EDGE TTS:guide"),
        ("ELEVENLABS / persona-voice", "ELEVENLABS:persona-voice"),
        ("WINDOWS SAPI / model-voice", "WINDOWS SAPI:model-voice"),
        ("KOKORO / import-voice", "KOKORO:import-voice"),
    ]


def test_voice_option_choices_falls_back_to_default_when_payload_is_not_a_mapping() -> None:
    assert voice_option_choices(None) == [("Default", "default")]


def test_voice_binding_summary_flags_missing_elevenlabs_key() -> None:
    with patch.dict(experience_presenter.os.environ, {}, clear=True):
        summary = voice_binding_summary({"engine": "ELEVENLABS", "source": "persona"})

    assert summary == "ELEVENLABS from persona voice (needs API key)"


def test_voice_binding_summary_reports_missing_edge_tts_dependency() -> None:
    with patch.object(experience_presenter.importlib.util, "find_spec", return_value=None):
        summary = voice_binding_summary({"engine": "EDGE TTS", "source": "model"})

    assert summary == "EDGE TTS from model voice (preview dependency missing)"


def test_voice_binding_summary_tolerates_probe_failures_and_unknown_sources() -> None:
    with patch.object(experience_presenter.importlib.util, "find_spec", side_effect=RuntimeError("boom")):
        summary = voice_binding_summary({"engine": "EDGE TTS", "source": "workspace"})

    assert summary == "EDGE TTS from voice setting (ready)"


def test_build_persona_options_uses_name_and_id_fallbacks() -> None:
    options = build_persona_options(
        [
            {"id": "builder", "name": "Builder Coach"},
            {"id": "ops"},
            {"name": "Nameless"},
            {},
            "ignored",
        ]
    )

    assert options == (
        ("Builder Coach", "builder"),
        ("ops", "ops"),
        ("Nameless", "guppy"),
        ("guppy", "guppy"),
    )


def test_personalization_state_empty_returns_safe_defaults() -> None:
    state = PersonalizationState.empty()

    assert state.persona_options == (("Guppy", "guppy"),)
    assert state.voice_options == (("Default", "default"),)
    assert state.voice_summary == "default voice"
    assert state.model_id == ""
    assert state.voice_choice == {}


def test_experience_config_exports_public_helpers() -> None:
    assert experience_config.PersonalizationState is PersonalizationState
    assert experience_config.apply_runtime_settings_to_env is apply_runtime_settings_to_env
    assert experience_config.build_persona_options is build_persona_options
    assert experience_config.configured_local_runtime_backend is configured_local_runtime_backend
    assert experience_config.ensure_personalization_scaffold is ensure_personalization_scaffold
    assert experience_config.list_model_ids is list_model_ids
    assert experience_config.list_persona_choices is list_persona_choices
    assert experience_config.load_persona_config is load_persona_config
    assert experience_config.load_persona_config_with_diagnostics is load_persona_config_with_diagnostics
    assert experience_config.load_provider_registry is load_provider_registry
    assert experience_config.load_runtime_settings is load_runtime_settings
    assert experience_config.load_voice_bindings is load_voice_bindings
    assert experience_config.personalization_backend_available is personalization_backend_available
    assert experience_config.recommend_runtime_profile is recommend_runtime_profile
    assert experience_config.resolve_voice_binding is resolve_voice_binding
    assert experience_config.runtime_settings_backend_available is runtime_settings_backend_available
    assert experience_config.save_persona_config is save_persona_config
    assert experience_config.save_provider_registry is save_provider_registry
    assert experience_config.save_runtime_settings is save_runtime_settings
    assert experience_config.save_voice_bindings is save_voice_bindings
    assert experience_config.validate_persona_config is validate_persona_config
    assert experience_config.validate_provider_registry is validate_provider_registry
    assert experience_config.validate_voice_bindings is validate_voice_bindings
    assert experience_config.voice_binding_summary is voice_binding_summary
    assert experience_config.voice_option_choices is voice_option_choices
    assert {
        "PersonalizationState",
        "apply_runtime_settings_to_env",
        "build_persona_options",
        "configured_local_runtime_backend",
        "ensure_personalization_scaffold",
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
    }.issubset(set(experience_config.__all__))


def test_configured_local_runtime_backend_prefers_settings_then_env() -> None:
    assert configured_local_runtime_backend({"local_runtime_backend": " lemonade "}) == "LEMONADE"
    with patch.dict(experience_services.os.environ, {"GUPPY_LOCAL_RUNTIME_BACKEND": "ollama"}, clear=True):
        assert configured_local_runtime_backend({}) == "OLLAMA"


def test_backend_availability_helpers_return_booleans() -> None:
    assert isinstance(runtime_settings_backend_available(), bool)
    assert isinstance(personalization_backend_available(), bool)
