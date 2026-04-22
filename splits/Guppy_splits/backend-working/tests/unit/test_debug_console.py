from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QTabWidget, QTextEdit

from src.guppy.debug import DebugConsole, open_debug_console
from src.guppy.debug._tabs import _format_log_lines


@pytest.fixture(scope="module", autouse=True)
def _qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_debug_console_builds_expected_tabs_and_clean_strings() -> None:
    console = DebugConsole()

    assert console.windowTitle() == "Debug Console"
    tabs = console.findChild(QTabWidget)
    assert tabs is not None
    assert [tabs.tabText(index) for index in range(tabs.count())] == ["Status", "Memory", "Emergency", "Voice", "Logs"]

    placeholders = [widget.placeholderText() for widget in console.findChildren(QTextEdit)]
    assert "System prompt loaded here..." in placeholders
    assert "Transcribed text will appear here..." in placeholders
    assert all(all(ord(char) < 128 for char in text) for text in placeholders)
    console.close()


def test_open_debug_console_returns_visible_console_instance() -> None:
    console = open_debug_console()

    assert isinstance(console, DebugConsole)
    assert console.isVisible()
    console.close()


def test_format_log_lines_uses_ascii_arrow_and_empty_state() -> None:
    assert _format_log_lines([]) == "No tool calls recorded yet."

    rendered = _format_log_lines(
        [{"time": "10:00", "tool": "search", "args": "birds", "result": "done"}]
    )

    assert "-> done" in rendered
    assert all(ord(char) < 128 for char in rendered)
