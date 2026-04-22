"""Typed workspace and connector governance contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


def _as_text(value: object, default: str = "") -> str:
    return str(value or default).strip()


def _as_string_tuple(values: object) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple, set)):
        return ()
    result: list[str] = []
    for item in values:
        text = str(item or "").strip()
        if text:
            result.append(text)
    return tuple(result)


def _as_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


@dataclass(slots=True)
class WorkspaceSummary:
    """Launcher-safe summary of a workspace/instance."""

    name: str
    label: str = ""
    instance_type: str = ""
    purpose: str = ""
    description: str = ""
    status: str = "unknown"
    auth_mode: str = ""
    active: bool = False
    note: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "WorkspaceSummary":
        data = _as_dict(payload)
        return cls(
            name=_as_text(data.get("name")),
            label=_as_text(data.get("label") or data.get("title")),
            instance_type=_as_text(data.get("type") or data.get("instance_type")),
            purpose=_as_text(data.get("purpose")),
            description=_as_text(data.get("description")),
            status=_as_text(data.get("status"), "unknown").upper(),
            auth_mode=_as_text(data.get("auth_mode")),
            active=bool(data.get("active", False)),
            note=_as_text(data.get("note")),
            metadata=data,
        )


@dataclass(slots=True)
class ConnectorInventoryItem:
    """Typed connector inventory row shared across App Mgmt and governance."""

    connector_id: str
    label: str = ""
    auth_state: str = "unknown"
    auth_detail: str = ""
    auth_kind: str = ""
    summary: str = ""
    provider: str = ""
    enabled: bool = False
    inherited: bool = False
    account_id: str = ""
    action_allow: tuple[str, ...] = ()
    action_block: tuple[str, ...] = ()
    endpoint_allow: tuple[str, ...] = ()
    endpoint_block: tuple[str, ...] = ()
    supported_actions: tuple[str, ...] = ()
    secret_fields: tuple[str, ...] = ()
    note: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "ConnectorInventoryItem":
        data = _as_dict(payload)
        connector_id = _as_text(data.get("id") or data.get("connector") or data.get("connector_id")).lower()
        return cls(
            connector_id=connector_id,
            label=_as_text(data.get("label"), connector_id.replace("_", " ").title()),
            auth_state=_as_text(data.get("auth_state"), "unknown").lower(),
            auth_detail=_as_text(data.get("auth_detail")),
            auth_kind=_as_text(data.get("auth_kind")),
            summary=_as_text(data.get("summary") or data.get("setup_summary") or data.get("verify_summary")),
            provider=_as_text(data.get("provider")),
            enabled=bool(data.get("enabled", False)),
            inherited=bool(data.get("inherited", False) or data.get("binding_inherited", False)),
            account_id=_as_text(data.get("account_id")),
            action_allow=_as_string_tuple(data.get("action_allow")),
            action_block=_as_string_tuple(data.get("action_block")),
            endpoint_allow=_as_string_tuple(data.get("endpoint_allow")),
            endpoint_block=_as_string_tuple(data.get("endpoint_block")),
            supported_actions=_as_string_tuple(data.get("supported_actions")),
            secret_fields=_as_string_tuple(data.get("secret_fields")),
            note=_as_text(data.get("note")),
            raw=data,
        )


@dataclass(slots=True)
class WorkspaceGovernanceSnapshot:
    """Typed policy/readiness state for the active workspace."""

    workspace: WorkspaceSummary
    connectors: tuple[ConnectorInventoryItem, ...] = ()
    policy_state: str = "unknown"
    readiness_state: str = "unknown"
    readiness_summary: str = ""
    policy_reason: str = ""
    policy_reason_code: str = ""
    auth_mode: str = ""
    tool_allow: tuple[str, ...] = ()
    tool_block: tuple[str, ...] = ()
    endpoint_allow: tuple[str, ...] = ()
    endpoint_block: tuple[str, ...] = ()
    operator_hint: str = ""
    note: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ConnectorActionRequest:
    """Typed connector action request emitted by launcher/UI code."""

    connector_id: str
    action: str
    provider: str = ""
    account_id: str = ""
    secret_key: str = ""
    secret_value: str = ""
    workspace_name: str = ""

    def to_payload(self) -> dict[str, str]:
        return {
            "connector_id": self.connector_id,
            "action": self.action,
            "provider": self.provider,
            "account_id": self.account_id,
            "secret_key": self.secret_key,
            "secret_value": self.secret_value,
            "workspace_name": self.workspace_name,
        }


@dataclass(slots=True)
class ConnectorActionResult:
    """Typed connector action result returned by future service adapters."""

    connector_id: str
    action: str
    ok: bool
    summary: str
    auth_state: str = "unknown"
    result_code: str = ""
    next_step: str = ""
    fix_target: str = ""
    docs_hint: str = ""
    entry_point: str = ""
    event_id: str = ""
    history: dict[str, Any] = field(default_factory=dict)
    status: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "ConnectorActionResult":
        data = _as_dict(payload)
        status = _as_dict(data.get("status"))
        connector_id = _as_text(data.get("connector") or data.get("connector_id") or status.get("id")).lower()
        return cls(
            connector_id=connector_id,
            action=_as_text(data.get("action")),
            ok=bool(data.get("ok", False)),
            summary=_as_text(data.get("summary")),
            auth_state=_as_text(status.get("auth_state"), "unknown").lower(),
            result_code=_as_text(data.get("result_code")),
            next_step=_as_text(data.get("next_step")),
            fix_target=_as_text(data.get("fix_target")),
            docs_hint=_as_text(data.get("docs_hint")),
            entry_point=_as_text(data.get("entry_point")),
            event_id=_as_text(data.get("event_id")),
            history=_as_dict(data.get("history")),
            status=status,
        )
