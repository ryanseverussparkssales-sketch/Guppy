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
    # ── Screen history (Screenpipe) ───────────────────────────────────────────
    ("screenpipe_search", "Screen History: Search", "Search recorded screen and audio history via local Screenpipe daemon (requires SCREENPIPE_URL)", "productivity", "builtin", '{"type":"object","properties":{"query":{"type":"string","description":"Text to search for in screen OCR or audio transcripts"},"limit":{"type":"number","default":20},"content_type":{"type":"string","enum":["all","ocr","audio"],"default":"all"},"app_name":{"type":"string","description":"Filter by application name"}},"required":["query"]}', 0),
    ("screenpipe_recent", "Screen History: Recent", "Fetch recent screen and audio activity from the last N minutes via Screenpipe", "productivity", "builtin", '{"type":"object","properties":{"minutes":{"type":"number","default":30,"description":"How many minutes of history to fetch"},"limit":{"type":"number","default":20}},"required":[]}', 0),
    # ── Library (Calibre) ─────────────────────────────────────────────────────
    ("calibre_search",        "Calibre: Search Library",       "Search the local Calibre ebook library by title, author, or keyword",                                        "library", "builtin", '{"type":"object","properties":{"query":{"type":"string","description":"Search query (title, author, tag, etc.)"},"limit":{"type":"number","default":20}},"required":[]}', 1),
    ("calibre_add_book",      "Calibre: Add Book",             "Add a book to Calibre from a local file path or a direct download URL (EPUB/MOBI/PDF)",                      "library", "builtin", '{"type":"object","properties":{"source":{"type":"string","description":"Local file path or direct URL to the book file"}},"required":["source"]}', 1),
    ("calibre_set_metadata",  "Calibre: Set Metadata",         "Update metadata fields (tags, title, authors, series, etc.) for a book in Calibre by its numeric ID",       "library", "builtin", '{"type":"object","properties":{"book_id":{"type":"integer"},"fields":{"type":"object","description":"Calibre field names to values, e.g. tags or series","additionalProperties":{"type":"string"}}},"required":["book_id","fields"]}', 1),
    ("gutenberg_search",      "Gutenberg: Search",             "Search Project Gutenberg for public-domain books via Gutendex (no auth required)",                           "library", "builtin", '{"type":"object","properties":{"query":{"type":"string"},"limit":{"type":"number","default":10}},"required":["query"]}', 1),
    ("gutenberg_download",    "Gutenberg: Download to Calibre","Download a Project Gutenberg book by its numeric ID and add it to the local Calibre library",               "library", "builtin", '{"type":"object","properties":{"book_id":{"type":"integer","description":"Gutenberg book ID (from gutenberg_search results)"}},"required":["book_id"]}', 1),
    ("openlibrary_search",    "Open Library: Search",          "Search Open Library for book metadata including ISBN, cover art, subjects, and publication year",            "library", "builtin", '{"type":"object","properties":{"query":{"type":"string"},"limit":{"type":"number","default":10}},"required":["query"]}', 1),
    ("send_to_kindle",        "Send to Kindle",                "Convert a Calibre book to MOBI and deliver it to the configured Kindle via email (requires KINDLE_EMAIL env)", "library", "builtin", '{"type":"object","properties":{"book_id":{"type":"integer","description":"Calibre book ID to convert and send"}},"required":["book_id"]}', 0),
    ("kindle_send_direct",    "Kindle: Send URL or File",      "Download any EPUB/PDF URL (or local file) and deliver it directly to Kindle via email — no Calibre library needed", "library", "builtin", '{"type":"object","properties":{"source":{"type":"string","description":"Direct URL or local file path to the ebook"},"format":{"type":"string","enum":["mobi","azw3","epub"],"default":"mobi"}},"required":["source"]}', 0),
    # ── Acquisition (LazyLibrarian + Prowlarr) ────────────────────────────────
    ("ll_search_book",        "LazyLibrarian: Search",         "Search LazyLibrarian book database by title or author",                                                          "library", "builtin", '{"type":"object","properties":{"title":{"type":"string"},"author":{"type":"string"}},"required":[]}', 0),
    ("ll_add_wanted",         "LazyLibrarian: Add Wanted",     "Add a book to LazyLibrarian wanted list by Goodreads ID or ISBN",                                                "library", "builtin", '{"type":"object","properties":{"goodreads_id":{"type":"string"},"isbn":{"type":"string"}},"required":[]}', 0),
    ("ll_add_author",         "LazyLibrarian: Watch Author",   "Add an author to LazyLibrarian — it will monitor and download all their new books",                              "library", "builtin", '{"type":"object","properties":{"name":{"type":"string","description":"Author full name"}},"required":["name"]}', 0),
    ("ll_get_wanted",         "LazyLibrarian: Wanted List",    "Return the current wanted/monitored books list from LazyLibrarian",                                              "library", "builtin", '{"type":"object","properties":{}}', 0),
    ("prowlarr_search",       "Prowlarr: Search Indexers",     "Search all configured Prowlarr indexers for ebooks (NZB/torrent)",                                               "library", "builtin", '{"type":"object","properties":{"query":{"type":"string"},"limit":{"type":"number","default":20},"ebooks_only":{"type":"boolean","default":true}},"required":["query"]}', 0),
    ("prowlarr_indexers",     "Prowlarr: List Indexers",       "List all configured Prowlarr indexers and their status",                                                          "library", "builtin", '{"type":"object","properties":{}}', 0),
    # ── Tier 3 sources ────────────────────────────────────────────────────────
    ("standard_ebooks_search",   "Standard Ebooks: Search",        "Search Standard Ebooks curated public-domain library (free, DRM-free, beautifully typeset)",              "library", "builtin", '{"type":"object","properties":{"query":{"type":"string"},"limit":{"type":"number","default":10}},"required":["query"]}', 1),
    ("standard_ebooks_download", "Standard Ebooks: Download",      "Download a Standard Ebooks title into the local Calibre library by EPUB URL or title/author",            "library", "builtin", '{"type":"object","properties":{"epub_url":{"type":"string"},"title":{"type":"string"},"author":{"type":"string"}},"required":[]}', 1),
    ("ia_search",                "Internet Archive: Search",       "Search Internet Archive for scanned books and texts",                                                      "library", "builtin", '{"type":"object","properties":{"query":{"type":"string"},"limit":{"type":"number","default":10},"media_type":{"type":"string","default":"texts"}},"required":["query"]}', 1),
    ("ia_download",              "Internet Archive: Download",     "Download an Internet Archive item by identifier into the local Calibre library",                         "library", "builtin", '{"type":"object","properties":{"identifier":{"type":"string","description":"IA item identifier from ia_search results"}},"required":["identifier"]}', 1),
    ("mylar3_search",            "Mylar3: Search Comics",          "Search Mylar3 comic database by series title (requires MYLAR3_APIKEY)",                                   "library", "builtin", '{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}', 0),
    ("mylar3_add_comic",         "Mylar3: Add Comic Series",       "Add a comic series to Mylar3 monitoring by its ID from mylar3_search results",                           "library", "builtin", '{"type":"object","properties":{"comic_id":{"type":"string"}},"required":["comic_id"]}', 0),
    # ── Document & file reading ───────────────────────────────────────────────
    ("file_extract_text",  "Read Document",       "Extract readable text from any file: PDF, DOCX, XLSX, PPTX, CSV, images (EXIF), or plain text/code", "file",   "builtin", '{"type":"object","properties":{"path":{"type":"string","description":"Absolute path or ~ path to the file"},"max_chars":{"type":"integer","default":50000,"description":"Max characters to extract; large files are truncated"}},"required":["path"]}', 1),
    ("file_info",          "File Info",           "Get metadata for a file: size, type, last modified, MIME type, read/write permissions",               "file",   "builtin", '{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}', 1),
    ("browse_directory",   "Browse Directory",    "List files and folders in a directory with sizes and dates; supports glob patterns",                   "file",   "builtin", '{"type":"object","properties":{"path":{"type":"string"},"pattern":{"type":"string","default":"*","description":"Glob filter e.g. *.pdf"}},"required":["path"]}', 1),
    # ── System monitoring ─────────────────────────────────────────────────────
    ("system_info",        "System Info",         "Current snapshot of CPU usage, RAM, swap, all disk volumes, and system uptime",                        "system", "builtin", '{"type":"object","properties":{}}', 1),
    ("top_processes",      "Top Processes",       "List the top N processes by CPU or memory usage",                                                      "system", "builtin", '{"type":"object","properties":{"limit":{"type":"integer","default":10},"sort":{"type":"string","enum":["cpu","memory"],"default":"cpu"}},"required":[]}', 1),
    ("disk_usage",         "Disk Usage",          "Disk space used/free for a specific path or drive",                                                    "system", "builtin", '{"type":"object","properties":{"path":{"type":"string","default":"C:/"}},"required":[]}', 1),
    ("network_stats",      "Network Stats",       "Network I/O counters (bytes sent/received, packets, errors) since boot",                               "system", "builtin", '{"type":"object","properties":{}}', 1),
    # ── Clipboard ────────────────────────────────────────────────────────────
    ("clipboard_read",     "Clipboard: Read",     "Read the current text content of the system clipboard",                                                "desktop", "builtin", '{"type":"object","properties":{}}', 1),
    ("clipboard_write",    "Clipboard: Write",    "Write text to the system clipboard, replacing or appending to existing content",                       "desktop", "builtin", '{"type":"object","properties":{"text":{"type":"string"},"append":{"type":"boolean","default":false}},"required":["text"]}', 1),
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


