"""Pure presenter helpers for the launcher workspace manager view."""

from __future__ import annotations

from typing import Any

from .instance_manager_connector_binding import (
    build_connector_binding_editor_state,
    build_connector_binding_feedback,
    connector_history_line,
    selector_label,
)
from .instance_manager_models import (
    DEFAULT_CONNECTOR_IDS,
    ConnectorBindingSaveRequest,
    ConnectorBindingState,
    GovernanceEditorState,
    GovernanceSaveRequest,
    InstanceManagerState,
    RolePreset,
    SaveAffordanceState,
    SectionToggleState,
    SelectorOption,
    SelectorState,
    WorkspaceCreateCopy,
    WorkspaceCreateFormState,
    WorkspaceCreateRequest,
    WorkspaceEditorsState,
)


def parse_policy_lines(text: str) -> list[str]:
    seen: set[str] = set()
    lines: list[str] = []
    for raw in str(text or "").splitlines():
        value = raw.strip()
        if not value:
            continue
        lowered = value.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        lines.append(lowered)
    return lines


def workspace_role_label(workspace_type: str) -> str:
    key = (workspace_type or "user_instance").strip().lower()
    return {
        "user_instance": "Daily assistant",
        "builder_instance": "Builder collaborator",
        "read_only_instance": "Read-only reference",
        "admin_instance": "Operations workspace",
    }.get(key, key.replace("_", " ").strip().title() or "Workspace")


def workspace_default_purpose(workspace_type: str) -> str:
    key = (workspace_type or "user_instance").strip().lower()
    return {
        "user_instance": "General help, recurring work, and quick tasks.",
        "builder_instance": "Planning, reviews, and low-risk builder collaboration.",
        "read_only_instance": "Safe research, source review, and reference work without writes.",
        "admin_instance": "Recovery, diagnostics, and guarded changes.",
    }.get(key, "Task-focused context for this workspace.")


def workspace_collaboration_hint(workspace_type: str) -> str:
    key = (workspace_type or "user_instance").strip().lower()
    return {
        "user_instance": "Best for recurring daily work and live conversation.",
        "builder_instance": "Best for reviews, plans, and low-risk builder collaboration.",
        "read_only_instance": "Best for source checking and safe reference work.",
        "admin_instance": "Best for recovery, diagnostics, and guarded operational steps.",
    }.get(key, "Best for focused work in its saved context.")


def workspace_reentry_hint(workspace_type: str) -> str:
    key = (workspace_type or "user_instance").strip().lower()
    return {
        "user_instance": "Return here for repeated daily requests, follow-ups, and quick decisions.",
        "builder_instance": "Return here for planning passes, review loops, and low-risk drafting.",
        "read_only_instance": "Return here for source checks, comparisons, and reference-safe inspection.",
        "admin_instance": "Return here for servicing, diagnostics, and guarded operator actions.",
    }.get(key, "Return here when you want this workspace's saved context and purpose.")


def workspace_first_run_recipe(workspace_type: str) -> str:
    key = (workspace_type or "user_instance").strip().lower()
    return {
        "user_instance": "First run: use MORNING BRIEF for priorities, then keep the workspace on daily follow-ups.",
        "builder_instance": "First run: open PLAN NEXT PASS, then use BUILDER REVIEW to catch regressions early.",
        "read_only_instance": "First run: open SOURCE RESEARCH, then SOURCE TRIAGE to organize evidence safely.",
        "admin_instance": "First run: open OPS CHECK, then VERIFY or REPAIR only after the evidence is clear.",
    }.get(key, "First run: use the starter that best matches the workspace's saved purpose.")


def workspace_example_names(workspace_type: str) -> str:
    key = (workspace_type or "user_instance").strip().lower()
    return {
        "user_instance": "Good names: daily-desk | inbox-desk | project-rhythm",
        "builder_instance": "Good names: builder-collab | release-review | docs-pass",
        "read_only_instance": "Good names: reference-desk | source-check | partner-brief",
        "admin_instance": "Good names: ops-console | recovery-desk | servicing-check",
    }.get(key, "Good names: pick one that matches the saved purpose.")


