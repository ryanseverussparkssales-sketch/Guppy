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
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

from src.guppy.paths import RUNTIME_DIR
from src.guppy.workspace_governance import read_machine_secret
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


def _check_result(check_id: str, label: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "id": str(check_id or "").strip(),
        "label": str(label or "").strip(),
        "state": "pass" if passed else "fail",
        "passed": bool(passed),
        "detail": str(detail or "").strip(),
    }


def _valid_url_host(value: str) -> tuple[bool, str]:
    cleaned = str(value or "").strip()
    if not cleaned:
        return False, ""
    try:
        parsed = urlparse(cleaned)
    except Exception:
        return False, ""
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False, ""
    return True, parsed.netloc.lower()


def verify_connector_provider(connector: str, provider: str) -> dict[str, Any]:
    normalized_connector = str(connector or "").strip().lower()
    normalized_provider = str(provider or "").strip().lower()
    checks: list[dict[str, Any]] = []
    summary = ""
    scope_detail = ""
    auth_state = "missing"

    if normalized_connector == "crm":
        if normalized_provider == "hubspot":
            token = read_machine_secret("HUBSPOT_API_KEY").strip()
            looks_valid = token.startswith("pat-") or len(token) >= 20
            checks = [
                _check_result("hubspot_api_key_present", "Private app token present", bool(token), "Token is stored for this machine." if token else "Missing HUBSPOT_API_KEY."),
                _check_result("hubspot_api_key_shape", "Token format looks plausible", looks_valid, "Token resembles a HubSpot private app token." if looks_valid else "Token is present but does not look like a modern HubSpot private app token."),
            ]
            auth_state = "ready" if all(item["passed"] for item in checks) else "partial" if token else "missing"
            summary = "HubSpot verify passed for contacts + opportunities." if auth_state == "ready" else "HubSpot verify found missing or weak private app token readiness."
            scope_detail = "Expected scope: contacts + opportunities via a machine-level HubSpot private app token."
        elif normalized_provider == "salesforce":
            token = read_machine_secret("SALESFORCE_ACCESS_TOKEN").strip()
            instance_url = read_machine_secret("SALESFORCE_INSTANCE_URL").strip()
            url_ok, host = _valid_url_host(instance_url)
            salesforce_host = host.endswith("salesforce.com") or host.endswith("force.com")
            checks = [
                _check_result("salesforce_access_token_present", "Access token present", bool(token), "Access token is stored for this machine." if token else "Missing SALESFORCE_ACCESS_TOKEN."),
                _check_result("salesforce_instance_url_present", "Instance URL present", bool(instance_url), "Instance URL is stored for this machine." if instance_url else "Missing SALESFORCE_INSTANCE_URL."),
                _check_result("salesforce_instance_url_valid", "Instance URL looks valid", url_ok and salesforce_host, f"Using Salesforce host {host}." if url_ok and salesforce_host else "Instance URL must be an https Salesforce org host."),
            ]
            auth_state = "ready" if all(item["passed"] for item in checks) else "partial" if token or instance_url else "missing"
            summary = "Salesforce verify passed for contacts + opportunities." if auth_state == "ready" else "Salesforce verify found missing token or invalid org URL readiness."
            scope_detail = "Expected scope: contacts + opportunities against the configured Salesforce org host."
        elif normalized_provider == "gohighlevel":
            token = read_machine_secret("GOHIGHLEVEL_API_KEY").strip()
            looks_valid = len(token) >= 16
            checks = [
                _check_result("gohighlevel_api_key_present", "API key present", bool(token), "API key is stored for this machine." if token else "Missing GOHIGHLEVEL_API_KEY."),
                _check_result("gohighlevel_api_key_shape", "API key length looks plausible", looks_valid, "API key length looks plausible." if looks_valid else "API key is present but unusually short."),
            ]
            auth_state = "ready" if all(item["passed"] for item in checks) else "partial" if token else "missing"
            summary = "GoHighLevel verify passed for contacts + pipelines." if auth_state == "ready" else "GoHighLevel verify found missing or weak API-key readiness."
            scope_detail = "Expected scope: contacts + pipelines via a machine-level GoHighLevel API key."
        elif normalized_provider == "zoho":
            token = read_machine_secret("ZOHO_ACCESS_TOKEN").strip()
            looks_valid = len(token) >= 20 and not token.lower().startswith("http")
            checks = [
                _check_result("zoho_access_token_present", "Access token present", bool(token), "Access token is stored for this machine." if token else "Missing ZOHO_ACCESS_TOKEN."),
                _check_result("zoho_access_token_shape", "Token format looks plausible", looks_valid, "Access token shape looks plausible." if looks_valid else "Access token is present but does not look like a Zoho access token."),
            ]
            auth_state = "ready" if all(item["passed"] for item in checks) else "partial" if token else "missing"
            summary = "Zoho verify passed for contacts + deals." if auth_state == "ready" else "Zoho verify found missing or weak access-token readiness."
            scope_detail = "Expected scope: contacts + deals via a machine-level Zoho access token."
        else:
            return {
                "auth_state": "missing",
                "summary": "Unknown CRM provider.",
                "checks": [],
                "scope_detail": "",
            }
    elif normalized_connector == "voip":
        if normalized_provider == "twilio":
            sid = read_machine_secret("TWILIO_ACCOUNT_SID").strip()
            token = read_machine_secret("TWILIO_AUTH_TOKEN").strip()
            sid_ok = sid.startswith("AC") and len(sid) >= 12
            token_ok = len(token) >= 8
            checks = [
                _check_result("twilio_account_sid_present", "Account SID present", bool(sid), "Account SID is stored for this machine." if sid else "Missing TWILIO_ACCOUNT_SID."),
                _check_result("twilio_account_sid_shape", "Account SID format looks valid", sid_ok, "Account SID starts with AC." if sid_ok else "Twilio Account SID should start with AC."),
                _check_result("twilio_auth_token_present", "Auth token present", bool(token), "Auth token is stored for this machine." if token else "Missing TWILIO_AUTH_TOKEN."),
                _check_result("twilio_auth_token_shape", "Auth token length looks plausible", token_ok, "Auth token length looks plausible." if token_ok else "Twilio auth token is present but unusually short."),
            ]
            auth_state = "ready" if all(item["passed"] for item in checks) else "partial" if sid or token else "missing"
            summary = "Twilio verify passed for outbound calling." if auth_state == "ready" else "Twilio verify found missing SID/token readiness."
            scope_detail = "Expected scope: outbound calling with a machine-level Twilio Account SID and auth token."
        elif normalized_provider == "generic":
            checks = [
                _check_result("generic_voip_manual_handoff", "Manual provider handoff", True, "Generic SIP remains operator-managed and does not require stored Guppy secrets in this pass."),
            ]
            auth_state = "optional"
            summary = "Generic SIP verify is informational only in this pass."
            scope_detail = "Expected scope: manual provider handoff for outbound calling."
        else:
            return {
                "auth_state": "missing",
                "summary": "Unknown VoIP provider.",
                "checks": [],
                "scope_detail": "",
            }
    else:
        return {
            "auth_state": "missing",
            "summary": "Unknown connector family.",
            "checks": [],
            "scope_detail": "",
        }

    return {
        "auth_state": auth_state,
        "summary": summary,
        "checks": checks,
        "scope_detail": scope_detail,
        "ok": auth_state in {"ready", "optional"},
    }


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

    if dry_run:
        return f"CRM contact upsert prepared (dry_run=True): {name} [{p}]"

    if not _provider_ready(p):
        return f"CRM provider {p} not configured — set required env vars."

    try:
        result = _live_crm_upsert_contact(p, name, email, phone, company, notes)
        _log_event("crm.upsert_contact.result", {**payload, **result})
        return f"CRM contact upserted [{p}]: {name} — {result}"
    except Exception as exc:
        logger.exception("CRM contact upsert failed")
        return f"CRM contact upsert failed [{p}]: {exc}"


