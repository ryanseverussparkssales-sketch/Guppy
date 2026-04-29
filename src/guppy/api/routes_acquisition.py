"""Automated book acquisition routes — LazyLibrarian + Prowlarr (Calibre Tier 2).

GET  /api/acquisition/status                   — health check for both services
GET  /api/acquisition/lazylibrarian/search     — search LL book database
GET  /api/acquisition/lazylibrarian/wanted     — current wanted list
POST /api/acquisition/lazylibrarian/add        — add book to wanted list
POST /api/acquisition/lazylibrarian/add-author — watch all books by an author
GET  /api/acquisition/lazylibrarian/downloads  — recent download history
GET  /api/acquisition/prowlarr/search          — search across all indexers
GET  /api/acquisition/prowlarr/indexers        — list configured indexers
"""
from __future__ import annotations

import asyncio
import urllib.error
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.guppy.api.server_context import ServerContext


def build_acquisition_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/acquisition")

    def _at():
        from src.guppy.tools import acquisition_tool
        return acquisition_tool

    # ── Status ────────────────────────────────────────────────────────────────

    @router.get("/status")
    async def acquisition_status(_user_id: str = Depends(ctx.require_rate_limit)):
        at = _at()
        ll_alive, pr_alive = await asyncio.gather(
            asyncio.to_thread(at.lazylibrarian_alive),
            asyncio.to_thread(at.prowlarr_alive),
        )
        return {
            "lazylibrarian": {
                "available": ll_alive,
                "url": at._ll_url(),
                "configured": bool(at._ll_key()),
            },
            "prowlarr": {
                "available": pr_alive,
                "url": at._pr_url(),
                "configured": bool(at._pr_key()),
            },
        }

    # ── LazyLibrarian ─────────────────────────────────────────────────────────

    @router.get("/lazylibrarian/search")
    async def ll_search(
        q: str = "",
        author: str = "",
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        if not q and not author:
            raise HTTPException(status_code=400, detail="'q' (title) or 'author' required")
        at = _at()
        try:
            books = await asyncio.to_thread(at.lazylibrarian_search_book, q, author)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except urllib.error.URLError:
            raise HTTPException(status_code=503, detail="LazyLibrarian not reachable")
        return {"books": books, "count": len(books)}

    @router.get("/lazylibrarian/wanted")
    async def ll_wanted(_user_id: str = Depends(ctx.require_rate_limit)):
        at = _at()
        try:
            books = await asyncio.to_thread(at.lazylibrarian_get_wanted)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except urllib.error.URLError:
            raise HTTPException(status_code=503, detail="LazyLibrarian not reachable")
        return {"books": books, "count": len(books)}

    @router.post("/lazylibrarian/add")
    async def ll_add_book(
        payload: dict[str, Any],
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        goodreads_id = str(payload.get("goodreads_id", "")).strip()
        isbn = str(payload.get("isbn", "")).strip()
        if not goodreads_id and not isbn:
            raise HTTPException(status_code=400, detail="'goodreads_id' or 'isbn' required")
        at = _at()
        try:
            return await asyncio.to_thread(at.lazylibrarian_add_wanted, goodreads_id, isbn)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        except urllib.error.URLError:
            raise HTTPException(status_code=503, detail="LazyLibrarian not reachable")

    @router.post("/lazylibrarian/add-author")
    async def ll_add_author(
        payload: dict[str, Any],
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        name = str(payload.get("name", "")).strip()
        if not name:
            raise HTTPException(status_code=400, detail="'name' (author name) required")
        at = _at()
        try:
            return await asyncio.to_thread(at.lazylibrarian_add_author, name)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except urllib.error.URLError:
            raise HTTPException(status_code=503, detail="LazyLibrarian not reachable")

    @router.get("/lazylibrarian/downloads")
    async def ll_downloads(_user_id: str = Depends(ctx.require_rate_limit)):
        at = _at()
        try:
            history = await asyncio.to_thread(at.lazylibrarian_get_downloads)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except urllib.error.URLError:
            raise HTTPException(status_code=503, detail="LazyLibrarian not reachable")
        return {"downloads": history, "count": len(history)}

    # ── Prowlarr ──────────────────────────────────────────────────────────────

    @router.get("/prowlarr/search")
    async def pr_search(
        q: str,
        limit: int = 20,
        ebooks_only: bool = True,
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        if not q:
            raise HTTPException(status_code=400, detail="'q' required")
        at = _at()
        categories = [7000, 7020] if ebooks_only else None  # 7000=Books, 7020=eBook
        try:
            results = await asyncio.to_thread(at.prowlarr_search, q, categories, min(limit, 100))
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except urllib.error.URLError:
            raise HTTPException(status_code=503, detail="Prowlarr not reachable")
        return {"results": results, "count": len(results), "query": q}

    @router.get("/prowlarr/indexers")
    async def pr_indexers(_user_id: str = Depends(ctx.require_rate_limit)):
        at = _at()
        try:
            indexers = await asyncio.to_thread(at.prowlarr_list_indexers)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except urllib.error.URLError:
            raise HTTPException(status_code=503, detail="Prowlarr not reachable")
        return {
            "indexers": indexers,
            "count": len(indexers),
            "enabled": sum(1 for i in indexers if i.get("enable")),
        }

    return router
