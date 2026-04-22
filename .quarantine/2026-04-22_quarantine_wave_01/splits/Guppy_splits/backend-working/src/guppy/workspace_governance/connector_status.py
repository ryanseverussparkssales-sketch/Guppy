"""Connector status and readiness builders for governance-owned flows."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .connector_metadata import connector_spec, secret_field_meta
from .machine_auth import read_machine_secret, secret_source
from .provider_status import (
    build_crm_status,
    build_provider_guidance,
    build_voip_status,
    select_account_row,
    select_provider_row,
)


def _home_path() -> Path:
    return Path.home()


def token_path_for_gmail_account(account_id: str) -> Path:
    normalized = str(account_id or "").strip().lower() or "main"
    return _home_path() / f".guppy_gmail_token_{normalized}.json"


def _account_history_ready(connector_id: str, account_id: str) -> dict[str, Any]:
    normalized_connector = str(connector_id or "").strip().lower()
    normalized_account = str(account_id or "").strip().lower()
    if normalized_connector == "gmail":
        token_path = token_path_for_gmail_account(normalized_account)
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


def build_connector_guidance(
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
    selected_provider = select_provider_row(status, provider=provider)
    selected_account = select_account_row(status, account_id=account_id)
    if provider_rows:
        if not selected_provider:
            return {
                "result_code": "provider_selection_needed",
                "next_step": f"App Mgmt: choose a {label} provider from the inventory before you save secrets, verify, or bind it.",
                "fix_target": "App Mgmt > Connector Inventory",
            }
        provider_guidance = build_provider_guidance(selected_provider)
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
    next_field_label = str(
        secret_field_meta(secret_fields[0]).get("label", secret_fields[0]) if secret_fields else "required secret"
    ).strip()
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


def _gmail_status() -> dict[str, Any]:
    accounts = _gmail_accounts()
    home = _home_path()
    creds_candidates = [
        os.environ.get("GMAIL_CREDENTIALS_PATH", "").strip(),
        str(home / "gmail_credentials.json"),
        str(home / "gmail_credentials_main.json"),
        str(home / "gmail_credentials_sales.json"),
        str(home / "gmail_credentials_personal.json"),
    ]
    creds_files = [path for path in creds_candidates if path and Path(path).exists()]
    token_paths = list(home.glob(".guppy_gmail_token*.json"))
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
        account_rows.append(
            {
                "id": account_id,
                "label": str(item.get("label", account_id) or account_id),
                **_account_history_ready("gmail", account_id),
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
    creds_path = os.environ.get("GOOGLE_CALENDAR_CREDENTIALS_PATH", "").strip() or str(
        _home_path() / "google_calendar_credentials.json"
    )
    token_path = _home_path() / ".guppy_calendar_token.json"
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
    token_path = _home_path() / ".guppy_spotify_token"
    required_keys = ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET")
    present = [key for key in required_keys if read_machine_secret(key).strip()]
    auth_state = "ready" if len(present) == len(required_keys) and token_path.exists() else "partial" if present else "missing"
    source_values = {secret_source(key) for key in required_keys if read_machine_secret(key).strip()}
    source = next(iter(source_values), "none") if len(source_values) == 1 else "mixed" if source_values else "none"
    if token_path.exists():
        source = "mixed" if source in {"env", "keyring"} else "token_cache" if source == "none" else "mixed"
    spec = connector_spec("spotify")
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
        "secret_fields": list(spec.get("secret_fields", [])),
        "scope_telemetry": {
            "endpoint_prefixes": ["connector://spotify", "connector://spotify/player"],
            "action_ids": ["read", "play", "control"],
            "summary": "Spotify bindings control read/playback actions against the machine-authenticated player.",
        },
    }


def _youtube_status() -> dict[str, Any]:
    key_present = bool(read_machine_secret("YOUTUBE_API_KEY").strip())
    spec = connector_spec("youtube")
    return {
        "auth_state": "ready" if key_present else "optional",
        "auth_detail": (
            "YouTube API key is configured."
            if key_present
            else "YouTube API key is missing; fallback scraping may still work."
        ),
        "source": secret_source("YOUTUBE_API_KEY"),
        "accounts": [],
        "providers": [],
        "secret_fields": list(spec.get("secret_fields", [])),
        "scope_telemetry": {
            "endpoint_prefixes": ["connector://youtube", "connector://youtube/search", "connector://youtube/play"],
            "action_ids": ["search", "play"],
            "summary": "YouTube can work in fallback mode, but an API key improves quota stability and predictable search access.",
        },
    }


def build_connector_status(
    connector_id: str,
    *,
    provider: str = "",
    account_id: str = "",
) -> dict[str, Any]:
    normalized = str(connector_id or "").strip().lower()
    spec = connector_spec(normalized)
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
        "crm": lambda: build_crm_status(provider),
        "voip": lambda: build_voip_status(provider),
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
    payload.update(build_connector_guidance(payload, provider=provider, account_id=account_id))
    return payload
