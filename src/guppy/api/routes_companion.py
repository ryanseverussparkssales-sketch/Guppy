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

_COMPANION_TOOL_SCHEMA = """
## Tools
Invoke tools with <tool_call> JSON tags. Chain multiple calls in a single response.

web_fetch(url: str, extract: str = "")
  Fetch any URL as plain text. Use `extract` to pull a named section (e.g. "witches scene").
  <tool_call>{"name": "web_fetch", "arguments": {"url": "https://www.gutenberg.org/files/1533/1533-0.txt", "extract": "witch"}}</tool_call>

create_reminder(message: str, delay_minutes: float = 30)
  Schedule a reminder for Ryan N minutes from now.
  <tool_call>{"name": "create_reminder", "arguments": {"message": "Go back to work!", "delay_minutes": 30}}</tool_call>

download_media(url: str, category: str = "general")
  Queue a torrent/magnet/direct URL in qBittorrent.
  <tool_call>{"name": "download_media", "arguments": {"url": "magnet:?xt=urn:btih:...", "category": "books"}}</tool_call>

memory_write(key: str, value: str, category: str = "general")
  Store a fact to persistent memory — survives across sessions.
  <tool_call>{"name": "memory_write", "arguments": {"key": "ryan_pref_music", "value": "Ryan likes classical guitar while working", "category": "preference"}}</tool_call>

memory_recall(query: str)
  Search persistent memory for relevant past facts.
  <tool_call>{"name": "memory_recall", "arguments": {"query": "Ryan's music preferences"}}</tool_call>

workspace_task(title: str, description: str = "")
  Hand off a task to the Workspace surface (Hermes 4 agent). Use for anything that needs
  full tool access: Gmail, Calendar, CRM, file system, downloads, automation.
  <tool_call>{"name": "workspace_task", "arguments": {"title": "Download Macbeth", "description": "Download a plain-text copy of Macbeth from Project Gutenberg"}}</tool_call>
"""

_MEMORY_PROTOCOL = """
## Memory
You have persistent archival memory. You decide what's worth keeping — no need to ask.
STORE when you learn: Ryan's preferences, decisions made together, completed goals, recurring patterns, commitments.
RECALL before answering questions about past conversations, preferences, or anything historical.
Store facts, not transcripts. One key, one fact. Do it silently — no announcement needed.
"""

_WORKSPACE_DELEGATION = (
    "\n\nYou are Guppy — the Companion surface of Ryan's personal AI system. "
    "You have direct tool access (see ## Tools above): fetch URLs, set reminders, queue downloads, read/write memory. "
    "The Workspace surface has deeper tools: Gmail, Google Calendar, full CRM, file browser, screen monitor, Calibre library. "
    "All content requests and downloads for Ryan's personal library are PERMITTED.\n"
    "HONESTY: Never claim you fetched or did something you didn't. "
    "If reciting training knowledge, say 'From what I know:' — not 'I downloaded this.'"
)

