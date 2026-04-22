from __future__ import annotations

import time
from pathlib import Path

from src.guppy.workspace_governance import resolve_instance_permissions

from .services import fetch_connector_inventory, fetch_workspace_connector_inventory
from .storage_io import read_json_dict


def instances_config_path(config_dir: Path) -> Path:
    return config_dir / "instances.json"


def instance_state_path(runtime_dir: Path) -> Path:
    return runtime_dir / "instance_state.json"


def default_governance_snapshot(instance_type: str) -> dict[str, object]:
    kind = str(instance_type or "user_instance").strip().lower() or "user_instance"
    capabilities = {
        "user_instance": {"read": True, "write": True, "execute": True, "network": True},
        "builder_instance": {"read": True, "write": True, "execute": False, "network": True},
        "read_only_instance": {"read": True, "write": False, "execute": False, "network": False},
        "admin_instance": {"read": True, "write": True, "execute": True, "network": True},
    }.get(kind, {"read": True, "write": True, "execute": True, "network": True})
    return {
        "auth_mode": "runtime_default",
        "tool_allow": [],
        "tool_block": [],
        "endpoint_allow": [],
        "endpoint_block": [],
        "policy_note": "",
        "capabilities": capabilities,
    }


def build_local_instance_snapshot(
    *,
    config_path: Path,
    state_path: Path,
    include_workspace_details: bool = True,
) -> dict[str, object]:
    config = read_json_dict(config_path)
    state = read_json_dict(state_path)
    items: list[dict[str, object]] = []
    warnings: list[str] = []
    raw_items = config.get("instances", []) if isinstance(config, dict) else []
    state_items = state.get("instances", {}) if isinstance(state, dict) else {}
    active = str(
        config.get("active_instance", state.get("active_instance", "guppy-primary"))
        if isinstance(config, dict)
        else "guppy-primary"
    ).strip() or "guppy-primary"

    for item in raw_items if isinstance(raw_items, list) else []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        instance_type = str(item.get("type", "user_instance") or "user_instance")
        runtime = state_items.get(name, {}) if isinstance(state_items, dict) else {}
        governance = default_governance_snapshot(instance_type)
        connectors: list[dict[str, object]] = []
        if include_workspace_details:
            resolved = resolve_instance_permissions(name, instance_type)
            if isinstance(resolved, dict) and resolved:
                governance = {
                    "auth_mode": str(resolved.get("_auth_mode", "runtime_default") or "runtime_default"),
                    "tool_allow": list(resolved.get("_tool_allow", [])),
                    "tool_block": list(resolved.get("_tool_block", [])),
                    "endpoint_allow": list(resolved.get("_endpoint_allow", [])),
                    "endpoint_block": list(resolved.get("_endpoint_block", [])),
                    "policy_note": str(resolved.get("_policy_note", "") or ""),
                    "capabilities": {
                        "read": bool(resolved.get("read", False)),
                        "write": bool(resolved.get("write", False)),
                        "execute": bool(resolved.get("execute", False)),
                        "network": bool(resolved.get("network", False)),
                    },
                }
            connectors = fetch_workspace_connector_inventory(name)
        items.append(
            {
                "name": name,
                "description": str(item.get("description", "")).strip(),
                "mode": str(item.get("mode", "auto") or "auto"),
                "persona": str(item.get("persona", "guppy") or "guppy"),
                "voice": str(item.get("voice", "default") or "default"),
                "type": instance_type,
                "created_at": item.get("created_at"),
                "enabled": bool(item.get("enabled", True)),
                "status": str(runtime.get("status", "idle") or "idle"),
                "last_message": str(runtime.get("last_message", "") or ""),
                "last_updated": runtime.get("last_updated"),
                "message_count": int(runtime.get("message_count", 0) or 0),
                "model_currently_using": str(runtime.get("model_currently_using", item.get("mode", "auto")) or "auto"),
                "governance": governance,
                "connectors": connectors,
            }
        )

    if not items:
        items = [
            {
                "name": "guppy-primary",
                "description": "Primary foreground assistant instance",
                "mode": "auto",
                "persona": "guppy",
                "voice": "default",
                "type": "user_instance",
                "created_at": None,
                "enabled": True,
                "status": "active",
                "last_message": "",
                "last_updated": None,
                "message_count": 0,
                "model_currently_using": "auto",
                "governance": default_governance_snapshot("user_instance"),
                "connectors": fetch_workspace_connector_inventory("guppy-primary") if include_workspace_details else [],
            }
        ]
        active = "guppy-primary"

    active_runtime = sum(
        1 for item in items if str(item.get("status", "idle")).strip().lower() in {"active", "running", "busy"}
    )
    if len(items) >= 5:
        warnings.append("configured instance cap reached (5 / 5)")
    if active_runtime >= 2:
        warnings.append("runtime-active instance cap reached (2 / 2)")
    return {
        "version": int(config.get("version", 1) or 1) if isinstance(config, dict) else 1,
        "active_instance": active,
        "instances": items,
        "limits": {
            "configured": len(items),
            "max_configured": 5,
            "active_runtime": active_runtime,
            "max_active_runtime": 2,
        },
        "warnings": warnings,
    }


