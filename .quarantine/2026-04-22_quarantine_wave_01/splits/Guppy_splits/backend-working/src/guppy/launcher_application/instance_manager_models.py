"""Typed state and request models for the workspace manager presenter."""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_CONNECTOR_IDS = ("gmail", "calendar", "spotify", "youtube", "crm", "voip")


@dataclass(frozen=True, slots=True)
class RolePreset:
    name_placeholder: str
    description_placeholder: str
    mode: str
    summary: str
    recipe: str


@dataclass(frozen=True, slots=True)
class GovernanceEditorState:
    auth_mode: str
    policy_note: str
    tool_allow_text: str
    tool_block_text: str
    endpoint_allow_text: str
    endpoint_block_text: str
    status_text: str


@dataclass(frozen=True, slots=True)
class SelectorOption:
    label: str
    value: str


@dataclass(frozen=True, slots=True)
class ConnectorBindingState:
    connector_ids: tuple[str, ...]
    selected_connector_id: str
    enabled: bool
    provider_options: tuple[SelectorOption, ...]
    selected_provider: str
    account_options: tuple[SelectorOption, ...]
    selected_account: str
    action_allow_text: str
    action_block_text: str
    endpoint_allow_text: str
    endpoint_block_text: str
    note: str
    status_text: str
    validation_text: str
    history_text: str


@dataclass(frozen=True, slots=True)
class InstanceManagerState:
    items: tuple[dict[str, object], ...]
    ordered_names: tuple[str, ...]
    governance_map: dict[str, dict[str, object]]
    connector_map: dict[str, dict[str, dict[str, object]]]
    governance_target: str
    connector_target_workspace: str
    connector_ids: tuple[str, ...]
    connector_target_id: str
    active_instance: str
    configured: int
    max_configured: int
    active_runtime: int
    max_active_runtime: int
    summary_text: str
    limits_text: str
    role_mix_text: str
    collaboration_text: str
    recurring_text: str
    show_empty_state: bool
    empty_state_text: str


@dataclass(frozen=True, slots=True)
class WorkspaceCreateCopy:
    workspace_type: str
    role_label: str
    default_purpose: str
    collaboration_hint: str
    reentry_hint: str
    first_run_recipe: str
    example_names: str
    name_placeholder: str
    description_placeholder: str
    default_mode: str
    preset_summary: str


@dataclass(frozen=True, slots=True)
class WorkspaceCreateRequest:
    name: str
    description: str
    mode: str
    persona: str
    voice: str
    workspace_type: str
    enabled: bool

    def as_payload(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "mode": self.mode,
            "persona": self.persona,
            "voice": self.voice,
            "type": self.workspace_type,
            "enabled": self.enabled,
        }


@dataclass(frozen=True, slots=True)
class GovernanceSaveRequest:
    name: str
    instance_type: str
    auth_mode: str
    tool_allow: tuple[str, ...]
    tool_block: tuple[str, ...]
    endpoint_allow: tuple[str, ...]
    endpoint_block: tuple[str, ...]
    policy_note: str

    def as_payload(self) -> dict[str, object]:
        return {
            "name": self.name,
            "instance_type": self.instance_type,
            "auth_mode": self.auth_mode,
            "tool_allow": list(self.tool_allow),
            "tool_block": list(self.tool_block),
            "endpoint_allow": list(self.endpoint_allow),
            "endpoint_block": list(self.endpoint_block),
            "policy_note": self.policy_note,
        }


@dataclass(frozen=True, slots=True)
class ConnectorBindingSaveRequest:
    name: str
    connector: str
    enabled: bool
    account_id: str
    provider: str
    action_allow: tuple[str, ...]
    action_block: tuple[str, ...]
    endpoint_allow: tuple[str, ...]
    endpoint_block: tuple[str, ...]
    note: str

    def as_payload(self) -> dict[str, object]:
        return {
            "name": self.name,
            "connector": self.connector,
            "enabled": self.enabled,
            "account_id": self.account_id,
            "provider": self.provider,
            "action_allow": list(self.action_allow),
            "action_block": list(self.action_block),
            "endpoint_allow": list(self.endpoint_allow),
            "endpoint_block": list(self.endpoint_block),
            "note": self.note,
        }


@dataclass(frozen=True, slots=True)
class SectionToggleState:
    visible: bool
    button_label: str


@dataclass(frozen=True, slots=True)
class SelectorState:
    options: tuple[str, ...]
    selected_value: str


@dataclass(frozen=True, slots=True)
class WorkspaceCreateFormState:
    copy: WorkspaceCreateCopy
    description_value: str | None
    mode_value: str | None


@dataclass(frozen=True, slots=True)
class SaveAffordanceState:
    enabled: bool
    warning_text: str


@dataclass(frozen=True, slots=True)
class WorkspaceEditorsState:
    governance_workspace: SelectorState
    connector_workspace: SelectorState
    connector_id: SelectorState
    governance_editor: GovernanceEditorState
    connector_editor: ConnectorBindingState
