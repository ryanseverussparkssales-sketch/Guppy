"""Workspace governance wrappers for instance capability policy checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

_FALLBACK_INSTANCE_DEFAULTS: dict[str, dict[str, bool]] = {
    "user_instance": {"read": True, "write": True, "execute": True, "network": True},
    "admin_instance": {"read": True, "write": True, "execute": True, "network": True},
    "builder_instance": {"read": True, "write": True, "execute": False, "network": True},
    "read_only_instance": {"read": True, "write": False, "execute": False, "network": True},
}
_BACKEND_READY = False
_BACKEND_AVAILABLE = False
_AUTH_MODE_LABEL: Callable[[str], str]
_CHECK_INSTANCE_TOOL_PERMISSION: Callable[..., tuple[bool, str, dict[str, Any]]]
_REQUIRED_CAPABILITY_FOR_TOOL: Callable[[str], str]
_RESOLVE_INSTANCE_PERMISSIONS: Callable[..., dict[str, Any]]
_SET_INSTANCE_TOOL_PERMISSION_POLICY: Callable[..., Path | None]


def _fallback_auth_mode_label(mode: str) -> str:
    normalized = str(mode or "runtime_default").strip().lower() or "runtime_default"
    aliases = {
        "runtime_default": "runtime default",
        "workspace_token_required": "workspace token required",
        "local_only": "local only",
        "disabled": "disabled",
    }
    return aliases.get(normalized, normalized.replace("_", " ") or "runtime default")


def _fallback_required_capability_for_tool(tool_name: str) -> str:
    normalized = str(tool_name or "").strip().lower()
    if normalized.startswith(("read_", "list_", "get_")) or normalized in {"read_file", "screenshot"}:
        return "read"
    if normalized.startswith(("write_", "save_", "create_", "add_", "update_")):
        return "write"
    if normalized.startswith(("search_", "fetch_", "gmail_", "spotify_", "youtube_", "crm_", "voip_")):
        return "network"
    return "execute"


def _fallback_check_instance_tool_permission(
    tool_name: str,
    *,
    instance_name: str | None = None,
    instance_type: str | None = None,
    config_path=None,
    endpoint: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> tuple[bool, str, dict[str, Any]]:
    del instance_name, config_path, endpoint, metadata
    capability = _fallback_required_capability_for_tool(tool_name)
    permissions = _fallback_resolve_instance_permissions(instance_type=instance_type)
    allowed = bool(permissions.get(capability, False))
    reason = "" if allowed else f"Tool {tool_name} requires {capability} capability."
    permissions["_required_capability"] = capability
    permissions["_policy_reason"] = reason
    return allowed, reason, permissions


def _fallback_resolve_instance_permissions(
    instance_name: str | None = None,
    instance_type: str | None = None,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    del instance_name, config_path
    normalized_type = str(instance_type or "").strip().lower()
    return dict(_FALLBACK_INSTANCE_DEFAULTS.get(normalized_type, _FALLBACK_INSTANCE_DEFAULTS["user_instance"]))


def _fallback_set_instance_tool_permission_policy(
    instance_name: str,
    policy_entry: dict[str, Any],
    *,
    config_path: str | Path | None = None,
) -> Path | None:
    path = Path(config_path) if config_path else Path.cwd() / "tool_permissions.json"
    payload = {
        "version": 1,
        "instances": {
            str(instance_name or "").strip(): {
                key: bool(value)
                for key, value in (policy_entry if isinstance(policy_entry, dict) else {}).items()
                if not str(key).startswith("_")
            }
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _ensure_backend_loaded() -> None:
    global _AUTH_MODE_LABEL
    global _BACKEND_AVAILABLE
    global _BACKEND_READY
    global _CHECK_INSTANCE_TOOL_PERMISSION
    global _REQUIRED_CAPABILITY_FOR_TOOL
    global _RESOLVE_INSTANCE_PERMISSIONS
    global _SET_INSTANCE_TOOL_PERMISSION_POLICY

    if _BACKEND_READY:
        return

    try:
        from utils.instance_capabilities import (
            auth_mode_label,
            check_instance_tool_permission,
            required_capability_for_tool,
            resolve_instance_permissions,
            set_instance_tool_permission_policy,
        )

        _AUTH_MODE_LABEL = auth_mode_label
        _CHECK_INSTANCE_TOOL_PERMISSION = check_instance_tool_permission
        _REQUIRED_CAPABILITY_FOR_TOOL = required_capability_for_tool
        _RESOLVE_INSTANCE_PERMISSIONS = resolve_instance_permissions
        _SET_INSTANCE_TOOL_PERMISSION_POLICY = set_instance_tool_permission_policy
        _BACKEND_AVAILABLE = True
    except Exception:
        _AUTH_MODE_LABEL = _fallback_auth_mode_label
        _CHECK_INSTANCE_TOOL_PERMISSION = _fallback_check_instance_tool_permission
        _REQUIRED_CAPABILITY_FOR_TOOL = _fallback_required_capability_for_tool
        _RESOLVE_INSTANCE_PERMISSIONS = _fallback_resolve_instance_permissions
        _SET_INSTANCE_TOOL_PERMISSION_POLICY = _fallback_set_instance_tool_permission_policy
        _BACKEND_AVAILABLE = False

    _BACKEND_READY = True


def instance_policy_backend_available() -> bool:
    _ensure_backend_loaded()
    return _BACKEND_AVAILABLE


def auth_mode_label(mode: str) -> str:
    _ensure_backend_loaded()
    return _AUTH_MODE_LABEL(mode)


def required_capability_for_tool(tool_name: str) -> str:
    _ensure_backend_loaded()
    return _REQUIRED_CAPABILITY_FOR_TOOL(tool_name)


def check_instance_tool_permission(
    tool_name: str,
    *,
    instance_name: str | None = None,
    instance_type: str | None = None,
    config_path: str | Path | None = None,
    endpoint: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> tuple[bool, str, dict[str, Any]]:
    _ensure_backend_loaded()
    return _CHECK_INSTANCE_TOOL_PERMISSION(
        tool_name,
        instance_name=instance_name,
        instance_type=instance_type,
        config_path=config_path,
        endpoint=endpoint,
        metadata=metadata,
    )


def resolve_instance_permissions(
    instance_name: str | None = None,
    instance_type: str | None = None,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    _ensure_backend_loaded()
    resolved = _RESOLVE_INSTANCE_PERMISSIONS(instance_name, instance_type, config_path=config_path)
    return resolved if isinstance(resolved, dict) else {}


def set_instance_tool_permission_policy(
    instance_name: str,
    policy_entry: dict[str, Any],
    *,
    config_path: str | Path | None = None,
) -> Path | None:
    _ensure_backend_loaded()
    payload = policy_entry if isinstance(policy_entry, dict) else {}
    return _SET_INSTANCE_TOOL_PERMISSION_POLICY(instance_name, payload, config_path=config_path)