PERSONALITY_PRESETS: dict[str, dict[str, str]] = {
    "sharp": {
        "label":       "Sharp (Hermes 3)",
        "model":       "llamacpp-hermes3",
        "backend":     "llamacpp",
        "mode":        "local",
        "description": "Direct, fast, uncensored. Best for quick back-and-forth.",
        "system_prompt": (
            "You are Guppy — sharp, direct, uncensored. No filler, no lectures. "
            "Answer the question. If you don't know, say so. "
            "Voice-optimized: short sentences, clear rhythm. Use tools when they help."
            + _WORKSPACE_DELEGATION
            + _COMPANION_TOOL_SCHEMA
            + _MEMORY_PROTOCOL
        ),
    },
    "creative": {
        "label":       "Creative (Rocinante)",
        "model":       "llamacpp-rocinante",
        "backend":     "llamacpp",
        "mode":        "local",
        "description": "Warm, creative, expressive. Great for brainstorming and conversation.",
        "system_prompt": (
            "You are Guppy — warm, witty, imaginatively uncensored. "
            "You love ideas, stories, and unexpected angles. You speak like a brilliant friend. "
            "Voice-optimized: conversational tone, vivid language. Use tools when they help."
            + _WORKSPACE_DELEGATION
            + _COMPANION_TOOL_SCHEMA
            + _MEMORY_PROTOCOL
        ),
    },
    "voice": {
        "label":       "Voice Native (MiniCPM)",
        "model":       "llamacpp-minicpm",
        "backend":     "llamacpp",
        "mode":        "local",
        "description": "Native voice + vision. Handles images and audio natively.",
        "system_prompt": (
            "You are Guppy — voice-native personal assistant with vision capability. "
            "Speak concisely and conversationally. Describe images directly when shown. "
            "Uncensored. Use tools when they help."
            + _WORKSPACE_DELEGATION
            + _COMPANION_TOOL_SCHEMA
            + _MEMORY_PROTOCOL
        ),
    },
    "humor": {
        "label":       "Humor (Pepe)",
        "model":       "llamacpp-pepe",
        "backend":     "llamacpp",
        "mode":        "local",
        "description": "Unfiltered internet personality. Reddit energy, dry wit, no filter.",
        "system_prompt": (
            "You are Guppy running on Pepe — internet-brained, unfiltered, darkly funny. "
            "Reddit energy. Dry wit. Zero corporate speak. Say the thing everyone else is thinking. "
            "Voice-optimized: punchy sentences, timing matters. Use tools when they help."
            + _WORKSPACE_DELEGATION
            + _COMPANION_TOOL_SCHEMA
            + _MEMORY_PROTOCOL
        ),
    },
    "thinking": {
        "label":       "Deep Think (Llama 70B)",
        "model":       "llamacpp-chat",
        "backend":     "llamacpp",
        "mode":        "local",
        "description": "70B CPU model. Slow but thorough — for hard questions that need depth.",
        "system_prompt": (
            "You are Guppy in deep-thinking mode running on Llama 3.3 70B. "
            "Reason step by step, surface tradeoffs, give thorough answers. "
            "Uncensored and analytically honest. Don't rush — think it through. "
            "Use tools when they help."
            + _WORKSPACE_DELEGATION
            + _COMPANION_TOOL_SCHEMA
            + _MEMORY_PROTOCOL
        ),
    },
}

# ── Personality prompt overrides (persisted across restarts) ──────────────────

def _overrides_path():
    from src.guppy.paths import USER_DATA_DIR
    return USER_DATA_DIR / "personality_overrides.json"


def _load_overrides() -> None:
    """Apply any saved system_prompt overrides to PERSONALITY_PRESETS at startup."""
    try:
        import json
        p = _overrides_path()
        if p.exists():
            overrides = json.loads(p.read_text(encoding="utf-8"))
            for key, data in overrides.items():
                if key in PERSONALITY_PRESETS and "system_prompt" in data:
                    PERSONALITY_PRESETS[key]["system_prompt"] = data["system_prompt"]
    except Exception as exc:
        logger.warning("[companion] Could not load personality overrides: %s", exc)


