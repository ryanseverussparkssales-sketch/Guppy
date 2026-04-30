"""
Drop Folder — watch a desktop folder and auto-extract any file dropped into it.

Default folder: ~/Desktop/GuppyDrop  (auto-created on first use)
Override via:   GUPPY_DROP_FOLDER env var

Events are pushed to all connected SSE clients immediately.
Items accumulate in _drop_queue so clients that connect later still see them.

Endpoints:
  GET  /api/drop/status           — watcher health + folder path + queue count
  GET  /api/drop/stream           — SSE stream of drop events
  GET  /api/drop/queue            — current unread item list
  DELETE /api/drop/items/{id}     — dismiss a single item
  POST /api/drop/clear            — dismiss all items
  POST /api/drop/restart          — restart the watcher (e.g. after folder change)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from src.guppy.api.server_context import ServerContext

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _drop_folder() -> Path:
    env = os.environ.get("GUPPY_DROP_FOLDER", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return Path.home() / "Desktop" / "GuppyDrop"

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

_drop_queue: list[dict[str, Any]] = []          # all unread items
_seen_paths: set[str] = set()                    # dedup processed files
_sse_clients: set[asyncio.Queue] = set()         # one Queue per SSE connection
_loop: asyncio.AbstractEventLoop | None = None   # captured on first async request
_observer = None                                 # watchdog.observers.Observer
_observer_lock = threading.Lock()

# ---------------------------------------------------------------------------
# File processing (runs in watchdog thread)
# ---------------------------------------------------------------------------

_IGNORE_SUFFIXES = {".tmp", ".part", ".crdownload", ".download", ".swp", ".~lock"}
_IGNORE_PREFIXES = {".", "~$"}

def _should_ignore(path: str) -> bool:
    name = Path(path).name
    if any(name.startswith(p) for p in _IGNORE_PREFIXES):
        return True
    if any(name.lower().endswith(s) for s in _IGNORE_SUFFIXES):
        return True
    return False


def _process_file(path: str) -> None:
    """Called from watchdog thread. Extract text and broadcast to SSE clients."""
    if _should_ignore(path):
        return
    resolved = str(Path(path).resolve())
    if resolved in _seen_paths:
        return
    _seen_paths.add(resolved)

    # Brief pause — Windows copy may emit a create event before the file is fully written
    time.sleep(0.6)

    p = Path(resolved)
    if not p.exists() or not p.is_file():
        return

    _log.info("[Drop] Processing: %s", p.name)

    try:
        from src.guppy.tools.file_tool import extract_text
        result = extract_text(resolved, max_chars=40_000)
    except Exception as exc:
        _log.warning("[Drop] Extraction failed for %s: %s", p.name, exc)
        result = {
            "format": p.suffix.lstrip(".") or "unknown",
            "text": f"[Could not extract text: {exc}]",
            "truncated": False,
            "token_estimate": 0,
            "file_size": "?",
        }

    item: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "filename": p.name,
        "path": resolved,
        "dropped_at": datetime.now(timezone.utc).isoformat(),
        **{k: result.get(k) for k in (
            "format", "text", "truncated", "token_estimate", "file_size",
            "pages", "slides", "sheets", "rows", "lines", "encoding",
        ) if result.get(k) is not None},
    }

    _drop_queue.append(item)

    # Auto-add dropped book files into the library and trigger enrichment.
    try:
        ext = p.suffix.lower()
        if ext in {".pdf", ".epub", ".mobi"}:
            from src.guppy.api import routes_library as _lib
            from src.guppy.library.enricher import enrich as _enrich

            lib_data = _lib._load()
            exists = any(str(x.get("file_path", "")) == resolved for x in lib_data.get("items", []))
            if not exists:
                now = _lib._now()
                meta = _enrich(p.stem, "")
                lib_item = {
                    "id": str(uuid.uuid4()),
                    "type": "artifact",
                    "title": p.stem,
                    "content": f"Imported from GuppyDrop: {p.name}",
                    "collection": None,
                    "tags": ["guppydrop", ext.lstrip(".")],
                    "is_favorite": False,
                    "created_at": now,
                    "updated_at": now,
                    "file_path": resolved,
                    "file_ext": ext,
                    "metadata_status": "enriched" if meta.get("found") else "missing",
                    "cover_url": meta.get("cover_url"),
                    "description": meta.get("description"),
                    "isbn": meta.get("isbn"),
                    "subjects": meta.get("subjects") or [],
                    "publish_year": meta.get("publish_year"),
                }
                lib_data.setdefault("items", []).append(lib_item)
                _lib._save(lib_data)
    except Exception as exc:
        _log.debug("[Drop] Auto-library sync skipped: %s", exc)

    # Broadcast to all SSE clients (thread-safe via call_soon_threadsafe)
    if _loop is not None:
        _loop.call_soon_threadsafe(_broadcast, item)
    else:
        _log.debug("[Drop] No event loop yet — item queued, will send on next SSE connect")


def _broadcast(item: dict) -> None:
    """Called in the asyncio event loop thread."""
    dead: set[asyncio.Queue] = set()
    for q in _sse_clients:
        try:
            q.put_nowait(item)
        except asyncio.QueueFull:
            dead.add(q)
    _sse_clients -= dead

# ---------------------------------------------------------------------------
# Watchdog observer
# ---------------------------------------------------------------------------

def _start_observer() -> None:
    global _observer
    with _observer_lock:
        if _observer is not None and _observer.is_alive():
            return

        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent

            folder = _drop_folder()
            folder.mkdir(parents=True, exist_ok=True)

            class _Handler(FileSystemEventHandler):
                def on_created(self, event):
                    if not event.is_directory:
                        threading.Thread(
                            target=_process_file, args=(event.src_path,), daemon=True
                        ).start()

                def on_moved(self, event):
                    # File dragged into the folder from outside
                    if not event.is_directory:
                        dest = getattr(event, "dest_path", "")
                        if dest and str(folder) in dest:
                            threading.Thread(
                                target=_process_file, args=(dest,), daemon=True
                            ).start()

            obs = Observer()
            obs.schedule(_Handler(), str(folder), recursive=False)
            obs.daemon = True
            obs.start()
            _observer = obs
            _log.info("[Drop] Watching: %s", folder)
        except Exception as exc:
            _log.error("[Drop] Could not start watcher: %s", exc)


def _stop_observer() -> None:
    global _observer
    with _observer_lock:
        if _observer is not None:
            try:
                _observer.stop()
                _observer.join(timeout=3)
            except Exception:
                pass
            _observer = None

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def build_drop_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/drop", tags=["drop"])

    # Start watcher immediately
    _start_observer()

    def _capture_loop():
        global _loop
        if _loop is None:
            try:
                _loop = asyncio.get_event_loop()
            except RuntimeError:
                pass

    @router.get("/status")
    async def drop_status(_uid: str = Depends(ctx.require_rate_limit)):
        _capture_loop()
        folder = _drop_folder()
        alive = _observer is not None and _observer.is_alive()
        return {
            "watching": alive,
            "folder": str(folder),
            "folder_exists": folder.exists(),
            "queue_count": len(_drop_queue),
            "connected_clients": len(_sse_clients),
        }

    @router.get("/stream")
    async def drop_stream(_uid: str = Depends(ctx.require_rate_limit)):
        """SSE stream — sends all pending items on connect, then live drops."""
        _capture_loop()
        q: asyncio.Queue = asyncio.Queue(maxsize=50)
        _sse_clients.add(q)

        async def event_gen():
            try:
                # Flush existing queue to this new client
                for item in list(_drop_queue):
                    yield f"event: drop\ndata: {json.dumps(item)}\n\n"

                # Then stream new events
                while True:
                    try:
                        item = await asyncio.wait_for(q.get(), timeout=25)
                        yield f"event: drop\ndata: {json.dumps(item)}\n\n"
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
            except asyncio.CancelledError:
                pass
            finally:
                _sse_clients.discard(q)

        return StreamingResponse(
            event_gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @router.get("/queue")
    async def get_queue(_uid: str = Depends(ctx.require_rate_limit)):
        _capture_loop()
        return {"items": list(_drop_queue), "count": len(_drop_queue)}

    @router.delete("/items/{item_id}", status_code=204)
    async def dismiss_item(item_id: str, _uid: str = Depends(ctx.require_rate_limit)):
        original = len(_drop_queue)
        _drop_queue[:] = [i for i in _drop_queue if i["id"] != item_id]
        if len(_drop_queue) == original:
            from fastapi import HTTPException
            raise HTTPException(404, f"Item '{item_id}' not found")

    @router.post("/clear", status_code=204)
    async def clear_queue(_uid: str = Depends(ctx.require_rate_limit)):
        _drop_queue.clear()

    @router.post("/restart", status_code=204)
    async def restart_watcher(_uid: str = Depends(ctx.require_rate_limit)):
        _stop_observer()
        _start_observer()

    return router
