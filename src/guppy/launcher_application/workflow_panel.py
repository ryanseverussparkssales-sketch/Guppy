"""Pure presenter helpers for the App Mgmt workflow panel."""

from __future__ import annotations

from dataclasses import dataclass

from .workflows import WorkflowSpec, get_workflow_spec, list_workflow_specs


@dataclass(frozen=True, slots=True)
class WorkflowPanelState:
    """Renderable workflow-panel state derived from the shared workflow catalog."""

    workflow_id: str
    title: str
    summary_text: str
    steps_text: str
    next_step_text: str
    outcome_text: str
    evidence_text: str
    status_text: str = "Workflow shortcuts ready"
    status_ok: bool = True
    commands: tuple[str, ...] = ()

    @property
    def has_commands(self) -> bool:
        return bool(self.commands)

    @property
    def first_command(self) -> str:
        return self.commands[0] if self.commands else ""

    @property
    def remaining_command_count(self) -> int:
        return max(0, len(self.commands) - 1)


def resolve_workflow_loop_spec(workflow_id: str) -> WorkflowSpec | None:
    """Resolve a selected workflow-loop spec, falling back to the first available loop."""

    recipe = get_workflow_spec(str(workflow_id or "").strip())
    if recipe is not None and recipe.category == "workflow_loop":
        return recipe
    workflows = list_workflow_specs(category="workflow_loop")
    return workflows[0] if workflows else None


def workflow_command_strings(workflow_id: str) -> tuple[str, ...]:
    recipe = resolve_workflow_loop_spec(workflow_id)
    if recipe is None:
        return ()
    return tuple(item.command for item in recipe.commands if str(item.command).strip())


def build_workflow_panel_state(
    workflow_id: str,
    *,
    terminal_status: str = "Shell idle",
) -> WorkflowPanelState:
    """Build the steady-state panel copy for the selected workflow."""

    recipe = resolve_workflow_loop_spec(workflow_id)
    commands = workflow_command_strings(workflow_id)
    summary = recipe.summary if recipe is not None else ""
    title = recipe.title if recipe is not None else "WORKFLOW"
    selected_id = recipe.workflow_id if recipe is not None else str(workflow_id or "").strip().lower()
    if commands:
        count = len(commands)
        return WorkflowPanelState(
            workflow_id=selected_id,
            title=title,
            summary_text=summary or "No workflow summary available.",
            steps_text="  |  ".join(f"{idx + 1}. {cmd}" for idx, cmd in enumerate(commands)),
            next_step_text=(
                f"Next step: load the first command for a guided start, or run all {count} commands in the embedded terminal."
            ),
            outcome_text=f"Outcome: {title} is ready with {count} command(s).",
            evidence_text=(
                f"Evidence: {count} command(s) ready | shell status: {str(terminal_status or 'Shell idle').lower()} "
                "| operator logs will mirror warnings and failures."
            ),
            commands=commands,
        )
    return WorkflowPanelState(
        workflow_id=selected_id,
        title=title,
        summary_text=summary or "No workflow summary available.",
        steps_text="No commands configured for this workflow.",
        next_step_text="Next step: choose a workflow with at least one command.",
        outcome_text="Outcome: No runnable commands are configured for this workflow.",
        evidence_text="Evidence: No runnable commands are available for this workflow.",
        status_text="Workflow recipe is empty",
        status_ok=False,
        commands=commands,
    )


def build_workflow_loaded_state(workflow_id: str) -> WorkflowPanelState:
    """Build the panel state after loading the first workflow command into the terminal."""

    base = build_workflow_panel_state(workflow_id)
    if not base.has_commands:
        return base
    return WorkflowPanelState(
        workflow_id=base.workflow_id,
        title=base.title,
        summary_text=base.summary_text,
        steps_text=base.steps_text,
        next_step_text=(
            f"Next step: review the first command, then press RUN or continue through the remaining "
            f"{base.remaining_command_count} command(s)."
        ),
        outcome_text=f"Outcome: Loaded the first command for {base.title}. Review it before you run the rest.",
        evidence_text=(
            f"Evidence: {base.title} loaded | first command is in the terminal input | "
            f"{base.remaining_command_count} command(s) remain after this guided step."
        ),
        status_text=f"Loaded {base.title} into the terminal input",
        status_ok=True,
        commands=base.commands,
    )


def build_workflow_queued_state(workflow_id: str) -> WorkflowPanelState:
    """Build the panel state after queueing the workflow in the embedded terminal."""

    base = build_workflow_panel_state(workflow_id)
    if not base.has_commands:
        return base
    count = len(base.commands)
    return WorkflowPanelState(
        workflow_id=base.workflow_id,
        title=base.title,
        summary_text=base.summary_text,
        steps_text=base.steps_text,
        next_step_text=(
            f"Next step: watch the embedded terminal and operator logs while {count} command(s) run."
        ),
        outcome_text=f"Outcome: {base.title} queued {count} command(s) in the embedded terminal.",
        evidence_text=(
            f"Evidence: {base.title} queued {count} command(s) | watch embedded terminal output and operator logs "
            "for pass/fail evidence."
        ),
        status_text=f"Queued {base.title} in the embedded terminal",
        status_ok=True,
        commands=base.commands,
    )
