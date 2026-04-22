from __future__ import annotations

from typing import Any

from fastapi import HTTPException


def _governance_summary_payload(owner: Any, instance_name: str, instance_type: str) -> dict[str, Any]:
    permissions = owner.resolve_instance_permissions(instance_name, instance_type)
    auth_mode = str(permissions.get("_auth_mode", "runtime_default") or "runtime_default")
    return {
        "auth_mode": auth_mode,
        "auth_mode_label": owner.auth_mode_label(auth_mode),
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


def _workspace_connector_payload(owner: Any, instance_name: str) -> list[dict[str, Any]]:
    return owner.workspace_connector_inventory(
        instance_name,
        config_path=owner._path_config.connector_bindings_path,
    )


def _connector_inventory_payload(owner: Any) -> list[dict[str, Any]]:
    return owner.connector_inventory()


def build_instance_list_response(owner: Any) -> dict[str, Any]:
    config, state, config_warnings, state_warnings = owner._load_normalized_instance_bundle(
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
        instance_type = str(item.get("type", "user_instance") or "user_instance")
        items.append(
            {
                "name": name,
                "description": str(item.get("description", "")),
                "mode": str(item.get("mode", "auto") or "auto"),
                "persona": str(item.get("persona", "guppy") or "guppy"),
                "voice": str(item.get("voice", "default") or "default"),
                "type": instance_type,
                "created_at": item.get("created_at"),
                "enabled": bool(item.get("enabled", True)),
                "status": str(st.get("status", "idle")),
                "last_message": str(st.get("last_message", "")),
                "last_updated": st.get("last_updated"),
                "message_count": int(st.get("message_count", 0) or 0),
                "model_currently_using": str(
                    st.get("model_currently_using", item.get("mode", "auto")) or "auto"
                ),
                "governance": _governance_summary_payload(owner, name, instance_type),
                "connectors": _workspace_connector_payload(owner, name),
            }
        )

    limits = owner._instance_limits_payload(config, state)
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


def create_or_update_instance_response(owner: Any, request: Any) -> dict[str, Any]:
    raw_config = owner._load_instances_config()
    config, _warnings = owner._normalize_instances_config(raw_config)
    config, action = owner._upsert_instance_config(config, request)
    owner._save_instances_config(config)

    names = owner._instance_names(config)
    raw_state = owner._load_instance_state(config)
    state, _state_warnings = owner._normalize_instance_state(
        raw_state,
        valid_names=names,
        active_instance=str(config.get("active_instance", names[0] if names else "guppy-primary")),
    )
    instances = state.get("instances", {}) if isinstance(state.get("instances"), dict) else {}
    request_name = str(request.name).strip()
    mode = (getattr(request, "mode", None) or "auto").strip().lower() or "auto"
    instances[request_name] = owner._default_instance_state(mode)
    state["instances"] = instances
    owner._activate_instance_state(
        state,
        str(config.get("active_instance", names[0] if names else request_name)).strip(),
    )
    owner._save_instance_state(state)
    limits = owner._instance_limits_payload(config, state)

    return {
        "ok": True,
        "action": action,
        "instance": request_name,
        "active_instance": str(config.get("active_instance", "guppy-primary")),
        "limits": limits,
    }


def save_instance_governance_response(owner: Any, name: str, request: Any) -> dict[str, Any]:
    target = (name or "").strip()
    config, _state, _warnings, _state_warnings = owner._load_normalized_instance_bundle(
        persist_repairs=True
    )
    target_entry = owner._get_instance_entry(config, target)
    if not isinstance(target_entry, dict):
        raise HTTPException(status_code=404, detail=f"unknown instance: {target}")
    instance_type = str(target_entry.get("type", "user_instance") or "user_instance").strip() or "user_instance"
    resolved = owner.resolve_instance_permissions(target, instance_type)
    owner.set_instance_tool_permission_policy(
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
        "governance": _governance_summary_payload(owner, target, instance_type),
    }


def list_connectors_response(owner: Any) -> dict[str, Any]:
    return {"connectors": _connector_inventory_payload(owner)}


def run_connector_action_response(owner: Any, connector_id: str, action: str, request: Any) -> dict[str, Any]:
    result = owner.run_connector_action(
        connector_id,
        action,
        provider=request.provider,
        account_id=request.account_id,
        secret_key=request.secret_key,
        secret_value=request.secret_value,
    )
    return {"connector": str(connector_id or "").strip().lower(), **result}


def list_instance_connectors_response(owner: Any, name: str) -> dict[str, Any]:
    target = (name or "").strip()
    config, _state, _warnings, _state_warnings = owner._load_normalized_instance_bundle(
        persist_repairs=True
    )
    target_entry = owner._get_instance_entry(config, target)
    if not isinstance(target_entry, dict):
        raise HTTPException(status_code=404, detail=f"unknown instance: {target}")
    return {
        "instance": target,
        "connectors": _workspace_connector_payload(owner, target),
    }


def save_instance_connector_binding_response(
    owner: Any,
    name: str,
    connector_id: str,
    request: Any,
) -> dict[str, Any]:
    target = (name or "").strip()
    normalized_connector = (connector_id or "").strip().lower()
    config, _state, _warnings, _state_warnings = owner._load_normalized_instance_bundle(
        persist_repairs=True
    )
    target_entry = owner._get_instance_entry(config, target)
    if not isinstance(target_entry, dict):
        raise HTTPException(status_code=404, detail=f"unknown instance: {target}")
    owner.save_workspace_connector_binding(
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
        config_path=owner._path_config.connector_bindings_path,
    )
    return {
        "ok": True,
        "instance": target,
        "connector": normalized_connector,
        "connectors": _workspace_connector_payload(owner, target),
    }


def activate_instance_response(owner: Any, name: str) -> dict[str, Any]:
    target = (name or "").strip()
    raw_config = owner._load_instances_config()
    config, _warnings = owner._normalize_instances_config(raw_config)
    names = owner._instance_names(config)
    if target not in names:
        raise HTTPException(status_code=404, detail=f"unknown instance: {target}")

    config["active_instance"] = target
    owner._save_instances_config(config)

    raw_state = owner._load_instance_state(config)
    state, _state_warnings = owner._normalize_instance_state(
        raw_state,
        valid_names=names,
        active_instance=target,
    )
    owner._activate_instance_state(state, target)
    owner._save_instance_state(state)
    return {
        "ok": True,
        "active_instance": target,
        "limits": owner._instance_limits_payload(config, state),
    }


def delete_instance_response(owner: Any, name: str) -> dict[str, Any]:
    target = (name or "").strip()
    raw_config = owner._load_instances_config()
    config, _warnings = owner._normalize_instances_config(raw_config)
    items = list(config.get("instances", [])) if isinstance(config.get("instances"), list) else []
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
    names = owner._instance_names(config)
    if str(config.get("active_instance", "")).strip() == target:
        config["active_instance"] = names[0]
    owner._save_instances_config(config)

    raw_state = owner._load_instance_state(config)
    state, _state_warnings = owner._normalize_instance_state(
        raw_state,
        valid_names=names,
        active_instance=str(config.get("active_instance", names[0])),
    )
    instances = state.get("instances", {}) if isinstance(state.get("instances"), dict) else {}
    instances.pop(target, None)
    state["instances"] = instances
    owner._save_instance_state(state)
    if owner._INSTANCE_LOGGER_AVAILABLE:
        owner.delete_instance_log(target)
    active_instance = str(config.get("active_instance", names[0]))
    return {
        "ok": True,
        "deleted": target,
        "active_instance": active_instance,
        "limits": owner._instance_limits_payload(config, state),
    }


def build_instance_logs_response(owner: Any, name: str, limit: int = 50) -> dict[str, Any]:
    target = (name or "").strip()
    raw_config = owner._load_instances_config()
    config, _warnings = owner._normalize_instances_config(raw_config)
    if target not in owner._instance_names(config):
        raise HTTPException(status_code=404, detail=f"unknown instance: {target}")
    return {
        "instance": target,
        "entries": owner.read_instance_log_tail(target, limit=limit)
        if owner._INSTANCE_LOGGER_AVAILABLE
        else [],
        "summary": owner.read_instance_log_summary(target)
        if owner._INSTANCE_LOGGER_AVAILABLE
        else {"entry_count": 0, "roles": {}, "statuses": {}},
    }
