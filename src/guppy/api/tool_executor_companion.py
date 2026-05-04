"""Companion surface tool executor.

All tools available to the companion surface. Desktop control tools require
GUPPY_DESKTOP_CONTROL=1 env var and pyautogui installed.
"""
from __future__ import annotations

import asyncio
import os
import re

# ── Per-tool HTTP timeout constants ───────────────────────────────────────────
_DOWNLOAD_TIMEOUT = 10.0  # qBittorrent add-torrent call


def _store_outcome(name: str, args: dict, result: dict) -> None:
    """Fire-and-forget: persist tool outcome to semantic memory for future recall."""
    if result.get("ok") is False:
        return  # don't log failures — they clutter memory
    try:
        from src.guppy.inference.context_injection import _bg_store_tool_outcome
        _bg_store_tool_outcome(name, args, str(result)[:400])
    except Exception:
        pass


_TOOL_ALIASES: dict[str, str] = {
    "fetch_url":         "web_fetch",
    "semantic_remember": "memory_write",
    "memory_read":       "memory_recall",
    "remember":          "memory_write",
    "recall":            "memory_recall",
}


async def _execute_companion_tool(name: str, args: dict) -> dict:
    """Execute one companion tool call. Returns a result dict."""
    import httpx

    name = _TOOL_ALIASES.get(name, name)

    if name == "web_fetch":
        from src.guppy.api.web_fetch_safe import safe_web_fetch
        url     = str(args.get("url", "")).strip()
        extract = str(args.get("extract", "")).strip().lower()
        return await safe_web_fetch(url, extract=extract)

    if name == "web_search":
        query = str(args.get("query", "")).strip()
        num_results = min(int(args.get("num_results", 5)), 10)
        if not query:
            return {"ok": False, "error": "query required"}
        try:
            async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": "Mozilla/5.0 Guppy/1.0"},
                )
            # Extract result snippets from DDG HTML response
            anchors = re.findall(
                r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a',
                resp.text, re.DOTALL,
            )
            results = [
                {"url": u, "title": re.sub(r"<[^>]+>", "", t).strip()}
                for u, t in anchors[:num_results]
            ]
            return {"ok": True, "results": results, "query": query}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if name == "create_reminder":
        from src.guppy.api.routes_reminders import create_reminder
        message       = str(args.get("message", "")).strip()
        delay_minutes = args.get("delay_minutes")
        due_iso       = args.get("due_iso")
        if not message:
            return {"ok": False, "error": "message required"}
        if delay_minutes is None and due_iso is None:
            delay_minutes = 30
        # Coerce delay_minutes to int if the LLM sent it as a string
        if delay_minutes is not None:
            try:
                delay_minutes = int(delay_minutes)
            except (TypeError, ValueError):
                return {"ok": False, "error": f"delay_minutes must be an integer, got: {delay_minutes!r}"}
        try:
            return {"ok": True, **create_reminder(message, due_iso=due_iso, delay_minutes=delay_minutes)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if name == "download_media":
        url      = str(args.get("url", "")).strip()
        category = str(args.get("category", "general")).strip()
        if not url:
            return {"ok": False, "error": "url required"}

        policy = os.environ.get("LIBRARY_ACQUISITION_POLICY", "user_approved").strip().lower()
        if policy == "open_content_only":
            return {
                "ok": False,
                "error": "download_media disabled by LIBRARY_ACQUISITION_POLICY=open_content_only",
            }

        try:
            # Call qBittorrent Web API directly (bypasses Guppy auth)
            qb_base = os.environ.get("QBITTORRENT_URL", "http://localhost:8080").rstrip("/")
            payload: dict = {"urls": url}
            if category:
                payload["category"] = category
            async with httpx.AsyncClient(timeout=_DOWNLOAD_TIMEOUT) as client:
                resp = await client.post(f"{qb_base}/api/v2/torrents/add", data=payload)
            return {"ok": resp.status_code < 300, "status": resp.status_code, "url": url}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if name == "memory_write":
        from src.guppy.memory.semantic import remember_semantic
        key      = str(args.get("key", "note")).strip()
        value    = str(args.get("value", "")).strip()
        category = str(args.get("category", "general")).strip()
        if not value:
            return {"ok": False, "error": "value required"}
        try:
            return {"ok": True, "stored": remember_semantic(key, value, category)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if name == "memory_recall":
        from src.guppy.memory.semantic import recall_semantic
        query = str(args.get("query", "")).strip()
        if not query:
            return {"ok": False, "error": "query required"}
        try:
            return {"ok": True, "recalled": recall_semantic(query)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if name == "workspace_task":
        title       = str(args.get("title", "Task")).strip()
        description = str(args.get("description", "")).strip()
        if not title:
            return {"ok": False, "error": "title required"}
        try:
            from src.guppy.api.routes_surface import _spawn_task_direct
            task = _spawn_task_direct(title=title, description=description, source="companion")
            return {"ok": True, "task_id": task["id"], "surface": "workspace"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if name == "cancel_workspace_task":
        task_id = str(args.get("task_id", "")).strip()
        if not task_id:
            return {"ok": False, "error": "task_id required"}
        try:
            from src.guppy.api.routes_surface import _cancel_task_direct
            return _cancel_task_direct(task_id)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if name == "list_workspace_tasks":
        status_filter = str(args.get("status", "")).strip()
        try:
            from src.guppy.api.routes_surface import _DB_PATH, _db
            if not _DB_PATH:
                return {"ok": False, "error": "surface DB not ready"}
            with _db() as conn:
                if status_filter:
                    rows = conn.execute(
                        "SELECT id, title, status, created_at FROM surface_tasks WHERE status=? ORDER BY created_at DESC LIMIT 10",
                        (status_filter,)
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT id, title, status, created_at FROM surface_tasks ORDER BY created_at DESC LIMIT 10"
                    ).fetchall()
            tasks = [{"id": r[0], "title": r[1], "status": r[2], "created_at": r[3]} for r in rows]
            return {"ok": True, "tasks": tasks, "count": len(tasks)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if name == "get_time":
        from datetime import datetime
        now = datetime.now()
        return {
            "ok": True,
            "time": now.strftime("%H:%M"),
            "date": now.strftime("%A, %B %d, %Y"),
            "iso": now.isoformat(),
        }

    # ── Desktop vision & control ───────────────────────────────────────────────

    if name == "desktop_screenshot":
        question = str(args.get("question", "Describe everything you can see on the screen in detail.")).strip()
        region   = args.get("region") or None
        try:
            from src.guppy.api.routes_desktop import _sync_read_screen
            description = await asyncio.to_thread(_sync_read_screen, region, question, 82)
            return {"ok": True, "description": description}
        except Exception as exc:
            return {"ok": False, "error": getattr(exc, "detail", str(exc))}

    if name == "desktop_click":
        if not os.environ.get("GUPPY_DESKTOP_CONTROL"):
            return {"ok": False, "error": "Desktop control is disabled — set GUPPY_DESKTOP_CONTROL=1 to enable."}
        description = str(args.get("description", "")).strip()
        x = args.get("x")
        y = args.get("y")
        try:
            from src.guppy.api.routes_desktop import _sync_click
            from src.guppy.workspace import screen_parser
            if description and x is None:
                coords = await asyncio.to_thread(screen_parser.ground_click, description)
                if not coords:
                    return {"ok": False, "error": f"Could not find '{description}' on screen"}
                x, y = coords
            result_msg = await asyncio.to_thread(_sync_click, int(x), int(y), "left", 1, 0.1)
            return {"ok": True, "result": result_msg}
        except Exception as exc:
            return {"ok": False, "error": getattr(exc, "detail", str(exc))}

    if name == "desktop_type":
        if not os.environ.get("GUPPY_DESKTOP_CONTROL"):
            return {"ok": False, "error": "Desktop control is disabled — set GUPPY_DESKTOP_CONTROL=1 to enable."}
        text = str(args.get("text", "")).strip()
        if not text:
            return {"ok": False, "error": "text required"}
        try:
            from src.guppy.api.routes_desktop import _sync_type
            result_msg = await asyncio.to_thread(_sync_type, text[:2000], 0.03)
            return {"ok": True, "result": result_msg}
        except Exception as exc:
            return {"ok": False, "error": getattr(exc, "detail", str(exc))}

    if name == "desktop_shortcut":
        if not os.environ.get("GUPPY_DESKTOP_CONTROL"):
            return {"ok": False, "error": "Desktop control is disabled — set GUPPY_DESKTOP_CONTROL=1 to enable."}
        keys = str(args.get("keys", "")).strip()
        if not keys:
            return {"ok": False, "error": "keys required (e.g. 'ctrl+c', 'win+d')"}
        try:
            from src.guppy.api.routes_desktop import _sync_shortcut
            result_msg = await asyncio.to_thread(_sync_shortcut, keys)
            return {"ok": True, "result": result_msg}
        except Exception as exc:
            return {"ok": False, "error": getattr(exc, "detail", str(exc))}

    if name == "desktop_scroll":
        x      = int(args.get("x", 0))
        y      = int(args.get("y", 0))
        clicks = int(args.get("clicks", 3))
        try:
            from src.guppy.api.routes_desktop import _sync_scroll
            result_msg = await asyncio.to_thread(_sync_scroll, x, y, clicks)
            return {"ok": True, "result": result_msg}
        except Exception as exc:
            return {"ok": False, "error": getattr(exc, "detail", str(exc))}

    result = {"ok": False, "error": f"Unknown tool: {name}"}
    _store_outcome(name, args, result)
    return result
