from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException


def ensure_m2_instance_scaffold(owner: Any) -> None:
    paths = owner._path_config
    paths.config_dir.mkdir(parents=True, exist_ok=True)
    paths.runtime_dir.mkdir(parents=True, exist_ok=True)

    if not paths.instances_path.exists():
        paths.instances_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "active_instance": "guppy-primary",
                    "instances": [
                        {
                            "name": "guppy-primary",
                            "description": "Primary foreground assistant instance",
                            "mode": "auto",
                            "persona": "guppy",
                            "voice": "default",
                            "enabled": True,
                            "type": "user_instance",
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        },
                        {
                            "name": "builder-collab",
                            "description": "Background collaborator instance",
                            "mode": "teaching",
                            "persona": "guppy",
                            "voice": "default",
                            "enabled": False,
                            "type": "builder_instance",
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        },
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    if not paths.instance_state_path.exists():
        paths.instance_state_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "active_instance": "guppy-primary",
                    "instances": {
                        "guppy-primary": {
                            "status": "idle",
                            "last_message": "",
                            "last_updated": None,
                            "message_count": 0,
                            "model_currently_using": "auto",
                        },
                        "builder-collab": {
                            "status": "idle",
                            "last_message": "",
                            "last_updated": None,
                            "message_count": 0,
                            "model_currently_using": "teaching",
                        },
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )


def load_instances_config(owner: Any) -> dict[str, Any]:
    ensure_m2_instance_scaffold(owner)
    try:
        data = json.loads(owner._path_config.instances_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_instance_state(owner: Any, config: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    del config
    ensure_m2_instance_scaffold(owner)
    try:
        data = json.loads(owner._path_config.instance_state_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_instance_state(owner: Any, state: dict[str, Any]) -> None:
    path = owner._path_config.instance_state_path
    path.parent.mkdir(parents=True, exist_ok=True)
    if owner._ATOMIC_JSON_IO:
        if not owner.write_json_atomic(path, state):
            raise OSError(
                f"Failed to write instance state atomically: {path}"
            )
    else:
        path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def save_instances_config(owner: Any, config: dict[str, Any]) -> None:
    path = owner._path_config.instances_path
    path.parent.mkdir(parents=True, exist_ok=True)
    if owner._ATOMIC_JSON_IO:
        if not owner.write_json_atomic(path, config):
            raise OSError(
                f"Failed to write instances config atomically: {path}"
            )
    else:
        path.write_text(json.dumps(config, indent=2), encoding="utf-8")


def load_normalized_instance_bundle(
    owner: Any, *, persist_repairs: bool = False
) -> tuple[dict[str, Any], dict[str, Any], list[str], list[str]]:
    raw_config = load_instances_config(owner)
    config, config_warnings = normalize_instances_config(raw_config)
    if persist_repairs and raw_config != config:
        save_instances_config(owner, config)
        config_warnings = list(config_warnings) + ["persisted normalized instances config"]

    raw_state = load_instance_state(owner, config)
    state, state_warnings = normalize_instance_state(
        raw_state,
        valid_names=instance_names(config),
        active_instance=str(config.get("active_instance", "guppy-primary")),
    )
    if persist_repairs and raw_state != state:
        save_instance_state(owner, state)
        state_warnings = list(state_warnings) + ["persisted normalized instance runtime state"]

    return config, state, config_warnings, state_warnings


def instance_config_entry(
    *,
    name: str,
    description: str = "",
    mode: str = "auto",
    persona: str = "guppy",
    voice: str = "default",
    enabled: bool = True,
    instance_type: str = "user_instance",
    created_at: str | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "mode": mode,
        "persona": persona,
        "voice": voice,
        "enabled": enabled,
        "type": instance_type,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
    }


def default_instance_state(mode: str = "auto") -> dict[str, Any]:
    return {
        "status": "idle",
        "last_message": "",
        "last_updated": None,
        "message_count": 0,
        "model_currently_using": mode,
    }


def instance_names(config: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for item in config.get("instances", []):
        if isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            if name:
                names.append(name)
    return names


def get_instance_entry(config: dict[str, Any], name: str) -> dict[str, Any] | None:
    target = str(name or "").strip()
    for item in config.get("instances", []):
        if isinstance(item, dict) and str(item.get("name", "")).strip() == target:
            return item
    return None


def get_active_instance_context(
    owner: Any,
) -> tuple[str | None, str | None, str | None, str | None]:
    config, _state, _warnings, _state_warnings = load_normalized_instance_bundle(
        owner, persist_repairs=True
    )
    active_name = str(config.get("active_instance", "")).strip()
    entry = get_instance_entry(config, active_name)
    instance_type = (
        str((entry or {}).get("type", "user_instance") or "user_instance").strip()
        or "user_instance"
    )
    persona = str((entry or {}).get("persona", "guppy") or "guppy").strip() or "guppy"
    voice = str((entry or {}).get("voice", "default") or "default").strip() or "default"
    return (active_name or None, instance_type, persona, voice)


def coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def normalize_instances_config(raw: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    version = max(1, coerce_int(raw.get("version", 1), 1))
    raw_instances = raw.get("instances")
    if not isinstance(raw_instances, list):
        warnings.append("instances must be a list; using default instance set")
        raw_instances = []

    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    for idx, entry in enumerate(raw_instances):
        if not isinstance(entry, dict):
            warnings.append(f"instances[{idx}] ignored: expected object")
            continue
        name = str(entry.get("name", "")).strip()
        if not name:
            warnings.append(f"instances[{idx}] ignored: missing name")
            continue
        if name in seen:
            warnings.append(f"instances[{idx}] ignored: duplicate name '{name}'")
            continue
        seen.add(name)
        items.append(
            instance_config_entry(
                name=name,
                description=str(entry.get("description", "")).strip(),
                mode=str(entry.get("mode", "auto") or "auto").strip().lower() or "auto",
                persona=str(entry.get("persona", "guppy") or "guppy").strip() or "guppy",
                voice=str(entry.get("voice", "default") or "default").strip() or "default",
                enabled=bool(entry.get("enabled", True)),
                instance_type=str(entry.get("type", "user_instance") or "user_instance").strip()
                or "user_instance",
                created_at=str(entry.get("created_at", "")).strip() or None,
            )
        )

    if not items:
        warnings.append("no valid instance entries found; restored default primary instance")
        items = [
            instance_config_entry(
                name="guppy-primary",
                description="Primary foreground assistant instance",
                mode="auto",
                persona="guppy",
                voice="default",
                enabled=True,
                instance_type="user_instance",
            )
        ]

    configured_active = str(raw.get("active_instance", "")).strip()
    valid_names = [item["name"] for item in items]
    active_instance = configured_active if configured_active in valid_names else valid_names[0]
    if configured_active and configured_active not in valid_names:
        warnings.append(
            f"active_instance '{configured_active}' not found; using '{active_instance}'"
        )
    elif not configured_active:
        warnings.append(f"active_instance missing; using '{active_instance}'")

    return {
        "version": version,
        "active_instance": active_instance,
        "instances": items,
    }, warnings


def normalize_instance_state(
    raw: dict[str, Any],
    *,
    valid_names: list[str],
    active_instance: str,
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    raw_instances = raw.get("instances")
    if not isinstance(raw_instances, dict):
        warnings.append("state.instances must be an object; rebuilding instance runtime state")
        raw_instances = {}

    normalized_instances: dict[str, dict[str, Any]] = {}
    for key in raw_instances.keys():
        if key not in valid_names:
            warnings.append(f"state instance '{key}' ignored: not present in config")

    allowed_status = {"idle", "busy", "error", "starting", "active", "running"}
    for name in valid_names:
        entry = raw_instances.get(name, {})
        if not isinstance(entry, dict):
            warnings.append(f"state for '{name}' invalid; resetting to defaults")
            entry = {}

        status = str(entry.get("status", "idle") or "idle").strip().lower()
        if status not in allowed_status:
            warnings.append(f"state for '{name}' had invalid status '{status}'; using 'idle'")
            status = "idle"

        message_count = max(0, coerce_int(entry.get("message_count", 0), 0))
        normalized_instances[name] = {
            "status": status,
            "last_message": str(entry.get("last_message", "") or ""),
            "last_updated": entry.get("last_updated"),
            "message_count": message_count,
            "model_currently_using": str(entry.get("model_currently_using", "") or ""),
        }

    active = (
        active_instance
        if active_instance in valid_names
        else (valid_names[0] if valid_names else "guppy-primary")
    )
    active_slots = 0
    for name, item in normalized_instances.items():
        if name == active:
            item["status"] = "active"
            active_slots += 1
            continue
        if item.get("status") in {"active", "running", "busy"}:
            if active_slots < 2:
                if item.get("status") == "active":
                    item["status"] = "running"
                active_slots += 1
            else:
                item["status"] = "idle"
    return {
        "version": 1,
        "active_instance": active,
        "instances": normalized_instances,
    }, warnings


def upsert_instance_config(config: dict[str, Any], payload: Any) -> tuple[dict[str, Any], str]:
    items = (
        list(config.get("instances", []))
        if isinstance(config.get("instances"), list)
        else []
    )
    target = (payload.name or "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="instance name is required")

    existing_idx = -1
    existing_created_at = None
    for idx, item in enumerate(items):
        if isinstance(item, dict) and str(item.get("name", "")).strip() == target:
            existing_idx = idx
            existing_created_at = str(item.get("created_at", "")).strip() or None
            break

    if existing_idx < 0 and len(items) >= 5:
        raise HTTPException(status_code=409, detail="instance limit reached (max 5 configured)")

    entry = instance_config_entry(
        name=target,
        description=(payload.description or "").strip(),
        mode=(payload.mode or "auto").strip().lower() or "auto",
        persona=(payload.persona or "guppy").strip() or "guppy",
        voice=(payload.voice or "default").strip() or "default",
        enabled=bool(payload.enabled),
        instance_type=(payload.type or "user_instance").strip() or "user_instance",
        created_at=existing_created_at,
    )
    action = "updated" if existing_idx >= 0 else "created"
    if existing_idx >= 0:
        items[existing_idx] = entry
    else:
        items.append(entry)
    config["instances"] = items
    if str(config.get("active_instance", "")).strip() not in instance_names(config):
        config["active_instance"] = target
    return config, action


def activate_instance_state(state: dict[str, Any], target: str) -> dict[str, Any]:
    instances = (
        state.get("instances", {})
        if isinstance(state.get("instances"), dict)
        else {}
    )
    current_active = str(state.get("active_instance", "")).strip()
    if current_active and current_active in instances and current_active != target:
        previous = instances.get(current_active)
        if isinstance(previous, dict) and previous.get("status") != "busy":
            previous["status"] = "idle"
    target_entry = instances.get(target)
    if isinstance(target_entry, dict):
        target_entry["status"] = "active"
        target_entry["last_updated"] = datetime.now(timezone.utc).isoformat()
    state["active_instance"] = target
    return state


def instance_limits_payload(config: dict[str, Any], state: dict[str, Any]) -> dict[str, int]:
    config_items = (
        config.get("instances", []) if isinstance(config.get("instances"), list) else []
    )
    configured = len(
        [
            item
            for item in config_items
            if isinstance(item, dict) and str(item.get("name", "")).strip()
        ]
    )
    runtime_items = (
        state.get("instances", {}) if isinstance(state.get("instances"), dict) else {}
    )
    active_runtime = 0
    for item in runtime_items.values():
        if not isinstance(item, dict):
            continue
        status = str(item.get("status", "idle") or "idle").strip().lower()
        if status in {"active", "running", "busy"}:
            active_runtime += 1
    return {
        "configured": configured,
        "max_configured": 5,
        "active_runtime": active_runtime,
        "max_active_runtime": 2,
    }


def governance_summary_payload(owner: Any, instance_name: str, instance_type: str) -> dict[str, Any]:
    permissions = owner.resolve_instance_permissions(instance_name, instance_type)
    return {
        "auth_mode": str(
            permissions.get("_auth_mode", "runtime_default") or "runtime_default"
        ),
        "auth_mode_label": owner.auth_mode_label(
            str(permissions.get("_auth_mode", "runtime_default") or "runtime_default")
        ),
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


def workspace_connector_payload(owner: Any, instance_name: str) -> list[dict[str, Any]]:
    return owner.workspace_connector_inventory(
        instance_name, config_path=owner._path_config.connector_bindings_path
    )


def connector_inventory_payload(owner: Any) -> list[dict[str, Any]]:
    return owner.connector_inventory()
