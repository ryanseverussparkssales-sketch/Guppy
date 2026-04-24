from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from src.guppy.launcher_application.automation_test_support import (
    build_automation_test_snapshot,
    write_user_test_evidence_pack,
)


def available_instance_names(snapshot: Mapping[str, object] | None) -> set[str]:
    items = snapshot.get("instances", []) if isinstance(snapshot, Mapping) else []
    return {
        str(item.get("name", "")).strip()
        for item in items
        if isinstance(item, dict) and bool(item.get("enabled", True)) and str(item.get("name", "")).strip()
    }


def preferred_builder_workspace_name(
    active_instance_name: str,
    snapshot: Mapping[str, object] | None,
) -> str:
    names = available_instance_names(snapshot)
    if "builder-collab" in names:
        return "builder-collab"
    return str(active_instance_name or "guppy-primary").strip() or "guppy-primary"


def user_test_evidence_paths(runtime_dir: Path) -> tuple[Path, Path]:
    return runtime_dir / "user_test_evidence.json", runtime_dir / "user_test_evidence.md"


def read_assistant_home_labels(owner: Any) -> dict[str, str]:
    labels: dict[str, str] = {}
    for key in (
        "background_event",
        "workspace_summary",
        "runtime_facts",
        "route_facts",
        "recovery_summary",
    ):
        attr_name = f"_{key}"
        widget = getattr(getattr(owner, "_assistant_view", None), attr_name, None)
        text_getter = getattr(widget, "text", None)
        if callable(text_getter):
            try:
                labels[key] = str(text_getter() or "").strip()
                continue
            except Exception:
                pass
        labels[key] = ""
    return labels


def write_launcher_user_test_evidence_pack(
    owner: Any,
    *,
    runtime_dir: Path,
    automation_report_path: Path,
    validation_command: str,
    report_path: Path | None = None,
    status: str = "",
) -> dict[str, str]:
    windows_snapshot_getter = getattr(getattr(owner, "_settings_hub_view", None), "windows_ops_snapshot", None)
    windows_snapshot = windows_snapshot_getter() if callable(windows_snapshot_getter) else {}
    snapshot = getattr(owner, "_last_instance_snapshot", {})
    evidence_json_path, evidence_summary_path = user_test_evidence_paths(runtime_dir)
    preferred_builder_workspace = preferred_builder_workspace_name(
        str(getattr(owner, "_active_instance_name", "") or ""),
        snapshot if isinstance(snapshot, Mapping) else {},
    )
    automation_status_getter = getattr(getattr(owner, "_settings_hub_view", None), "automation_status_text", None)
    resolved_status = str(status or (automation_status_getter() if callable(automation_status_getter) else "") or "").strip()
    return write_user_test_evidence_pack(
        runtime_dir=runtime_dir,
        repo_root=runtime_dir.parent,
        active_instance_name=str(getattr(owner, "_active_instance_name", "") or ""),
        preferred_builder_workspace=preferred_builder_workspace,
        last_instance_snapshot=snapshot if isinstance(snapshot, Mapping) else {},
        home_labels=read_assistant_home_labels(owner),
        automation_status=resolved_status,
        windows_snapshot=windows_snapshot if isinstance(windows_snapshot, Mapping) else {},
        report_path=report_path,
        automation_report_path=automation_report_path,
        validation_command=validation_command,
        evidence_json_path=evidence_json_path,
        evidence_summary_path=evidence_summary_path,
    )


