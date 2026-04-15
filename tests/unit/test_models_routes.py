from ui.launcher.views.models_view import ModelsView


def test_route_targets_from_registry_extracts_unique_sorted_targets() -> None:
    registry = {
        "providers": [
            {
                "id": "anthropic",
                "models": [{"id": "claude-haiku"}, {"id": "claude-sonnet"}],
            },
            {
                "id": "openai",
                "models": [{"id": "gpt-4o"}, {"id": "gpt-4o"}],
            },
            {"id": "broken", "models": ["not-a-dict"]},
            "not-a-provider",
        ]
    }

    assert ModelsView._route_targets_from_registry(registry) == [
        "anthropic/claude-haiku",
        "anthropic/claude-sonnet",
        "openai/gpt-4o",
    ]


def test_parse_fallback_chain_trims_and_ignores_empty_tokens() -> None:
    assert ModelsView._parse_fallback_chain("anthropic/claude-haiku, , local/guppy ,") == [
        "anthropic/claude-haiku",
        "local/guppy",
    ]


def test_describe_route_decision_surfaces_reason_and_models() -> None:
    text = ModelsView._describe_route_decision(
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
    assert ModelsView._friendly_route_target("anthropic/claude-haiku") == "ANTHROPIC / claude-haiku"
    assert ModelsView._friendly_route_target("local") == "the local model"


def test_route_evidence_for_decision_uses_live_environment_words() -> None:
    view = ModelsView()

    text = view._route_evidence_for_decision({"route": "haiku"})

    assert "Cloud evidence:" in text
    assert "Cloud path" in text
