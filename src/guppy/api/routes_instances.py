from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException

from src.guppy.api._server_fragment_models import (
    ConnectorActionRequest,
    InstanceConfigRequest,
    InstanceConnectorBindingRequest,
    InstanceGovernanceRequest,
    InstanceQueryRequest,
)
from src.guppy.api.server_context import ServerContext
from src.guppy.workspace_governance import validate_connector_binding_request


def build_instances_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter()
    owner = ctx.owner

    @router.get("/instances")
    async def list_instances(user_id: str = Depends(ctx.require_rate_limit)):
        del user_id
        config, state, config_warnings, state_warnings = ctx.load_normalized_instance_bundle(
            persist_repairs=True
        )

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
                    "model_currently_using": str(
                        st.get("model_currently_using", item.get("mode", "auto")) or "auto"
                    ),
                    "governance": ctx.governance_summary_payload(
                        name, str(item.get("type", "user_instance") or "user_instance")
                    ),
                    "connectors": ctx.workspace_connector_payload(name),
                }
            )
        limits = ctx.instance_limits_payload(config, state)
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

    @router.post("/instances")
    async def create_or_update_instance(
        request: InstanceConfigRequest,
        user_id: str = Depends(ctx.require_rate_limit),
    ):
        del user_id
        raw_config = ctx.load_instances_config()
        config, _warnings = ctx.normalize_instances_config(raw_config)
        config, action = ctx.upsert_instance_config(config, request)
        ctx.save_instances_config(config)

        names = ctx.instance_names(config)
        raw_state = ctx.load_instance_state(config)
        state, _state_warnings = ctx.normalize_instance_state(
            raw_state,
            valid_names=names,
            active_instance=str(
                config.get("active_instance", names[0] if names else "guppy-primary")
            ),
        )
        instances = state.get("instances", {}) if isinstance(state.get("instances"), dict) else {}
        instances[str(request.name).strip()] = ctx.default_instance_state(
            (request.mode or "auto").strip().lower() or "auto"
        )
        state["instances"] = instances
        ctx.activate_instance_state(
            state, str(config.get("active_instance", names[0] if names else request.name)).strip()
        )
        ctx.save_instance_state(state)
        limits = ctx.instance_limits_payload(config, state)

        return {
            "ok": True,
            "action": action,
            "instance": str(request.name).strip(),
            "active_instance": str(config.get("active_instance", "guppy-primary")),
            "limits": limits,
        }

    @router.post("/instances/{name}/governance")
    async def save_instance_governance(
        name: str,
        request: InstanceGovernanceRequest,
        user_id: str = Depends(ctx.require_rate_limit),
    ):
        del user_id
        target = (name or "").strip()
        config, _state, _warnings, _state_warnings = ctx.load_normalized_instance_bundle(
            persist_repairs=True
        )
        target_entry = ctx.get_instance_entry(config, target)
        if not isinstance(target_entry, dict):
            raise HTTPException(status_code=404, detail=f"unknown instance: {target}")
        instance_type = (
            str(target_entry.get("type", "user_instance") or "user_instance").strip()
            or "user_instance"
        )
        resolved = ctx.resolve_instance_permissions(target, instance_type)
        ctx.set_instance_tool_permission_policy(
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
            "governance": ctx.governance_summary_payload(target, instance_type),
        }

    @router.get("/connectors")
    async def list_connectors(user_id: str = Depends(ctx.require_rate_limit)):
        del user_id
        return {"connectors": ctx.connector_inventory_payload()}

    @router.post("/connectors/{connector_id}/verify")
    async def verify_connector(
        connector_id: str,
        request: ConnectorActionRequest,
        user_id: str = Depends(ctx.require_rate_limit),
    ):
        del user_id
        result = ctx.run_connector_action(
            connector_id,
            "verify",
            provider=request.provider,
            account_id=request.account_id,
            secret_key=request.secret_key,
            secret_value=request.secret_value,
        )
        return {"connector": str(connector_id or "").strip().lower(), **result}

    @router.post("/connectors/{connector_id}/connect")
    async def connect_connector(
        connector_id: str,
        request: ConnectorActionRequest,
        user_id: str = Depends(ctx.require_rate_limit),
    ):
        del user_id
        result = ctx.run_connector_action(
            connector_id,
            "connect",
            provider=request.provider,
            account_id=request.account_id,
            secret_key=request.secret_key,
            secret_value=request.secret_value,
        )
        return {"connector": str(connector_id or "").strip().lower(), **result}

    @router.post("/connectors/{connector_id}/reconnect")
    async def reconnect_connector(
        connector_id: str,
        request: ConnectorActionRequest,
        user_id: str = Depends(ctx.require_rate_limit),
    ):
        del user_id
        result = ctx.run_connector_action(
            connector_id,
            "reconnect",
            provider=request.provider,
            account_id=request.account_id,
            secret_key=request.secret_key,
            secret_value=request.secret_value,
        )
        return {"connector": str(connector_id or "").strip().lower(), **result}

    @router.post("/connectors/{connector_id}/disconnect")
    async def disconnect_connector(
        connector_id: str,
        request: ConnectorActionRequest,
        user_id: str = Depends(ctx.require_rate_limit),
    ):
        del user_id
        result = ctx.run_connector_action(
            connector_id,
            "disconnect",
            provider=request.provider,
            account_id=request.account_id,
            secret_key=request.secret_key,
            secret_value=request.secret_value,
        )
        return {"connector": str(connector_id or "").strip().lower(), **result}

    @router.get("/instances/{name}/connectors")
    async def list_instance_connectors(
        name: str,
        user_id: str = Depends(ctx.require_rate_limit),
    ):
        del user_id
        target = (name or "").strip()
        config, _state, _warnings, _state_warnings = ctx.load_normalized_instance_bundle(
            persist_repairs=True
        )
        target_entry = ctx.get_instance_entry(config, target)
        if not isinstance(target_entry, dict):
            raise HTTPException(status_code=404, detail=f"unknown instance: {target}")
        return {"instance": target, "connectors": ctx.workspace_connector_payload(target)}

    @router.post("/instances/{name}/connectors/{connector_id}")
    async def save_instance_connector_binding(
        name: str,
        connector_id: str,
        request: InstanceConnectorBindingRequest,
        user_id: str = Depends(ctx.require_rate_limit),
    ):
        del user_id
        target = (name or "").strip()
        normalized_connector = (connector_id or "").strip().lower()
        config, _state, _warnings, _state_warnings = ctx.load_normalized_instance_bundle(
            persist_repairs=True
        )
        target_entry = ctx.get_instance_entry(config, target)
        if not isinstance(target_entry, dict):
            raise HTTPException(status_code=404, detail=f"unknown instance: {target}")
        error, payload = validate_connector_binding_request(normalized_connector, request)
        if error:
            raise HTTPException(status_code=422, detail=error)
        ctx.save_workspace_connector_binding(
            target,
            normalized_connector,
            payload,
            config_path=ctx.paths.connector_bindings_path,
        )
        return {
            "ok": True,
            "instance": target,
            "connector": normalized_connector,
            "connectors": ctx.workspace_connector_payload(target),
        }

    @router.post("/instances/{name}/start")
    @router.post("/instances/{name}/activate")
    async def activate_instance(
        name: str,
        user_id: str = Depends(ctx.require_rate_limit),
    ):
        del user_id
        target = (name or "").strip()
        raw_config = ctx.load_instances_config()
        config, _warnings = ctx.normalize_instances_config(raw_config)
        names = ctx.instance_names(config)
        if target not in names:
            raise HTTPException(status_code=404, detail=f"unknown instance: {target}")

        config["active_instance"] = target
        ctx.save_instances_config(config)

        raw_state = ctx.load_instance_state(config)
        state, _state_warnings = ctx.normalize_instance_state(
            raw_state,
            valid_names=names,
            active_instance=target,
        )
        ctx.activate_instance_state(state, target)
        ctx.save_instance_state(state)
        return {
            "ok": True,
            "active_instance": target,
            "limits": ctx.instance_limits_payload(config, state),
        }

    @router.post("/instances/{name}/stop")
    async def stop_instance(name: str, user_id: str = Depends(ctx.require_rate_limit)):
        del user_id
        # Desktop: stopping an instance just means it's no longer active
        return {"ok": True, "instance": name, "status": "stopped"}

    @router.delete("/instances/{name}")
    async def delete_instance(
        name: str,
        user_id: str = Depends(ctx.require_rate_limit),
    ):
        del user_id
        target = (name or "").strip()
        raw_config = ctx.load_instances_config()
        config, _warnings = ctx.normalize_instances_config(raw_config)
        items = (
            list(config.get("instances", []))
            if isinstance(config.get("instances"), list)
            else []
        )
        kept = [
            item
            for item in items
            if not (isinstance(item, dict) and str(item.get("name", "")).strip() == target)
        ]
        if len(kept) == len(items):
            raise HTTPException(status_code=404, detail=f"unknown instance: {target}")
        if not kept:
            raise HTTPException(status_code=400, detail="cannot delete the last configured instance")

        config["instances"] = kept
        names = ctx.instance_names(config)
        if str(config.get("active_instance", "")).strip() == target:
            config["active_instance"] = names[0]
        ctx.save_instances_config(config)

        raw_state = ctx.load_instance_state(config)
        state, _state_warnings = ctx.normalize_instance_state(
            raw_state,
            valid_names=names,
            active_instance=str(config.get("active_instance", names[0])),
        )
        instances = state.get("instances", {}) if isinstance(state.get("instances"), dict) else {}
        instances.pop(target, None)
        state["instances"] = instances
        ctx.save_instance_state(state)
        if ctx.instance_logger_available:
            ctx.delete_instance_log(target)
        return {
            "ok": True,
            "deleted": target,
            "active_instance": str(config.get("active_instance", names[0])),
            "limits": ctx.instance_limits_payload(config, state),
        }

    @router.get("/instances/{name}/logs")
    async def get_instance_logs(
        name: str,
        limit: int = 50,
        user_id: str = Depends(ctx.require_rate_limit),
    ):
        del user_id
        target = (name or "").strip()
        raw_config = ctx.load_instances_config()
        config, _warnings = ctx.normalize_instances_config(raw_config)
        if target not in ctx.instance_names(config):
            raise HTTPException(status_code=404, detail=f"unknown instance: {target}")
        return {
            "instance": target,
            "entries": ctx.read_instance_log_tail(target, limit=limit)
            if ctx.instance_logger_available
            else [],
            "summary": ctx.read_instance_log_summary(target)
            if ctx.instance_logger_available
            else {"entry_count": 0, "roles": {}, "statuses": {}},
        }

    @router.post("/instances/{name}/query")
    async def query_instance(
        name: str,
        request: InstanceQueryRequest,
        user_id: str = Depends(ctx.require_rate_limit),
    ):
        del user_id
        target = (name or "").strip()
        if not target:
            raise HTTPException(status_code=400, detail="instance name is required")
        if not owner.GUPPY_CORE_AVAILABLE:
            raise HTTPException(status_code=503, detail="Guppy core not available")

        config, state, _config_warnings, _state_warnings = ctx.load_normalized_instance_bundle(
            persist_repairs=True
        )
        names = ctx.instance_names(config)
        if target not in names:
            raise HTTPException(status_code=404, detail=f"unknown instance: {target}")
        target_entry = ctx.get_instance_entry(config, target) or {}
        target_type = (
            str(target_entry.get("type", "user_instance") or "user_instance").strip()
            or "user_instance"
        )
        source_instance = (request.source_instance or "launcher").strip() or "launcher"
        if source_instance != "launcher":
            if source_instance not in names:
                raise HTTPException(status_code=404, detail=f"unknown source instance: {source_instance}")
            source_entry = ctx.get_instance_entry(config, source_instance) or {}
            source_type = (
                str(source_entry.get("type", "user_instance") or "user_instance").strip()
                or "user_instance"
            )
            allowed, reason, _permissions = ctx.check_instance_tool_permission(
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

        if not ctx.instance_query_lock.acquire(blocking=False):
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

            system_prompt = ctx.build_chat_system_prompt(
                session_id=f"instance-{target}",
                message=query_text,
                mode=mode,
                persona=str(target_entry.get("persona", "guppy") or "guppy").strip() or "guppy",
                model_id="",
            )
            try:
                response = await ctx.run_blocking(
                    ctx.call_unified_inference,
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
                ctx.save_instance_state(state)

            if ctx.instance_logger_available:
                ctx.append_instance_log(
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
                    ctx.append_instance_log(
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
            ctx.instance_query_lock.release()

    return router