def build_launcher_automation_test_snapshot(
    owner: Any,
    *,
    runtime_dir: Path,
    automation_report_path: Path,
    validation_command: str,
    report_path: Path | None = None,
    status: str = "",
    evidence_pack_path: str = "",
    stress_report_path: str = "",
    recent_events: str = "",
) -> dict[str, str]:
    snapshot = getattr(owner, "_last_instance_snapshot", {})
    preferred_builder_workspace = preferred_builder_workspace_name(
        str(getattr(owner, "_active_instance_name", "") or ""),
        snapshot if isinstance(snapshot, Mapping) else {},
    )
    return build_automation_test_snapshot(
        runtime_dir=runtime_dir,
        repo_root=runtime_dir.parent,
        active_instance_name=str(getattr(owner, "_active_instance_name", "") or ""),
        preferred_builder_workspace=preferred_builder_workspace,
        automation_report_path=automation_report_path,
        validation_command=validation_command,
        report_path=report_path,
        status=status,
        evidence_pack_path=evidence_pack_path,
        stress_report_path=stress_report_path,
        recent_events=recent_events,
    )


def sync_launcher_automation_test_state(
    owner: Any,
    *,
    runtime_dir: Path,
    automation_report_path: Path,
    validation_command: str,
    status: str = "",
    ok: bool = True,
    report_path: Path | None = None,
    persist: bool = False,
) -> None:
    evidence_bundle = (
        write_launcher_user_test_evidence_pack(
            owner,
            runtime_dir=runtime_dir,
            automation_report_path=automation_report_path,
            validation_command=validation_command,
            report_path=report_path,
            status=status,
        )
        if persist
        else {}
    )
    snapshot = build_launcher_automation_test_snapshot(
        owner,
        runtime_dir=runtime_dir,
        automation_report_path=automation_report_path,
        validation_command=validation_command,
        report_path=report_path,
        status=status,
        evidence_pack_path=str(evidence_bundle.get("summary_path", "") or ""),
        stress_report_path=str(evidence_bundle.get("stress_report_path", "") or ""),
        recent_events=str(evidence_bundle.get("recent_events", "") or ""),
    )
    settings_view = getattr(owner, "_settings_hub_view", None)
    if settings_view is not None:
        settings_view.set_automation_snapshot(snapshot)
        if status:
            settings_view.set_automation_status(status, ok=ok)


def write_launcher_automation_report(
    owner: Any,
    *,
    automation_report_path: Path,
    validation_command: str,
) -> Path:
    from src.guppy.launcher_application.builder_workflow import build_builder_report, metrics_path, queue_path, results_path

    report = build_builder_report(queue_path=queue_path(), results_path=results_path(), metrics_path=metrics_path())
    payload = {
        **report,
        "active_workspace": str(getattr(owner, "_active_instance_name", "") or ""),
        "preferred_builder_workspace": preferred_builder_workspace_name(
            str(getattr(owner, "_active_instance_name", "") or ""),
            getattr(owner, "_last_instance_snapshot", {}),
        ),
        "validation_command": validation_command,
    }
    automation_report_path.parent.mkdir(parents=True, exist_ok=True)
    automation_report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return automation_report_path


