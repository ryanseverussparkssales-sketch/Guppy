from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile, WebSocket, WebSocketDisconnect


async def _await_chat_idempotency_owner(owner: Any, request: Any) -> tuple[str, str, bool]:
    idempotency_key = str(getattr(request, "idempotency_key", "") or "").strip()
    if not idempotency_key:
        return "", "", False

    request_fingerprint = owner.build_chat_request_fingerprint(
        message=request.message,
        session_id=request.session_id,
        mode=request.mode,
        persona=request.persona,
        history=request.history,
    )
    while True:
        is_owner, idempotency_event = owner.register_chat_idempotency_key(
            idempotency_key,
            request_fingerprint,
        )
        if is_owner:
            return idempotency_key, request_fingerprint, True

        await owner._run_blocking(
            idempotency_event.wait,
            timeout_seconds=max(owner.CHAT_TIMEOUT_SECONDS, 120.0),
        )
        idempotent_result = owner.resolve_chat_idempotency_key(
            idempotency_key,
            request_fingerprint,
        )
        if isinstance(idempotent_result, dict):
            response_payload = idempotent_result.get("response")
            if isinstance(response_payload, dict):
                raise _SnapshotIdempotentResponse(response_payload)
            if "error" in idempotent_result:
                raise HTTPException(
                    status_code=int(idempotent_result.get("status", 500) or 500),
                    detail=idempotent_result.get("error"),
                    headers=idempotent_result.get("headers")
                    if isinstance(idempotent_result.get("headers"), dict)
                    else None,
                )
        is_owner, _event, took_ownership = owner.takeover_chat_idempotency_key(
            idempotency_key,
            request_fingerprint,
        )
        if is_owner and took_ownership:
            return idempotency_key, request_fingerprint, True


def _complete_chat_success(
    owner: Any,
    *,
    idempotency_key: str,
    idempotency_owner: bool,
    payload: dict[str, Any],
) -> None:
    if idempotency_owner and idempotency_key:
        owner.complete_chat_idempotency_key(
            idempotency_key,
            response=payload,
            status_code=200,
        )


def _complete_chat_http_error(
    owner: Any,
    *,
    idempotency_key: str,
    idempotency_owner: bool,
    exc: HTTPException,
) -> None:
    if idempotency_owner and idempotency_key:
        owner.complete_chat_idempotency_key(
            idempotency_key,
            error=getattr(exc, "detail", "chat request failed"),
            status_code=int(getattr(exc, "status_code", 500) or 500),
            headers=getattr(exc, "headers", None),
        )


def _complete_chat_error(
    owner: Any,
    *,
    idempotency_key: str,
    idempotency_owner: bool,
    error: str,
) -> None:
    if idempotency_owner and idempotency_key:
        owner.complete_chat_idempotency_key(
            idempotency_key,
            error=error,
            status_code=500,
        )


def _persist_message_pair(owner: Any, *, session_id: str | None, user_text: str, assistant_text: str) -> None:
    if not session_id or not getattr(owner, "GUPPY_MEMORY_AVAILABLE", False):
        return
    owner.memory.save_message(session_id, "user", user_text)
    owner.memory.save_message(session_id, "assistant", assistant_text)


def _system_prompt_for_chat(owner: Any, request: Any, active_instance_persona: str) -> str:
    return owner._build_chat_system_prompt(
        session_id=request.session_id,
        message=request.message,
        mode=request.mode,
        persona=request.persona or active_instance_persona,
        model_id=request.mode,
        history=request.history,
    )


def _maybe_get_cached_chat_response(
    owner: Any,
    *,
    request: Any,
    system_prompt: str,
    active_instance_name: str | None,
    active_instance_type: str | None,
) -> tuple[str | None, str | None]:
    if not getattr(owner, "INFERENCE_ROUTER_AVAILABLE", False) or not owner._request_is_cacheable(request):
        return None, None
    try:
        router_factory = getattr(owner, "get_router", None)
        router = router_factory() if callable(router_factory) else None
        task_type = router._classify_task(request.message, system_prompt) if router is not None else None
        if task_type != "simple":
            return None, None
        cache_key = owner.build_response_cache_key(
            message=request.message,
            system_prompt=system_prompt,
            mode=request.mode or "auto",
            instance_name=active_instance_name,
            instance_type=active_instance_type,
        )
        return cache_key, owner.get_cached_response(cache_key)
    except Exception as exc:
        owner.logger.debug("Response cache lookup skipped: %s", exc)
        return None, None


