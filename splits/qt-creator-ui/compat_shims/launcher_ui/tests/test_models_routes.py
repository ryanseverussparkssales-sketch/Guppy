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
