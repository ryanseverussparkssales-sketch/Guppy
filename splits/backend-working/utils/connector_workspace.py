from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any, Callable


JsonDict = dict[str, Any]


def history_timeline(recent_events: list[JsonDict]) -> list[JsonDict]:
    timeline: list[JsonDict] = []
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


def history_payload(
    connector_id: str,
    *,
    load_state: Callable[[], JsonDict],
) -> JsonDict:
    state = load_state()
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
    timeline = history_timeline(recent_rows)
    recent_summary = " | ".join(
        f"{str(item.get('action', 'action') or 'action')}={'OK' if bool(item.get('ok', False)) else 'FAIL'}"
        + (
            f" ref={str(item.get('event_id', '') or '').strip()}"
            if str(item.get("event_id", "") or "").strip()
            else ""
        )
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


def effective_binding_enabled(workspace_name: str, binding: JsonDict) -> tuple[bool, bool]:
    if bool(binding.get("_exists", False)):
        return bool(binding.get("enabled", False)), False
    if str(workspace_name or "").strip().lower() == "guppy-primary":
        return True, True
    return False, False


def binding_validation_payload(
    workspace_name: str,
    binding: JsonDict,
    status: JsonDict,
    *,
    enabled: bool,
    inherited: bool,
    provider: str,
    account_id: str,
) -> JsonDict:
    selected_account = str(account_id or "").strip().lower()
    available_accounts = {
        str(account.get("id", "")).strip().lower()
        for account in status.get("accounts", [])
        if isinstance(account, dict) and str(account.get("id", "")).strip()
    }
    available_providers = {
        str(provider_row.get("id", "")).strip().lower()
        for provider_row in status.get("providers", [])
        if isinstance(provider_row, dict) and str(provider_row.get("id", "")).strip()
    }
    provider_valid = not provider or provider in available_providers
    account_valid = not selected_account or selected_account in available_accounts
    host_ready = str(status.get("auth_state", "missing") or "missing") in {"ready", "optional"}
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
        else str(status.get("auth_detail", "") or "Host auth is not ready for this connector.")
        if validation_state == "host_auth_missing"
        else "Workspace binding matches the current machine inventory."
    )
    return {
        "state": validation_state,
        "message": validation_message,
        "provider_valid": provider_valid,
        "account_valid": account_valid,
        "host_ready": host_ready,
        "binding_enabled": bool(enabled),
        "binding_inherited": bool(inherited),
        "workspace": str(workspace_name or "").strip(),
        "provider": str(provider or "").strip().lower(),
        "account_id": selected_account,
        "note": str(binding.get("note", "") or "").strip(),
    }


def history_summary_line(history: JsonDict) -> str:
    last_verify_at = str(history.get("last_verified_at", "") or "").strip()
    last_verify_summary = str(history.get("last_verify_summary", "") or "").strip()
    last_verify_event_id = str(history.get("last_verify_event_id", "") or "").strip()
    if last_verify_at:
        verdict = "OK" if bool(history.get("last_verify_ok", False)) else "CHECK"
        summary = f"Last verify {verdict} @ {last_verify_at}"
        if last_verify_summary:
            summary += f" | {last_verify_summary}"
        if last_verify_event_id:
            summary += f" | Ref: {last_verify_event_id}"
        return summary

    last_action = str(history.get("last_action", "") or "").strip()
    last_action_at = str(history.get("last_action_at", "") or "").strip()
    last_result = str(history.get("last_result", "") or "").strip()
    last_event_id = str(history.get("last_event_id", "") or "").strip()
    if not last_action:
        return "No verify/connect activity has been recorded yet."
    summary = f"Last {last_action}"
    if last_action_at:
        summary += f" @ {last_action_at}"
    if last_result:
        summary += f" | {last_result}"
    if last_event_id:
        summary += f" | Ref: {last_event_id}"
    return summary


