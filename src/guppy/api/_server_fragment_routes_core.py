@app.get("/instances/{name}/logs")
async def get_instance_logs(
    name: str,
    limit: int = 50,
    user_id: str = Depends(require_rate_limit),
):
    del user_id
    target = (name or "").strip()
    raw_config = _load_instances_config()
    config, _warnings = _normalize_instances_config(raw_config)
    if target not in _instance_names(config):
        raise HTTPException(status_code=404, detail=f"unknown instance: {target}")
    return {
        "instance": target,
        "entries": read_instance_log_tail(target, limit=limit) if _INSTANCE_LOGGER_AVAILABLE else [],
        "summary": read_instance_log_summary(target) if _INSTANCE_LOGGER_AVAILABLE else {"entry_count": 0, "roles": {}, "statuses": {}},
    }


@app.post("/instances/{name}/query")
async def query_instance(
    name: str,
    request: InstanceQueryRequest,
    user_id: str = Depends(require_rate_limit),
):
    """Contract-first M2 endpoint: bounded synchronous inter-instance query.

    M2.0 semantics:
    - single in-flight cross-instance query globally
    - returns status=busy if another query is running
    - returns status=timeout for bounded timeout exhaustion
    """
    del user_id
    target = (name or "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="instance name is required")
    if not GUPPY_CORE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Guppy core not available")

    config, state, _config_warnings, _state_warnings = _load_normalized_instance_bundle(persist_repairs=True)
    names = _instance_names(config)
    if target not in names:
        raise HTTPException(status_code=404, detail=f"unknown instance: {target}")
    target_entry = _get_instance_entry(config, target) or {}
    target_type = str(target_entry.get("type", "user_instance") or "user_instance").strip() or "user_instance"
    source_instance = (request.source_instance or "launcher").strip() or "launcher"
    if source_instance != "launcher":
        if source_instance not in names:
            raise HTTPException(status_code=404, detail=f"unknown source instance: {source_instance}")
        source_entry = _get_instance_entry(config, source_instance) or {}
        source_type = str(source_entry.get("type", "user_instance") or "user_instance").strip() or "user_instance"
        allowed, reason, _permissions = check_instance_tool_permission(
            "query_instance",
            instance_name=source_instance,
            instance_type=source_type,
            endpoint=f"instance://{target}",
            metadata={"target_instance": target},
        )
        if not allowed:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"workspace {source_instance} cannot use cross-workspace query right now: "
                    f"{reason or 'query permission denied'}"
                ),
            )

    if not _instance_query_lock.acquire(blocking=False):
        return {
            "status": "busy",
            "source_instance": source_instance,
            "target_instance": target,
            "response": "",
            "tokens_used": 0,
            "model": "",
            "duration_ms": 0,
        }

    started = time.perf_counter()
    try:
        timeout_s = max(0.5, min(float(request.timeout_s or 5.0), 5.0))
        query_text = (request.message or "").strip()
        if not query_text:
            raise HTTPException(status_code=400, detail="message is required")

        mode = "auto"
        for item in config.get("instances", []):
            if isinstance(item, dict) and str(item.get("name", "")).strip() == target:
                mode = str(item.get("mode", "auto") or "auto").strip().lower()
                break

        system_prompt = _build_chat_system_prompt(
            session_id=f"instance-{target}",
            message=query_text,
            mode=mode,
            persona=str(target_entry.get("persona", "guppy") or "guppy").strip() or "guppy",
            model_id="",
        )
        try:
            response = await _run_blocking(
                _call_unified_inference,
                query_text,
                system_prompt,
                mode,
                None,
                instance_name=target,
                instance_type=target_type,
                timeout_seconds=timeout_s,
            )
            status = "ok"
        except HTTPException as e:
            if e.status_code == 504:
                response = ""
                status = "timeout"
            else:
                raise

        duration_ms = int((time.perf_counter() - started) * 1000)

        instances = state.setdefault("instances", {}) if isinstance(state, dict) else {}
        if isinstance(instances, dict):
            inst = instances.setdefault(target, {})
            if isinstance(inst, dict):
                inst["status"] = "busy" if status == "busy" else "running"
                inst["last_message"] = query_text[:200]
                inst["last_updated"] = datetime.now(timezone.utc).isoformat()
                inst["message_count"] = int(inst.get("message_count", 0) or 0) + 1
                inst["model_currently_using"] = mode
            _save_instance_state(state)

        if _INSTANCE_LOGGER_AVAILABLE:
            append_instance_log(
                target,
                {
                    "role": "user",
                    "source_instance": source_instance,
                    "message": query_text,
                    "status": status,
                    "model": mode,
                },
            )
            if response:
                append_instance_log(
                    target,
                    {
                        "role": "assistant",
                        "source_instance": target,
                        "message": response,
                        "status": status,
                        "model": mode,
                        "duration_ms": duration_ms,
                    },
                )

        return {
            "status": status,
            "source_instance": source_instance,
            "target_instance": target,
            "response": response,
            "tokens_used": max(1, len(response) // 4) if response else 0,
            "model": mode,
            "duration_ms": duration_ms,
        }
    finally:
        _instance_query_lock.release()


@app.get("/logs/recent")
async def get_recent_logs(
    limit: int = 100,
    user_id: str = Depends(require_rate_limit),
):
    """Return recent structured events for fast review during active sessions."""
    del user_id
    lim = max(1, min(int(limit), 300))
    runtime_dir = _runtime_dir
    return {
        "session_events": tail_session_events(limit=lim),
        "agent_performance": _read_jsonl_tail(runtime_dir / "agent_performance.jsonl", limit=lim),
        "integration_events": _read_jsonl_tail(runtime_dir / "integration_events.jsonl", limit=lim),
    }


@app.get("/telemetry/query")
async def telemetry_query(
    stream: Optional[str] = None,
    event: Optional[str] = None,
    level: Optional[str] = None,
    since_minutes: int = 1440,
    limit: int = 200,
    backend: str = "auto",
    user_id: str = Depends(require_rate_limit),
):
    """Query operational telemetry with filters (SQLite-first with JSONL fallback)."""
    del user_id
    lim = max(1, min(int(limit), 1000))
    since = max(0, int(since_minutes))
    stream_key = (stream or "").strip() or None
    event_key = (event or "").strip() or None
    level_key = (level or "").strip().lower() or None
    backend_key = (backend or "auto").strip().lower()
    if backend_key not in {"auto", "sqlite", "jsonl"}:
        raise HTTPException(status_code=400, detail="backend must be one of: auto, sqlite, jsonl")

    events: list[dict[str, Any]] = []
    source = backend_key
    if backend_key in {"auto", "sqlite"}:
        events = _query_sqlite_telemetry(stream_key, event_key, level_key, since, lim)
        source = "sqlite"

    if backend_key == "jsonl" or (backend_key == "auto" and not events):
        events = _query_jsonl_telemetry(stream_key, event_key, level_key, since, lim)
        source = "jsonl"

    return {
        "source": source,
        "count": len(events),
        "filters": {
            "stream": stream_key,
            "event": event_key,
            "level": level_key,
            "since_minutes": since,
            "limit": lim,
        },
        "events": events,
    }


@app.get("/telemetry/report")
async def telemetry_report(
    stream: Optional[str] = None,
    since_minutes: int = 1440,
    limit: int = 1000,
    backend: str = "auto",
    user_id: str = Depends(require_rate_limit),
):
    """Return summarized telemetry report for dashboards and ops checks."""
    del user_id
    lim = max(1, min(int(limit), 2000))
    since = max(0, int(since_minutes))
    stream_key = (stream or "").strip() or None
    backend_key = (backend or "auto").strip().lower()
    if backend_key not in {"auto", "sqlite", "jsonl"}:
        raise HTTPException(status_code=400, detail="backend must be one of: auto, sqlite, jsonl")

    events: list[dict[str, Any]] = []
    source = backend_key
    if backend_key in {"auto", "sqlite"}:
        events = _query_sqlite_telemetry(stream_key, None, None, since, lim)
        source = "sqlite"

    if backend_key == "jsonl" or (backend_key == "auto" and not events):
        events = _query_jsonl_telemetry(stream_key, None, None, since, lim)
        source = "jsonl"

    report = _build_telemetry_report(events)
    return {
        "source": source,
        "window": {
            "stream": stream_key,
            "since_minutes": since,
            "limit": lim,
        },
        "report": report,
    }


def _require_repair_token(request: Request) -> None:
    """Dependency: verify X-Repair-Token matches the in-memory token set at startup."""
    provided = (request.headers.get("X-Repair-Token") or "").strip()

    if not _REPAIR_TOKEN:
        log_session_event(
            "api",
            "repair_token_rejected",
            level="warning",
            reason_code="repair_token_uninitialized",
            has_header=bool(provided),
        )
        raise HTTPException(
            status_code=403,
            detail={"code": "repair_token_uninitialized", "message": "Invalid repair token"},
        )

    if not provided:
        log_session_event(
            "api",
            "repair_token_rejected",
            level="warning",
            reason_code="repair_token_missing",
            has_header=False,
        )
        raise HTTPException(
            status_code=403,
            detail={"code": "repair_token_missing", "message": "Invalid repair token"},
        )

    if not secrets.compare_digest(_REPAIR_TOKEN, provided):
        log_session_event(
            "api",
            "repair_token_rejected",
            level="warning",
            reason_code="repair_token_mismatch",
            has_header=True,
        )
        raise HTTPException(
            status_code=403,
            detail={"code": "repair_token_mismatch", "message": "Invalid repair token"},
        )


@app.get("/repair-token/refresh")
async def repair_token_refresh(_req: Request):
    """
    Re-read the current repair token from the OS credential store (or fallback file)
    and return it to a local caller.

    Security: localhost-only. Only 127.0.0.1 may call this endpoint.
    Purpose: allows the launcher to recover after an API restart rotates the token
    in cases where the OS keyring read in the launcher fails or races.
    The endpoint itself carries no auth requirement because it is the auth source.
    """
    client_ip = _req.client.host if _req.client else ""
    if client_ip not in ("127.0.0.1", "::1", "localhost", ""):
        log_session_event(
            "api", "repair_token_refresh_rejected",
            level="warning", client_ip=client_ip,
        )
        raise HTTPException(status_code=403, detail="localhost only")

    # Prefer the active in-memory token first. Keyring/file can lag behind restarts.
    token = _REPAIR_TOKEN or ""
    if _SECRET_STORE_AVAILABLE and _secret_store is not None:
        try:
            token = token or (_secret_store.get_secret("repair_token") or "")
        except Exception:
            pass
    if not token and _REPAIR_TOKEN_FILE.exists():
        try:
            token = _REPAIR_TOKEN_FILE.read_text(encoding="utf-8").strip()
        except Exception:
            pass

    log_session_event(
        "api", "repair_token_refresh",
        level="info", client_ip=client_ip, has_token=bool(token),
    )
    return {"repair_token": token}


@app.post("/repair")
async def repair_runtime(
    request: RepairRequest,
    _req: Request,
    user_id: str = Depends(require_rate_limit),
    _tok: None = Depends(_require_repair_token),
):
    """Guarded internal repair entrypoint for launcher/operator flows."""
    del user_id
    action = (request.action or "").strip().lower()
    dry_run = bool(request.dry_run)
    result = await asyncio.to_thread(_do_repair_action, action, dry_run)
    log_session_event(
        "api",
        "repair_runtime",
        level="info",
        action=action,
        dry_run=dry_run,
        ok=bool(result.get("ok", False)),
        summary=str(result.get("summary", "")),
    )
    return {
        "action": action,
        "dry_run": dry_run,
        **result,
    }


@app.get("/revenue/dashboard")
async def get_revenue_dashboard(user_id: str = Depends(require_rate_limit)):
    """Return structured revenue and pipeline dashboard data."""
    del user_id
    if not GUPPY_MEMORY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Memory module not available")
    if not hasattr(memory, "get_revenue_dashboard_data"):
        raise HTTPException(status_code=503, detail="Revenue dashboard not configured")

    try:
        return memory.get_revenue_dashboard_data()
    except Exception as e:
        logger.error(f"Revenue dashboard failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat(request: ChatRequest, user_id: str = Depends(require_rate_limit)):
    """Send text message and get response."""
    del user_id

    if not GUPPY_CORE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Guppy core not available")

    idempotency_key = str(request.idempotency_key or "").strip()
    request_fingerprint = _build_chat_request_fingerprint(request) if idempotency_key else ""
    idempotency_owner = False
    if idempotency_key:
        while True:
            idempotency_owner, idempotency_event = _register_chat_idempotency_key(idempotency_key, request_fingerprint)
            if idempotency_owner:
                break
            await _run_blocking(
                idempotency_event.wait,
                timeout_seconds=max(CHAT_TIMEOUT_SECONDS, 120.0),
            )
            idempotent_result = _resolve_chat_idempotency_key(idempotency_key, request_fingerprint)
            if isinstance(idempotent_result, dict):
                response_payload = idempotent_result.get("response")
                if isinstance(response_payload, dict):
                    return response_payload
                if "error" in idempotent_result:
                    raise HTTPException(
                        status_code=int(idempotent_result.get("status", 500) or 500),
                        detail=idempotent_result.get("error"),
                        headers=idempotent_result.get("headers") if isinstance(idempotent_result.get("headers"), dict) else None,
                    )
            idempotency_owner, idempotency_event, took_ownership = _takeover_chat_idempotency_key(
                idempotency_key,
                request_fingerprint,
            )
            if idempotency_owner and took_ownership:
                break

    try:
        active_instance_name, active_instance_type, active_instance_persona, _active_instance_voice = _get_active_instance_context()
        if _request_is_morning_brief(request):
            response = _build_morning_brief_response()
            log_session_event(
                "api",
                "morning_brief_served",
                level="info",
                session_id=request.session_id or "",
                instance_name=active_instance_name,
                used_saved_report=bool(_latest_daily_report_path()),
            )
            if request.session_id and GUPPY_MEMORY_AVAILABLE:
                for role, content in (("user", request.message), ("assistant", response)):
                    try:
                        memory.save_message(
                            request.session_id,
                            role,
                            content,
                            workspace_name=str(active_instance_name or "").strip(),
                        )
                    except Exception as exc:
                        logger.error(
                            "morning brief memory.save_message failed session_id=%r role=%s error=%s",
                            request.session_id,
                            role,
                            exc,
                        )
            payload = {"response": response, "session_id": request.session_id, "brief": True}
            if idempotency_owner and idempotency_key:
                _complete_chat_idempotency_key(idempotency_key, response=payload, status_code=200)
            return payload

        system_prompt = _build_chat_system_prompt(
            session_id=request.session_id,
            message=request.message,
            mode=request.mode,
            persona=request.persona or active_instance_persona,
            model_id=request.mode,
            history=request.history,
        )

        cache_key = None
        if INFERENCE_ROUTER_AVAILABLE and _request_is_cacheable(request):
            try:
                router = get_router()
                task_type = router._classify_task(request.message, system_prompt)
                if task_type == "simple":
                    cache_key = build_response_cache_key(
                        message=request.message,
                        system_prompt=system_prompt,
                        mode=request.mode or "auto",
                        instance_name=active_instance_name,
                        instance_type=active_instance_type,
                    )
                    cached_response = get_cached_response(cache_key)
                    if cached_response:
                        payload = {"response": cached_response, "session_id": request.session_id, "cached": True}
                        if idempotency_owner and idempotency_key:
                            _complete_chat_idempotency_key(idempotency_key, response=payload, status_code=200)
                        return payload
            except Exception as e:
                logger.debug("Response cache lookup skipped: %s", e)

        response = await _run_blocking(
            _call_unified_inference,
            request.message,
            system_prompt,
            request.mode,
            request.history,
            instance_name=active_instance_name,
            instance_type=active_instance_type,
            timeout_seconds=CHAT_TIMEOUT_SECONDS,
        )

        if cache_key and response.strip():
            try:
                set_cached_response(cache_key, response)
            except Exception as e:
                logger.debug("Response cache store skipped: %s", e)

        if request.session_id and GUPPY_MEMORY_AVAILABLE:
            memory.save_message(
                request.session_id,
                "user",
                request.message,
                workspace_name=str(active_instance_name or "").strip(),
            )
            memory.save_message(
                request.session_id,
                "assistant",
                response,
                workspace_name=str(active_instance_name or "").strip(),
            )

        payload = {"response": response, "session_id": request.session_id}
        if idempotency_owner and idempotency_key:
            _complete_chat_idempotency_key(idempotency_key, response=payload, status_code=200)
        return payload

    except HTTPException as exc:
        if idempotency_owner and idempotency_key:
            _complete_chat_idempotency_key(
                idempotency_key,
                error=getattr(exc, "detail", "chat request failed"),
                status_code=int(getattr(exc, "status_code", 500) or 500),
                headers=getattr(exc, "headers", None),
            )
        raise
    except Exception as e:
        logger.error(f"Chat request failed: {e}")
        log_session_event(
            "api",
            "chat_failed",
            level="error",
            session_id=request.session_id or "",
            use_claude=bool(request.use_claude),
            error=str(e),
        )
        if idempotency_owner and idempotency_key:
            _complete_chat_idempotency_key(idempotency_key, error=str(e), status_code=500)
        raise HTTPException(status_code=500, detail=str(e))
