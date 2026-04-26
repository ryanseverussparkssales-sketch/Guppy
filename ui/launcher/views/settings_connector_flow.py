"""
settings_connector_flow.py

Lane: TR54-C3
Responsibilities:
  - Connector workflow state machine (new → connecting → verifying → connected → expired → reconnecting → error)
  - Signal routing for verify/reconnect/remove/configure actions
  - Abort/cancel always available
  - Delegates remediation path resolution to connector_remediation_paths
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
import time
import logging

from ..accounts.connector_remediation_paths import (
    ConnectorBlockedReason,
    RemediationAction,
    build_remediation_path,
    remediation_button_label,
    remediation_summary,
)

logger = logging.getLogger("launcher.views.connector_flow")


class ConnectorFlowState(Enum):
    NEW = "new"
    CONNECTING = "connecting"
    VERIFYING = "verifying"
    CONNECTED = "connected"
    EXPIRED = "expired"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    ABORTED = "aborted"


_VALID_TRANSITIONS: dict[ConnectorFlowState, set[ConnectorFlowState]] = {
    ConnectorFlowState.NEW: {ConnectorFlowState.CONNECTING, ConnectorFlowState.ABORTED},
    ConnectorFlowState.CONNECTING: {ConnectorFlowState.VERIFYING, ConnectorFlowState.ERROR, ConnectorFlowState.ABORTED},
    ConnectorFlowState.VERIFYING: {ConnectorFlowState.CONNECTED, ConnectorFlowState.ERROR, ConnectorFlowState.ABORTED},
    ConnectorFlowState.CONNECTED: {ConnectorFlowState.EXPIRED, ConnectorFlowState.RECONNECTING, ConnectorFlowState.ABORTED},
    ConnectorFlowState.EXPIRED: {ConnectorFlowState.RECONNECTING, ConnectorFlowState.ABORTED},
    ConnectorFlowState.RECONNECTING: {ConnectorFlowState.VERIFYING, ConnectorFlowState.ERROR, ConnectorFlowState.ABORTED},
    ConnectorFlowState.ERROR: {ConnectorFlowState.RECONNECTING, ConnectorFlowState.ABORTED},
    ConnectorFlowState.ABORTED: set(),
}


@dataclass
class ConnectorFlowEvent:
    connector_id: str
    from_state: ConnectorFlowState
    to_state: ConnectorFlowState
    timestamp: float = field(default_factory=time.time)
    action: str = ""
    detail: str = ""
    error_code: str = ""


@dataclass
class ConnectorFlowContext:
    connector_id: str
    state: ConnectorFlowState = ConnectorFlowState.NEW
    blocked_reason: str = ""
    last_verified_at: Optional[float] = None
    error_message: str = ""
    history: list[ConnectorFlowEvent] = field(default_factory=list)


class SettingsConnectorFlow:
    """
    Manages connector lifecycle state transitions in the Settings surface.

    Callers wire on_state_changed to update UI. on_action_requested routes
    outbound signals (reconnect, verify, remove, configure) to the backend.
    """

    def __init__(
        self,
        connector_id: str,
        on_state_changed: Optional[Callable[[ConnectorFlowContext], None]] = None,
        on_action_requested: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> None:
        self._ctx = ConnectorFlowContext(connector_id=connector_id)
        self._on_state_changed = on_state_changed
        self._on_action_requested = on_action_requested

    @property
    def connector_id(self) -> str:
        return self._ctx.connector_id

    @property
    def state(self) -> ConnectorFlowState:
        return self._ctx.state

    @property
    def context(self) -> ConnectorFlowContext:
        return self._ctx

    def apply_backend_state(self, backend_payload: dict[str, Any]) -> None:
        raw_state = str(backend_payload.get("state", "") or "").strip().lower()
        blocked_reason = str(backend_payload.get("blocked_reason", "") or "").strip().lower()
        error_message = str(backend_payload.get("error_message", "") or "").strip()
        last_verified_at = backend_payload.get("last_verified_at")

        flow_state = _backend_state_to_flow(raw_state, blocked_reason)
        self._ctx.blocked_reason = blocked_reason
        self._ctx.error_message = error_message
        if isinstance(last_verified_at, (int, float)):
            self._ctx.last_verified_at = float(last_verified_at)
        self._transition(flow_state, action="backend_sync", detail=raw_state)

    def request_verify(self) -> None:
        self._emit_action(RemediationAction.VERIFY.value, {
            "connector": self._ctx.connector_id,
            "action": "verify",
            "request_source": "settings_connector_flow",
        })
        self._transition(ConnectorFlowState.VERIFYING, action="verify")

    def request_reconnect(self) -> None:
        self._emit_action(RemediationAction.RECONNECT.value, {
            "connector": self._ctx.connector_id,
            "action": "reconnect",
            "request_source": "settings_connector_flow",
        })
        target = (
            ConnectorFlowState.RECONNECTING
            if self._ctx.state in (ConnectorFlowState.CONNECTED, ConnectorFlowState.EXPIRED)
            else ConnectorFlowState.CONNECTING
        )
        self._transition(target, action="reconnect")

    def request_remove(self) -> None:
        self._emit_action(RemediationAction.REMOVE.value, {
            "connector": self._ctx.connector_id,
            "action": "disconnect",
            "request_source": "settings_connector_flow",
        })

    def request_configure(self) -> None:
        self._emit_action(RemediationAction.CONFIGURE.value, {
            "connector": self._ctx.connector_id,
            "action": "configure",
            "request_source": "settings_connector_flow",
        })

    def abort(self) -> None:
        self._transition(ConnectorFlowState.ABORTED, action="abort")

    def remediation_summary(self) -> str:
        return remediation_summary(self._ctx.connector_id, self._ctx.blocked_reason)

    def primary_button_label(self) -> str:
        return remediation_button_label(self._ctx.connector_id, self._ctx.blocked_reason)

    def remediation_steps(self) -> list[dict[str, str]]:
        path = build_remediation_path(self._ctx.connector_id, self._ctx.blocked_reason)
        return [
            {
                "action": step.action.value,
                "label": step.label,
                "description": step.description,
                "button_label": step.button_label,
            }
            for step in path.steps
        ]

    def _transition(self, target: ConnectorFlowState, action: str = "", detail: str = "") -> None:
        current = self._ctx.state
        if current == target:
            return
        allowed = _VALID_TRANSITIONS.get(current, set())
        if target not in allowed:
            logger.warning(
                "connector_flow: invalid transition %s → %s for %s",
                current.value, target.value, self._ctx.connector_id,
            )
            return
        event = ConnectorFlowEvent(
            connector_id=self._ctx.connector_id,
            from_state=current,
            to_state=target,
            action=action,
            detail=detail,
        )
        self._ctx.state = target
        self._ctx.history.append(event)
        if self._on_state_changed is not None:
            try:
                self._on_state_changed(self._ctx)
            except Exception:
                logger.exception("connector_flow: on_state_changed callback raised")

    def _emit_action(self, action_name: str, payload: dict[str, Any]) -> None:
        if self._on_action_requested is not None:
            try:
                self._on_action_requested(payload)
            except Exception:
                logger.exception("connector_flow: on_action_requested callback raised for %s", action_name)


def _backend_state_to_flow(raw_state: str, blocked_reason: str) -> ConnectorFlowState:
    mapping: dict[str, ConnectorFlowState] = {
        "connected": ConnectorFlowState.CONNECTED,
        "connecting": ConnectorFlowState.CONNECTING,
        "verifying": ConnectorFlowState.VERIFYING,
        "expired": ConnectorFlowState.EXPIRED,
        "reconnecting": ConnectorFlowState.RECONNECTING,
        "error": ConnectorFlowState.ERROR,
        "new": ConnectorFlowState.NEW,
    }
    if raw_state in mapping:
        return mapping[raw_state]
    if blocked_reason in (
        ConnectorBlockedReason.EXPIRED.value,
    ):
        return ConnectorFlowState.EXPIRED
    if blocked_reason in (
        ConnectorBlockedReason.HOST_AUTH_MISSING.value,
        ConnectorBlockedReason.ACCOUNT_UNAVAILABLE.value,
        ConnectorBlockedReason.PROVIDER_UNCONFIGURED.value,
    ):
        return ConnectorFlowState.ERROR
    return ConnectorFlowState.NEW


def make_flow(
    connector_id: str,
    on_state_changed: Optional[Callable[[ConnectorFlowContext], None]] = None,
    on_action_requested: Optional[Callable[[dict[str, Any]], None]] = None,
) -> SettingsConnectorFlow:
    return SettingsConnectorFlow(
        connector_id=connector_id,
        on_state_changed=on_state_changed,
        on_action_requested=on_action_requested,
    )