def readiness_evidence_payload(
    connector_id: str,
    status: JsonDict,
    history: JsonDict,
    validation: JsonDict,
    *,
    action_id: str,
    provider: str,
    account_id: str,
    connector_guidance: Callable[..., JsonDict],
) -> JsonDict:
    guidance = connector_guidance(status, provider=provider, account_id=account_id)
    validation_state = str(validation.get("state", "") or "").strip().lower()
    auth_state = str(status.get("auth_state", "missing") or "missing").strip().lower()
    auth_source = str(status.get("source", "none") or "none").strip().lower()
    history_summary = history_summary_line(history)
    if validation_state != "ready":
        readiness_state = "blocked"
    elif str(history.get("last_verify_event_id", "") or "").strip():
        readiness_state = "verified" if bool(history.get("last_verify_ok", False)) else "verification_failed"
    elif auth_state in {"ready", "optional"}:
        readiness_state = "pending_verify"
    elif auth_state == "partial":
        readiness_state = "host_setup_incomplete"
    else:
        readiness_state = "host_setup_missing"
    readiness_label = {
        "verified": "Connector evidence is current.",
        "pending_verify": "Connector policy allows access, but no verify evidence has been recorded yet.",
        "verification_failed": "Connector verify evidence needs attention.",
        "host_setup_incomplete": "Connector host setup is still incomplete.",
        "host_setup_missing": "Connector host auth is missing.",
        "blocked": "Connector policy or binding is blocking this workspace.",
    }.get(readiness_state, "Connector readiness needs attention.")
    evidence_parts = [
        readiness_label,
        f"Binding: {str(validation.get('message', '') or 'No binding validation detail is available.').strip()}",
        f"Auth: {auth_state.upper()} via {auth_source.upper() or 'NONE'}.",
        f"History: {history_summary}",
    ]
    next_step = str(guidance.get("next_step", "") or "").strip()
    if next_step and readiness_state != "verified":
        evidence_parts.append(f"Next: {next_step}")
    return {
        "connector": str(connector_id or "").strip().lower(),
        "action_id": str(action_id or "").strip().lower(),
        "state": readiness_state,
        "label": readiness_label,
        "summary": " | ".join(part for part in evidence_parts if part),
        "history_summary": history_summary,
        "result_code": str(guidance.get("result_code", "") or "").strip(),
        "next_step": next_step,
        "fix_target": str(guidance.get("fix_target", "") or "").strip(),
        "auth_state": auth_state,
        "auth_source": auth_source,
    }


