from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

_log = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from jose import JWTError, jwt
from src.guppy.api.auth import ALGORITHM, SECRET_KEY

from src.guppy.api._server_fragment_models import ChatRequest
from src.guppy.api.server_context import ServerContext
from src.guppy.api.realtime_inference_support import (
    stream_unified_inference,
    _REPLACE_SENTINEL,
    _SOURCE_SENTINEL,
    _repair_tool_json,
)
from src.guppy.api.tool_executor_companion import _execute_companion_tool
from src.guppy.api.tool_executor_workspace import (
    _execute_workspace_tool,
    _WORKSPACE_TOOL_SCHEMA,
    _SHELL_SAFE_PREFIXES,
)
from src.guppy.voice import voice as _voice

# ── Companion tool-call parser ─────────────────────────────────────────────────
# Hermes 3/4 emit tool calls as: <tool_call>{"name": "...", "arguments": {...}}</tool_call>
_TOOL_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)


async def _generate_conversation_title(user_message: str, conv_id: str) -> None:
    """Fire-and-forget: generate a short title for a new conversation.

    Uses the dispatch llamacpp server (Qwen2.5-3B-Instruct) via OpenAI-compatible API.
    Updates the DB on success, silently no-ops on any failure.
    """
    import httpx
    from src.guppy.api.routes_chat_history import _chat_history_db

    snippet = user_message.strip()[:120]
    payload = {
        "model": "qwen2.5-3b-instruct",
        "messages": [
            {
                "role": "user",
                "content": (
                    f"Write a chat title of 5 words or fewer for this message. "
                    f"Reply with ONLY the title, no punctuation, no quotes:\n{snippet}"
                ),
            }
        ],
        "stream": False,
        "temperature": 0.3,
        "max_tokens": 16,
    }
    try:
        try:
            from src.guppy.api.routes_backends import _LLAMACPP_CONFIG as _lcfg
            _port = _lcfg.get("llamacpp-dispatch", {}).get("port", 8085)
        except Exception:
            _port = 8085
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(f"http://127.0.0.1:{_port}/v1/chat/completions", json=payload)
            resp.raise_for_status()
            title = resp.json()["choices"][0]["message"]["content"].strip()
            title = title.strip('"\'').strip()
            if title:
                await asyncio.to_thread(_chat_history_db.update_conversation_title, conv_id, title)
    except Exception:
        pass  # title gen is best-effort — never surface errors to the user


def _get_active_local_model() -> Optional[str]:
    """Read the user-selected local model from the settings DB."""
    try:
        from src.guppy.api.routes_settings import _settings_db
        val = _settings_db.get_setting("local_active_model")
        return val.strip() if val and val.strip() else None
    except Exception:
        return None


def _get_active_cloud_model(provider: str = "") -> Optional[str]:
    """Read the user-selected cloud model for the active provider from the settings DB.

    When *provider* is empty, the function reads the active provider from settings
    first.  This ensures that when the user has selected Mistral, Cohere, etc. as
    their active provider, the correct model ID is returned for routing.
    """
    try:
        from src.guppy.api.routes_settings import _settings_db
        resolved = provider or _settings_db.get_active_provider() or "anthropic"
        val = _settings_db.get_setting(f"{resolved}_active_model")
        return val.strip() if val and val.strip() else None
    except Exception:
        return None


# ── Surface-aware model selection ──────────────────────────────────────────────
# Each surface has a dedicated always-on local model and a preferred cloud fallback.
# companion → Hermes 3 (fast, uncensored, 9GB VRAM, port 8087)
# workspace → Hermes 4 (tools, uncensored, 11GB VRAM, port 8086)
# codespace → Hermes 4 (code-capable, same stack)
# Cloud fallbacks are surface-appropriate: Haiku for companion (fast/cheap),
# Sonnet for workspace/codespace (capable).

_SURFACE_LOCAL_DEFAULTS: dict[str, str] = {
    "companion": "llamacpp-hermes3",
    "workspace": "llamacpp-hermes4",
    "codespace": "llamacpp-hermes4",
}

_SURFACE_CLOUD_DEFAULTS: dict[str, str] = {
    "companion": "claude-haiku-4-5-20251001",
    "workspace": "claude-sonnet-4-6",
    "codespace": "claude-sonnet-4-6",
}


