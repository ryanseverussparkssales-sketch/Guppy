"""Cloud-safe workspace routes.

In the cloud context there is no desktop runtime, so a single default
workspace is returned.  POST creates an in-process entry for the lifetime
of the deployment instance.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["workspaces"])

_DEFAULT_WORKSPACE: dict[str, Any] = {
    "id": "default",
    "name": "Default",
    "description": "Default workspace",
    "created_at": "",
    "is_active": True,
}

_workspaces: dict[str, dict[str, Any]] = {"default": dict(_DEFAULT_WORKSPACE)}


class WorkspaceCreate(BaseModel):
    name: str
    description: str = ""


class WorkspaceUpdate(BaseModel):
    name: str = ""
    description: str = ""


@router.get("/api/workspaces")
async def list_workspaces() -> dict[str, Any]:
    return {"workspaces": list(_workspaces.values()), "total": len(_workspaces)}


@router.post("/api/workspaces")
async def create_workspace(body: WorkspaceCreate) -> dict[str, Any]:
    ws_id = str(uuid.uuid4())[:8]
    ws: dict[str, Any] = {
        "id": ws_id,
        "name": body.name,
        "description": body.description,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "is_active": False,
    }
    _workspaces[ws_id] = ws
    return ws


@router.get("/api/workspaces/{workspace_id}")
async def get_workspace(workspace_id: str) -> dict[str, Any]:
    ws = _workspaces.get(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


@router.put("/api/workspaces/{workspace_id}")
async def update_workspace(workspace_id: str, body: WorkspaceUpdate) -> dict[str, Any]:
    ws = _workspaces.get(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if body.name:
        ws["name"] = body.name
    if body.description:
        ws["description"] = body.description
    return ws


@router.post("/api/workspaces/{workspace_id}/activate")
async def activate_workspace(workspace_id: str) -> dict[str, Any]:
    if workspace_id not in _workspaces:
        raise HTTPException(status_code=404, detail="Workspace not found")
    for ws in _workspaces.values():
        ws["is_active"] = ws["id"] == workspace_id
    return {"ok": True, "active_workspace_id": workspace_id}


@router.delete("/api/workspaces/{workspace_id}")
async def delete_workspace(workspace_id: str) -> dict[str, Any]:
    if workspace_id == "default":
        raise HTTPException(status_code=400, detail="Cannot delete default workspace")
    if workspace_id not in _workspaces:
        raise HTTPException(status_code=404, detail="Workspace not found")
    _workspaces.pop(workspace_id)
    return {"ok": True}