def _live_crm_upsert_contact(
    provider: str, name: str, email: str, phone: str, company: str, notes: str
) -> dict:
    import requests

    if provider == "hubspot":
        api_key = read_machine_secret("HUBSPOT_API_KEY").strip()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        def _contact_props() -> dict:
            props: dict = {}
            if name:
                parts = name.split(None, 1)
                props["firstname"] = parts[0]
                if len(parts) > 1:
                    props["lastname"] = parts[1]
            if email:   props["email"]   = email
            if phone:   props["phone"]   = phone
            if company: props["company"] = company
            return props

        if email:
            search = requests.post(
                "https://api.hubapi.com/crm/v3/objects/contacts/search",
                headers=headers,
                json={"filterGroups": [{"filters": [{"propertyName": "email", "operator": "EQ", "value": email}]}]},
                timeout=10,
            )
            if search.status_code == 200 and search.json().get("total", 0) > 0:
                contact_id = search.json()["results"][0]["id"]
                r = requests.patch(
                    f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}",
                    headers=headers,
                    json={"properties": _contact_props()},
                    timeout=10,
                )
                r.raise_for_status()
                return {"action": "updated", "id": contact_id}

        r = requests.post(
            "https://api.hubapi.com/crm/v3/objects/contacts",
            headers=headers,
            json={"properties": _contact_props()},
            timeout=10,
        )
        r.raise_for_status()
        return {"action": "created", "id": r.json()["id"]}

    if provider == "salesforce":
        token = read_machine_secret("SALESFORCE_ACCESS_TOKEN").strip()
        instance_url = read_machine_secret("SALESFORCE_INSTANCE_URL").strip().rstrip("/")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        data: dict = {}
        if name:
            parts = name.split(None, 1)
            data["FirstName"] = parts[0]
            data["LastName"] = parts[1] if len(parts) > 1 else "."
        if email:   data["Email"]   = email
        if phone:   data["Phone"]   = phone
        if company: data["Account"] = {"Name": company}
        r = requests.post(
            f"{instance_url}/services/data/v57.0/sobjects/Contact",
            headers=headers, json=data, timeout=10,
        )
        r.raise_for_status()
        return {"action": "created", "id": r.json().get("id")}

    if provider == "gohighlevel":
        api_key = read_machine_secret("GOHIGHLEVEL_API_KEY").strip()
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        data = {"name": name, "email": email, "phone": phone, "companyName": company}
        r = requests.post(
            "https://rest.gohighlevel.com/v1/contacts/",
            headers=headers, json={k: v for k, v in data.items() if v}, timeout=10,
        )
        r.raise_for_status()
        return {"action": "created", "id": r.json().get("contact", {}).get("id")}

    if provider == "zoho":
        token = read_machine_secret("ZOHO_ACCESS_TOKEN").strip()
        headers = {"Authorization": f"Zoho-oauthtoken {token}", "Content-Type": "application/json"}
        parts = name.split(None, 1) if name else ["Unknown"]
        data = {
            "data": [{
                "First_Name": parts[0],
                "Last_Name": parts[1] if len(parts) > 1 else ".",
                "Email": email,
                "Phone": phone,
                "Account_Name": company,
            }]
        }
        r = requests.post(
            "https://www.zohoapis.com/crm/v2/Contacts",
            headers=headers, json=data, timeout=10,
        )
        r.raise_for_status()
        created = r.json().get("data", [{}])[0]
        return {"action": "created", "id": created.get("details", {}).get("id")}

    raise ValueError(f"Unhandled provider: {provider}")


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

    if dry_run:
        return f"CRM opportunity prepared (dry_run=True): {title} [{p}]"

    if not _provider_ready(p):
        return f"CRM provider {p} not configured — set required env vars."

    try:
        result = _live_crm_create_opportunity(p, title, value, stage, company, contact_name, notes)
        _log_event("crm.create_opportunity.result", {**payload, **result})
        return f"CRM opportunity created [{p}]: {title} — {result}"
    except Exception as exc:
        logger.exception("CRM opportunity creation failed")
        return f"CRM opportunity creation failed [{p}]: {exc}"