def workspace_saved_context(payload: dict[str, object]) -> str:
    mode = str(payload.get("mode", "auto") or "auto").strip().upper()
    persona = str(payload.get("persona", "guppy") or "guppy").strip().upper()
    voice = str(payload.get("voice", "default") or "default").strip().upper()
    return f"Saved context: {mode} mode | {persona} persona | {voice} voice"


def workspace_recent_context(payload: dict[str, object]) -> str:
    last_message = str(payload.get("last_message", "") or "").strip()
    if not last_message:
        return "Recent context: no recent thread is pinned yet."
    snippet = last_message[:120] + ("..." if len(last_message) > 120 else "")
    return f"Recent context: {snippet}"


def workspace_continuity_text(payload: dict[str, object]) -> str:
    continuity = payload.get("continuity", {}) if isinstance(payload.get("continuity"), dict) else {}
    summary = str(continuity.get("continuity_summary", "") or "").strip()
    if summary:
        return summary
    return workspace_recent_context(payload)


def workspace_role_summary(items: list[dict[str, object]] | tuple[dict[str, object], ...]) -> str:
    counts = {"daily": 0, "builder": 0, "reference": 0, "ops": 0}
    for item in items:
        if not isinstance(item, dict):
            continue
        key = str(item.get("type", "user_instance") or "user_instance").strip().lower()
        if key == "builder_instance":
            counts["builder"] += 1
        elif key == "read_only_instance":
            counts["reference"] += 1
        elif key == "admin_instance":
            counts["ops"] += 1
        else:
            counts["daily"] += 1
    return (
        f"Daily {counts['daily']} | Builder {counts['builder']} | "
        f"Reference {counts['reference']} | Ops {counts['ops']}"
    )


def role_preset(workspace_type: str) -> RolePreset:
    key = (workspace_type or "user_instance").strip().lower()
    presets = {
        "user_instance": RolePreset(
            "daily-desk",
            "Daily tasks, follow-ups, and recurring requests",
            "auto",
            "Preset: daily workspace defaults favor recurring conversation, quick follow-ups, and calm starter flows.",
            "First run: use MORNING BRIEF for priorities, then continue with daily follow-ups.",
        ),
        "builder_instance": RolePreset(
            "builder-collab",
            "Planning, review loops, and low-risk drafting",
            "code",
            "Preset: builder workspace defaults favor review passes, planning, and low-risk drafting.",
            "First run: open PLAN NEXT PASS, then use BUILDER REVIEW on the draft.",
        ),
        "read_only_instance": RolePreset(
            "reference-desk",
            "Source checking, comparisons, and safe reference work",
            "local",
            "Preset: reference workspace defaults favor safe inspection, comparisons, and evidence-first research.",
            "First run: open SOURCE RESEARCH, then SOURCE TRIAGE to sort the evidence.",
        ),
        "admin_instance": RolePreset(
            "ops-console",
            "Recovery, diagnostics, servicing, and guarded operator work",
            "auto",
            "Preset: ops workspace defaults favor diagnostics, recovery, and guarded operator actions.",
            "First run: open OPS CHECK, then VERIFY or REPAIR after checking evidence.",
        ),
    }
    return presets.get(key, presets["user_instance"])


def build_workspace_create_copy(workspace_type: str) -> WorkspaceCreateCopy:
    key = (workspace_type or "user_instance").strip().lower() or "user_instance"
    preset = role_preset(key)
    return WorkspaceCreateCopy(
        workspace_type=key,
        role_label=workspace_role_label(key),
        default_purpose=workspace_default_purpose(key),
        collaboration_hint=workspace_collaboration_hint(key),
        reentry_hint=workspace_reentry_hint(key),
        first_run_recipe=workspace_first_run_recipe(key),
        example_names=workspace_example_names(key),
        name_placeholder=preset.name_placeholder,
        description_placeholder=preset.description_placeholder,
        default_mode=preset.mode,
        preset_summary=preset.summary,
    )


def build_workspace_create_request(
    *,
    name: str,
    description: str,
    mode: str,
    persona: str,
    voice: str,
    workspace_type: str,
    enabled: bool,
) -> WorkspaceCreateRequest:
    return WorkspaceCreateRequest(
        name=str(name or "").strip(),
        description=str(description or "").strip(),
        mode=str(mode or "auto").strip() or "auto",
        persona=str(persona or "guppy").strip() or "guppy",
        voice=str(voice or "default").strip() or "default",
        workspace_type=(str(workspace_type or "user_instance").strip().lower() or "user_instance"),
        enabled=bool(enabled),
    )


