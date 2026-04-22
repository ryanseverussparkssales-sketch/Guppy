"""Workspace management API — organize conversations and context.

GET  /api/workspaces              — list all workspaces
POST /api/workspaces              — create new workspace { name: string, description?: string }
GET  /api/workspaces/{id}         — get workspace details
PUT  /api/workspaces/{id}         — update workspace
DELETE /api/workspaces/{id}       — delete workspace
GET  /api/workspaces/active       — get currently active workspace
POST /api/workspaces/{id}/activate — set as active workspace
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from src.guppy.api.server_context import ServerContext


class WorkspaceDB:
    """Simple SQLite-based workspace storage."""

    def __init__(self, db_path: str = "workspaces.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema if not exists."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workspaces (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    is_active INTEGER DEFAULT 0
                )
                """
            )
            conn.commit()

    def list_workspaces(self) -> List[Dict[str, Any]]:
        """Get all workspaces."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM workspaces ORDER BY created_at DESC").fetchall()
            return [dict(row) for row in rows]

    def get_workspace(self, ws_id: str) -> Optional[Dict[str, Any]]:
        """Get a single workspace by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM workspaces WHERE id = ?", (ws_id,)).fetchone()
            return dict(row) if row else None

    def create_workspace(self, name: str, description: str = "") -> Dict[str, Any]:
        """Create a new workspace."""
        ws_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO workspaces (id, name, description, created_at, updated_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (ws_id, name, description, now, now, 0),
            )
            conn.commit()
        return {"id": ws_id, "name": name, "description": description, "created_at": now, "updated_at": now, "is_active": False}

    def update_workspace(self, ws_id: str, name: Optional[str] = None, description: Optional[str] = None) -> Dict[str, Any]:
        """Update workspace metadata."""
        ws = self.get_workspace(ws_id)
        if not ws:
            raise ValueError(f"Workspace {ws_id} not found")

        now = datetime.utcnow().isoformat()
        updates = {"updated_at": now}
        if name is not None:
            updates["name"] = name
        if description is not None:
            updates["description"] = description

        update_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [ws_id]

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(f"UPDATE workspaces SET {update_clause} WHERE id = ?", values)
            conn.commit()

        return self.get_workspace(ws_id)

    def delete_workspace(self, ws_id: str) -> bool:
        """Delete a workspace."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM workspaces WHERE id = ?", (ws_id,))
            conn.commit()
        return True

    def set_active_workspace(self, ws_id: str) -> None:
        """Set workspace as active (only one active at a time)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE workspaces SET is_active = 0")
            conn.execute("UPDATE workspaces SET is_active = 1 WHERE id = ?", (ws_id,))
            conn.commit()

    def get_active_workspace(self) -> Optional[Dict[str, Any]]:
        """Get the currently active workspace."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM workspaces WHERE is_active = 1").fetchone()
            return dict(row) if row else None


# Global DB instance
_workspace_db = WorkspaceDB()


def build_workspaces_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/workspaces")

    @router.get("")
    async def list_workspaces(user_id: str = Depends(ctx.require_rate_limit)):
        """List all workspaces."""
        del user_id
        workspaces = _workspace_db.list_workspaces()
        active = _workspace_db.get_active_workspace()
        return {
            "workspaces": workspaces,
            "active_id": active["id"] if active else None,
            "count": len(workspaces),
        }

    @router.post("")
    async def create_workspace(
        payload: Dict[str, str],
        user_id: str = Depends(ctx.require_rate_limit),
    ):
        """Create a new workspace."""
        del user_id
        name = payload.get("name", "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="workspace name required")

        description = payload.get("description", "").strip()
        workspace = _workspace_db.create_workspace(name, description)
        return workspace

    @router.get("/{ws_id}")
    async def get_workspace(ws_id: str, user_id: str = Depends(ctx.require_rate_limit)):
        """Get workspace details."""
        del user_id
        ws = _workspace_db.get_workspace(ws_id)
        if not ws:
            raise HTTPException(status_code=404, detail="workspace not found")
        return ws

    @router.put("/{ws_id}")
    async def update_workspace(
        ws_id: str,
        payload: Dict[str, str],
        user_id: str = Depends(ctx.require_rate_limit),
    ):
        """Update workspace metadata."""
        del user_id
        try:
            ws = _workspace_db.update_workspace(
                ws_id,
                name=payload.get("name"),
                description=payload.get("description"),
            )
            return ws
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @router.delete("/{ws_id}")
    async def delete_workspace(ws_id: str, user_id: str = Depends(ctx.require_rate_limit)):
        """Delete a workspace."""
        del user_id
        try:
            _workspace_db.delete_workspace(ws_id)
            return {"deleted": ws_id}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/{ws_id}/activate")
    async def activate_workspace(ws_id: str, user_id: str = Depends(ctx.require_rate_limit)):
        """Set workspace as active."""
        del user_id
        ws = _workspace_db.get_workspace(ws_id)
        if not ws:
            raise HTTPException(status_code=404, detail="workspace not found")

        _workspace_db.set_active_workspace(ws_id)
        return {"active": ws_id}

    @router.get("/active/current")
    async def get_active_workspace(user_id: str = Depends(ctx.require_rate_limit)):
        """Get currently active workspace."""
        del user_id
        ws = _workspace_db.get_active_workspace()
        if not ws:
            raise HTTPException(status_code=404, detail="no active workspace")
        return ws

    return router
