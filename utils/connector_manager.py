from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils.connector_bindings import (
    list_workspace_connector_bindings,
    resolve_workspace_connector_binding,
    set_workspace_connector_binding,
)

try:
    from utils import secret_store as _secret_store
    _SECRET_STORE_AVAILABLE = True
except Exception:
    _secret_store = None  # type: ignore[assignment]
    _SECRET_STORE_AVAILABLE = False


_ROOT = Path(__file__).resolve().parent.parent
_RUNTIME_DIR = _ROOT / "runtime"
_CONNECTOR_STATE_PATH = _RUNTIME_DIR / "connector_state.json"
_INTEGRATION_EVENTS_PATH = _RUNTIME_DIR / "integration_events.jsonl"
_KEYRING_PREFIX = "connector_secret:"

_CONNECTOR_IDS = ("gmail", "calendar", "spotify", "youtube", "crm", "voip")

_CONNECTOR_CATALOG: dict[str, dict[str, Any]] = {
    "gmail": {
        "label": "Gmail",
        "category": "communication",
        "auth_kind": "oauth_file_token",
        "actions_supported": ["verify", "connect", "reconnect", "disconnect"],
        "secret_fields": [],
    },
    "calendar": {
        "label": "Calendar",
        "category": "productivity",
        "auth_kind": "oauth_file_token",
        "actions_supported": ["verify", "connect", "reconnect", "disconnect"],
        "secret_fields": [],
    },
    "spotify": {
        "label": "Spotify",
        "category": "media",
        "auth_kind": "oauth_secret",
        "actions_supported": ["verify", "connect", "reconnect", "disconnect"],
        "secret_fields": ["SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET", "SPOTIFY_REDIRECT_URI"],
    },
    "youtube": {
        "label": "YouTube",
        "category": "media",
        "auth_kind": "api_key",
        "actions_supported": ["verify", "connect", "disconnect"],
        "secret_fields": ["YOUTUBE_API_KEY"],
    },
    "crm": {
        "label": "CRM",
        "category": "business",
        "auth_kind": "provider_secret",
        "actions_supported": ["verify", "connect", "disconnect"],
        "secret_fields": [
            "HUBSPOT_API_KEY",
            "SALESFORCE_ACCESS_TOKEN",
            "SALESFORCE_INSTANCE_URL",
            "GOHIGHLEVEL_API_KEY",
            "ZOHO_ACCESS_TOKEN",
        ],
    },
    "voip": {
        "label": "VoIP",
        "category": "business",
        "auth_kind": "provider_secret",
        "actions_supported": ["verify", "connect", "disconnect"],
        "secret_fields": ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"],
    },
}

_CRM_PROVIDER_ENV = {
    "hubspot": ["HUBSPOT_API_KEY"],
    "salesforce": ["SALESFORCE_ACCESS_TOKEN", "SALESFORCE_INSTANCE_URL"],
    "gohighlevel": ["GOHIGHLEVEL_API_KEY"],
    "zoho": ["ZOHO_ACCESS_TOKEN"],
}

_VOIP_PROVIDER_ENV = {
    "twilio": ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"],
    "generic": [],
}

_TOOL_CONNECTOR_MAP = {
    "open_gmail": "gmail",
    "draft_email": "gmail",
    "send_email": "gmail",
    "gmail_scan_inbox": "gmail",
    "calendar_events": "calendar",
    "spotify_play": "spotify",
    "spotify_pause": "spotify",
    "spotify_resume": "spotify",
    "spotify_next": "spotify",
    "spotify_prev": "spotify",
    "spotify_current": "spotify",
    "spotify_volume": "spotify",
    "youtube_play": "youtube",
    "youtube_search": "youtube",
    "crm_upsert_contact": "crm",
    "crm_create_opportunity": "crm",
    "voip_place_call": "voip",
}