def _live_crm_create_opportunity(
    provider: str, title: str, value: float, stage: str,
    company: str, contact_name: str, notes: str,
) -> dict:
    import requests

    if provider == "hubspot":
        api_key = read_machine_secret("HUBSPOT_API_KEY").strip()
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        data = {
            "properties": {
                "dealname": title,
                "amount": str(value),
                "dealstage": stage,
                "description": notes,
            }
        }
        r = requests.post(
            "https://api.hubapi.com/crm/v3/objects/deals",
            headers=headers, json=data, timeout=10,
        )
        r.raise_for_status()
        return {"action": "created", "id": r.json()["id"]}

    if provider == "salesforce":
        token = read_machine_secret("SALESFORCE_ACCESS_TOKEN").strip()
        instance_url = read_machine_secret("SALESFORCE_INSTANCE_URL").strip().rstrip("/")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        data = {"Name": title, "Amount": value, "StageName": stage or "Prospecting", "CloseDate": "2099-12-31"}
        r = requests.post(
            f"{instance_url}/services/data/v57.0/sobjects/Opportunity",
            headers=headers, json=data, timeout=10,
        )
        r.raise_for_status()
        return {"action": "created", "id": r.json().get("id")}

    if provider == "gohighlevel":
        api_key = read_machine_secret("GOHIGHLEVEL_API_KEY").strip()
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        data = {"title": title, "monetaryValue": value, "stage": stage}
        r = requests.post(
            "https://rest.gohighlevel.com/v1/opportunities/",
            headers=headers, json={k: v for k, v in data.items() if v is not None}, timeout=10,
        )
        r.raise_for_status()
        return {"action": "created", "id": r.json().get("opportunity", {}).get("id")}

    if provider == "zoho":
        token = read_machine_secret("ZOHO_ACCESS_TOKEN").strip()
        headers = {"Authorization": f"Zoho-oauthtoken {token}", "Content-Type": "application/json"}
        data = {"data": [{"Deal_Name": title, "Amount": value, "Stage": stage or "Qualification"}]}
        r = requests.post(
            "https://www.zohoapis.com/crm/v2/Deals",
            headers=headers, json=data, timeout=10,
        )
        r.raise_for_status()
        created = r.json().get("data", [{}])[0]
        return {"action": "created", "id": created.get("details", {}).get("id")}

    raise ValueError(f"Unhandled provider: {provider}")


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

    if dry_run:
        return f"VoIP call prepared (dry_run=True): {to_number} via {p}"

    if not configured:
        return f"VoIP provider {p} not configured — set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN."

    try:
        result = _live_twilio_call(to_number, from_number, purpose)
        _log_event("voip.place_call.result", {**payload, **result})
        return f"Call initiated [{p}] to {to_number}: sid={result.get('call_sid')} status={result.get('status')}"
    except Exception as exc:
        logger.exception("VoIP call placement failed")
        return f"VoIP call failed [{p}]: {exc}"


def _live_twilio_call(to_number: str, from_number: str, purpose: str) -> dict:
    import requests
    from requests.auth import HTTPBasicAuth

    sid = read_machine_secret("TWILIO_ACCOUNT_SID").strip()
    auth_token = read_machine_secret("TWILIO_AUTH_TOKEN").strip()
    from_num = (from_number or "").strip() or os.environ.get("TWILIO_FROM_NUMBER", "").strip()
    twiml_url = os.environ.get("TWILIO_TWIML_URL", "").strip()

    if not from_num:
        raise ValueError("TWILIO_FROM_NUMBER not set and no from_number provided")

    if not twiml_url:
        msg = f"Guppy outbound call{': ' + purpose if purpose else '.'}"
        twiml_url = (
            "https://twimlets.com/message"
            f"?Message%5B0%5D={msg.replace(' ', '+')}"
        )

    resp = requests.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json",
        auth=HTTPBasicAuth(sid, auth_token),
        data={"To": to_number, "From": from_num, "Url": twiml_url},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return {"call_sid": data.get("sid"), "status": data.get("status")}
