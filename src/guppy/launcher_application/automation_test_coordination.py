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
