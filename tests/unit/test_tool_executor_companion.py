"""Unit tests for the companion tool executor.

Covers:
  - Tool alias resolution (semantic_remember → memory_write, fetch_url → web_fetch, etc.)
  - Required-field validation and error path behaviour
  - get_time always succeeds
"""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── Helpers ──────────────────────────────────────────────────────────────────

def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── 1. Alias resolution ────────────────────────────────────────────────────

class TestToolAliases:
    """Deprecated / alternate tool names must resolve silently to canonical names."""

    def test_fetch_url_resolves_to_web_fetch(self):
        from src.guppy.api.tool_executor_companion import _execute_companion_tool
        with patch(
            "src.guppy.api.web_fetch_safe.safe_web_fetch",
            new_callable=AsyncMock,
            return_value={"ok": True, "text": "pong", "url": "http://example.com"},
        ) as mock_fetch:
            result = _run(_execute_companion_tool("fetch_url", {"url": "http://example.com"}))
        assert result["ok"] is True
        mock_fetch.assert_called_once()

    def test_semantic_remember_resolves_to_memory_write(self):
        from src.guppy.api.tool_executor_companion import _execute_companion_tool
        with patch(
            "src.guppy.memory.semantic.remember_semantic",
            return_value="stored",
        ) as mock_store:
            result = _run(_execute_companion_tool(
                "semantic_remember",
                {"key": "coffee_pref", "value": "dark roast"},
            ))
        assert result["ok"] is True
        mock_store.assert_called_once()

    def test_memory_read_resolves_to_memory_recall(self):
        from src.guppy.api.tool_executor_companion import _execute_companion_tool
        with patch(
            "src.guppy.memory.semantic.recall_semantic",
            return_value="Semantic recall results:\n- coffee_pref [preference]: dark roast",
        ):
            result = _run(_execute_companion_tool("memory_read", {"query": "coffee"}))
        assert result["ok"] is True
        assert "dark roast" in result["recalled"]

    def test_remember_resolves_to_memory_write(self):
        from src.guppy.api.tool_executor_companion import _execute_companion_tool
        with patch("src.guppy.memory.semantic.remember_semantic", return_value="stored"):
            result = _run(_execute_companion_tool(
                "remember", {"key": "fact", "value": "something"},
            ))
        assert result["ok"] is True

    def test_recall_resolves_to_memory_recall(self):
        from src.guppy.api.tool_executor_companion import _execute_companion_tool
        with patch("src.guppy.memory.semantic.recall_semantic", return_value="found: something"):
            result = _run(_execute_companion_tool("recall", {"query": "something"}))
        assert result["ok"] is True

    def test_unknown_tool_returns_error(self):
        from src.guppy.api.tool_executor_companion import _execute_companion_tool
        result = _run(_execute_companion_tool("totally_fake_tool", {}))
        assert result["ok"] is False
        assert "Unknown tool" in result["error"]


# ── 2. Required-field validation ──────────────────────────────────────────

class TestToolErrorPaths:
    """Tools must reject missing/empty required fields with ok=False."""

    def test_web_fetch_empty_url(self):
        from src.guppy.api.tool_executor_companion import _execute_companion_tool
        with patch(
            "src.guppy.api.web_fetch_safe.safe_web_fetch",
            new_callable=AsyncMock,
            return_value={"ok": False, "error": "url required"},
        ):
            result = _run(_execute_companion_tool("web_fetch", {"url": ""}))
        # Either the tool executor itself rejects it, or safe_web_fetch does
        assert result["ok"] is False

    def test_memory_write_missing_value(self):
        from src.guppy.api.tool_executor_companion import _execute_companion_tool
        result = _run(_execute_companion_tool("memory_write", {"key": "k", "value": ""}))
        assert result["ok"] is False
        assert "value required" in result["error"]

    def test_memory_write_no_args(self):
        from src.guppy.api.tool_executor_companion import _execute_companion_tool
        result = _run(_execute_companion_tool("memory_write", {}))
        assert result["ok"] is False

    def test_memory_recall_empty_query(self):
        from src.guppy.api.tool_executor_companion import _execute_companion_tool
        result = _run(_execute_companion_tool("memory_recall", {"query": ""}))
        assert result["ok"] is False
        assert "query required" in result["error"]

    def test_create_reminder_missing_message(self):
        from src.guppy.api.tool_executor_companion import _execute_companion_tool
        result = _run(_execute_companion_tool("create_reminder", {}))
        assert result["ok"] is False
        assert "message required" in result["error"]

    def test_download_media_empty_url(self):
        from src.guppy.api.tool_executor_companion import _execute_companion_tool
        result = _run(_execute_companion_tool("download_media", {"url": ""}))
        assert result["ok"] is False
        assert "url required" in result["error"]


# ── 3. get_time always succeeds ───────────────────────────────────────────

class TestGetTime:
    def test_get_time_returns_time_and_date(self):
        from src.guppy.api.tool_executor_companion import _execute_companion_tool
        result = _run(_execute_companion_tool("get_time", {}))
        assert result["ok"] is True
        assert "time" in result
        assert "date" in result
        assert "iso" in result

    def test_get_time_alias_not_needed(self):
        """get_time has no alias — calling it directly must work."""
        from src.guppy.api.tool_executor_companion import _TOOL_ALIASES
        assert "get_time" not in _TOOL_ALIASES


# ── 4. Alias table completeness ───────────────────────────────────────────

class TestAliasTable:
    def test_all_aliases_resolve_to_known_tools(self):
        """Every alias target must be a real, implemented tool."""
        from src.guppy.api.tool_executor_companion import _TOOL_ALIASES
        known_tools = {
            "web_fetch", "web_search", "create_reminder", "download_media",
            "memory_write", "memory_recall", "workspace_task", "cancel_workspace_task",
            "list_workspace_tasks", "get_time", "promote_durable_chat_memory",
        }
        for alias, target in _TOOL_ALIASES.items():
            assert target in known_tools, (
                f"Alias {alias!r} → {target!r} points to an unknown tool"
            )

    def test_no_self_referential_aliases(self):
        from src.guppy.api.tool_executor_companion import _TOOL_ALIASES
        for alias, target in _TOOL_ALIASES.items():
            assert alias != target, f"Alias {alias!r} points to itself"
