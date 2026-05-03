"""Screen activity monitor — timeline aggregation over Screenpipe data.

Groups raw Screenpipe OCR/audio captures into 30-minute activity windows,
stores them in SQLite, and exposes a timeline API. After each snapshot a
phi-4-mini → hermes4 cascade generates a one-sentence AI activity summary
("You were working on…"). A background job runs every 30 minutes; the UI
can also trigger on-demand snapshots.

GET  /api/screen/timeline         — list windows (today by default)
GET  /api/screen/timeline/today   — today's windows, newest first
POST /api/screen/timeline/snapshot — capture right now (last 30 min)
GET  /api/screen/status           — monitor job status
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.guppy.api.server_context import ServerContext

logger = logging.getLogger(__name__)

# ── DB ────────────────────────────────────────────────────────────────────────

from src.guppy.paths import MAIN_DB_PATH
_DB_PATH = str(MAIN_DB_PATH)


def _conn() -> sqlite3.Connection:
    MAIN_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS screen_windows (
            id           TEXT PRIMARY KEY,
            window_start TEXT NOT NULL,
            window_end   TEXT NOT NULL,
            apps         TEXT NOT NULL DEFAULT '[]',
            highlights   TEXT NOT NULL DEFAULT '[]',
            item_count   INTEGER NOT NULL DEFAULT 0,
            word_count   INTEGER NOT NULL DEFAULT 0,
            summary      TEXT NOT NULL DEFAULT '',
            created_at   TEXT NOT NULL
        )
    """)
    # Migration: add summary column if absent (existing DB from prior version)
    try:
        conn.execute("ALTER TABLE screen_windows ADD COLUMN summary TEXT NOT NULL DEFAULT ''")
    except Exception:
        pass  # column already exists
    conn.commit()
    return conn


# ── Screenpipe helpers ────────────────────────────────────────────────────────

def _call_screenpipe_recent(minutes: int = 30, limit: int = 100) -> list[dict[str, Any]]:
    """Call the Screenpipe daemon; fall back to native window tracker if unavailable."""
    try:
        import os, json as _json, urllib.request
        from urllib.parse import urlencode
        from datetime import datetime as _dt, timedelta as _td, timezone as _tz
        base = os.environ.get("SCREENPIPE_URL", "http://localhost:3030").rstrip("/")
        end = _dt.now(_tz.utc)
        start = end - _td(minutes=minutes)
        params = urlencode({
            "q": "", "limit": limit, "content_type": "all",
            "start_time": start.isoformat(), "end_time": end.isoformat(),
        })
        url = f"{base}/search?{params}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read().decode())
            items = data.get("data") or []
            if items:
                return items
            # Screenpipe online but returned no data — fall through to native
    except Exception as exc:
        logger.debug("[screen_monitor] screenpipe unavailable: %s", exc)

    # Native fallback: ctypes window title tracker
    try:
        from src.guppy.workspace.native_activity import get_recent_activity, start_tracker
        start_tracker()
        native_items = get_recent_activity(minutes=minutes)
        if native_items:
            logger.debug("[screen_monitor] native fallback returned %d entries", len(native_items))
        # Unwrap to flat dicts expected by _extract_app_names / _extract_highlights
        flat: list[dict[str, Any]] = []
        for item in native_items:
            content = item.get("content") or {}
            flat.append({
                "app_name": content.get("app_name", ""),
                "window_name": content.get("window_name", ""),
                "text": content.get("text", ""),
            })
        return flat
    except Exception as exc:
        logger.debug("[screen_monitor] native fallback error: %s", exc)
        return []


def _extract_app_names(items: list[dict]) -> list[str]:
    seen: dict[str, int] = {}
    for item in items:
        app = item.get("app_name") or item.get("window_name") or ""
        if app:
            seen[app] = seen.get(app, 0) + 1
    return sorted(seen, key=lambda k: seen[k], reverse=True)[:10]


