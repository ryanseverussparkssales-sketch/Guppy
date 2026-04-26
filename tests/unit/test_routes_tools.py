from __future__ import annotations

from src.guppy.api.routes_tools import _registry_to_tool
from src.guppy.launcher_application.tool_action_registry import TOOL_ACTION_REGISTRY


def test_registry_to_tool_maps_available_entry_correctly() -> None:
    tool = _registry_to_tool("read_file")

    assert tool["id"] == "read_file"
    assert tool["name"] == "Read File"
    assert tool["description"] == "Read this file"
    assert tool["category"] == "read"
    assert tool["isEnabled"] is True
    assert tool["type"] == "builtin"
    assert tool["parameters"] == {}


def test_registry_to_tool_marks_planned_entry_as_disabled() -> None:
    tool = _registry_to_tool("voip_place_call")

    assert tool["id"] == "voip_place_call"
    assert tool["isEnabled"] is False


def test_registry_to_tool_covers_all_registry_keys() -> None:
    for key in TOOL_ACTION_REGISTRY:
        tool = _registry_to_tool(key)
        assert tool["id"] == key
        assert tool["name"]
        assert tool["category"]
        assert tool["type"] == "builtin"
