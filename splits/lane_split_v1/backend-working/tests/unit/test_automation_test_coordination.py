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
