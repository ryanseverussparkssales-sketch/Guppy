from __future__ import annotations

from typing import Any, Callable

from .windows_ops import WindowsOpsExecutionKind, build_windows_ops_descriptor
from .windows_ops_coordination import begin_windows_ops_chain, progress_windows_ops_chain
from .windows_ops_runtime import default_windows_ops_event_id


DelayedScheduler = Callable[[int, Callable[[], None]], None]


def start_windows_ops_chain_request(owner: Any, action: str) -> None:
    normalized = str(action or "").strip().lower()
    steps = owner._windows_ops_chain_steps(normalized)
    owner._active_windows_ops_chain = begin_windows_ops_chain(
        normalized,
        steps=steps,
        changes=owner._windows_ops_chain_changes(normalized),
    )


def update_windows_ops_chain_request(owner: Any, action: str, *, ok: bool, summary: str) -> bool:
    active_chain = owner._active_windows_ops_chain
    progress = progress_windows_ops_chain(
        active_chain,
        action,
        ok=ok,
        summary=summary,
        guidance_builder=lambda parent_action, overall_ok: owner._windows_ops_guidance(
            parent_action,
            ok=overall_ok,
            phase="completed",
        ),
        artifacts=owner._windows_ops_artifact_refs(
            str(active_chain.get("action", "") or action).strip().lower(),
            owner._collect_windows_service_snapshot(),
        ) if isinstance(active_chain, dict) else [],
        receipt_path=owner._windows_release_receipt_path(),
        summary_path=owner._windows_release_summary_path(),
    )
    if not progress.matched:
        return False
    owner._active_windows_ops_chain = progress.next_chain
    if not progress.completed or progress.state_record is None or progress.event_fields is None:
        return True
    record = progress.state_record
    owner._record_windows_ops_state(
        record.action,
        record.summary,
        record.changes,
        ok=record.ok,
        event_id=record.event_id,
        steps_completed=record.steps_completed,
        steps_total=record.steps_total,
        phase=record.phase,
        next_step=record.next_step,
        fix_target=record.fix_target,
        docs_hint=record.docs_hint,
        entry_point=record.entry_point,
        artifacts=record.artifacts,
    )
    owner._log_launcher_event("windows_ops_completed", **progress.event_fields)
    owner._active_windows_ops_chain = None
    return True