def _get_surface_local_model(surface: Optional[str]) -> Optional[str]:
    """Return the local model configured for *surface*, with hardcoded per-surface defaults.

    Priority: surface_config DB value → per-surface hardcoded default → global setting.
    The DB value is written by BackendSelector when the user picks a model for a surface.
    """
    default = _SURFACE_LOCAL_DEFAULTS.get(surface or "")
    if not surface:
        return _get_active_local_model() or default
    try:
        import sqlite3
        from src.guppy.paths import MAIN_DB_PATH
        db_path = str(MAIN_DB_PATH)
        conn = sqlite3.connect(db_path, check_same_thread=False, timeout=3)
        row = conn.execute(
            "SELECT model FROM surface_config WHERE surface = ?", (surface,)
        ).fetchone()
        conn.close()
        if row:
            model = str(row[0] or "").strip()
            if model and model not in ("auto", ""):
                return model
    except Exception:
        pass
    return default


def _get_surface_cloud_model(surface: Optional[str]) -> Optional[str]:
    """Return the cloud fallback model for *surface*.

    User's explicit provider selection wins if set; otherwise use the surface default.
    companion → claude-haiku-4-5-20251001 (fast, cheap)
    workspace/codespace → claude-sonnet-4-6 (capable)
    """
    user_model = _get_active_cloud_model()
    return user_model or _SURFACE_CLOUD_DEFAULTS.get(surface or "", "claude-sonnet-4-6")


