from utils.personalization_config import (
    build_persona_prompt_overlay,
    resolve_persona_profile,
    resolve_voice_binding,
)


def test_resolve_persona_profile_prefers_explicit_selection_over_assignments() -> None:
    config = {
        "personas": [
            {"id": "global", "name": "Global", "scope": "global", "traits": {}, "teaching": {}},
            {"id": "builder", "name": "Builder Coach", "scope": "model", "model": "guppy-fast", "traits": {}, "teaching": {}},
        ],
        "assignments": {"global": "global", "by_model": {"guppy-fast": "builder"}},
        "default_persona_id": "global",
    }

    resolved = resolve_persona_profile(
        requested_persona="Builder Coach",
        model_id="guppy",
        persona_config=config,
    )

    assert resolved["id"] == "builder"


def test_resolve_persona_profile_uses_model_assignment_when_no_explicit_persona() -> None:
    config = {
        "personas": [
            {"id": "global", "name": "Global", "scope": "global", "traits": {}, "teaching": {}},
            {"id": "coder", "name": "Code Reviewer", "scope": "model", "model": "guppy-code", "traits": {}, "teaching": {}},
        ],
        "assignments": {"global": "global", "by_model": {"guppy-code": "coder"}},
        "default_persona_id": "global",
    }

    resolved = resolve_persona_profile(model_id="guppy-code", persona_config=config)

    assert resolved["id"] == "coder"


def test_build_persona_prompt_overlay_contains_trait_and_prompt_details() -> None:
    config = {
        "personas": [
            {
                "id": "builder",
                "name": "Builder Coach",
                "scope": "global",
                "system_prompt": "Keep output review-first and bounded.",
                "traits": {"tone": "coach", "verbosity": "high", "response_style": "structured"},
                "teaching": {"enabled": True, "socratic_bias": 55, "example_bias": 65},
            }
        ],
        "assignments": {"global": "builder", "by_model": {}},
        "default_persona_id": "builder",
    }

    persona, overlay = build_persona_prompt_overlay(requested_persona="builder", persona_config=config)

    assert persona["name"] == "Builder Coach"
    assert "Builder Coach" in overlay
    assert "coach" in overlay.lower()
    assert "review-first" in overlay.lower()
    assert "55/100" in overlay


def test_build_persona_prompt_overlay_includes_curated_profile_summary() -> None:
    config = {
        "personas": [
            {
                "id": "main_guppy",
                "name": "Main Guppy",
                "scope": "global",
                "system_prompt": "Stay calm and exact.",
                "profile_summary": "- Ryan prefers concise answers.\n- Keep Home calm and chat-first.",
                "traits": {"tone": "butler", "verbosity": "medium", "response_style": "direct"},
                "teaching": {"enabled": True, "socratic_bias": 35, "example_bias": 60},
            }
        ],
        "assignments": {"global": "main_guppy", "by_model": {}},
        "default_persona_id": "main_guppy",
    }

    _persona, overlay = build_persona_prompt_overlay(requested_persona="main_guppy", persona_config=config)

    assert "Curated long-term profile summary" in overlay
    assert "concise answers" in overlay
    assert "Home calm and chat-first" in overlay


def test_resolve_voice_binding_prefers_model_then_persona_then_default() -> None:
    bindings = {
        "defaults": {"engine": "EDGE TTS", "voice_id": "default-voice"},
        "bindings": {
            "by_persona": {"builder": {"engine": "KOKORO", "voice_id": "persona-voice"}},
            "by_model": {"guppy-code": {"engine": "WINDOWS SAPI", "voice_id": "model-voice"}},
        },
        "imports": [],
    }

    model_hit = resolve_voice_binding(persona_id="builder", model_id="guppy-code", voice_bindings=bindings)
    persona_hit = resolve_voice_binding(persona_id="builder", model_id="guppy-fast", voice_bindings=bindings)
    default_hit = resolve_voice_binding(persona_id="unknown", model_id="unknown", voice_bindings=bindings)

    assert model_hit == {"engine": "WINDOWS SAPI", "voice_id": "model-voice", "source": "model"}
    assert persona_hit == {"engine": "KOKORO", "voice_id": "persona-voice", "source": "persona"}
    assert default_hit == {"engine": "EDGE TTS", "voice_id": "default-voice", "source": "default"}
