from __future__ import annotations

from typing import Any, Callable


JsonDict = dict[str, Any]


def record_action_result(
    connector_id: str,
    action: str,
    *,
    ok: bool,
    summary: str,
    provider: str = "",
    account_id: str = "",
    secret_key: str = "",
    status: JsonDict | None = None,
    guidance: JsonDict | None = None,
    load_state: Callable[[], JsonDict],
    save_state: Callable[[JsonDict], None],
    now_iso: Callable[[], str],
    new_event_id: Callable[[str], str],
    log_integration_event: Callable[[str, JsonDict], None],
    selected_provider_row: Callable[..., JsonDict],
    connector_guidance: Callable[..., JsonDict],
) -> None:
    state = load_state()
    connectors = state.get("connectors", {}) if isinstance(state.get("connectors"), dict) else {}
    previous = connectors.get(connector_id, {}) if isinstance(connectors.get(connector_id), dict) else {}
    status_payload = status if isinstance(status, dict) else {}
    selected_provider = str(provider or "").strip().lower()
    selected_provider_payload = selected_provider_row(status_payload, provider=selected_provider)
    guidance_payload = guidance if isinstance(guidance, dict) else connector_guidance(
        status_payload,
        provider=provider,
        account_id=account_id,
    )
    event_id = new_event_id(f"{connector_id}-{action}")
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
        "at": now_iso(),
        "auth_state": str(status_payload.get("auth_state", "") or ""),
        "auth_detail": str(status_payload.get("auth_detail", "") or ""),
        "missing_fields": list(selected_provider_payload.get("missing_fields", []))
        if isinstance(selected_provider_payload, dict)
        else [],
        "result_code": str(guidance_payload.get("result_code", "") or ""),
        "next_step": str(guidance_payload.get("next_step", "") or ""),
        "fix_target": str(guidance_payload.get("fix_target", "") or ""),
        "provider_auth_state": str(selected_provider_payload.get("auth_state", "") or ""),
        "verify_check_summary": str(selected_provider_payload.get("verify_check_summary", "") or ""),
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
        "last_verified_at": str(action_record.get("at", "") or "")
        if action == "verify"
        else str(previous.get("last_verified_at", "") or ""),
        "last_verify_summary": summary if action == "verify" else str(previous.get("last_verify_summary", "") or ""),
        "last_verify_event_id": event_id if action == "verify" else str(previous.get("last_verify_event_id", "") or ""),
        "last_verify_record": action_record if action == "verify" else previous.get("last_verify_record", {}),
    }
    connectors[connector_id] = next_payload
    state["connectors"] = connectors
    save_state(state)
    log_integration_event(
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
            "provider_auth_state": str(selected_provider_payload.get("auth_state", "") or ""),
            "verify_check_summary": str(selected_provider_payload.get("verify_check_summary", "") or ""),
        },
    )


def finalize_action_result(
    connector_id: str,
    action: str,
    *,
    ok: bool,
    summary: str,
    provider: str = "",
    account_id: str = "",
    secret_key: str = "",
    status: JsonDict | None = None,
    connector_guidance: Callable[..., JsonDict],
    record_action_result_fn: Callable[..., None],
    history_payload_fn: Callable[[str], JsonDict],
) -> JsonDict:
    status_payload = status if isinstance(status, dict) else {}
    guidance = connector_guidance(status_payload, provider=provider, account_id=account_id)
    record_action_result_fn(
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
    history = history_payload_fn(connector_id)
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
