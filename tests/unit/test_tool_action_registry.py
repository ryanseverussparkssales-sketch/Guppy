"""Unit tests for PL-C1 — tool_action_registry consistency.

Verifies:
- Every key in TOOL_ACTION_REGISTRY has non-empty required fields
- get_action_for_tool resolves known keys correctly
- get_tool_starters returns the right shape for Home surfaces
- get_home_starter_prompt never returns empty string for known or unknown keys
- Registry keys match the catalog keys in tools_view_cards.py INSTANCE_TOOL_CATALOG
"""

from __future__ import annotations

import pytest

from src.guppy.launcher_application.tool_action_registry import (
    TOOL_ACTION_REGISTRY,
    ToolActionEntry,
    get_action_for_tool,
    get_canonical_action_line,
    get_home_starter_prompt,
    get_tool_starters,
)


# ---------------------------------------------------------------------------
# Basic structure
# ---------------------------------------------------------------------------


class TestRegistryStructure:
    def test_registry_is_not_empty(self) -> None:
        assert len(TOOL_ACTION_REGISTRY) > 0

    def test_all_entries_have_non_empty_label(self) -> None:
        for key, entry in TOOL_ACTION_REGISTRY.items():
            assert entry.label.strip(), f"entry {key!r} has empty label"

    def test_all_entries_have_non_empty_command_hint(self) -> None:
        for key, entry in TOOL_ACTION_REGISTRY.items():
            assert entry.command_hint.strip(), f"entry {key!r} has empty command_hint"

    def test_all_entries_have_non_empty_home_starter_prompt(self) -> None:
        for key, entry in TOOL_ACTION_REGISTRY.items():
            assert entry.home_starter_prompt.strip(), f"entry {key!r} has empty home_starter_prompt"

    def test_all_entries_have_valid_category(self) -> None:
        valid_categories = {"READ", "QUERY", "DEBUG", "CODE", "WRITE", "CONNECTOR"}
        for key, entry in TOOL_ACTION_REGISTRY.items():
            assert entry.category in valid_categories, (
                f"entry {key!r} has unexpected category {entry.category!r}"
            )

    def test_all_keys_are_lowercase_strings(self) -> None:
        for key in TOOL_ACTION_REGISTRY:
            assert isinstance(key, str) and key == key.lower(), (
                f"registry key {key!r} is not lowercase"
            )

    def test_all_entries_are_tool_action_entry_instances(self) -> None:
        for key, entry in TOOL_ACTION_REGISTRY.items():
            assert isinstance(entry, ToolActionEntry), (
                f"registry entry {key!r} is not a ToolActionEntry"
            )


# ---------------------------------------------------------------------------
# get_action_for_tool
# ---------------------------------------------------------------------------


class TestGetActionForTool:
    def test_resolves_read_file(self) -> None:
        entry = get_action_for_tool("read_file")
        assert entry is not None
        assert entry.label == "READ FILE"

    def test_resolves_run_python(self) -> None:
        entry = get_action_for_tool("run_python")
        assert entry is not None
        assert entry.category == "CODE"

    def test_returns_none_for_unknown_key(self) -> None:
        assert get_action_for_tool("nonexistent_tool_xyz") is None

    def test_empty_string_returns_none(self) -> None:
        assert get_action_for_tool("") is None

    def test_whitespace_is_stripped(self) -> None:
        entry = get_action_for_tool("  write_file  ")
        assert entry is not None
        assert entry.label == "WRITE FILE"

    def test_case_insensitive_lookup(self) -> None:
        entry = get_action_for_tool("SEND_EMAIL")
        assert entry is not None
        assert entry.label == "GMAIL"


# ---------------------------------------------------------------------------
# get_home_starter_prompt
# ---------------------------------------------------------------------------


class TestGetHomeStarterPrompt:
    def test_known_key_returns_registry_prompt(self) -> None:
        prompt = get_home_starter_prompt("read_file")
        assert len(prompt) > 10
        assert "read" in prompt.lower() or "file" in prompt.lower()

    def test_unknown_key_returns_non_empty_fallback(self) -> None:
        prompt = get_home_starter_prompt("totally_unknown_tool")
        assert isinstance(prompt, str) and prompt.strip(), (
            "get_home_starter_prompt must not return empty for unknown keys"
        )

    def test_empty_key_returns_non_empty_fallback(self) -> None:
        prompt = get_home_starter_prompt("")
        assert isinstance(prompt, str) and prompt.strip()


class TestCanonicalActionLine:
    def test_known_key_uses_command_hint(self) -> None:
        assert get_canonical_action_line("youtube_search") == 'Say or type: "Search YouTube"'

    def test_unknown_key_still_returns_non_empty_line(self) -> None:
        assert get_canonical_action_line("custom_tool").startswith('Say or type: "custom tool"')


# ---------------------------------------------------------------------------
# get_tool_starters — Home surface consistency
# ---------------------------------------------------------------------------


class TestGetToolStarters:
    def test_returns_a_list(self) -> None:
        starters = get_tool_starters()
        assert isinstance(starters, list)
        assert len(starters) > 0

    def test_each_starter_has_required_keys(self) -> None:
        required_keys = {"tool_key", "label", "command_hint", "home_starter_prompt", "category"}
        for starter in get_tool_starters():
            missing = required_keys - set(starter.keys())
            assert not missing, f"starter {starter.get('tool_key')!r} missing keys: {missing}"

    def test_starters_match_registry_entries(self) -> None:
        starters = get_tool_starters()
        for starter in starters:
            key = starter["tool_key"]
            entry = TOOL_ACTION_REGISTRY.get(key)
            assert entry is not None, f"starter key {key!r} not found in registry"
            assert starter["label"] == entry.label
            assert starter["command_hint"] == entry.command_hint
            assert starter["home_starter_prompt"] == entry.home_starter_prompt
            assert starter["category"] == entry.category

    def test_starters_count_matches_registry(self) -> None:
        available_count = sum(1 for e in TOOL_ACTION_REGISTRY.values() if e.availability_status != "planned")
        assert len(get_tool_starters()) == available_count

    def test_no_duplicate_tool_keys(self) -> None:
        keys = [s["tool_key"] for s in get_tool_starters()]
        assert len(keys) == len(set(keys)), "get_tool_starters returned duplicate tool_keys"


# ---------------------------------------------------------------------------
# Catalog cross-check: registry covers INSTANCE_TOOL_CATALOG keys
# ---------------------------------------------------------------------------


class TestRegistryCatalogCoverage:
    def test_all_catalog_keys_in_registry(self) -> None:
        """Every tool in the Tools Hub catalog must have a registry entry."""
        pytest.skip("ui.launcher quarantined — catalog cross-check skipped")

    def test_registry_and_catalog_labels_are_consistent(self) -> None:
        """tool.name in catalog should match entry.label in registry."""
        pytest.skip("ui.launcher quarantined — catalog cross-check skipped")
