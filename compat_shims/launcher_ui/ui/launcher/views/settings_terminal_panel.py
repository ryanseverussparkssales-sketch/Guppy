from __future__ import annotations

from src.guppy.launcher_application.workflow_panel import (
    build_workflow_failed_state,
    build_workflow_loaded_state,
    build_workflow_panel_state,
    build_workflow_queued_state,
    workflow_loaded_log_lines,
)

from .. import tokens as T


def focus_terminal(owner, note: str = "") -> None:
    if not owner._details_visible:
        owner._details_visible = True
        owner._sync_detail_visibility()
    if note:
        append_terminal_output(owner, note)
    owner._terminal_input.setFocus()


def apply_workflow_panel_state(owner, state) -> None:
    owner._workflow_summary_lbl.setText(state.summary_text or "No workflow summary available.")
    owner._workflow_steps_lbl.setText(state.steps_text)
    owner._workflow_next_step_lbl.setText(state.next_step_text)
    owner._workflow_outcome_lbl.setText(state.outcome_text)
    owner._workflow_outcome_lbl.setStyleSheet(
        f"color: {T.PRIMARY_DIM if state.status_ok else T.ERROR}; "
        f"font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
    )
    owner._workflow_evidence_lbl.setText(state.evidence_text)
    owner._set_workflow_status(state.status_text, ok=state.status_ok)


def sync_workflow_recipe(owner) -> None:
    state = build_workflow_panel_state(
        str(owner._workflow_cb.currentData() or ""),
        terminal_status=owner._terminal_status_lbl.text(),
    )
    apply_workflow_panel_state(owner, state)


def load_workflow_recipe(owner) -> None:
    state = build_workflow_loaded_state(str(owner._workflow_cb.currentData() or ""))
    if not state.has_commands:
        apply_workflow_panel_state(owner, state)
        return
    owner._terminal_input.setText(state.first_command)
    for line in workflow_loaded_log_lines(state):
        append_terminal_output(owner, line)
    owner._terminal_input.setFocus()
    apply_workflow_panel_state(owner, state)


def handle_terminal_recipe_marker(owner, line: str) -> bool:
    result = owner._terminal_session.handle_recipe_marker(line)
    if not result.ok:
        return False
    if result.status_text:
        owner._terminal_status_lbl.setText(result.status_text)
    for payload in result.completed_payloads:
        owner.terminal_recipe_finished.emit(payload)
    return True


def run_terminal_commands(
    owner,
    commands: list[str],
    *,
    label: str,
    recipe_context: dict[str, object] | None = None,
) -> bool:
    cleaned = [str(item).strip() for item in commands if str(item).strip()]
    if not cleaned:
        append_terminal_output(owner, f"[launcher] {label} has no commands to run")
        workflow_id = str(recipe_context.get("workflow_id", "") or "") if recipe_context else ""
        if workflow_id:
            apply_workflow_panel_state(
                owner,
                build_workflow_failed_state(
                    workflow_id,
                    reason=f"{label} did not start because no commands were available.",
                ),
            )
        return False
    result = owner._terminal_session.queue_commands(cleaned, label=label, recipe_context=recipe_context)
    for line in result.log_lines:
        append_terminal_output(owner, line)
    if result.status_text:
        owner._terminal_status_lbl.setText(result.status_text)
    if result.ok:
        if recipe_context and str(recipe_context.get("kind", "") or "").strip().lower() == "workflow_loop":
            apply_workflow_panel_state(
                owner,
                build_workflow_queued_state(str(recipe_context.get("workflow_id", "") or "")),
            )
        return True
    workflow_id = str(recipe_context.get("workflow_id", "") or "") if recipe_context else ""
    if workflow_id:
        apply_workflow_panel_state(
            owner,
            build_workflow_failed_state(
                workflow_id,
                reason=result.status_text or f"{label} failed before queueing all commands.",
            ),
        )
    return False


def run_workflow_recipe(owner) -> None:
    state = build_workflow_queued_state(str(owner._workflow_cb.currentData() or ""))
    if run_terminal_commands(
        owner,
        list(state.commands),
        label=state.title,
        recipe_context={"kind": "workflow_loop", "workflow_id": state.workflow_id},
    ):
        apply_workflow_panel_state(owner, state)


def append_terminal_output(owner, text: str) -> None:
    current = owner._terminal_output.toPlainText().splitlines()
    current.extend(str(text or "").splitlines() or [""])
    owner._terminal_output.setPlainText("\n".join(current[-400:]))
    bar = owner._terminal_output.verticalScrollBar()
    bar.setValue(bar.maximum())


def submit_terminal_command(owner) -> None:
    command = owner._terminal_input.text().strip()
    if not command:
        return
    result = owner._terminal_session.submit_command(command)
    for line in result.log_lines:
        append_terminal_output(owner, line)
    if result.status_text:
        owner._terminal_status_lbl.setText(result.status_text)
    if result.clear_input:
        owner._terminal_input.clear()


def drain_terminal_queue(owner) -> None:
    result = owner._terminal_session.drain_output()
    for line in result.log_lines:
        append_terminal_output(owner, line)
    if result.focus_output:
        owner._terminal_output.setFocus()
    if result.status_text:
        owner._terminal_status_lbl.setText(result.status_text)
    for payload in result.completed_payloads:
        owner.terminal_recipe_finished.emit(payload)


def stop_terminal_process(owner) -> None:
    result = owner._terminal_session.stop()
    for line in result.log_lines:
        append_terminal_output(owner, line)
    if result.status_text:
        owner._terminal_status_lbl.setText(result.status_text)