class _SnapshotIdempotentResponse(Exception):
    def __init__(self, payload: dict[str, Any]) -> None:
        super().__init__("idempotent response ready")
        self.payload = payload


async def chat_response(owner: Any, request: Any) -> dict[str, Any]:
    if not getattr(owner, "GUPPY_CORE_AVAILABLE", False):
        raise HTTPException(status_code=503, detail="Guppy core not available")

    try:
        idempotency_key, _request_fingerprint, idempotency_owner = await _await_chat_idempotency_owner(owner, request)
    except _SnapshotIdempotentResponse as response:
        return response.payload

    try:
        active_instance_name, active_instance_type, active_instance_persona, _active_instance_voice = (
            owner._get_active_instance_context()
        )
        if owner._request_is_morning_brief(request):
            response = owner._build_morning_brief_response()
            owner.log_session_event(
                "api",
                "morning_brief_served",
                level="info",
                session_id=request.session_id or "",
                instance_name=active_instance_name,
                used_saved_report=bool(owner._latest_daily_report_path()),
            )
            if request.session_id and getattr(owner, "GUPPY_MEMORY_AVAILABLE", False):
                for role, content in (("user", request.message), ("assistant", response)):
                    try:
                        owner.memory.save_message(request.session_id, role, content)
                    except Exception as exc:
                        owner.logger.error(
                            "morning brief memory.save_message failed session_id=%r role=%s error=%s",
                            request.session_id,
                            role,
                            exc,
                        )
            payload = {"response": response, "session_id": request.session_id, "brief": True}
            _complete_chat_success(
                owner,
                idempotency_key=idempotency_key,
                idempotency_owner=idempotency_owner,
                payload=payload,
            )
            return payload

        system_prompt = _system_prompt_for_chat(owner, request, str(active_instance_persona or ""))
        cache_key, cached_response = _maybe_get_cached_chat_response(
            owner,
            request=request,
            system_prompt=system_prompt,
            active_instance_name=active_instance_name,
            active_instance_type=active_instance_type,
        )
        if cached_response:
            payload = {
                "response": cached_response,
                "session_id": request.session_id,
                "cached": True,
            }
            _complete_chat_success(
                owner,
                idempotency_key=idempotency_key,
                idempotency_owner=idempotency_owner,
                payload=payload,
            )
            return payload

        response = await owner._run_blocking(
            owner._call_unified_inference,
            request.message,
            system_prompt,
            request.mode,
            request.history,
            instance_name=active_instance_name,
            instance_type=active_instance_type,
            timeout_seconds=owner.CHAT_TIMEOUT_SECONDS,
        )

        if cache_key and response.strip():
            try:
                owner.set_cached_response(cache_key, response)
            except Exception as exc:
                owner.logger.debug("Response cache store skipped: %s", exc)

        _persist_message_pair(
            owner,
            session_id=request.session_id,
            user_text=request.message,
            assistant_text=response,
        )
        payload = {"response": response, "session_id": request.session_id}
        _complete_chat_success(
            owner,
            idempotency_key=idempotency_key,
            idempotency_owner=idempotency_owner,
            payload=payload,
        )
        return payload
    except HTTPException as exc:
        _complete_chat_http_error(
            owner,
            idempotency_key=idempotency_key,
            idempotency_owner=idempotency_owner,
            exc=exc,
        )
        raise
    except Exception as exc:
        owner.logger.error("Chat request failed: %s", exc)
        owner.log_session_event(
            "api",
            "chat_failed",
            level="error",
            session_id=request.session_id or "",
            use_claude=bool(getattr(request, "use_claude", False)),
            error=str(exc),
        )
        _complete_chat_error(
            owner,
            idempotency_key=idempotency_key,
            idempotency_owner=idempotency_owner,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail=str(exc))


