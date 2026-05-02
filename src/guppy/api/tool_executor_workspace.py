"""Workspace surface tool executor.

All tools available to the workspace surface (Hermes 4). Shared tools are
delegated to the companion executor; workspace-only tools are implemented here.
"""
from __future__ import annotations

import asyncio
import os

from src.guppy.api.tool_executor_companion import _execute_companion_tool

# ── Per-tool HTTP timeout constants ───────────────────────────────────────────
_SEARCH_TIMEOUT  = 12.0
_WEATHER_TIMEOUT = 10.0
_API_TIMEOUT     = 15.0  # default; overridable per tool call via args["timeout"]
_VISION_TIMEOUT  = 30.0

# ── Shell command safe-prefix whitelist ───────────────────────────────────────
# Only read-only / introspection commands are allowed.
# SECURITY: "python -c" is intentionally excluded — it allows arbitrary code
# execution (e.g. python -c "import os; os.system(...)") and bypasses the
# whitelist intent. "echo" is excluded because it can be chained with shell
# redirects on Windows (echo foo > C:\file).
_SHELL_SAFE_PREFIXES = (
    "dir", "ls", "git status", "git log", "git diff", "git branch",
    "python --version", "python -m", "type ", "cat ", "head ",
    "tail ", "where ", "which ", "pip list", "pip show",
)

# ── Workspace tool schema (injected into Hermes 4 system prompt) ──────────────
_WORKSPACE_TOOL_SCHEMA = """
## Tools — Workspace Agent (Hermes 4)
You are an autonomous workspace agent. Use <tool_call> blocks to invoke tools.
Chain multiple calls to complete tasks. Use tools when they would help — don't just describe.

web_fetch(url, extract="")   — fetch any URL as plain text
  <tool_call>{"name": "web_fetch", "arguments": {"url": "https://www.gutenberg.org/files/1533/1533-0.txt", "extract": "witches"}}</tool_call>

web_search(query, num_results=5)   — search the web via DuckDuckGo
  <tool_call>{"name": "web_search", "arguments": {"query": "Project Gutenberg Macbeth plain text", "num_results": 5}}</tool_call>

file_read(path)   — read a local file
  <tool_call>{"name": "file_read", "arguments": {"path": "C:/Users/Ryan/Documents/notes.txt"}}</tool_call>

file_list(path=".")   — list files in a directory
  <tool_call>{"name": "file_list", "arguments": {"path": "C:/Users/Ryan/Downloads"}}</tool_call>

shell_run(command)   — read-only shell commands: dir, ls, git status/log/diff, python, type, cat
  <tool_call>{"name": "shell_run", "arguments": {"command": "dir C:/Users/Ryan/Downloads"}}</tool_call>

contacts_search(query)   — search CRM contacts by name/company/email
  <tool_call>{"name": "contacts_search", "arguments": {"query": "Smith"}}</tool_call>

screenpipe_search(query, limit=5)   — search recent screen/audio context via Screenpipe
    <tool_call>{"name": "screenpipe_search", "arguments": {"query": "invoice draft", "limit": 5}}</tool_call>

memory_write(key, value, category="general")   — store a fact permanently
  <tool_call>{"name": "memory_write", "arguments": {"key": "macbeth_location", "value": "Saved to C:/Users/Ryan/Downloads/macbeth.txt", "category": "completed"}}</tool_call>

memory_recall(query)   — recall facts from persistent memory
  <tool_call>{"name": "memory_recall", "arguments": {"query": "where is Macbeth saved"}}</tool_call>

create_reminder(message, delay_minutes=30)   — schedule a reminder for Ryan
  <tool_call>{"name": "create_reminder", "arguments": {"message": "Read the Macbeth witches scene", "delay_minutes": 60}}</tool_call>

download_media(url, category="general")   — queue a download in qBittorrent
  <tool_call>{"name": "download_media", "arguments": {"url": "magnet:?xt=urn:btih:...", "category": "books"}}</tool_call>
"""


