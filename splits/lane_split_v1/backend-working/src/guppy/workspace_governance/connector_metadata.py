"""Pure connector governance metadata and lookup helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_CONNECTOR_IDS: tuple[str, ...] = ("gmail", "calendar", "spotify", "youtube", "crm", "voip")

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

_PROVIDER_ENVIRONMENT_FIELDS: dict[str, dict[str, tuple[str, ...]]] = {
    "crm": {
        "hubspot": ("HUBSPOT_API_KEY",),
        "salesforce": ("SALESFORCE_ACCESS_TOKEN", "SALESFORCE_INSTANCE_URL"),
        "gohighlevel": ("GOHIGHLEVEL_API_KEY",),
        "zoho": ("ZOHO_ACCESS_TOKEN",),
    },
    "voip": {
        "twilio": ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"),
        "generic": (),
    },
}

_PROVIDER_METADATA: dict[str, dict[str, dict[str, Any]]] = {
    "crm": {
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
    },
    "voip": {
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
    },
}

_SECRET_FIELD_METADATA: dict[str, dict[str, Any]] = {
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

_TOOL_CONNECTOR_MAP: dict[str, str] = {
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

_TOOL_ACTION_MAP: dict[str, str] = {
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


def list_connector_ids() -> tuple[str, ...]:
    return tuple(_CONNECTOR_IDS)


def connector_catalog() -> dict[str, dict[str, Any]]:
    return deepcopy(_CONNECTOR_CATALOG)


def connector_spec(connector_id: str) -> dict[str, Any]:
    normalized = str(connector_id or "").strip().lower()
    return deepcopy(_CONNECTOR_CATALOG.get(normalized, {}))


def provider_environment_fields(connector_id: str) -> dict[str, tuple[str, ...]]:
    normalized = str(connector_id or "").strip().lower()
    return deepcopy(_PROVIDER_ENVIRONMENT_FIELDS.get(normalized, {}))


def provider_metadata(connector_id: str) -> dict[str, dict[str, Any]]:
    normalized = str(connector_id or "").strip().lower()
    return deepcopy(_PROVIDER_METADATA.get(normalized, {}))


def provider_spec(connector_id: str, provider_id: str) -> dict[str, Any]:
    normalized_connector = str(connector_id or "").strip().lower()
    normalized_provider = str(provider_id or "").strip().lower()
    return deepcopy(_PROVIDER_METADATA.get(normalized_connector, {}).get(normalized_provider, {}))


def secret_field_meta(secret_key: str) -> dict[str, Any]:
    normalized = str(secret_key or "").strip().upper()
    metadata = _SECRET_FIELD_METADATA.get(normalized, {})
    label = str(metadata.get("label", normalized.replace("_", " ").title()) or normalized.replace("_", " ").title())
    return {
        "key": normalized,
        "label": label,
        "placeholder": str(metadata.get("placeholder", "") or ""),
        "input_hint": str(metadata.get("input_hint", "") or ""),
        "validation_hint": str(metadata.get("validation_hint", "") or ""),
        "kind": str(metadata.get("kind", "token") or "token"),
        "masked": bool(metadata.get("masked", True)),
    }


def validate_secret_value(secret_key: str, value: str) -> tuple[bool, str]:
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
    if normalized in {
        "HUBSPOT_API_KEY",
        "GOHIGHLEVEL_API_KEY",
        "ZOHO_ACCESS_TOKEN",
        "YOUTUBE_API_KEY",
        "SPOTIFY_CLIENT_SECRET",
        "TWILIO_AUTH_TOKEN",
    } and len(cleaned) < 8:
        return False, f"{normalized} looks too short. Paste the full provider value."
    if normalized == "SPOTIFY_CLIENT_ID" and len(cleaned) < 8:
        return False, "Spotify client id looks too short."
    return True, ""


def connector_id_for_tool(tool_name: str) -> str:
    normalized = str(tool_name or "").strip().lower()
    if normalized.startswith("gmail_"):
        return "gmail"
    return _TOOL_CONNECTOR_MAP.get(normalized, "")


def connector_action_for_tool(tool_name: str) -> str:
    normalized = str(tool_name or "").strip().lower()
    return _TOOL_ACTION_MAP.get(normalized, "default")
