"""Calibre Tier 3 acquisition routes.

GET  /api/tier3/status                        — health check (SE reachable, IA reachable, Mylar3 alive)
GET  /api/tier3/standardebooks/search         — search Standard Ebooks OPDS (?q=&limit=10)
POST /api/tier3/standardebooks/download       — download SE book into Calibre
GET  /api/tier3/internetarchive/search        — search Internet Archive (?q=&limit=10)
GET  /api/tier3/internetarchive/download-url  — get best download URL for an IA item
POST /api/tier3/internetarchive/download      — download IA item into Calibre
GET  /api/tier3/mylar3/search                 — search Mylar3 comic database
POST /api/tier3/mylar3/add                    — add comic to Mylar3
GET  /api/tier3/mylar3/wanted                 — Mylar3 wanted/missing issues
"""
from __future__ import annotations

import asyncio
import urllib.error
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.guppy.api.server_context import ServerContext


def build_tier3_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/tier3")

    def _t3():
        from src.guppy.tools import tier3_tool
        return tier3_tool

    # ── Status ────────────────────────────────────────────────────────────────

    @router.get("/status")
    async def tier3_status(_user_id: str = Depends(ctx.require_rate_limit)):
        t3 = _t3()
        # Probe SE and IA with a lightweight request
        async def _se_alive() -> bool:
            try:
                await asyncio.to_thread(t3._http_get, "https://standardebooks.org/feeds/opds", 5)
                return True
            except Exception:
                return False

        async def _ia_alive() -> bool:
            try:
                await asyncio.to_thread(
                    t3._http_json,
                    "https://archive.org/advancedsearch.php?q=test&output=json&rows=1",
                    5,
                )
                return True
            except Exception:
                return False

        se_configured = t3.standard_ebooks_configured()

        async def _se_probe():
            if not se_configured:
                return False
            return await _se_alive()

        se_alive, ia_alive, mylar_alive = await asyncio.gather(
            _se_probe(),
            _ia_alive(),
            asyncio.to_thread(t3.mylar3_alive),
        )
        return {
            "standard_ebooks": {
                "available": se_alive,
                "configured": se_configured,
                "url": "https://standardebooks.org",
                "note": "Set STANDARD_EBOOKS_EMAIL + STANDARD_EBOOKS_PASSWORD in .env" if not se_configured else None,
            },
            "internet_archive": {"available": ia_alive, "url": "https://archive.org"},
            "mylar3": {
                "available": mylar_alive,
                "url": t3._mylar_url(),
                "configured": bool(t3._mylar_key()),
            },
        }

    # ── Standard Ebooks ───────────────────────────────────────────────────────

    @router.get("/standardebooks/search")
    async def se_search(
        q: str,
        limit: int = 10,
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        if not q:
            raise HTTPException(status_code=400, detail="'q' required")
        t3 = _t3()
        if not t3.standard_ebooks_configured():
            raise HTTPException(
                status_code=503,
                detail="Standard Ebooks not configured. Set STANDARD_EBOOKS_EMAIL and STANDARD_EBOOKS_PASSWORD in .env (free account at standardebooks.org).",
            )
        try:
            results = await asyncio.to_thread(t3.standard_ebooks_search, q, min(limit, 50))
        except urllib.error.URLError:
            raise HTTPException(status_code=503, detail="Cannot reach standardebooks.org")
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Standard Ebooks error: {exc}")
        return {"results": results, "count": len(results), "source": "Standard Ebooks"}

    @router.post("/standardebooks/download")
    async def se_download(
        payload: dict[str, Any],
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        """Download a Standard Ebooks book into the local Calibre library.

        Pass either {"epub_url": "https://..."} from search results,
        or {"title": "...", "author": "..."} to auto-search-and-download the first result.
        """
        from src.guppy.tools.calibre_tool import calibre_add, calibre_available
        if not calibre_available():
            raise HTTPException(status_code=503, detail="Calibre not installed")

        epub_url = str(payload.get("epub_url", "")).strip()
        if not epub_url:
            # auto-search
            title = str(payload.get("title", "")).strip()
            author = str(payload.get("author", "")).strip()
            query = f"{title} {author}".strip()
            if not query:
                raise HTTPException(status_code=400, detail="'epub_url', 'title', or 'author' required")
            t3 = _t3()
            results = await asyncio.to_thread(t3.standard_ebooks_search, query, 1)
            if not results:
                raise HTTPException(status_code=404, detail=f"No Standard Ebooks results for '{query}'")
            epub_url = results[0].get("epub_url") or ""
            if not epub_url:
                raise HTTPException(status_code=404, detail="No EPUB URL in first result")

        try:
            result = await asyncio.to_thread(calibre_add, epub_url)
            result["epub_url"] = epub_url
            return result
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    # ── Internet Archive ──────────────────────────────────────────────────────

    @router.get("/internetarchive/search")
    async def ia_search(
        q: str,
        limit: int = 10,
        media_type: str = "texts",
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        if not q:
            raise HTTPException(status_code=400, detail="'q' required")
        t3 = _t3()
        try:
            results = await asyncio.to_thread(
                t3.internet_archive_search, q, min(limit, 50), media_type
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Internet Archive error: {exc}")
        return {"results": results, "count": len(results), "source": "Internet Archive"}

    @router.get("/internetarchive/download-url")
    async def ia_download_url(
        identifier: str,
        prefer_format: str = "epub",
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        if not identifier:
            raise HTTPException(status_code=400, detail="'identifier' required")
        t3 = _t3()
        try:
            url = await asyncio.to_thread(
                t3.internet_archive_get_download_url, identifier, prefer_format
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Internet Archive error: {exc}")
        if not url:
            raise HTTPException(
                status_code=404,
                detail=f"No {prefer_format.upper()} or PDF found for '{identifier}'",
            )
        return {"identifier": identifier, "download_url": url, "prefer_format": prefer_format}

    @router.post("/internetarchive/download")
    async def ia_download(
        payload: dict[str, Any],
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        identifier = str(payload.get("identifier", "")).strip()
        if not identifier:
            raise HTTPException(status_code=400, detail="'identifier' required")
        t3 = _t3()
        try:
            return await asyncio.to_thread(t3.internet_archive_download_to_calibre, identifier)
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Internet Archive error: {exc}")

    # ── Mylar3 ────────────────────────────────────────────────────────────────

    @router.get("/mylar3/search")
    async def mylar3_search(
        q: str,
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        if not q:
            raise HTTPException(status_code=400, detail="'q' required")
        t3 = _t3()
        try:
            results = await asyncio.to_thread(t3.mylar3_search_comic, q)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except urllib.error.URLError:
            raise HTTPException(status_code=503, detail="Mylar3 not reachable")
        return {"results": results, "count": len(results)}

    @router.post("/mylar3/add")
    async def mylar3_add(
        payload: dict[str, Any],
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        comic_id = str(payload.get("comic_id", "")).strip()
        if not comic_id:
            raise HTTPException(status_code=400, detail="'comic_id' required")
        t3 = _t3()
        try:
            return await asyncio.to_thread(t3.mylar3_add_comic, comic_id)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except urllib.error.URLError:
            raise HTTPException(status_code=503, detail="Mylar3 not reachable")

    @router.get("/mylar3/wanted")
    async def mylar3_wanted(_user_id: str = Depends(ctx.require_rate_limit)):
        t3 = _t3()
        try:
            wanted = await asyncio.to_thread(t3.mylar3_get_wanted)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except urllib.error.URLError:
            raise HTTPException(status_code=503, detail="Mylar3 not reachable")
        return {"wanted": wanted, "count": len(wanted)}

    return router