def handle_automation_action_request(
    owner: Any,
    action: str,
    *,
    automation_report_path: Path,
    validation_command: str,
) -> None:
    """Dispatch automation action buttons from the UI to the appropriate support calls.

    Extracted from LauncherWindow._on_automation_action_requested as part of TR54-B1.
    """
    target = (action or "").strip().lower()

    if target == "verify_now":
        owner._settings_hub_view.focus_automation_test(
            note="VERIFY NOW queued runtime readiness checks in the Settings terminal."
        )
        owner._on_windows_ops_requested("verify_runtime")
        owner._sync_automation_test_state(
            status="VERIFY NOW queued runtime readiness checks in the embedded terminal.",
            persist=True,
        )
        return

    if target == "switch_builder_workspace":
        preferred = owner._preferred_builder_instance_name()
        if preferred != "builder-collab":
            owner._sync_automation_test_state(
                status="builder-collab is unavailable, so the current workspace stays active.",
                ok=False,
                persist=True,
            )
            return
        if owner._active_instance_name == "builder-collab":
            owner._sync_automation_test_state(status="builder-collab is already active.", persist=True)
            return
        owner._on_instance_selected("builder-collab")
        owner._settings_hub_view.focus_automation_test(
            note="Builder workspace selected for automation dry runs."
        )
        owner._sync_automation_test_state(status="Switched to builder-collab for automation testing.", persist=True)
        return

    if target == "queue_dry_run":
        instance_name = owner._preferred_builder_instance_name()
        try:
            task = owner._queue_builder_task(
                template_id="regression_checklist",
                target_ref="automation test launcher and approval flow",
                instance_name=instance_name,
                announce_text=f"Automation dry run queued for {instance_name}",
            )
        except Exception as exc:
            owner._sync_automation_test_state(status=f"Queue failed: {exc}", ok=False, persist=True)
            owner._status_panel.append_syslog(f"automation dry run queue failed: {exc}")
            return
        owner._settings_hub_view.focus_automation_test(
            note=f"Dry run queued: {task['title']} -> {task['output_file_path']}"
        )
        return

    if target == "open_latest_report":
        path = owner._write_automation_report()
        evidence_bundle = owner._write_user_test_evidence_pack(
            report_path=path,
            status="Evidence pack refreshed for the guided tester lane.",
        )
        summary_path = str(evidence_bundle.get("summary_path", "") or "")
        owner._settings_hub_view.focus_operator_logs(
            "ALL",
            note=f"Evidence pack refreshed: {summary_path or path}",
        )
        owner._assistant_view.add_system_message(f"Evidence pack refreshed: {summary_path or path}")
        owner._status_panel.append_syslog(f"automation evidence refreshed: {summary_path or path}")
        owner._sync_automation_test_state(
            status=f"Evidence pack refreshed at {summary_path or path}",
            report_path=path,
            persist=True,
        )
        return

    if target == "approve_latest_staged_task":
        try:
            payload = owner._approve_latest_builder_task()
        except Exception as exc:
            owner._sync_automation_test_state(status=f"Approval failed: {exc}", ok=False, persist=True)
            owner._status_panel.append_syslog(f"automation approval failed: {exc}")
            return
        output_file = str(payload.get("output_file", "") or "").strip()
        owner._assistant_view.add_system_message(f"Approved staged builder output -> {output_file}")
        owner._status_panel.append_syslog(f"automation approval complete: {output_file}")
        owner._set_daily_activity("Approved staged automation test output")
        owner._sync_automation_test_state(
            status=f"Approved latest staged task -> {output_file}",
            report_path=automation_report_path,
            persist=True,
        )
        return

    if target == "run_validation":
        queued = owner._settings_hub_view.queue_terminal_recipe(
            [validation_command],
            label="AUTOMATION TEST VALIDATION",
            recipe_context={
                "kind": "automation_test",
                "action": "run_validation",
                "changes": "Runs the focused builder validation suite after dry-run review or approval.",
            },
        )
        if queued:
            owner._set_daily_activity("Automation validation queued in Settings terminal")
            owner._status_panel.append_syslog("automation validation queued")
            owner._sync_automation_test_state(
                status="Focused automation validation queued in the embedded terminal.",
                persist=True,
            )
        else:
            owner._sync_automation_test_state(
                status="Validation could not queue in the embedded terminal.",
                ok=False,
                persist=True,
            )
        return

    owner._sync_automation_test_state(status=f"Automation action unavailable: {action}", ok=False, persist=True)


def approve_latest_builder_task(owner: Any) -> dict[str, object]:
    """Find and approve the most recently staged builder task.

    Extracted from LauncherWindow._approve_latest_builder_task as part of TR54-B1.
    """
    from src.guppy.launcher_application.builder_workflow import (
        approve_builder_task,
        metrics_path,
        queue_path,
        results_path,
    )
    from src.guppy.launcher_application.storage_io import read_json_dict

    queue_file = queue_path()
    results_file = results_path()
    metrics_file = metrics_path()
    queue_payload = read_json_dict(queue_file)
    tasks = [
        item for item in queue_payload.get("tasks", [])
        if isinstance(item, dict)
    ] if isinstance(queue_payload, dict) else []
    pending_task = next(
        (
            item for item in reversed(tasks)
            if str(item.get("status", "")).strip() == "awaiting_approval"
            and isinstance(item.get("pending_approval"), dict)
        ),
        None,
    )
    if pending_task is None:
        raise ValueError("No staged builder task is awaiting approval.")
    active_instance = getattr(owner, "_active_instance_name", None) or "launcher"
    return approve_builder_task(
        str(pending_task.get("id", "")).strip(),
        queue_path=queue_file,
        results_path=results_file,
        metrics_path=metrics_file,
        approved_by=active_instance,
    )


