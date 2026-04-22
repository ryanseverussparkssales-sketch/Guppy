from __future__ import annotations

import importlib


def test_run_spell_uses_specialist_support_for_research(monkeypatch) -> None:
    core = importlib.import_module("src.guppy.merlin.core")

    monkeypatch.setattr(
        core._specialist_support,
        "_research",
        lambda query="", url="": f"research:{query}:{url}",
    )

    result = core.run_spell("research", {"query": "status", "url": ""})

    assert result == "research:status:"


def test_run_spell_still_maps_core_tool_names(monkeypatch) -> None:
    core = importlib.import_module("src.guppy.merlin.core")
    captured: list[tuple[str, dict]] = []

    monkeypatch.setattr(core, "_run_tool", lambda name, payload: captured.append((name, payload)) or "ok")

    result = core.run_spell("scry", {"query": "weather"})

    assert result == "ok"
    assert captured == [("search_web", {"query": "weather"})]


def test_merlin_clear_cache_is_reexported_from_specialist_support() -> None:
    core = importlib.import_module("src.guppy.merlin.core")

    assert core.merlin_clear_cache() == "Analysis cache cleared."
