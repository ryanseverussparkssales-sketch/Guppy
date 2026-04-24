from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.guppy.launcher_application.provider_registry import get_example_prompt, get_provider
from src.guppy.workspace_governance import secret_field_meta


@dataclass(frozen=True)
class ConnectorBrand:
    badge: str
    accent: str
    wash: str


@dataclass(frozen=True)
class ConnectorCardSpec:
    connector_id: str
    button_text: str
    ready: bool
    brand: ConnectorBrand


@dataclass(frozen=True)
class ConnectorPanelState:
    current_auth_kind: str
    status_text: str
    detail_text: str
    step_text: str
    next_step_hint: str
    connect_text: str
    save_text: str
    verify_text: str
    disconnect_text: str
    show_connect: bool
    show_save: bool
    show_verify: bool
    show_disconnect: bool
    connect_enabled: bool
    save_enabled: bool
    verify_enabled: bool
    disconnect_enabled: bool
    connect_tooltip: str
    save_tooltip: str
    verify_tooltip: str
    disconnect_tooltip: str


@dataclass(frozen=True)
class DeviceAccountsDensityState:
    desktop_action_labels: tuple[str, ...]
    connect_text: str
    save_text: str
    verify_text: str
    disconnect_text: str


def connector_brand(connector_id: str) -> ConnectorBrand:
    normalized = str(connector_id or "").strip().lower()
    brands: dict[str, ConnectorBrand] = {
        "gmail": ConnectorBrand(badge="G", accent="#d74f3f", wash="#fff1ed"),
        "youtube": ConnectorBrand(badge=">", accent="#e64b3c", wash="#fff0ee"),
        "spotify": ConnectorBrand(badge="S", accent="#1f8f55", wash="#eefaf2"),
        "outlook": ConnectorBrand(badge="O", accent="#2f6df6", wash="#eef4ff"),
    }
    return brands.get(normalized, ConnectorBrand(badge="#", accent="#e58a2b", wash="#f7f2ea"))


def service_purpose(connector_id: str) -> str:
    return {
        "gmail": "Email",
        "calendar": "Calendar",
        "spotify": "Music",
        "youtube": "Video tools",
        "crm": "Customer records",
        "voip": "Calling",
    }.get(str(connector_id or "").strip().lower(), "Connected service")


def auth_state_text(auth_state: str) -> str:
    normalized = str(auth_state or "").strip().lower()
    return {
        "ready": "Connected",
        "optional": "Optional",
        "partial": "Finish setup",
        "missing": "Needs setup",
    }.get(normalized, "Needs setup")


def _normalized_storage_posture(payload: dict[str, object]) -> str:
    posture = str(payload.get("storage_posture", "") or "").strip().lower()
    if posture:
        return posture
    source = str(payload.get("source", "") or "").strip().lower()
    return {
        "keyring": "keyring",
        "env": "env_only",
        "mixed": "mixed_env",
    }.get(source, "none")


def _selected_storage_payload(
    item: dict[str, object],
    providers: list[dict[str, object]],
    selected_provider_id: str,
) -> dict[str, object]:
    normalized = str(selected_provider_id or "").strip().lower()
    if normalized:
        for row in providers:
            if isinstance(row, dict) and str(row.get("id", "")).strip().lower() == normalized:
                return row
    return providers[0] if len(providers) == 1 and isinstance(providers[0], dict) else item


def _selected_account_payload(
    accounts: list[dict[str, object]],
    selected_account_id: str,
) -> dict[str, object]:
    normalized = str(selected_account_id or "").strip().lower()
    if normalized:
        for row in accounts:
            if isinstance(row, dict) and str(row.get("id", "")).strip().lower() == normalized:
                return row
    return accounts[0] if len(accounts) == 1 and isinstance(accounts[0], dict) else {}


