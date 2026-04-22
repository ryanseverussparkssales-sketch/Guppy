from __future__ import annotations

from pathlib import Path

from src.guppy.experience_config.personalization_storage import (
    load_provider_registry_with_diagnostics,
    normalize_voice_bindings,
)


def test_load_provider_registry_with_diagnostics_repairs_invalid_routes(tmp_path: Path) -> None:
    path = tmp_path / "provider_registry.json"
    path.write_text(
        '{"providers": [{"id": "anthropic", "models": [{"id": "claude-haiku-4-5-20251001"}]}], "routes": {"simple": "bad/route", "complex": 3, "teaching": null, "fallback_chain": ["bad/route"]}}',
        encoding="utf-8",
    )

    data, diagnostics = load_provider_registry_with_diagnostics(path)

    assert data["routes"]["simple"] == "anthropic/claude-haiku-4-5-20251001"
    assert "local/guppy" in data["routes"]["fallback_chain"]
    assert any("routes.simple" in item for item in diagnostics)


def test_normalize_voice_bindings_repairs_invalid_defaults() -> None:
    normalized = normalize_voice_bindings({"defaults": [], "bindings": {"by_model": [], "by_persona": None}, "imports": {}})

    assert normalized["defaults"]["engine"]
    assert normalized["bindings"]["by_model"] == {}