def _apply_env_defaults() -> None:
    """Enable tools that depend on external services, when the required env vars are set."""
    import os
    changes: list[tuple[int, str]] = []

    screenpipe_url = os.environ.get("SCREENPIPE_URL", "").strip()
    if screenpipe_url:
        changes += [(1, "screenpipe_search"), (1, "screenpipe_recent")]

    if os.environ.get("LAZYLIBRARIAN_URL", "").strip() and os.environ.get("LAZYLIBRARIAN_API_KEY", "").strip():
        changes += [(1, "ll_search_book"), (1, "ll_add_wanted"), (1, "ll_add_author"), (1, "ll_get_wanted")]

    if os.environ.get("PROWLARR_URL", "").strip() and os.environ.get("PROWLARR_API_KEY", "").strip():
        changes += [(1, "prowlarr_search"), (1, "prowlarr_indexers")]

    if os.environ.get("KINDLE_EMAIL", "").strip():
        changes += [(1, "send_to_kindle"), (1, "kindle_send_direct")]

    if os.environ.get("SPOTIFY_CLIENT_ID", "").strip():
        changes += [(1, "spotify")]

    if os.environ.get("MYLAR3_APIKEY", "").strip():
        changes += [(1, "mylar3_search"), (1, "mylar3_add_comic")]

    if os.environ.get("GUPPY_DEV_MODE", "").strip():
        changes += [(1, "write_file"), (1, "apply_patch"), (1, "execute_command")]

    if not changes:
        return

    with sqlite3.connect(_db_path()) as conn:
        for enabled, tool_id in changes:
            conn.execute("UPDATE tools SET is_enabled = ? WHERE id = ?", (enabled, tool_id))
        conn.commit()


_apply_env_defaults()


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
