from __future__ import annotations

import json
import logging
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from utils.connector_manager import (
    connector_action_for_tool,
    connector_id_for_tool,
    connector_status,
    evaluate_workspace_connector_policy,
    log_connector_policy_denial,
)


logger = logging.getLogger(__name__)


_CAPABILITY_KEYS = ("read", "write", "execute", "network")
_DEFAULT_POLICY_PATH = Path(__file__).resolve().parent.parent / "config" / "tool_permissions.json"
_DEFAULT_AUTH_MODE = "runtime_default"

_INSTANCE_TYPE_DEFAULTS: dict[str, dict[str, bool]] = {
    "user_instance": {"read": True, "write": True, "execute": True, "network": True},
    "admin_instance": {"read": True, "write": True, "execute": True, "network": True},
    "builder_instance": {"read": True, "write": True, "execute": False, "network": True},
    "read_only_instance": {"read": True, "write": False, "execute": False, "network": True},
}

_EXPLICIT_TOOL_CAPABILITIES: dict[str, str] = {
    "read_file": "read",
    "list_directory": "read",
    "screenshot": "read",
    "get_screen_info": "read",
    "recall": "read",
    "semantic_recall": "read",
    "get_tasks": "read",
    "get_contacts": "read",
    "get_pipeline_items": "read",
    "get_revenue_dashboard": "read",
    "get_reminders": "read",
    "calendar_events": "network",
    "morning_brief": "read",
    "read_screen_text": "read",
    "debug_console": "read",
    "query_instance": "network",
    "write_file": "write",
    "apply_patch": "write",
    "create_call_report": "write",
    "create_order_note": "write",
    "remember": "write",
    "semantic_remember": "write",
    "forget": "write",
    "add_task": "write",
    "complete_task": "write",
    "save_contact": "write",
    "add_pipeline_item": "write",
    "update_pipeline_item": "write",
    "log_pipeline_activity": "write",
    "remind_me": "write",
    "cancel_reminder": "write",
    "execute_command": "execute",
    "run_python": "execute",
    "open_application": "execute",
    "mouse_move": "execute",
    "mouse_click": "execute",
    "keyboard_type": "execute",
    "keyboard_shortcut": "execute",
    "open_kindle": "execute",
    "search_web": "network",
    "fetch_url": "network",
    "get_news": "network",
    "get_weather": "network",
    "open_gmail": "network",
    "draft_email": "network",
    "send_email": "network",
    "gmail_scan_inbox": "network",
    "list_external_integrations": "network",
    "crm_upsert_contact": "network",
    "crm_create_opportunity": "network",
    "voip_place_call": "network",
    "get_foundation_readiness": "network",
    "spotify_play": "network",
    "spotify_pause": "network",
    "spotify_resume": "network",
    "spotify_next": "network",
    "spotify_prev": "network",
    "spotify_current": "network",
    "spotify_volume": "network",
    "youtube_play": "network",
    "youtube_search": "network",
    "gmail_purge": "network",
    "gmail_purge_label": "network",
    "gmail_purge_sender": "network",
    "gmail_purge_older_than": "network",
    "gmail_empty_trash": "network",
    "gmail_switch_account": "network",
    "gmail_list_accounts": "network",
    "gmail_smart_cleanup": "network",
}

_PREFIX_CAPABILITIES: tuple[tuple[str, str], ...] = (
    ("read_", "read"),
    ("get_", "read"),
    ("list_", "read"),
    ("write_", "write"),
    ("create_", "write"),
    ("save_", "write"),
    ("add_", "write"),
    ("update_", "write"),
    ("cancel_", "write"),
    ("delete_", "write"),
    ("open_", "execute"),
    ("mouse_", "execute"),
    ("keyboard_", "execute"),
    ("search_", "network"),
    ("fetch_", "network"),
    ("spotify_", "network"),
    ("youtube_", "network"),
    ("gmail_", "network"),
    ("crm_", "network"),
    ("voip_", "network"),
)

