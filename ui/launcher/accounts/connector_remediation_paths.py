"""
connector_remediation_paths.py

Lane: TR54-C3
Responsibilities:
  - Per-connector remediation step definitions
  - Recovery path builders for each blocked state
  - Settings-owned remediation lane resolution
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RemediationAction(Enum):
    RECONNECT = "reconnect"
    VERIFY = "verify"
    REMOVE = "remove"
    CONFIGURE = "configure"
    OPEN_SETTINGS = "open_settings"
    CONTACT_SUPPORT = "contact_support"


class ConnectorBlockedReason(Enum):
    ACCOUNT_UNAVAILABLE = "connector_account_unavailable"
    PROVIDER_UNCONFIGURED = "connector_provider_unconfigured"
    HOST_AUTH_MISSING = "connector_host_auth_missing"
    CONNECTOR_UNBOUND = "connector_unbound"
    ACTION_BLOCKED = "connector_action_blocked"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


@dataclass
class RemediationStep:
    action: RemediationAction
    label: str
    description: str
    button_label: str
    destination: str = ""
    requires_credential: bool = False


@dataclass
class ConnectorRemediationPath:
    connector_id: str
    blocked_reason: ConnectorBlockedReason
    title: str
    summary: str
    steps: list[RemediationStep] = field(default_factory=list)
    settings_destination: str = "settings_device_accounts"
    can_abort: bool = True


_VERIFY_STEP = RemediationStep(
    action=RemediationAction.VERIFY,
    label="Verify connection",
    description="Test the connector with a live API call to confirm access.",
    button_label="VERIFY",
)

_RECONNECT_STEP = RemediationStep(
    action=RemediationAction.RECONNECT,
    label="Reconnect account",
    description="Re-authenticate to restore access.",
    button_label="RECONNECT",
    requires_credential=True,
)

_REMOVE_STEP = RemediationStep(
    action=RemediationAction.REMOVE,
    label="Remove connector",
    description="Clear stored credentials and remove this connector.",
    button_label="REMOVE",
)

_OPEN_SETTINGS_STEP = RemediationStep(
    action=RemediationAction.OPEN_SETTINGS,
    label="Open Device & Accounts",
    description="Go to Settings > Device & Accounts to manage this connector.",
    button_label="OPEN DEVICE & ACCOUNTS",
    destination="settings_device_accounts",
)


def _base_path(
    connector_id: str,
    reason: ConnectorBlockedReason,
    title: str,
    summary: str,
    steps: list[RemediationStep],
) -> ConnectorRemediationPath:
    return ConnectorRemediationPath(
        connector_id=connector_id,
        blocked_reason=reason,
        title=title,
        summary=summary,
        steps=steps,
    )


def build_remediation_path(
    connector_id: str,
    blocked_reason: str,
) -> ConnectorRemediationPath:
    reason = _coerce_reason(blocked_reason)
    builder = _BUILDERS.get(reason, _build_generic)
    return builder(connector_id, reason)


def _coerce_reason(code: str) -> ConnectorBlockedReason:
    normalized = str(code or "").strip().lower()
    for member in ConnectorBlockedReason:
        if member.value == normalized:
            return member
    return ConnectorBlockedReason.UNKNOWN


def _build_account_unavailable(connector_id: str, reason: ConnectorBlockedReason) -> ConnectorRemediationPath:
    label = connector_id.title()
    return _base_path(
        connector_id=connector_id,
        reason=reason,
        title=f"{label} account not available",
        summary=(
            f"No valid {label} account is set up on this machine. "
            "Connect an account in Settings > Device & Accounts, then bind it in Workspaces."
        ),
        steps=[_OPEN_SETTINGS_STEP, _RECONNECT_STEP, _VERIFY_STEP],
    )


def _build_provider_unconfigured(connector_id: str, reason: ConnectorBlockedReason) -> ConnectorRemediationPath:
    label = connector_id.title()
    return _base_path(
        connector_id=connector_id,
        reason=reason,
        title=f"{label} provider not configured",
        summary=(
            f"The {label} provider has not been configured on this machine. "
            "Complete provider setup in Settings > Device & Accounts before binding."
        ),
        steps=[
            _OPEN_SETTINGS_STEP,
            RemediationStep(
                action=RemediationAction.CONFIGURE,
                label="Configure provider",
                description=f"Set up the {label} provider with the required credentials.",
                button_label="CONFIGURE",
                requires_credential=True,
            ),
            _VERIFY_STEP,
        ],
    )


def _build_host_auth_missing(connector_id: str, reason: ConnectorBlockedReason) -> ConnectorRemediationPath:
    label = connector_id.title()
    return _base_path(
        connector_id=connector_id,
        reason=reason,
        title=f"{label} machine-level auth missing",
        summary=(
            f"Machine-level authentication for {label} is missing or expired. "
            "Connect or verify the auth in Settings > Device & Accounts."
        ),
        steps=[_OPEN_SETTINGS_STEP, _RECONNECT_STEP, _VERIFY_STEP, _REMOVE_STEP],
    )


def _build_expired(connector_id: str, reason: ConnectorBlockedReason) -> ConnectorRemediationPath:
    label = connector_id.title()
    return _base_path(
        connector_id=connector_id,
        reason=reason,
        title=f"{label} session expired",
        summary=(
            f"Your {label} session has expired. Reconnect to restore access."
        ),
        steps=[_RECONNECT_STEP, _VERIFY_STEP, _REMOVE_STEP],
    )


def _build_generic(connector_id: str, reason: ConnectorBlockedReason) -> ConnectorRemediationPath:
    label = connector_id.title()
    return _base_path(
        connector_id=connector_id,
        reason=reason,
        title=f"{label} connector blocked",
        summary=(
            f"The {label} connector is not available. "
            "Open Settings > Device & Accounts to diagnose and fix."
        ),
        steps=[_OPEN_SETTINGS_STEP, _VERIFY_STEP],
    )


_BUILDERS = {
    ConnectorBlockedReason.ACCOUNT_UNAVAILABLE: _build_account_unavailable,
    ConnectorBlockedReason.PROVIDER_UNCONFIGURED: _build_provider_unconfigured,
    ConnectorBlockedReason.HOST_AUTH_MISSING: _build_host_auth_missing,
    ConnectorBlockedReason.EXPIRED: _build_expired,
    ConnectorBlockedReason.UNKNOWN: _build_generic,
}


def remediation_button_label(connector_id: str, blocked_reason: str) -> str:
    path = build_remediation_path(connector_id, blocked_reason)
    if not path.steps:
        return "OPEN DEVICE & ACCOUNTS"
    return path.steps[0].button_label


def remediation_destination(connector_id: str, blocked_reason: str) -> str:
    path = build_remediation_path(connector_id, blocked_reason)
    for step in path.steps:
        if step.destination:
            return step.destination
    return path.settings_destination


def remediation_summary(connector_id: str, blocked_reason: str) -> str:
    return build_remediation_path(connector_id, blocked_reason).summary