def _storage_posture_detail(label: str, payload: dict[str, object], *, auth_state: str) -> str:
    posture = _normalized_storage_posture(payload)
    if posture == "keyring" and auth_state in {"ready", "optional"}:
        return f"Saved details stay in keyring-first storage on this PC for {label}."
    if posture == "env_only":
        prefix = (
            f"{label} is working, but "
            if auth_state in {"ready", "optional"}
            else f"{label} setup is still using "
        )
        return prefix + "degraded environment fallback instead of keyring-first storage on this PC."
    if posture == "mixed_env":
        prefix = (
            f"{label} is working, but "
            if auth_state in {"ready", "optional"}
            else f"{label} setup still has "
        )
        return prefix + "some saved details resolving from degraded environment fallback instead of keyring-first storage on this PC."
    return ""


def _merge_detail(base_detail: str, storage_detail: str) -> str:
    base = str(base_detail or "").strip()
    posture = str(storage_detail or "").strip()
    if not posture:
        return base
    if not base:
        return posture
    return f"{base} {posture}".strip()


def _account_inventory_detail(
    accounts: list[dict[str, object]],
    *,
    selected_account_id: str,
) -> str:
    rows = [row for row in accounts if isinstance(row, dict)]
    if not rows:
        return ""
    selected = _selected_account_payload(rows, selected_account_id)
    selected_label = str(selected.get("label", selected.get("id", "")) or "").strip()
    if selected_label:
        return f"Selected account: {selected_label}."
    if len(rows) == 1:
        only_label = str(rows[0].get("label", rows[0].get("id", "")) or "").strip()
        return f"Account ready on this PC: {only_label}." if only_label else ""
    return f"{len(rows)} accounts are available on this PC. Choose one before reconnecting or removing access."


def _storage_migration_hint(payload: dict[str, object], *, auth_state: str) -> str:
    posture = _normalized_storage_posture(payload)
    if auth_state not in {"ready", "optional"}:
        return ""
    if posture == "env_only":
        return "Save the current details again on this PC to move them into keyring-first storage."
    if posture == "mixed_env":
        return "Re-save the current details on this PC to reduce degraded environment fallback and finish keyring-first storage."
    return ""


def selector_label(item: dict[str, object], *, fallback: str) -> str:
    label = str(item.get("label", item.get("id", fallback)) or fallback).strip() or fallback
    auth_state = str(item.get("auth_state", "") or "").strip().upper()
    if auth_state:
        label += f" [{auth_state}]"
    return label


def provider_tier_badge(tier: str) -> str:
    return {
        "core": " [CORE]",
        "supported_optional": " [OPT]",
        "experimental": " [BETA]",
    }.get(str(tier or "").strip().lower(), "")


def resolve_field_payloads(item: dict[str, object], selected_provider_id: str) -> list[dict[str, Any]]:
    providers = item.get("providers", []) if isinstance(item.get("providers"), list) else []
    selected_provider = next(
        (
            row
            for row in providers
            if isinstance(row, dict) and str(row.get("id", "")).strip().lower() == selected_provider_id
        ),
        {},
    )
    field_details = (
        [row for row in selected_provider.get("field_details", []) if isinstance(row, dict)]
        if isinstance(selected_provider, dict)
        else []
    )
    if field_details:
        return field_details
    return [secret_field_meta(field) for field in item.get("secret_fields", []) if str(field).strip()]


def build_connector_card_specs(items: list[dict[str, object]]) -> list[ConnectorCardSpec]:
    specs: list[ConnectorCardSpec] = []
    for item in items:
        connector_id = str(item.get("id", "")).strip().lower()
        if not connector_id:
            continue
        label = str(item.get("label", connector_id.title()) or connector_id.title())
        status = auth_state_text(str(item.get("auth_state", "") or "").strip())
        purpose = service_purpose(connector_id)
        brand = connector_brand(connector_id)
        specs.append(
            ConnectorCardSpec(
                connector_id=connector_id,
                button_text=f"{brand.badge}  {label}\n{purpose} - {status}",
                ready=str(item.get("auth_state", "") or "").strip().upper() == "READY",
                brand=brand,
            )
        )
    return specs


