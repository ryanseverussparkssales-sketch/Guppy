"""Presenter helpers for App Mgmt status, context, and automation copy."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .windows_ops_presenter import build_windows_gate_followup_line, build_windows_handoff_line
from .windows_ops_runtime import latest_runtime_artifact


@dataclass(frozen=True, slots=True)
class DailyContextState:
    activity_text: str
    workspace_text: str
    runtime_text: str
    route_text: str
    recovery_text: str
    recovery_ok: bool


@dataclass(frozen=True, slots=True)
class StatusSnapshotState:
    health_text: str
    voice_text: str
    route_health_text: str
    resource_text: str
    windows_runtime_text: str


@dataclass(frozen=True, slots=True)
class InstanceSnapshotState:
    instances_text: str


@dataclass(frozen=True, slots=True)
class AutomationSnapshotState:
    workspace_text: str
    queue_text: str
    staged_text: str
    result_text: str
    approval_text: str
    report_text: str
    evidence_text: str
    stress_text: str
    recent_text: str
    validation_text: str
    status_text: str


@dataclass(frozen=True, slots=True)
class ConnectorSelectorOption:
    label: str
    value: str


@dataclass(frozen=True, slots=True)
class ConnectorActionButtonState:
    text: str
    visible: bool
    enabled: bool
    tooltip: str


@dataclass(frozen=True, slots=True)
class ConnectorInventoryState:
    provider_options: tuple[ConnectorSelectorOption, ...]
    selected_provider: str
    account_options: tuple[ConnectorSelectorOption, ...]
    selected_account: str
    secret_field_options: tuple[ConnectorSelectorOption, ...]
    selected_secret_key: str
    state_text: str
    auth_text: str
    detail_text: str
    validation_text: str
    scope_text: str
    setup_text: str
    next_step_text: str
    history_text: str
    recent_text: str
    secret_text: str
    secret_placeholder: str
    secret_masked: bool
    button_states: dict[str, ConnectorActionButtonState]


def _clean_guidance_text(text: str) -> str:
    cleaned = str(text or "").strip()
    replacements = (
        ("App Mgmt:", ""),
        ("Workspaces >", ""),
        ("App Mgmt >", ""),
    )
    for old, new in replacements:
        cleaned = cleaned.replace(old, new)
    return " ".join(cleaned.split())


def _service_purpose(connector_id: str) -> str:
    return {
        "gmail": "Email",
        "calendar": "Calendar",
        "spotify": "Music",
        "youtube": "Video tools",
        "crm": "Customer records",
        "voip": "Calling",
    }.get(str(connector_id or "").strip().lower(), "Connected service")


def _friendly_auth_state(auth_state: str) -> str:
    normalized = str(auth_state or "").strip().lower()
    return {
        "ready": "Connected",
        "optional": "Optional",
        "partial": "Almost ready",
        "missing": "Needs setup",
    }.get(normalized, "Needs setup")


def _selector_label(item: Mapping[str, object], *, fallback: str) -> str:
    label = str(item.get("label", item.get("id", fallback)) or fallback).strip() or fallback
    auth_state = str(item.get("auth_state", "") or "").strip().upper()
    if auth_state:
        label += f" [{auth_state}]"
    return label


def _history_line(history: Mapping[str, object]) -> str:
    last_action = str(history.get("last_action", "") or "").strip()
    last_action_at = str(history.get("last_action_at", "") or "").strip()
    last_result = str(history.get("last_result", "") or "").strip()
    last_event_id = str(history.get("last_event_id", "") or "").strip()
    if not last_action:
        return "History: no connector action has been recorded yet."
    summary = f"History: last {last_action}"
    if last_action_at:
        summary += f" @ {last_action_at}"
    if last_result:
        summary += f" | {last_result}"
    if last_event_id:
        summary += f" | Ref: {last_event_id}"
    return summary


def _recent_history_line(history: Mapping[str, object]) -> str:
    recent_summary = str(history.get("recent_summary", "") or "").strip()
    if recent_summary:
        return "Recent attempts: " + recent_summary
    timeline = [item for item in history.get("timeline", []) if isinstance(item, dict)] if isinstance(history.get("timeline"), list) else []
    if not timeline:
        return "Recent attempts: none recorded yet."
    rendered: list[str] = []
    for item in timeline[-3:]:
        action = str(item.get("action", "action") or "action").strip()
        result = str(item.get("result", item.get("status", "")) or "").strip()
        when = str(item.get("timestamp", item.get("at", "")) or "").strip()
        bit = action
        if result:
            bit += f"={result}"
        if when:
            bit += f" @ {when}"
        rendered.append(bit)
    return "Recent attempts: " + " | ".join(rendered)


def _provider_field_details(payload: Mapping[str, object]) -> list[dict[str, object]]:
    field_details = payload.get("field_details", [])
    return [row for row in field_details if isinstance(row, dict)] if isinstance(field_details, list) else []


def _provider_secret_fields(payload: Mapping[str, object], item: Mapping[str, object]) -> list[str]:
    provider_field_details = _provider_field_details(payload)
    fields = [
        str(row.get("key", "")).strip()
        for row in provider_field_details
        if str(row.get("key", "")).strip()
    ]
    if fields:
        return fields
    required_fields = payload.get("required_fields", [])
    if isinstance(required_fields, list):
        fields = [str(row).strip() for row in required_fields if str(row).strip()]
    if fields:
        return fields
    secret_fields = item.get("secret_fields", [])
    return [str(row).strip() for row in secret_fields if str(row).strip()] if isinstance(secret_fields, list) else []


def build_connector_inventory_state(
    item: Mapping[str, object] | None,
    *,
    previous_provider: str = "",
    previous_account: str = "",
    previous_secret_key: str = "",
    fallback_connector_id: str = "",
) -> ConnectorInventoryState:
    payload = item if isinstance(item, Mapping) else {}
    providers = [row for row in payload.get("providers", []) if isinstance(row, dict)] if isinstance(payload.get("providers"), list) else []
    accounts = [row for row in payload.get("accounts", []) if isinstance(payload.get("accounts"), list) and isinstance(row, dict)] if isinstance(payload.get("accounts"), list) else []
    history = payload.get("history", {}) if isinstance(payload.get("history"), Mapping) else {}
    scope = payload.get("scope_telemetry", {}) if isinstance(payload.get("scope_telemetry"), Mapping) else {}

    selected_provider_payload = next(
        (row for row in providers if str(row.get("id", "")).strip().lower() == str(previous_provider).strip().lower()),
        providers[0] if providers else {},
    )
    selected_account_payload = next(
        (row for row in accounts if str(row.get("id", "")).strip().lower() == str(previous_account).strip().lower()),
        accounts[0] if accounts else {},
    )
    provider_field_details = _provider_field_details(selected_provider_payload)
    secret_fields = _provider_secret_fields(selected_provider_payload, payload)
    default_secret_key = str(selected_provider_payload.get("next_field", {}).get("key", "") or "").strip() if isinstance(selected_provider_payload, Mapping) else ""
    if default_secret_key and default_secret_key in secret_fields:
        selected_secret_key = default_secret_key
    elif previous_secret_key and previous_secret_key in secret_fields:
        selected_secret_key = previous_secret_key
    else:
        selected_secret_key = secret_fields[0] if secret_fields else ""

    selected_field_detail = next(
        (row for row in provider_field_details if str(row.get("key", "")).strip() == selected_secret_key),
        {},
    )
    selected_provider = str(selected_provider_payload.get("id", "") or "").strip()
    selected_account = str(selected_account_payload.get("id", "") or "").strip()

    connector_id = str(payload.get("id", fallback_connector_id) or fallback_connector_id).strip().lower()
    auth_kind = str(payload.get("auth_kind", "unknown") or "unknown")
    auth_state = str(payload.get("auth_state", "unknown") or "unknown").upper()
    detail = str(payload.get("auth_detail", "") or "").strip()
    connector_label = str(payload.get("label", connector_id or "Service") or connector_id or "Service")
    purpose = _service_purpose(connector_id)

    validation_bits: list[str] = []
    if providers:
        if selected_provider_payload:
            validation_bits.append(str(selected_provider_payload.get("auth_detail", "") or "").strip())
            setup_summary = str(selected_provider_payload.get("setup_summary", "") or "").strip()
            if setup_summary:
                validation_bits.append(setup_summary)
            verify_summary = str(selected_provider_payload.get("verify_summary", "") or "").strip()
            if verify_summary:
                validation_bits.append(verify_summary)
            verify_check_summary = str(selected_provider_payload.get("verify_check_summary", "") or "").strip()
            if verify_check_summary:
                validation_bits.append("Checks: " + verify_check_summary)
        else:
            validation_bits.append("Choose a provider before you save or verify this connector.")
    if accounts:
        if selected_account_payload:
            validation_bits.append(str(selected_account_payload.get("auth_detail", "") or "").strip())
        else:
            validation_bits.append("Choose which account you want to use on this PC.")
    if not validation_bits:
        validation_bits.append(detail or "This service is ready to review.")

    endpoint_prefixes = [str(entry).strip() for entry in scope.get("endpoint_prefixes", []) if str(entry).strip()] if isinstance(scope.get("endpoint_prefixes"), list) else []
    scope_summary = str(scope.get("summary", "") or "").strip()
    selected_scope = str(selected_provider_payload.get("scope_label", "") or selected_account_payload.get("label", "") or "").strip()
    rendered_scope = selected_scope or scope_summary or "No explicit scope guidance is available."
    provider_scope_detail = str(selected_provider_payload.get("scope_detail", "") or "").strip()
    if provider_scope_detail:
        rendered_scope += f" | {provider_scope_detail}"
    if endpoint_prefixes:
        rendered_scope += f" | {len(endpoint_prefixes[:3])} machine actions available"

    if provider_field_details:
        present_count = len([row for row in provider_field_details if bool(row.get("present", False))])
        total_count = len(provider_field_details)
        next_field = selected_provider_payload.get("next_field", {}) if isinstance(selected_provider_payload, Mapping) else {}
        next_label = str(next_field.get("label", next_field.get("key", "")) or next_field.get("key", "")).strip()
        next_hint = str(next_field.get("validation_hint", "") or next_field.get("input_hint", "") or "").strip()
        setup_text = f"Saved details: {present_count}/{total_count} ready"
        if next_label and present_count < total_count:
            setup_text += f" | Next: add {next_label}"
        if next_hint:
            setup_text += f" | {next_hint}"
    elif secret_fields:
        setup_text = "Saved details: choose the detail you want to save, then test the connection."
    else:
        setup_text = "Saved details: this service mostly uses account selection or browser sign-in."

    next_step = str(selected_provider_payload.get("next_step", "") or payload.get("next_step", "") or "").strip()
    fix_target = str(selected_provider_payload.get("fix_target", "") or payload.get("fix_target", "") or "").strip()
    next_step_text = (
        "Next step: " + _clean_guidance_text(next_step) + (f" | Change it in {fix_target}" if fix_target else "")
        if next_step
        else "Next step: choose a service or test the current connection."
    )
    if auth_kind == "oauth_file_token" and auth_state == "MISSING":
        next_step_text = (
            f"Next step: add the downloaded {connector_label.lower()} credentials JSON on this PC before browser sign-in can start."
        )

    if provider_field_details:
        field_summary = ", ".join(
            f"{str(row.get('label', row.get('key', 'field')))}={'READY' if bool(row.get('present', False)) else 'MISSING'}"
            for row in provider_field_details
        )
        secret_text = "Saved details: " + (field_summary or "none")
    else:
        secret_text = "Saved details: " + (", ".join(secret_fields) if secret_fields else "none")

    secret_placeholder = "secret value for API-key or provider-backed connectors"
    secret_masked = True
    if selected_field_detail:
        secret_placeholder = str(
            selected_field_detail.get("placeholder")
            or selected_field_detail.get("input_hint")
            or secret_placeholder
        ).strip() or secret_placeholder
        secret_masked = bool(selected_field_detail.get("masked", True))

    actions = {str(action).strip() for action in payload.get("actions_supported", []) if str(action).strip()} if isinstance(payload.get("actions_supported"), list) else set()
    provider_required = bool(providers)
    provider_selected = bool(selected_provider_payload) or not provider_required
    action_text = {
        "verify": "VERIFY",
        "connect": "CONNECT",
        "reconnect": "RECONNECT",
        "disconnect": "DISCONNECT",
        "save_secret": "SAVE SECRET",
        "clear_secret": "CLEAR SECRET",
    }
    if auth_kind == "api_key":
        action_text.update({"verify": "TEST KEY", "connect": "SAVE KEY", "reconnect": "RECONNECT", "disconnect": "REMOVE KEY"})
    elif auth_kind == "oauth_file_token":
        action_text.update({"verify": "CHECK SIGN-IN", "connect": "SIGN IN", "reconnect": "SIGN IN AGAIN", "disconnect": "REMOVE SIGN-IN"})
    elif auth_kind in {"provider_secret", "oauth_secret"}:
        action_text.update({"verify": "CHECK SETUP", "connect": "SAVE DETAILS", "reconnect": "RECONNECT", "disconnect": "CLEAR DETAILS"})

    button_states: dict[str, ConnectorActionButtonState] = {}
    for action_name in ("verify", "connect", "reconnect", "disconnect", "save_secret", "clear_secret"):
        resolved_action = "connect" if action_name == "save_secret" else "disconnect" if action_name == "clear_secret" else action_name
        enabled = resolved_action in actions
        if action_name in {"save_secret", "clear_secret"}:
            enabled = enabled and bool(secret_fields)
        enabled = enabled and provider_selected
        if auth_kind == "api_key" and action_name in {"connect", "reconnect"}:
            visible = False
        elif auth_kind == "provider_secret" and action_name == "reconnect":
            visible = False
        elif auth_kind == "oauth_file_token" and auth_state == "MISSING" and action_name in {"connect", "reconnect"}:
            visible = False
        else:
            visible = True
        if enabled:
            tooltip = ""
        elif provider_required and not provider_selected:
            tooltip = "Choose a provider from the inventory before running connector actions."
        else:
            tooltip = f"{connector_id or 'connector'} does not support {resolved_action}."
        button_states[action_name] = ConnectorActionButtonState(
            text=action_text[action_name],
            visible=visible,
            enabled=enabled,
            tooltip=tooltip,
        )

    return ConnectorInventoryState(
        provider_options=tuple(
            ConnectorSelectorOption(_selector_label(value, fallback="(provider)"), str(value.get("id", "")))
            for value in providers
        ),
        selected_provider=selected_provider,
        account_options=tuple(
            ConnectorSelectorOption(_selector_label(value, fallback="(account)"), str(value.get("id", "")))
            for value in accounts
        ),
        selected_account=selected_account,
        secret_field_options=tuple(ConnectorSelectorOption(field, field) for field in secret_fields),
        selected_secret_key=selected_secret_key,
        state_text=f"{connector_label} helps with {purpose.lower()} on this PC.",
        auth_text=f"Connection status: {_friendly_auth_state(auth_state)}",
        detail_text=_clean_guidance_text(detail or f"Choose {connector_label} to see how to connect it."),
        validation_text="What to do next: " + " | ".join(_clean_guidance_text(bit) for bit in validation_bits if bit),
        scope_text=f"What it can help with: {_clean_guidance_text(rendered_scope)}",
        setup_text=setup_text,
        next_step_text=next_step_text,
        history_text=_history_line(history),
        recent_text=_recent_history_line(history),
        secret_text=secret_text,
        secret_placeholder=secret_placeholder,
        secret_masked=secret_masked,
        button_states=button_states,
    )


def validate_connector_action(
    item: Mapping[str, object] | None,
    action: str,
    *,
    selected_provider_id: str = "",
    selected_secret_key: str = "",
    secret_value: str = "",
) -> str:
    payload = item if isinstance(item, Mapping) else {}
    connector_id = str(payload.get("id", "") or "").strip().lower()
    providers = [row for row in payload.get("providers", []) if isinstance(row, dict)] if isinstance(payload.get("providers"), list) else []
    provider_payload = next(
        (row for row in providers if str(row.get("id", "")).strip().lower() == str(selected_provider_id).strip().lower()),
        {},
    )
    if providers and not provider_payload:
        return "Choose a provider from the connector inventory before running this action."
    if action in {"connect", "save_secret"}:
        field_details = _provider_field_details(provider_payload)
        needs_secret = bool(field_details) or bool(_provider_secret_fields(provider_payload, payload))
        if needs_secret and not selected_secret_key:
            return "Choose which provider field you want to save before continuing."
        if selected_secret_key and not str(secret_value or "").strip():
            selected_field = next(
                (row for row in field_details if str(row.get("key", "")).strip() == selected_secret_key),
                {},
            )
            field_label = str(selected_field.get("label", selected_secret_key) or selected_secret_key).strip() or selected_secret_key
            return f"Enter a value for {field_label} before saving it."
    if action == "reconnect" and connector_id in {"crm", "voip", "youtube"}:
        return f"{connector_id} does not expose reconnect in this guided secret flow."
    return ""


def build_windows_ops_snapshot(
    root: Path,
    *,
    configured_backend: str,
    launcher_python: str,
) -> dict[str, str]:
    runtime_dir = root / "runtime"
    config_dir = root / "config"
    settings_path = runtime_dir / "app_settings.json"
    launcher_events = runtime_dir / "launcher_events.jsonl"
    state_path = runtime_dir / "windows_ops_state.json"
    venv_python = root / ".venv" / "Scripts" / "python.exe"
    supervisor_script = root / "bin" / "launch_api_supervised.bat"
    build_script = root / "bin" / "build_executable.bat"
    repair_file = runtime_dir / "repair_token.txt"
    latest_bundle = latest_runtime_artifact(runtime_dir, "diagnostics_bundle_*.json", "diagnostics_*.json")
    latest_bundle_text = str(latest_bundle) if latest_bundle is not None else "none yet"
    install_bits = [
        f"Launcher python: {launcher_python}",
        f"Repo python: {'present' if venv_python.exists() else 'missing'}",
        f"Ollama CLI: {'found' if shutil.which('ollama') else 'missing'}",
        f"Lemonade CLI: {'found' if shutil.which('lemonade') else 'missing'}",
        f"Supervisor script: {'ready' if supervisor_script.exists() else 'missing'}",
        f"Packager: {'ready' if build_script.exists() else 'missing'}",
    ]

    repair_hint = (
        "keyring-backed first; file fallback present"
        if repair_file.exists()
        else "keyring-backed first; file fallback not present"
    )
    state_payload: dict[str, object] = {}
    if state_path.exists():
        try:
            parsed = json.loads(state_path.read_text(encoding="utf-8"))
            state_payload = parsed if isinstance(parsed, dict) else {}
        except Exception:
            state_payload = {}
    last_action = str(state_payload.get("action", "") or "").strip()
    last_timestamp = str(state_payload.get("timestamp", "") or "").strip()
    last_summary = str(state_payload.get("summary", "") or "").strip()
    last_changes = str(state_payload.get("changes", "") or "").strip()
    last_phase = str(state_payload.get("phase", "") or "").strip().lower()
    last_event_id = str(state_payload.get("event_id", "") or "").strip()
    next_step = str(state_payload.get("next_step", "") or "").strip()
    fix_target = str(state_payload.get("fix_target", "") or "").strip()
    docs_hint = str(state_payload.get("docs_hint", "") or "").strip()
    entry_point = str(state_payload.get("entry_point", "") or "").strip()
    steps_completed = state_payload.get("steps_completed")
    steps_total = state_payload.get("steps_total")
    ok = bool(state_payload.get("ok", False))
    artifacts = (
        [item for item in state_payload.get("artifacts", []) if isinstance(item, dict)]
        if isinstance(state_payload.get("artifacts"), list)
        else []
    )
    receipt_path = str(state_payload.get("release_receipt", "") or "").strip()
    summary_path = str(state_payload.get("release_summary", "") or "").strip()
    gate_summary = str(state_payload.get("gate_summary", "") or "").strip()
    gate_detail = str(state_payload.get("gate_detail", "") or "").strip()
    gate_recommendations = (
        [str(item).strip() for item in state_payload.get("gate_recommendations", []) if str(item).strip()]
        if isinstance(state_payload.get("gate_recommendations"), list)
        else []
    )
    gate_recommendation_details = (
        [item for item in state_payload.get("gate_recommendation_details", []) if isinstance(item, dict)]
        if isinstance(state_payload.get("gate_recommendation_details"), list)
        else []
    )
    review_order = (
        [str(item).strip() for item in state_payload.get("review_order", []) if str(item).strip()]
        if isinstance(state_payload.get("review_order"), list)
        else []
    )
    step_text = (
        f" | Steps: {int(steps_completed or 0)}/{int(steps_total or 0)}"
        if steps_completed is not None and steps_total is not None
        else ""
    )
    phase_text = f" | Phase: {last_phase}" if last_phase else ""
    ref_text = f" | Ref: {last_event_id}" if last_event_id else ""
    return {
        "install": "Installed on this PC: " + " | ".join(install_bits),
        "runtime": f"Local AI runtime: {configured_backend} | Live backend: waiting for first status poll",
        "paths": f"Data locations: runtime={runtime_dir} | config={config_dir} | settings={settings_path}",
        "repair": f"Repair help: {repair_hint} | API relaunch: {supervisor_script}",
        "update": (
            "Update steps: python -m pip install -r requirements.txt | "
            "optional extras: python -m pip install -r requirements-optional.txt | "
            "postflight: python tools/validate_build_checks.py + python tools/verify_ollama_runtime.py --prompt ok | "
            "daily launcher: python src/guppy/cli/launch.py launcher"
        ),
        "diagnostics": (
            f"Diagnostics: launcher log={launcher_events} | latest bundle={latest_bundle_text} | "
            "runtime check: python tools/verify_ollama_runtime.py --prompt ok"
        ),
        "entry": (
            "Useful entry points: launcher=python src/guppy/cli/launch.py launcher | "
            "package=bin/build_executable.bat --no-clean | "
            f"supervisor={supervisor_script}"
        ),
        "next": (
            "Recommended next step: "
            + (
                next_step
                + (f" | Fix in: {fix_target}" if fix_target else "")
                + (f" | Doc: {docs_hint}" if docs_hint else "")
                + (f" | Command: {entry_point}" if entry_point else "")
            )
            if next_step
            else "Recommended next step: choose VERIFY, UPDATE, PACKAGE, RELEASE DRY RUN, SUPERVISED API, RESTART, or REPAIR."
        ),
        "service": (
            f"Recent service action: {last_action} @ {last_timestamp} | {'OK' if ok else 'CHECK'} | {last_summary}{phase_text}{step_text}{ref_text}"
            if last_action
            else "Recent service action: none recorded yet"
        ),
        "changes": f"Recent changes: {last_changes or 'No service summary recorded yet.'}",
        "gate": "Release check: "
        + (gate_summary + (f" | {gate_detail}" if gate_detail else "") if gate_summary else "no dry-run result recorded yet."),
        "gate_fix": build_windows_gate_followup_line(
            gate_summary,
            gate_recommendations,
            gate_recommendation_details,
        ),
        "handoff": build_windows_handoff_line(
            artifacts,
            receipt_path=receipt_path,
            summary_path=summary_path,
            review_order=review_order,
            root=root,
        ),
    }


def build_daily_context_state(
    *,
    activity: str = "",
    workspace: str = "",
    runtime: str = "",
    route: str = "",
    recovery: str = "",
    recovery_ok: bool = True,
) -> DailyContextState:
    activity_msg = (activity or "launcher ready").strip() or "launcher ready"
    workspace_msg = (workspace or "workspace context unavailable").strip() or "workspace context unavailable"
    runtime_msg = (runtime or "runtime details unavailable").strip() or "runtime details unavailable"
    route_msg = (route or "route preview unavailable").strip() or "route preview unavailable"
    recovery_msg = (recovery or "Recovery: all clear").strip() or "Recovery: all clear"
    return DailyContextState(
        activity_text=f"Recent activity: {activity_msg}",
        workspace_text=workspace_msg,
        runtime_text=runtime_msg if ":" in runtime_msg else f"Ready now: {runtime_msg}",
        route_text=route_msg,
        recovery_text=recovery_msg,
        recovery_ok=recovery_ok,
    )


def build_status_snapshot_state(
    payload: Mapping[str, object] | None,
    *,
    configured_backend: str,
    previous_windows_runtime: str = "",
) -> StatusSnapshotState:
    source = payload if isinstance(payload, Mapping) else {}
    api_state = str(source.get("status", "unknown") or "unknown").upper()
    startup = source.get("startup_readiness", {})
    startup_overall = "UNKNOWN"
    if isinstance(startup, Mapping):
        startup_overall = str(startup.get("overall", startup.get("status", "unknown")) or "unknown").upper()

    voice_tts = str(source.get("voice_tts_backend", "unknown") or "unknown")
    voice_stt = str(source.get("voice_stt_backend", "unknown") or "unknown")
    binding = str(source.get("voice_binding", "") or "").strip()

    route_evidence = str(source.get("route_evidence", "") or "").strip()
    route_text = f"Why the next route was chosen: {route_evidence or 'waiting for the next route preview'}"

    resource_text = "System headroom: unknown"
    envelope = source.get("resource_envelope", {})
    if isinstance(envelope, Mapping):
        state = str(envelope.get("state", "unknown") or "unknown")
        detail = str(envelope.get("message", envelope.get("detail", "")) or "").strip()
        resource_text = f"System headroom: {state}" + (f" | {detail}" if detail else "")

    windows_runtime_text = previous_windows_runtime
    local_runtime = source.get("local_runtime", {})
    if isinstance(local_runtime, Mapping):
        live_backend = str(local_runtime.get("backend", configured_backend.lower()) or configured_backend).strip().upper()
        live_state = str(local_runtime.get("state", "unknown") or "unknown").strip().upper()
        live_detail = str(local_runtime.get("detail", "") or "").strip()
        windows_runtime_text = (
            f"Local AI runtime: {configured_backend} | Live backend: {live_backend} | Status: {live_state}"
            + (f" | {live_detail}" if live_detail else "")
        )

    return StatusSnapshotState(
        health_text=f"API health: {api_state} | Startup readiness: {startup_overall}",
        voice_text=f"Voice services: tts={voice_tts} | stt={voice_stt}" + (f" | {binding}" if binding else ""),
        route_health_text=route_text,
        resource_text=resource_text,
        windows_runtime_text=windows_runtime_text,
    )


def build_instance_snapshot_state(payload: Mapping[str, object] | None) -> InstanceSnapshotState:
    source = payload if isinstance(payload, Mapping) else {}
    limits = source.get("limits", {})
    configured = int(limits.get("configured", 0) or 0) if isinstance(limits, Mapping) else 0
    max_configured = int(limits.get("max_configured", 5) or 5) if isinstance(limits, Mapping) else 5
    active_runtime = int(limits.get("active_runtime", 0) or 0) if isinstance(limits, Mapping) else 0
    max_active_runtime = int(limits.get("max_active_runtime", 2) or 2) if isinstance(limits, Mapping) else 2
    active_instance = str(source.get("active_instance", "-") or "-")
    return InstanceSnapshotState(
        instances_text=(
            f"Workspaces: active={active_instance} | configured {configured}/{max_configured} | "
            f"live {active_runtime}/{max_active_runtime}"
        )
    )


def build_automation_snapshot_state(payload: Mapping[str, object] | None) -> AutomationSnapshotState:
    source = payload if isinstance(payload, Mapping) else {}
    workspace = str(source.get("workspace", "") or "").strip()
    queue_counts = str(source.get("queue_counts", "") or "").strip()
    staged_file = str(source.get("staged_file", "") or "").strip()
    result_path = str(source.get("result_path", "") or "").strip()
    approval_state = str(source.get("approval_state", "") or "").strip()
    report_path = str(source.get("report_path", "") or "runtime/offhours_builder_report.json").strip()
    evidence_pack_path = str(source.get("evidence_pack_path", "") or "runtime/user_test_evidence.md").strip()
    stress_report_path = str(source.get("stress_report_path", "") or "").strip()
    recent_events = str(source.get("recent_events", "") or "").strip()
    validation_command = str(source.get("validation_command", "") or "").strip()
    status = str(source.get("status", "") or "").strip()
    return AutomationSnapshotState(
        workspace_text=workspace or "Workspace step: active workspace telemetry is not available yet.",
        queue_text=queue_counts or "Queue counts: builder queue status is not available yet.",
        staged_text=staged_file or "Latest staged output: nothing is waiting for approval yet.",
        result_text=result_path or "Latest result: no approved builder output has been recorded yet.",
        approval_text=approval_state or "Latest approval: no staged task is awaiting approval yet.",
        report_text=f"Builder report: {report_path}",
        evidence_text=f"Evidence pack: {evidence_pack_path}",
        stress_text=(
            f"Latest stress run: {stress_report_path}"
            if stress_report_path
            else "Latest stress run: no stress report recorded yet."
        ),
        recent_text=recent_events or "Recent operator notes: no recent launcher notes recorded yet.",
        validation_text=(
            f"Validation command: {validation_command}"
            if validation_command
            else "Validation command: unavailable"
        ),
        status_text=status,
    )