def build_workspace_create_form_state(
    *,
    workspace_type: str,
    current_description: str,
    current_mode: str,
    previous_copy: WorkspaceCreateCopy,
) -> WorkspaceCreateFormState:
    copy = build_workspace_create_copy(workspace_type)
    description = str(current_description or "").strip()
    mode = str(current_mode or "").strip().lower()
    description_value = None
    mode_value = None
    if not description or description == previous_copy.description_placeholder:
        description_value = copy.description_placeholder
    if not mode or mode == previous_copy.default_mode:
        mode_value = copy.default_mode
    return WorkspaceCreateFormState(
        copy=copy,
        description_value=description_value,
        mode_value=mode_value,
    )


def build_governance_save_request(
    *,
    target: str,
    policy: dict[str, object] | None,
    auth_mode: str,
    tool_allow_text: str,
    tool_block_text: str,
    endpoint_allow_text: str,
    endpoint_block_text: str,
    policy_note: str,
) -> tuple[GovernanceSaveRequest | None, str]:
    workspace_name = str(target or "").strip()
    if not workspace_name:
        return None, "Choose a workspace before saving governance."
    payload = policy if isinstance(policy, dict) else {}
    return (
        GovernanceSaveRequest(
            name=workspace_name,
            instance_type=str(payload.get("instance_type", "user_instance") or "user_instance"),
            auth_mode=str(auth_mode or "runtime_default").strip() or "runtime_default",
            tool_allow=tuple(parse_policy_lines(tool_allow_text)),
            tool_block=tuple(parse_policy_lines(tool_block_text)),
            endpoint_allow=tuple(parse_policy_lines(endpoint_allow_text)),
            endpoint_block=tuple(parse_policy_lines(endpoint_block_text)),
            policy_note=str(policy_note or "").strip(),
        ),
        "",
    )


def build_connector_binding_save_request(
    *,
    workspace_name: str,
    connector_id: str,
    enabled: bool,
    account_id: str,
    provider: str,
    action_allow_text: str,
    action_block_text: str,
    endpoint_allow_text: str,
    endpoint_block_text: str,
    note: str,
) -> tuple[ConnectorBindingSaveRequest | None, str]:
    name = str(workspace_name or "").strip()
    connector = str(connector_id or "").strip().lower()
    if not name or not connector:
        return None, "Choose a workspace and connector before saving."
    return (
        ConnectorBindingSaveRequest(
            name=name,
            connector=connector,
            enabled=bool(enabled),
            account_id=str(account_id or "").strip().lower(),
            provider=str(provider or "").strip().lower(),
            action_allow=tuple(parse_policy_lines(action_allow_text)),
            action_block=tuple(parse_policy_lines(action_block_text)),
            endpoint_allow=tuple(parse_policy_lines(endpoint_allow_text)),
            endpoint_block=tuple(parse_policy_lines(endpoint_block_text)),
            note=str(note or "").strip(),
        ),
        "",
    )


def build_section_toggle_state(
    visible: bool,
    *,
    show_label: str,
    hide_label: str,
) -> SectionToggleState:
    return SectionToggleState(
        visible=bool(visible),
        button_label=hide_label if visible else show_label,
    )


def build_selector_state(
    options: tuple[str, ...],
    selected_value: str,
) -> SelectorState:
    normalized_options = tuple(str(item).strip() for item in options if str(item).strip())
    if not normalized_options:
        return SelectorState(options=(), selected_value="")
    target = str(selected_value or "").strip()
    if target not in normalized_options:
        target = normalized_options[0]
    return SelectorState(options=normalized_options, selected_value=target)


def workspace_onboarding_ready_message(name: str, workspace_type: str) -> str:
    copy = build_workspace_create_copy(workspace_type)
    role = copy.role_label
    if "workspace" not in role.lower():
        role = f"{role} workspace"
    workspace_name = str(name or "").strip() or "workspace"
    return f"{role} {workspace_name} is ready. {copy.first_run_recipe}"


