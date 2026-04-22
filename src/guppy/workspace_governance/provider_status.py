"""Provider readiness and connector status builders for governance-owned flows."""

from __future__ import annotations

import os
from typing import Any

from .connector_metadata import connector_spec, provider_environment_fields, provider_metadata, secret_field_meta
from .machine_auth import merge_secret_sources, secret_status


def select_provider_row(status: dict[str, Any], provider: str = "") -> dict[str, Any]:
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


def select_account_row(status: dict[str, Any], account_id: str = "") -> dict[str, Any]:
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


def summarize_verify_checks(checks: list[dict[str, Any]]) -> str:
    rendered: list[str] = []
    for item in checks[:4]:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", item.get("id", "check")) or item.get("id", "check")).strip()
        if not label:
            continue
        rendered.append(f"{label}={'OK' if bool(item.get('passed', False)) else 'MISS'}")
    return ", ".join(rendered)


def build_provider_guidance(provider_row: dict[str, Any]) -> dict[str, str]:
    if not isinstance(provider_row, dict):
        return {"result_code": "", "next_step": "", "fix_target": "", "verify_check_summary": ""}
    provider_label = str(
        provider_row.get("label", provider_row.get("id", "provider")) or provider_row.get("id", "provider")
    ).strip()
    auth_state = str(provider_row.get("auth_state", "missing") or "missing").strip().lower()
    missing_fields = [str(item) for item in provider_row.get("missing_fields", []) if str(item).strip()]
    next_field = provider_row.get("next_field", {}) if isinstance(provider_row.get("next_field"), dict) else {}
    next_label = str(next_field.get("label", next_field.get("key", "")) or next_field.get("key", "")).strip()
    next_hint = str(next_field.get("validation_hint", "") or next_field.get("input_hint", "") or "").strip()
    verify_summary = str(provider_row.get("verify_summary", "") or "").strip()
    verify_checks = (
        [item for item in provider_row.get("verify_checks", []) if isinstance(item, dict)]
        if isinstance(provider_row.get("verify_checks"), list)
        else []
    )
    verify_check_summary = summarize_verify_checks(verify_checks)
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


def _provider_verify_payload(connector_id: str, provider_id: str) -> dict[str, Any]:
    if connector_id not in {"crm", "voip"}:
        return {}
    try:
        from src.guppy.integrations.crm_voip import verify_connector_provider

        candidate = verify_connector_provider(connector_id, provider_id)
        return candidate if isinstance(candidate, dict) else {}
    except Exception:
        return {}


