"""Lightweight async stdio MCP client — JSON-RPC 2.0 over subprocess pipes.

Does not depend on the `mcp` package; speaks the protocol directly.
Wire protocol: newline-delimited JSON objects on stdin/stdout.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PROTOCOL_VERSION = "2024-11-05"
_CLIENT_INFO = {"name": "guppy", "version": "1.0.0"}
_INIT_CAPABILITIES = {
    "roots": {"listChanged": False},
    "sampling": {},
}


class MCPError(Exception):
    """Raised when the MCP server returns a JSON-RPC error."""
    def __init__(self, code: int, message: str):
        super().__init__(f"MCP error {code}: {message}")
        self.code = code


class MCPStdioClient:
    """Async stdio MCP client for a single server process.

    Lifecycle:
        client = MCPStdioClient("npx", ["-y", "@modelcontextprotocol/server-fetch"], {})
        await client.start()
        tools = await client.list_tools()
        result = await client.call_tool("fetch", {"url": "https://example.com"})
        await client.stop()
    """

    def __init__(self, command: str, args: List[str], env: Dict[str, str]):
        self._command = command
        self._args = args
        self._extra_env = env
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._req_id = 0
        self._lock = asyncio.Lock()
        self.server_info: Dict[str, Any] = {}
        self.server_capabilities: Dict[str, Any] = {}

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self, timeout: float = 15.0) -> None:
        """Spawn the server process and run the MCP handshake."""
        full_env = {**os.environ, **self._extra_env}
        self._proc = await asyncio.create_subprocess_exec(
            self._command,
            *self._args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=full_env,
        )
        await asyncio.wait_for(self._initialize(), timeout=timeout)

    async def stop(self) -> None:
        """Terminate the server process gracefully."""
        if self._proc and self._proc.returncode is None:
            try:
                self._proc.terminate()
                await asyncio.wait_for(self._proc.wait(), timeout=5.0)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
        self._proc = None

    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    # ── JSON-RPC transport ────────────────────────────────────────────────────

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    async def _send_raw(self, obj: dict) -> None:
        if not self._proc or not self._proc.stdin:
            raise RuntimeError("MCP server process not running")
        data = json.dumps(obj, separators=(",", ":")).encode() + b"\n"
        self._proc.stdin.write(data)
        await self._proc.stdin.drain()

    async def _recv_raw(self, timeout: float = 30.0) -> dict:
        if not self._proc or not self._proc.stdout:
            raise RuntimeError("MCP server process not running")
        line = await asyncio.wait_for(self._proc.stdout.readline(), timeout=timeout)
        if not line:
            raise RuntimeError("MCP server closed stdout unexpectedly")
        return json.loads(line.decode().strip())

    async def _request(self, method: str, params: dict, timeout: float = 30.0) -> Any:
        """Send a JSON-RPC request and return the result, raising on error."""
        async with self._lock:
            req_id = self._next_id()
            await self._send_raw({
                "jsonrpc": "2.0",
                "id": req_id,
                "method": method,
                "params": params,
            })
            # Skip notifications (no id) until we get our response
            while True:
                resp = await self._recv_raw(timeout=timeout)
                if resp.get("id") == req_id:
                    break
                # Log unexpected messages without failing
                logger.debug("[MCP] Unexpected message: %s", resp)

        if "error" in resp:
            err = resp["error"]
            raise MCPError(err.get("code", -1), err.get("message", "unknown error"))
        return resp.get("result")

    async def _notify(self, method: str, params: dict) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        await self._send_raw({"jsonrpc": "2.0", "method": method, "params": params})

    # ── MCP protocol ──────────────────────────────────────────────────────────

    async def _initialize(self) -> None:
        result = await self._request("initialize", {
            "protocolVersion": _PROTOCOL_VERSION,
            "capabilities": _INIT_CAPABILITIES,
            "clientInfo": _CLIENT_INFO,
        }, timeout=15.0)
        self.server_info = result.get("serverInfo", {})
        self.server_capabilities = result.get("capabilities", {})
        await self._notify("notifications/initialized", {})
        logger.info("[MCP] Connected to %s", self.server_info.get("name", "unknown"))

    async def list_tools(self) -> List[Dict[str, Any]]:
        """Return the list of tool definitions from the server."""
        result = await self._request("tools/list", {})
        return result.get("tools", [])

    async def call_tool(self, name: str, arguments: Dict[str, Any], timeout: float = 60.0) -> str:
        """Call a tool and return its text output."""
        result = await self._request("tools/call", {"name": name, "arguments": arguments}, timeout=timeout)
        if result.get("isError"):
            content = result.get("content", [])
            msg = " ".join(c.get("text", "") for c in content if c.get("type") == "text")
            raise MCPError(-32000, msg or "Tool returned an error")
        content = result.get("content", [])
        parts = []
        for item in content:
            if item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif item.get("type") == "image":
                parts.append(f"[image: {item.get('mimeType', 'image')}]")
            elif item.get("type") == "resource":
                parts.append(f"[resource: {item.get('uri', '')}]")
        return "\n".join(parts) or "(empty response)"

    async def list_resources(self) -> List[Dict[str, Any]]:
        """Return available resources (if server supports them)."""
        if "resources" not in self.server_capabilities:
            return []
        result = await self._request("resources/list", {})
        return result.get("resources", [])

    async def read_resource(self, uri: str) -> str:
        """Read a resource by URI."""
        result = await self._request("resources/read", {"uri": uri})
        contents = result.get("contents", [])
        return "\n".join(c.get("text", "") for c in contents if c.get("type") == "text")
