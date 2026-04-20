from src.guppy.launcher_application.models_presenter import (
    build_models_loadout_help_text,
    build_models_route_decision_text,
    build_models_route_evidence_text,
    build_models_route_preview_hint_text,
    build_models_route_preview_text,
    build_models_provider_readiness_state,
    build_models_route_summary_text,
    build_models_runtime_evidence_state,
    friendly_models_route_target,
)


def test_runtime_evidence_state_surfaces_chat_harness_and_warning_tone() -> None:
    state = build_models_runtime_evidence_state(
        {
            "local_runtime": {
                "backend": "ollama",
                "state": "ready",
                "detail": "Runtime is responding.",
                "requested_model": "qwen2.5:7b",
                "resolved_model": "qwen2.5:7b",
                "tool_loop": "enabled",
                "base_url": "http://127.0.0.1:11434",
                "available_roles": ["main"],
                "missing_roles": ["sub_b"],
                "chat_ready": False,
                "chat_state": "warming",
                "chat_detail": "Warm sample still loading.",
                "chat_model": "qwen2.5:7b",
            }
        },
        editor_backend="ollama",
        saved_backend="ollama",
    )

    assert state.tone == "warning"
    assert "Chat harness WARMING" in state.text
    assert "Missing mapped roles: SUB_B" in state.text


def test_provider_readiness_state_flags_active_backend_failure() -> None:
    state = build_models_provider_readiness_state(
        {
            "anthropic": "missing API key",
            "openai": "ready",
            "gemini": "missing API key",
            "ollama_api": "ready",
            "ollama_local": "offline",
            "lmstudio_local": "reachable",
            "lemonade_local": "ready",
            "local_harness": "offline",
        },
        active_backend="ollama",
    )

    assert state.tone == "error"
    assert "Current backend gate: OLLAMA needs attention" in state.text
    assert "Harness note:" in state.text


def test_loadout_help_text_surfaces_role_assignments() -> None:
    text = build_models_loadout_help_text(
        main_model="qwen-main",
        sub_a_model="qwen-fast",
        sub_b_model="qwen-code",
    )

    assert "complex/default -> qwen-main" in text
    assert "simple/fast -> qwen-fast" in text
    assert "code specialist -> qwen-code" in text


def test_route_summary_text_includes_fallback_and_live_evidence() -> None:
    summary, evidence = build_models_route_summary_text(
        simple_target="Claude Haiku",
        complex_target="Claude Sonnet",
        teaching_target="LOCAL / guppy",
        fallback_targets=["Claude Opus", "LOCAL / guppy"],
        health_summary="Cloud path configured | Local runtime OLLAMA heartbeat seen",
    )

    assert "Simple requests start with Claude Haiku." in summary
    assert "Complex requests start with Claude Sonnet." in summary
    assert "Claude Opus, LOCAL / guppy" in summary
    assert evidence == "Live evidence: Cloud path configured | Local runtime OLLAMA heartbeat seen"


def test_route_decision_text_surfaces_reason_and_models() -> None:
    text = build_models_route_decision_text(
        {
            "task_type": "simple",
            "route": "haiku",
            "executor": "claude",
            "model": "claude-haiku-4-5-20251001",
            "backup_model": "claude-sonnet-4-6",
            "route_reason": "simple task classification",
        }
    )

    assert "Simple work will start with Claude Haiku 4 5 20251001." in text
    assert "through CLAUDE" in text
    assert "Backup: Claude Sonnet 4 6" in text
    assert "Why: simple task classification" in text


def test_friendly_route_target_formats_provider_and_named_routes() -> None:
    assert friendly_models_route_target("anthropic/claude-haiku") == "ANTHROPIC / claude-haiku"
    assert friendly_models_route_target("local") == "the local model"


def test_route_preview_text_uses_evidence_prefix_for_decision() -> None:
    text = build_models_route_preview_text(
        {"route": "haiku", "task_type": "simple", "route_reason": "classification"},
        health_summary="Cloud path configured | Local runtime OLLAMA heartbeat seen",
    )

    assert "Cloud evidence: Cloud path configured" in text


def test_route_evidence_text_uses_launcher_prefix_for_unknown_routes() -> None:
    text = build_models_route_evidence_text(
        {"route": "pending"},
        health_summary="Cloud path configured | Local runtime OLLAMA heartbeat seen",
    )

    assert text == "Launcher evidence: Cloud path configured | Local runtime OLLAMA heartbeat seen"


def test_route_preview_hint_text_matches_chat_first_guidance() -> None:
    assert "Try the kind of question" in build_models_route_preview_hint_text()