def queue_builder_task(
    owner: Any,
    *,
    template_id: str,
    target_ref: str,
    instance_name: str,
    announce_text: str,
    automation_report_path: Path,
) -> dict[str, object]:
    """Render, enqueue, and announce a builder task.

    Extracted from LauncherWindow._queue_builder_task as part of TR54-B1.
    """
    from src.guppy.launcher_application.builder_workflow import enqueue_builder_task, render_builder_task

    task = render_builder_task(
        template_id,
        target_ref=target_ref,
        requested_by_instance=instance_name,
    )
    enqueue_builder_task(task)
    tools_view = getattr(owner, "_tools_view", None)
    if tools_view is not None:
        tools_view.set_builder_status(f"Queued {task['title']} for dry-run review")
    assistant_view = getattr(owner, "_assistant_view", None)
    if assistant_view is not None:
        assistant_view.add_system_message(
            f"Queued local builder task: {task['title']} -> {task['output_file_path']}"
        )
    set_act = getattr(owner, "_set_daily_activity", None)
    if callable(set_act):
        set_act(announce_text)
    status_panel = getattr(owner, "_status_panel", None)
    if status_panel is not None:
        status_panel.append_syslog(f"builder task queued: {task['id']}")
    owner._sync_automation_test_state(
        status=f"Queued {task['title']} for dry-run review.",
        report_path=automation_report_path,
        persist=True,
    )
    return task


def handle_builder_task_requested(
    owner: Any,
    payload: dict[str, object],
    *,
    automation_report_path: Path,
) -> None:
    """Handle a builder task request from the tools panel.

    Extracted from LauncherWindow._on_builder_task_requested as part of TR54-B1.
    """
    try:
        template_id = str(payload.get("template_id", "")).strip()
        target_ref = str(payload.get("target_ref", "")).strip()
        active_instance = getattr(owner, "_active_instance_name", "guppy-primary") or "guppy-primary"
        instance_name = str(payload.get("instance_name", active_instance)).strip() or active_instance
        owner._log_launcher_event(
            "tool_builder_task_requested",
            tool="builder_task",
            instance=instance_name,
            action=template_id,
            summary=target_ref,
        )
        task = queue_builder_task(
            owner,
            template_id=template_id,
            target_ref=target_ref,
            instance_name=instance_name,
            announce_text=f"Builder task queued for {instance_name}: {template_id}",
            automation_report_path=automation_report_path,
        )
        settings_hub = getattr(owner, "_settings_hub_view", None)
        if settings_hub is not None:
            settings_hub.set_automation_status(
                f"Queued {task['title']} from Tools. Review staged output in Settings when it is ready."
            )
    except Exception as exc:
        tools_view = getattr(owner, "_tools_view", None)
        if tools_view is not None:
            tools_view.set_builder_status(f"Queue failed: {exc}", ok=False)
        settings_hub = getattr(owner, "_settings_hub_view", None)
        if settings_hub is not None:
            settings_hub.set_automation_status(f"Queue failed: {exc}", ok=False)
        status_panel = getattr(owner, "_status_panel", None)
        if status_panel is not None:
            status_panel.append_syslog(f"builder task queue failed: {exc}")
        active_instance = getattr(owner, "_active_instance_name", "guppy-primary") or "guppy-primary"
        owner._log_launcher_event(
            "tool_builder_task_error",
            tool="builder_task",
            instance=active_instance,
            error=str(exc),
        )
    refresh = getattr(owner, "_refresh_tools_debug_surface", None)
    if callable(refresh):
        refresh()