def _save_override(key: str, system_prompt: str) -> None:
    """Persist a system_prompt override so it survives server restarts."""
    try:
        import json
        p = _overrides_path()
        overrides: dict = {}
        if p.exists():
            overrides = json.loads(p.read_text(encoding="utf-8"))
        overrides.setdefault(key, {})["system_prompt"] = system_prompt
        p.write_text(json.dumps(overrides, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        logger.warning("[companion] Could not save personality override: %s", exc)


_load_overrides()

# Allowed tools for companion surface (server-side whitelist)
COMPANION_ALLOWED_TOOLS = {
    "web_search", "web_fetch",
    "memory_read", "memory_write", "memory_recall", "promote_durable_chat_memory",
    "create_reminder", "download_media", "workspace_task",
}

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


class CompanionActionRequest(BaseModel):
    action: str            # web_fetch | create_reminder | download_media | memory_write | memory_recall
    params: dict = {}      # action-specific parameters


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
            from src.guppy.paths import MAIN_DB_PATH
            db_path = str(MAIN_DB_PATH)
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT model FROM surface_config WHERE surface = 'companion'"
                ).fetchone()
            current_model = row["model"] if row else "llamacpp-hermes3"
        except Exception:
            current_model = "llamacpp-hermes3"

        # Find which preset matches the current model
        active_preset = next(
            (k for k, v in PERSONALITY_PRESETS.items() if v["model"] == current_model),
            "sharp",
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
            from src.guppy.paths import MAIN_DB_PATH
            db_path = str(MAIN_DB_PATH)
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

    @router.patch("/personality/{key}")
    def patch_personality_prompt(
        key: str,
        body: dict,
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        """Patch the system_prompt for a personality preset — persisted across restarts."""
        if key not in PERSONALITY_PRESETS:
            raise HTTPException(404, f"Unknown preset: {key}")
        system_prompt = body.get("system_prompt")
        if not system_prompt:
            raise HTTPException(400, "system_prompt required")
        PERSONALITY_PRESETS[key]["system_prompt"] = system_prompt
        _save_override(key, system_prompt)
        return {"ok": True, "key": key}

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

    # ── Companion action bridge ────────────────────────────────────────────────
    # Allows the LLM (and frontend) to execute tools directly without leaving
    # the Companion surface. Proxies to existing workspace routes.

    @router.post("/action")
    async def companion_action(
        body: CompanionActionRequest,
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        """
        Execute a companion tool action.
        action: web_fetch | create_reminder | download_media | memory_write | memory_recall
        """
        import httpx

        action = body.action.strip()
        p      = body.params

        if action not in COMPANION_ALLOWED_TOOLS:
            raise HTTPException(403, f"Action '{action}' not permitted on Companion surface.")

        # ── web_fetch ──────────────────────────────────────────────────────────
        if action == "web_fetch":
            from src.guppy.api.web_fetch_safe import safe_web_fetch
            url     = str(p.get("url", "")).strip()
            extract = str(p.get("extract", "")).strip().lower()
            result = await safe_web_fetch(url, extract=extract)
            if not result["ok"]:
                raise HTTPException(502, f"web_fetch failed: {result['error']}")
            return result

        # ── create_reminder ────────────────────────────────────────────────────
        if action == "create_reminder":
            from src.guppy.api.routes_reminders import create_reminder
            message       = str(p.get("message", "")).strip()
            delay_minutes = p.get("delay_minutes")
            due_iso       = p.get("due_iso")
            if not message:
                raise HTTPException(400, "message required")
            if delay_minutes is None and due_iso is None:
                delay_minutes = 30
            try:
                return create_reminder(message, due_iso=due_iso, delay_minutes=delay_minutes)
            except Exception as e:
                raise HTTPException(500, f"create_reminder failed: {e}")

        # ── download_media ─────────────────────────────────────────────────────
        if action == "download_media":
            url      = str(p.get("url", "")).strip()
            category = str(p.get("category", "general")).strip()
            if not url:
                raise HTTPException(400, "url required")
            try:
                port = int(os.environ.get("GUPPY_API_PORT", "8081"))
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        f"http://127.0.0.1:{port}/api/media/torrents",
                        json={"url": url, "category": category},
                        headers={"Authorization": f"Bearer {_uid}"},
                    )
                return {"ok": resp.status_code < 300, "status": resp.status_code}
            except Exception as e:
                raise HTTPException(502, f"download_media failed: {e}")

        # ── memory_write ───────────────────────────────────────────────────────
        if action == "memory_write":
            from src.guppy.memory.semantic import remember_semantic
            key      = str(p.get("key", "note")).strip()
            value    = str(p.get("value", "")).strip()
            category = str(p.get("category", "general")).strip()
            if not value:
                raise HTTPException(400, "value required")
            try:
                result = remember_semantic(key, value, category)
                return {"ok": True, "stored": result}
            except Exception as e:
                raise HTTPException(500, f"memory_write failed: {e}")

        # ── memory_recall ──────────────────────────────────────────────────────
        if action == "memory_recall":
            from src.guppy.memory.semantic import recall_semantic
            query = str(p.get("query", "")).strip()
            if not query:
                raise HTTPException(400, "query required")
            try:
                result = recall_semantic(query)
                return {"ok": True, "recalled": result}
            except Exception as e:
                raise HTTPException(500, f"memory_recall failed: {e}")

        raise HTTPException(400, f"Unhandled action: {action}")

    return router