_TOOL_ACTION_MAP = {
    "open_gmail": "compose",
    "draft_email": "compose",
    "send_email": "send",
    "gmail_scan_inbox": "scan",
    "gmail_switch_account": "account_admin",
    "gmail_list_accounts": "account_admin",
    "gmail_purge": "cleanup",
    "gmail_purge_label": "cleanup",
    "gmail_purge_sender": "cleanup",
    "gmail_purge_older_than": "cleanup",
    "gmail_empty_trash": "cleanup",
    "gmail_smart_cleanup": "cleanup",
    "calendar_events": "read",
    "spotify_play": "play",
    "spotify_pause": "control",
    "spotify_resume": "control",
    "spotify_next": "control",
    "spotify_prev": "control",
    "spotify_current": "read",
    "spotify_volume": "control",
    "youtube_play": "play",
    "youtube_search": "search",
    "crm_upsert_contact": "contact_write",
    "crm_create_opportunity": "opportunity_write",
    "voip_place_call": "call",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_state() -> dict[str, Any]:
    if not _CONNECTOR_STATE_PATH.exists():
        return {"version": 1, "connectors": {}}
    try:
        return json.loads(_CONNECTOR_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "connectors": {}}


def _save_state(payload: dict[str, Any]) -> None:
    _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    _CONNECTOR_STATE_PATH.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _log_integration_event(event_type: str, payload: dict[str, Any]) -> None:
    _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": _now_iso(),
        "event_type": event_type,
        "payload": payload,
    }
    with _INTEGRATION_EVENTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")


def _keyring_key(secret_key: str) -> str:
    return f"{_KEYRING_PREFIX}{str(secret_key or '').strip()}"


def read_machine_secret(secret_key: str, *, fallback: str | None = None) -> str:
    key = str(secret_key or "").strip()
    default = fallback if fallback is not None else os.environ.get(key, "")
    if not key:
        return str(default or "")
    if _SECRET_STORE_AVAILABLE and _secret_store is not None:
        try:
            value = _secret_store.get_secret(_keyring_key(key), fallback=default)
            return str(value or "")
        except Exception:
            return str(default or "")
    return str(default or "")


def write_machine_secret(secret_key: str, value: str) -> bool:
    key = str(secret_key or "").strip()
    if not key or not _SECRET_STORE_AVAILABLE or _secret_store is None:
        return False
    try:
        return bool(_secret_store.set_secret(_keyring_key(key), str(value or "")))
    except Exception:
        return False


def clear_machine_secret(secret_key: str) -> bool:
    key = str(secret_key or "").strip()
    if not key or not _SECRET_STORE_AVAILABLE or _secret_store is None:
        return False
    try:
        return bool(_secret_store.delete_secret(_keyring_key(key)))
    except Exception:
        return False


def _secret_source(secret_key: str) -> str:
    key = str(secret_key or "").strip()
    if not key:
        return "none"
    env_value = os.environ.get(key, "").strip()
    keyring_value = ""
    if _SECRET_STORE_AVAILABLE and _secret_store is not None:
        try:
            keyring_value = str(_secret_store.get_secret(_keyring_key(key), fallback="") or "").strip()
        except Exception:
            keyring_value = ""
    if env_value and keyring_value:
        return "mixed"
    if keyring_value:
        return "keyring"
    if env_value:
        return "env"
    return "none"


def connector_id_for_tool(tool_name: str) -> str:
    normalized = str(tool_name or "").strip().lower()
    if normalized.startswith("gmail_"):
        return "gmail"
    return _TOOL_CONNECTOR_MAP.get(normalized, "")


def connector_action_for_tool(tool_name: str) -> str:
    normalized = str(tool_name or "").strip().lower()
    return _TOOL_ACTION_MAP.get(normalized, "default")


