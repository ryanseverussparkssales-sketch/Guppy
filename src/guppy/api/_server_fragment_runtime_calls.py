def _call_ollama_with_tools(
    user_text: str,
    system_prompt: str,
    *,
    instance_name: Optional[str] = None,
    instance_type: Optional[str] = None,
    model_override: Optional[str] = None,
) -> str:
    model = str(model_override or os.environ.get("OLLAMA_MODEL", "guppy")).strip() or "guppy"
    ok, err = core.check_ollama(model)
    if not ok:
        raise RuntimeError(err)

    all_msgs = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}]
    ollama_tools = core.to_ollama_tools(core.TOOLS)
    final_text = ""

    while True:
        payload = json.dumps({
            "model": model,
            "messages": all_msgs,
            "tools": ollama_tools,
            "stream": False,
            "keep_alive": "10m",
            "options": {"temperature": 0.8, "top_p": 0.95, "top_k": 40, "num_predict": 512},
        }).encode()
        req = urllib.request.Request(
            "http://localhost:11434/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read().decode())

        msg = data.get("message", {})
        content = (msg.get("content") or "").strip()
        if content:
            final_text = content

        tool_calls = msg.get("tool_calls") or []
        clean_assistant = {"role": "assistant", "content": content}
        if tool_calls:
            clean_assistant["tool_calls"] = tool_calls
        all_msgs.append(clean_assistant)

        if not tool_calls:
            break

        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            result = core.run_tool(
                name,
                args if isinstance(args, dict) else {},
                instance_name=instance_name,
                instance_type=instance_type,
            )
            all_msgs.append({"role": "tool", "content": str(result)})

    return final_text or "No response produced."


async def _stream_chunks(text: str) -> AsyncGenerator[str, None]:
    for chunk in text.split():
        yield chunk + " "

# â”€â”€ Routes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "Guppy API is running", "status": "healthy"}


@app.get("/metrics")
async def get_metrics(_user_id: str = Depends(require_rate_limit)):
    """Runtime metrics for API and tool execution health."""
    with _api_metrics_lock:
        requests_total = _api_metrics["requests_total"]
        avg_latency_ms = (_api_metrics["latency_total_ms"] / requests_total) if requests_total else 0.0
        payload = {
            "started_at": _api_metrics["started_at"],
            "requests_total": requests_total,
            "errors_total": _api_metrics["errors_total"],
            "slow_requests": _api_metrics["slow_requests"],
            "average_latency_ms": round(avg_latency_ms, 2),
            "path_counts": dict(_api_metrics["path_counts"]),
            "status_counts": dict(_api_metrics["status_counts"]),
        }

    if GUPPY_CORE_AVAILABLE and hasattr(core, "get_tool_health_snapshot"):
        try:
            payload["tool_runner"] = core.get_tool_health_snapshot()
        except Exception as e:
            payload["tool_runner_error"] = str(e)
    return payload

@app.post("/auth/verify", response_model=TokenResponse)
async def auth_verify_turnstile_token(
    request: TurnstileToken,
    _auth_limiter: str = Depends(require_auth_rate_limit)
):
    """Verify Turnstile token and issue JWT."""
    if not await verify_turnstile_token_auth(request.token):
        raise HTTPException(status_code=400, detail="Invalid Turnstile token")

    # Issue JWT token
    access_token = create_access_token(data={"sub": "guppy_user"})
    return TokenResponse(
        access_token=access_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@app.get("/auth/self-check")
async def auth_self_check(_user_id: str = Depends(require_rate_limit)):
    """Local auth handshake probe for launcher diagnostics."""
    return {
        "ok": True,
        "user_id": user_id,
        "mode": "dev" if DEV_MODE else "strict",
    }


@app.get("/status")
async def get_status(_user_id: str = Depends(require_rate_limit)):
    """Get system status and current context."""

    if not GUPPY_CORE_AVAILABLE:
        return {"status": "error", "message": "Guppy core not available"}

    try:
        now = time.time()
        if _status_cache["payload"] is not None and _status_cache["expires_at"] > now:
            return _status_cache["payload"]

        context = {}
        if STATUS_INCLUDE_WINDOW_CONTEXT and GUPPY_DAEMON_AVAILABLE:
            daemon = get_daemon_manager()
            if daemon and getattr(daemon, "window_watcher", None):
                try:
                    context = await asyncio.wait_for(
                        asyncio.to_thread(daemon.window_watcher.get_enhanced_context),
                        timeout=0.2,
                    )
                except Exception:
                    # Keep /status responsive even when watcher context polling stalls.
                    context = {}

        voice_tts = _VOICE_TTS_BACKEND if GUPPY_VOICE_AVAILABLE else "none"
        voice_stt = _VOICE_STT_BACKEND if GUPPY_VOICE_AVAILABLE else "none"
        voice_status = {
            "available": GUPPY_VOICE_AVAILABLE,
            "tts_backend": voice_tts,
            "stt_backend": voice_stt,
            "details": _VOICE_BACKEND_DETAILS if GUPPY_VOICE_AVAILABLE else [],
        }

        payload = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "context": context,
            "memory_available": GUPPY_MEMORY_AVAILABLE,
            "voice_available": GUPPY_VOICE_AVAILABLE,
            "voice_tts_backend": voice_tts,
            "voice_stt_backend": voice_stt,
            "voice_status": voice_status,
            "daemon_available": GUPPY_DAEMON_AVAILABLE,
            "startup_readiness": _startup_readiness_cached_or_unknown(),
            "local_runtime": _build_local_runtime_status(),
            "resource_envelope": _read_resource_envelope_status(),
        }
        _status_cache["payload"] = payload
        _status_cache["expires_at"] = now + STATUS_CACHE_TTL_SECONDS
        return payload
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        log_session_event("api", "status_failed", level="error", error=str(e))
        return {"status": "error", "message": str(e)}


@app.get("/startup/check")
async def startup_check(deep: bool = False, _user_id: str = Depends(require_rate_limit)):
    """Startup readiness checks (cached by default, deep probe when requested)."""
    if deep:
        snapshot = await asyncio.to_thread(_startup_readiness_snapshot)
    else:
        snapshot = _startup_readiness_cached_or_unknown()
        if snapshot.get("overall") == "UNKNOWN" or _startup_readiness_cache_expired():
            _trigger_startup_readiness_refresh()
    log_session_event("api", "startup_check", level="info", overall=snapshot.get("overall", "unknown"))
    return snapshot


def _governance_summary_payload(instance_name: str, instance_type: str) -> dict[str, Any]:
    permissions = resolve_instance_permissions(instance_name, instance_type)
    return {
        "auth_mode": str(permissions.get("_auth_mode", "runtime_default") or "runtime_default"),
        "auth_mode_label": auth_mode_label(str(permissions.get("_auth_mode", "runtime_default") or "runtime_default")),
        "tool_allow": list(permissions.get("_tool_allow", [])),
        "tool_block": list(permissions.get("_tool_block", [])),
        "endpoint_allow": list(permissions.get("_endpoint_allow", [])),
        "endpoint_block": list(permissions.get("_endpoint_block", [])),
        "policy_note": str(permissions.get("_policy_note", "") or ""),
        "capabilities": {
            "read": bool(permissions.get("read", False)),
            "write": bool(permissions.get("write", False)),
            "execute": bool(permissions.get("execute", False)),
            "network": bool(permissions.get("network", False)),
        },
    }


def _workspace_connector_payload(instance_name: str) -> list[dict[str, Any]]:
    return workspace_connector_inventory(instance_name, config_path=_config_dir / "connector_bindings.json")


def _connector_inventory_payload() -> list[dict[str, Any]]:
    return connector_inventory()


@app.get("/instances")
async def list_instances(_user_id: str = Depends(require_rate_limit)):
    """Contract-first M2 endpoint: list configured instances with lightweight runtime state."""
    config, state, config_warnings, state_warnings = _load_normalized_instance_bundle(persist_repairs=True)

    items: list[dict[str, Any]] = []
    instance_state = state.get("instances", {}) if isinstance(state, dict) else {}
    for item in config.get("instances", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        st = instance_state.get(name, {}) if isinstance(instance_state, dict) else {}
        items.append(
            {
                "name": name,
                "description": str(item.get("description", "")),
                "mode": str(item.get("mode", "auto") or "auto"),
                "persona": str(item.get("persona", "guppy") or "guppy"),
                "voice": str(item.get("voice", "default") or "default"),
                "type": str(item.get("type", "user_instance") or "user_instance"),
                "created_at": item.get("created_at"),
                "enabled": bool(item.get("enabled", True)),
                "status": str(st.get("status", "idle")),
                "last_message": str(st.get("last_message", "")),
                "last_updated": st.get("last_updated"),
                "message_count": int(st.get("message_count", 0) or 0),
                "model_currently_using": str(st.get("model_currently_using", item.get("mode", "auto")) or "auto"),
                "governance": _governance_summary_payload(name, str(item.get("type", "user_instance") or "user_instance")),
                "connectors": _workspace_connector_payload(name),
            }
        )
    limits = _instance_limits_payload(config, state)
    warnings = config_warnings + state_warnings
    if limits["configured"] >= limits["max_configured"]:
        warnings.append("configured instance cap reached (5 / 5)")
    if limits["active_runtime"] >= limits["max_active_runtime"]:
        warnings.append("runtime-active instance cap reached (2 / 2)")

    return {
        "version": int(config.get("version", 1) or 1),
        "active_instance": str(config.get("active_instance", "guppy-primary")),
        "instances": items,
        "limits": limits,
        "warnings": warnings,
    }


@app.post("/instances")
async def create_or_update_instance(
    request: InstanceConfigRequest,
    _user_id: str = Depends(require_rate_limit),
):
    raw_config = _load_instances_config()
    config, _warnings = _normalize_instances_config(raw_config)
    config, action = _upsert_instance_config(config, request)
    _save_instances_config(config)

    names = _instance_names(config)
    raw_state = _load_instance_state(config)
    state, _state_warnings = _normalize_instance_state(
        raw_state,
        valid_names=names,
        active_instance=str(config.get("active_instance", names[0] if names else "guppy-primary")),
    )
    instances = state.get("instances", {}) if isinstance(state.get("instances"), dict) else {}
    instances[str(request.name).strip()] = _default_instance_state((request.mode or "auto").strip().lower() or "auto")
    state["instances"] = instances
    _activate_instance_state(state, str(config.get("active_instance", names[0] if names else request.name)).strip())
    _save_instance_state(state)
    limits = _instance_limits_payload(config, state)

    return {
        "ok": True,
        "action": action,
        "instance": str(request.name).strip(),
        "active_instance": str(config.get("active_instance", "guppy-primary")),
        "limits": limits,
    }


@app.post("/instances/{name}/governance")
async def save_instance_governance(
    name: str,
    request: InstanceGovernanceRequest,
    _user_id: str = Depends(require_rate_limit),
):
    target = (name or "").strip()
    config, _state, _warnings, _state_warnings = _load_normalized_instance_bundle(persist_repairs=True)
    target_entry = _get_instance_entry(config, target)
    if not isinstance(target_entry, dict):
        raise HTTPException(status_code=404, detail=f"unknown instance: {target}")
    instance_type = str(target_entry.get("type", "user_instance") or "user_instance").strip() or "user_instance"
    resolved = resolve_instance_permissions(target, instance_type)
    set_instance_tool_permission_policy(
        target,
        {
            "read": bool(resolved.get("read", False)),
            "write": bool(resolved.get("write", False)),
            "execute": bool(resolved.get("execute", False)),
            "network": bool(resolved.get("network", False)),
            "auth_mode": request.auth_mode,
            "tool_allow": request.tool_allow,
            "tool_block": request.tool_block,
            "endpoint_allow": request.endpoint_allow,
            "endpoint_block": request.endpoint_block,
            "policy_note": request.policy_note,
        },
    )
    return {
        "ok": True,
        "instance": target,
        "governance": _governance_summary_payload(target, instance_type),
    }


@app.get("/connectors")
async def list_connectors(_user_id: str = Depends(require_rate_limit)):
    return {
        "connectors": _connector_inventory_payload(),
    }


@app.post("/connectors/{connector_id}/verify")
async def verify_connector(
    connector_id: str,
    request: ConnectorActionRequest,
    _user_id: str = Depends(require_rate_limit),
):
    result = run_connector_action(
        connector_id,
        "verify",
        provider=request.provider,
        account_id=request.account_id,
        secret_key=request.secret_key,
        secret_value=request.secret_value,
    )
    return {"connector": str(connector_id or "").strip().lower(), **result}


@app.post("/connectors/{connector_id}/connect")
async def connect_connector(
    connector_id: str,
    request: ConnectorActionRequest,
    _user_id: str = Depends(require_rate_limit),
):
    result = run_connector_action(
        connector_id,
        "connect",
        provider=request.provider,
        account_id=request.account_id,
        secret_key=request.secret_key,
        secret_value=request.secret_value,
    )
    return {"connector": str(connector_id or "").strip().lower(), **result}


@app.post("/connectors/{connector_id}/reconnect")
async def reconnect_connector(
    connector_id: str,
    request: ConnectorActionRequest,
    _user_id: str = Depends(require_rate_limit),
):
    result = run_connector_action(
        connector_id,
        "reconnect",
        provider=request.provider,
        account_id=request.account_id,
        secret_key=request.secret_key,
        secret_value=request.secret_value,
    )
    return {"connector": str(connector_id or "").strip().lower(), **result}


@app.post("/connectors/{connector_id}/disconnect")
async def disconnect_connector(
    connector_id: str,
    request: ConnectorActionRequest,
    _user_id: str = Depends(require_rate_limit),
):
    result = run_connector_action(
        connector_id,
        "disconnect",
        provider=request.provider,
        account_id=request.account_id,
        secret_key=request.secret_key,
        secret_value=request.secret_value,
    )
    return {"connector": str(connector_id or "").strip().lower(), **result}


@app.get("/instances/{name}/connectors")
async def list_instance_connectors(
    name: str,
    _user_id: str = Depends(require_rate_limit),
):
    target = (name or "").strip()
    config, _state, _warnings, _state_warnings = _load_normalized_instance_bundle(persist_repairs=True)
    target_entry = _get_instance_entry(config, target)
    if not isinstance(target_entry, dict):
        raise HTTPException(status_code=404, detail=f"unknown instance: {target}")
    return {
        "instance": target,
        "connectors": _workspace_connector_payload(target),
    }


@app.post("/instances/{name}/connectors/{connector_id}")
async def save_instance_connector_binding(
    name: str,
    connector_id: str,
    request: InstanceConnectorBindingRequest,
    _user_id: str = Depends(require_rate_limit),
):
    target = (name or "").strip()
    normalized_connector = (connector_id or "").strip().lower()
    config, _state, _warnings, _state_warnings = _load_normalized_instance_bundle(persist_repairs=True)
    target_entry = _get_instance_entry(config, target)
    if not isinstance(target_entry, dict):
        raise HTTPException(status_code=404, detail=f"unknown instance: {target}")
    save_workspace_connector_binding(
        target,
        normalized_connector,
        {
            "enabled": bool(request.enabled),
            "account_id": request.account_id,
            "provider": request.provider,
            "action_allow": request.action_allow,
            "action_block": request.action_block,
            "endpoint_allow": request.endpoint_allow,
            "endpoint_block": request.endpoint_block,
            "note": request.note,
        },
        config_path=_config_dir / "connector_bindings.json",
    )
    return {
        "ok": True,
        "instance": target,
        "connector": normalized_connector,
        "connectors": _workspace_connector_payload(target),
    }


@app.post("/instances/{name}/activate")
async def activate_instance(
    name: str,
    _user_id: str = Depends(require_rate_limit),
):
    target = (name or "").strip()
    raw_config = _load_instances_config()
    config, _warnings = _normalize_instances_config(raw_config)
    names = _instance_names(config)
    if target not in names:
        raise HTTPException(status_code=404, detail=f"unknown instance: {target}")

    config["active_instance"] = target
    _save_instances_config(config)

    raw_state = _load_instance_state(config)
    state, _state_warnings = _normalize_instance_state(
        raw_state,
        valid_names=names,
        active_instance=target,
    )
    _activate_instance_state(state, target)
    _save_instance_state(state)
    return {
        "ok": True,
        "active_instance": target,
        "limits": _instance_limits_payload(config, state),
    }


@app.delete("/instances/{name}")
async def delete_instance(
    name: str,
    _user_id: str = Depends(require_rate_limit),
):
    target = (name or "").strip()
    raw_config = _load_instances_config()
    config, _warnings = _normalize_instances_config(raw_config)
    items = list(config.get("instances", [])) if isinstance(config.get("instances"), list) else []
    kept = [item for item in items if not (isinstance(item, dict) and str(item.get("name", "")).strip() == target)]
    if len(kept) == len(items):
        raise HTTPException(status_code=404, detail=f"unknown instance: {target}")
    if not kept:
        raise HTTPException(status_code=400, detail="cannot delete the last configured instance")

    config["instances"] = kept
    names = _instance_names(config)
    if str(config.get("active_instance", "")).strip() == target:
        config["active_instance"] = names[0]
    _save_instances_config(config)

    raw_state = _load_instance_state(config)
    state, _state_warnings = _normalize_instance_state(
        raw_state,
        valid_names=names,
        active_instance=str(config.get("active_instance", names[0])),
    )
    instances = state.get("instances", {}) if isinstance(state.get("instances"), dict) else {}
    instances.pop(target, None)
    state["instances"] = instances
    _save_instance_state(state)
    if _INSTANCE_LOGGER_AVAILABLE:
        delete_instance_log(target)
    return {
        "ok": True,
        "deleted": target,
        "active_instance": str(config.get("active_instance", names[0])),
        "limits": _instance_limits_payload(config, state),
    }
