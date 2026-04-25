"""MCP Plugin Manager API — manage Model Context Protocol server connections.

GET    /api/mcp/servers                        — list all registered servers
POST   /api/mcp/servers                        — add a custom server
GET    /api/mcp/servers/{id}                   — get server details
PUT    /api/mcp/servers/{id}/env               — update env vars / credentials
DELETE /api/mcp/servers/{id}                   — remove a custom server
POST   /api/mcp/servers/{id}/enable            — enable + connect
POST   /api/mcp/servers/{id}/disable           — disable + disconnect
POST   /api/mcp/servers/{id}/test              — test connection
GET    /api/mcp/servers/{id}/tools             — list tools from server
GET    /api/mcp/tools                          — all enabled-server tools in LLM format
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.guppy.api.server_context import ServerContext
from src.guppy.mcp.manager import get_mcp_manager


class AddServerRequest(BaseModel):
    id: str
    name: str
    description: str = ""
    command: str
    args: List[str] = []
    envVars: Dict[str, str] = {}


class UpdateEnvRequest(BaseModel):
    envVars: Dict[str, str]


_ID_RE = re.compile(r'^[a-z0-9_-]{1,64}$')


def build_mcp_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/mcp")
    mgr = get_mcp_manager()

    @router.get("/servers")
    async def list_servers(_uid: str = Depends(ctx.require_rate_limit)):
        return await mgr.list_servers()

    @router.post("/servers", status_code=201)
    async def add_server(body: AddServerRequest, _uid: str = Depends(ctx.require_rate_limit)):
        if not _ID_RE.match(body.id):
            raise HTTPException(status_code=422, detail="id must be lowercase alphanumeric/dash/underscore, max 64 chars")
        return await mgr.add_server(body.id, body.name, body.description, body.command, body.args, body.envVars)

    @router.get("/servers/{server_id}")
    async def get_server(server_id: str, _uid: str = Depends(ctx.require_rate_limit)):
        servers = await mgr.list_servers()
        match = next((s for s in servers if s["id"] == server_id), None)
        if not match:
            raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found")
        return match

    @router.put("/servers/{server_id}/env")
    async def update_env(server_id: str, body: UpdateEnvRequest, _uid: str = Depends(ctx.require_rate_limit)):
        try:
            return await mgr.update_env_vars(server_id, body.envVars)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found")

    @router.delete("/servers/{server_id}", status_code=204)
    async def delete_server(server_id: str, _uid: str = Depends(ctx.require_rate_limit)):
        servers = await mgr.list_servers()
        match = next((s for s in servers if s["id"] == server_id), None)
        if not match:
            raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found")
        if match.get("isPreset"):
            raise HTTPException(status_code=400, detail="Cannot delete preset servers — use disable instead")
        await mgr.delete_server(server_id)

    @router.post("/servers/{server_id}/enable")
    async def enable_server(server_id: str, _uid: str = Depends(ctx.require_rate_limit)):
        try:
            return await mgr.set_enabled(server_id, True)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found")

    @router.post("/servers/{server_id}/disable")
    async def disable_server(server_id: str, _uid: str = Depends(ctx.require_rate_limit)):
        try:
            return await mgr.set_enabled(server_id, False)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found")

    @router.post("/servers/{server_id}/test")
    async def test_server(server_id: str, _uid: str = Depends(ctx.require_rate_limit)):
        return await mgr.test_server(server_id)

    @router.get("/servers/{server_id}/tools")
    async def list_server_tools(server_id: str, _uid: str = Depends(ctx.require_rate_limit)):
        tools = await mgr.get_tools(server_id)
        return {"serverId": server_id, "tools": tools}

    @router.get("/tools")
    async def list_all_tools(_uid: str = Depends(ctx.require_rate_limit)):
        return await mgr.get_tools_for_llm()

    return router
