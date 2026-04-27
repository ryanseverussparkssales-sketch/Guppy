from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from src.guppy.api._server_fragment_models import ChatRequest
from src.guppy.api.server_context import ServerContext
from src.guppy.api.realtime_inference_support import stream_unified_inference


def _get_active_local_model() -> Optional[str]:
    """Read the user-selected local model from the settings DB."""
    try:
        from src.guppy.api.routes_settings import _settings_db
        val = _settings_db.get_setting("local_active_model")
        return val.strip() if val and val.strip() else None
    except Exception:
        return None


def _get_active_cloud_model(provider: str = "anthropic") -> Optional[str]:
    """Read the user-selected cloud model from the settings DB."""
    try:
        from src.guppy.api.routes_settings import _settings_db
        val = _settings_db.get_setting(f"{provider}_active_model")
        return val.strip() if val and val.strip() else None
    except Exception:
        return None


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

            response = await ctx.run_blocking(
                ctx.call_unified_inference,
                request.message,
                system_prompt,
                request.mode,
                request.history,
                instance_name=active_instance_name,
                instance_type=active_instance_type,
                active_local_model=_get_active_local_model(),
                active_cloud_model=_get_active_cloud_model(),
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
            user_msg = str(e)
            if "ollama" in user_msg.lower() or "11434" in user_msg or "connect" in user_msg.lower():
                user_msg = f"Cannot reach local inference backend. Start Ollama and try again. ({e})"
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
        )

        _active_local_model = _get_active_local_model()
        _active_cloud_model = _get_active_cloud_model()

        async def _generate():
            full_response = ""
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
                ):
                    full_response += token
                    yield f"data: {json.dumps({'token': token})}\n\n"

                yield "data: [DONE]\n\n"

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

        return StreamingResponse(
            _generate(),
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
                voice_handler = await ctx.run_blocking(
                    owner.voice.GuppyVoice,
                    timeout_seconds=owner.VOICE_TIMEOUT_SECONDS,
                )
                if hasattr(voice_handler, "transcribe_audio"):
                    transcription = await ctx.run_blocking(
                        voice_handler.transcribe_audio,
                        temp_path,
                        timeout_seconds=owner.VOICE_TIMEOUT_SECONDS,
                    )
                elif hasattr(voice_handler, "whisper_model") and voice_handler.whisper_model:
                    segments, _info = await ctx.run_blocking(
                        voice_handler.whisper_model.transcribe,
                        temp_path,
                        timeout_seconds=owner.VOICE_TIMEOUT_SECONDS,
                    )
                    transcription = " ".join(seg.text for seg in segments).strip()
                else:
                    raise HTTPException(
                        status_code=503, detail="Voice transcription engine not available"
                    )

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

    @router.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()

        try:
            auth_data = await websocket.receive_json()
            token = auth_data.get("token")

            if not token:
                await websocket.send_json({"error": "Authentication required"})
                await websocket.close()
                return

            try:
                payload = owner.jwt.decode(
                    token, owner.SECRET_KEY, algorithms=[owner.ALGORITHM]
                )
                _ = payload.get("sub")
            except owner.JWTError:
                await websocket.send_json({"error": "Invalid token"})
                await websocket.close()
                return

            await websocket.send_json({"status": "authenticated"})

            while True:
                try:
                    data = await websocket.receive_json()
                    message = data.get("message")
                    session_id = data.get("session_id")
                    mode = data.get("mode")
                    use_claude = data.get("use_claude", True)

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
                    owner.logger.error(f"WebSocket error: {e}")
                    owner.log_session_event("api", "ws_error", level="error", error=str(e))
                    await websocket.send_json({"error": str(e)})
        except Exception as e:
            owner.logger.error(f"WebSocket connection failed: {e}")
            owner.log_session_event(
                "api", "ws_connection_failed", level="error", error=str(e)
            )

    return router
