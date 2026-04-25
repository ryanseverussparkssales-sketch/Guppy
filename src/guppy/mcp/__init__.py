"""Guppy MCP plugin layer — Model Context Protocol client and registry."""
from .manager import MCPPluginManager, get_mcp_manager

__all__ = ["MCPPluginManager", "get_mcp_manager"]
