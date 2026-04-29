"""Companion surface — dedicated API endpoints.

POST /api/companion/vision              — image + text → minicpm vision model
POST /api/companion/voice/session       — start wake-word voice session
DELETE /api/companion/voice/session     — stop voice session
GET  /api/companion/personality         — current companion personality config
PUT  /api/companion/personality         — switch companion personality preset

Tool policy enforcement: companion surface only allows web_search + memory.
Requests from the companion surface that include disallowed tools return 403.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import threading
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from src.guppy.api.server_context import ServerContext

logger = logging.getLogger(__name__)

# ── Personality presets ────────────────────────────────────────────────────────

_WORKSPACE_DELEGATION = (
    "\n\nYou are the Companion surface of the Guppy AI system — a quick voice/chat surface. "
    "You have web_search available. "
    "The Workspace surface (accessible from the sidebar) has full tool access: "
    "Calibre ebook library, Project Gutenberg downloads (public-domain books), Open Library, "
    "LazyLibrarian/Prowlarr book acquisition, qBittorrent media downloads, "
    "Gmail, Google Calendar, CRM, task manager, file browser, and screen monitor. "
    "All downloads to Ryan's own library are PERMITTED — do not cite any policy against them. "
    "If the user asks for something requiring those tools, say: "
    "'Go to Workspace → Chat tab and ask there — it has [specific tool].' "
    "HONESTY RULE: Never claim you fetched or downloaded something you did not. "
    "If reciting from training data, say 'From what I know about this:' not 'I downloaded this from…'."
)

PERSONALITY_PRESETS: dict[str, dict[str, str]] = {
    "sharp": {
        "label":       "Sharp (Hermes 3)",
        "model":       "llamacpp-hermes3",
        "backend":     "llamacpp",
        "mode":        "local",
        "description": "Direct, fast, uncensored. Best for quick back-and-forth.",
        "system_prompt": (
            "You are Guppy — sharp, direct, and uncensored. No padding, no lectures. "
            "Answer the question in front of you. If you don't know, say so. "
            "Voice-optimized: short sentences, clear rhythm."
            + _WORKSPACE_DELEGATION
        ),
    },
    "creative": {
        "label":       "Creative (Rocinante)",
        "model":       "llamacpp-rocinante",
        "backend":     "llamacpp",
        "mode":        "local",
        "description": "Warm, creative, expressive. Great for brainstorming and conversation.",
        "system_prompt": (
            "You are Guppy — warm, witty, and imaginatively uncensored. "
            "You love ideas, stories, and interesting angles. You speak like a brilliant friend, "
            "not a corporate assistant. Voice-optimized: conversational tone, vivid language."
            + _WORKSPACE_DELEGATION
        ),
    },
    "voice": {
        "label":       "Voice Native (MiniCPM)",
        "model":       "llamacpp-minicpm",
        "backend":     "llamacpp",
        "mode":        "local",
        "description": "Native voice + vision. Handles images and audio natively.",
        "system_prompt": (
            "You are Guppy — a voice-native personal assistant with vision capability. "
            "You speak concisely, conversationally, and helpfully. "
            "When shown images, describe and analyze them directly. "
            "You are uncensored and speak to your user as an equal."
            + _WORKSPACE_DELEGATION
        ),
    },
    "thinking": {
        "label":       "Deep Thinking (Qwen3)",
        "model":       "llamacpp-qwen3",
        "backend":     "llamacpp",
        "mode":        "local",
        "description": "Slow, thorough reasoning. For hard questions that need depth.",
        "system_prompt": (
            "You are Guppy in deep-thinking mode. Reason step by step, surface tradeoffs, "
            "and give thorough answers. You are uncensored and analytically honest. "
            "Don't rush — think it through."
            + _WORKSPACE_DELEGATION
        ),
    },
}

# Allowed tools for companion surface (server-side whitelist)
COMPANION_ALLOWED_TOOLS = {"web_search", "memory_read", "memory_write", "memory_recall"}

# ── Voice session state ────────────────────────────────────────────────────────

_voice_session_active = False
_voice_session_thread: threading.Thread | None = None
_voice_session_stop   = threading.Event()


def _stop_voice_session() -> None:
    global _voice_session_active
    _voice_session_stop.set()
    _voice_session_active = False
    logger.info("[companion] Voice session stopped")


# ── Pydantic models ────────────────────────────────────────────────────────────

class PersonalitySwitch(BaseModel):
    preset: str  # one of PERSONALITY_PRESETS keys


class VisionRequest(BaseModel):
    text:         str
    image_base64: str | None = None
    image_url:    str | None = None


# ── Router ─────────────────────────────────────────────────────────────────────

def build_companion_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/companion", tags=["companion"])

    # ── Personality ────────────────────────────────────────────────────────────

    @router.get("/personality")
    def get_personality(_uid: str = Depends(ctx.require_rate_limit)):
        """Return all personality presets and which is currently active."""
        try:
            import sqlite3
            from src.guppy.paths import USER_DATA_DIR
            db_path = str(USER_DATA_DIR / "surface.db")
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT model FROM surface_config WHERE surface = 'companion'"
                ).fetchone()
            current_model = row["model"] if row else "llamacpp-rocinante"
        except Exception:
            current_model = "llamacpp-rocinante"

        # Find which preset matches the current model
        active_preset = next(
            (k for k, v in PERSONALITY_PRESETS.items() if v["model"] == current_model),
            "creative",
        )

        return {
            "active_preset": active_preset,
            "presets":       PERSONALITY_PRESETS,
        }

    @router.put("/personality")
    def switch_personality(body: PersonalitySwitch, _uid: str = Depends(ctx.require_rate_limit)):
        """Switch companion personality preset — updates surface_config."""
        if body.preset not in PERSONALITY_PRESETS:
            raise HTTPException(400, f"Unknown preset: {body.preset}. Choose from: {list(PERSONALITY_PRESETS)}")

        preset = PERSONALITY_PRESETS[body.preset]

        try:
            import sqlite3
            from datetime import datetime, timezone
            from src.guppy.paths import USER_DATA_DIR
            db_path = str(USER_DATA_DIR / "surface.db")
            now = datetime.now(timezone.utc).isoformat()
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    """UPDATE surface_config
                       SET model=?, backend=?, mode=?, system_prompt=?, updated_at=?
                       WHERE surface='companion'""",
                    (preset["model"], preset["backend"], preset["mode"], preset["system_prompt"], now),
                )
                conn.commit()
        except Exception as e:
            raise HTTPException(500, f"Failed to update personality: {e}")

        return {"ok": True, "active_preset": body.preset, "preset": preset}

    # ── Vision ─────────────────────────────────────────────────────────────────

    @router.post("/vision")
    async def vision_query(
        text:        str = Form(...),
        image:       UploadFile | None = File(None),
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        """
        Accept text + optional image, route to minicpm vision model via /api/chat.
        Returns a streaming SSE response so the frontend can display tokens progressively.
        """
        image_b64: str | None = None
        if image:
            data = await image.read()
            image_b64 = base64.b64encode(data).decode()

        # Build the chat payload for the realtime endpoint
        payload: dict[str, Any] = {
            "message": text,
            "mode":    "local",
            "model":   "llamacpp-minicpm",
            "surface": "companion",
        }
        if image_b64:
            payload["image_base64"] = image_b64

        # Forward to internal chat endpoint
        try:
            from src.guppy.api import services_realtime
            # Use the existing realtime inference directly
            result = await services_realtime.stream_chat_response(payload)
            return result
        except Exception as e:
            logger.warning(f"[companion] Vision via services_realtime failed: {e}")

        # Fallback: call /api/chat internally via httpx
        try:
            import httpx
            port = int(os.environ.get("GUPPY_API_PORT", "8081"))
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"http://127.0.0.1:{port}/api/chat",
                    json=payload,
                    headers={"Authorization": f"Bearer {_uid}"},
                )
                return JSONResponse(content={"response": resp.text})
        except Exception as e:
            raise HTTPException(500, f"Vision query failed: {e}")

    # ── Tool policy enforcement ────────────────────────────────────────────────

    @router.post("/tools/check")
    def check_tool_allowed(
        body: dict,
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        """
        Check whether a tool name is allowed on the companion surface.
        Called by the frontend before executing a tool call.
        Returns {"allowed": bool, "reason": str}.
        """
        tool_name = body.get("tool", "")
        allowed   = tool_name in COMPANION_ALLOWED_TOOLS
        return {
            "allowed": allowed,
            "tool":    tool_name,
            "reason":  "" if allowed else f"Tool '{tool_name}' is not available on the Companion surface. Use Workspace for full tool access.",
        }

    # ── Voice session ──────────────────────────────────────────────────────────

    @router.post("/voice/session")
    def start_voice_session(_uid: str = Depends(ctx.require_rate_limit)):
        """Start a persistent wake-word voice session for the companion surface."""
        global _voice_session_active, _voice_session_thread, _voice_session_stop

        if _voice_session_active:
            return {"ok": True, "status": "already_active"}

        try:
            from src.guppy.voice import voice as _voice
            _voice_session_stop.clear()
            _voice_session_active = True

            def _run_session():
                try:
                    _voice.start_wake_word_detection()
                except Exception as e:
                    logger.warning(f"[companion] Voice session error: {e}")
                finally:
                    global _voice_session_active
                    _voice_session_active = False

            _voice_session_thread = threading.Thread(target=_run_session, daemon=True)
            _voice_session_thread.start()
            return {"ok": True, "status": "started"}
        except Exception as e:
            _voice_session_active = False
            raise HTTPException(500, f"Could not start voice session: {e}")

    @router.delete("/voice/session")
    def stop_voice_session(_uid: str = Depends(ctx.require_rate_limit)):
        """Stop the wake-word voice session."""
        global _voice_session_active
        if not _voice_session_active:
            return {"ok": True, "status": "not_active"}
        try:
            from src.guppy.voice import voice as _voice
            _voice.stop_listening()
        except Exception:
            pass
        _stop_voice_session()
        return {"ok": True, "status": "stopped"}

    @router.get("/voice/session")
    def voice_session_status(_uid: str = Depends(ctx.require_rate_limit)):
        return {
            "active":   _voice_session_active,
            "status":   "active" if _voice_session_active else "idle",
        }

    return router