def build_governance_editor_state(
    workspace_name: str,
    governance_by_name: dict[str, dict[str, object]],
) -> GovernanceEditorState:
    target = str(workspace_name or "").strip()
    policy = governance_by_name.get(target, {})
    auth_mode = str(policy.get("auth_mode", "runtime_default") or "runtime_default")
    capabilities = policy.get("capabilities", {}) if isinstance(policy.get("capabilities"), dict) else {}
    return GovernanceEditorState(
        auth_mode=auth_mode,
        policy_note=str(policy.get("policy_note", "") or ""),
        tool_allow_text="\n".join(str(item) for item in policy.get("tool_allow", []) if str(item).strip()),
        tool_block_text="\n".join(str(item) for item in policy.get("tool_block", []) if str(item).strip()),
        endpoint_allow_text="\n".join(str(item) for item in policy.get("endpoint_allow", []) if str(item).strip()),
        endpoint_block_text="\n".join(str(item) for item in policy.get("endpoint_block", []) if str(item).strip()),
        status_text=(
            f"Editing {target or 'workspace'} | auth mode={auth_mode} | "
            f"caps r/w/x/n={int(bool(capabilities.get('read', False)))}/{int(bool(capabilities.get('write', False)))}/"
            f"{int(bool(capabilities.get('execute', False)))}/{int(bool(capabilities.get('network', False)))}"
        ),
    )


def build_workspace_editors_state(state: InstanceManagerState) -> WorkspaceEditorsState:
    governance_workspace = build_selector_state(state.ordered_names, state.governance_target)
    connector_workspace = build_selector_state(state.ordered_names, state.connector_target_workspace)
    connector_id = build_selector_state(state.connector_ids, state.connector_target_id)
    return WorkspaceEditorsState(
        governance_workspace=governance_workspace,
        connector_workspace=connector_workspace,
        connector_id=connector_id,
        governance_editor=build_governance_editor_state(
            governance_workspace.selected_value,
            state.governance_map,
        ),
        connector_editor=build_connector_binding_editor_state(
            connector_workspace.selected_value,
            connector_id.selected_value,
            state.connector_map,
        ),
    )


def build_save_affordance_state(
    *,
    candidate_name: str,
    known_names: set[str] | tuple[str, ...],
    configured: int,
    max_configured: int,
) -> SaveAffordanceState:
    candidate = str(candidate_name or "").strip()
    is_new_name = bool(candidate) and candidate not in set(known_names)
    at_limit = int(configured) >= int(max_configured)
    if at_limit and is_new_name:
        return SaveAffordanceState(
            enabled=False,
            warning_text=(
                f"Workspace limit reached ({configured} / {max_configured}). "
                "Update an existing workspace or delete one first."
            ),
        )
    return SaveAffordanceState(enabled=True, warning_text="")


def build_workspace_activity_log_text(
    instance_name: str,
    entries: list[dict[str, object]] | tuple[dict[str, object], ...],
) -> str:
    lines: list[str] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        timestamp = str(item.get("timestamp", "")).replace("T", " ").replace("+00:00", "Z")
        role = str(item.get("role", "event")).upper()
        message = str(item.get("message", item.get("response", ""))).strip()
        if message:
            lines.append(f"[{timestamp}] {role}: {message}")
    if lines:
        return "\n".join(lines)
    return f"No recent conversation or ops activity yet for workspace {instance_name}"