def _gmail_accounts() -> list[dict[str, str]]:
    try:
        from src.guppy.tools.media import _GMAIL_ACCOUNTS
        return [
            {"id": str(alias), "label": str(email)}
            for alias, (email, _creds) in _GMAIL_ACCOUNTS.items()
            if str(alias).strip()
        ]
    except Exception:
        return [
            {"id": "main", "label": "main"},
            {"id": "sales", "label": "sales"},
            {"id": "personal", "label": "personal"},
        ]


def _token_path_for_gmail_account(account_id: str) -> Path:
    normalized = str(account_id or "").strip().lower() or "main"
    return Path.home() / f".guppy_gmail_token_{normalized}.json"


def _gmail_status() -> dict[str, Any]:
    accounts = _gmail_accounts()
    creds_candidates = [
        os.environ.get("GMAIL_CREDENTIALS_PATH", "").strip(),
        str(Path.home() / "gmail_credentials.json"),
        str(Path.home() / "gmail_credentials_main.json"),
        str(Path.home() / "gmail_credentials_sales.json"),
        str(Path.home() / "gmail_credentials_personal.json"),
    ]
    creds_files = [path for path in creds_candidates if path and Path(path).exists()]
    token_paths = list(Path.home().glob(".guppy_gmail_token*.json"))
    auth_state = "ready" if creds_files and token_paths else "partial" if creds_files else "missing"
    auth_detail = (
        "Gmail credentials and at least one cached account token are present."
        if auth_state == "ready"
        else "Gmail credentials exist, but browser auth has not completed yet."
        if auth_state == "partial"
        else "Gmail credentials file is missing for this host."
    )
    return {
        "auth_state": auth_state,
        "auth_detail": auth_detail,
        "source": "mixed" if creds_files and token_paths else "file" if creds_files else "none",
        "accounts": accounts,
        "providers": [],
        "secret_fields": [],
    }


def _calendar_status() -> dict[str, Any]:
    creds_path = os.environ.get("GOOGLE_CALENDAR_CREDENTIALS_PATH", "").strip() or str(Path.home() / "google_calendar_credentials.json")
    token_path = Path.home() / ".guppy_calendar_token.json"
    creds_exists = Path(creds_path).exists()
    token_exists = token_path.exists()
    auth_state = "ready" if creds_exists and token_exists else "partial" if creds_exists else "missing"
    auth_detail = (
        "Calendar credentials and cached token are present."
        if auth_state == "ready"
        else "Calendar credentials exist, but browser auth has not completed yet."
        if auth_state == "partial"
        else "Calendar credentials file is missing for this host."
    )
    return {
        "auth_state": auth_state,
        "auth_detail": auth_detail,
        "source": "mixed" if creds_exists and token_exists else "file" if creds_exists else "none",
        "accounts": [{"id": "primary", "label": "Primary calendar"}],
        "providers": [],
        "secret_fields": [],
    }


def _spotify_status() -> dict[str, Any]:
    token_path = Path.home() / ".guppy_spotify_token"
    required_keys = ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET")
    present = [key for key in required_keys if read_machine_secret(key).strip()]
    auth_state = "ready" if len(present) == len(required_keys) and token_path.exists() else "partial" if present else "missing"
    source_values = {_secret_source(key) for key in required_keys if read_machine_secret(key).strip()}
    source = next(iter(source_values), "none") if len(source_values) == 1 else "mixed" if source_values else "none"
    if token_path.exists():
        source = "mixed" if source in {"env", "keyring"} else "token_cache" if source == "none" else "mixed"
    return {
        "auth_state": auth_state,
        "auth_detail": (
            "Spotify API credentials and token cache are present."
            if auth_state == "ready"
            else "Spotify credentials exist, but browser auth has not completed yet."
            if auth_state == "partial"
            else "Spotify API credentials are missing."
        ),
        "source": source,
        "accounts": [],
        "providers": [],
        "secret_fields": list(_CONNECTOR_CATALOG["spotify"]["secret_fields"]),
    }