def build_provider_row(
    connector_id: str,
    provider_id: str,
    *,
    required_fields: list[str],
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = meta if isinstance(meta, dict) else {}
    status_payload = secret_status(required_fields)
    verify_payload = _provider_verify_payload(connector_id, provider_id)
    provider_label = str(metadata.get("label", provider_id.title()) or provider_id.title())
    scope_label = str(metadata.get("scope_label", "") or "").strip()
    endpoint_prefixes = [str(item) for item in metadata.get("endpoint_prefixes", []) if str(item).strip()]
    actions = [str(item) for item in metadata.get("actions", []) if str(item).strip()]
    auth_state = str(status_payload.get("auth_state", "missing") or "missing")
    verified_auth_state = str(verify_payload.get("auth_state", "") or "").strip().lower()
    if verified_auth_state in {"ready", "partial", "missing", "optional"}:
        auth_state = verified_auth_state
    missing_fields = list(status_payload.get("missing_fields", []))
    present_fields = list(status_payload.get("present_fields", []))
    field_sources = dict(status_payload.get("field_sources", {}))
    field_details: list[dict[str, Any]] = []
    for idx, field in enumerate(required_fields, start=1):
        detail = secret_field_meta(field)
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
    next_field = next(
        (item for item in field_details if bool(item.get("missing"))),
        field_details[0] if field_details else {},
    )
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
    storage_posture = str(status_payload.get("storage_posture", "none") or "none")
    storage_warning = str(status_payload.get("storage_warning", "") or "").strip()
    verify_summary = str(verify_payload.get("summary", "") or "").strip()
    verify_checks = (
        [item for item in verify_payload.get("checks", []) if isinstance(item, dict)]
        if isinstance(verify_payload.get("checks"), list)
        else []
    )
    scope_detail = str(verify_payload.get("scope_detail", "") or "").strip()
    payload = {
        "id": str(provider_id or "").strip().lower(),
        "label": provider_label,
        "ready": auth_state in {"ready", "optional"},
        "auth_state": auth_state,
        "auth_detail": auth_detail,
        "required_fields": list(status_payload.get("required_fields", [])),
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
        "source": str(status_payload.get("source", "none") or "none"),
        "storage_posture": storage_posture,
        "storage_warning": storage_warning,
        "scope_label": scope_label,
        "endpoint_prefixes": endpoint_prefixes,
        "actions": actions,
        "connector": connector_id,
    }
    if storage_warning:
        payload["auth_detail"] = f"{payload['auth_detail']} {storage_warning}".strip()
    payload.update(build_provider_guidance(payload))
    return payload


def _supported_providers(connector_id: str) -> list[str]:
    try:
        from src.guppy.integrations.crm_voip import SUPPORTED_CRM, SUPPORTED_VOIP

        if connector_id == "crm":
            return [str(item) for item in SUPPORTED_CRM]
        if connector_id == "voip":
            return [str(item) for item in SUPPORTED_VOIP]
    except Exception:
        pass
    return list(provider_environment_fields(connector_id).keys())


def _build_provider_family_status(
    connector_id: str,
    *,
    provider: str = "",
    default_provider: str = "",
) -> dict[str, Any]:
    provider_env = provider_environment_fields(connector_id)
    provider_meta = provider_metadata(connector_id)
    providers = _supported_providers(connector_id)
    provider_rows = [
        build_provider_row(
            connector_id,
            provider_id,
            required_fields=list(provider_env.get(provider_id, [])),
            meta=provider_meta.get(provider_id, {}),
        )
        for provider_id in providers
    ]
    selected = str(provider or default_provider).strip().lower()
    selected_row = next(
        (row for row in provider_rows if str(row.get("id", "")).strip().lower() == selected),
        provider_rows[0] if provider_rows else {},
    )
    ready_rows = [row for row in provider_rows if bool(row.get("ready", False))]
    partial_rows = [row for row in provider_rows if str(row.get("auth_state", "") or "").strip().lower() == "partial"]
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
        else merge_secret_sources([str(row.get("source", "")) for row in ready_rows])
    )
    storage_warning = (
        str(selected_row.get("storage_warning", "") or "").strip()
        if selected_row
        else ""
    )
    if connector_id == "crm":
        selected_label = str(selected_row.get("label", "") or "").strip()
        auth_detail = (
            f"{selected_label} provider credentials are configured."
            if selected_row and auth_state == "ready"
            else str(selected_row.get("auth_detail", "Select a CRM provider to inspect readiness."))
            if selected_row
            else f"{len(ready_rows)} CRM provider(s) are ready on this machine."
            if ready_rows
            else "No CRM providers are fully configured on this machine yet."
        )
        summary = "CRM bindings can pin a provider and narrow contact/opportunity actions plus endpoint scope."
        action_ids = ["contact_write", "opportunity_write"]
    else:
        auth_detail = (
            str(selected_row.get("auth_detail", "Select a VoIP provider to inspect readiness."))
            if selected_row
            else f"{len(ready_rows)} VoIP provider(s) are ready on this machine."
            if ready_rows
            else "No VoIP providers are fully configured on this machine yet."
        )
        summary = "VoIP bindings can pin a calling provider and restrict call endpoint scope."
        action_ids = ["call"]
    if storage_warning:
        auth_detail = f"{auth_detail} {storage_warning}".strip()
    spec = connector_spec(connector_id)
    return {
        "auth_state": auth_state,
        "auth_detail": auth_detail,
        "source": source,
        "accounts": [],
        "providers": provider_rows,
        "secret_fields": list(spec.get("secret_fields", [])),
        "scope_telemetry": {
            "endpoint_prefixes": [prefix for row in provider_rows for prefix in row.get("endpoint_prefixes", [])],
            "action_ids": action_ids,
            "summary": summary,
        },
    }


def build_crm_status(provider: str = "") -> dict[str, Any]:
    return _build_provider_family_status("crm", provider=provider)


def build_voip_status(provider: str = "") -> dict[str, Any]:
    provider_ids = list(provider_environment_fields("voip").keys())
    default_provider = str(
        provider or os.environ.get("VOIP_PROVIDER", provider_ids[0] if provider_ids else "twilio")
    ).strip()
    if not default_provider:
        default_provider = "twilio"
    return _build_provider_family_status("voip", provider=provider, default_provider=default_provider)