def fetch_instance_snapshot(owner, *, force: bool = False) -> dict[str, object]:
    now = time.monotonic()
    if not force and owner._last_instance_snapshot and now < owner._instance_snapshot_expires_at:
        return owner._last_instance_snapshot
    try:
        snapshot = owner._http_json(
            "/instances",
            method="GET",
            timeout=1.2,
            retry_auth_on_401=True,
            auth_retry_reason="instances_list",
        )
    except Exception:
        snapshot = owner._local_instance_snapshot()
    if isinstance(snapshot, dict) and snapshot:
        owner._last_instance_snapshot = snapshot
        owner._instance_snapshot_expires_at = now + max(2.0, owner._instance_snapshot_ttl_s)
    return snapshot


def fetch_connector_inventory_snapshot(owner, *, force: bool = False) -> list[dict[str, object]]:
    now = time.monotonic()
    if not force and owner._last_connector_inventory_snapshot and now < owner._connector_inventory_expires_at:
        return list(owner._last_connector_inventory_snapshot)
    try:
        payload = owner._http_json(
            "/connectors",
            method="GET",
            timeout=1.5,
            retry_auth_on_401=True,
            auth_retry_reason="connectors_list",
        )
        rows = payload.get("connectors", []) if isinstance(payload, dict) else []
        snapshot = [item for item in rows if isinstance(item, dict)]
    except Exception:
        snapshot = [item.raw for item in fetch_connector_inventory()]
    owner._last_connector_inventory_snapshot = list(snapshot)
    owner._connector_inventory_expires_at = now + max(3.0, owner._connector_inventory_ttl_s)
    return snapshot


def load_instance_history_from_logs(
    name: str,
    *,
    instance_logger_available: bool,
    log_reader,
) -> list[dict[str, str]]:
    if not instance_logger_available:
        return []
    history: list[dict[str, str]] = []
    for item in log_reader(name, limit=80):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        message = str(item.get("message", item.get("response", ""))).strip()
        if role in {"user", "assistant"} and message:
            history.append({"role": role, "content": message})
    return history


def load_instance_catalog(owner, snapshot: dict | None = None) -> tuple[list[str], str]:
    current = snapshot if isinstance(snapshot, dict) and snapshot else owner._local_instance_snapshot(
        include_workspace_details=False
    )
    if not isinstance(current, dict) or not current.get("instances"):
        current = owner._fetch_instance_snapshot(force=True)
    active = str(current.get("active_instance", "")).strip()
    names: list[str] = []
    for item in current.get("instances", []) if isinstance(current, dict) else []:
        if not isinstance(item, dict):
            continue
        if not bool(item.get("enabled", True)):
            continue
        name = str(item.get("name", "")).strip()
        if name and name not in names:
            names.append(name)
    if not names:
        names = [active or "guppy-primary"]
    if active not in names:
        active = names[0]
    return names, active