def _youtube_status() -> dict[str, Any]:
    key_present = bool(read_machine_secret("YOUTUBE_API_KEY").strip())
    return {
        "auth_state": "ready" if key_present else "optional",
        "auth_detail": "YouTube API key is configured." if key_present else "YouTube API key is missing; fallback scraping may still work.",
        "source": _secret_source("YOUTUBE_API_KEY"),
        "accounts": [],
        "providers": [],
        "secret_fields": list(_CONNECTOR_CATALOG["youtube"]["secret_fields"]),
    }


def _crm_status(provider: str = "") -> dict[str, Any]:
    try:
        from src.guppy.integrations.crm_voip import SUPPORTED_CRM
        providers = [str(item) for item in SUPPORTED_CRM]
    except Exception:
        providers = list(_CRM_PROVIDER_ENV.keys())
    selected = str(provider or providers[0] if providers else "hubspot").strip().lower()
    required = list(_CRM_PROVIDER_ENV.get(selected, []))
    present = [key for key in required if read_machine_secret(key).strip()]
    auth_state = "ready" if required and len(present) == len(required) else "partial" if present else "missing"
    source_values = {_secret_source(key) for key in required if read_machine_secret(key).strip()}
    source = next(iter(source_values), "none") if len(source_values) == 1 else "mixed" if source_values else "none"
    return {
        "auth_state": auth_state,
        "auth_detail": (
            f"{selected} provider credentials are configured."
            if auth_state == "ready"
            else f"{selected} provider is missing {', '.join(sorted(set(required) - set(present)))}."
            if required
            else f"{selected} provider is not configured."
        ),
        "source": source,
        "accounts": [],
        "providers": [{"id": item, "label": item.title()} for item in providers],
        "secret_fields": list(_CONNECTOR_CATALOG["crm"]["secret_fields"]),
    }


def _voip_status(provider: str = "") -> dict[str, Any]:
    try:
        from src.guppy.integrations.crm_voip import SUPPORTED_VOIP
        providers = [str(item) for item in SUPPORTED_VOIP]
    except Exception:
        providers = list(_VOIP_PROVIDER_ENV.keys())
    selected = str(provider or os.environ.get("VOIP_PROVIDER", providers[0] if providers else "twilio")).strip().lower() or "twilio"
    required = list(_VOIP_PROVIDER_ENV.get(selected, []))
    present = [key for key in required if read_machine_secret(key).strip()]
    auth_state = "ready" if not required or len(present) == len(required) else "partial" if present else "missing"
    source_values = {_secret_source(key) for key in required if read_machine_secret(key).strip()}
    source = next(iter(source_values), "none") if len(source_values) == 1 else "mixed" if source_values else "none"
    return {
        "auth_state": auth_state,
        "auth_detail": (
            f"{selected} provider credentials are configured."
            if auth_state == "ready"
            else f"{selected} provider is missing {', '.join(sorted(set(required) - set(present)))}."
            if required
            else f"{selected} provider does not require dedicated auth secrets."
        ),
        "source": source,
        "accounts": [],
        "providers": [{"id": item, "label": item.title()} for item in providers],
        "secret_fields": list(_CONNECTOR_CATALOG["voip"]["secret_fields"]),
    }


