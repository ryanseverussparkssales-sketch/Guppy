from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def bindings_config_path(config_path: str | Path | None) -> Path | None:
    if not config_path:
        return None
    path = Path(config_path)
    return path.with_name("connector_bindings.json")


def coerce_permissions(raw: Any, *, capability_keys: tuple[str, ...]) -> dict[str, bool]:
    data = raw if isinstance(raw, dict) else {}
    return {key: bool(data.get(key, False)) for key in capability_keys}


def normalize_auth_mode(value: Any, *, default_auth_mode: str, auth_mode_labels: dict[str, str]) -> str:
    normalized = str(value or default_auth_mode).strip().lower()
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
    return normalized if normalized in auth_mode_labels else default_auth_mode


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


def coerce_policy_entry(
    raw: Any,
    *,
    capability_keys: tuple[str, ...],
    default_auth_mode: str,
    auth_mode_labels: dict[str, str],
) -> dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    policy = coerce_permissions(data, capability_keys=capability_keys)
    policy["_auth_mode"] = normalize_auth_mode(
        data.get("auth_mode", data.get("_auth_mode")),
        default_auth_mode=default_auth_mode,
        auth_mode_labels=auth_mode_labels,
    )
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


def merge_policy_entry(
    base: dict[str, Any],
    override: dict[str, Any],
    *,
    capability_keys: tuple[str, ...],
    default_auth_mode: str,
    auth_mode_labels: dict[str, str],
) -> dict[str, Any]:
    merged = dict(base)
    for key in capability_keys:
        if key in override:
            merged[key] = bool(override.get(key, False))
    merged["_auth_mode"] = normalize_auth_mode(
        override.get("_auth_mode", merged.get("_auth_mode", default_auth_mode)),
        default_auth_mode=default_auth_mode,
        auth_mode_labels=auth_mode_labels,
    )
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


def _default_policy_payload(
    *,
    capability_keys: tuple[str, ...],
    default_auth_mode: str,
    auth_mode_labels: dict[str, str],
) -> dict[str, Any]:
    return {
        "version": 2,
        "defaults": coerce_policy_entry(
            {
                "read": True,
                "write": False,
                "execute": False,
                "network": True,
                "auth_mode": default_auth_mode,
            },
            capability_keys=capability_keys,
            default_auth_mode=default_auth_mode,
            auth_mode_labels=auth_mode_labels,
        ),
        "instances": {},
    }


def _serialize_policy_entry(
    policy: dict[str, Any],
    *,
    capability_keys: tuple[str, ...],
    default_auth_mode: str,
    auth_mode_labels: dict[str, str],
) -> dict[str, Any]:
    payload = {key: bool(policy.get(key, False)) for key in capability_keys}
    payload["auth_mode"] = normalize_auth_mode(
        policy.get("_auth_mode"),
        default_auth_mode=default_auth_mode,
        auth_mode_labels=auth_mode_labels,
    )
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


def save_tool_permission_policy(
    policy: dict[str, Any],
    *,
    default_policy_path: Path,
    capability_keys: tuple[str, ...],
    default_auth_mode: str,
    auth_mode_labels: dict[str, str],
    config_path: str | Path | None = None,
) -> Path:
    path = Path(config_path) if config_path else default_policy_path
    defaults = coerce_policy_entry(
        policy.get("defaults", {}),
        capability_keys=capability_keys,
        default_auth_mode=default_auth_mode,
        auth_mode_labels=auth_mode_labels,
    )
    instances_raw = policy.get("instances", {}) if isinstance(policy.get("instances"), dict) else {}
    instances = {
        str(name).strip(): _serialize_policy_entry(
            coerce_policy_entry(
                value,
                capability_keys=capability_keys,
                default_auth_mode=default_auth_mode,
                auth_mode_labels=auth_mode_labels,
            ),
            capability_keys=capability_keys,
            default_auth_mode=default_auth_mode,
            auth_mode_labels=auth_mode_labels,
        )
        for name, value in instances_raw.items()
        if str(name).strip()
    }
    payload = {
        "version": max(2, int(policy.get("version", 2) or 2)),
        "defaults": _serialize_policy_entry(
            defaults,
            capability_keys=capability_keys,
            default_auth_mode=default_auth_mode,
            auth_mode_labels=auth_mode_labels,
        ),
        "instances": instances,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    return path


def load_tool_permission_policy(
    *,
    default_policy_path: Path,
    capability_keys: tuple[str, ...],
    default_auth_mode: str,
    auth_mode_labels: dict[str, str],
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(config_path) if config_path else default_policy_path
    if not path.exists():
        return _default_policy_payload(
            capability_keys=capability_keys,
            default_auth_mode=default_auth_mode,
            auth_mode_labels=auth_mode_labels,
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse tool permission policy at %s: %s", path, exc)
        data = {}
    except OSError as exc:
        logger.warning("Failed to read tool permission policy at %s: %s", path, exc)
        data = {}
    defaults = coerce_policy_entry(
        data.get("defaults", {}),
        capability_keys=capability_keys,
        default_auth_mode=default_auth_mode,
        auth_mode_labels=auth_mode_labels,
    )
    instances_raw = data.get("instances", {}) if isinstance(data.get("instances"), dict) else {}
    instances = {
        str(name).strip(): coerce_policy_entry(
            value,
            capability_keys=capability_keys,
            default_auth_mode=default_auth_mode,
            auth_mode_labels=auth_mode_labels,
        )
        for name, value in instances_raw.items()
        if str(name).strip()
    }
    return {
        "version": int(data.get("version", 2) or 2),
        "defaults": defaults,
        "instances": instances,
    }


def resolve_instance_permissions(
    *,
    instance_name: str | None,
    instance_type: str | None,
    config_path: str | Path | None,
    instance_type_defaults: dict[str, dict[str, bool]],
    default_policy_path: Path,
    capability_keys: tuple[str, ...],
    default_auth_mode: str,
    auth_mode_labels: dict[str, str],
) -> dict[str, Any]:
    policy = load_tool_permission_policy(
        default_policy_path=default_policy_path,
        capability_keys=capability_keys,
        default_auth_mode=default_auth_mode,
        auth_mode_labels=auth_mode_labels,
        config_path=config_path,
    )
    permissions = dict(policy.get("defaults", {}))
    normalized_type = str(instance_type or "").strip().lower()
    if normalized_type in instance_type_defaults:
        permissions.update(
            coerce_permissions(instance_type_defaults[normalized_type], capability_keys=capability_keys)
        )
    normalized_name = str(instance_name or "").strip()
    if normalized_name:
        permissions = merge_policy_entry(
            permissions,
            policy.get("instances", {}).get(normalized_name, {}),
            capability_keys=capability_keys,
            default_auth_mode=default_auth_mode,
            auth_mode_labels=auth_mode_labels,
        )
    return permissions
