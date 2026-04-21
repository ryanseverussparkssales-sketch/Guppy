from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


_DEFAULT_BINDINGS_PATH = Path(__file__).resolve().parent.parent / "config" / "connector_bindings.json"
_BINDING_KEYS = (
    "enabled",
    "account_id",
    "provider",
    "action_allow",
    "action_block",
    "endpoint_allow",
    "endpoint_block",
    "note",
)


def _default_binding() -> dict[str, Any]:
    return {
        "enabled": False,
        "account_id": "",
        "provider": "",
        "action_allow": [],
        "action_block": [],
        "endpoint_allow": [],
        "endpoint_block": [],
        "note": "",
    }


def _coerce_name_list(raw: Any) -> list[str]:
    if not isinstance(raw, (list, tuple, set)):
        return []
    seen: set[str] = set()
    values: list[str] = []
    for item in raw:
        value = str(item or "").strip().lower()
        if not value or value in seen:
            continue
        seen.add(value)
        values.append(value)
    return values


def _coerce_binding(raw: Any) -> dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    binding = _default_binding()
    binding["enabled"] = bool(data.get("enabled", False))
    binding["account_id"] = str(data.get("account_id", "") or "").strip().lower()
    binding["provider"] = str(data.get("provider", "") or "").strip().lower()
    binding["action_allow"] = _coerce_name_list(data.get("action_allow"))
    binding["action_block"] = _coerce_name_list(data.get("action_block"))
    binding["endpoint_allow"] = _coerce_name_list(data.get("endpoint_allow"))
    binding["endpoint_block"] = _coerce_name_list(data.get("endpoint_block"))
    binding["note"] = str(data.get("note", "") or "").strip()
    return binding


def _serialize_binding(binding: dict[str, Any]) -> dict[str, Any]:
    payload = _coerce_binding(binding)
    serialized: dict[str, Any] = {}
    for key in _BINDING_KEYS:
        value = payload.get(key)
        if key == "enabled":
            serialized[key] = bool(value)
            continue
        if value == "" or value == []:
            continue
        serialized[key] = value
    return serialized


def _default_payload() -> dict[str, Any]:
    return {
        "version": 1,
        "workspaces": {},
    }


def load_connector_bindings(config_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(config_path) if config_path else _DEFAULT_BINDINGS_PATH
    if not path.exists():
        return _default_payload()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse connector bindings at %s: %s", path, exc)
        return _default_payload()
    except OSError as exc:
        logger.warning("Failed to read connector bindings at %s: %s", path, exc)
        return _default_payload()
    workspaces_raw = data.get("workspaces", {}) if isinstance(data.get("workspaces"), dict) else {}
    workspaces: dict[str, dict[str, dict[str, Any]]] = {}
    for workspace_name, connectors in workspaces_raw.items():
        normalized_name = str(workspace_name or "").strip()
        if not normalized_name or not isinstance(connectors, dict):
            continue
        normalized_connectors: dict[str, dict[str, Any]] = {}
        for connector_id, binding in connectors.items():
            normalized_id = str(connector_id or "").strip().lower()
            if not normalized_id:
                continue
            normalized_connectors[normalized_id] = _coerce_binding(binding)
        if normalized_connectors:
            workspaces[normalized_name] = normalized_connectors
    return {
        "version": int(data.get("version", 1) or 1),
        "workspaces": workspaces,
    }


def save_connector_bindings(payload: dict[str, Any], config_path: str | Path | None = None) -> Path:
    path = Path(config_path) if config_path else _DEFAULT_BINDINGS_PATH
    raw_workspaces = payload.get("workspaces", {}) if isinstance(payload.get("workspaces"), dict) else {}
    workspaces: dict[str, dict[str, dict[str, Any]]] = {}
    for workspace_name, connectors in raw_workspaces.items():
        normalized_name = str(workspace_name or "").strip()
        if not normalized_name or not isinstance(connectors, dict):
            continue
        normalized_connectors: dict[str, dict[str, Any]] = {}
        for connector_id, binding in connectors.items():
            normalized_id = str(connector_id or "").strip().lower()
            if not normalized_id:
                continue
            normalized_connectors[normalized_id] = _serialize_binding(binding)
        if normalized_connectors:
            workspaces[normalized_name] = normalized_connectors
    output = {
        "version": max(1, int(payload.get("version", 1) or 1)),
        "workspaces": workspaces,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=True, indent=2), encoding="utf-8")
    return path


def resolve_workspace_connector_binding(
    workspace_name: str,
    connector_id: str,
    *,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    normalized_workspace = str(workspace_name or "").strip()
    normalized_connector = str(connector_id or "").strip().lower()
    binding = _default_binding()
    binding["_exists"] = False
    if not normalized_workspace or not normalized_connector:
        return binding
    payload = load_connector_bindings(config_path)
    workspace_payload = payload.get("workspaces", {}).get(normalized_workspace, {})
    if isinstance(workspace_payload, dict) and normalized_connector in workspace_payload:
        binding = _coerce_binding(workspace_payload.get(normalized_connector, {}))
        binding["_exists"] = True
    return binding


def set_workspace_connector_binding(
    workspace_name: str,
    connector_id: str,
    binding: dict[str, Any],
    *,
    config_path: str | Path | None = None,
) -> Path:
    normalized_workspace = str(workspace_name or "").strip()
    normalized_connector = str(connector_id or "").strip().lower()
    if not normalized_workspace:
        raise ValueError("workspace name is required")
    if not normalized_connector:
        raise ValueError("connector id is required")
    payload = load_connector_bindings(config_path)
    workspaces = dict(payload.get("workspaces", {}))
    workspace_payload = dict(workspaces.get(normalized_workspace, {}))
    workspace_payload[normalized_connector] = _coerce_binding(binding)
    workspaces[normalized_workspace] = workspace_payload
    payload["workspaces"] = workspaces
    return save_connector_bindings(payload, config_path=config_path)


def list_workspace_connector_bindings(
    workspace_name: str,
    *,
    config_path: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    normalized_workspace = str(workspace_name or "").strip()
    if not normalized_workspace:
        return {}
    payload = load_connector_bindings(config_path)
    workspace_payload = payload.get("workspaces", {}).get(normalized_workspace, {})
    if not isinstance(workspace_payload, dict):
        return {}
    return {
        str(connector_id): _coerce_binding(binding)
        for connector_id, binding in workspace_payload.items()
        if str(connector_id).strip()
    }
