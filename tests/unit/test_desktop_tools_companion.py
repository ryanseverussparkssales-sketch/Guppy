"""Unit tests for companion desktop control tools.

Covers:
  - desktop_screenshot routes to _sync_read_screen, returns ok+description
  - desktop_click / type / shortcut / scroll gated by GUPPY_DESKTOP_CONTROL
  - desktop_click with description calls screen_parser.ground_click
  - desktop_click with x/y skips ground_click
  - Errors from pyautogui are caught and returned as ok=False
"""
from __future__ import annotations

import asyncio
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── 1. desktop_screenshot ─────────────────────────────────────────────────────

class TestDesktopScreenshot:
    def test_screenshot_returns_description(self):
        from src.guppy.api.tool_executor_companion import _execute_companion_tool
        with patch(
            "src.guppy.api.routes_desktop._sync_read_screen",
            return_value="A browser window with a form visible.",
        ):
            result = _run(_execute_companion_tool("desktop_screenshot", {"question": "What's on screen?"}))
        assert result["ok"] is True
        assert "browser" in result["description"]

    def test_screenshot_default_question_used_when_omitted(self):
        from src.guppy.api.tool_executor_companion import _execute_companion_tool
        with patch(
            "src.guppy.api.routes_desktop._sync_read_screen",
            return_value="Desktop with icons.",
        ) as mock_read:
            _run(_execute_companion_tool("desktop_screenshot", {}))
        # Called with some question (the default) and quality=82
        _, call_args, call_kwargs = mock_read.mock_calls[0]
        assert call_args[1]  # question is non-empty

    def test_screenshot_pyautogui_error_returns_ok_false(self):
        from src.guppy.api.tool_executor_companion import _execute_companion_tool
        from fastapi import HTTPException
        with patch(
            "src.guppy.api.routes_desktop._sync_read_screen",
            side_effect=HTTPException(status_code=503, detail="pyautogui not installed"),
        ):
            result = _run(_execute_companion_tool("desktop_screenshot", {}))
        assert result["ok"] is False
        assert "pyautogui" in result["error"]


# ── 2. Control tool gating ────────────────────────────────────────────────────

class TestDesktopControlGating:
    """click/type/shortcut must return ok=False when GUPPY_DESKTOP_CONTROL is unset."""

    def _without_control(self, name: str, args: dict) -> dict:
        from src.guppy.api.tool_executor_companion import _execute_companion_tool
        env = {k: v for k, v in os.environ.items() if k != "GUPPY_DESKTOP_CONTROL"}
        with patch.dict(os.environ, env, clear=True):
            return _run(_execute_companion_tool(name, args))

    def test_click_gated_without_env(self):
        result = self._without_control("desktop_click", {"x": 100, "y": 200})
        assert result["ok"] is False
        assert "GUPPY_DESKTOP_CONTROL" in result["error"]

    def test_type_gated_without_env(self):
        result = self._without_control("desktop_type", {"text": "hello"})
        assert result["ok"] is False
        assert "GUPPY_DESKTOP_CONTROL" in result["error"]

    def test_shortcut_gated_without_env(self):
        result = self._without_control("desktop_shortcut", {"keys": "ctrl+c"})
        assert result["ok"] is False
        assert "GUPPY_DESKTOP_CONTROL" in result["error"]


# ── 3. desktop_click — coordinate vs grounded ─────────────────────────────────

