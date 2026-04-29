"""Screenpipe integration routes.

Screenpipe (https://github.com/mediar-ai/screenpipe) is a self-hosted daemon
that continuously captures screen frames + audio, runs local OCR and Whisper
transcription, and stores everything in SQLite. Its REST API lets you query
that history by keyword, time range, or content type.

GET  /api/screenpipe/status           — health check (is Screenpipe daemon up?)
GET  /api/screenpipe/search           — search screen/audio history
GET  /api/screenpipe/recent           — recent activity (last N minutes)

Environment:
    SCREENPIPE_URL   — base URL of the Screenpipe daemon (default: http://localhost:3030)
"""
from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.guppy.api.server_context import ServerContext

_DEFAULT_SCREENPIPE_URL = "http://localhost:3030"


def _sp_url() -> str:
    return os.environ.get("SCREENPIPE_URL", _DEFAULT_SCREENPIPE_URL).rstrip("/")


def _http_get(path: str, timeout: int = 10) -> Any:
    url = f"{_sp_url()}{path}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _screenpipe_alive() -> bool:
    try:
        _http_get("/health", timeout=3)
        return True
    except Exception:
        return False


def _search(
    query: str,
    limit: int = 20,
    content_type: str = "all",
    start_time: str | None = None,
    end_time: str | None = None,
    app_name: str | None = None,
) -> list[dict[str, Any]]:
    """Query Screenpipe's search endpoint."""
    from urllib.parse import urlencode
    params: dict[str, Any] = {
        "q": query,
        "limit": min(limit, 100),
        "content_type": content_type,  # "ocr" | "audio" | "all"
    }
    if start_time:
        params["start_time"] = start_time
    if end_time:
        params["end_time"] = end_time
    if app_name:
        params["app_name"] = app_name
    qs = urlencode(params)
    data = _http_get(f"/search?{qs}")
    # Screenpipe returns {"data": [...], "pagination": {...}}
    return data.get("data") or []


def _recent(minutes: int = 30, limit: int = 20) -> list[dict[str, Any]]:
    """Fetch recent screen activity from the last N minutes."""
    from datetime import datetime, timedelta, timezone
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=minutes)
    return _search(
        query="",
        limit=limit,
        content_type="all",
        start_time=start.isoformat(),
        end_time=end.isoformat(),
    )


def build_screenpipe_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/screenpipe")

    @router.get("/status")
    async def screenpipe_status(_user_id: str = Depends(ctx.require_rate_limit)):
        alive = await asyncio.to_thread(_screenpipe_alive)
        return {
            "available": alive,
            "url": _sp_url(),
            "configured": os.environ.get("SCREENPIPE_URL") is not None,
        }

    @router.get("/search")
    async def screenpipe_search(
        q: str,
        limit: int = 20,
        content_type: str = "all",
        start_time: str | None = None,
        end_time: str | None = None,
        app_name: str | None = None,
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        if not q:
            raise HTTPException(status_code=400, detail="'q' required")
        try:
            results = await asyncio.to_thread(
                _search, q, min(limit, 100), content_type, start_time, end_time, app_name
            )
        except urllib.error.URLError:
            raise HTTPException(
                status_code=503,
                detail=f"Screenpipe not reachable at {_sp_url()} — is the daemon running?",
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Screenpipe error: {exc}")
        return {
            "results": results,
            "count": len(results),
            "query": q,
            "content_type": content_type,
        }

    @router.get("/recent")
    async def screenpipe_recent(
        minutes: int = 30,
        limit: int = 20,
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        try:
            results = await asyncio.to_thread(_recent, min(minutes, 1440), min(limit, 100))
        except urllib.error.URLError:
            raise HTTPException(
                status_code=503,
                detail=f"Screenpipe not reachable at {_sp_url()} — is the daemon running?",
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Screenpipe error: {exc}")
        return {
            "results": results,
            "count": len(results),
            "window_minutes": minutes,
        }

    return router