def connector_status(connector_id: str, *, provider: str = "") -> dict[str, Any]:
    normalized = str(connector_id or "").strip().lower()
    spec = _CONNECTOR_CATALOG.get(normalized, {})
    if not spec:
        return {
            "id": normalized,
            "category": "unknown",
            "auth_kind": "unknown",
            "auth_state": "missing",
            "auth_detail": "Unknown connector.",
            "source": "none",
            "accounts": [],
            "providers": [],
            "actions_supported": [],
            "secret_fields": [],
        }
    detail_map = {
        "gmail": _gmail_status,
        "calendar": _calendar_status,
        "spotify": _spotify_status,
        "youtube": _youtube_status,
        "crm": lambda: _crm_status(provider),
        "voip": lambda: _voip_status(provider),
    }
    detail = detail_map.get(normalized, lambda: {})()
    payload = {
        "id": normalized,
        "label": str(spec.get("label", normalized.title())),
        "category": str(spec.get("category", "general")),
        "auth_kind": str(spec.get("auth_kind", "unknown")),
        "auth_state": str(detail.get("auth_state", "missing")),
        "auth_detail": str(detail.get("auth_detail", "")),
        "source": str(detail.get("source", "none")),
        "accounts": list(detail.get("accounts", [])),
        "providers": list(detail.get("providers", [])),
        "actions_supported": list(spec.get("actions_supported", [])),
        "secret_fields": list(detail.get("secret_fields", spec.get("secret_fields", []))),
    }
    _record_auth_state(payload)
    return payload


def _record_auth_state(payload: dict[str, Any]) -> None:
    connector_id = str(payload.get("id", "")).strip().lower()
    if not connector_id:
        return
    state = _load_state()
    connectors = state.get("connectors", {}) if isinstance(state.get("connectors"), dict) else {}
    previous = connectors.get(connector_id, {}) if isinstance(connectors.get(connector_id), dict) else {}
    next_state = str(payload.get("auth_state", "missing"))
    if str(previous.get("auth_state", "")) != next_state:
        _log_integration_event(
            "connector.auth_state_changed",
            {
                "connector": connector_id,
                "from": str(previous.get("auth_state", "unknown")),
                "to": next_state,
                "detail": str(payload.get("auth_detail", "")),
            },
        )
    connectors[connector_id] = {
        **previous,
        "auth_state": next_state,
        "auth_detail": str(payload.get("auth_detail", "")),
        "source": str(payload.get("source", "none")),
        "last_seen_at": _now_iso(),
    }
    state["connectors"] = connectors
    _save_state(state)


def connector_inventory() -> list[dict[str, Any]]:
    state = _load_state()
    rows: list[dict[str, Any]] = []
    for connector_id in _CONNECTOR_IDS:
        item = connector_status(connector_id)
        previous = state.get("connectors", {}).get(connector_id, {}) if isinstance(state.get("connectors"), dict) else {}
        item["last_verified_at"] = str(previous.get("last_verified_at", "") or "")
        item["last_verify_ok"] = bool(previous.get("last_verify_ok", False))
        item["last_action"] = str(previous.get("last_action", "") or "")
        item["last_result"] = str(previous.get("last_result", "") or "")
        rows.append(item)
    return rows


def _effective_binding_enabled(workspace_name: str, binding: dict[str, Any]) -> tuple[bool, bool]:
    if bool(binding.get("_exists", False)):
        return bool(binding.get("enabled", False)), False
    if str(workspace_name or "").strip().lower() == "guppy-primary":
        return True, True
    return False, False