_AUTH_MODE_LABELS = {
    "runtime_default": "runtime default",
    "workspace_token_required": "workspace token required",
    "local_only": "local only",
    "disabled": "disabled",
}

_LOCAL_ENDPOINT_PREFIXES = (
    "instance://",
    "connector://internal",
    "http://127.0.0.1",
    "https://127.0.0.1",
    "http://localhost",
    "https://localhost",
)


def _bindings_config_path(config_path: str | Path | None) -> Path | None:
    if not config_path:
        return None
    path = Path(config_path)
    return path.with_name("connector_bindings.json")


def _coerce_permissions(raw: Any) -> dict[str, bool]:
    data = raw if isinstance(raw, dict) else {}
    return {key: bool(data.get(key, False)) for key in _CAPABILITY_KEYS}


def _normalize_auth_mode(value: Any) -> str:
    normalized = str(value or _DEFAULT_AUTH_MODE).strip().lower()
    aliases = {
        "default": "runtime_default",
        "inherit": "runtime_default",
        "runtime": "runtime_default",
        "workspace_token": "workspace_token_required",
        "token_required": "workspace_token_required",
        "local": "local_only",
        "off": "disabled",
        "blocked": "disabled",
    }
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in _AUTH_MODE_LABELS else _DEFAULT_AUTH_MODE


def _coerce_name_list(raw: Any) -> list[str]:
    if not isinstance(raw, (list, tuple, set)):
        return []
    seen: set[str] = set()
    ordered: list[str] = []
    for item in raw:
        value = str(item or "").strip().lower()
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _coerce_endpoint_list(raw: Any) -> list[str]:
    if not isinstance(raw, (list, tuple, set)):
        return []
    seen: set[str] = set()
    ordered: list[str] = []
    for item in raw:
        value = str(item or "").strip().lower()
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _coerce_policy_entry(raw: Any) -> dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    policy = _coerce_permissions(data)
    policy["_auth_mode"] = _normalize_auth_mode(data.get("auth_mode", data.get("_auth_mode")))
    policy["_tool_allow"] = _coerce_name_list(
        data.get("tool_allow") or data.get("allow_tools") or data.get("_tool_allow")
    )
    policy["_tool_block"] = _coerce_name_list(
        data.get("tool_block") or data.get("block_tools") or data.get("_tool_block")
    )
    policy["_endpoint_allow"] = _coerce_endpoint_list(
        data.get("endpoint_allow") or data.get("allow_endpoints") or data.get("_endpoint_allow")
    )
    policy["_endpoint_block"] = _coerce_endpoint_list(
        data.get("endpoint_block") or data.get("block_endpoints") or data.get("_endpoint_block")
    )
    policy["_policy_note"] = str(data.get("policy_note", data.get("_policy_note", "")) or "").strip()
    return policy