def build_instance_manager_state(
    payload: dict[str, object] | None,
    *,
    previous_governance_workspace: str = "",
    previous_connector_workspace: str = "",
    previous_connector_id: str = "",
) -> InstanceManagerState:
    raw_payload = payload if isinstance(payload, dict) else {}
    instances = raw_payload.get("instances", []) if isinstance(raw_payload.get("instances"), list) else []
    items = tuple(item for item in instances if isinstance(item, dict))
    active_instance = str(raw_payload.get("active_instance", "") or "").strip()
    warnings = raw_payload.get("warnings", []) if isinstance(raw_payload.get("warnings"), list) else []
    ordered_names = tuple(
        str(item.get("name", "")).strip()
        for item in items
        if str(item.get("name", "")).strip()
    )
    governance_map: dict[str, dict[str, object]] = {}
    connector_map: dict[str, dict[str, dict[str, object]]] = {}
    for item in items:
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        governance = item.get("governance", {}) if isinstance(item.get("governance"), dict) else {}
        governance_map[name] = {
            **governance,
            "instance_type": str(item.get("type", "user_instance") or "user_instance"),
        }
        connector_rows = item.get("connectors", []) if isinstance(item.get("connectors"), list) else []
        workspace_auth_mode = str(governance.get("auth_mode", "runtime_default") or "runtime_default")
        connector_map[name] = {
            str(row.get("id", "")).strip().lower(): {
                **row,
                "workspace_auth_mode": workspace_auth_mode,
            }
            for row in connector_rows
            if isinstance(row, dict) and str(row.get("id", "")).strip()
        }
    governance_target = previous_governance_workspace or active_instance or (ordered_names[0] if ordered_names else "")
    connector_target_workspace = previous_connector_workspace or active_instance or (ordered_names[0] if ordered_names else "")
    connector_rows = connector_map.get(connector_target_workspace, {})
    connector_ids = tuple(str(item).strip() for item in connector_rows.keys() if str(item).strip()) or DEFAULT_CONNECTOR_IDS
    normalized_previous_connector_id = str(previous_connector_id or "").strip().lower()
    connector_target_id = normalized_previous_connector_id if normalized_previous_connector_id in connector_ids else connector_ids[0]
    limits = raw_payload.get("limits", {}) if isinstance(raw_payload.get("limits"), dict) else {}
    if isinstance(limits, dict):
        configured = int(limits.get("configured", len(items)) or len(items))
        max_configured = int(limits.get("max_configured", 5) or 5)
        active_runtime = int(limits.get("active_runtime", 0) or 0)
        max_active_runtime = int(limits.get("max_active_runtime", 2) or 2)
    else:
        configured = len(items)
        max_configured = 5
        active_runtime = sum(
            1
            for item in items
            if str(item.get("status", "idle")).strip().lower() in {"active", "running", "busy"}
        )
        max_active_runtime = 2
    role_mix = workspace_role_summary(items)
    summary_text = (
        f"Configured workspaces: {configured} / {max_configured} | Active workspace: {active_instance or '-'}"
        + (f" | Roles: {role_mix}" if items else "")
        + (f" | Warnings: {len(warnings)}" if warnings else "")
    )
    limits_text = f"Live workspaces: {active_runtime} / {max_active_runtime}"
    if configured >= max_configured:
        limits_text += " | workspace cap reached"
    if active_runtime >= max_active_runtime:
        limits_text += " | collaborator cap reached"
    active_payload = next(
        (
            item
            for item in items
            if str(item.get("name", "")).strip() == active_instance
        ),
        {},
    )
    active_type = str(active_payload.get("type", "user_instance") or "user_instance")
    active_purpose = str(active_payload.get("description", "") or workspace_default_purpose(active_type)).strip()
    collaboration_text = (
        f"Active workspace fit: {workspace_role_label(active_type)}. {active_purpose} | {workspace_collaboration_hint(active_type)}"
        if active_instance
        else "Pick a workspace to see its saved purpose and collaboration fit."
    )
    recurring_text = (
        f"Recurring context: {workspace_saved_context(active_payload)} | {workspace_reentry_hint(active_type)} | {workspace_continuity_text(active_payload)}"
        if active_instance
        else "Pick a workspace to see its saved mode/persona/voice rhythm and recent thread cues."
    )
    return InstanceManagerState(
        items=items,
        ordered_names=ordered_names,
        governance_map=governance_map,
        connector_map=connector_map,
        governance_target=governance_target,
        connector_target_workspace=connector_target_workspace,
        connector_ids=connector_ids,
        connector_target_id=connector_target_id,
        active_instance=active_instance,
        configured=configured,
        max_configured=max_configured,
        active_runtime=active_runtime,
        max_active_runtime=max_active_runtime,
        summary_text=summary_text,
        limits_text=limits_text,
        role_mix_text="Role mix: " + role_mix,
        collaboration_text=collaboration_text,
        recurring_text=recurring_text,
        show_empty_state=not bool(items),
        empty_state_text=(
            "No workspaces yet.\n\nStart with Daily for recurring help, Builder for reviews and planning, "
            "Reference for evidence-first checks, or Ops for guarded recovery work."
        ),
    )
