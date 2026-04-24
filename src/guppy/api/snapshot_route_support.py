from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException


_LOCALHOST_CLIENTS = {"127.0.0.1", "::1", "localhost", ""}


def _coerce_instance_type(entry: dict[str, Any] | None) -> str:
    return str((entry or {}).get("type", "user_instance") or "user_instance").strip() or "user_instance"


def _coerce_instance_persona(entry: dict[str, Any] | None) -> str:
    return str((entry or {}).get("persona", "guppy") or "guppy").strip() or "guppy"


def _resolve_instance_mode(config: dict[str, Any], target: str) -> str:
    for item in config.get("instances", []):
        if isinstance(item, dict) and str(item.get("name", "")).strip() == target:
            return str(item.get("mode", "auto") or "auto").strip().lower() or "auto"
    return "auto"


def _update_instance_runtime_state(owner: Any, state: dict[str, Any], target: str, query_text: str, mode: str, status: str) -> None:
    instances = state.setdefault("instances", {}) if isinstance(state, dict) else {}
    if not isinstance(instances, dict):
        return
    instance_state = instances.setdefault(target, {})
    if not isinstance(instance_state, dict):
        return
    instance_state["status"] = "busy" if status == "busy" else "running"
    instance_state["last_message"] = query_text[:200]
    instance_state["last_updated"] = datetime.now(timezone.utc).isoformat()
    instance_state["message_count"] = int(instance_state.get("message_count", 0) or 0) + 1
    instance_state["model_currently_using"] = mode
    owner._save_instance_state(state)


def _append_instance_conversation_logs(
    owner: Any,
    *,
    target: str,
    source_instance: str,
    query_text: str,
    response: str,
    status: str,
    mode: str,
    duration_ms: int,
) -> None:
    if not getattr(owner, "_INSTANCE_LOGGER_AVAILABLE", False):
        return
    owner.append_instance_log(
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
        owner.append_instance_log(
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


async def query_instance_response(owner: Any, name: str, request: Any) -> dict[str, Any]:
    target = (name or "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="instance name is required")
    if not getattr(owner, "GUPPY_CORE_AVAILABLE", False):
        raise HTTPException(status_code=503, detail="Guppy core not available")

    config, state, _config_warnings, _state_warnings = owner._load_normalized_instance_bundle(persist_repairs=True)
    names = owner._instance_names(config)
    if target not in names:
        raise HTTPException(status_code=404, detail=f"unknown instance: {target}")

    target_entry = owner._get_instance_entry(config, target) or {}
    target_type = _coerce_instance_type(target_entry)
    source_instance = (request.source_instance or "launcher").strip() or "launcher"
    if source_instance != "launcher":
        if source_instance not in names:
            raise HTTPException(status_code=404, detail=f"unknown source instance: {source_instance}")
        source_entry = owner._get_instance_entry(config, source_instance) or {}
        source_type = _coerce_instance_type(source_entry)
        allowed, reason, _permissions = owner.check_instance_tool_permission(
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

    if not owner._instance_query_lock.acquire(blocking=False):
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

        mode = _resolve_instance_mode(config, target)
        system_prompt = owner._build_chat_system_prompt(
            session_id=f"instance-{target}",
            message=query_text,
            mode=mode,
            persona=_coerce_instance_persona(target_entry),
            model_id="",
        )
        try:
            response = await owner._run_blocking(
                owner._call_unified_inference,
                query_text,
                system_prompt,
                mode,
                None,
                instance_name=target,
                instance_type=target_type,
                timeout_seconds=timeout_s,
            )
            status = "ok"
        except HTTPException as exc:
            if exc.status_code != 504:
                raise
            response = ""
            status = "timeout"

        duration_ms = int((time.perf_counter() - started) * 1000)
        _update_instance_runtime_state(owner, state, target, query_text, mode, status)
        _append_instance_conversation_logs(
            owner,
            target=target,
            source_instance=source_instance,
            query_text=query_text,
            response=response,
            status=status,
            mode=mode,
            duration_ms=duration_ms,
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
        owner._instance_query_lock.release()


def recent_logs_response(owner: Any, limit: int = 100) -> dict[str, Any]:
    bounded_limit = max(1, min(int(limit), 300))
    runtime_dir = owner._runtime_dir
    return {
        "session_events": owner.tail_session_events(limit=bounded_limit),
        "agent_performance": owner._read_jsonl_tail(runtime_dir / "agent_performance.jsonl", limit=bounded_limit),
        "integration_events": owner._read_jsonl_tail(runtime_dir / "integration_events.jsonl", limit=bounded_limit),
    }


def repair_token_refresh_response(owner: Any, client_ip: str) -> dict[str, str]:
    normalized_client_ip = str(client_ip or "").strip()
    if normalized_client_ip not in _LOCALHOST_CLIENTS:
        owner.log_session_event(
            "api",
            "repair_token_refresh_rejected",
            level="warning",
            client_ip=normalized_client_ip,
        )
        raise HTTPException(status_code=403, detail="localhost only")

    token = str(getattr(owner, "_REPAIR_TOKEN", "") or "")
    secret_store_available = bool(getattr(owner, "_SECRET_STORE_AVAILABLE", False))
    secret_store = getattr(owner, "_secret_store", None)
    if secret_store_available and secret_store is not None:
        try:
            token = token or (secret_store.get_secret("repair_token") or "")
        except Exception:
            pass

    repair_token_file = getattr(owner, "_REPAIR_TOKEN_FILE", None)
    if not token and repair_token_file is not None and repair_token_file.exists():
        try:
            token = repair_token_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass

    owner.log_session_event(
        "api",
        "repair_token_refresh",
        level="info",
        client_ip=normalized_client_ip,
        has_token=bool(token),
    )
    return {"repair_token": token}  # nosec: localhost-only endpoint; token is intentionally distributed to caller


async def repair_runtime_response(owner: Any, request: Any) -> dict[str, Any]:
    action = (request.action or "").strip().lower()
    dry_run = bool(request.dry_run)
    result = await asyncio.to_thread(owner._do_repair_action, action, dry_run)
    owner.log_session_event(
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


def revenue_dashboard_response(owner: Any) -> Any:
    if not getattr(owner, "GUPPY_MEMORY_AVAILABLE", False):
        raise HTTPException(status_code=503, detail="Memory module not available")

    memory_module = getattr(owner, "memory", None)
    if memory_module is None or not hasattr(memory_module, "get_revenue_dashboard_data"):
        raise HTTPException(status_code=503, detail="Revenue dashboard not configured")

    try:
        return memory_module.get_revenue_dashboard_data()
    except Exception as exc:
        owner.logger.error("Revenue dashboard failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
