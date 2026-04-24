"""Tools catalog API: list tool actions from the shared registry.

GET /api/tools  — list all available (non-planned) tool actions, mapped to the
                  web Tool interface (id, name, description, category, isEnabled,
                  parameters, type).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from src.guppy.api.server_context import ServerContext
from src.guppy.launcher_application.tool_action_registry import TOOL_ACTION_REGISTRY


def _registry_to_tool(tool_key: str) -> dict:
    entry = TOOL_ACTION_REGISTRY[tool_key]
    return {
        "id": tool_key,
        "name": entry.label.title(),
        "description": entry.command_hint,
        "category": entry.category.lower(),
        "isEnabled": entry.availability_status != "planned",
        "parameters": {},
        "type": "builtin",
    }


def build_tools_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/tools")

    @router.get("")
    async def list_tools(user_id: str = Depends(ctx.require_rate_limit)):
        del user_id
        return [_registry_to_tool(key) for key in TOOL_ACTION_REGISTRY]

    return router


__all__ = ["build_tools_router"]
