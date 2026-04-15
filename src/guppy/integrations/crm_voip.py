"""
crm_voip_integrations.py
Future-ready stubs for external CRM and VoIP providers.

Providers currently targeted:
- HubSpot
- Salesforce
- GoHighLevel
- Zoho

VoIP providers (future):
- Twilio (default planned)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

from src.guppy.paths import RUNTIME_DIR
from utils.connector_manager import read_machine_secret
from utils.session_logger import rotate_jsonl_file

INTEGRATION_LOG = RUNTIME_DIR / "integration_events.jsonl"

SUPPORTED_CRM = ["hubspot", "salesforce", "gohighlevel", "zoho"]
SUPPORTED_VOIP = ["twilio", "generic"]

CONNECTION_BLUEPRINT = {
    "crms": {
        "hubspot": {
            "required_env": ["HUBSPOT_API_KEY"],
            "status": "stub_ready",
            "notes": "Contact and opportunity stubs are wired. Live client pending.",
        },
        "salesforce": {
            "required_env": ["SALESFORCE_ACCESS_TOKEN", "SALESFORCE_INSTANCE_URL"],
            "status": "stub_ready",
            "notes": "Contact and opportunity stubs are wired. Live client pending.",
        },
        "gohighlevel": {
            "required_env": ["GOHIGHLEVEL_API_KEY"],
            "status": "stub_ready",
            "notes": "Contact and opportunity stubs are wired. Live client pending.",
        },
        "zoho": {
            "required_env": ["ZOHO_ACCESS_TOKEN"],
            "status": "stub_ready",
            "notes": "Contact and opportunity stubs are wired. Live client pending.",
        },
    },
    "voip": {
        "twilio": {
            "required_env": ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"],
            "status": "stub_ready",
            "notes": "Outbound call stub is wired. Live dialer pending.",
        }
    },
    "media_and_ops": {
        "spotify": {
            "required_env": ["SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET", "SPOTIFY_REDIRECT_URI"],
            "status": "live_supported",
            "notes": "Playback tools available when provider auth is complete.",
        },
        "youtube": {
            "required_env": ["YOUTUBE_API_KEY"],
            "status": "partial",
            "notes": "Search/play tooling works with fallback scraping. API key enables stable quotas.",
        },
        "gmail": {
            "required_env": ["GMAIL_CREDENTIALS_PATH"],
            "status": "live_supported",
            "notes": "Gmail cleanup and account routing tools are present.",
        },
        "calendar": {
            "required_env": ["GOOGLE_CALENDAR_CREDENTIALS_PATH"],
            "status": "planned",
            "notes": "Calendar orchestration planned. Reminder layer exists today.",
        },
        "utorrent": {
            "required_env": ["UTORRENT_HOST", "UTORRENT_PORT", "UTORRENT_USER", "UTORRENT_PASS"],
            "status": "live_supported",
            "notes": "Merlin torrent spells available with configured WebUI.",
        },
        "plex": {
            "required_env": ["PLEX_URL", "PLEX_TOKEN"],
            "status": "stub",
            "notes": "Status layer exists. Full command coverage planned.",
        },
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log_event(event_type: str, payload: Dict[str, Any]) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    rotate_jsonl_file(INTEGRATION_LOG)
    record = {
        "timestamp": _now_iso(),
        "event_type": event_type,
        "payload": payload,
    }
    with INTEGRATION_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=True) + "\n")


def list_external_integrations() -> str:
    crm_lines = []
    for provider in SUPPORTED_CRM:
        if provider == "salesforce":
            enabled = bool(read_machine_secret("SALESFORCE_ACCESS_TOKEN").strip()) and bool(read_machine_secret("SALESFORCE_INSTANCE_URL").strip())
        else:
            enabled = bool(read_machine_secret(f"{provider.upper()}_API_KEY").strip())
        crm_lines.append(f"- {provider}: {'configured' if enabled else 'not configured'}")

    voip_provider = os.environ.get("VOIP_PROVIDER", "twilio").strip().lower() or "twilio"
    voip_enabled = bool(read_machine_secret("TWILIO_ACCOUNT_SID").strip()) and bool(
        read_machine_secret("TWILIO_AUTH_TOKEN").strip()
    )

    lines = [
        "External integration status",
        "CRMs:",
        *crm_lines,
        "VoIP:",
        f"- provider: {voip_provider}",
        f"- status: {'configured' if voip_enabled else 'not configured'}",
    ]
    return "\n".join(lines)


def get_foundation_readiness() -> dict:
    """Return a full readiness snapshot for planned connection foundations."""
    snapshot = {
        "generated_at": _now_iso(),
        "sections": {},
        "ready_count": 0,
        "total_connections": 0,
    }

    for section, providers in CONNECTION_BLUEPRINT.items():
        section_rows = {}
        for provider, spec in providers.items():
            required_env = spec.get("required_env", [])
            present = [k for k in required_env if read_machine_secret(k).strip()]
            missing = [k for k in required_env if k not in present]
            configured = len(missing) == 0
            snapshot["total_connections"] += 1
            if configured:
                snapshot["ready_count"] += 1

            section_rows[provider] = {
                "status": spec.get("status", "planned"),
                "configured": configured,
                "required_env": required_env,
                "present_env": present,
                "missing_env": missing,
                "notes": spec.get("notes", ""),
            }
        snapshot["sections"][section] = section_rows

    snapshot["readiness_percent"] = round(
        (snapshot["ready_count"] / snapshot["total_connections"] * 100.0)
        if snapshot["total_connections"]
        else 0.0,
        2,
    )
    return snapshot


def get_foundation_readiness_text() -> str:
    data = get_foundation_readiness()
    lines = [
        "Foundation readiness",
        f"Configured: {data['ready_count']} / {data['total_connections']} ({data['readiness_percent']}%)",
    ]
    for section, providers in data["sections"].items():
        lines.append(f"\n[{section}]")
        for provider, row in providers.items():
            state = "ready" if row["configured"] else "pending"
            lines.append(f"- {provider}: {state} ({row['status']})")
            if row["missing_env"]:
                lines.append(f"  missing: {', '.join(row['missing_env'])}")
    return "\n".join(lines)


def _provider_ready(provider: str) -> bool:
    p = (provider or "").strip().lower()
    if p == "hubspot":
        return bool(read_machine_secret("HUBSPOT_API_KEY").strip())
    if p == "salesforce":
        return bool(read_machine_secret("SALESFORCE_ACCESS_TOKEN").strip()) and bool(
            read_machine_secret("SALESFORCE_INSTANCE_URL").strip()
        )
    if p == "gohighlevel":
        return bool(read_machine_secret("GOHIGHLEVEL_API_KEY").strip())
    if p == "zoho":
        return bool(read_machine_secret("ZOHO_ACCESS_TOKEN").strip())
    return False


def crm_upsert_contact(
    provider: str,
    name: str,
    email: str = "",
    phone: str = "",
    company: str = "",
    notes: str = "",
    dry_run: bool = True,
) -> str:
    p = (provider or "").strip().lower()
    if p not in SUPPORTED_CRM:
        return f"Unsupported CRM provider: {provider}. Supported: {', '.join(SUPPORTED_CRM)}"

    payload = {
        "provider": p,
        "name": name,
        "email": email,
        "phone": phone,
        "company": company,
        "notes": notes,
        "dry_run": dry_run,
    }
    _log_event("crm.upsert_contact.request", payload)

    if dry_run or not _provider_ready(p):
        reason = "dry run" if dry_run else "provider not configured"
        return f"CRM contact upsert stub ({p}) prepared: {name} [{reason}]"

    return (
        f"CRM provider {p} is configured. Live upsert is intentionally stubbed for now. "
        "Set dry_run=true until provider-specific client is implemented."
    )


def crm_create_opportunity(
    provider: str,
    title: str,
    value: float = 0.0,
    stage: str = "new",
    company: str = "",
    contact_name: str = "",
    notes: str = "",
    dry_run: bool = True,
) -> str:
    p = (provider or "").strip().lower()
    if p not in SUPPORTED_CRM:
        return f"Unsupported CRM provider: {provider}. Supported: {', '.join(SUPPORTED_CRM)}"

    payload = {
        "provider": p,
        "title": title,
        "value": float(value or 0.0),
        "stage": stage,
        "company": company,
        "contact_name": contact_name,
        "notes": notes,
        "dry_run": dry_run,
    }
    _log_event("crm.create_opportunity.request", payload)

    if dry_run or not _provider_ready(p):
        reason = "dry run" if dry_run else "provider not configured"
        return f"CRM opportunity stub ({p}) prepared: {title} [{reason}]"

    return (
        f"CRM provider {p} is configured. Live opportunity creation is intentionally stubbed for now. "
        "Set dry_run=true until provider-specific client is implemented."
    )


def voip_place_call(
    provider: str,
    to_number: str,
    from_number: str = "",
    contact_name: str = "",
    purpose: str = "",
    dry_run: bool = True,
) -> str:
    p = (provider or os.environ.get("VOIP_PROVIDER", "twilio")).strip().lower() or "twilio"
    if p not in SUPPORTED_VOIP:
        return f"Unsupported VoIP provider: {p}. Supported: {', '.join(SUPPORTED_VOIP)}"

    payload = {
        "provider": p,
        "to_number": to_number,
        "from_number": from_number,
        "contact_name": contact_name,
        "purpose": purpose,
        "dry_run": dry_run,
    }
    _log_event("voip.place_call.request", payload)

    configured = bool(read_machine_secret("TWILIO_ACCOUNT_SID").strip()) and bool(
        read_machine_secret("TWILIO_AUTH_TOKEN").strip()
    )

    if dry_run or not configured:
        reason = "dry run" if dry_run else "provider not configured"
        return f"VoIP call stub ({p}) prepared to {to_number} [{reason}]"

    return (
        f"VoIP provider {p} is configured. Live call placement is intentionally stubbed for now. "
        "Set dry_run=true until provider-specific client is implemented."
    )