async def _execute_workspace_tool(name: str, args: dict) -> dict:
    """Execute one workspace tool call. Delegates shared tools to companion executor."""
    import httpx

    # Shared tools — delegate to companion executor
    if name in (
        "web_fetch", "create_reminder", "download_media",
        "memory_write", "memory_recall", "workspace_task",
    ):
        return await _execute_companion_tool(name, args)

    if name == "web_search":
        query = str(args.get("query", "")).strip()
        try:
            num_results = min(int(args.get("num_results", 5)), 10)
        except (TypeError, ValueError):
            num_results = 5
        if not query:
            return {"ok": False, "error": "query required"}
        try:
            from bs4 import BeautifulSoup
            async with httpx.AsyncClient(timeout=_SEARCH_TIMEOUT, follow_redirects=True) as client:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Guppy/1.0"},
                )
            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            for div in soup.select(".result"):
                a_tag = div.select_one(".result__a")
                snippet_tag = div.select_one(".result__snippet")
                if not a_tag:
                    continue
                url   = a_tag.get("href", "") or ""
                title = a_tag.get_text(strip=True)
                snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
                if url and title:
                    results.append({"url": url, "title": title, "snippet": snippet})
                if len(results) >= num_results:
                    break
            return {"ok": True, "results": results, "query": query, "count": len(results)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if name == "file_read":
        from pathlib import Path
        path = str(args.get("path", "")).strip()
        if not path:
            return {"ok": False, "error": "path required"}
        try:
            content = Path(path).read_text(encoding="utf-8", errors="replace")
            return {"ok": True, "path": path, "content": content[:20000]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if name == "file_list":
        from pathlib import Path
        path = str(args.get("path", ".")).strip() or "."
        try:
            p = Path(path)
            entries = [
                {
                    "name": x.name,
                    "type": "dir" if x.is_dir() else "file",
                    "size": x.stat().st_size if x.is_file() else 0,
                }
                for x in sorted(p.iterdir())
            ]
            return {"ok": True, "path": str(p.resolve()), "entries": entries[:200]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if name == "shell_run":
        import subprocess
        command = str(args.get("command", "")).strip()
        if not command:
            return {"ok": False, "error": "command required"}
        cmd_lower = command.lower()
        if not any(cmd_lower.startswith(p.lower()) for p in _SHELL_SAFE_PREFIXES):
            return {
                "ok": False,
                "error": f"Not in safe-command whitelist (read-only only): {command[:80]}",
            }
        try:
            import shlex as _shlex
            result = subprocess.run(
                _shlex.split(command), shell=False, capture_output=True, text=True, timeout=15,
            )
            return {
                "ok": True,
                "stdout": result.stdout[:8000],
                "stderr": result.stderr[:2000],
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "command timed out (15 s)"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if name == "contacts_search":
        query = str(args.get("query", "")).strip()
        try:
            from src.guppy.api.routes_workspace_data import _contacts_json
            contacts = _contacts_json(search=query)
            return {"ok": True, "contacts": contacts[:20]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if name == "screenpipe_search":
        query = str(args.get("query", "")).strip()
        try:
            limit = min(max(int(args.get("limit", 5)), 1), 20)
        except (TypeError, ValueError):
            limit = 5
        if not query:
            return {"ok": False, "error": "query required"}
        try:
            from src.guppy.api.routes_screenpipe import _search

            results = await asyncio.to_thread(
                _search,
                query,
                limit,
                "all",
                None,
                None,
                None,
            )
            formatted = [
                {
                    "timestamp": r.get("timestamp", ""),
                    "app": r.get("app_name", "Unknown"),
                    "content": (r.get("content", "") or "")[:240],
                    "type": r.get("type", "unknown"),
                }
                for r in results[:limit]
            ]
            return {
                "ok": True,
                "query": query,
                "count": len(formatted),
                "results": formatted,
            }
        except Exception as e:
            return {"ok": False, "error": f"screenpipe_search failed: {e}"}

    if name == "get_weather":
        location = str(args.get("location", "auto")).strip() or "auto"
        try:
            import httpx
            async with httpx.AsyncClient(timeout=_WEATHER_TIMEOUT, follow_redirects=True) as client:
                resp = await client.get(
                    f"https://wttr.in/{location}",
                    params={"format": "j1"},
                    headers={"User-Agent": "Guppy/1.0"},
                )
                resp.raise_for_status()
            data = resp.json()
            current = data["current_condition"][0]
            area = (data.get("nearest_area") or [{}])[0]
            area_name = (area.get("areaName") or [{}])[0].get("value", location)
            country = (area.get("country") or [{}])[0].get("value", "")
            return {
                "ok": True,
                "location": f"{area_name}, {country}".strip(", "),
                "temp_c": current.get("temp_C"),
                "temp_f": current.get("temp_F"),
                "feels_like_c": current.get("FeelsLikeC"),
                "humidity": current.get("humidity"),
                "description": (current.get("weatherDesc") or [{}])[0].get("value", ""),
                "wind_kmph": current.get("windspeedKmph"),
                "visibility_km": current.get("visibility"),
            }
        except Exception as e:
            return {"ok": False, "error": f"weather lookup failed: {e}"}

    if name == "get_news":
        topic = str(args.get("topic", "")).strip()
        try:
            max_results = min(int(args.get("max_results", 5) or 5), 20)
        except (TypeError, ValueError):
            max_results = 5
        try:
            import feedparser
            if topic.lower() in ("tech", "technology", "programming", "hacking"):
                feed_url = "https://hnrss.org/frontpage"
            elif topic.lower() in ("world", "international", "global"):
                feed_url = "https://feeds.bbci.co.uk/news/world/rss.xml"
            elif topic.lower() in ("business", "finance", "markets"):
                feed_url = "https://feeds.reuters.com/reuters/businessNews"
            elif topic.lower() in ("science",):
                feed_url = "https://feeds.reuters.com/reuters/scienceNews"
            else:
                # General: search HN, fall back to BBC
                feed_url = f"https://hnrss.org/newest?q={topic}&count={max_results}"
            feed = await asyncio.to_thread(feedparser.parse, feed_url)
            items = [
                {
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "summary": (entry.get("summary", "") or "")[:240],
                }
                for entry in feed.entries[:max_results]
            ]
            return {"ok": True, "topic": topic, "count": len(items), "items": items}
        except Exception as e:
            return {"ok": False, "error": f"news lookup failed: {e}"}

    if name == "clipboard_read":
        try:
            import pyperclip
            text = await asyncio.to_thread(pyperclip.paste)
            return {"ok": True, "text": text or ""}
        except Exception as e:
            return {"ok": False, "error": f"clipboard_read failed: {e}"}

    if name == "clipboard_write":
        text = str(args.get("text", ""))
        append = bool(args.get("append", False))
        try:
            import pyperclip
            if append:
                existing = await asyncio.to_thread(pyperclip.paste)
                text = (existing or "") + text
            await asyncio.to_thread(pyperclip.copy, text)
            return {"ok": True, "text": text}
        except Exception as e:
            return {"ok": False, "error": f"clipboard_write failed: {e}"}

    if name == "open_application":
        import webbrowser
        import subprocess
        target = str(args.get("target", "")).strip()
        if not target:
            return {"ok": False, "error": "target required"}
        try:
            if target.startswith(("http://", "https://", "ftp://")):
                await asyncio.to_thread(webbrowser.open, target)
                return {"ok": True, "opened": target, "method": "browser"}
            elif os.name == "nt":
                await asyncio.to_thread(os.startfile, target)  # type: ignore[attr-defined]
                return {"ok": True, "opened": target, "method": "startfile"}
            else:
                proc = await asyncio.to_thread(
                    subprocess.run,
                    ["xdg-open", target],
                    capture_output=True,
                    timeout=5,
                )
                return {"ok": proc.returncode == 0, "opened": target, "method": "xdg-open"}
        except Exception as e:
            return {"ok": False, "error": f"open_application failed: {e}"}

    if name == "api_request":
        method  = str(args.get("method", "GET")).strip().upper()
        url     = str(args.get("url", "")).strip()
        headers = args.get("headers") or {}
        body    = args.get("body")
        try:
            timeout = float(args.get("timeout", _API_TIMEOUT))
        except (TypeError, ValueError):
            timeout = _API_TIMEOUT
        if not url:
            return {"ok": False, "error": "url required"}
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"}:
            return {"ok": False, "error": f"unsupported method: {method}"}
        try:
            import httpx
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                req_kwargs: dict = {"headers": headers}
                if body is not None:
                    if isinstance(body, (dict, list)):
                        req_kwargs["json"] = body
                    else:
                        req_kwargs["content"] = str(body).encode()
                resp = await client.request(method, url, **req_kwargs)
            try:
                resp_body = resp.json()
            except Exception:
                resp_body = resp.text[:8000]
            return {
                "ok": resp.is_success,
                "status": resp.status_code,
                "headers": dict(resp.headers),
                "body": resp_body,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if name == "read_screen_text":
        region = args.get("region")  # optional {"left": x, "top": y, "width": w, "height": h}
        prompt = str(args.get("prompt", "Describe all visible text and UI elements")).strip()
        try:
            import base64
            import httpx
            import io
            try:
                import pyautogui as _pag  # type: ignore
            except ImportError:
                return {"ok": False, "error": "pyautogui not installed"}
            # Capture screenshot (sync → thread)
            if region and isinstance(region, dict):
                raw = await asyncio.to_thread(
                    _pag.screenshot,
                    region=(
                        int(region.get("left", 0)),
                        int(region.get("top", 0)),
                        int(region.get("width", 800)),
                        int(region.get("height", 600)),
                    ),
                )
            else:
                raw = await asyncio.to_thread(_pag.screenshot)
            buf = io.BytesIO()
            raw.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            # Send to MiniCPM vision model if available
            from src.guppy.api.routes_backends import _port_alive as _rpal
            if _rpal(8084):
                vision_payload = {
                    "model": "minicpm-o",
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                            {"type": "text", "text": prompt},
                        ],
                    }],
                    "max_tokens": 512,
                    "stream": False,
                }
                async with httpx.AsyncClient(timeout=_VISION_TIMEOUT) as client:
                    vr = await client.post("http://127.0.0.1:8084/v1/chat/completions", json=vision_payload)
                vdata = vr.json()
                description = (
                    vdata.get("choices", [{}])[0].get("message", {}).get("content", "")
                    or "Vision model returned no content."
                )
            else:
                description = "(Vision model offline — screenshot captured but not described.)"
            return {"ok": True, "description": description, "screenshot_b64": b64}
        except Exception as e:
            return {"ok": False, "error": f"read_screen_text failed: {e}"}

    if name == "write_file":
        import pathlib
        fpath   = str(args.get("path", "")).strip()
        content = str(args.get("content", ""))
        mode    = str(args.get("mode", "overwrite")).strip().lower()
        if not fpath:
            return {"ok": False, "error": "path required"}
        # Build allowlist from env (default: Downloads, Documents, Desktop)
        _default_safe = [
            str(pathlib.Path.home() / "Downloads"),
            str(pathlib.Path.home() / "Documents"),
            str(pathlib.Path.home() / "Desktop"),
        ]
        _env_dirs = os.environ.get("GUPPY_WRITE_DIRS", "")
        _allowed  = [d.strip() for d in _env_dirs.split(";") if d.strip()] or _default_safe
        # Dev mode bypasses allowlist
        _dev = os.environ.get("GUPPY_DEV_MODE", "").lower() in ("1", "true", "yes")
        resolved = str(pathlib.Path(fpath).expanduser().resolve())
        if not _dev and not any(resolved.startswith(a) for a in _allowed):
            return {
                "ok": False,
                "error": (
                    f"Path not in write-allowed directories. "
                    f"Allowed: {_allowed}. Set GUPPY_WRITE_DIRS to override."
                ),
            }
        try:
            p = pathlib.Path(resolved)
            p.parent.mkdir(parents=True, exist_ok=True)
            if mode == "append":
                with open(p, "a", encoding="utf-8") as f:
                    f.write(content)
            else:
                p.write_text(content, encoding="utf-8")
            return {"ok": True, "path": resolved, "bytes_written": len(content.encode())}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    return {"ok": False, "error": f"Unknown workspace tool: {name}"}