def build_realtime_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter()
    owner = ctx.owner

    def _persist_chat_memory(
        *,
        session_id: str | None,
        user_text: str,
        assistant_text: str,
        persona_id: str = "",
        workspace_name: str = "",
    ) -> None:
        if not session_id or not owner.GUPPY_MEMORY_AVAILABLE:
            return
        try:
            owner.memory.save_message(
                session_id,
                "user",
                user_text,
                workspace_name=workspace_name,
            )
            owner.memory.save_message(
                session_id,
                "assistant",
                assistant_text,
                workspace_name=workspace_name,
            )
            if hasattr(owner.memory, "promote_durable_chat_memory"):
                owner.memory.promote_durable_chat_memory(
                    user_text,
                    assistant_text,
                    session_id=session_id,
                    persona_id=persona_id,
                )
        except Exception as exc:
            owner.logger.error(
                "chat memory persistence failed session_id=%r persona_id=%r error=%s",
                session_id,
                persona_id,
                exc,
            )

    @router.post("/chat")
    async def chat(request: ChatRequest, _user_id: str = Depends(ctx.require_rate_limit)):

        if not owner.GUPPY_CORE_AVAILABLE:
            raise HTTPException(status_code=503, detail="Guppy core not available")

        idempotency_key = str(request.idempotency_key or "").strip()
        request_fingerprint = ctx.build_chat_request_fingerprint(request) if idempotency_key else ""
        idempotency_owner = False
        if idempotency_key:
            while True:
                idempotency_owner, idempotency_event = ctx.register_chat_idempotency_key(
                    idempotency_key, request_fingerprint
                )
                if idempotency_owner:
                    break
                await ctx.run_blocking(
                    idempotency_event.wait,
                    timeout_seconds=max(owner.CHAT_TIMEOUT_SECONDS, 120.0),
                )
                idempotent_result = ctx.resolve_chat_idempotency_key(
                    idempotency_key, request_fingerprint
                )
                if isinstance(idempotent_result, dict):
                    response_payload = idempotent_result.get("response")
                    if isinstance(response_payload, dict):
                        return response_payload
                    if "error" in idempotent_result:
                        raise HTTPException(
                            status_code=int(idempotent_result.get("status", 500) or 500),
                            detail=idempotent_result.get("error"),
                            headers=idempotent_result.get("headers")
                            if isinstance(idempotent_result.get("headers"), dict)
                            else None,
                        )
                (
                    idempotency_owner,
                    idempotency_event,
                    took_ownership,
                ) = ctx.takeover_chat_idempotency_key(idempotency_key, request_fingerprint)
                if idempotency_owner and took_ownership:
                    break

        try:
            (
                active_instance_name,
                active_instance_type,
                active_instance_persona,
                _active_instance_voice,
            ) = ctx.get_active_instance_context()
            if ctx.request_is_morning_brief(request):
                response = ctx.build_morning_brief_response()
                owner.log_session_event(
                    "api",
                    "morning_brief_served",
                    level="info",
                    session_id=request.session_id or "",
                    instance_name=active_instance_name,
                    used_saved_report=bool(ctx.latest_daily_report_path()),
                )
                if request.session_id and owner.GUPPY_MEMORY_AVAILABLE:
                    for role, content in (("user", request.message), ("assistant", response)):
                        try:
                            owner.memory.save_message(
                                request.session_id,
                                role,
                                content,
                                workspace_name=str(active_instance_name or "").strip(),
                            )
                        except Exception as exc:
                            owner.logger.error(
                                "morning brief memory.save_message failed session_id=%r role=%s error=%s",
                                request.session_id,
                                role,
                                exc,
                            )
                payload = {"response": response, "session_id": request.session_id, "brief": True}
                if idempotency_owner and idempotency_key:
                    ctx.complete_chat_idempotency_key(
                        idempotency_key, response=payload, status_code=200
                    )
                return payload

            system_prompt = ctx.build_chat_system_prompt(
                session_id=request.session_id,
                message=request.message,
                mode=request.mode,
                persona=request.persona or active_instance_persona,
                model_id=request.mode,
                history=request.history,
                surface=request.surface,
            )

            cache_key = None
            if owner.INFERENCE_ROUTER_AVAILABLE and ctx.request_is_cacheable(request):
                try:
                    router_impl = owner.get_router()
                    task_type = router_impl._classify_task(request.message, system_prompt)
                    if task_type == "simple":
                        cache_key = owner.build_response_cache_key(
                            message=request.message,
                            system_prompt=system_prompt,
                            mode=request.mode or "auto",
                            instance_name=active_instance_name,
                            instance_type=active_instance_type,
                        )
                        cached_response = owner.get_cached_response(cache_key)
                        if cached_response:
                            payload = {
                                "response": cached_response,
                                "session_id": request.session_id,
                                "cached": True,
                            }
                            if idempotency_owner and idempotency_key:
                                ctx.complete_chat_idempotency_key(
                                    idempotency_key, response=payload, status_code=200
                                )
                            return payload
                except Exception as e:
                    owner.logger.debug("Response cache lookup skipped: %s", e)

            _active_local = _get_surface_local_model(request.surface)
            # Voice fast-path: companion voice always uses Hermes3 (fastest always-on)
            if request.is_voice and request.surface == "companion":
                _active_local = "llamacpp-hermes3"

            response = await ctx.run_blocking(
                ctx.call_unified_inference,
                request.message,
                system_prompt,
                request.mode,
                request.history,
                instance_name=active_instance_name,
                instance_type=active_instance_type,
                active_local_model=_active_local,
                active_cloud_model=_get_surface_cloud_model(request.surface),
                timeout_seconds=owner.CHAT_TIMEOUT_SECONDS,
            )

            if cache_key and response.strip():
                try:
                    owner.set_cached_response(cache_key, response)
                except Exception as e:
                    owner.logger.debug("Response cache store skipped: %s", e)

            _persist_chat_memory(
                session_id=request.session_id,
                user_text=request.message,
                assistant_text=response,
                persona_id=str(request.persona or active_instance_persona or "").strip(),
                workspace_name=str(active_instance_name or "").strip(),
            )

            payload = {"response": response, "session_id": request.session_id}
            if idempotency_owner and idempotency_key:
                ctx.complete_chat_idempotency_key(
                    idempotency_key, response=payload, status_code=200
                )
            return payload

        except HTTPException as exc:
            if idempotency_owner and idempotency_key:
                ctx.complete_chat_idempotency_key(
                    idempotency_key,
                    error=getattr(exc, "detail", "chat request failed"),
                    status_code=int(getattr(exc, "status_code", 500) or 500),
                    headers=getattr(exc, "headers", None),
                )
            raise
        except Exception as e:
            owner.logger.error(f"Chat request failed: {e}")
            owner.log_session_event(
                "api",
                "chat_failed",
                level="error",
                session_id=request.session_id or "",
                use_claude=bool(request.use_claude),
                error=str(e),
            )
            if idempotency_owner and idempotency_key:
                ctx.complete_chat_idempotency_key(
                    idempotency_key, error=str(e), status_code=500
                )
            _raw = str(e)
            if "llamacpp" in _raw.lower() or "connect" in _raw.lower() or any(
                p in _raw for p in ("8085", "8086", "8087", "8088", "8089", "8090", "8091")
            ):
                user_msg = "Cannot reach local inference backend. Ensure llamacpp model servers are running."
            else:
                user_msg = "Inference request failed. Please try again."
            logger.error("[chat] inference error: %s", e)
            raise HTTPException(status_code=500, detail=user_msg)

    @router.post("/chat/stream")
    async def chat_stream(
        request: ChatRequest,
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        """
        SSE streaming chat endpoint. Yields tokens as they are produced by the
        inference backend.  Each event is ``data: {"token": "..."}\\n\\n``.
        The stream ends with ``data: [DONE]\\n\\n``.
        On error: ``data: {"error": "..."}\\n\\n``.
        """

        (
            active_instance_name,
            active_instance_type,
            active_instance_persona,
            _active_instance_voice,
        ) = ctx.get_active_instance_context()
        system_prompt = ctx.build_chat_system_prompt(
            session_id=request.session_id,
            message=request.message,
            mode=request.mode,
            persona=request.persona or active_instance_persona,
            model_id=request.mode,
            history=request.history,
            surface=request.surface,
        )

        _active_local_model = _get_surface_local_model(request.surface)
        _active_cloud_model = _get_surface_cloud_model(request.surface)

        # Voice fast-path: companion voice always uses Hermes3 (fastest always-on)
        if request.is_voice and request.surface == "companion":
            _active_local_model = "llamacpp-hermes3"

        # ── Local-model check — prefer local, fall back to cloud transparently ──
        # If the companion's local model port is down, announce it in-stream and
        # route to the cloud fallback rather than hard-failing. This keeps the
        # conversation alive. The watchdog will restart the local model in <60 s.
        _local_offline_notice: str | None = None
        if request.surface == "companion" and _active_local_model:
            try:
                from src.guppy.api.routes_backends import _LLAMACPP_CONFIG, _port_alive
                from src.guppy.inference.local_client import _LLAMACPP_MODEL_ROUTE as _ROUTE_MAP
                _canonical = _ROUTE_MAP.get(_active_local_model, _active_local_model)
                _cfg_entry = _LLAMACPP_CONFIG.get(_canonical, {})
                _model_port = _cfg_entry.get("port")
                if _model_port and not _port_alive(_model_port):
                    _model_label = _cfg_entry.get("label", _active_local_model)
                    _local_offline_notice = (
                        f"[Local model offline — routing to cloud. "
                        f"{_model_label} will restart automatically.] "
                    )
                    _active_local_model = None  # force cloud path
            except Exception:
                pass

        # Inject workspace tool schema so Hermes4 knows what tools it has
        if request.surface == "workspace" and _WORKSPACE_TOOL_SCHEMA not in system_prompt:
            system_prompt = system_prompt + _WORKSPACE_TOOL_SCHEMA

        async def _generate():
            full_response = ""
            last_source: str = ""

            # Emit offline notice as first token so TTS picks it up immediately
            if _local_offline_notice:
                yield f"data: {json.dumps({'token': _local_offline_notice})}\n\n"
                full_response += _local_offline_notice

            # ── Workspace surface: two-pass with full tool-call execution ─────
            if request.surface == "workspace":
                first_response = ""
                try:
                    async for token in stream_unified_inference(
                        owner,
                        request.message,
                        system_prompt,
                        mode=request.mode,
                        history=request.history,
                        instance_name=active_instance_name,
                        instance_type=active_instance_type,
                        active_local_model=_active_local_model,
                        active_cloud_model=_active_cloud_model,
                        image_base64=request.image_base64 or None,
                        skip_tools=True,
                        surface=request.surface or "workspace",
                    ):
                        if token.startswith(_SOURCE_SENTINEL) or token.startswith(_REPLACE_SENTINEL):
                            continue
                        first_response += token
                except asyncio.CancelledError:
                    _log.info("Client disconnected mid-stream — cancelling workspace pass-1 inference")
                    return
                except Exception as exc:
                    owner.logger.error("Workspace pass-1 buffering failed: %s", exc)
                    yield f"data: {json.dumps({'error': str(exc)})}\n\n"
                    return

                if not first_response.strip():
                    first_response = "Ready — what do you need?"

                tool_blocks = _TOOL_CALL_RE.findall(first_response)

                if not tool_blocks:
                    full_response = first_response
                    yield f"data: {json.dumps({'replace': first_response})}\n\n"
                else:
                    tool_results: list[dict] = []
                    for tc_json in tool_blocks:
                        try:
                            tc = _repair_tool_json(tc_json)
                            if tc is None:
                                tool_results.append({"tool": "?", "error": "malformed tool JSON"})
                                continue
                            tool_name = tc.get("name", "")
                            tool_args = tc.get("arguments", {})
                            yield f"data: {json.dumps({'tool_exec': tool_name})}\n\n"
                            result = await _execute_workspace_tool(tool_name, tool_args)
                            from src.guppy.api.tool_call_log import log_tool_call
                            log_tool_call(
                                surface=request.surface or "workspace",
                                tool_name=tool_name,
                                tool_args=tool_args,
                                result=result,
                                session_id=request.session_id,
                            )
                            tool_results.append({"tool": tool_name, "result": result})
                        except Exception as exc:
                            tool_results.append({"tool": "?", "error": str(exc)})

                    tool_result_text = "\n\n".join(
                        f"[{r['tool']} result]\n{json.dumps(r.get('result', r.get('error', '')), ensure_ascii=False)[:6000]}"
                        for r in tool_results
                    )
                    follow_up_history = list(request.history or []) + [
                        {"role": "assistant", "content": first_response},
                        {
                            "role": "user",
                            "content": (
                                f"Tool execution complete:\n\n{tool_result_text}\n\n"
                                "Give a clear response based on these results. "
                                "Continue with more tool calls if the task needs them."
                            ),
                        },
                    ]

                    try:
                        async for token in stream_unified_inference(
                            owner,
                            "Respond based on the tool results.",
                            system_prompt,
                            mode=request.mode,
                            history=follow_up_history,
                            instance_name=active_instance_name,
                            instance_type=active_instance_type,
                            active_local_model=_active_local_model,
                            active_cloud_model=_active_cloud_model,
                            image_base64=None,
                            surface=request.surface or "workspace",
                        ):
                            if token.startswith(_SOURCE_SENTINEL):
                                last_source = token[len(_SOURCE_SENTINEL):]
                                continue
                            if token.startswith(_REPLACE_SENTINEL):
                                replaced = token[len(_REPLACE_SENTINEL):]
                                full_response = replaced
                                yield f"data: {json.dumps({'replace': replaced})}\n\n"
                                continue
                            full_response += token
                            yield f"data: {json.dumps({'token': token})}\n\n"
                    except asyncio.CancelledError:
                        _log.info("Client disconnected mid-stream — cancelling workspace pass-2 inference")
                        return
                    except Exception as exc:
                        owner.logger.error("Workspace pass-2 streaming failed: %s", exc)
                        yield f"data: {json.dumps({'error': str(exc)})}\n\n"
                        return

                done_payload: dict = {}
                if last_source:
                    done_payload["source"] = last_source
                yield f"data: {json.dumps({**done_payload, 'done': True})}\n\n" if done_payload else "data: [DONE]\n\n"

                _persist_chat_memory(
                    session_id=request.session_id,
                    user_text=request.message,
                    assistant_text=full_response,
                    persona_id=str(request.persona or active_instance_persona or "").strip(),
                    workspace_name=str(active_instance_name or "").strip(),
                )
                if request.session_id and full_response:
                    try:
                        from src.guppy.api.routes_chat_history import _chat_history_db
                        conv = _chat_history_db.get_conversation(request.session_id)
                        if conv and conv.get("message_count", 0) <= 2 and str(conv.get("title", "")).startswith("Conversation "):
                            asyncio.create_task(_generate_conversation_title(request.message, request.session_id))
                    except Exception:
                        pass
                return

            # ── Companion surface: two-pass with tool-call detection ───────────
            if request.surface == "companion":
                # Pass 1: buffer streaming tokens to detect <tool_call> blocks.
                # MUST use stream_unified_inference, not call_unified_inference:
                # the non-streaming path runs through _parse_openai which strips
                # <tool_call> blocks before they reach our regex. Streaming yields
                # raw tokens so the markup is preserved for detection.
                first_response = ""
                try:
                    async for token in stream_unified_inference(
                        owner,
                        request.message,
                        system_prompt,
                        mode=request.mode,
                        history=request.history,
                        instance_name=active_instance_name,
                        instance_type=active_instance_type,
                        active_local_model=_active_local_model,
                        active_cloud_model=_active_cloud_model,
                        image_base64=request.image_base64 or None,
                        skip_tools=True,
                        surface=request.surface or "companion",
                    ):
                        if token.startswith(_SOURCE_SENTINEL) or token.startswith(_REPLACE_SENTINEL):
                            continue
                        first_response += token
                except asyncio.CancelledError:
                    _log.info("Client disconnected mid-stream — cancelling companion pass-1 inference")
                    return
                except Exception as exc:
                    owner.logger.error("Companion pass-1 buffering failed: %s", exc)
                    yield f"data: {json.dumps({'error': str(exc)})}\n\n"
                    return

                # If the model generated nothing, substitute a polite fallback so the
                # frontend never receives an empty replace (which shows confusing UI).
                if not first_response.strip():
                    first_response = "I'm here — could you rephrase that?"

                tool_blocks = _TOOL_CALL_RE.findall(first_response)

                if not tool_blocks:
                    # No tool calls — deliver response via replace (instant display)
                    full_response = first_response
                    yield f"data: {json.dumps({'replace': first_response})}\n\n"
                else:
                    # Execute each tool in sequence, emitting tool_exec status events
                    tool_results: list[dict] = []
                    for tc_json in tool_blocks:
                        try:
                            tc = _repair_tool_json(tc_json)
                            if tc is None:
                                tool_results.append({"tool": "?", "error": "malformed tool JSON"})
                                continue
                            tool_name = tc.get("name", "")
                            tool_args = tc.get("arguments", {})
                            yield f"data: {json.dumps({'tool_exec': tool_name})}\n\n"
                            result = await _execute_companion_tool(tool_name, tool_args)
                            from src.guppy.api.tool_call_log import log_tool_call
                            log_tool_call(
                                surface=request.surface or "companion",
                                tool_name=tool_name,
                                tool_args=tool_args,
                                result=result,
                                session_id=request.session_id,
                            )
                            tool_results.append({"tool": tool_name, "result": result})
                        except Exception as exc:
                            tool_results.append({"tool": "?", "error": str(exc)})

                    # Build tool-result injection for pass 2
                    tool_result_text = "\n\n".join(
                        f"[{r['tool']} result]\n{json.dumps(r.get('result', r.get('error', '')), ensure_ascii=False)[:4000]}"
                        for r in tool_results
                    )
                    follow_up_history = list(request.history or []) + [
                        {"role": "assistant", "content": first_response},
                        {
                            "role": "user",
                            "content": (
                                f"Tool execution complete:\n\n{tool_result_text}\n\n"
                                "Give the user a natural, conversational response based on these results. "
                                "No more <tool_call> blocks."
                            ),
                        },
                    ]

                    # Pass 2: stream the follow-up response
                    try:
                        async for token in stream_unified_inference(
                            owner,
                            "Respond naturally based on the tool results.",
                            system_prompt,
                            mode=request.mode,
                            history=follow_up_history,
                            instance_name=active_instance_name,
                            instance_type=active_instance_type,
                            active_local_model=_active_local_model,
                            active_cloud_model=_active_cloud_model,
                            image_base64=None,
                            surface=request.surface or "companion",
                        ):
                            if token.startswith(_SOURCE_SENTINEL):
                                last_source = token[len(_SOURCE_SENTINEL):]
                                continue
                            if token.startswith(_REPLACE_SENTINEL):
                                replaced = token[len(_REPLACE_SENTINEL):]
                                full_response = replaced
                                yield f"data: {json.dumps({'replace': replaced})}\n\n"
                                continue
                            full_response += token
                            yield f"data: {json.dumps({'token': token})}\n\n"
                    except asyncio.CancelledError:
                        _log.info("Client disconnected mid-stream — cancelling companion pass-2 inference")
                        return
                    except Exception as exc:
                        owner.logger.error("Companion pass-2 streaming failed: %s", exc)
                        yield f"data: {json.dumps({'error': str(exc)})}\n\n"
                        return

                done_payload: dict = {}
                if last_source:
                    done_payload["source"] = last_source
                yield f"data: {json.dumps({**done_payload, 'done': True})}\n\n" if done_payload else "data: [DONE]\n\n"

                _persist_chat_memory(
                    session_id=request.session_id,
                    user_text=request.message,
                    assistant_text=full_response,
                    persona_id=str(request.persona or active_instance_persona or "").strip(),
                    workspace_name=str(active_instance_name or "").strip(),
                )
                if request.session_id and full_response:
                    try:
                        from src.guppy.api.routes_chat_history import _chat_history_db
                        conv = _chat_history_db.get_conversation(request.session_id)
                        if conv and conv.get("message_count", 0) <= 2 and str(conv.get("title", "")).startswith("Conversation "):
                            asyncio.create_task(_generate_conversation_title(request.message, request.session_id))
                    except Exception:
                        pass
                return

            # ── Standard streaming for all other surfaces ─────────────────────
            try:
                async for token in stream_unified_inference(
                    owner,
                    request.message,
                    system_prompt,
                    mode=request.mode,
                    history=request.history,
                    instance_name=active_instance_name,
                    instance_type=active_instance_type,
                    active_local_model=_active_local_model,
                    active_cloud_model=_active_cloud_model,
                    image_base64=request.image_base64 or None,
                    surface=request.surface or "",
                ):
                    if token.startswith(_SOURCE_SENTINEL):
                        last_source = token[len(_SOURCE_SENTINEL):]
                        continue
                    if token.startswith(_REPLACE_SENTINEL):
                        replaced = token[len(_REPLACE_SENTINEL):]
                        full_response = replaced
                        yield f"data: {json.dumps({'replace': replaced})}\n\n"
                        continue
                    full_response += token
                    yield f"data: {json.dumps({'token': token})}\n\n"

                done_payload: dict = {}
                if last_source:
                    done_payload["source"] = last_source
                yield f"data: {json.dumps({**done_payload, 'done': True})}\n\n" if done_payload else "data: [DONE]\n\n"

            except asyncio.CancelledError:
                _log.info("Client disconnected mid-stream — cancelling standard inference")
                return
            except Exception as exc:
                owner.logger.error("Streaming chat error: %s", exc)
                yield f"data: {json.dumps({'error': str(exc)})}\n\n"
                return

            _persist_chat_memory(
                session_id=request.session_id,
                user_text=request.message,
                assistant_text=full_response,
                persona_id=str(request.persona or active_instance_persona or "").strip(),
                workspace_name=str(active_instance_name or "").strip(),
            )

            # Auto-title: fire-and-forget on the first assistant turn only.
            if request.session_id and full_response:
                try:
                    from src.guppy.api.routes_chat_history import _chat_history_db
                    conv = _chat_history_db.get_conversation(request.session_id)
                    if conv and conv.get("message_count", 0) <= 2 and str(conv.get("title", "")).startswith("Conversation "):
                        asyncio.create_task(
                            _generate_conversation_title(request.message, request.session_id)
                        )
                except Exception:
                    pass  # best-effort, never block the response

        async def _generate_with_heartbeat():
            """Wrap _generate() with SSE comment keepalives every 15 s.
            Prevents proxy / browser from killing idle slow-model connections.

            Enforces a maximum wall-clock cap (GUPPY_STREAM_TIMEOUT_SECONDS, default 300 s)
            and detects client disconnects so the async generator is cleaned up promptly.
            """
            import asyncio as _aio
            import os as _os
            _max_secs = float(_os.environ.get("GUPPY_STREAM_TIMEOUT_SECONDS", "300"))
            gen = _generate()
            start_time = _aio.get_event_loop().time()
            while True:
                # Disconnect detection — clean up and stop early if client has gone away.
                try:
                    if await request.is_disconnected():
                        owner.logger.debug("Client disconnected — cleaning up stream generator")
                        await gen.aclose()
                        return
                except Exception:
                    pass

                # Wall-clock timeout guard.
                elapsed = _aio.get_event_loop().time() - start_time
                if elapsed > _max_secs:
                    owner.logger.warning("Stream timeout after %.0f s — terminating", elapsed)
                    await gen.aclose()
                    yield f"data: {json.dumps({'error': 'Stream timeout'})}\n\n"
                    return

                try:
                    chunk = await _aio.wait_for(gen.__anext__(), timeout=15.0)
                    yield chunk
                except StopAsyncIteration:
                    break
                except _aio.TimeoutError:
                    yield ": heartbeat\n\n"  # SSE comment — ignored by client, keeps TCP alive

        return StreamingResponse(
            _generate_with_heartbeat(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    @router.post("/chat/voice")
    async def chat_voice(
        file: UploadFile = File(...),
        session_id: Optional[str] = None,
        use_claude: Optional[bool] = True,
        _user_id: str = Depends(ctx.require_rate_limit),
    ):

        if not owner.GUPPY_CORE_AVAILABLE:
            raise HTTPException(status_code=503, detail="Guppy core not available")

        if not owner.GUPPY_VOICE_AVAILABLE:
            raise HTTPException(status_code=503, detail="Voice processing not available")

        try:
            (
                active_instance_name,
                active_instance_type,
                active_instance_persona,
                _active_instance_voice,
            ) = ctx.get_active_instance_context()
            temp_path = await ctx.save_voice_upload_tempfile(file)

            try:
                # Transcribe via Stack C facade
                audio_bytes = Path(temp_path).read_bytes()
                stt_result = await _voice.transcribe(audio_bytes)
                if stt_result.error:
                    raise HTTPException(status_code=503, detail=stt_result.error or "STT failed")
                transcription = stt_result.text

                if not transcription:
                    raise HTTPException(status_code=400, detail="Could not transcribe audio")

                system_prompt = ctx.build_chat_system_prompt(
                    session_id=session_id,
                    message=transcription,
                    persona=active_instance_persona,
                    model_id="",
                )

                response = await ctx.run_blocking(
                    ctx.call_unified_inference,
                    transcription,
                    system_prompt,
                    instance_name=active_instance_name,
                    instance_type=active_instance_type,
                    active_local_model=_get_active_local_model(),
                    active_cloud_model=_get_active_cloud_model(),
                    timeout_seconds=owner.CHAT_TIMEOUT_SECONDS,
                )

                _persist_chat_memory(
                    session_id=session_id,
                    user_text=f"[Voice] {transcription}",
                    assistant_text=response,
                    persona_id=str(active_instance_persona or "").strip(),
                    workspace_name=str(active_instance_name or "").strip(),
                )

                return {
                    "transcription": transcription,
                    "response": response,
                    "session_id": session_id,
                }
            finally:
                Path(temp_path).unlink(missing_ok=True)
        except HTTPException:
            raise
        except Exception as e:
            owner.logger.error(f"Voice chat request failed: {e}")
            owner.log_session_event(
                "api",
                "voice_chat_failed",
                level="error",
                session_id=session_id or "",
                use_claude=bool(use_claude),
                error=str(e),
            )
            raise HTTPException(status_code=500, detail=str(e))

    def _ws_validate_token(token: str) -> bool:
        """Return True if the JWT is valid. Uses the same key/algo as HTTP auth."""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return bool(payload.get("sub"))
        except JWTError:
            return False

    @router.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        # Phase 1 — Auth.
        # If an Authorization header is present we can validate before accept()
        # and reject with no race window.  Browser clients that can't set custom
        # WS headers send the token in their first JSON message instead.
        auth_header = websocket.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            if not _ws_validate_token(auth_header[7:]):
                await websocket.close(code=4001)
                return
            await websocket.accept()
        else:
            await websocket.accept()
            try:
                auth_data = await websocket.receive_json()
            except WebSocketDisconnect:
                return
            token = auth_data.get("token") if isinstance(auth_data, dict) else None
            if not token or not _ws_validate_token(token):
                msg = "Authentication required" if not token else "Invalid token"
                await websocket.send_json({"error": msg})
                await websocket.close(code=4001)
                return

        await websocket.send_json({"status": "authenticated"})

        # Phase 2 — Message loop (both auth paths converge here).
        try:
            while True:
                try:
                    data = await websocket.receive_json()
                    message = data.get("message")
                    session_id = data.get("session_id")
                    mode = data.get("mode")

                    if not message:
                        continue

                    if not owner.GUPPY_CORE_AVAILABLE:
                        await websocket.send_json({"error": "Guppy core not available"})
                        continue

                    (
                        active_instance_name,
                        active_instance_type,
                        active_instance_persona,
                        _active_instance_voice,
                    ) = ctx.get_active_instance_context()
                    system_prompt = ctx.build_chat_system_prompt(
                        session_id=session_id,
                        message=message,
                        mode=mode,
                        persona=data.get("persona") or active_instance_persona,
                        model_id=mode or "",
                    )

                    text = await ctx.run_blocking(
                        ctx.call_unified_inference,
                        message,
                        system_prompt,
                        instance_name=active_instance_name,
                        instance_type=active_instance_type,
                        active_local_model=_get_active_local_model(),
                        active_cloud_model=_get_active_cloud_model(),
                        timeout_seconds=owner.CHAT_TIMEOUT_SECONDS,
                    )
                    async for chunk in ctx.stream_chunks(text):
                        await websocket.send_json({"chunk": chunk})

                    await websocket.send_json({"done": True})
                    _persist_chat_memory(
                        session_id=session_id,
                        user_text=message,
                        assistant_text=text,
                        persona_id=str(data.get("persona") or active_instance_persona or "").strip(),
                        workspace_name=str(active_instance_name or "").strip(),
                    )

                except WebSocketDisconnect:
                    break
                except Exception as e:
                    owner.logger.error("WebSocket message error: %s", e)
                    ctx.log_session_event("api", "ws_error", level="error", error=str(e))
                    await websocket.send_json({"error": str(e)})
        except Exception as e:
            owner.logger.error("WebSocket connection failed: %s", e)
            ctx.log_session_event("api", "ws_connection_failed", level="error", error=str(e))

    return router
