from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]


def _load_dev_workflow_module():
    spec = importlib.util.spec_from_file_location("guppy_dev_workflow", ROOT / "tools" / "dev_workflow.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _repo_tmp_dir(label: str) -> Path:
    path = ROOT / ".tmp" / "pytest-local" / f"{label}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_write_release_outputs_includes_ref_and_next_review_step() -> None:
    dev_workflow = _load_dev_workflow_module()
    tmp_dir = _repo_tmp_dir("release-summary-pass")
    try:
        receipt_path = tmp_dir / "release-check-receipt.json"
        summary_path = tmp_dir / "release-check-summary.txt"
        results = [
            dev_workflow.StepResult(
                name="guardrails (delta)",
                command=["python", "tools/dev_workflow.py", "dev-check", "--guard-scope", "delta"],
                returncode=0,
                duration_seconds=1.2,
            )
        ]

        dev_workflow._write_release_outputs("release-check", results, receipt_path, summary_path)

        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        summary = summary_path.read_text(encoding="utf-8")

        assert receipt["ok"] is True
        assert receipt["ref"].startswith("release-check-")
        assert receipt["gate_state"] == "1/1 passed"
        assert "Review release-check-summary.txt and release-check-receipt.json" in receipt["next_review_step"]
        assert "ref: release-check-" in summary
        assert "gate_state: 1/1 passed" in summary
        assert "## Next Review Step" in summary
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_write_release_outputs_uses_fix_first_on_failure() -> None:
    dev_workflow = _load_dev_workflow_module()
    tmp_dir = _repo_tmp_dir("release-summary-fail")
    try:
        receipt_path = tmp_dir / "release-check-receipt.json"
        summary_path = tmp_dir / "release-check-summary.txt"
        results = [
            dev_workflow.StepResult(
                name="guardrails (delta)",
                command=["python", "tools/dev_workflow.py", "dev-check", "--guard-scope", "delta"],
                returncode=1,
                duration_seconds=1.2,
            )
        ]

        dev_workflow._write_release_outputs("release-check", results, receipt_path, summary_path)

        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        summary = summary_path.read_text(encoding="utf-8")

        assert receipt["ok"] is False
        assert receipt["gate_state"] == "0/1 passed"
        assert "rerun `python tools/dev_workflow.py release-check`" in receipt["next_review_step"]
        assert "## Fix-First" in summary
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_release_receipt_schema_stability() -> None:
    dev_workflow = _load_dev_workflow_module()
    tmp_dir = _repo_tmp_dir("release-schema")
    try:
        receipt_path = tmp_dir / "release-check-receipt.json"
        summary_path = tmp_dir / "release-check-summary.txt"
        results = [
            dev_workflow.StepResult(
                name="guardrails (delta)",
                command=["python", "tools/dev_workflow.py", "dev-check", "--guard-scope", "delta"],
                returncode=0,
                duration_seconds=0.8,
            )
        ]

        dev_workflow._write_release_outputs("release-check", results, receipt_path, summary_path)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

        assert set(receipt.keys()) == {
            "subcommand",
            "ref",
            "python",
            "finished_at",
            "ok",
            "gate_state",
            "steps_total",
            "steps_passed",
            "next_review_step",
            "steps",
            "workspace_paths",
        }
        assert set(receipt["steps"][0].keys()) == {
            "name",
            "command",
            "returncode",
            "duration_seconds",
            "ok",
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