def workspace_connector_inventory(
    workspace_name: str,
    *,
    config_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    workspace = str(workspace_name or "").strip()
    rows: list[dict[str, Any]] = []
    for connector_id in _CONNECTOR_IDS:
        binding = resolve_workspace_connector_binding(workspace, connector_id, config_path=config_path)
        enabled, inherited = _effective_binding_enabled(workspace, binding)
        provider = str(binding.get("provider", "") or "")
        item = connector_status(connector_id, provider=provider)
        item["binding"] = {
            "enabled": enabled,
            "inherited": inherited,
            "account_id": str(binding.get("account_id", "") or ""),
            "provider": provider,
            "action_allow": list(binding.get("action_allow", [])),
            "action_block": list(binding.get("action_block", [])),
            "endpoint_allow": list(binding.get("endpoint_allow", [])),
            "endpoint_block": list(binding.get("endpoint_block", [])),
            "note": str(binding.get("note", "") or ""),
        }
        rows.append(item)
    return rows


def get_workspace_connector_context(
    tool_name: str,
    workspace_name: str,
    *,
    metadata: dict[str, Any] | None = None,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    details = metadata if isinstance(metadata, dict) else {}
    connector_id = connector_id_for_tool(tool_name)
    if not connector_id:
        return {
            "connector_id": "",
            "action_id": "",
            "binding_enabled": True,
            "binding_inherited": True,
            "binding": {},
            "status": {},
            "account_id": "",
            "provider": "",
        }
    binding = resolve_workspace_connector_binding(workspace_name, connector_id, config_path=config_path)
    binding_enabled, inherited = _effective_binding_enabled(workspace_name, binding)
    explicit_account = str(details.get("account") or details.get("account_id") or "").strip().lower()
    explicit_provider = str(details.get("provider") or "").strip().lower()
    account_id = explicit_account or str(binding.get("account_id", "") or "").strip().lower()
    provider = explicit_provider or str(binding.get("provider", "") or "").strip().lower()
    status = connector_status(connector_id, provider=provider)
    return {
        "connector_id": connector_id,
        "action_id": connector_action_for_tool(tool_name),
        "binding_enabled": binding_enabled,
        "binding_inherited": inherited,
        "binding": binding,
        "status": status,
        "account_id": account_id,
        "provider": provider,
    }


def evaluate_workspace_connector_policy(
    tool_name: str,
    workspace_name: str,
    *,
    metadata: dict[str, Any] | None = None,
    endpoint: str = "",
    config_path: str | Path | None = None,
) -> tuple[bool, str, dict[str, Any]]:
    context = get_workspace_connector_context(tool_name, workspace_name, metadata=metadata, config_path=config_path)
    connector_id = str(context.get("connector_id", "") or "")
    if not connector_id:
        return True, "", context

    binding = context.get("binding", {}) if isinstance(context.get("binding"), dict) else {}
    status = context.get("status", {}) if isinstance(context.get("status"), dict) else {}
    action_id = str(context.get("action_id", "default") or "default")
    account_id = str(context.get("account_id", "") or "")
    provider = str(context.get("provider", "") or "")
    normalized_endpoint = str(endpoint or "").strip().lower()
    binding_enabled = bool(context.get("binding_enabled", False))

    if not binding_enabled:
        return False, f"Workspace {workspace_name} is not bound to connector {connector_id}", {
            **context,
            "reason_code": "connector_unbound",
        }

    action_allow = [str(item) for item in binding.get("action_allow", []) if str(item).strip()]
    action_block = [str(item) for item in binding.get("action_block", []) if str(item).strip()]
    if action_allow and action_id not in action_allow:
        return False, f"Connector action {action_id} is outside the workspace action allow list for {connector_id}", {
            **context,
            "reason_code": "connector_action_blocked",
        }
    if action_id in action_block:
        return False, f"Connector action {action_id} is blocked for {connector_id} in workspace {workspace_name}", {
            **context,
            "reason_code": "connector_action_blocked",
        }

    endpoint_block = [str(item) for item in binding.get("endpoint_block", []) if str(item).strip()]
    endpoint_allow = [str(item) for item in binding.get("endpoint_allow", []) if str(item).strip()]
    if normalized_endpoint and endpoint_block and any(normalized_endpoint.startswith(pattern.rstrip("*")) for pattern in endpoint_block):
        return False, f"Connector endpoint {normalized_endpoint} is blocked for {connector_id} in workspace {workspace_name}", {
            **context,
            "reason_code": "endpoint_block",
        }
    if normalized_endpoint and endpoint_allow:
        matches_allow = any(normalized_endpoint.startswith(pattern.rstrip("*")) for pattern in endpoint_allow)
        if not matches_allow:
            return False, f"Connector endpoint {normalized_endpoint} is outside the workspace connector filters for {connector_id}", {
                **context,
                "reason_code": "endpoint_allow",
            }

    available_accounts = {
        str(item.get("id", "")).strip().lower()
        for item in status.get("accounts", [])
        if isinstance(item, dict) and str(item.get("id", "")).strip()
    }
    if account_id and available_accounts and account_id not in available_accounts:
        return False, f"Connector account {account_id} is not available for {connector_id} on this host", {
            **context,
            "reason_code": "connector_account_unavailable",
        }

    available_providers = {
        str(item.get("id", "")).strip().lower()
        for item in status.get("providers", [])
        if isinstance(item, dict) and str(item.get("id", "")).strip()
    }
    if provider and available_providers and provider not in available_providers:
        return False, f"Connector provider {provider} is not configured for {connector_id}", {
            **context,
            "reason_code": "connector_provider_unconfigured",
        }

    auth_state = str(status.get("auth_state", "missing") or "missing")
    if auth_state == "missing":
        return False, f"Connector {connector_id} host auth is not ready: {str(status.get('auth_detail', '') or 'missing credentials')}", {
            **context,
            "reason_code": "connector_host_auth_missing",
        }

    return True, "", {**context, "reason_code": ""}


def _record_action_result(
    connector_id: str,
    action: str,
    *,
    ok: bool,
    summary: str,
) -> None:
    state = _load_state()
    connectors = state.get("connectors", {}) if isinstance(state.get("connectors"), dict) else {}
    previous = connectors.get(connector_id, {}) if isinstance(connectors.get(connector_id), dict) else {}
    next_payload = {
        **previous,
        "last_action": action,
        "last_action_at": _now_iso(),
        "last_result": summary,
        "last_verify_ok": bool(ok) if action == "verify" else bool(previous.get("last_verify_ok", False)),
        "last_verified_at": _now_iso() if action == "verify" else str(previous.get("last_verified_at", "") or ""),
    }
    connectors[connector_id] = next_payload
    state["connectors"] = connectors
    _save_state(state)
    _log_integration_event(
        f"connector.{action}",
        {
            "connector": connector_id,
            "ok": ok,
            "summary": summary,
        },
    )


def run_connector_action(
    connector_id: str,
    action: str,
    *,
    provider: str = "",
    account_id: str = "",
    secret_key: str = "",
    secret_value: str = "",
) -> dict[str, Any]:
    normalized_connector = str(connector_id or "").strip().lower()
    normalized_action = str(action or "").strip().lower()
    summary = ""
    ok = True

    if normalized_action == "verify":
        status = connector_status(normalized_connector, provider=provider)
        summary = f"{status.get('label', normalized_connector)} verify: {status.get('auth_state', 'unknown')} | {status.get('auth_detail', '')}"
        ok = str(status.get("auth_state", "missing")) not in {"missing"}
        _record_action_result(normalized_connector, normalized_action, ok=ok, summary=summary)
        return {"ok": ok, "summary": summary, "status": status}

    if normalized_connector in {"youtube", "crm", "voip"} and normalized_action == "connect":
        if not secret_key or not secret_value:
            ok = False
            summary = f"{normalized_connector} connect requires a secret key and value."
        else:
            stored = write_machine_secret(secret_key, secret_value)
            summary = (
                f"Stored {secret_key} in OS credential storage for {normalized_connector}."
                if stored
                else f"Could not persist {secret_key}; environment fallback remains unchanged."
            )
        _record_action_result(normalized_connector, normalized_action, ok=ok, summary=summary)
        return {"ok": ok, "summary": summary, "status": connector_status(normalized_connector, provider=provider)}

    if normalized_connector in {"youtube", "crm", "voip"} and normalized_action == "disconnect":
        if not secret_key:
            ok = False
            summary = f"{normalized_connector} disconnect requires a secret key to clear."
        else:
            cleared = clear_machine_secret(secret_key)
            env_still_present = bool(os.environ.get(secret_key, "").strip())
            summary = (
                f"Cleared stored {secret_key} for {normalized_connector}."
                if cleared and not env_still_present
                else f"Cleared stored {secret_key} for {normalized_connector}, but an environment value is still present."
                if cleared and env_still_present
                else f"No stored {secret_key} value was cleared for {normalized_connector}."
            )
        _record_action_result(normalized_connector, normalized_action, ok=ok, summary=summary)
        return {"ok": ok, "summary": summary, "status": connector_status(normalized_connector, provider=provider)}

    try:
        if normalized_connector == "gmail":
            from media_tools import gmail_unread_count
            target_account = str(account_id or "main").strip().lower() or "main"
            if normalized_action == "disconnect":
                token_path = _token_path_for_gmail_account(target_account)
                if token_path.exists():
                    token_path.unlink()
                    summary = f"Removed cached Gmail token for account {target_account}."
                else:
                    summary = f"No cached Gmail token found for account {target_account}."
            else:
                if normalized_action == "reconnect":
                    token_path = _token_path_for_gmail_account(target_account)
                    if token_path.exists():
                        token_path.unlink()
                count, err = gmail_unread_count(target_account)
                summary = err or f"Gmail account {target_account} verified with {count} unread message(s)."
                ok = not bool(err and "not found" in err.lower())
        elif normalized_connector == "calendar":
            from media_tools import calendar_events
            token_path = Path.home() / ".guppy_calendar_token.json"
            if normalized_action == "disconnect":
                if token_path.exists():
                    token_path.unlink()
                    summary = "Removed cached Calendar token."
                else:
                    summary = "No cached Calendar token found."
            else:
                if normalized_action == "reconnect" and token_path.exists():
                    token_path.unlink()
                result = calendar_events(days=1, max_results=1, calendar_id="primary")
                summary = result.splitlines()[0] if result else "Calendar connect completed."
                ok = "Error" not in summary
        elif normalized_connector == "spotify":
            from media_tools import spotify_current
            token_path = Path.home() / ".guppy_spotify_token"
            if normalized_action == "disconnect":
                if token_path.exists():
                    token_path.unlink()
                    summary = "Removed cached Spotify token."
                else:
                    summary = "No cached Spotify token found."
            else:
                if normalized_action == "reconnect" and token_path.exists():
                    token_path.unlink()
                result = spotify_current()
                summary = result.splitlines()[0] if result else "Spotify connect completed."
                ok = "requires spotify api" not in summary.lower()
        else:
            ok = False
            summary = f"Action {normalized_action} is not supported for connector {normalized_connector}."
    except Exception as exc:
        ok = False
        summary = f"{normalized_connector} {normalized_action} failed: {exc}"

    _record_action_result(normalized_connector, normalized_action, ok=ok, summary=summary)
    return {"ok": ok, "summary": summary, "status": connector_status(normalized_connector, provider=provider)}


def save_workspace_connector_binding(
    workspace_name: str,
    connector_id: str,
    payload: dict[str, Any],
    *,
    config_path: str | Path | None = None,
) -> Path:
    path = set_workspace_connector_binding(workspace_name, connector_id, payload, config_path=config_path)
    _log_integration_event(
        "workspace.connector_binding_saved",
        {
            "workspace": str(workspace_name or "").strip(),
            "connector": str(connector_id or "").strip().lower(),
            "enabled": bool(payload.get("enabled", False)),
        },
    )
    return path


def workspace_binding_map(
    workspace_name: str,
    *,
    config_path: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    return list_workspace_connector_bindings(workspace_name, config_path=config_path)


def log_connector_policy_denial(
    connector_id: str,
    workspace_name: str,
    reason_code: str,
    reason: str,
) -> None:
    _log_integration_event(
        "connector.policy_denied",
        {
            "connector": str(connector_id or "").strip().lower(),
            "workspace": str(workspace_name or "").strip(),
            "reason_code": str(reason_code or "").strip(),
            "reason": str(reason or "").strip(),
        },
    )
