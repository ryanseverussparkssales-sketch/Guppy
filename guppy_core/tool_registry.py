"""
guppy_core/tool_registry.py
Re-export shim — canonical data lives in utils/tool_registry.py.
"""
from __future__ import annotations

from utils.tool_registry import TOOLS, _validate_tool_input  # noqa: F401

__all__ = ["TOOLS", "_validate_tool_input"]
