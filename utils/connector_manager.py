from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

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

try:
    from utils.operational_telemetry import log_operational_event as _log_operational_event
    _OPS_TELEMETRY_AVAILABLE = True
except Exception:
    _OPS_TELEMETRY_AVAILABLE = False

    def _log_operational_event(stream: str, event: str, payload: dict[str, Any], level: str = "info") -> None:
        del stream, event, payload, level
        return


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

_CRM_PROVIDER_META: dict[str, dict[str, Any]] = {
    "hubspot": {
        "label": "HubSpot",
        "scope_label": "contacts + opportunities",
        "endpoint_prefixes": [
            "connector://crm/hubspot",
            "connector://crm/hubspot/contacts",
            "connector://crm/hubspot/opportunities",
        ],
        "actions": ["contact_write", "opportunity_write"],
    },
    "salesforce": {
        "label": "Salesforce",
        "scope_label": "contacts + opportunities",
        "endpoint_prefixes": [
            "connector://crm/salesforce",
            "connector://crm/salesforce/contacts",
            "connector://crm/salesforce/opportunities",
        ],
        "actions": ["contact_write", "opportunity_write"],
    },
    "gohighlevel": {
        "label": "GoHighLevel",
        "scope_label": "contacts + pipelines",
        "endpoint_prefixes": [
            "connector://crm/gohighlevel",
            "connector://crm/gohighlevel/contacts",
            "connector://crm/gohighlevel/opportunities",
        ],
        "actions": ["contact_write", "opportunity_write"],
    },
    "zoho": {
        "label": "Zoho",
        "scope_label": "contacts + deals",
        "endpoint_prefixes": [
            "connector://crm/zoho",
            "connector://crm/zoho/contacts",
            "connector://crm/zoho/opportunities",
        ],
        "actions": ["contact_write", "opportunity_write"],
    },
}

_VOIP_PROVIDER_META: dict[str, dict[str, Any]] = {
    "twilio": {
        "label": "Twilio",
        "scope_label": "outbound calling",
        "endpoint_prefixes": [
            "connector://voip/twilio",
            "connector://voip/twilio/calls",
        ],
        "actions": ["call"],
    },
    "generic": {
        "label": "Generic SIP",
        "scope_label": "manual provider handoff",
        "endpoint_prefixes": [
            "connector://voip/generic",
            "connector://voip/generic/calls",
        ],
        "actions": ["call"],
    },
}