async def chat_voice_response(
    owner: Any,
    *,
    file: UploadFile,
    session_id: str | None,
    use_claude: bool | None,
) -> dict[str, Any]:
    if not getattr(owner, "GUPPY_CORE_AVAILABLE", False):
        raise HTTPException(status_code=503, detail="Guppy core not available")
    if not getattr(owner, "GUPPY_VOICE_AVAILABLE", False):
        raise HTTPException(status_code=503, detail="Voice processing not available")

    try:
        active_instance_name, active_instance_type, active_instance_persona, _active_instance_voice = (
            owner._get_active_instance_context()
        )
        temp_path = await owner._save_voice_upload_tempfile(file)
        try:
            voice_handler = await owner._run_blocking(
                owner.voice.GuppyVoice,
                timeout_seconds=owner.VOICE_TIMEOUT_SECONDS,
            )
            if hasattr(voice_handler, "transcribe_audio"):
                transcription = await owner._run_blocking(
                    voice_handler.transcribe_audio,
                    temp_path,
                    timeout_seconds=owner.VOICE_TIMEOUT_SECONDS,
                )
            elif hasattr(voice_handler, "whisper_model") and voice_handler.whisper_model:
                segments, _info = await owner._run_blocking(
                    voice_handler.whisper_model.transcribe,
                    temp_path,
                    timeout_seconds=owner.VOICE_TIMEOUT_SECONDS,
                )
                transcription = " ".join(seg.text for seg in segments).strip()
            else:
                raise HTTPException(status_code=503, detail="Voice transcription engine not available")

            if not transcription:
                raise HTTPException(status_code=400, detail="Could not transcribe audio")

            system_prompt = owner._build_chat_system_prompt(
                session_id=session_id,
                message=transcription,
                persona=active_instance_persona,
                model_id="",
            )
            response = await owner._run_blocking(
                owner._call_unified_inference,
                transcription,
                system_prompt,
                instance_name=active_instance_name,
                instance_type=active_instance_type,
                timeout_seconds=owner.CHAT_TIMEOUT_SECONDS,
            )
            _persist_message_pair(
                owner,
                session_id=session_id,
                user_text=f"[Voice] {transcription}",
                assistant_text=response,
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
    except Exception as exc:
        owner.logger.error("Voice chat request failed: %s", exc)
        owner.log_session_event(
            "api",
            "voice_chat_failed",
            level="error",
            session_id=session_id or "",
            use_claude=bool(use_claude),
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail=str(exc))


async def websocket_response(owner: Any, websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        auth_data = await websocket.receive_json()
        token = auth_data.get("token")
        if not token:
            await websocket.send_json({"error": "Authentication required"})
            await websocket.close()
            return

        try:
            payload = owner.jwt.decode(token, owner.SECRET_KEY, algorithms=[owner.ALGORITHM])
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
                if not message:
                    continue
                if not getattr(owner, "GUPPY_CORE_AVAILABLE", False):
                    await websocket.send_json({"error": "Guppy core not available"})
                    continue

                active_instance_name, active_instance_type, active_instance_persona, _active_instance_voice = (
                    owner._get_active_instance_context()
                )
                system_prompt = owner._build_chat_system_prompt(
                    session_id=session_id,
                    message=message,
                    mode=mode,
                    persona=data.get("persona") or active_instance_persona,
                    model_id=mode or "",
                )
                text = await owner._run_blocking(
                    owner._call_unified_inference,
                    message,
                    system_prompt,
                    instance_name=active_instance_name,
                    instance_type=active_instance_type,
                    timeout_seconds=owner.CHAT_TIMEOUT_SECONDS,
                )
                async for chunk in owner._stream_chunks(text):
                    await websocket.send_json({"chunk": chunk})
                await websocket.send_json({"done": True})
            except WebSocketDisconnect:
                break
            except Exception as exc:
                owner.logger.error("WebSocket error: %s", exc)
                owner.log_session_event("api", "ws_error", level="error", error=str(exc))
                await websocket.send_json({"error": str(exc)})
    except Exception as exc:
        owner.logger.error("WebSocket connection failed: %s", exc)
        owner.log_session_event("api", "ws_connection_failed", level="error", error=str(exc))
