"""Calibre library and Kindle delivery API routes.

GET  /api/calibre/status                — calibre install check + config
GET  /api/calibre/search                — search local library (?q=&limit=20)
POST /api/calibre/add                   — add book from URL or local path
POST /api/calibre/set-metadata          — update book fields
GET  /api/calibre/gutenberg/search      — search Project Gutenberg (?q=&limit=10)
POST /api/calibre/gutenberg/download    — download Gutenberg book into calibre
GET  /api/calibre/openlibrary/search    — search Open Library (?q=&limit=10)
POST /api/calibre/send-to-kindle        — convert + email calibre book to Kindle
POST /api/calibre/organize              — list books missing tags (for agent tagging)

GET  /api/kindle/status                 — Kindle delivery config check
POST /api/kindle/send                   — send any URL/file directly to Kindle
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.guppy.api.server_context import ServerContext


def build_calibre_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/calibre")

    # Lazy import so startup doesn't fail if calibre isn't installed
    def _ct():
        from src.guppy.tools import calibre_tool
        return calibre_tool

    # ── Status ───────────────────────────────────────────────────────────────

    @router.get("/status")
    async def calibre_status(_user_id: str = Depends(ctx.require_rate_limit)):
        ct = _ct()
        return {
            "calibre_available":       ct.calibre_available(),
            "ebook_convert_available": ct.ebook_convert_available(),
            "library_path":            os.environ.get("CALIBRE_LIBRARY_PATH") or None,
            "kindle_configured":       bool(os.environ.get("KINDLE_EMAIL")),
            "smtp_configured":         bool(os.environ.get("SMTP_USER") and os.environ.get("SMTP_PASS")),
        }

    # ── Local library ─────────────────────────────────────────────────────────

    @router.get("/search")
    async def search_library(
        q: str = "",
        limit: int = 20,
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        ct = _ct()
        if not ct.calibre_available():
            raise HTTPException(status_code=503, detail="Calibre not installed")
        try:
            books = await asyncio.to_thread(ct.calibre_search, q, min(limit, 200))
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        return {"books": books, "count": len(books)}

    @router.post("/add")
    async def add_book(
        payload: dict[str, Any],
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        source = str(payload.get("source", "")).strip()
        if not source:
            raise HTTPException(status_code=400, detail="'source' (URL or file path) required")
        ct = _ct()
        if not ct.calibre_available():
            raise HTTPException(status_code=503, detail="Calibre not installed")
        try:
            return await asyncio.to_thread(ct.calibre_add, source)
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @router.post("/set-metadata")
    async def set_metadata(
        payload: dict[str, Any],
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        book_id = payload.get("book_id")
        fields: dict[str, str] = payload.get("fields", {})
        if not book_id:
            raise HTTPException(status_code=400, detail="'book_id' required")
        if not fields:
            raise HTTPException(status_code=400, detail="'fields' must be non-empty")
        ct = _ct()
        if not ct.calibre_available():
            raise HTTPException(status_code=503, detail="Calibre not installed")
        try:
            return await asyncio.to_thread(ct.calibre_set_metadata, int(book_id), fields)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    # ── Gutenberg ─────────────────────────────────────────────────────────────

    @router.get("/gutenberg/search")
    async def gutenberg_search(
        q: str,
        limit: int = 10,
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        if not q:
            raise HTTPException(status_code=400, detail="'q' required")
        ct = _ct()
        try:
            results = await asyncio.to_thread(ct.gutenberg_search, q, min(limit, 50))
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Gutendex error: {exc}")
        return {"results": results, "count": len(results), "source": "Project Gutenberg"}

    @router.post("/gutenberg/download")
    async def gutenberg_download(
        payload: dict[str, Any],
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        book_id = payload.get("book_id")
        if not book_id:
            raise HTTPException(status_code=400, detail="'book_id' required")
        ct = _ct()
        if not ct.calibre_available():
            raise HTTPException(status_code=503, detail="Calibre not installed")
        try:
            return await asyncio.to_thread(ct.gutenberg_download_to_calibre, int(book_id))
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    # ── Open Library ──────────────────────────────────────────────────────────

    @router.get("/openlibrary/search")
    async def openlibrary_search(
        q: str,
        limit: int = 10,
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        if not q:
            raise HTTPException(status_code=400, detail="'q' required")
        ct = _ct()
        try:
            results = await asyncio.to_thread(ct.openlibrary_search, q, min(limit, 50))
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Open Library error: {exc}")
        return {"results": results, "count": len(results), "source": "Open Library"}

    # ── Send-to-Kindle ────────────────────────────────────────────────────────

    @router.post("/send-to-kindle")
    async def send_to_kindle(
        payload: dict[str, Any],
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        book_id = payload.get("book_id")
        if not book_id:
            raise HTTPException(status_code=400, detail="'book_id' required")
        ct = _ct()
        if not ct.calibre_available():
            raise HTTPException(status_code=503, detail="Calibre not installed")
        if not ct.ebook_convert_available():
            raise HTTPException(status_code=503, detail="ebook-convert not found")
        try:
            return await asyncio.to_thread(ct.send_to_kindle, int(book_id))
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    # ── Organize (agent tagging helper) ──────────────────────────────────────

    @router.post("/organize")
    async def organize_library(
        payload: dict[str, Any] | None = None,
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        """Return books that are missing tags so the agent can tag them.

        The agent calls GET /api/calibre/search, decides on tags per book,
        then calls POST /api/calibre/set-metadata for each one. This endpoint
        just surfaces the untagged list to make that loop easy to start.
        """
        ct = _ct()
        if not ct.calibre_available():
            raise HTTPException(status_code=503, detail="Calibre not installed")
        limit = int((payload or {}).get("limit", 50))
        try:
            all_books = await asyncio.to_thread(ct.calibre_search, "", min(limit, 200))
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc))

        untagged = [
            b for b in all_books
            if not (b.get("tags") or "").strip()
        ]
        return {
            "untagged": untagged,
            "untagged_count": len(untagged),
            "total_count": len(all_books),
            "hint": (
                "For each book, call POST /api/calibre/set-metadata with "
                "{'book_id': id, 'fields': {'tags': 'fiction, ...'}}"
            ),
        }

    return router


def build_kindle_router(ctx: ServerContext) -> APIRouter:
    """Standalone Kindle delivery routes — no Calibre library required."""
    router = APIRouter(prefix="/api/kindle")

    def _ct():
        from src.guppy.tools import calibre_tool
        return calibre_tool

    @router.get("/status")
    async def kindle_status(_user_id: str = Depends(ctx.require_rate_limit)):
        import os as _os
        return {
            "kindle_configured": bool(_os.environ.get("KINDLE_EMAIL")),
            "kindle_email": _os.environ.get("KINDLE_EMAIL") or None,
            "smtp_configured": bool(_os.environ.get("SMTP_USER") and _os.environ.get("SMTP_PASS")),
            "ebook_convert_available": _ct().ebook_convert_available(),
            "note": (
                "Set KINDLE_EMAIL, SMTP_USER, SMTP_PASS in .env. "
                "Sender must be whitelisted in Amazon's 'Approved Personal Document E-mail List'."
            ),
        }

    @router.post("/send")
    async def kindle_send(
        payload: dict[str, Any],
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        """Send any URL or local file path directly to Kindle.

        Accepts: {"source": "https://...", "format": "mobi"}
        Converts with ebook-convert if needed (requires Calibre).
        Does NOT add the book to the Calibre library.
        """
        source = str(payload.get("source", "")).strip()
        fmt = str(payload.get("format", "mobi")).strip().lower() or "mobi"
        if not source:
            raise HTTPException(status_code=400, detail="'source' (URL or file path) required")
        ct = _ct()
        try:
            return await asyncio.to_thread(ct.kindle_send_direct, source, fmt)
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    return router