_SECRET_FIELD_META: dict[str, dict[str, Any]] = {
    "HUBSPOT_API_KEY": {
        "label": "Private App Token",
        "placeholder": "pat-...",
        "input_hint": "Paste the HubSpot private app token for this machine.",
        "validation_hint": "HubSpot private app tokens usually start with pat- or use a long legacy API-key value.",
        "kind": "token",
        "masked": True,
    },
    "SALESFORCE_ACCESS_TOKEN": {
        "label": "Access Token",
        "placeholder": "00D...!....",
        "input_hint": "Paste the Salesforce access token issued for this org.",
        "validation_hint": "Use the access token string, not the instance URL.",
        "kind": "token",
        "masked": True,
    },
    "SALESFORCE_INSTANCE_URL": {
        "label": "Instance URL",
        "placeholder": "https://your-domain.my.salesforce.com",
        "input_hint": "Paste the Salesforce org or My Domain base URL.",
        "validation_hint": "Use an https URL that points at the Salesforce org host.",
        "kind": "url",
        "masked": False,
    },
    "GOHIGHLEVEL_API_KEY": {
        "label": "API Key",
        "placeholder": "ghl_...",
        "input_hint": "Paste the GoHighLevel API key.",
        "validation_hint": "Use the raw API key string from the provider dashboard.",
        "kind": "token",
        "masked": True,
    },
    "ZOHO_ACCESS_TOKEN": {
        "label": "Access Token",
        "placeholder": "1000....",
        "input_hint": "Paste the Zoho OAuth access token for this machine.",
        "validation_hint": "Zoho access tokens are long opaque strings and should not be URLs.",
        "kind": "token",
        "masked": True,
    },
    "TWILIO_ACCOUNT_SID": {
        "label": "Account SID",
        "placeholder": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "input_hint": "Paste the Twilio Account SID.",
        "validation_hint": "Twilio Account SIDs start with AC.",
        "kind": "account_id",
        "masked": False,
    },
    "TWILIO_AUTH_TOKEN": {
        "label": "Auth Token",
        "placeholder": "twilio-auth-token",
        "input_hint": "Paste the Twilio auth token paired with the selected Account SID.",
        "validation_hint": "Use the auth token value from the Twilio console, not the Account SID.",
        "kind": "token",
        "masked": True,
    },
    "SPOTIFY_CLIENT_ID": {
        "label": "Client ID",
        "placeholder": "spotify-client-id",
        "input_hint": "Paste the Spotify application client id.",
        "validation_hint": "Use the client id from the Spotify developer app.",
        "kind": "client_id",
        "masked": False,
    },
    "SPOTIFY_CLIENT_SECRET": {
        "label": "Client Secret",
        "placeholder": "spotify-client-secret",
        "input_hint": "Paste the Spotify application client secret.",
        "validation_hint": "Use the client secret from the Spotify developer app.",
        "kind": "token",
        "masked": True,
    },
    "SPOTIFY_REDIRECT_URI": {
        "label": "Redirect URI",
        "placeholder": "http://localhost:8888/callback",
        "input_hint": "Paste the redirect URI registered with Spotify.",
        "validation_hint": "Redirect URIs must be valid http or https URLs.",
        "kind": "url",
        "masked": False,
    },
    "YOUTUBE_API_KEY": {
        "label": "API Key",
        "placeholder": "youtube-api-key",
        "input_hint": "Paste the YouTube Data API key.",
        "validation_hint": "Use the API key string from Google Cloud Console.",
        "kind": "token",
        "masked": True,
    },
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


def _integration_level(event_type: str, payload: dict[str, Any]) -> str:
    normalized_event = str(event_type or "").strip().lower()
    reason_code = str(payload.get("reason_code", "") or "").strip().lower()
    if payload.get("ok") is False or "error" in normalized_event or "failed" in normalized_event:
        return "error"
    if "policy_denied" in normalized_event or reason_code:
        return "warning"
    return "info"


def _new_event_id(prefix: str) -> str:
    normalized = str(prefix or "connector").strip().lower() or "connector"
    return f"{normalized}-{uuid4().hex[:10]}"


def _log_integration_event(event_type: str, payload: dict[str, Any], *, level: str | None = None) -> None:
    _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    ts = _now_iso()
    resolved_level = str(level or _integration_level(event_type, payload)).strip().lower() or "info"
    record = {
        "timestamp": ts,
        "ts": ts,
        "event_type": event_type,
        "event": event_type,
        "level": resolved_level,
        "payload": payload,
    }
    with _INTEGRATION_EVENTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")
    if _OPS_TELEMETRY_AVAILABLE:
        _log_operational_event("integration_events", str(event_type or "event"), payload, level=resolved_level)


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


def _merge_sources(values: list[str]) -> str:
    normalized = [str(value or "").strip().lower() for value in values if str(value or "").strip()]
    unique = sorted(set(normalized))
    if not unique:
        return "none"
    if len(unique) == 1:
        return unique[0]
    return "mixed"


def _secret_status(required_fields: list[str]) -> dict[str, Any]:
    present_fields: list[str] = []
    missing_fields: list[str] = []
    field_sources: dict[str, str] = {}
    for field in required_fields:
        normalized = str(field or "").strip()
        if not normalized:
            continue
        value = read_machine_secret(normalized).strip()
        source = _secret_source(normalized)
        if value:
            present_fields.append(normalized)
        else:
            missing_fields.append(normalized)
        field_sources[normalized] = source
    auth_state = (
        "ready"
        if required_fields and not missing_fields
        else "partial"
        if present_fields
        else "ready"
        if not required_fields
        else "missing"
    )
    return {
        "required_fields": list(required_fields),
        "present_fields": present_fields,
        "missing_fields": missing_fields,
        "field_sources": field_sources,
        "source": _merge_sources([field_sources.get(field, "") for field in present_fields]),
        "auth_state": auth_state,
    }


def _secret_field_meta(secret_key: str) -> dict[str, Any]:
    normalized = str(secret_key or "").strip().upper()
    metadata = _SECRET_FIELD_META.get(normalized, {})
    label = str(metadata.get("label", normalized.replace("_", " ").title()) or normalized.replace("_", " ").title())
    placeholder = str(metadata.get("placeholder", "") or "")
    input_hint = str(metadata.get("input_hint", "") or "")
    validation_hint = str(metadata.get("validation_hint", "") or "")
    return {
        "key": normalized,
        "label": label,
        "placeholder": placeholder,
        "input_hint": input_hint,
        "validation_hint": validation_hint,
        "kind": str(metadata.get("kind", "token") or "token"),
        "masked": bool(metadata.get("masked", True)),
    }


def _validate_secret_value(secret_key: str, value: str) -> tuple[bool, str]:
    normalized = str(secret_key or "").strip().upper()
    cleaned = str(value or "").strip()
    if not normalized:
        return False, "Choose which provider field you want to save first."
    if not cleaned:
        return False, f"{normalized} still needs a value."
    lowered = cleaned.lower()
    if normalized.endswith("_URL"):
        if not (lowered.startswith("https://") or lowered.startswith("http://")):
            return False, f"{normalized} must be an http or https URL."
        if normalized == "SALESFORCE_INSTANCE_URL" and all(token not in lowered for token in ("salesforce.com", "force.com")):
            return False, "Salesforce instance URLs should point at a salesforce.com or force.com host."
        return True, ""
    if normalized == "TWILIO_ACCOUNT_SID":
        if not cleaned.startswith("AC") or len(cleaned) < 12:
            return False, "Twilio Account SID values should start with AC and include the full account id."
        return True, ""
    if normalized == "SALESFORCE_ACCESS_TOKEN" and lowered.startswith("http"):
        return False, "Salesforce access token should be the token string, not a URL."
    if normalized in {"HUBSPOT_API_KEY", "GOHIGHLEVEL_API_KEY", "ZOHO_ACCESS_TOKEN", "YOUTUBE_API_KEY", "SPOTIFY_CLIENT_SECRET", "TWILIO_AUTH_TOKEN"} and len(cleaned) < 8:
        return False, f"{normalized} looks too short. Paste the full provider value."
    if normalized == "SPOTIFY_CLIENT_ID" and len(cleaned) < 8:
        return False, "Spotify client id looks too short."
    return True, ""


def _selected_provider_row(status: dict[str, Any], provider: str = "") -> dict[str, Any]:
    provider_rows = status.get("providers", []) if isinstance(status.get("providers"), list) else []
    selected = str(provider or "").strip().lower()
    if selected:
        return next(
            (
                row
                for row in provider_rows
                if isinstance(row, dict) and str(row.get("id", "")).strip().lower() == selected
            ),
            {},
        )
    return next((row for row in provider_rows if isinstance(row, dict)), {})


def _selected_account_row(status: dict[str, Any], account_id: str = "") -> dict[str, Any]:
    account_rows = status.get("accounts", []) if isinstance(status.get("accounts"), list) else []
    selected = str(account_id or "").strip().lower()
    if selected:
        return next(
            (
                row
                for row in account_rows
                if isinstance(row, dict) and str(row.get("id", "")).strip().lower() == selected
            ),
            {},
        )
    return account_rows[0] if len(account_rows) == 1 and isinstance(account_rows[0], dict) else {}


def _verify_check_summary(checks: list[dict[str, Any]]) -> str:
    rendered: list[str] = []
    for item in checks[:4]:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", item.get("id", "check")) or item.get("id", "check")).strip()
        if not label:
            continue
        rendered.append(f"{label}={'OK' if bool(item.get('passed', False)) else 'MISS'}")
    return ", ".join(rendered)


def _provider_guidance(provider_row: dict[str, Any]) -> dict[str, str]:
    if not isinstance(provider_row, dict):
        return {"result_code": "", "next_step": "", "fix_target": "", "verify_check_summary": ""}
    provider_label = str(provider_row.get("label", provider_row.get("id", "provider")) or provider_row.get("id", "provider")).strip()
    auth_state = str(provider_row.get("auth_state", "missing") or "missing").strip().lower()
    missing_fields = [str(item) for item in provider_row.get("missing_fields", []) if str(item).strip()]
    next_field = provider_row.get("next_field", {}) if isinstance(provider_row.get("next_field"), dict) else {}
    next_label = str(next_field.get("label", next_field.get("key", "")) or next_field.get("key", "")).strip()
    next_hint = str(next_field.get("validation_hint", "") or next_field.get("input_hint", "") or "").strip()
    verify_summary = str(provider_row.get("verify_summary", "") or "").strip()
    verify_checks = [
        item for item in provider_row.get("verify_checks", [])
        if isinstance(item, dict)
    ] if isinstance(provider_row.get("verify_checks"), list) else []
    verify_check_summary = _verify_check_summary(verify_checks)
    if auth_state in {"ready", "optional"}:
        return {
            "result_code": "ready",
            "next_step": f"Machine auth is ready for {provider_label}. Use Workspaces to bind or narrow policy for this provider.",
            "fix_target": "Workspaces > Connector Bindings",
            "verify_check_summary": verify_check_summary,
        }
    if missing_fields:
        next_step = f"App Mgmt: save {next_label or missing_fields[0]} for {provider_label}"
        if next_hint:
            next_step += f" ({next_hint})"
        next_step += ", then run Verify."
        return {
            "result_code": "provider_setup_incomplete",
            "next_step": next_step,
            "fix_target": "App Mgmt > Connector Inventory",
            "verify_check_summary": verify_check_summary,
        }
    if auth_state == "partial":
        next_step = f"App Mgmt: run Verify for {provider_label} to confirm scope and host readiness."
        if verify_summary:
            next_step += f" Current result: {verify_summary}"
        return {
            "result_code": "provider_verify_needed",
            "next_step": next_step,
            "fix_target": "App Mgmt > Connector Inventory",
            "verify_check_summary": verify_check_summary,
        }
    return {
        "result_code": "provider_missing",
        "next_step": f"App Mgmt: choose {provider_label} and start guided setup before you verify or bind it.",
        "fix_target": "App Mgmt > Connector Inventory",
        "verify_check_summary": verify_check_summary,
    }


def _connector_guidance(
    status: dict[str, Any],
    *,
    provider: str = "",
    account_id: str = "",
) -> dict[str, str]:
    if not isinstance(status, dict):
        return {"result_code": "", "next_step": "", "fix_target": ""}
    label = str(status.get("label", status.get("id", "connector")) or status.get("id", "connector")).strip()
    auth_kind = str(status.get("auth_kind", "unknown") or "unknown").strip().lower()
    auth_state = str(status.get("auth_state", "missing") or "missing").strip().lower()
    provider_rows = status.get("providers", []) if isinstance(status.get("providers"), list) else []
    account_rows = status.get("accounts", []) if isinstance(status.get("accounts"), list) else []
    selected_provider = _selected_provider_row(status, provider=provider)
    selected_account = _selected_account_row(status, account_id=account_id)
    if provider_rows:
        if not selected_provider:
            return {
                "result_code": "provider_selection_needed",
                "next_step": f"App Mgmt: choose a {label} provider from the inventory before you save secrets, verify, or bind it.",
                "fix_target": "App Mgmt > Connector Inventory",
            }
        provider_guidance = _provider_guidance(selected_provider)
        return {
            "result_code": str(provider_guidance.get("result_code", "") or ""),
            "next_step": str(provider_guidance.get("next_step", "") or ""),
            "fix_target": str(provider_guidance.get("fix_target", "") or ""),
        }
    if account_rows and not selected_account and len(account_rows) > 1:
        return {
            "result_code": "account_selection_needed",
            "next_step": f"App Mgmt: choose which {label} account you want to verify or bind before continuing.",
            "fix_target": "App Mgmt > Connector Inventory",
        }
    if auth_state in {"ready", "optional"}:
        target_label = str(selected_account.get("label", label) or label).strip()
        return {
            "result_code": "ready",
            "next_step": f"Machine auth is ready for {target_label}. Use Workspaces to bind access or narrow workspace policy.",
            "fix_target": "Workspaces > Connector Bindings",
        }
    if auth_kind == "oauth_file_token":
        return {
            "result_code": "host_auth_incomplete",
            "next_step": (
                f"App Mgmt: reconnect {label} to finish browser auth, then run Verify."
                if auth_state == "partial"
                else f"App Mgmt: connect {label} on this machine, then run Verify."
            ),
            "fix_target": "App Mgmt > Connector Inventory",
        }
    secret_fields = [str(item) for item in status.get("secret_fields", []) if str(item).strip()]
    next_field_label = str(_secret_field_meta(secret_fields[0]).get("label", secret_fields[0]) if secret_fields else "required secret").strip()
    if auth_kind in {"provider_secret", "api_key", "oauth_secret"} and secret_fields:
        return {
            "result_code": "host_secret_missing" if auth_state == "missing" else "host_secret_incomplete",
            "next_step": (
                f"App Mgmt: save {next_field_label} for {label}, then run Verify."
                if auth_state != "optional"
                else f"Optional: save {next_field_label} for {label} to improve readiness and quota stability."
            ),
            "fix_target": "App Mgmt > Connector Inventory",
        }
    return {
        "result_code": "host_auth_missing",
        "next_step": f"App Mgmt: repair machine auth for {label}, then rerun Verify.",
        "fix_target": "App Mgmt > Connector Inventory",
    }


def _history_timeline(recent_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    for item in recent_events[-5:]:
        if not isinstance(item, dict):
            continue
        timeline.append(
            {
                "event_id": str(item.get("event_id", "") or "").strip(),
                "integration_event": str(item.get("integration_event", "") or "").strip(),
                "action": str(item.get("action", "") or "").strip(),
                "provider": str(item.get("provider", "") or "").strip(),
                "account_id": str(item.get("account_id", "") or "").strip(),
                "ok": bool(item.get("ok", False)),
                "summary": str(item.get("summary", "") or "").strip(),
                "at": str(item.get("at", "") or "").strip(),
                "result_code": str(item.get("result_code", "") or "").strip(),
                "next_step": str(item.get("next_step", "") or "").strip(),
                "fix_target": str(item.get("fix_target", "") or "").strip(),
            }
        )
    return timeline


def _history_payload(connector_id: str) -> dict[str, Any]:
    state = _load_state()
    rows = state.get("connectors", {}) if isinstance(state.get("connectors"), dict) else {}
    previous = rows.get(str(connector_id or "").strip().lower(), {})
    if not isinstance(previous, dict):
        previous = {}
    recent_events = previous.get("recent_events", [])
    if not isinstance(recent_events, list):
        recent_events = []
    last_action_record = previous.get("last_action_record", {})
    if not isinstance(last_action_record, dict):
        last_action_record = {}
    last_verify_record = previous.get("last_verify_record", {})
    if not isinstance(last_verify_record, dict):
        last_verify_record = {}
    recent_rows = [item for item in recent_events if isinstance(item, dict)][-5:]
    timeline = _history_timeline(recent_rows)
    recent_summary = " | ".join(
        f"{str(item.get('action', 'action') or 'action')}={'OK' if bool(item.get('ok', False)) else 'FAIL'}"
        + (f" ref={str(item.get('event_id', '') or '').strip()}" if str(item.get("event_id", "") or "").strip() else "")
        for item in timeline[-3:]
    )
    return {
        "last_verified_at": str(previous.get("last_verified_at", "") or ""),
        "last_verify_ok": bool(previous.get("last_verify_ok", False)),
        "last_verify_summary": str(previous.get("last_verify_summary", "") or ""),
        "last_verify_event_id": str(previous.get("last_verify_event_id", "") or ""),
        "last_action": str(previous.get("last_action", "") or ""),
        "last_action_at": str(previous.get("last_action_at", "") or ""),
        "last_action_ok": bool(previous.get("last_action_ok", False)),
        "last_result": str(previous.get("last_result", "") or ""),
        "last_event_id": str(previous.get("last_event_id", "") or ""),
        "last_action_record": last_action_record,
        "last_verify_record": last_verify_record,
        "recent_events": recent_rows,
        "timeline": timeline,
        "recent_summary": recent_summary,
    }


def _account_history_ready(connector_id: str, account_id: str) -> dict[str, Any]:
    normalized_connector = str(connector_id or "").strip().lower()
    normalized_account = str(account_id or "").strip().lower()
    if normalized_connector == "gmail":
        token_path = _token_path_for_gmail_account(normalized_account)
        token_exists = token_path.exists()
        return {
            "available": token_exists,
            "auth_state": "ready" if token_exists else "missing",
            "auth_detail": (
                f"Cached browser token is present for Gmail account {normalized_account}."
                if token_exists
                else f"No cached browser token was found yet for Gmail account {normalized_account}."
            ),
            "source": "token_cache" if token_exists else "none",
        }
    return {
        "available": True,
        "auth_state": "ready",
        "auth_detail": "",
        "source": "none",
    }


def _provider_row(
    connector_id: str,
    provider_id: str,
    *,
    required_fields: list[str],
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = meta if isinstance(meta, dict) else {}
    secret_status = _secret_status(required_fields)
    verify_payload: dict[str, Any] = {}
    if connector_id in {"crm", "voip"}:
        try:
            from src.guppy.integrations.crm_voip import verify_connector_provider
            candidate = verify_connector_provider(connector_id, provider_id)
            verify_payload = candidate if isinstance(candidate, dict) else {}
        except Exception:
            verify_payload = {}
    provider_label = str(metadata.get("label", provider_id.title()) or provider_id.title())
    scope_label = str(metadata.get("scope_label", "") or "").strip()
    endpoint_prefixes = [str(item) for item in metadata.get("endpoint_prefixes", []) if str(item).strip()]
    actions = [str(item) for item in metadata.get("actions", []) if str(item).strip()]
    auth_state = str(secret_status.get("auth_state", "missing") or "missing")
    verified_auth_state = str(verify_payload.get("auth_state", "") or "").strip().lower()
    if verified_auth_state in {"ready", "partial", "missing", "optional"}:
        auth_state = verified_auth_state
    missing_fields = list(secret_status.get("missing_fields", []))
    present_fields = list(secret_status.get("present_fields", []))
    field_sources = dict(secret_status.get("field_sources", {}))
    field_details: list[dict[str, Any]] = []
    for idx, field in enumerate(required_fields, start=1):
        detail = _secret_field_meta(field)
        detail.update(
            {
                "present": field in present_fields,
                "missing": field in missing_fields,
                "source": str(field_sources.get(field, "none") or "none"),
                "step": idx,
                "total_steps": len(required_fields),
            }
        )
        field_details.append(detail)
    next_field = next((item for item in field_details if bool(item.get("missing"))), field_details[0] if field_details else {})
    setup_state = (
        "complete"
        if required_fields and not missing_fields
        else "in_progress"
        if present_fields
        else "missing"
        if required_fields
        else "not_required"
    )
    if field_details and next_field:
        next_label = str(next_field.get("label", next_field.get("key", "")) or next_field.get("key", "")).strip()
        setup_summary = (
            f"All required fields are present. Run verify to confirm {provider_label} readiness."
            if not missing_fields
            else f"Step {int(next_field.get('step', 1) or 1)}/{len(field_details)}: add {next_label}."
        )
    else:
        setup_summary = f"{provider_label} does not require stored secrets in this flow."
    auth_detail = (
        f"{provider_label} is ready for {scope_label}."
        if auth_state == "ready" and scope_label
        else f"{provider_label} provider credentials are configured."
        if auth_state == "ready"
        else f"{provider_label} still needs {', '.join(missing_fields)}."
        if missing_fields
        else f"{provider_label} provider is not configured yet."
    )
    verify_summary = str(verify_payload.get("summary", "") or "").strip()
    verify_checks = [
        item for item in verify_payload.get("checks", [])
        if isinstance(item, dict)
    ] if isinstance(verify_payload.get("checks"), list) else []
    scope_detail = str(verify_payload.get("scope_detail", "") or "").strip()
    payload = {
        "id": str(provider_id or "").strip().lower(),
        "label": provider_label,
        "ready": auth_state in {"ready", "optional"},
        "auth_state": auth_state,
        "auth_detail": auth_detail,
        "required_fields": list(secret_status.get("required_fields", [])),
        "present_fields": present_fields,
        "missing_fields": missing_fields,
        "field_sources": field_sources,
        "field_details": field_details,
        "setup_state": setup_state,
        "setup_summary": setup_summary,
        "next_field": next_field,
        "verify_summary": verify_summary,
        "verify_checks": verify_checks,
        "scope_detail": scope_detail,
        "source": str(secret_status.get("source", "none") or "none"),
        "scope_label": scope_label,
        "endpoint_prefixes": endpoint_prefixes,
        "actions": actions,
        "connector": connector_id,
    }
    payload.update(_provider_guidance(payload))
    return payload


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
    account_rows: list[dict[str, Any]] = []
    for item in accounts:
        account_id = str(item.get("id", "")).strip().lower()
        status = _account_history_ready("gmail", account_id)
        account_rows.append(
            {
                "id": account_id,
                "label": str(item.get("label", account_id) or account_id),
                **status,
                "endpoint_prefixes": [f"connector://gmail/{account_id}", "connector://gmail"],
                "actions": ["compose", "send", "scan", "cleanup"],
            }
        )
    return {
        "auth_state": auth_state,
        "auth_detail": auth_detail,
        "source": "mixed" if creds_files and token_paths else "file" if creds_files else "none",
        "accounts": account_rows,
        "providers": [],
        "secret_fields": [],
        "scope_telemetry": {
            "endpoint_prefixes": ["connector://gmail", "connector://gmail/inbox", "connector://gmail/labels"],
            "action_ids": ["compose", "send", "scan", "cleanup", "account_admin"],
            "summary": "Workspace bindings can pin a Gmail account and narrow allowed mail actions.",
        },
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
        "accounts": [
            {
                "id": "primary",
                "label": "Primary calendar",
                "available": token_exists or creds_exists,
                "auth_state": auth_state,
                "auth_detail": auth_detail,
                "source": "token_cache" if token_exists else "file" if creds_exists else "none",
                "endpoint_prefixes": ["connector://calendar/primary", "connector://calendar"],
                "actions": ["read"],
            }
        ],
        "providers": [],
        "secret_fields": [],
        "scope_telemetry": {
            "endpoint_prefixes": ["connector://calendar", "connector://calendar/primary"],
            "action_ids": ["read"],
            "summary": "Calendar bindings currently scope reads to the selected calendar surface.",
        },
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
        "scope_telemetry": {
            "endpoint_prefixes": ["connector://spotify", "connector://spotify/player"],
            "action_ids": ["read", "play", "control"],
            "summary": "Spotify bindings control read/playback actions against the machine-authenticated player.",
        },
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
        "scope_telemetry": {
            "endpoint_prefixes": ["connector://youtube", "connector://youtube/search", "connector://youtube/play"],
            "action_ids": ["search", "play"],
            "summary": "YouTube can work in fallback mode, but an API key improves quota stability and predictable search access.",
        },
    }


def _crm_status(provider: str = "") -> dict[str, Any]:
    try:
        from src.guppy.integrations.crm_voip import SUPPORTED_CRM
        providers = [str(item) for item in SUPPORTED_CRM]
    except Exception:
        providers = list(_CRM_PROVIDER_ENV.keys())
    provider_rows = [
        _provider_row(
            "crm",
            item,
            required_fields=list(_CRM_PROVIDER_ENV.get(item, [])),
            meta=_CRM_PROVIDER_META.get(item, {}),
        )
        for item in providers
    ]
    selected = str(provider or "").strip().lower()
    selected_row = next((row for row in provider_rows if str(row.get("id", "")) == selected), provider_rows[0] if provider_rows else {})
    ready_rows = [row for row in provider_rows if bool(row.get("ready", False))]
    partial_rows = [row for row in provider_rows if str(row.get("auth_state", "")) == "partial"]
    auth_state = (
        str(selected_row.get("auth_state", "missing") or "missing")
        if selected_row
        else "ready"
        if ready_rows
        else "partial"
        if partial_rows
        else "missing"
    )
    source = (
        str(selected_row.get("source", "none") or "none")
        if selected_row
        else _merge_sources([str(row.get("source", "")) for row in ready_rows])
    )
    selected_label = str(selected_row.get("label", "") or "").strip()
    return {
        "auth_state": auth_state,
        "auth_detail": (
            f"{selected_label} provider credentials are configured."
            if selected_row and auth_state == "ready"
            else str(selected_row.get("auth_detail", "Select a CRM provider to inspect readiness."))
            if selected_row
            else f"{len(ready_rows)} CRM provider(s) are ready on this machine."
            if ready_rows
            else "No CRM providers are fully configured on this machine yet."
        ),
        "source": source,
        "accounts": [],
        "providers": provider_rows,
        "secret_fields": list(_CONNECTOR_CATALOG["crm"]["secret_fields"]),
        "scope_telemetry": {
            "endpoint_prefixes": [prefix for row in provider_rows for prefix in row.get("endpoint_prefixes", [])],
            "action_ids": ["contact_write", "opportunity_write"],
            "summary": "CRM bindings can pin a provider and narrow contact/opportunity actions plus endpoint scope.",
        },
    }


def _voip_status(provider: str = "") -> dict[str, Any]:
    try:
        from src.guppy.integrations.crm_voip import SUPPORTED_VOIP
        providers = [str(item) for item in SUPPORTED_VOIP]
    except Exception:
        providers = list(_VOIP_PROVIDER_ENV.keys())
    selected = str(provider or os.environ.get("VOIP_PROVIDER", providers[0] if providers else "twilio")).strip().lower() or "twilio"
    provider_rows = [
        _provider_row(
            "voip",
            item,
            required_fields=list(_VOIP_PROVIDER_ENV.get(item, [])),
            meta=_VOIP_PROVIDER_META.get(item, {}),
        )
        for item in providers
    ]
    selected_row = next((row for row in provider_rows if str(row.get("id", "")) == selected), provider_rows[0] if provider_rows else {})
    ready_rows = [row for row in provider_rows if bool(row.get("ready", False))]
    partial_rows = [row for row in provider_rows if str(row.get("auth_state", "")) == "partial"]
    auth_state = (
        str(selected_row.get("auth_state", "missing") or "missing")
        if selected_row
        else "ready"
        if ready_rows
        else "partial"
        if partial_rows
        else "missing"
    )
    source = (
        str(selected_row.get("source", "none") or "none")
        if selected_row
        else _merge_sources([str(row.get("source", "")) for row in ready_rows])
    )
    return {
        "auth_state": auth_state,
        "auth_detail": (
            str(selected_row.get("auth_detail", "Select a VoIP provider to inspect readiness."))
            if selected_row
            else f"{len(ready_rows)} VoIP provider(s) are ready on this machine."
            if ready_rows
            else "No VoIP providers are fully configured on this machine yet."
        ),
        "source": source,
        "accounts": [],
        "providers": provider_rows,
        "secret_fields": list(_CONNECTOR_CATALOG["voip"]["secret_fields"]),
        "scope_telemetry": {
            "endpoint_prefixes": [prefix for row in provider_rows for prefix in row.get("endpoint_prefixes", [])],
            "action_ids": ["call"],
            "summary": "VoIP bindings can pin a calling provider and restrict call endpoint scope.",
        },
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
            "scope_telemetry": {"endpoint_prefixes": [], "action_ids": [], "summary": ""},
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
        "scope_telemetry": dict(detail.get("scope_telemetry", {})),
    }
    payload.update(_connector_guidance(payload, provider=provider))
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
    rows: list[dict[str, Any]] = []
    for connector_id in _CONNECTOR_IDS:
        item = connector_status(connector_id)
        history = _history_payload(connector_id)
        item["history"] = history
        item.update(history)
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
        history = _history_payload(connector_id)
        selected_account = str(binding.get("account_id", "") or "").strip().lower()
        available_accounts = {
            str(account.get("id", "")).strip().lower()
            for account in item.get("accounts", [])
            if isinstance(account, dict) and str(account.get("id", "")).strip()
        }
        available_providers = {
            str(provider_row.get("id", "")).strip().lower()
            for provider_row in item.get("providers", [])
            if isinstance(provider_row, dict) and str(provider_row.get("id", "")).strip()
        }
        provider_valid = not provider or provider in available_providers
        account_valid = not selected_account or selected_account in available_accounts
        host_ready = str(item.get("auth_state", "missing") or "missing") in {"ready", "optional"}
        validation_state = (
            "unbound"
            if not enabled
            else "provider_required"
            if available_providers and not provider
            else "provider_invalid"
            if not provider_valid
            else "account_invalid"
            if not account_valid
            else "host_auth_missing"
            if not host_ready
            else "ready"
        )
        validation_message = (
            "Workspace is not bound to this connector yet."
            if validation_state == "unbound"
            else "Choose a provider from the machine inventory before you save this binding."
            if validation_state == "provider_required"
            else f"Saved provider {provider} is not available on this machine."
            if validation_state == "provider_invalid"
            else f"Saved account {selected_account} is not available on this machine."
            if validation_state == "account_invalid"
            else str(item.get("auth_detail", "") or "Host auth is not ready for this connector.")
            if validation_state == "host_auth_missing"
            else "Workspace binding matches the current machine inventory."
        )
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
        item["history"] = history
        item.update(history)
        item["binding_validation"] = {
            "state": validation_state,
            "message": validation_message,
            "provider_valid": provider_valid,
            "account_valid": account_valid,
            "host_ready": host_ready,
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
    if available_providers and not provider:
        return False, f"Connector {connector_id} requires an explicit provider selection for workspace {workspace_name}", {
            **context,
            "reason_code": "connector_provider_unconfigured",
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
    provider: str = "",
    account_id: str = "",
    secret_key: str = "",
    status: dict[str, Any] | None = None,
    guidance: dict[str, Any] | None = None,
) -> None:
    state = _load_state()
    connectors = state.get("connectors", {}) if isinstance(state.get("connectors"), dict) else {}
    previous = connectors.get(connector_id, {}) if isinstance(connectors.get(connector_id), dict) else {}
    status_payload = status if isinstance(status, dict) else {}
    selected_provider = str(provider or "").strip().lower()
    selected_provider_row = _selected_provider_row(status_payload, provider=selected_provider)
    guidance_payload = guidance if isinstance(guidance, dict) else _connector_guidance(
        status_payload,
        provider=provider,
        account_id=account_id,
    )
    event_id = _new_event_id(f"{connector_id}-{action}")
    action_record = {
        "event_id": event_id,
        "integration_event": f"connector.{action}",
        "action": action,
        "connector": connector_id,
        "provider": selected_provider,
        "account_id": str(account_id or "").strip().lower(),
        "secret_key": str(secret_key or "").strip(),
        "ok": bool(ok),
        "summary": summary,
        "at": _now_iso(),
        "auth_state": str(status_payload.get("auth_state", "") or ""),
        "auth_detail": str(status_payload.get("auth_detail", "") or ""),
        "missing_fields": list(selected_provider_row.get("missing_fields", [])) if isinstance(selected_provider_row, dict) else [],
        "result_code": str(guidance_payload.get("result_code", "") or ""),
        "next_step": str(guidance_payload.get("next_step", "") or ""),
        "fix_target": str(guidance_payload.get("fix_target", "") or ""),
        "provider_auth_state": str(selected_provider_row.get("auth_state", "") or ""),
        "verify_check_summary": str(selected_provider_row.get("verify_check_summary", "") or ""),
    }
    recent_events = previous.get("recent_events", [])
    if not isinstance(recent_events, list):
        recent_events = []
    recent_events = [item for item in recent_events if isinstance(item, dict)][-4:] + [action_record]
    next_payload = {
        **previous,
        "last_action": action,
        "last_action_at": str(action_record.get("at", "") or ""),
        "last_action_ok": bool(ok),
        "last_result": summary,
        "last_event_id": event_id,
        "last_action_record": action_record,
        "recent_events": recent_events,
        "last_verify_ok": bool(ok) if action == "verify" else bool(previous.get("last_verify_ok", False)),
        "last_verified_at": str(action_record.get("at", "") or "") if action == "verify" else str(previous.get("last_verified_at", "") or ""),
        "last_verify_summary": summary if action == "verify" else str(previous.get("last_verify_summary", "") or ""),
        "last_verify_event_id": event_id if action == "verify" else str(previous.get("last_verify_event_id", "") or ""),
        "last_verify_record": action_record if action == "verify" else previous.get("last_verify_record", {}),
    }
    connectors[connector_id] = next_payload
    state["connectors"] = connectors
    _save_state(state)
    _log_integration_event(
        f"connector.{action}",
        {
            "event_id": event_id,
            "connector": connector_id,
            "action": action,
            "provider": selected_provider,
            "account_id": str(account_id or "").strip().lower(),
            "secret_key": str(secret_key or "").strip(),
            "auth_state": str(status_payload.get("auth_state", "") or ""),
            "ok": ok,
            "summary": summary,
            "result_code": str(guidance_payload.get("result_code", "") or ""),
            "next_step": str(guidance_payload.get("next_step", "") or ""),
            "fix_target": str(guidance_payload.get("fix_target", "") or ""),
            "provider_auth_state": str(selected_provider_row.get("auth_state", "") or ""),
            "verify_check_summary": str(selected_provider_row.get("verify_check_summary", "") or ""),
        },
    )


def _finalize_action_result(
    connector_id: str,
    action: str,
    *,
    ok: bool,
    summary: str,
    provider: str = "",
    account_id: str = "",
    secret_key: str = "",
    status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status_payload = status if isinstance(status, dict) else {}
    guidance = _connector_guidance(status_payload, provider=provider, account_id=account_id)
    _record_action_result(
        connector_id,
        action,
        ok=ok,
        summary=summary,
        provider=provider,
        account_id=account_id,
        secret_key=secret_key,
        status=status_payload,
        guidance=guidance,
    )
    history = _history_payload(connector_id)
    last_action_record = history.get("last_action_record", {}) if isinstance(history.get("last_action_record"), dict) else {}
    return {
        "ok": ok,
        "summary": summary,
        "status": status_payload,
        "history": history,
        "event_id": str(last_action_record.get("event_id", history.get("last_event_id", "")) or ""),
        "result_code": str(guidance.get("result_code", "") or ""),
        "next_step": str(guidance.get("next_step", "") or ""),
        "fix_target": str(guidance.get("fix_target", "") or ""),
    }


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
        if normalized_connector in {"crm", "voip"} and str(provider or "").strip():
            selected_provider = _selected_provider_row(status, provider=str(provider or "").strip().lower())
            verify_summary = str(selected_provider.get("verify_summary", "") or "").strip()
            selected_state = str(selected_provider.get("auth_state", status.get("auth_state", "missing")) or status.get("auth_state", "missing"))
            detail = str(selected_provider.get("scope_detail", "") or selected_provider.get("auth_detail", "") or "").strip()
            summary = verify_summary or f"{status.get('label', normalized_connector)} verify: {selected_state}"
            if detail:
                summary += f" | {detail}"
            ok = selected_state in {"ready", "optional"}
        else:
            summary = f"{status.get('label', normalized_connector)} verify: {status.get('auth_state', 'unknown')} | {status.get('auth_detail', '')}"
            ok = str(status.get("auth_state", "missing")) in {"ready", "optional"}
        return _finalize_action_result(
            normalized_connector,
            normalized_action,
            ok=ok,
            summary=summary,
            provider=provider,
            account_id=account_id,
            secret_key=secret_key,
            status=status,
        )

    if normalized_connector in {"youtube", "crm", "voip"} and normalized_action == "connect":
        connector_status_payload = connector_status(normalized_connector, provider=provider)
        provider_rows = connector_status_payload.get("providers", []) if isinstance(connector_status_payload.get("providers"), list) else []
        selected_provider = _selected_provider_row(connector_status_payload, provider=str(provider or "").strip().lower())
        if provider_rows and not selected_provider:
            ok = False
            summary = f"{normalized_connector} connect requires choosing a provider first."
            status = connector_status(normalized_connector, provider=provider)
            return _finalize_action_result(
                normalized_connector,
                normalized_action,
                ok=ok,
                summary=summary,
                provider=provider,
                account_id=account_id,
                secret_key=secret_key,
                status=status,
            )
        required_fields = list(selected_provider.get("required_fields", [])) if isinstance(selected_provider, dict) else []
        next_field = selected_provider.get("next_field", {}) if isinstance(selected_provider.get("next_field"), dict) else {}
        resolved_secret_key = str(secret_key or "").strip()
        if not resolved_secret_key and isinstance(next_field, dict):
            resolved_secret_key = str(next_field.get("key", "") or "").strip()
        if not resolved_secret_key and len(required_fields) == 1:
            resolved_secret_key = str(required_fields[0] or "").strip()
        if not resolved_secret_key or not secret_value:
            ok = False
            missing_text = ", ".join(required_fields) or "a secret key and value"
            summary = f"{normalized_connector} connect requires {missing_text}."
        else:
            valid, validation_error = _validate_secret_value(resolved_secret_key, secret_value)
            if not valid:
                ok = False
                summary = validation_error
            else:
                stored = write_machine_secret(resolved_secret_key, secret_value)
                ok = bool(stored)
                refreshed = connector_status(normalized_connector, provider=provider)
                refreshed_provider = next(
                    (
                        row for row in refreshed.get("providers", [])
                        if isinstance(row, dict) and str(row.get("id", "")).strip().lower() == str(provider or "").strip().lower()
                    ),
                    {},
                )
                remaining = list(refreshed_provider.get("missing_fields", [])) if isinstance(refreshed_provider, dict) else []
                field_meta = _secret_field_meta(resolved_secret_key)
                field_label = str(field_meta.get("label", resolved_secret_key) or resolved_secret_key)
                provider_label = str(refreshed_provider.get("label", provider or normalized_connector) or provider or normalized_connector)
                if stored:
                    summary = f"Saved {field_label} for {provider_label}."
                    if remaining:
                        next_label = str(_secret_field_meta(remaining[0]).get("label", remaining[0]) or remaining[0])
                        summary += f" Next required field: {next_label}."
                    else:
                        summary += " All required fields are present; run verify to confirm readiness."
                else:
                    summary = f"Could not persist {field_label} for {provider_label}; environment fallback remains unchanged."
        status = connector_status(normalized_connector, provider=provider)
        return _finalize_action_result(
            normalized_connector,
            normalized_action,
            ok=ok,
            summary=summary,
            provider=provider,
            account_id=account_id,
            secret_key=resolved_secret_key,
            status=status,
        )

    if normalized_connector in {"youtube", "crm", "voip"} and normalized_action == "disconnect":
        connector_status_payload = connector_status(normalized_connector, provider=provider)
        selected_provider = _selected_provider_row(connector_status_payload, provider=str(provider or "").strip().lower())
        required_fields = list(selected_provider.get("required_fields", [])) if isinstance(selected_provider, dict) else []
        keys_to_clear = [str(secret_key).strip()] if str(secret_key or "").strip() else [str(item) for item in required_fields if str(item).strip()]
        if not keys_to_clear:
            ok = False
            summary = f"{normalized_connector} disconnect requires a provider secret to clear."
        else:
            cleared_any = False
            still_present: list[str] = []
            for item in keys_to_clear:
                cleared_any = clear_machine_secret(item) or cleared_any
                if os.environ.get(item, "").strip():
                    still_present.append(item)
            summary = (
                f"Cleared {len(keys_to_clear)} stored secret(s) for {normalized_connector}."
                if cleared_any and not still_present
                else f"Cleared {len(keys_to_clear)} stored secret(s) for {normalized_connector}, but env values are still present for {', '.join(still_present)}."
                if cleared_any and still_present
                else f"No stored secrets were cleared for {normalized_connector}."
            )
        status = connector_status(normalized_connector, provider=provider)
        return _finalize_action_result(
            normalized_connector,
            normalized_action,
            ok=ok,
            summary=summary,
            provider=provider,
            account_id=account_id,
            secret_key=secret_key,
            status=status,
        )

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

    status = connector_status(normalized_connector, provider=provider)
    return _finalize_action_result(
        normalized_connector,
        normalized_action,
        ok=ok,
        summary=summary,
        provider=provider,
        account_id=account_id,
        secret_key=secret_key,
        status=status,
    )


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
        level="warning",
    )
