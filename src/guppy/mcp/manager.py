"""MCP Plugin Manager — SQLite-backed registry of MCP server configs.

Manages lifecycle of MCPStdioClient instances for all enabled servers.
Tool naming convention: mcp__<server_id>__<tool_name>
"""
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from typing import Any, Dict, List, Optional

from src.guppy.mcp.stdio_client import MCPStdioClient, MCPError
from src.guppy.paths import ensure_user_data_dir

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS mcp_servers (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    command     TEXT NOT NULL,
    args        TEXT NOT NULL DEFAULT '[]',
    env_vars    TEXT NOT NULL DEFAULT '{}',
    is_enabled  INTEGER NOT NULL DEFAULT 0,
    is_preset   INTEGER NOT NULL DEFAULT 0
);
"""

_PRESET_SERVERS = [
    (
        "filesystem",
        "Filesystem",
        "Read/write local files and directories",
        "npx",
        json.dumps(["-y", "@modelcontextprotocol/server-filesystem", "."]),
        "{}",
        0, 1,
    ),
    (
        "fetch",
        "Fetch",
        "Fetch URLs and web content",
        "npx",
        json.dumps(["-y", "@modelcontextprotocol/server-fetch"]),
        "{}",
        0, 1,
    ),
    (
        "memory",
        "Memory",
        "Persistent key-value memory across conversations",
        "npx",
        json.dumps(["-y", "@modelcontextprotocol/server-memory"]),
        "{}",
        0, 1,
    ),
    (
        "sequential-thinking",
        "Sequential Thinking",
        "Structured step-by-step reasoning and problem solving",
        "npx",
        json.dumps(["-y", "@modelcontextprotocol/server-sequential-thinking"]),
        "{}",
        0, 1,
    ),
    (
        "github",
        "GitHub",
        "Search repos, read files, manage issues and PRs",
        "npx",
        json.dumps(["-y", "@modelcontextprotocol/server-github"]),
        json.dumps({"GITHUB_PERSONAL_ACCESS_TOKEN": ""}),
        0, 1,
    ),
    (
        "brave-search",
        "Brave Search",
        "Web and news search via Brave Search API",
        "npx",
        json.dumps(["-y", "@modelcontextprotocol/server-brave-search"]),
        json.dumps({"BRAVE_API_KEY": ""}),
        0, 1,
    ),
    (
        "slack",
        "Slack",
        "Read channels, send messages, manage workspaces",
        "npx",
        json.dumps(["-y", "@modelcontextprotocol/server-slack"]),
        json.dumps({"SLACK_BOT_TOKEN": "", "SLACK_TEAM_ID": ""}),
        0, 1,
    ),
    (
        "postgres",
        "PostgreSQL",
        "Query and inspect PostgreSQL databases",
        "npx",
        json.dumps(["-y", "@modelcontextprotocol/server-postgres"]),
        json.dumps({"DATABASE_URL": ""}),
        0, 1,
    ),
    (
        "sqlite",
        "SQLite",
        "Query and inspect local SQLite database files",
        "npx",
        json.dumps(["-y", "@modelcontextprotocol/server-sqlite", "--db-path", "data.db"]),
        "{}",
        0, 1,
    ),
    (
        "puppeteer",
        "Puppeteer",
        "Browser automation — screenshots, scraping, form filling",
        "npx",
        json.dumps(["-y", "@modelcontextprotocol/server-puppeteer"]),
        "{}",
        0, 1,
    ),
    (
        "google-maps",
        "Google Maps",
        "Search places, get directions, geocoding",
        "npx",
        json.dumps(["-y", "@modelcontextprotocol/server-google-maps"]),
        json.dumps({"GOOGLE_MAPS_API_KEY": ""}),
        0, 1,
    ),
]


def _db_path() -> str:
    return str(ensure_user_data_dir() / "mcp_servers.db")


def _init_db() -> None:
    with sqlite3.connect(_db_path()) as conn:
        conn.executescript(_SCHEMA)
        existing = {r[0] for r in conn.execute("SELECT id FROM mcp_servers").fetchall()}
        for row in _PRESET_SERVERS:
            if row[0] not in existing:
                conn.execute(
                    "INSERT INTO mcp_servers (id, name, description, command, args, env_vars, is_enabled, is_preset)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    row,
                )
        conn.commit()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id":          row["id"],
        "name":        row["name"],
        "description": row["description"],
        "command":     row["command"],
        "args":        json.loads(row["args"] or "[]"),
        "envVars":     json.loads(row["env_vars"] or "{}"),
        "isEnabled":   bool(row["is_enabled"]),
        "isPreset":    bool(row["is_preset"]),
    }


def _read_all() -> list[dict[str, Any]]:
    with sqlite3.connect(_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        return [_row_to_dict(r) for r in conn.execute("SELECT * FROM mcp_servers ORDER BY is_preset DESC, name").fetchall()]


def _read_one(server_id: str) -> Optional[dict[str, Any]]:
    with sqlite3.connect(_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM mcp_servers WHERE id = ?", (server_id,)).fetchone()
        return _row_to_dict(row) if row else None


def _upsert(server_id: str, name: str, description: str, command: str,
            args: list, env_vars: dict, is_preset: bool = False) -> dict[str, Any]:
    with sqlite3.connect(_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(
            "INSERT INTO mcp_servers (id, name, description, command, args, env_vars, is_enabled, is_preset)"
            " VALUES (?,?,?,?,?,?,0,?)"
            " ON CONFLICT(id) DO UPDATE SET"
            "   name=excluded.name, description=excluded.description,"
            "   command=excluded.command, args=excluded.args, env_vars=excluded.env_vars",
            (server_id, name, description, command, json.dumps(args), json.dumps(env_vars), int(is_preset)),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM mcp_servers WHERE id = ?", (server_id,)).fetchone()
        return _row_to_dict(row)


def _set_enabled(server_id: str, enabled: bool) -> dict[str, Any]:
    with sqlite3.connect(_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("UPDATE mcp_servers SET is_enabled = ? WHERE id = ?", (int(enabled), server_id))
        conn.commit()
        row = conn.execute("SELECT * FROM mcp_servers WHERE id = ?", (server_id,)).fetchone()
        if not row:
            raise KeyError(server_id)
        return _row_to_dict(row)


def _set_env_vars(server_id: str, env_vars: dict) -> dict[str, Any]:
    with sqlite3.connect(_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("UPDATE mcp_servers SET env_vars = ? WHERE id = ?", (json.dumps(env_vars), server_id))
        conn.commit()
        row = conn.execute("SELECT * FROM mcp_servers WHERE id = ?", (server_id,)).fetchone()
        if not row:
            raise KeyError(server_id)
        return _row_to_dict(row)


def _delete(server_id: str) -> None:
    with sqlite3.connect(_db_path()) as conn:
        conn.execute("DELETE FROM mcp_servers WHERE id = ? AND is_preset = 0", (server_id,))
        conn.commit()


_init_db()


class MCPPluginManager:
    """Manages MCP server lifecycle and tool discovery.

    Keeps a pool of MCPStdioClient instances for enabled servers.
    Thread-safe via asyncio.Lock.
    """

    def __init__(self) -> None:
        self._clients: Dict[str, MCPStdioClient] = {}
        self._tool_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = asyncio.Lock()

    # ── Server registry (sync wrappers) ───────────────────────────────────────

    async def list_servers(self) -> list[dict[str, Any]]:
        return await asyncio.to_thread(_read_all)

    async def add_server(self, server_id: str, name: str, description: str,
                         command: str, args: list, env_vars: dict) -> dict[str, Any]:
        return await asyncio.to_thread(_upsert, server_id, name, description, command, args, env_vars, False)

    async def update_env_vars(self, server_id: str, env_vars: dict) -> dict[str, Any]:
        async with self._lock:
            result = await asyncio.to_thread(_set_env_vars, server_id, env_vars)
            # Restart client if running so new creds take effect
            if server_id in self._clients:
                await self._disconnect(server_id)
            return result

    async def delete_server(self, server_id: str) -> None:
        async with self._lock:
            if server_id in self._clients:
                await self._disconnect(server_id)
            await asyncio.to_thread(_delete, server_id)

    async def set_enabled(self, server_id: str, enabled: bool) -> dict[str, Any]:
        async with self._lock:
            result = await asyncio.to_thread(_set_enabled, server_id, enabled)
            if enabled:
                await self._ensure_connected(server_id)
            else:
                await self._disconnect(server_id)
            return result

    # ── Client pool ───────────────────────────────────────────────────────────

    async def _ensure_connected(self, server_id: str) -> Optional[MCPStdioClient]:
        if server_id in self._clients and self._clients[server_id].is_running:
            return self._clients[server_id]
        cfg = await asyncio.to_thread(_read_one, server_id)
        if not cfg or not cfg["isEnabled"]:
            return None
        client = MCPStdioClient(cfg["command"], cfg["args"], cfg["envVars"])
        try:
            await client.start(timeout=20.0)
            self._clients[server_id] = client
            self._tool_cache.pop(server_id, None)
            logger.info("[MCP] Connected: %s (%s)", cfg["name"], server_id)
            return client
        except Exception as exc:
            logger.warning("[MCP] Failed to start %s: %s", server_id, exc)
            return None

    async def _disconnect(self, server_id: str) -> None:
        client = self._clients.pop(server_id, None)
        self._tool_cache.pop(server_id, None)
        if client:
            try:
                await client.stop()
            except Exception:
                pass

    async def connect_all_enabled(self) -> None:
        """Start clients for all currently-enabled servers (called at app startup)."""
        servers = await asyncio.to_thread(_read_all)
        async with self._lock:
            for srv in servers:
                if srv["isEnabled"]:
                    await self._ensure_connected(srv["id"])

    async def disconnect_all(self) -> None:
        """Stop all running clients (called at app shutdown)."""
        async with self._lock:
            for server_id in list(self._clients.keys()):
                await self._disconnect(server_id)

    # ── Tool discovery ────────────────────────────────────────────────────────

    async def get_tools(self, server_id: str) -> List[Dict[str, Any]]:
        """Return raw tool definitions from a server (cached)."""
        if server_id in self._tool_cache:
            return self._tool_cache[server_id]
        async with self._lock:
            client = await self._ensure_connected(server_id)
            if not client:
                return []
            try:
                tools = await client.list_tools()
                self._tool_cache[server_id] = tools
                return tools
            except Exception as exc:
                logger.warning("[MCP] list_tools failed for %s: %s", server_id, exc)
                return []

    async def get_tools_for_llm(self) -> List[Dict[str, Any]]:
        """Return all enabled server tools in Guppy tool format.

        Tool IDs use the convention: mcp__<server_id>__<tool_name>
        """
        servers = await asyncio.to_thread(_read_all)
        result: List[Dict[str, Any]] = []
        for srv in servers:
            if not srv["isEnabled"]:
                continue
            tools = await self.get_tools(srv["id"])
            for t in tools:
                guppy_id = f"mcp__{srv['id']}__{t['name']}"
                result.append({
                    "id":          guppy_id,
                    "name":        f"{srv['name']}: {t.get('name', '')}",
                    "description": t.get("description", ""),
                    "category":    "mcp",
                    "type":        "mcp",
                    "parameters":  t.get("inputSchema", {}),
                    "isEnabled":   True,
                    "_server_id":  srv["id"],
                    "_tool_name":  t["name"],
                })
        return result

    # ── Tool dispatch ─────────────────────────────────────────────────────────

    async def call_tool(self, server_id: str, tool_name: str,
                        arguments: Dict[str, Any], timeout: float = 60.0) -> str:
        """Call a tool on the specified server."""
        async with self._lock:
            client = await self._ensure_connected(server_id)
        if not client:
            raise RuntimeError(f"MCP server '{server_id}' is not connected")
        return await client.call_tool(tool_name, arguments, timeout=timeout)

    async def call_tool_by_guppy_id(self, guppy_tool_id: str,
                                     arguments: Dict[str, Any], timeout: float = 60.0) -> str:
        """Dispatch by mcp__<server_id>__<tool_name> convention."""
        parts = guppy_tool_id.split("__", 2)
        if len(parts) != 3 or parts[0] != "mcp":
            raise ValueError(f"Invalid MCP tool ID: {guppy_tool_id!r}")
        _, server_id, tool_name = parts
        return await self.call_tool(server_id, tool_name, arguments, timeout=timeout)

    async def test_server(self, server_id: str) -> Dict[str, Any]:
        """Attempt connection and return status."""
        async with self._lock:
            if server_id in self._clients:
                await self._disconnect(server_id)
            client = await self._ensure_connected(server_id)
        if not client:
            return {"ok": False, "error": "Failed to start server process"}
        try:
            tools = await client.list_tools()
            return {"ok": True, "toolCount": len(tools), "serverInfo": client.server_info}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


_manager: Optional[MCPPluginManager] = None


def get_mcp_manager() -> MCPPluginManager:
    global _manager
    if _manager is None:
        _manager = MCPPluginManager()
    return _manager
