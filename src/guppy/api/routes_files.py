"""
File & System API

GET  /api/files/info            — metadata for a single file (?path=)
POST /api/files/read            — extract text from any supported file
GET  /api/files/browse          — list directory contents (?path=&pattern=)
GET  /api/system/info           — CPU, RAM, disk, uptime snapshot
GET  /api/system/processes      — top N processes (?limit=10&sort=cpu)
GET  /api/system/disk           — disk usage for a path (?path=C:/)
GET  /api/system/network        — network I/O counters
GET  /api/clipboard             — read clipboard
POST /api/clipboard             — write clipboard  {"text": "..."}
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.guppy.api.server_context import ServerContext


class ReadRequest(BaseModel):
    path: str
    max_chars: int = 50_000


class ClipboardWriteRequest(BaseModel):
    text: str
    append: bool = False
    separator: str = "\n"


def build_files_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(tags=["files"])

    # ── File operations ───────────────────────────────────────────────────────

    @router.get("/api/files/info")
    def get_file_info(
        path: str = Query(..., description="Absolute or ~ path to file"),
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        from src.guppy.tools.file_tool import file_info
        try:
            return file_info(path)
        except FileNotFoundError as e:
            raise HTTPException(404, str(e))
        except Exception as e:
            raise HTTPException(400, str(e))

    @router.post("/api/files/read")
    def read_file(body: ReadRequest, _uid: str = Depends(ctx.require_rate_limit)):
        """Extract text content from any supported file type.

        Handles PDF, DOCX, XLSX, CSV, PPTX, images (EXIF), and all text/code formats.
        Large files are truncated to max_chars to protect context windows.
        """
        from src.guppy.tools.file_tool import extract_text
        try:
            return extract_text(body.path, body.max_chars)
        except FileNotFoundError as e:
            raise HTTPException(404, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))
        except Exception as e:
            raise HTTPException(500, f"Extraction failed: {e}")

    @router.get("/api/files/browse")
    def browse_directory(
        path: str = Query(..., description="Directory path to list"),
        pattern: str = Query(default="*", description="Glob pattern, e.g. *.pdf"),
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        from src.guppy.tools.file_tool import list_directory
        try:
            return list_directory(path, pattern)
        except FileNotFoundError as e:
            raise HTTPException(404, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))

    # ── System monitoring ─────────────────────────────────────────────────────

    @router.get("/api/system/info")
    def get_system_info(_uid: str = Depends(ctx.require_rate_limit)):
        from src.guppy.tools.system_tool import system_info
        return system_info()

    @router.get("/api/system/processes")
    def get_processes(
        limit: int = Query(default=10, ge=1, le=100),
        sort: str = Query(default="cpu", pattern="^(cpu|memory)$"),
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        from src.guppy.tools.system_tool import top_processes
        return {"processes": top_processes(limit=limit, sort_by=sort)}

    @router.get("/api/system/disk")
    def get_disk_usage(
        path: str = Query(default="C:/"),
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        from src.guppy.tools.system_tool import disk_usage
        try:
            return disk_usage(path)
        except Exception as e:
            raise HTTPException(400, str(e))

    @router.get("/api/system/network")
    def get_network_stats(_uid: str = Depends(ctx.require_rate_limit)):
        from src.guppy.tools.system_tool import network_stats
        return network_stats()

    # ── Clipboard ─────────────────────────────────────────────────────────────

    @router.get("/api/clipboard")
    def read_clipboard(_uid: str = Depends(ctx.require_rate_limit)):
        from src.guppy.tools.clipboard_tool import clipboard_read
        return clipboard_read()

    @router.post("/api/clipboard")
    def write_clipboard(
        body: ClipboardWriteRequest,
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        from src.guppy.tools.clipboard_tool import clipboard_write, clipboard_append
        if body.append:
            return clipboard_append(body.text, body.separator)
        return clipboard_write(body.text)

    return router