def friendly_runtime_summary(windows_snapshot: dict[str, str]) -> tuple[str, str, str, str, str]:
    install_raw = str(windows_snapshot.get("install", "") or "")
    runtime_raw = str(windows_snapshot.get("runtime", "") or "")
    next_raw = str(windows_snapshot.get("next", "") or "")
    runtime_fields = pipe_fields(runtime_raw)
    configured = runtime_fields.get("local ai runtime", "local ai").upper()
    live_backend = runtime_fields.get("live backend", configured).upper()
    state = runtime_fields.get("status", "unknown").strip().lower()

    installed_bits: list[str] = []
    if "Ollama CLI: found" in install_raw:
        installed_bits.append("Ollama")
    if "Lemonade CLI: found" in install_raw:
        installed_bits.append("Lemonade")
    if "Packager: ready" in install_raw:
        installed_bits.append("desktop packaging")
    if "Supervisor script: ready" in install_raw:
        installed_bits.append("supervised launch")
    install_text = "Ready on this PC: " + (
        ", ".join(installed_bits) + " are available." if installed_bits else "Core launcher tools are available."
    )

    if state == "ready":
        runtime_text = (
            f"Local AI health: {live_backend.title()} is healthy and ready on this PC. "
            "Choose or change the backend in Models > Model Sourcing."
        )
        summary = f"{live_backend.title()} is ready on this PC."
    elif state == "unknown":
        runtime_text = (
            f"Local AI health: {configured.title()} is selected, but it still needs a quick Verify check. "
            "Choose or change the backend in Models > Model Sourcing."
        )
        summary = f"{configured.title()} is selected, but it still needs a quick health check."
    else:
        runtime_text = (
            f"Local AI health: {configured.title()} needs attention before you rely on it. "
            "Choose or change the backend in Models > Model Sourcing."
        )
        summary = f"{configured.title()} needs attention before you rely on it."

    next_value = line_value(next_raw).lower()
    if "verification passed" in next_value:
        next_text = "Next step: Everything looks okay. Run Verify again after major model or runtime changes."
    elif "build_executable" in next_value or "package" in next_value:
        next_text = "Next step: Use Package when you want a fresh desktop build to share."
    elif next_value:
        next_text = "Next step: " + line_value(next_raw)
    else:
        next_text = "Next step: Use Verify to check that your local setup is healthy."

    diagnostics_text = (
        "Health notes: Logs, supervised launch, and repair tools are ready if something goes wrong. "
        "Keys and provider sign-in stay in Device & Accounts with keyring-first posture called out when env fallback is active."
    )
    return summary, install_text, runtime_text, next_text, diagnostics_text


