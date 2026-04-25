"""Desktop vision and control API.

GET  /api/desktop/info         — screen resolution + cursor position
POST /api/desktop/screenshot   — full or region capture → base64 JPEG
POST /api/desktop/click        — mouse click at (x, y)
POST /api/desktop/move         — move mouse to (x, y)
POST /api/desktop/type         — type text via keyboard
POST /api/desktop/shortcut     — send key combination (e.g. "ctrl+c")
POST /api/desktop/scroll       — scroll wheel at position
POST /api/desktop/drag         — click-drag from one point to another
POST /api/desktop/read-screen  — vision OCR on screen region via LLM
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import time
import urllib.request
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from src.guppy.api.server_context import ServerContext

# ── pyautogui availability ────────────────────────────────────────────────────
try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05
    _PYA = True
except ImportError:
    _PYA = False


def _require_pya() -> None:
    if not _PYA:
        raise HTTPException(status_code=503, detail="pyautogui not installed (pip install pyautogui)")


# ── Screenshot helpers ────────────────────────────────────────────────────────

def _capture_region(region: str | None) -> "pyautogui.PIL.Image.Image":
    """Capture the screen or a named region, returns a PIL Image."""
    if not region or region == "full":
        return pyautogui.screenshot()

    sw, sh = pyautogui.size()
    region_map: dict[str, tuple[int, int, int, int]] = {
        "top":    (0, 0, sw, sh // 2),
        "bottom": (0, sh // 2, sw, sh // 2),
        "left":   (0, 0, sw // 2, sh),
        "right":  (sw // 2, 0, sw // 2, sh),
    }
    if region in region_map:
        return pyautogui.screenshot(region=region_map[region])

    if region == "active_window":
        try:
            import ctypes
            import ctypes.wintypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            rect = ctypes.wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
            x, y = rect.left, rect.top
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            if w > 0 and h > 0:
                return pyautogui.screenshot(region=(x, y, w, h))
        except Exception:
            pass

    return pyautogui.screenshot()


def _image_to_b64(img: Any, quality: int = 85) -> str:
    """Encode PIL Image as base64 JPEG string."""
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return base64.standard_b64encode(buf.getvalue()).decode()


# ── Vision / OCR helper ───────────────────────────────────────────────────────

def _run_vision(img_b64: str, instruction: str) -> str:
    """Send image to local vision model or Claude fallback."""
    local_model = os.environ.get("GUPPY_VISION_MODEL", "guppy-vision")
    ollama_base = os.environ.get("GUPPY_OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")

    payload = json.dumps({
        "model": local_model,
        "messages": [{"role": "user", "content": instruction, "images": [img_b64]}],
        "stream": False,
        "options": {"num_predict": 2048},
    }).encode()
    try:
        req = urllib.request.Request(
            f"{ollama_base}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        text = (data.get("message", {}).get("content") or "").strip()
        if text:
            return text
    except Exception:
        pass

    # Claude fallback
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return "Vision unavailable: local model unreachable and no ANTHROPIC_API_KEY set."
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        backup = os.environ.get("ANTHROPIC_BACKUP_MODEL", "claude-haiku-4-5-20251001")
        resp = client.messages.create(
            model=backup,
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
                    {"type": "text", "text": instruction},
                ],
            }],
        )
        return resp.content[0].text if resp.content else "No response."
    except Exception as e:
        return f"Vision error: {e}"


# ── Sync worker functions (run in thread) ─────────────────────────────────────

def _sync_screenshot(region: str | None, quality: int) -> dict[str, Any]:
    _require_pya()
    img = _capture_region(region)
    b64 = _image_to_b64(img, quality)
    return {
        "image": b64,
        "mime_type": "image/jpeg",
        "width": img.size[0],
        "height": img.size[1],
        "region": region or "full",
        "timestamp": time.time(),
    }


def _sync_info() -> dict[str, Any]:
    _require_pya()
    sz = pyautogui.size()
    pos = pyautogui.position()
    return {"width": sz.width, "height": sz.height, "cursor_x": pos.x, "cursor_y": pos.y}


def _sync_click(x: int, y: int, button: str, clicks: int, interval: float) -> str:
    _require_pya()
    pyautogui.click(x, y, button=button, clicks=clicks, interval=interval)
    return f"Clicked ({x}, {y}) with {button} button x{clicks}"


def _sync_move(x: int, y: int, duration: float) -> str:
    _require_pya()
    pyautogui.moveTo(x, y, duration=duration)
    return f"Moved to ({x}, {y})"


def _sync_type(text: str, interval: float) -> str:
    _require_pya()
    pyautogui.write(text, interval=interval)
    return f"Typed {len(text)} characters"


def _sync_shortcut(keys: str) -> str:
    _require_pya()
    parts = [k.strip() for k in keys.lower().split("+")]
    pyautogui.hotkey(*parts)
    return f"Pressed: {keys}"


def _sync_scroll(x: int, y: int, clicks: int) -> str:
    _require_pya()
    pyautogui.scroll(clicks, x=x, y=y)
    direction = "up" if clicks > 0 else "down"
    return f"Scrolled {direction} {abs(clicks)} clicks at ({x}, {y})"


def _sync_drag(x1: int, y1: int, x2: int, y2: int, duration: float, button: str) -> str:
    _require_pya()
    pyautogui.moveTo(x1, y1, duration=0.1)
    pyautogui.dragTo(x2, y2, duration=duration, button=button)
    return f"Dragged ({x1},{y1}) → ({x2},{y2})"


def _sync_read_screen(region: str | None, instruction: str, quality: int) -> str:
    _require_pya()
    img = _capture_region(region)
    b64 = _image_to_b64(img, quality)
    return _run_vision(b64, instruction)


# ── Router factory ────────────────────────────────────────────────────────────

def build_desktop_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/desktop")

    @router.get("/info")
    async def get_screen_info(_user: str = Depends(ctx.require_rate_limit)) -> Dict[str, Any]:
        """Return screen resolution and current cursor position."""
        return await asyncio.to_thread(_sync_info)

    @router.post("/screenshot")
    async def take_screenshot(
        payload: Dict[str, Any] = {},
        _user: str = Depends(ctx.require_rate_limit),
    ) -> Dict[str, Any]:
        """Capture screen (or named region) and return base64 JPEG.

        Body params (all optional):
          region  : "full" | "top" | "bottom" | "left" | "right" | "active_window"
          quality : JPEG quality 1-95 (default 82)
        """
        region  = payload.get("region") or None
        quality = int(payload.get("quality", 82))
        quality = max(1, min(95, quality))
        return await asyncio.to_thread(_sync_screenshot, region, quality)

    @router.post("/click")
    async def mouse_click(
        payload: Dict[str, Any],
        _user: str = Depends(ctx.require_rate_limit),
    ) -> Dict[str, str]:
        """Click at (x, y).

        Body: { x, y, button="left"|"right"|"middle", clicks=1, interval=0.1 }
        """
        x = int(payload.get("x", 0))
        y = int(payload.get("y", 0))
        button   = str(payload.get("button", "left"))
        clicks   = int(payload.get("clicks", 1))
        interval = float(payload.get("interval", 0.1))
        msg = await asyncio.to_thread(_sync_click, x, y, button, clicks, interval)
        return {"result": msg}

    @router.post("/move")
    async def mouse_move(
        payload: Dict[str, Any],
        _user: str = Depends(ctx.require_rate_limit),
    ) -> Dict[str, str]:
        """Move mouse to (x, y).

        Body: { x, y, duration=0.25 }
        """
        x        = int(payload.get("x", 0))
        y        = int(payload.get("y", 0))
        duration = float(payload.get("duration", 0.25))
        msg = await asyncio.to_thread(_sync_move, x, y, duration)
        return {"result": msg}

    @router.post("/type")
    async def keyboard_type(
        payload: Dict[str, Any],
        _user: str = Depends(ctx.require_rate_limit),
    ) -> Dict[str, str]:
        """Type text via keyboard.

        Body: { text, interval=0.03 }
        """
        text     = str(payload.get("text", ""))[:2000]
        interval = float(payload.get("interval", 0.03))
        if not text:
            raise HTTPException(status_code=400, detail="text required")
        msg = await asyncio.to_thread(_sync_type, text, interval)
        return {"result": msg}

    @router.post("/shortcut")
    async def keyboard_shortcut(
        payload: Dict[str, Any],
        _user: str = Depends(ctx.require_rate_limit),
    ) -> Dict[str, str]:
        """Send a key combination.

        Body: { keys: "ctrl+c" | "win+d" | "alt+tab" | etc. }
        """
        keys = str(payload.get("keys", "")).strip()
        if not keys:
            raise HTTPException(status_code=400, detail="keys required (e.g. 'ctrl+c')")
        msg = await asyncio.to_thread(_sync_shortcut, keys)
        return {"result": msg}

    @router.post("/scroll")
    async def mouse_scroll(
        payload: Dict[str, Any],
        _user: str = Depends(ctx.require_rate_limit),
    ) -> Dict[str, str]:
        """Scroll at (x, y).

        Body: { x=0, y=0, clicks=3 }  positive = up, negative = down
        """
        x      = int(payload.get("x", 0))
        y      = int(payload.get("y", 0))
        clicks = int(payload.get("clicks", 3))
        msg = await asyncio.to_thread(_sync_scroll, x, y, clicks)
        return {"result": msg}

    @router.post("/drag")
    async def mouse_drag(
        payload: Dict[str, Any],
        _user: str = Depends(ctx.require_rate_limit),
    ) -> Dict[str, str]:
        """Click-drag from one point to another.

        Body: { x1, y1, x2, y2, duration=0.5, button="left" }
        """
        x1       = int(payload.get("x1", 0))
        y1       = int(payload.get("y1", 0))
        x2       = int(payload.get("x2", 0))
        y2       = int(payload.get("y2", 0))
        duration = float(payload.get("duration", 0.5))
        button   = str(payload.get("button", "left"))
        msg = await asyncio.to_thread(_sync_drag, x1, y1, x2, y2, duration, button)
        return {"result": msg}

    @router.post("/read-screen")
    async def read_screen(
        payload: Dict[str, Any],
        _user: str = Depends(ctx.require_rate_limit),
    ) -> Dict[str, str]:
        """Capture screen region and run vision inference on it.

        Body:
          instruction : what to extract/answer (default: "Describe what you see")
          region      : "full" | "top" | "bottom" | "left" | "right" | "active_window"
          quality     : JPEG quality 1-95 (default 82)
        """
        instruction = str(payload.get("instruction", "Describe what you see on the screen."))[:1000]
        region      = payload.get("region") or None
        quality     = int(payload.get("quality", 82))
        quality     = max(1, min(95, quality))
        result = await asyncio.to_thread(_sync_read_screen, region, instruction, quality)
        return {"result": result}

    return router
