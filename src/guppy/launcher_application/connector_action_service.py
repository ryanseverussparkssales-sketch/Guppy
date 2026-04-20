"""Connector action orchestration helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def _verify_connector_action(
    connector_id: str,
    *,
    provider: str,
    account_id: str,
    secret_key: str,
    connector_status_fn: Callable[..., dict[str, Any]],
    selected_provider_row_fn: Callable[[dict[str, Any], str], dict[str, Any]],
    finalize_action_result_fn: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    status = connector_status_fn(connector_id, provider=provider)
    if connector_id in {"crm", "voip"} and str(provider or "").strip():
        selected_provider = selected_provider_row_fn(status, provider=str(provider or "").strip().lower())
        verify_summary = str(selected_provider.get("verify_summary", "") or "").strip()
        selected_state = str(
            selected_provider.get("auth_state", status.get("auth_state", "missing")) or status.get("auth_state", "missing")
        )
        detail = str(selected_provider.get("scope_detail", "") or selected_provider.get("auth_detail", "") or "").strip()
        summary = verify_summary or f"{status.get('label', connector_id)} verify: {selected_state}"
        if detail:
            summary += f" | {detail}"
        ok = selected_state in {"ready", "optional"}
    else:
        summary = f"{status.get('label', connector_id)} verify: {status.get('auth_state', 'unknown')} | {status.get('auth_detail', '')}"
        ok = str(status.get("auth_state", "missing")) in {"ready", "optional"}
    return finalize_action_result_fn(
        connector_id,
        "verify",
        ok=ok,
        summary=summary,
        provider=provider,
        account_id=account_id,
        secret_key=secret_key,
        status=status,
    )


def _provider_connect_action(
    connector_id: str,
    *,
    provider: str,
    account_id: str,
    secret_key: str,
    secret_value: str,
    connector_status_fn: Callable[..., dict[str, Any]],
    selected_provider_row_fn: Callable[[dict[str, Any], str], dict[str, Any]],
    validate_secret_value_fn: Callable[[str, str], tuple[bool, str]],
    write_machine_secret_fn: Callable[[str, str], bool],
    secret_field_meta_fn: Callable[[str], dict[str, Any]],
    finalize_action_result_fn: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    connector_status_payload = connector_status_fn(connector_id, provider=provider)
    provider_rows = connector_status_payload.get("providers", []) if isinstance(connector_status_payload.get("providers"), list) else []
    selected_provider = selected_provider_row_fn(connector_status_payload, provider=str(provider or "").strip().lower())
    if provider_rows and not selected_provider:
        status = connector_status_fn(connector_id, provider=provider)
        return finalize_action_result_fn(
            connector_id,
            "connect",
            ok=False,
            summary=f"{connector_id} connect requires choosing a provider first.",
            provider=provider,
            account_id=account_id,
            secret_key=secret_key,
            status=status,
        )
    required_fields = list(selected_provider.get("required_fields", [])) if isinstance(selected_provider, dict) else []
    next_field = selected_provider.get("next_field", {}) if isinstance(selected_provider, dict) else {}
    resolved_secret_key = str(secret_key or "").strip()
    if not resolved_secret_key and isinstance(next_field, dict):
        resolved_secret_key = str(next_field.get("key", "") or "").strip()
    if not resolved_secret_key and len(required_fields) == 1:
        resolved_secret_key = str(required_fields[0] or "").strip()
    if not resolved_secret_key or not secret_value:
        missing_text = ", ".join(required_fields) or "a secret key and value"
        summary = f"{connector_id} connect requires {missing_text}."
        ok = False
    else:
        valid, validation_error = validate_secret_value_fn(resolved_secret_key, secret_value)
        if not valid:
            summary = validation_error
            ok = False
        else:
            stored = write_machine_secret_fn(resolved_secret_key, secret_value)
            ok = bool(stored)
            refreshed = connector_status_fn(connector_id, provider=provider)
            refreshed_provider = next(
                (
                    row for row in refreshed.get("providers", [])
                    if isinstance(row, dict) and str(row.get("id", "")).strip().lower() == str(provider or "").strip().lower()
                ),
                {},
            )
            remaining = list(refreshed_provider.get("missing_fields", [])) if isinstance(refreshed_provider, dict) else []
            field_meta = secret_field_meta_fn(resolved_secret_key)
            field_label = str(field_meta.get("label", resolved_secret_key) or resolved_secret_key)
            provider_label = str(refreshed_provider.get("label", provider or connector_id) or provider or connector_id)
            if stored:
                summary = f"Saved {field_label} for {provider_label}."
                if remaining:
                    next_label = str(secret_field_meta_fn(remaining[0]).get("label", remaining[0]) or remaining[0])
                    summary += f" Next required field: {next_label}."
                else:
                    summary += " All required fields are present; run verify to confirm readiness."
            else:
                summary = f"Could not persist {field_label} for {provider_label}; environment fallback remains unchanged."
    status = connector_status_fn(connector_id, provider=provider)
    return finalize_action_result_fn(
        connector_id,
        "connect",
        ok=ok,
        summary=summary,
        provider=provider,
        account_id=account_id,
        secret_key=resolved_secret_key,
        status=status,
    )


def _provider_disconnect_action(
    connector_id: str,
    *,
    provider: str,
    account_id: str,
    secret_key: str,
    connector_status_fn: Callable[..., dict[str, Any]],
    selected_provider_row_fn: Callable[[dict[str, Any], str], dict[str, Any]],
    clear_machine_secret_fn: Callable[[str], bool],
    finalize_action_result_fn: Callable[..., dict[str, Any]],
    env: dict[str, str],
) -> dict[str, Any]:
    connector_status_payload = connector_status_fn(connector_id, provider=provider)
    selected_provider = selected_provider_row_fn(connector_status_payload, provider=str(provider or "").strip().lower())
    required_fields = list(selected_provider.get("required_fields", [])) if isinstance(selected_provider, dict) else []
    keys_to_clear = [str(secret_key).strip()] if str(secret_key or "").strip() else [str(item) for item in required_fields if str(item).strip()]
    if not keys_to_clear:
        summary = f"{connector_id} disconnect requires a provider secret to clear."
        ok = False
    else:
        cleared_any = False
        still_present: list[str] = []
        for item in keys_to_clear:
            cleared_any = clear_machine_secret_fn(item) or cleared_any
            if env.get(item, "").strip():
                still_present.append(item)
        if cleared_any and not still_present:
            summary = f"Cleared {len(keys_to_clear)} stored secret(s) for {connector_id}."
        elif cleared_any and still_present:
            summary = (
                f"Cleared {len(keys_to_clear)} stored secret(s) for {connector_id}, "
                f"but env values are still present for {', '.join(still_present)}."
            )
        else:
            summary = f"No stored secrets were cleared for {connector_id}."
        ok = True
    status = connector_status_fn(connector_id, provider=provider)
    return finalize_action_result_fn(
        connector_id,
        "disconnect",
        ok=ok,
        summary=summary,
        provider=provider,
        account_id=account_id,
        secret_key=secret_key,
        status=status,
    )


def _gmail_action(
    action: str,
    *,
    account_id: str,
    reconnect: bool = False,
    token_path_for_gmail_account_fn: Callable[[str], Path],
) -> tuple[bool, str]:
    from src.guppy.tools.media import gmail_unread_count

    target_account = str(account_id or "main").strip().lower() or "main"
    if action == "disconnect":
        token_path = token_path_for_gmail_account_fn(target_account)
        if token_path.exists():
            token_path.unlink()
            return True, f"Removed cached Gmail token for account {target_account}."
        return True, f"No cached Gmail token found for account {target_account}."
    if reconnect:
        token_path = token_path_for_gmail_account_fn(target_account)
        if token_path.exists():
            token_path.unlink()
    count, err = gmail_unread_count(target_account)
    return (not bool(err), err or f"Gmail account {target_account} verified with {count} unread message(s).")


def _calendar_action(action: str, *, reconnect: bool = False) -> tuple[bool, str]:
    from src.guppy.tools.media import calendar_events

    token_path = Path.home() / ".guppy_calendar_token.json"
    if action == "disconnect":
        if token_path.exists():
            token_path.unlink()
            return True, "Removed cached Calendar token."
        return True, "No cached Calendar token found."
    if reconnect and token_path.exists():
        token_path.unlink()
    result = calendar_events(days=1, max_results=1, calendar_id="primary")
    summary = result.splitlines()[0] if result else "Calendar connect completed."
    lowered = summary.lower()
    return (not any(token in lowered for token in ("error", "failed", "missing", "not found")), summary)


def _spotify_action(action: str, *, reconnect: bool = False) -> tuple[bool, str]:
    from src.guppy.tools.media import spotify_current

    token_path = Path.home() / ".guppy_spotify_token"
    if action == "disconnect":
        if token_path.exists():
            token_path.unlink()
            return True, "Removed cached Spotify token."
        return True, "No cached Spotify token found."
    if reconnect and token_path.exists():
        token_path.unlink()
    result = spotify_current()
    summary = result.splitlines()[0] if result else "Spotify connect completed."
    lowered = summary.lower()
    return (not any(token in lowered for token in ("requires spotify api", "error", "failed", "missing", "not found")), summary)


def run_connector_action(
    connector_id: str,
    action: str,
    *,
    provider: str = "",
    account_id: str = "",
    secret_key: str = "",
    secret_value: str = "",
    connector_status_fn: Callable[..., dict[str, Any]],
    selected_provider_row_fn: Callable[[dict[str, Any], str], dict[str, Any]],
    validate_secret_value_fn: Callable[[str, str], tuple[bool, str]],
    write_machine_secret_fn: Callable[[str, str], bool],
    clear_machine_secret_fn: Callable[[str], bool],
    secret_field_meta_fn: Callable[[str], dict[str, Any]],
    finalize_action_result_fn: Callable[..., dict[str, Any]],
    token_path_for_gmail_account_fn: Callable[[str], Path],
    env: dict[str, str],
) -> dict[str, Any]:
    normalized_connector = str(connector_id or "").strip().lower()
    normalized_action = str(action or "").strip().lower()

    if normalized_action == "verify":
        return _verify_connector_action(
            normalized_connector,
            provider=provider,
            account_id=account_id,
            secret_key=secret_key,
            connector_status_fn=connector_status_fn,
            selected_provider_row_fn=selected_provider_row_fn,
            finalize_action_result_fn=finalize_action_result_fn,
        )

    if normalized_connector in {"youtube", "crm", "voip"} and normalized_action == "connect":
        return _provider_connect_action(
            normalized_connector,
            provider=provider,
            account_id=account_id,
            secret_key=secret_key,
            secret_value=secret_value,
            connector_status_fn=connector_status_fn,
            selected_provider_row_fn=selected_provider_row_fn,
            validate_secret_value_fn=validate_secret_value_fn,
            write_machine_secret_fn=write_machine_secret_fn,
            secret_field_meta_fn=secret_field_meta_fn,
            finalize_action_result_fn=finalize_action_result_fn,
        )

    if normalized_connector in {"youtube", "crm", "voip"} and normalized_action == "disconnect":
        return _provider_disconnect_action(
            normalized_connector,
            provider=provider,
            account_id=account_id,
            secret_key=secret_key,
            connector_status_fn=connector_status_fn,
            selected_provider_row_fn=selected_provider_row_fn,
            clear_machine_secret_fn=clear_machine_secret_fn,
            finalize_action_result_fn=finalize_action_result_fn,
            env=env,
        )

    try:
        if normalized_connector == "gmail":
            ok, summary = _gmail_action(
                normalized_action,
                account_id=account_id,
                reconnect=normalized_action == "reconnect",
                token_path_for_gmail_account_fn=token_path_for_gmail_account_fn,
            )
        elif normalized_connector == "calendar":
            ok, summary = _calendar_action(normalized_action, reconnect=normalized_action == "reconnect")
        elif normalized_connector == "spotify":
            ok, summary = _spotify_action(normalized_action, reconnect=normalized_action == "reconnect")
        else:
            ok = False
            summary = f"Action {normalized_action} is not supported for connector {normalized_connector}."
    except Exception as exc:
        ok = False
        summary = f"{normalized_connector} {normalized_action} failed: {exc}"

    status = connector_status_fn(normalized_connector, provider=provider)
    return finalize_action_result_fn(
        normalized_connector,
        normalized_action,
        ok=ok,
        summary=summary,
        provider=provider,
        account_id=account_id,
        secret_key=secret_key,
        status=status,
    )