def build_connector_panel_state(
    *,
    item: dict[str, object],
    providers: list[dict[str, object]],
    accounts: list[dict[str, object]],
    fields: list[dict[str, Any]],
    selected_provider_id: str,
    selected_account_id: str = "",
) -> ConnectorPanelState:
    label = str(item.get("label", "This service") or "This service")
    connector_id = str(item.get("id", "") or "").strip().lower()
    registry_entry = get_provider(connector_id)
    purpose = service_purpose(connector_id)
    auth_kind = str(item.get("auth_kind", "unknown") or "unknown").strip().lower()
    auth_state = str(item.get("auth_state", "missing") or "missing").strip().lower()
    auth_detail = str(item.get("auth_detail", "") or "").strip()
    first_field = fields[0] if fields else {}
    first_field_label = str(first_field.get("label", "details") or "details")
    connect_hint = (registry_entry.connect_hint if registry_entry else "").strip()
    supports = {str(supported).strip().lower() for supported in item.get("actions_supported", []) if str(supported).strip()}
    has_secret_flow = auth_kind in {"api_key", "provider_secret", "oauth_secret"}
    example_prompt = get_example_prompt(connector_id).strip()
    next_step_hint = ""
    storage_payload = _selected_storage_payload(item, providers, selected_provider_id)
    selected_account_payload = _selected_account_payload(accounts, selected_account_id)
    storage_detail = _storage_posture_detail(label, storage_payload, auth_state=auth_state)
    account_detail = _account_inventory_detail(accounts, selected_account_id=selected_account_id)
    account_selection_required = auth_kind == "oauth_file_token" and len(accounts) > 1 and not selected_account_payload

    if auth_kind == "api_key":
        status = f"{label} helps with {purpose.lower()} on this PC."
        if auth_state == "optional":
            detail = f"You can keep using basic {label.lower()} features without a key. Adding one makes results more reliable."
        elif auth_state == "ready":
            detail = f"Your {label} API key is saved and ready to use."
        else:
            detail = connect_hint or f"{label} uses a single API key on this PC."
        detail = _merge_detail(detail, storage_detail)
        step = f"Next step: Paste your {first_field_label.lower()}, then click Save API Key."
        save_text = "SAVE API KEY"
        verify_text = "VERIFY KEY"
        disconnect_text = "REMOVE KEY"
        connect_text = "BROWSER SIGN-IN"
    elif auth_kind == "oauth_file_token":
        status = f"{label} uses browser sign-in for {purpose.lower()}."
        if auth_state == "ready":
            detail = f"{label} is already connected on this PC."
        elif auth_state == "partial":
            detail = f"{label} is almost ready, but browser sign-in still needs to finish."
        else:
            detail = auth_detail or connect_hint or (
                f"{label} still needs the downloaded Google credentials file on this PC before browser sign-in can start."
            )
        if auth_state == "missing":
            step = f"Next step: Add the {label.lower()} credentials JSON file, then click Sign In."
        elif auth_state == "partial":
            step = f"Next step: Click Reconnect to finish connecting {label} on this PC."
        elif account_selection_required:
            step = f"Next step: Choose the {label} account you want to use, then click Sign In."
        else:
            step = f"Next step: Click Sign In to connect {label} on this PC."
        detail = _merge_detail(detail, account_detail)
        save_text = "SAVE & VERIFY"
        verify_text = "VERIFY SIGN-IN"
        disconnect_text = "REMOVE SIGN-IN"
        connect_text = "RECONNECT" if auth_state == "partial" else "SIGN IN"
    elif auth_kind == "oauth_secret":
        status = f"{label} needs app details before it can sign in."
        if providers and not selected_provider_id:
            status = f"{label} needs app details before it can sign in."
            detail = f"Choose which {label} provider you use first."
            step = f"Next step: Pick a {label} provider first."
        else:
            detail = connect_hint or f"{label} uses app credentials plus browser sign-in."
            detail = _merge_detail(detail, storage_detail)
            step = f"Next step: Add your {first_field_label.lower()}, save it, then use Sign In."
        save_text = "SAVE APP KEYS"
        verify_text = "VERIFY CONNECTION"
        disconnect_text = "REMOVE CONNECTION"
        connect_text = "RECONNECT" if auth_state == "partial" else "OPEN SIGN-IN"
    elif auth_kind == "provider_secret":
        status = f"{label} can connect after you add the provider details for this PC."
        if providers and not selected_provider_id:
            detail = f"Choose which {label} provider you use first."
            step = f"Next step: Pick a {label} provider first."
        else:
            if auth_state in {"ready", "optional"}:
                detail = f"{label} is ready. You can now allow it in a workspace when you need it."
            else:
                detail = connect_hint or f"Enter the provider details Guppy needs for {label.lower()}."
            detail = _merge_detail(detail, storage_detail)
            step = f"Next step: Add your {first_field_label.lower()}, then click Save Details."
        save_text = "SAVE DETAILS"
        verify_text = "VERIFY SETUP"
        disconnect_text = "CLEAR DETAILS"
        connect_text = "BROWSER SIGN-IN"
    else:
        status = f"{label} is available as a connected service."
        detail = "Choose this service to see what sign-in it needs."
        step = "Next step: Pick a service to get started."
        save_text = "SAVE"
        verify_text = "VERIFY"
        disconnect_text = "REMOVE"
        connect_text = "SIGN IN"

    if auth_state in {"ready", "optional"}:
        hint_text = (registry_entry.next_step_hint if registry_entry else "").strip()
        migration_hint = _storage_migration_hint(storage_payload, auth_state=auth_state)
        if hint_text:
            extra = f" {example_prompt}" if example_prompt else ""
            next_step_hint = f"Connected - {hint_text}{extra}"
        if migration_hint:
            next_step_hint = f"{next_step_hint} {migration_hint}".strip()

    show_connect = (
        "connect" in supports
        and auth_kind not in {"api_key", "provider_secret"}
        and not (auth_kind == "oauth_file_token" and auth_state == "missing")
    )
    connect_tooltip = connect_hint or f"Connect {label} on this PC."
    save_tooltip = f"Save the current {label} details on this PC."
    verify_tooltip = f"Verify {label} on this PC."
    if example_prompt:
        verify_tooltip += f" {example_prompt}"
    disconnect_tooltip = f"Remove the current {label} connection from this PC."
    if account_selection_required:
        connect_tooltip = f"Choose a {label} account first."
        verify_tooltip = f"Choose a {label} account first."
        disconnect_tooltip = f"Choose a {label} account first."

    return ConnectorPanelState(
        current_auth_kind=auth_kind,
        status_text=status,
        detail_text=detail,
        step_text=step,
        next_step_hint=next_step_hint,
        connect_text=connect_text,
        save_text=save_text,
        verify_text=verify_text,
        disconnect_text=disconnect_text,
        show_connect=show_connect,
        show_save=has_secret_flow,
        show_verify="verify" in supports,
        show_disconnect="disconnect" in supports,
        connect_enabled=show_connect and not account_selection_required,
        save_enabled=has_secret_flow,
        verify_enabled="verify" in supports and not account_selection_required,
        disconnect_enabled="disconnect" in supports and not account_selection_required,
        connect_tooltip=connect_tooltip,
        save_tooltip=save_tooltip,
        verify_tooltip=verify_tooltip,
        disconnect_tooltip=disconnect_tooltip,
    )


