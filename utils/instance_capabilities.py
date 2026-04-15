from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


_CAPABILITY_KEYS = ("read", "write", "execute", "network")
_DEFAULT_POLICY_PATH = Path(__file__).resolve().parent.parent / "config" / "tool_permissions.json"

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
    "calendar_events": "read",
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


def _coerce_permissions(raw: Any) -> dict[str, bool]:
    data = raw if isinstance(raw, dict) else {}
    return {key: bool(data.get(key, False)) for key in _CAPABILITY_KEYS}


def load_tool_permission_policy(config_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(config_path) if config_path else _DEFAULT_POLICY_PATH
    if not path.exists():
        return {
            "version": 1,
            "defaults": _coerce_permissions({"read": True, "write": False, "execute": False, "network": True}),
            "instances": {},
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse tool permission policy at %s: %s", path, exc)
        data = {}
    except OSError as exc:
        logger.warning("Failed to read tool permission policy at %s: %s", path, exc)
        data = {}
    defaults = _coerce_permissions(data.get("defaults", {}))
    instances_raw = data.get("instances", {}) if isinstance(data.get("instances"), dict) else {}
    instances = {str(name).strip(): _coerce_permissions(value) for name, value in instances_raw.items() if str(name).strip()}
    return {
        "version": int(data.get("version", 1) or 1),
        "defaults": defaults,
        "instances": instances,
    }


def resolve_instance_permissions(
    instance_name: str | None = None,
    instance_type: str | None = None,
    config_path: str | Path | None = None,
) -> dict[str, bool]:
    policy = load_tool_permission_policy(config_path)
    permissions = dict(policy.get("defaults", {}))
    normalized_type = str(instance_type or "").strip().lower()
    if normalized_type in _INSTANCE_TYPE_DEFAULTS:
        permissions.update(_INSTANCE_TYPE_DEFAULTS[normalized_type])
    normalized_name = str(instance_name or "").strip()
    if normalized_name:
        permissions.update(policy.get("instances", {}).get(normalized_name, {}))
    return _coerce_permissions(permissions)


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


def check_instance_tool_permission(
    tool_name: str,
    *,
    instance_name: str | None = None,
    instance_type: str | None = None,
    config_path: str | Path | None = None,
) -> tuple[bool, str, dict[str, bool]]:
    if not instance_name and not instance_type:
        return True, "", {}
    permissions = resolve_instance_permissions(instance_name, instance_type, config_path=config_path)
    required = required_capability_for_tool(tool_name)
    if permissions.get(required, False):
        return True, "", permissions
    subject = str(instance_name or instance_type or "instance").strip() or "instance"
    reason = f"Tool {tool_name} requires {required} capability for {subject}"
    return False, reason, permissions
