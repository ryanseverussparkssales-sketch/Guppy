"""Tools management API — list, enable, disable, create, update, and delete tools.

GET    /tools              — list all tools with enabled state
POST   /tools/:id/enable   — enable a tool
POST   /tools/:id/disable  — disable a tool
POST   /tools              — create a custom tool
PUT    /tools/:id          — update a custom tool
DELETE /tools/:id          — delete a custom tool
"""
from __future__ import annotations

import asyncio
import re
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.guppy.api.server_context import ServerContext
from src.guppy.paths import ensure_user_data_dir


_SCHEMA = """
CREATE TABLE IF NOT EXISTS tools (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL,
    category    TEXT NOT NULL,
    type        TEXT NOT NULL DEFAULT 'builtin',
    parameters  TEXT NOT NULL DEFAULT '{}',
    is_enabled  INTEGER NOT NULL DEFAULT 1
);
"""

_SEED_TOOLS = [
    # ── Search & Web ─────────────────────────────────────────────────────────
    ("web_search",      "Web Search",       "Search the web for current information",                             "search",  "builtin", '{"type":"object","properties":{"query":{"type":"string"},"maxResults":{"type":"number","default":10}},"required":["query"]}', 1),
    ("fetch_url",       "Fetch URL",        "Download content from a URL",                                        "search",  "builtin", '{"type":"object","properties":{"url":{"type":"string"},"format":{"type":"string","enum":["text","html","json"],"default":"text"}},"required":["url"]}', 1),
    ("get_news",        "Get News",         "Retrieve recent news headlines on a topic",                          "search",  "builtin", '{"type":"object","properties":{"topic":{"type":"string"},"max_results":{"type":"number","default":5}},"required":["topic"]}', 1),
    ("get_weather",     "Weather",          "Get current weather and forecasts for a location",                   "search",  "builtin", '{"type":"object","properties":{"location":{"type":"string"}},"required":["location"]}', 1),
    ("api_request",     "API Request",      "Make HTTP requests to external APIs",                                "search",  "builtin", '{"type":"object","properties":{"url":{"type":"string"},"method":{"type":"string","enum":["GET","POST","PUT","DELETE"],"default":"GET"},"headers":{"type":"object"},"body":{"type":"string"}},"required":["url"]}', 1),
    # ── File & Shell ─────────────────────────────────────────────────────────
    ("read_file",       "Read File",        "Read contents from a local file",                                    "file",    "builtin", '{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}', 1),
    ("write_file",      "Write File",       "Write or overwrite a local file",                                    "file",    "builtin", '{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}', 0),
    ("list_directory",  "List Directory",   "List files and folders in a directory",                              "file",    "builtin", '{"type":"object","properties":{"path":{"type":"string","default":"."}},"required":[]}', 1),
    ("apply_patch",     "Apply Patch",      "Apply a unified diff patch to a file",                               "file",    "builtin", '{"type":"object","properties":{"path":{"type":"string"},"patch":{"type":"string"}},"required":["path","patch"]}', 0),
    ("execute_command", "Shell Command",    "Execute a shell command (PowerShell/bash)",                          "system",  "builtin", '{"type":"object","properties":{"command":{"type":"string"},"timeout":{"type":"number","default":30}},"required":["command"]}', 0),
    ("code_execution",  "Code Execution",   "Execute Python code in a sandboxed environment",                     "code",    "builtin", '{"type":"object","properties":{"code":{"type":"string"},"timeout":{"type":"number","default":30}},"required":["code"]}', 1),
    # ── Desktop Vision & Control ─────────────────────────────────────────────
    ("screenshot",      "Screenshot",       "Capture the current screen as an image",                             "desktop", "builtin", '{"type":"object","properties":{"save_path":{"type":"string","description":"Optional file path to save"}}}', 1),
    ("mouse_click",     "Mouse Click",      "Click the mouse at specific screen coordinates",                     "desktop", "builtin", '{"type":"object","properties":{"x":{"type":"integer"},"y":{"type":"integer"},"button":{"type":"string","enum":["left","right","middle"],"default":"left"},"clicks":{"type":"integer","default":1}},"required":["x","y"]}', 1),
    ("mouse_move",      "Mouse Move",       "Move the mouse cursor to screen coordinates",                        "desktop", "builtin", '{"type":"object","properties":{"x":{"type":"integer"},"y":{"type":"integer"},"duration":{"type":"number","default":0.3}},"required":["x","y"]}', 1),
    ("keyboard_type",   "Keyboard Type",    "Type text using the keyboard",                                       "desktop", "builtin", '{"type":"object","properties":{"text":{"type":"string"},"interval":{"type":"number","default":0.03}},"required":["text"]}', 1),
    ("keyboard_shortcut","Keyboard Shortcut","Send a keyboard shortcut (e.g. ctrl+c, win+d)",                    "desktop", "builtin", '{"type":"object","properties":{"keys":{"type":"string","description":"Keys joined by + e.g. ctrl+c"}},"required":["keys"]}', 1),
    ("get_screen_info", "Screen Info",      "Get screen resolution and current cursor position",                  "desktop", "builtin", '{"type":"object","properties":{}}', 1),
    ("read_screen_text","Read Screen Text", "Capture screen region and extract/describe text using vision AI",    "vision",  "builtin", '{"type":"object","properties":{"region":{"type":"string","enum":["full","top","bottom","left","right","active_window"],"default":"full"},"instruction":{"type":"string","default":"Extract all visible text"}},"required":[]}', 1),
    ("open_application","Open Application", "Open an application or URL",                                         "desktop", "builtin", '{"type":"object","properties":{"target":{"type":"string","description":"App name or URL"}},"required":["target"]}', 1),
    # ── Communication ─────────────────────────────────────────────────────────
    ("draft_email",     "Draft Email",      "Open Gmail compose with pre-filled recipient, subject, and body",    "comms",   "builtin", '{"type":"object","properties":{"to":{"type":"string"},"subject":{"type":"string"},"body":{"type":"string"}}}', 1),
    ("open_gmail",      "Open Gmail",       "Open Gmail inbox or compose window",                                 "comms",   "builtin", '{"type":"object","properties":{"compose":{"type":"boolean","default":false},"to":{"type":"string"},"subject":{"type":"string"},"body":{"type":"string"}}}', 1),
    # ── Memory ────────────────────────────────────────────────────────────────
    ("remember",        "Remember",         "Store a key-value fact in persistent memory",                        "memory",  "builtin", '{"type":"object","properties":{"key":{"type":"string"},"value":{"type":"string"}},"required":["key","value"]}', 1),
    ("recall",          "Recall",           "Retrieve a previously stored fact by key",                           "memory",  "builtin", '{"type":"object","properties":{"key":{"type":"string"}},"required":["key"]}', 1),
    # ── Tasks ─────────────────────────────────────────────────────────────────
    ("add_task",        "Add Task",         "Add a task to the task list",                                        "tasks",   "builtin", '{"type":"object","properties":{"task":{"type":"string"},"due":{"type":"string"},"priority":{"type":"string","enum":["low","normal","high"],"default":"normal"}},"required":["task"]}', 1),
    ("get_tasks",       "Get Tasks",        "List pending tasks",                                                 "tasks",   "builtin", '{"type":"object","properties":{"status":{"type":"string","enum":["pending","all","done"],"default":"pending"}}}', 1),
    ("complete_task",   "Complete Task",    "Mark a task as complete",                                            "tasks",   "builtin", '{"type":"object","properties":{"task_id":{"type":"string"}},"required":["task_id"]}', 1),
    # ── Media ─────────────────────────────────────────────────────────────────
    ("spotify",         "Spotify",          "Control Spotify playback and search music",                          "media",   "builtin", '{"type":"object","properties":{"action":{"type":"string","description":"play/pause/next/search/volume"},"query":{"type":"string"}},"required":["action"]}', 0),
]