def _extract_highlights(items: list[dict]) -> list[str]:
    """Pick up to 5 distinct meaningful text snippets."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        body = (item.get("text") or item.get("content") or item.get("transcription") or "").strip()
        if len(body) < 20:
            continue
        snippet = body[:120].strip()
        if snippet and snippet not in seen:
            seen.add(snippet)
            result.append(snippet)
        if len(result) >= 5:
            break
    return result


def _word_count(items: list[dict]) -> int:
    total = 0
    for item in items:
        body = item.get("text") or item.get("content") or item.get("transcription") or ""
        total += len(body.split())
    return total


# ── AI summary ────────────────────────────────────────────────────────────────

def _generate_ai_summary(apps: list[str], highlights: list[str]) -> str:
    """Produce a one-sentence 'you were working on…' label. Cascades phi-4-mini → hermes4."""
    if not apps and not highlights:
        return ""
    context_parts: list[str] = []
    if apps:
        context_parts.append(f"Apps open: {', '.join(apps[:6])}")
    if highlights:
        context_parts.append(f"Screen text sample: {highlights[0][:200]}")
    context = "\n".join(context_parts)
    prompt = (
        "In exactly one short sentence, describe what the user was working on based on "
        "the following screen activity. Start with 'You were'. Be specific but concise.\n\n"
        f"{context}\n\nSummary:"
    )
    try:
        import json as _json, urllib.request as _req
        try:
            from src.guppy.api.routes_backends import _LLAMACPP_CONFIG as _lcfg
        except Exception:
            _lcfg = {}
        _candidates = [
            (_lcfg.get("llamacpp-phi4-mini", {}).get("port", 8091), "phi-4-mini-instruct"),
            (_lcfg.get("llamacpp-hermes4", {}).get("port", 8086), "hermes-4-36b"),
        ]
        for _port, _model in _candidates:
            try:
                payload = _json.dumps({
                    "model": _model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 60,
                    "stream": False,
                }).encode()
                request = _req.Request(
                    f"http://127.0.0.1:{_port}/v1/chat/completions",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with _req.urlopen(request, timeout=15) as resp:
                    data = _json.loads(resp.read().decode())
                    choices = data.get("choices", [])
                    if choices:
                        content = choices[0].get("message", {}).get("content", "")
                        text = content.strip().split("\n")[0].strip()
                        if text:
                            return text
            except Exception:
                continue
    except Exception as exc:
        logger.debug("[screen_monitor] AI summary failed: %s", exc)
    return ""


# ── mss vision capture ────────────────────────────────────────────────────────

def _mss_capture_description() -> str:
    """Screenshot → MiniCPM vision. Only fires if port 8084 is already warm.

    Never cold-starts MiniCPM — the health check returns immediately if offline.
    """
    try:
        import urllib.request as _req
        _req.urlopen("http://127.0.0.1:8084/health", timeout=1).close()
    except Exception:
        return ""  # MiniCPM offline — skip

    try:
        import io, base64, json as _json, mss, mss.tools
        import urllib.request as _req2
        with mss.mss() as sct:
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            shot = sct.grab(monitor)
            png_bytes = mss.tools.to_png(shot.rgb, shot.size)

        # Downsample if PIL is available to keep payload under 1 MB
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(png_bytes))
            img.thumbnail((1280, 720))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=65)
            img_bytes = buf.getvalue()
            mime = "image/jpeg"
        except ImportError:
            img_bytes = png_bytes
            mime = "image/png"

        b64 = base64.b64encode(img_bytes).decode()
        payload = _json.dumps({
            "model": "minicpm-o",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    {"type": "text", "text": (
                        "Briefly describe what is visible on the screen. "
                        "Focus on which applications are open and what the user appears to be doing. "
                        "One short paragraph, no more than 60 words."
                    )},
                ],
            }],
            "max_tokens": 120,
            "stream": False,
        }).encode()
        req = _req2.Request(
            "http://127.0.0.1:8084/v1/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with _req2.urlopen(req, timeout=25) as resp:
            data = _json.loads(resp.read().decode())
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
    except Exception as exc:
        logger.debug("[screen_monitor] mss/vision failed: %s", exc)
    return ""


# ── Core snapshot function ────────────────────────────────────────────────────

def take_snapshot(minutes: int = 30) -> dict[str, Any] | None:
    """Capture the last `minutes` of screen activity and store a window record."""
    items = _call_screenpipe_recent(minutes=minutes, limit=200)

    # If only window titles are available (no OCR text), opportunistically enrich
    # with a MiniCPM screen description — but only if MiniCPM is already warm.
    _has_rich_text = any(len((i.get("text") or "").split()) > 20 for i in items)
    if not _has_rich_text:
        vision_desc = _mss_capture_description()
        if vision_desc:
            items.append({"app_name": "screen-vision", "window_name": "", "text": vision_desc})

    if not items:
        return None

    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=minutes)
    win_id = str(uuid.uuid4())

    apps       = _extract_app_names(items)
    highlights = _extract_highlights(items)
    words      = _word_count(items)

    # AI-generated activity summary (best-effort; no-op if Ollama down)
    summary = _generate_ai_summary(apps, highlights)

    record = {
        "id":           win_id,
        "window_start": start.isoformat(),
        "window_end":   now.isoformat(),
        "apps":         apps,
        "highlights":   highlights,
        "item_count":   len(items),
        "word_count":   words,
        "summary":      summary,
        "created_at":   now.isoformat(),
    }

    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO screen_windows "
            "(id, window_start, window_end, apps, highlights, item_count, word_count, summary, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                win_id,
                record["window_start"],
                record["window_end"],
                json.dumps(apps),
                json.dumps(highlights),
                len(items),
                words,
                summary,
                record["created_at"],
            ),
        )
        conn.commit()

    logger.info("[screen_monitor] snapshot: %d items, %d apps, %d words, summary=%r",
                len(items), len(apps), words, summary[:60] if summary else "")
    return record


def _list_windows(date_iso: str | None = None, limit: int = 48) -> list[dict[str, Any]]:
    with _conn() as conn:
        if date_iso:
            rows = conn.execute(
                "SELECT * FROM screen_windows WHERE window_start LIKE ? "
                "ORDER BY window_start DESC LIMIT ?",
                (f"{date_iso[:10]}%", limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM screen_windows ORDER BY window_start DESC LIMIT ?",
                (limit,),
            ).fetchall()
    result = []
    for r in rows:
        result.append({
            "id":           r["id"],
            "window_start": r["window_start"],
            "window_end":   r["window_end"],
            "apps":         json.loads(r["apps"] or "[]"),
            "highlights":   json.loads(r["highlights"] or "[]"),
            "item_count":   r["item_count"],
            "word_count":   r["word_count"],
            "summary":      r["summary"] if "summary" in r.keys() else "",
            "created_at":   r["created_at"],
        })
    return result


# ── Background job ────────────────────────────────────────────────────────────

_monitor_thread: threading.Thread | None = None
_monitor_stop   = threading.Event()
_INTERVAL_MIN   = 30  # run every 30 minutes


def _monitor_loop() -> None:
    logger.info("[screen_monitor] background job started (interval=%dm)", _INTERVAL_MIN)
    while not _monitor_stop.is_set():
        try:
            result = take_snapshot(_INTERVAL_MIN)
            if result:
                logger.info("[screen_monitor] auto-snapshot: %d items", result["item_count"])
        except Exception as exc:
            logger.warning("[screen_monitor] snapshot error: %s", exc)
        # sleep in 60s chunks so we can respond quickly to stop signal
        for _ in range(_INTERVAL_MIN):
            if _monitor_stop.is_set():
                break
            time.sleep(60)
    logger.info("[screen_monitor] background job stopped")


def start_monitor() -> None:
    global _monitor_thread
    if _monitor_thread and _monitor_thread.is_alive():
        return
    _monitor_stop.clear()
    _monitor_thread = threading.Thread(target=_monitor_loop, name="screen-monitor", daemon=True)
    _monitor_thread.start()


def stop_monitor() -> None:
    _monitor_stop.set()


# ── Router ────────────────────────────────────────────────────────────────────

def build_screen_monitor_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/screen", tags=["screen-monitor"])

    @router.get("/timeline")
    def list_timeline(
        date: str = "",
        limit: int = 48,
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        return _list_windows(date_iso=date or None, limit=min(limit, 200))

    @router.get("/timeline/today")
    def today_timeline(_uid: str = Depends(ctx.require_rate_limit)):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return _list_windows(date_iso=today, limit=48)

    @router.post("/timeline/snapshot")
    async def manual_snapshot(
        minutes: int = 30,
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        import asyncio
        result = await asyncio.to_thread(take_snapshot, min(minutes, 180))
        if not result:
            return {"ok": False, "message": "Screenpipe not available or no data"}
        return {"ok": True, **result}

    @router.get("/status")
    def monitor_status(_uid: str = Depends(ctx.require_rate_limit)):
        return {
            "running": bool(_monitor_thread and _monitor_thread.is_alive()),
            "interval_minutes": _INTERVAL_MIN,
        }

    return router