def _merge_name_lists(base: list[str], override: list[str], *, merge: bool = False) -> list[str]:
    if not merge:
        return list(override) if override else list(base)
    seen: set[str] = set()
    ordered: list[str] = []
    for value in [*base, *override]:
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _merge_policy_entry(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key in _CAPABILITY_KEYS:
        if key in override:
            merged[key] = bool(override.get(key, False))
    merged["_auth_mode"] = _normalize_auth_mode(override.get("_auth_mode", merged.get("_auth_mode", _DEFAULT_AUTH_MODE)))
    merged["_tool_allow"] = _merge_name_lists(
        list(merged.get("_tool_allow", [])),
        list(override.get("_tool_allow", [])),
    )
    merged["_tool_block"] = _merge_name_lists(
        list(merged.get("_tool_block", [])),
        list(override.get("_tool_block", [])),
        merge=True,
    )
    merged["_endpoint_allow"] = _merge_name_lists(
        list(merged.get("_endpoint_allow", [])),
        list(override.get("_endpoint_allow", [])),
    )
    merged["_endpoint_block"] = _merge_name_lists(
        list(merged.get("_endpoint_block", [])),
        list(override.get("_endpoint_block", [])),
        merge=True,
    )
    policy_note = str(override.get("_policy_note", "") or "").strip()
    if policy_note:
        merged["_policy_note"] = policy_note
    return merged


def _default_policy_payload() -> dict[str, Any]:
    return {
        "version": 2,
        "defaults": _coerce_policy_entry(
            {
                "read": True,
                "write": False,
                "execute": False,
                "network": True,
                "auth_mode": _DEFAULT_AUTH_MODE,
            }
        ),
        "instances": {},
    }


def _serialize_policy_entry(policy: dict[str, Any]) -> dict[str, Any]:
    payload = {key: bool(policy.get(key, False)) for key in _CAPABILITY_KEYS}
    payload["auth_mode"] = _normalize_auth_mode(policy.get("_auth_mode"))
    if policy.get("_tool_allow"):
        payload["tool_allow"] = list(policy.get("_tool_allow", []))
    if policy.get("_tool_block"):
        payload["tool_block"] = list(policy.get("_tool_block", []))
    if policy.get("_endpoint_allow"):
        payload["endpoint_allow"] = list(policy.get("_endpoint_allow", []))
    if policy.get("_endpoint_block"):
        payload["endpoint_block"] = list(policy.get("_endpoint_block", []))
    note = str(policy.get("_policy_note", "") or "").strip()
    if note:
        payload["policy_note"] = note
    return payload


def save_tool_permission_policy(policy: dict[str, Any], config_path: str | Path | None = None) -> Path:
    path = Path(config_path) if config_path else _DEFAULT_POLICY_PATH
    defaults = _coerce_policy_entry(policy.get("defaults", {}))
    instances_raw = policy.get("instances", {}) if isinstance(policy.get("instances"), dict) else {}
    instances = {
        str(name).strip(): _serialize_policy_entry(_coerce_policy_entry(value))
        for name, value in instances_raw.items()
        if str(name).strip()
    }
    payload = {
        "version": max(2, int(policy.get("version", 2) or 2)),
        "defaults": _serialize_policy_entry(defaults),
        "instances": instances,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    return path


def set_instance_tool_permission_policy(
    instance_name: str,
    policy_entry: dict[str, Any],
    *,
    config_path: str | Path | None = None,
) -> Path:
    normalized_name = str(instance_name or "").strip()
    if not normalized_name:
        raise ValueError("instance name is required")
    policy = load_tool_permission_policy(config_path)
    instances = dict(policy.get("instances", {}))
    instances[normalized_name] = _coerce_policy_entry(policy_entry)
    policy["instances"] = instances
    return save_tool_permission_policy(policy, config_path=config_path)


def load_tool_permission_policy(config_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(config_path) if config_path else _DEFAULT_POLICY_PATH
    if not path.exists():
        return _default_policy_payload()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse tool permission policy at %s: %s", path, exc)
        data = {}
    except OSError as exc:
        logger.warning("Failed to read tool permission policy at %s: %s", path, exc)
        data = {}
    defaults = _coerce_policy_entry(data.get("defaults", {}))
    instances_raw = data.get("instances", {}) if isinstance(data.get("instances"), dict) else {}
    instances = {
        str(name).strip(): _coerce_policy_entry(value)
        for name, value in instances_raw.items()
        if str(name).strip()
    }
    return {
        "version": int(data.get("version", 2) or 2),
        "defaults": defaults,
        "instances": instances,
    }


def resolve_instance_permissions(
    instance_name: str | None = None,
    instance_type: str | None = None,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    policy = load_tool_permission_policy(config_path)
    permissions = dict(policy.get("defaults", {}))
    normalized_type = str(instance_type or "").strip().lower()
    if normalized_type in _INSTANCE_TYPE_DEFAULTS:
        permissions.update(_coerce_permissions(_INSTANCE_TYPE_DEFAULTS[normalized_type]))
    normalized_name = str(instance_name or "").strip()
    if normalized_name:
        permissions = _merge_policy_entry(permissions, policy.get("instances", {}).get(normalized_name, {}))
    return permissions


def required_capability_for_tool(tool_name: str) -> str:
    normalized = str(tool_name or "").strip().lower()
    if not normalized:
        return "execute"
    explicit = _EXPLICIT_TOOL_CAPABILITIES.get(normalized)
    if explicit:
        return explicit
    for prefix, capability in _PREFIX_CAPABILITIES:
        if normalized.startswith(prefix):
            return capability
    return "execute"


def _normalize_endpoint(endpoint: Any) -> str:
    return str(endpoint or "").strip().lower()


def _inferred_tool_endpoint(tool_name: str, metadata: dict[str, Any]) -> str:
    normalized = str(tool_name or "").strip().lower()
    if not normalized:
        return ""
    if normalized == "query_instance":
        target = str(
            metadata.get("target_instance")
            or metadata.get("instance")
            or metadata.get("endpoint_target")
            or ""
        ).strip().lower()
        return f"instance://{target or 'workspace'}"
    if normalized == "list_external_integrations":
        return "connector://catalog"
    if normalized in {"open_gmail", "draft_email", "send_email"} or normalized.startswith("gmail_"):
        return "connector://gmail"
    if normalized == "calendar_events":
        calendar_id = str(metadata.get("calendar_id", "primary") or "primary").strip().lower()
        return f"connector://calendar/{calendar_id}"
    if normalized.startswith("spotify_"):
        return "connector://spotify"
    if normalized.startswith("youtube_"):
        return "connector://youtube"
    if normalized.startswith("crm_"):
        return "connector://crm"
    if normalized.startswith("voip_"):
        return "connector://voip"
    if normalized == "get_weather":
        return "connector://weather"
    if normalized == "get_news":
        return "connector://news"
    if normalized in {"fetch_url", "search_web"}:
        url = _normalize_endpoint(metadata.get("url"))
        return url or "https://external/*"
    return ""


def _resolved_tool_endpoint(tool_name: str, endpoint: Any, metadata: dict[str, Any]) -> str:
    explicit = _normalize_endpoint(endpoint)
    return explicit or _inferred_tool_endpoint(tool_name, metadata)


def _matches_any(value: str, patterns: list[str]) -> bool:
    target = str(value or "").strip().lower()
    if not target:
        return False
    return any(fnmatch(target, pattern) for pattern in patterns)


def _is_local_endpoint(endpoint: str) -> bool:
    normalized = _normalize_endpoint(endpoint)
    return any(normalized.startswith(prefix) for prefix in _LOCAL_ENDPOINT_PREFIXES)


def auth_mode_label(mode: str) -> str:
    normalized = _normalize_auth_mode(mode)
    return _AUTH_MODE_LABELS.get(normalized, normalized.replace("_", " ").strip() or "runtime default")


def _connector_auth_telemetry(tool_name: str, metadata: dict[str, Any]) -> dict[str, Any]:
    normalized = str(tool_name or "").strip().lower()
    connector_id = connector_id_for_tool(normalized)
    provider = str(metadata.get("provider", "") or "").strip().lower()

    if normalized == "query_instance":
        return {
            "connector": "workspace_bridge",
            "auth_state": "ready",
            "auth_detail": "Cross-workspace query uses local launcher/API auth.",
            "block_on_missing": False,
        }
    if normalized == "list_external_integrations":
        return {
            "connector": "integration_catalog",
            "auth_state": "ready",
            "auth_detail": "Catalog inspection does not require provider auth.",
            "block_on_missing": False,
        }
    if normalized in {"fetch_url", "search_web", "get_news", "get_weather"}:
        return {
            "connector": "web",
            "auth_state": "not_required",
            "auth_detail": "This connector does not require a dedicated workspace credential.",
            "block_on_missing": False,
        }
    if connector_id:
        status = connector_status(connector_id, provider=provider)
        return {
            "connector": str(status.get("id", connector_id) or connector_id),
            "auth_state": str(status.get("auth_state", "unknown") or "unknown"),
            "auth_detail": str(status.get("auth_detail", "") or ""),
            "block_on_missing": str(status.get("auth_state", "missing") or "missing") == "missing",
        }
    return {
        "connector": "workspace_tool",
        "auth_state": "not_required",
        "auth_detail": "No connector-specific auth is required for this workspace tool.",
        "block_on_missing": False,
    }


def check_instance_tool_permission(
    tool_name: str,
    *,
    instance_name: str | None = None,
    instance_type: str | None = None,
    config_path: str | Path | None = None,
    endpoint: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> tuple[bool, str, dict[str, Any]]:
    if not instance_name and not instance_type:
        return True, "", {}

    details = metadata if isinstance(metadata, dict) else {}
    permissions = resolve_instance_permissions(instance_name, instance_type, config_path=config_path)
    required = required_capability_for_tool(tool_name)
    subject = str(instance_name or instance_type or "instance").strip() or "instance"
    normalized_tool = str(tool_name or "").strip().lower()
    resolved_endpoint = _resolved_tool_endpoint(tool_name, endpoint, details)
    auth_mode = _normalize_auth_mode(permissions.get("_auth_mode"))
    tool_allow = list(permissions.get("_tool_allow", []))
    tool_block = list(permissions.get("_tool_block", []))
    endpoint_allow = list(permissions.get("_endpoint_allow", []))
    endpoint_block = list(permissions.get("_endpoint_block", []))
    connector_telemetry = _connector_auth_telemetry(normalized_tool, details)

    permissions = dict(permissions)
    permissions["_required_capability"] = required
    permissions["_resolved_endpoint"] = resolved_endpoint
    permissions["_policy_subject"] = subject
    permissions["_auth_mode_label"] = auth_mode_label(auth_mode)
    permissions["_connector"] = str(connector_telemetry.get("connector", "workspace_tool"))
    permissions["_connector_auth_state"] = str(connector_telemetry.get("auth_state", "unknown"))
    permissions["_connector_auth_detail"] = str(connector_telemetry.get("auth_detail", ""))
    permissions["_policy_reason_code"] = ""
    permissions["_connector_action"] = connector_action_for_tool(normalized_tool)

    if tool_allow and normalized_tool not in tool_allow:
        reason = f"Tool {tool_name} is outside the workspace allow list for {subject}"
        permissions["_policy_reason"] = reason
        permissions["_policy_reason_code"] = "tool_allow_list"
        return False, reason, permissions

    if normalized_tool in tool_block:
        reason = f"Tool {tool_name} is explicitly block-listed for {subject}"
        permissions["_policy_reason"] = reason
        permissions["_policy_reason_code"] = "tool_block_list"
        return False, reason, permissions

    if not permissions.get(required, False):
        reason = f"Tool {tool_name} requires {required} capability for {subject}"
        permissions["_policy_reason"] = reason
        permissions["_policy_reason_code"] = "capability_required"
        return False, reason, permissions

    connector_id = connector_id_for_tool(normalized_tool)
    if connector_id:
        connector_allowed, connector_reason, connector_context = evaluate_workspace_connector_policy(
            normalized_tool,
            subject,
            metadata=details,
            endpoint=resolved_endpoint,
            config_path=_bindings_config_path(config_path),
        )
        binding = connector_context.get("binding", {}) if isinstance(connector_context.get("binding"), dict) else {}
        status = connector_context.get("status", {}) if isinstance(connector_context.get("status"), dict) else {}
        permissions["_connector"] = str(connector_context.get("connector_id", connector_id) or connector_id)
        permissions["_connector_action"] = str(connector_context.get("action_id", permissions.get("_connector_action", "")) or "")
        permissions["_connector_binding_enabled"] = bool(connector_context.get("binding_enabled", False))
        permissions["_connector_binding_inherited"] = bool(connector_context.get("binding_inherited", False))
        permissions["_connector_binding_account"] = str(connector_context.get("account_id", "") or "")
        permissions["_connector_binding_provider"] = str(connector_context.get("provider", "") or "")
        permissions["_connector_binding_action_allow"] = list(binding.get("action_allow", []))
        permissions["_connector_binding_action_block"] = list(binding.get("action_block", []))
        permissions["_connector_binding_endpoint_allow"] = list(binding.get("endpoint_allow", []))
        permissions["_connector_binding_endpoint_block"] = list(binding.get("endpoint_block", []))
        permissions["_connector_binding_note"] = str(binding.get("note", "") or "")
        permissions["_connector_auth_state"] = str(status.get("auth_state", permissions.get("_connector_auth_state", "unknown")) or "unknown")
        permissions["_connector_auth_detail"] = str(status.get("auth_detail", permissions.get("_connector_auth_detail", "")) or "")
        permissions["_connector_auth_source"] = str(status.get("source", "none") or "none")
        if not connector_allowed:
            permissions["_policy_reason"] = connector_reason
            permissions["_policy_reason_code"] = str(connector_context.get("reason_code", "") or "")
            log_connector_policy_denial(
                str(connector_context.get("connector_id", connector_id) or connector_id),
                subject,
                permissions["_policy_reason_code"],
                connector_reason,
            )
            return False, connector_reason, permissions

    if required == "network":
        if bool(connector_telemetry.get("block_on_missing")) and str(connector_telemetry.get("auth_state", "")) == "missing":
            reason = (
                f"{str(connector_telemetry.get('connector', 'connector')).replace('_', ' ')} auth is not ready for {subject}: "
                f"{str(connector_telemetry.get('auth_detail', '') or 'missing credentials')}"
            )
            permissions["_policy_reason"] = reason
            permissions["_policy_reason_code"] = "connector_auth_missing"
            return False, reason, permissions
        if auth_mode == "disabled":
            reason = f"Workspace auth mode is disabled for connector/network tools in {subject}"
            permissions["_policy_reason"] = reason
            permissions["_policy_reason_code"] = "auth_mode_disabled"
            return False, reason, permissions
        if auth_mode == "workspace_token_required" and not bool(details.get("workspace_auth")):
            reason = f"Workspace {subject} requires workspace-managed auth before {tool_name} can run"
            permissions["_policy_reason"] = reason
            permissions["_policy_reason_code"] = "workspace_auth_required"
            return False, reason, permissions
        if auth_mode == "local_only" and resolved_endpoint and not _is_local_endpoint(resolved_endpoint):
            reason = f"Workspace {subject} is local-only for connector/network access; {resolved_endpoint} is outside local scope"
            permissions["_policy_reason"] = reason
            permissions["_policy_reason_code"] = "local_only_scope"
            return False, reason, permissions

    if resolved_endpoint and endpoint_block and _matches_any(resolved_endpoint, endpoint_block):
        reason = f"Endpoint {resolved_endpoint} is blocked by workspace endpoint policy for {subject}"
        permissions["_policy_reason"] = reason
        permissions["_policy_reason_code"] = "endpoint_block"
        return False, reason, permissions

    if resolved_endpoint and endpoint_allow and not _matches_any(resolved_endpoint, endpoint_allow):
        reason = f"Endpoint {resolved_endpoint} is outside the allowed endpoint filters for {subject}"
        permissions["_policy_reason"] = reason
        permissions["_policy_reason_code"] = "endpoint_allow"
        return False, reason, permissions

    permissions["_policy_reason"] = ""
    return True, "", permissions
