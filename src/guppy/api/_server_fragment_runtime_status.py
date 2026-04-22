async def _run_blocking(func, *args, timeout_seconds: float, **kwargs):
    """Run blocking work in a thread with a hard timeout."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(partial(func, *args, **kwargs)),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Request timed out") from exc


def _extract_text_from_anthropic_blocks(blocks) -> str:
    parts = []
    for b in blocks:
        if getattr(b, "type", None) == "text" and getattr(b, "text", "").strip():
            parts.append(b.text.strip())
    return "\n".join(parts).strip()


def _sanitize_chat_history(history: Any, limit: int = 12) -> list[dict[str, str]]:
    if not isinstance(history, list):
        return []
    out: list[dict[str, str]] = []
    for item in history[-max(1, limit):]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if role not in {"user", "assistant"} or not content:
            continue
        out.append({"role": role, "content": content[:2000]})
    return out


def _build_router_messages(system_prompt: str, user_text: str, history: list[dict[str, str]]) -> list[dict[str, str]]:
    trimmed = list(history)
    if trimmed and trimmed[-1].get("role") == "user" and trimmed[-1].get("content", "").strip() == user_text.strip():
        trimmed = trimmed[:-1]

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(trimmed)
    messages.append({"role": "user", "content": user_text})
    return messages


def _request_is_cacheable(request: ChatRequest) -> bool:
    if not response_cache_enabled():
        return False
    if request.session_id:
        return False
    if _sanitize_chat_history(request.history):
        return False
    mode = (request.mode or "auto").strip().lower()
    if mode in {"teaching", "vault"}:
        return False
    return bool((request.message or "").strip())


def _augment_system_with_history(system_prompt: str, history: list[dict[str, str]]) -> str:
    if not history:
        return system_prompt
    lines = ["LIVE SESSION HISTORY (RECENT TURNS):"]
    for item in history[-8:]:
        speaker = "Ryan" if item.get("role") == "user" else "Guppy"
        snippet = item.get("content", "").replace("\n", " ").strip()
        if len(snippet) > 240:
            snippet = snippet[:240] + "..."
        lines.append(f"- {speaker}: {snippet}")
    return f"{system_prompt}\n\n" + "\n".join(lines)


def _is_rate_limited_error(error: Exception | str) -> bool:
    txt = str(error or "").lower()
    return "429" in txt or "rate limit" in txt or "too many requests" in txt


def _call_unified_inference(
    user_text: str,
    system_prompt: str,
    mode: Optional[str] = None,
    history: Optional[list[dict[str, str]]] = None,
    instance_name: Optional[str] = None,
    instance_type: Optional[str] = None,
) -> str:
    """
    NEW: Unified inference using intelligent router.
    Priority: local (guppy) -> haiku -> sonnet
    Automatically falls back if local model is unavailable.

    This is now the PRIMARY inference method.
    """
    if not GUPPY_CORE_AVAILABLE:
        raise RuntimeError("Guppy core not available.")

    if not INFERENCE_ROUTER_AVAILABLE:
        # Fallback to Claude if router unavailable
        logger.warning("Router unavailable, falling back to Claude")
        return _call_claude_with_tools(
            user_text,
            system_prompt,
            instance_name=instance_name,
            instance_type=instance_type,
        )

    router = get_router()
    clean_history = _sanitize_chat_history(history)
    augmented_system_prompt = _augment_system_with_history(system_prompt, clean_history)
    router_messages = _build_router_messages(augmented_system_prompt, user_text, clean_history)
    requested_mode = (mode or os.environ.get("GUPPY_DEFAULT_MODE", "auto") or "auto").strip().lower()

    try:
        # Local-only mode for overnight low-compute reliability.
        if requested_mode == "local":
            task_type = router._classify_task(user_text, augmented_system_prompt)
            model_name = router.LOCAL_TIER_MAP.get(task_type, router.LOCAL_MODEL)
            paired = os.environ.get("GUPPY_LOCAL_PAIRED", "0").strip().lower() in {"1", "true", "yes", "on"}
            if paired and task_type != "simple":
                result = router.query_local_paired(
                    augmented_system_prompt,
                    user_text,
                    task_type,
                    core.TOOLS,
                    router_messages,
                )
                if not result:
                    raise RuntimeError("Local-only paired mode failed (Ollama/model unavailable)")
                response = str(result.get("response", "")).strip()
                if not response:
                    raise RuntimeError("Local-only paired mode returned empty response")
                source = str(result.get("source", "local"))
                metadata = dict(result.get("metadata", {}))
            else:
                response = _call_selected_local_runtime(
                    user_text,
                    augmented_system_prompt,
                    instance_name=instance_name,
                    instance_type=instance_type,
                    model_override=model_name,
                )
                source = "local"
                metadata = {"route_mode": "local", "model": model_name}
        elif requested_mode == "code":
            result = router.query_with_boost(
                system_prompt=augmented_system_prompt,
                user_text=user_text,
                model=router.LOCAL_CODE_MODEL,
                boost_mode=router.HAIKU_BOOST_CODE_REVIEW,
                tools=None,
                messages=router_messages,
            )
            if not result:
                raise RuntimeError("Code mode local model unavailable")
            response = str(result.get("response", ""))
            source = str(result.get("source", "local"))
            metadata = dict(result.get("metadata", {}))
        else:
            route_decision = router.resolve_ui_route(
                user_text=user_text,
                system_prompt=augmented_system_prompt,
                mode=requested_mode,
                api_key_available=bool(getattr(router, "anthropic_available", False)),
            )
            executor = str(route_decision.get("executor", "") or "").strip().lower()
            target_model = str(route_decision.get("model", "") or "").strip()
            backup_model = str(route_decision.get("backup_model", "") or "").strip()

            if executor == "error":
                raise RuntimeError(str(route_decision.get("error") or route_decision.get("route_reason") or "Requested route unavailable"))

            if executor == "claude":
                response = _call_claude_with_tools(
                    user_text,
                    augmented_system_prompt,
                    instance_name=instance_name,
                    instance_type=instance_type,
                    preferred_model=target_model or None,
                    backup_model=backup_model or None,
                )
                source = "haiku" if "haiku" in (target_model or "").lower() else "sonnet"
                metadata = {"route_decision": route_decision}
            elif executor in {"ollama", "ollama_paired"}:
                if executor == "ollama_paired":
                    result = router.query_local_paired(
                        augmented_system_prompt,
                        user_text,
                        str(route_decision.get("task_type", "complex") or "complex"),
                        core.TOOLS,
                        router_messages,
                    )
                    if not result:
                        raise RuntimeError("Local paired route failed")
                    response = str(result.get("response", "")).strip()
                    if not response:
                        raise RuntimeError("Local paired route returned empty response")
                    source = str(result.get("source", "local"))
                    metadata = dict(result.get("metadata", {}))
                else:
                    response = _call_selected_local_runtime(
                        user_text,
                        augmented_system_prompt,
                        instance_name=instance_name,
                        instance_type=instance_type,
                        model_override=target_model or None,
                    )
                    source = "local"
                    metadata = {"route_decision": route_decision}
            else:
                response, source, metadata = router.query_smart(
                    system_prompt=augmented_system_prompt,
                    user_text=user_text,
                    tools=core.TOOLS,
                    messages=router_messages,
                )

        logger.info(f"Inference completed via {source}. Tokens: {metadata.get('usage', {}).get('output_tokens', '?')}")
        return response

    except Exception as e:
        # Do NOT fall back to Claude when mode is explicitly 'local' or 'code' â€”
        # those modes are intentional; silently spending cloud quota is wrong and
        # hides the real error (e.g. Ollama not running).
        if requested_mode in {"local", "code", "claude", "ollama"}:
            logger.error(f"Inference failed in explicit mode '{requested_mode}': {e}")
            raise
        logger.error(f"Unified inference failed: {e}. Escalating to Claude Sonnet.")
        # Final fallback to Claude (auto/teaching/default modes only).
        # If cloud quota is throttled, fall back to local Ollama text mode before giving up.
        try:
            return _call_claude_with_tools(
                user_text,
                augmented_system_prompt,
                instance_name=instance_name,
                instance_type=instance_type,
            )
        except Exception as cloud_error:
            if _is_rate_limited_error(cloud_error):
                logger.warning("Claude fallback hit rate limits; trying local Ollama fallback")
                return _call_ollama_with_tools(
                    user_text,
                    augmented_system_prompt,
                    instance_name=instance_name,
                    instance_type=instance_type,
                )
            raise



def _call_claude_with_tools(
    user_text: str,
    system_prompt: str,
    *,
    instance_name: Optional[str] = None,
    instance_type: Optional[str] = None,
    preferred_model: Optional[str] = None,
    backup_model: Optional[str] = None,
) -> str:
    if not ANTHROPIC_AVAILABLE:
        raise RuntimeError("Anthropic SDK is not installed.")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")

    primary_model = str(preferred_model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")).strip() or "claude-sonnet-4-6"
    backup_model_name = str(backup_model or os.environ.get("ANTHROPIC_BACKUP_MODEL", "claude-haiku-4-5-20251001")).strip()
    model_chain = [primary_model] + ([backup_model_name] if backup_model_name and backup_model_name != primary_model else [])

    client = anthropic.Anthropic(api_key=api_key)
    msgs = [{"role": "user", "content": user_text}]
    final_text = ""

    while True:
        resp = None
        last_err = None
        for model_name in model_chain:
            try:
                resp = client.messages.create(
                    model=model_name,
                    max_tokens=4096,
                    system=system_prompt,
                    tools=core.TOOLS,
                    messages=msgs,
                )
                break
            except Exception as e:
                last_err = e
        if resp is None:
            raise RuntimeError(f"Claude request failed on all configured models: {last_err}")

        msgs.append({"role": "assistant", "content": resp.content})
        block_text = _extract_text_from_anthropic_blocks(resp.content)
        if block_text:
            final_text = block_text

        tool_uses = [b for b in resp.content if getattr(b, "type", None) == "tool_use"]
        if not tool_uses or getattr(resp, "stop_reason", "") == "end_turn":
            break

        results = []
        for tu in tool_uses:
            result = core.run_tool(
                tu.name,
                tu.input,
                instance_name=instance_name,
                instance_type=instance_type,
            )
            results.append({"type": "tool_result", "tool_use_id": tu.id, "content": str(result)})
        msgs.append({"role": "user", "content": results})

    return final_text or "No response produced."
