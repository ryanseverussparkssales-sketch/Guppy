from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from src.guppy.launcher_application.automation_test_coordination import (
    preferred_builder_workspace_name,
    read_assistant_home_labels,
    user_test_evidence_paths,
    write_launcher_automation_report,
)
from src.guppy.launcher_application.automation_test_support import build_automation_test_snapshot


def test_preferred_builder_workspace_name_uses_builder_collab_when_available() -> None:
    snapshot = {
        "instances": [
            {"name": "guppy-primary", "enabled": True},
            {"name": "builder-collab", "enabled": True},
        ]
    }

    assert preferred_builder_workspace_name("guppy-primary", snapshot) == "builder-collab"


def test_read_assistant_home_labels_tolerates_missing_widgets() -> None:
    owner = SimpleNamespace(_assistant_view=SimpleNamespace(_background_event=SimpleNamespace(text=lambda: " Ready ")))

    labels = read_assistant_home_labels(owner)

    assert labels["background_event"] == "Ready"
    assert labels["workspace_summary"] == ""
    assert labels["runtime_facts"] == ""


def test_user_test_evidence_paths_point_into_runtime_dir(tmp_path: Path) -> None:
    evidence_json, evidence_md = user_test_evidence_paths(tmp_path)

    assert evidence_json == tmp_path / "user_test_evidence.json"
    assert evidence_md == tmp_path / "user_test_evidence.md"


def test_write_launcher_automation_report_records_preferred_workspace(tmp_path: Path, monkeypatch) -> None:
    queue_file = tmp_path / "queue.json"
    results_file = tmp_path / "results.json"
    metrics_file = tmp_path / "metrics.json"
    queue_file.write_text(json.dumps({"tasks": []}), encoding="utf-8")
    results_file.write_text(json.dumps({"results": []}), encoding="utf-8")
    metrics_file.write_text(json.dumps({}), encoding="utf-8")

    import src.guppy.launcher_application.builder_workflow as builder_workflow

    monkeypatch.setattr(builder_workflow, "queue_path", lambda: queue_file)
    monkeypatch.setattr(builder_workflow, "results_path", lambda: results_file)
    monkeypatch.setattr(builder_workflow, "metrics_path", lambda: metrics_file)

    owner = SimpleNamespace(
        _active_instance_name="guppy-primary",
        _last_instance_snapshot={
            "instances": [
                {"name": "guppy-primary", "enabled": True},
                {"name": "builder-collab", "enabled": True},
            ]
        },
    )
    report_path = tmp_path / "automation_report.json"

    out = write_launcher_automation_report(
        owner,
        automation_report_path=report_path,
        validation_command="pytest tests/unit/test_offhours_builder.py -q",
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["active_workspace"] == "guppy-primary"
    assert payload["preferred_builder_workspace"] == "builder-collab"
    assert payload["validation_command"] == "pytest tests/unit/test_offhours_builder.py -q"


def test_build_automation_snapshot_surfaces_pending_approval_and_stress_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_dir = tmp_path / "runtime"
    stress_dir = runtime_dir / "stress_reports"
    stress_dir.mkdir(parents=True)
    queue_file = runtime_dir / "queue.json"
    results_file = runtime_dir / "results.jsonl"
    metrics_file = runtime_dir / "metrics.jsonl"
    staged_file = runtime_dir / "offhours_results" / "dry_run" / "builder_note.staged"
    staged_file.parent.mkdir(parents=True)
    staged_file.write_text("# staged\n", encoding="utf-8")
    queue_file.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "builder_pending",
                        "title": "Draft approval handoff",
                        "status": "awaiting_approval",
                        "requested_by_instance": "builder-collab",
                        "output_file_path": "docs/generated/builder_lane_approval_handoff.md",
                        "pending_approval": {
                            "staged_file": str(staged_file),
                            "workspace_file": "docs/generated/builder_lane_approval_handoff.md",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    results_file.write_text("", encoding="utf-8")
    metrics_file.write_text(
        json.dumps(
            {
                "ts": "2026-04-21T03:00:00+00:00",
                "event": "builder_task_enqueued",
                "title": "Draft approval handoff",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (stress_dir / "stress_report_20260421_030000.json").write_text(
        json.dumps({"failure_count": 0, "profile": "bounded", "status": "pass"}),
        encoding="utf-8",
    )

    import src.guppy.launcher_application.builder_workflow as builder_workflow
    import src.guppy.launcher_application.automation_test_support as automation_test_support
    import utils.offhours_builder as offhours_builder

    old_root = offhours_builder.ROOT
    old_runtime = offhours_builder.RUNTIME
    monkeypatch.setattr(builder_workflow, "queue_path", lambda: queue_file)
    monkeypatch.setattr(builder_workflow, "results_path", lambda: results_file)
    monkeypatch.setattr(builder_workflow, "metrics_path", lambda: metrics_file)
    monkeypatch.setattr(automation_test_support, "queue_path", lambda: queue_file)
    monkeypatch.setattr(automation_test_support, "results_path", lambda: results_file)
    monkeypatch.setattr(automation_test_support, "metrics_path", lambda: metrics_file)
    monkeypatch.setattr(
        "src.guppy.launcher_application.automation_test_support.read_json_dict",
        lambda _path: json.loads(queue_file.read_text(encoding="utf-8")),
    )
    try:
        offhours_builder.ROOT = tmp_path
        offhours_builder.RUNTIME = runtime_dir
        snapshot = build_automation_test_snapshot(
            runtime_dir=runtime_dir,
            repo_root=tmp_path,
            active_instance_name="guppy-primary",
            preferred_builder_workspace="builder-collab",
            automation_report_path=runtime_dir / "automation_report.json",
            validation_command="pytest tests/unit/test_offhours_builder.py -q",
        )
    finally:
        offhours_builder.ROOT = old_root
        offhours_builder.RUNTIME = old_runtime

    assert "Draft approval handoff" in snapshot["approval_state"]
    assert "builder-collab" in snapshot["approval_state"]
    assert snapshot["staged_file"] == "Latest staged output: runtime/offhours_results/dry_run/builder_note.staged"
    assert snapshot["stress_report_path"] == "runtime/stress_reports/stress_report_20260421_030000.json"