def build_device_accounts_density_state(width: int, auth_kind: str) -> DeviceAccountsDensityState:
    compact = width <= 1080
    tight = width <= 920
    action_labels = ("VERIFY", "UPDATE", "START API", "RESTART", "REPAIR")
    compact_action_labels = ("VERIFY", "UPDATE", "START", "RESTART", "REPAIR")
    tight_action_labels = ("VERIFY", "UPDATE", "START", "RESET", "REPAIR")
    desktop_action_labels = tight_action_labels if tight else compact_action_labels if compact else action_labels

    if auth_kind == "api_key":
        connect_text = "BROWSER SIGN-IN"
        save_text = "SAVE API KEY"
        verify_text = "VERIFY KEY"
        disconnect_text = "REMOVE KEY"
    elif auth_kind == "provider_secret":
        connect_text = "BROWSER SIGN-IN"
        save_text = "SAVE DETAILS"
        verify_text = "VERIFY SETUP"
        disconnect_text = "CLEAR DETAILS"
    elif auth_kind == "oauth_file_token":
        connect_text = "SIGN IN"
        save_text = "SAVE & VERIFY"
        verify_text = "VERIFY SIGN-IN"
        disconnect_text = "REMOVE SIGN-IN"
    elif auth_kind == "oauth_secret":
        connect_text = "OPEN SIGN-IN"
        save_text = "SAVE APP KEYS"
        verify_text = "VERIFY CONNECTION"
        disconnect_text = "REMOVE CONNECTION"
    else:
        connect_text = "SIGN IN"
        save_text = "SAVE"
        verify_text = "VERIFY"
        disconnect_text = "REMOVE"

    return DeviceAccountsDensityState(
        desktop_action_labels=desktop_action_labels,
        connect_text="SIGN IN" if compact else connect_text,
        save_text="SAVE" if tight else save_text,
        verify_text="VERIFY" if tight else verify_text,
        disconnect_text="CLEAR" if tight else disconnect_text,
    )


def line_value(text: str) -> str:
    value = str(text or "").strip()
    return value.split(":", 1)[1].strip() if ":" in value else value


def pipe_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for segment in [part.strip() for part in str(text or "").split("|") if part.strip()]:
        if ":" in segment:
            label, value = segment.split(":", 1)
            fields[label.strip().lower()] = value.strip()
    return fields
