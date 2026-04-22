@app.post("/chat/voice")
async def chat_voice(
    file: UploadFile = File(...),
    session_id: Optional[str] = None,
    use_claude: Optional[bool] = True,
    user_id: str = Depends(require_rate_limit)
):
    """Upload audio file and get transcription + response."""
    del user_id

    if not GUPPY_CORE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Guppy core not available")

    if not GUPPY_VOICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Voice processing not available")

    try:
        active_instance_name, active_instance_type, active_instance_persona, _active_instance_voice = _get_active_instance_context()
        temp_path = await _save_voice_upload_tempfile(file)

        try:
            # Transcribe audio
            voice_handler = await _run_blocking(
                voice.GuppyVoice,
                timeout_seconds=VOICE_TIMEOUT_SECONDS,
            )
            if hasattr(voice_handler, "transcribe_audio"):
                transcription = await _run_blocking(
                    voice_handler.transcribe_audio,
                    temp_path,
                    timeout_seconds=VOICE_TIMEOUT_SECONDS,
                )
            elif hasattr(voice_handler, "whisper_model") and voice_handler.whisper_model:
                segments, _info = await _run_blocking(
                    voice_handler.whisper_model.transcribe,
                    temp_path,
                    timeout_seconds=VOICE_TIMEOUT_SECONDS,
                )
                transcription = " ".join(seg.text for seg in segments).strip()
            else:
                raise HTTPException(status_code=503, detail="Voice transcription engine not available")

            if not transcription:
                raise HTTPException(status_code=400, detail="Could not transcribe audio")

            # Get response using transcribed text
            system_prompt = _build_chat_system_prompt(
                session_id=session_id,
                message=transcription,
                persona=active_instance_persona,
                model_id="",
            )

            # Route through priority chain: local (guppy) -> haiku -> sonnet
            response = await _run_blocking(
                _call_unified_inference,
                transcription,
                system_prompt,
                instance_name=active_instance_name,
                instance_type=active_instance_type,
                timeout_seconds=CHAT_TIMEOUT_SECONDS,
            )

            # Store in memory if session provided and memory is available
            if session_id and GUPPY_MEMORY_AVAILABLE:
                memory.save_message(
                    session_id,
                    "user",
                    f"[Voice] {transcription}",
                    workspace_name=str(active_instance_name or "").strip(),
                )
                memory.save_message(
                    session_id,
                    "assistant",
                    response,
                    workspace_name=str(active_instance_name or "").strip(),
                )

            return {
                "transcription": transcription,
                "response": response,
                "session_id": session_id
            }

        finally:
            # Clean up temp file
            Path(temp_path).unlink(missing_ok=True)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice chat request failed: {e}")
        log_session_event(
            "api",
            "voice_chat_failed",
            level="error",
            session_id=session_id or "",
            use_claude=bool(use_claude),
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for streaming responses."""
    await websocket.accept()

    try:
        # Receive initial auth message
        auth_data = await websocket.receive_json()
        token = auth_data.get("token")

        if not token:
            await websocket.send_json({"error": "Authentication required"})
            await websocket.close()
            return

        # Verify token
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            _ = payload.get("sub")  # validated but not used beyond auth check
        except JWTError:
            await websocket.send_json({"error": "Invalid token"})
            await websocket.close()
            return

        await websocket.send_json({"status": "authenticated"})

        # Handle streaming chat
        while True:
            try:
                data = await websocket.receive_json()
                message = data.get("message")
                session_id = data.get("session_id")
                mode = data.get("mode")
                use_claude = data.get("use_claude", True)

                if not message:
                    continue

                if not GUPPY_CORE_AVAILABLE:
                    await websocket.send_json({"error": "Guppy core not available"})
                    continue

                # Get system prompt
                active_instance_name, active_instance_type, active_instance_persona, _active_instance_voice = _get_active_instance_context()
                system_prompt = _build_chat_system_prompt(
                    session_id=session_id,
                    message=message,
                    mode=mode,
                    persona=data.get("persona") or active_instance_persona,
                    model_id=mode or "",
                )

                # Stream response â€” route through priority chain: local (guppy) -> haiku -> sonnet
                text = await _run_blocking(
                    _call_unified_inference,
                    message,
                    system_prompt,
                    instance_name=active_instance_name,
                    instance_type=active_instance_type,
                    timeout_seconds=CHAT_TIMEOUT_SECONDS,
                )
                async for chunk in _stream_chunks(text):
                    await websocket.send_json({"chunk": chunk})

                await websocket.send_json({"done": True})

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                log_session_event("api", "ws_error", level="error", error=str(e))
                await websocket.send_json({"error": str(e)})

    except Exception as e:
        logger.error(f"WebSocket connection failed: {e}")
        log_session_event("api", "ws_connection_failed", level="error", error=str(e))

# â”€â”€ Main â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

if __name__ == "__main__":
    api_reload = os.environ.get("GUPPY_API_RELOAD", "").strip().lower() in {"1", "true", "yes", "on"}
    if not api_reload:
        api_reload = DEV_MODE

        uvicorn.run(
            "src.guppy.api.server:app",
        host=HOST,
        port=PORT,
        reload=api_reload,
        log_level="info"
    )
