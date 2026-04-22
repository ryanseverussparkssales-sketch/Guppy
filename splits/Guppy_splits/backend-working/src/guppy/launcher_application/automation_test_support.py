from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from src.guppy.launcher_application.builder_workflow import (
    build_builder_report,
    metrics_path,
    queue_path,
    results_path,
)
from src.guppy.launcher_application.storage_io import read_json_dict, read_jsonl_tail, write_json_atomic


def event_level(item: Mapping[str, object]) -> str:
    event = str(item.get("event", "") or "").lower()
    summary = json.dumps(dict(item), ensure_ascii=True).lower()
    if "error" in event or "error" in summary or "failed" in summary:
        return "ERROR"
    if "warn" in event or "warning" in summary or "over_budget" in event:
        return "WARN"
    return "INFO"


def display_repo_path(repo_root: Path, path: Path | str | None) -> str:
    if path is None:
        return ""
    target = Path(path) if not isinstance(path, Path) else path
    try:
        return str(target.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except Exception:
        return str(target).replace("\\", "/")


def latest_stress_report_path(runtime_dir: Path) -> Path | None:
    candidates: list[Path] = []
    for folder in (runtime_dir, runtime_dir / "stress_reports"):
        if not folder.exists():
            continue
        candidates.extend(folder.glob("stress_report_*.json"))
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def recent_launcher_event_summaries(runtime_dir: Path, limit: int = 4) -> list[str]:
    items = read_jsonl_tail(runtime_dir / "launcher_events.jsonl", limit=24)
    rendered: list[str] = []
    for item in reversed(items):
        if not isinstance(item, dict):
            continue
        level = event_level(item)
        event = str(item.get("event", "event") or "event").replace("_", " ").strip()
        detail = (
            str(item.get("summary", "") or "").strip()
            or str(item.get("status", "") or "").strip()
            or str(item.get("action", "") or "").strip()
            or str(item.get("instance", "") or "").strip()
            or str(item.get("destination", "") or "").strip()
            or str(item.get("command", "") or "").strip()
        )
        line = f"{level} {event}"
        if detail:
            snippet = detail[:88] + ("..." if len(detail) > 88 else "")
            line += f": {snippet}"
        rendered.append(line)
        if len(rendered) >= limit:
            break
    return rendered


def write_user_test_evidence_summary(summary_path: Path, payload: Mapping[str, object]) -> str:
    workspace = payload.get("active_workspace", {}) if isinstance(payload.get("active_workspace"), dict) else {}
    home = payload.get("home", {}) if isinstance(payload.get("home"), dict) else {}
    automation = payload.get("automation", {}) if isinstance(payload.get("automation"), dict) else {}
    windows_ops = payload.get("windows_ops", {}) if isinstance(payload.get("windows_ops"), dict) else {}
    recent_events = [
        str(item).strip()
        for item in payload.get("recent_operator_notes", [])
        if str(item).strip()
    ] if isinstance(payload.get("recent_operator_notes"), list) else []
    lines = [
        "# User Test Evidence Pack",
        "",
        f"Generated: {payload.get('generated_at', '')}",
        f"Active workspace: {workspace.get('name', payload.get('active_workspace_name', 'unknown'))}",
        f"Workspace role: {workspace.get('type', 'unknown')}",
        f"Preferred builder workspace: {payload.get('preferred_builder_workspace', '')}",
        f"Automation status: {automation.get('status', '')}",
        f"Builder report: {automation.get('builder_report_path', '')}",
        f"Evidence JSON: {payload.get('evidence_json_path', '')}",
        f"Latest stress run: {payload.get('latest_stress_report', '') or 'not recorded'}",
        "",
        "## Home",
        "",
        f"- Background activity: {home.get('background_event', '')}",
        f"- Workspace summary: {home.get('workspace_summary', '')}",
        f"- Runtime facts: {home.get('runtime_facts', '')}",
        f"- Route facts: {home.get('route_facts', '')}",
        "",
        "## Setup & Health",
        "",
        f"- Next step: {windows_ops.get('next', '')}",
        f"- Service status: {windows_ops.get('service', '')}",
        f"- Release check: {windows_ops.get('gate', '')}",
        "",
        "## Recent Operator Notes",
        "",
    ]
    if recent_events:
        lines.extend([f"- {item}" for item in recent_events])
    else:
        lines.append("- No recent launcher notes were recorded.")
    text = "\n".join(lines).strip() + "\n"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(text, encoding="utf-8")
    return text


def write_user_test_evidence_pack(
    *,
    runtime_dir: Path,
    repo_root: Path,
    active_instance_name: str,
    preferred_builder_workspace: str,
    last_instance_snapshot: Mapping[str, object] | None,
    home_labels: Mapping[str, str],
    automation_status: str,
    windows_snapshot: Mapping[str, object] | None,
    report_path: Path | None,
    automation_report_path: Path,
    validation_command: str,
    evidence_json_path: Path,
    evidence_summary_path: Path,
) -> dict[str, str]:
    snapshot = last_instance_snapshot if isinstance(last_instance_snapshot, Mapping) else {}
    items = snapshot.get("instances", []) if isinstance(snapshot, Mapping) else []
    active_workspace = next(
        (
            item for item in items
            if isinstance(item, dict) and str(item.get("name", "")).strip() == active_instance_name
        ),
        {"name": active_instance_name or "guppy-primary", "type": "user_instance"},
    )
    stress_report = latest_stress_report_path(runtime_dir)
    builder_report = Path(report_path) if isinstance(report_path, Path) else automation_report_path
    payload: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "active_workspace_name": active_instance_name,
        "preferred_builder_workspace": preferred_builder_workspace,
        "active_workspace": active_workspace if isinstance(active_workspace, dict) else {},
        "home": {
            "background_event": str(home_labels.get("background_event", "") or "").strip(),
            "workspace_summary": str(home_labels.get("workspace_summary", "") or "").strip(),
            "runtime_facts": str(home_labels.get("runtime_facts", "") or "").strip(),
            "route_facts": str(home_labels.get("route_facts", "") or "").strip(),
            "recovery_summary": str(home_labels.get("recovery_summary", "") or "").strip(),
        },
        "automation": {
            "status": str(automation_status or "").strip(),
            "builder_report_path": display_repo_path(repo_root, builder_report),
            "validation_command": validation_command,
        },
        "windows_ops": dict(windows_snapshot) if isinstance(windows_snapshot, Mapping) else {},
        "latest_stress_report": display_repo_path(repo_root, stress_report) if stress_report else "",
        "recent_operator_notes": recent_launcher_event_summaries(runtime_dir, limit=5),
    }
    payload["evidence_json_path"] = display_repo_path(repo_root, evidence_json_path)
    payload["evidence_summary_path"] = display_repo_path(repo_root, evidence_summary_path)
    write_json_atomic(evidence_json_path, payload)
    write_user_test_evidence_summary(evidence_summary_path, payload)
    recent_operator_notes = payload.get("recent_operator_notes", [])
    recent_events = (
        "Recent operator notes: " + " | ".join(recent_operator_notes)
        if isinstance(recent_operator_notes, list) and recent_operator_notes
        else "Recent operator notes: no recent launcher notes recorded yet."
    )
    return {
        "json_path": display_repo_path(repo_root, evidence_json_path),
        "summary_path": display_repo_path(repo_root, evidence_summary_path),
        "stress_report_path": display_repo_path(repo_root, stress_report) if stress_report else "",
        "recent_events": recent_events,
    }