def workspace_connector_inventory(
    workspace_name: str,
    *,
    connector_ids: list[str],
    resolve_workspace_connector_binding: Callable[..., JsonDict],
    connector_status: Callable[..., JsonDict],
    history_payload_fn: Callable[[str], JsonDict],
    binding_validation_payload_fn: Callable[..., JsonDict],
    readiness_evidence_payload_fn: Callable[..., JsonDict],
    config_path: str | Path | None = None,
) -> list[JsonDict]:
    workspace = str(workspace_name or "").strip()
    rows: list[JsonDict] = []
    for connector_id in connector_ids:
        binding = resolve_workspace_connector_binding(workspace, connector_id, config_path=config_path)
        enabled, inherited = effective_binding_enabled(workspace, binding)
        provider = str(binding.get("provider", "") or "")
        item = connector_status(connector_id, provider=provider)
        history = history_payload_fn(connector_id)
        selected_account = str(binding.get("account_id", "") or "").strip().lower()
        validation = binding_validation_payload_fn(
            workspace,
            binding,
            item,
            enabled=enabled,
            inherited=inherited,
            provider=provider,
            account_id=selected_account,
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
        item["binding_validation"] = validation
        item["readiness"] = readiness_evidence_payload_fn(
            connector_id,
            item,
            history,
            validation,
            action_id="",
            provider=provider,
            account_id=selected_account,
        )
        rows.append(item)
    return rows


def get_workspace_connector_context(
    tool_name: str,
    workspace_name: str,
    *,
    connector_id_for_tool: Callable[[str], str],
    connector_action_for_tool: Callable[[str], str],
    resolve_workspace_connector_binding: Callable[..., JsonDict],
    connector_status: Callable[..., JsonDict],
    metadata: JsonDict | None = None,
    config_path: str | Path | None = None,
) -> JsonDict:
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
    binding_enabled, inherited = effective_binding_enabled(workspace_name, binding)
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


def workspace_tool_readiness(
    tool_name: str,
    workspace_name: str,
    *,
    get_workspace_connector_context_fn: Callable[..., JsonDict],
    history_payload_fn: Callable[[str], JsonDict],
    binding_validation_payload_fn: Callable[..., JsonDict],
    readiness_evidence_payload_fn: Callable[..., JsonDict],
    metadata: JsonDict | None = None,
    endpoint: str = "",
    config_path: str | Path | None = None,
) -> JsonDict:
    del endpoint
    context = get_workspace_connector_context_fn(
        tool_name,
        workspace_name,
        metadata=metadata,
        config_path=config_path,
    )
    connector_id = str(context.get("connector_id", "") or "").strip().lower()
    if not connector_id:
        return {
            **context,
            "history": {},
            "binding_validation": {
                "state": "not_applicable",
                "message": "No connector-specific binding evidence is required for this tool.",
            },
            "readiness": {
                "connector": "",
                "action_id": "",
                "state": "not_applicable",
                "label": "Workspace-governed tool; no connector readiness evidence is required.",
                "summary": "Evidence: workspace-governed tool; no connector readiness proof is required.",
                "history_summary": "No connector history is required.",
                "result_code": "",
                "next_step": "",
                "fix_target": "",
                "auth_state": "not_required",
                "auth_source": "none",
            },
        }

    binding = context.get("binding", {}) if isinstance(context.get("binding"), dict) else {}
    status = context.get("status", {}) if isinstance(context.get("status"), dict) else {}
    provider = str(context.get("provider", "") or "").strip().lower()
    account_id = str(context.get("account_id", "") or "").strip().lower()
    history = history_payload_fn(connector_id)
    validation = binding_validation_payload_fn(
        workspace_name,
        binding,
        status,
        enabled=bool(context.get("binding_enabled", False)),
        inherited=bool(context.get("binding_inherited", False)),
        provider=provider,
        account_id=account_id,
    )
    readiness = readiness_evidence_payload_fn(
        connector_id,
        status,
        history,
        validation,
        action_id=str(context.get("action_id", "") or "").strip().lower(),
        provider=provider,
        account_id=account_id,
    )
    return {
        **context,
        "history": history,
        "binding_validation": validation,
        "readiness": readiness,
    }


def evaluate_workspace_connector_policy(
    tool_name: str,
    workspace_name: str,
    *,
    get_workspace_connector_context_fn: Callable[..., JsonDict],
    metadata: JsonDict | None = None,
    endpoint: str = "",
    config_path: str | Path | None = None,
) -> tuple[bool, str, JsonDict]:
    context = get_workspace_connector_context_fn(
        tool_name,
        workspace_name,
        metadata=metadata,
        config_path=config_path,
    )
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

    def matches_endpoint_pattern(value: str, pattern: str) -> bool:
        candidate = str(pattern or "").strip().lower()
        if not candidate:
            return False
        if any(token in candidate for token in ("*", "?", "[")):
            return fnmatchcase(value, candidate)
        return value.startswith(candidate)

    if normalized_endpoint and endpoint_block and any(
        matches_endpoint_pattern(normalized_endpoint, pattern)
        for pattern in endpoint_block
    ):
        return False, f"Connector endpoint {normalized_endpoint} is blocked for {connector_id} in workspace {workspace_name}", {
            **context,
            "reason_code": "endpoint_block",
        }
    if normalized_endpoint and endpoint_allow:
        matches_allow = any(matches_endpoint_pattern(normalized_endpoint, pattern) for pattern in endpoint_allow)
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