class TestDesktopClick:
    def _with_control(self, name: str, args: dict) -> dict:
        from src.guppy.api.tool_executor_companion import _execute_companion_tool
        with patch.dict(os.environ, {"GUPPY_DESKTOP_CONTROL": "1"}, clear=False):
            return _run(_execute_companion_tool(name, args))

    def test_click_with_xy_skips_ground_click(self):
        from src.guppy.api.tool_executor_companion import _execute_companion_tool
        with patch.dict(os.environ, {"GUPPY_DESKTOP_CONTROL": "1"}, clear=False), \
             patch("src.guppy.api.routes_desktop._sync_click", return_value="Clicked (100, 200) with left button x1") as mock_click, \
             patch("src.guppy.workspace.screen_parser.ground_click") as mock_ground:
            result = _run(_execute_companion_tool("desktop_click", {"x": 100, "y": 200}))
        mock_click.assert_called_once_with(100, 200, "left", 1, 0.1)
        mock_ground.assert_not_called()
        assert result["ok"] is True

    def test_click_with_description_uses_ground_click(self):
        from src.guppy.api.tool_executor_companion import _execute_companion_tool
        with patch.dict(os.environ, {"GUPPY_DESKTOP_CONTROL": "1"}, clear=False), \
             patch("src.guppy.workspace.screen_parser.ground_click", return_value=(500, 300)) as mock_ground, \
             patch("src.guppy.api.routes_desktop._sync_click", return_value="Clicked (500, 300) with left button x1"):
            result = _run(_execute_companion_tool("desktop_click", {"description": "Submit button"}))
        mock_ground.assert_called_once_with("Submit button")
        assert result["ok"] is True

    def test_click_description_not_found_returns_error(self):
        from src.guppy.api.tool_executor_companion import _execute_companion_tool
        with patch.dict(os.environ, {"GUPPY_DESKTOP_CONTROL": "1"}, clear=False), \
             patch("src.guppy.workspace.screen_parser.ground_click", return_value=None):
            result = _run(_execute_companion_tool("desktop_click", {"description": "invisible widget"}))
        assert result["ok"] is False
        assert "Could not find" in result["error"]


# ── 4. desktop_type ───────────────────────────────────────────────────────────

class TestDesktopType:
    def test_type_calls_sync_type(self):
        from src.guppy.api.tool_executor_companion import _execute_companion_tool
        with patch.dict(os.environ, {"GUPPY_DESKTOP_CONTROL": "1"}, clear=False), \
             patch("src.guppy.api.routes_desktop._sync_type", return_value="Typed 5 characters") as mock_type:
            result = _run(_execute_companion_tool("desktop_type", {"text": "hello"}))
        mock_type.assert_called_once_with("hello", 0.03)
        assert result["ok"] is True

    def test_type_empty_text_returns_error(self):
        from src.guppy.api.tool_executor_companion import _execute_companion_tool
        with patch.dict(os.environ, {"GUPPY_DESKTOP_CONTROL": "1"}, clear=False):
            result = _run(_execute_companion_tool("desktop_type", {"text": ""}))
        assert result["ok"] is False
        assert "text required" in result["error"]


# ── 5. desktop_shortcut ───────────────────────────────────────────────────────

class TestDesktopShortcut:
    def test_shortcut_calls_sync_shortcut(self):
        from src.guppy.api.tool_executor_companion import _execute_companion_tool
        with patch.dict(os.environ, {"GUPPY_DESKTOP_CONTROL": "1"}, clear=False), \
             patch("src.guppy.api.routes_desktop._sync_shortcut", return_value="Pressed: ctrl+c") as mock_sc:
            result = _run(_execute_companion_tool("desktop_shortcut", {"keys": "ctrl+c"}))
        mock_sc.assert_called_once_with("ctrl+c")
        assert result["ok"] is True

    def test_shortcut_empty_keys_returns_error(self):
        from src.guppy.api.tool_executor_companion import _execute_companion_tool
        with patch.dict(os.environ, {"GUPPY_DESKTOP_CONTROL": "1"}, clear=False):
            result = _run(_execute_companion_tool("desktop_shortcut", {"keys": ""}))
        assert result["ok"] is False
        assert "keys required" in result["error"]


# ── 6. desktop_scroll (no GUPPY_DESKTOP_CONTROL gate) ────────────────────────

class TestDesktopScroll:
    def test_scroll_calls_sync_scroll(self):
        from src.guppy.api.tool_executor_companion import _execute_companion_tool
        with patch("src.guppy.api.routes_desktop._sync_scroll", return_value="Scrolled down 3 clicks at (0, 0)") as mock_sc:
            result = _run(_execute_companion_tool("desktop_scroll", {"clicks": -3}))
        mock_sc.assert_called_once_with(0, 0, -3)
        assert result["ok"] is True