def build_automation_test_snapshot(
    *,
    runtime_dir: Path,
    repo_root: Path,
    active_instance_name: str,
    preferred_builder_workspace: str,
    automation_report_path: Path,
    validation_command: str,
    report_path: Path | None = None,
    status: str = "",
    evidence_pack_path: str = "",
    stress_report_path: str = "",
    recent_events: str = "",
) -> dict[str, str]:
    queue_file = queue_path()
    results_file = results_path()
    metrics_file = metrics_path()
    report = build_builder_report(queue_path=queue_file, results_path=results_file, metrics_path=metrics_file)
    queue_payload = read_json_dict(queue_file)
    tasks = [
        item for item in queue_payload.get("tasks", [])
        if isinstance(item, dict)
    ] if isinstance(queue_payload, dict) else []
    counts = report.get("queue_counts", {}) if isinstance(report, dict) else {}
    pending = int(counts.get("pending", 0) or 0)
    running = int(counts.get("running", 0) or 0)
    awaiting = int(counts.get("awaiting_approval", 0) or 0)
    done = int(counts.get("done", 0) or 0)
    latest_pending = next(
        (
            item for item in reversed(tasks)
            if str(item.get("status", "")).strip() == "awaiting_approval"
            and isinstance(item.get("pending_approval"), dict)
        ),
        {},
    )
    latest_result = next(
        (
            item for item in reversed(report.get("recent_results", []))
            if isinstance(item, dict)
        ),
        {},
    )
    latest_staged_file = str(
        (latest_pending.get("pending_approval", {}) if isinstance(latest_pending, dict) else {}).get("staged_file", "")
    ).strip()
    latest_result_path = str(latest_result.get("output_file", "") or "").strip()
    if not latest_result_path:
        latest_done_task = next(
            (
                item for item in reversed(tasks)
                if str(item.get("status", "")).strip() == "done"
            ),
            {},
        )
        latest_result_path = str(latest_done_task.get("approved_output_file", "") or "").strip()
    if preferred_builder_workspace == "builder-collab":
        workspace_line = (
            f"Workspace step: active={active_instance_name} | preferred=builder-collab | "
            "switch here before queueing if you want the default builder workspace."
        )
    else:
        workspace_line = (
            f"Workspace step: active={active_instance_name} | preferred={preferred_builder_workspace} | "
            "builder-collab is unavailable, so automation stays in the current workspace."
        )
    if latest_pending:
        approval_state = (
            "Latest approval: awaiting approval for "
            f"{str(latest_pending.get('title', latest_pending.get('id', 'builder task')))}"
        )
    elif latest_result_path:
        approval_state = f"Latest approval: most recent approved output is {latest_result_path}"
    else:
        approval_state = "Latest approval: no staged task is awaiting approval yet."
    if not evidence_pack_path:
        evidence_pack_path = display_repo_path(repo_root, runtime_dir / "user_test_evidence.md")
    if not stress_report_path:
        latest_stress = latest_stress_report_path(runtime_dir)
        stress_report_path = display_repo_path(repo_root, latest_stress) if latest_stress else ""
    if not recent_events:
        recent_items = recent_launcher_event_summaries(runtime_dir, limit=4)
        recent_events = (
            "Recent operator notes: " + " | ".join(recent_items)
            if recent_items else
            "Recent operator notes: no recent launcher notes recorded yet."
        )
    return {
        "workspace": workspace_line,
        "queue_counts": (
            f"Queue counts: pending={pending} | running={running} | awaiting approval={awaiting} | done={done}"
        ),
        "staged_file": (
            f"Latest staged output: {latest_staged_file}"
            if latest_staged_file
            else "Latest staged output: nothing is waiting for approval yet."
        ),
        "result_path": (
            f"Latest result: {latest_result_path}"
            if latest_result_path
            else "Latest result: no approved builder output has been recorded yet."
        ),
        "approval_state": approval_state,
        "report_path": display_repo_path(repo_root, report_path or automation_report_path),
        "evidence_pack_path": evidence_pack_path,
        "stress_report_path": stress_report_path,
        "recent_events": recent_events,
        "validation_command": validation_command,
        "status": str(status or "").strip(),
    }