def dispatch_windows_ops_request(owner: Any, action: str, *, delayed_scheduler: DelayedScheduler) -> None:
    descriptor = build_windows_ops_descriptor(action)
    target = descriptor.action
    plan = owner._windows_ops_plan(target)
    label = str(descriptor.label or plan.get("label", "") or "").strip()
    changes = str(descriptor.changes or plan.get("changes", "") or "").strip()
    if descriptor.execution_kind == WindowsOpsExecutionKind.TERMINAL_RECIPE:
        commands = list(descriptor.commands)
        if not commands:
            owner._status_panel.append_syslog(f"windows ops unavailable: {action}")
            return
        guidance = owner._windows_ops_guidance(target, ok=True, phase="queued")
        queued = owner._settings_hub_view.queue_terminal_recipe(
            commands,
            label=label,
            recipe_context={
                "kind": "windows_ops",
                "action": target,
                "changes": changes,
                "pre_snapshot": owner._collect_windows_service_snapshot(),
            },
        )
        if queued:
            summary = str(descriptor.request_summary or f"{label.title()} queued in Settings terminal")
            owner._set_daily_activity(summary)
            owner._status_panel.append_syslog(str(descriptor.syslog_message or f"{label.lower()} queued"))
            owner._record_windows_ops_state(
                target,
                summary,
                changes,
                ok=True,
                commands=commands,
                phase="queued",
                next_step=str(guidance.get("next_step", "") or ""),
                fix_target=str(guidance.get("fix_target", "") or ""),
                docs_hint=str(guidance.get("docs_hint", "") or ""),
                entry_point=str(guidance.get("entry_point", "") or ""),
            )
            owner._log_launcher_event(
                "windows_ops_action",
                action=target,
                queued=True,
                commands=len(commands),
                next_step=str(guidance.get("next_step", "") or ""),
                fix_target=str(guidance.get("fix_target", "") or ""),
            )
        else:
            summary = f"{label.title()} failed to queue"
            owner._status_panel.append_syslog(f"{label.lower()} failed to queue")
            failed_guidance = owner._windows_ops_guidance(target, ok=False, phase="queue_failed")
            owner._record_windows_ops_state(
                target,
                summary,
                changes or "No update commands were queued.",
                ok=False,
                commands=commands,
                phase="queue_failed",
                next_step=str(failed_guidance.get("next_step", "") or ""),
                fix_target=str(failed_guidance.get("fix_target", "") or ""),
                docs_hint=str(failed_guidance.get("docs_hint", "") or ""),
                entry_point=str(failed_guidance.get("entry_point", "") or ""),
            )
            owner._log_launcher_event(
                "windows_ops_action",
                action=target,
                queued=False,
                commands=len(commands),
                next_step=str(failed_guidance.get("next_step", "") or ""),
                fix_target=str(failed_guidance.get("fix_target", "") or ""),
            )
        return

    if descriptor.execution_kind == WindowsOpsExecutionKind.SUBPROCESS and target == "start_supervised_api":
        guidance = owner._windows_ops_guidance(target, ok=True, phase="queued")
        summary = str(descriptor.request_summary or "Supervised API launch requested from Settings")
        owner._status_panel.append_syslog(str(descriptor.syslog_message or "supervised api requested"))
        owner._set_daily_activity(summary)
        owner._record_windows_ops_state(
            target,
            summary,
            changes,
            ok=True,
            phase="queued",
            next_step=str(guidance.get("next_step", "") or ""),
            fix_target=str(guidance.get("fix_target", "") or ""),
            docs_hint=str(guidance.get("docs_hint", "") or ""),
            entry_point=str(guidance.get("entry_point", "") or ""),
        )
        owner._log_launcher_event(
            "windows_ops_action",
            action=target,
            queued=True,
            next_step=str(guidance.get("next_step", "") or ""),
            fix_target=str(guidance.get("fix_target", "") or ""),
        )
        started, detail = owner._start_supervised_api_subprocess()
        if started:
            owner._refresh_api_auth_state("start_supervised_api")
        final_guidance = owner._windows_ops_guidance(target, ok=started, phase="completed")
        final_summary = detail or ("supervised api started and reachable" if started else "supervised api did not become reachable")
        artifacts = owner._windows_ops_artifact_refs(target, owner._collect_windows_service_snapshot())
        event_id = default_windows_ops_event_id(target)
        owner._record_windows_ops_state(
            target,
            final_summary,
            changes,
            ok=started,
            event_id=event_id,
            phase="completed",
            next_step=str(final_guidance.get("next_step", "") or ""),
            fix_target=str(final_guidance.get("fix_target", "") or ""),
            docs_hint=str(final_guidance.get("docs_hint", "") or ""),
            entry_point=str(final_guidance.get("entry_point", "") or ""),
            artifacts=artifacts,
        )
        owner._log_launcher_event(
            "windows_ops_completed",
            action=target,
            ok=started,
            summary=final_summary,
            event_id=event_id,
            next_step=str(final_guidance.get("next_step", "") or ""),
            fix_target=str(final_guidance.get("fix_target", "") or ""),
            artifacts=artifacts,
            release_receipt=str(owner._windows_release_receipt_path()),
            release_summary=str(owner._windows_release_summary_path()),
        )
        owner._status_panel.append_syslog(final_summary)
        owner._settings_hub_view.append_log(final_summary)
        owner._set_daily_activity(final_summary)
        return

    if descriptor.execution_kind == WindowsOpsExecutionKind.RECOVERY_CHAIN and target in {"restart_runtime", "repair_runtime"}:
        summary = str(descriptor.request_summary or f"{label.title()} queued")
        owner._status_panel.append_syslog(str(descriptor.syslog_message or f"{label.lower()} requested"))
        owner._set_daily_activity(summary)
        start_windows_ops_chain_request(owner, target)
        guidance = owner._windows_ops_guidance(target, ok=True, phase="queued")
        owner._record_windows_ops_state(
            target,
            summary,
            changes,
            ok=True,
            steps_completed=0,
            steps_total=len(descriptor.chain_steps),
            phase="queued",
            next_step=str(guidance.get("next_step", "") or ""),
            fix_target=str(guidance.get("fix_target", "") or ""),
            docs_hint=str(guidance.get("docs_hint", "") or ""),
            entry_point=str(guidance.get("entry_point", "") or ""),
        )
        owner._log_launcher_event(
            "windows_ops_action",
            action=target,
            queued=True,
            next_step=str(guidance.get("next_step", "") or ""),
            fix_target=str(guidance.get("fix_target", "") or ""),
        )
        for step in descriptor.chain_steps:
            if step.delay_ms <= 0:
                owner._on_recovery_requested(step.name)
            else:
                delayed_scheduler(step.delay_ms, lambda recovery_action=step.name: owner._on_recovery_requested(recovery_action))
        return

    owner._status_panel.append_syslog(f"windows ops unavailable: {action}")