def _db_path() -> str:
    return str(ensure_user_data_dir() / "tools.db")


def _init_db() -> None:
    with sqlite3.connect(_db_path()) as conn:
        conn.executescript(_SCHEMA)
        existing = {row[0] for row in conn.execute("SELECT id FROM tools").fetchall()}
        for row in _SEED_TOOLS:
            if row[0] not in existing:
                conn.execute(
                    "INSERT INTO tools (id, name, description, category, type, parameters, is_enabled) VALUES (?,?,?,?,?,?,?)",
                    row,
                )
        conn.commit()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    import json
    return {
        "id":          row["id"],
        "name":        row["name"],
        "description": row["description"],
        "category":    row["category"],
        "type":        row["type"],
        "parameters":  json.loads(row["parameters"] or "{}"),
        "isEnabled":   bool(row["is_enabled"]),
    }


def _get_all() -> list[dict[str, Any]]:
    with sqlite3.connect(_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        return [_row_to_dict(r) for r in conn.execute("SELECT * FROM tools ORDER BY category, name").fetchall()]


def _create_custom(name: str, description: str, category: str) -> dict[str, Any]:
    base_id = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')[:40] or "custom_tool"
    with sqlite3.connect(_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        existing = {r[0] for r in conn.execute("SELECT id FROM tools").fetchall()}
        tool_id, suffix = base_id, 1
        while tool_id in existing:
            tool_id = f"{base_id}_{suffix}"
            suffix += 1
        conn.execute(
            "INSERT INTO tools (id, name, description, category, type, parameters, is_enabled) VALUES (?,?,?,?,?,?,?)",
            (tool_id, name, description, category, "custom", "{}", 1),
        )
        conn.commit()
        return _row_to_dict(conn.execute("SELECT * FROM tools WHERE id = ?", (tool_id,)).fetchone())


def _update_custom(tool_id: str, name: str, description: str, category: str) -> dict[str, Any]:
    with sqlite3.connect(_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT type FROM tools WHERE id = ?", (tool_id,)).fetchone()
        if not row or row[0] != "custom":
            raise KeyError(tool_id)
        conn.execute(
            "UPDATE tools SET name=?, description=?, category=? WHERE id=?",
            (name, description, category, tool_id),
        )
        conn.commit()
        return _row_to_dict(conn.execute("SELECT * FROM tools WHERE id = ?", (tool_id,)).fetchone())


def _delete_custom(tool_id: str) -> bool:
    with sqlite3.connect(_db_path()) as conn:
        row = conn.execute("SELECT type FROM tools WHERE id = ?", (tool_id,)).fetchone()
        if not row or row[0] != "custom":
            return False
        conn.execute("DELETE FROM tools WHERE id = ?", (tool_id,))
        conn.commit()
        return True


def _set_enabled(tool_id: str, enabled: bool) -> dict[str, Any]:
    with sqlite3.connect(_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("UPDATE tools SET is_enabled = ? WHERE id = ?", (int(enabled), tool_id))
        conn.commit()
        row = conn.execute("SELECT * FROM tools WHERE id = ?", (tool_id,)).fetchone()
        if not row:
            raise KeyError(tool_id)
        return _row_to_dict(row)


_init_db()


def build_tools_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter()

    @router.get("/tools")
    async def list_tools(_user_id: str = Depends(ctx.require_rate_limit)):
        return await asyncio.to_thread(_get_all)

    @router.post("/tools")
    async def create_tool(payload: dict[str, Any], _user_id: str = Depends(ctx.require_rate_limit)):
        name = str(payload.get("name", "")).strip()
        description = str(payload.get("description", "")).strip()
        category = str(payload.get("category", "api")).strip() or "api"
        if not name or not description:
            raise HTTPException(status_code=400, detail="name and description required")
        return await asyncio.to_thread(_create_custom, name, description, category)

    @router.put("/tools/{tool_id}")
    async def update_tool(tool_id: str, payload: dict[str, Any], _user_id: str = Depends(ctx.require_rate_limit)):
        name = str(payload.get("name", "")).strip()
        description = str(payload.get("description", "")).strip()
        category = str(payload.get("category", "api")).strip() or "api"
        if not name or not description:
            raise HTTPException(status_code=400, detail="name and description required")
        try:
            return await asyncio.to_thread(_update_custom, tool_id, name, description, category)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Custom tool '{tool_id}' not found")

    @router.delete("/tools/{tool_id}")
    async def delete_tool(tool_id: str, _user_id: str = Depends(ctx.require_rate_limit)):
        deleted = await asyncio.to_thread(_delete_custom, tool_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Custom tool '{tool_id}' not found")
        return {"ok": True}

    @router.post("/tools/{tool_id}/enable")
    async def enable_tool(tool_id: str, _user_id: str = Depends(ctx.require_rate_limit)):
        try:
            return await asyncio.to_thread(_set_enabled, tool_id, True)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")

    @router.post("/tools/{tool_id}/disable")
    async def disable_tool(tool_id: str, _user_id: str = Depends(ctx.require_rate_limit)):
        try:
            return await asyncio.to_thread(_set_enabled, tool_id, False)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")

    return router
