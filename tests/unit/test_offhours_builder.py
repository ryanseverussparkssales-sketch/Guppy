from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from utils import offhours_builder


class OffhoursBuilderTests(unittest.TestCase):
    def test_sanitize_builder_output_strips_terminal_control_sequences(self):
        dirty = "\x1b[31m```python\nprint('ok')\n```\x1b[0m\r\n"
        cleaned = offhours_builder.sanitize_builder_output(dirty)
        self.assertEqual(cleaned, "```python\nprint('ok')\n```")

    def test_render_builder_task_uses_safe_paths(self):
        with tempfile.TemporaryDirectory() as td:
            queue_path = Path(td) / "offhours_task_queue.json"
            task = offhours_builder.render_builder_task(
                "unit_test_stub",
                target_ref="src/guppy/api/server.py",
                requested_by_instance="builder-collab",
                queue_path=queue_path,
            )
            self.assertEqual(task["task_type"], "write")
            self.assertEqual(task["requested_by_instance"], "builder-collab")
            self.assertTrue(task["output_file_path"].startswith("tests/unit/"))

    def test_enqueue_builder_task_appends_queue(self):
        with tempfile.TemporaryDirectory() as td:
            queue_path = Path(td) / "offhours_task_queue.json"
            metrics_path = Path(td) / "offhours_metrics.jsonl"
            task = offhours_builder.render_builder_task("docs_followup", target_ref="builder drift", queue_path=queue_path)
            offhours_builder.enqueue_builder_task(task, queue_path=queue_path, metrics_path=metrics_path)
            payload = json.loads(queue_path.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["tasks"]), 1)
            self.assertIn("builder_task_enqueued", metrics_path.read_text(encoding="utf-8"))

    def test_load_builder_templates_backfills_new_default_templates(self):
        with tempfile.TemporaryDirectory() as td:
            template_path = Path(td) / "builder_task_templates.json"
            template_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "templates": [
                            {
                                "id": "unit_test_stub",
                                "title": "Generate unit test stub",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            templates = offhours_builder.load_builder_templates(template_path)
            ids = {item["id"] for item in templates}
            self.assertIn("unit_test_stub", ids)
            self.assertIn("ui_input_audit", ids)
            self.assertIn("schema_example", ids)
            self.assertIn("approval_handoff", ids)
            self.assertIn("stress_validation_note", ids)

    def test_approve_builder_task_writes_only_safe_outputs(self):
        old_root = offhours_builder.ROOT
        old_runtime = offhours_builder.RUNTIME
        old_dry_run = offhours_builder.DRY_RUN_DIR
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                runtime = root / "runtime"
                dry_run_dir = runtime / "offhours_results" / "dry_run"
                dry_run_dir.mkdir(parents=True, exist_ok=True)
                staged_file = dry_run_dir / "sample.staged"
                staged_file.write_text("\x1b[32mprint('ok')\x1b[0m\n", encoding="utf-8")

                offhours_builder.ROOT = root
                offhours_builder.RUNTIME = runtime
                offhours_builder.DRY_RUN_DIR = dry_run_dir

                queue_path = runtime / "offhours_task_queue.json"
                queue_path.parent.mkdir(parents=True, exist_ok=True)
                queue_path.write_text(
                    json.dumps(
                        {
                            "version": 1,
                            "tasks": [
                                {
                                    "id": "builder_unit_test",
                                    "title": "Generate unit test stub",
                                    "status": "awaiting_approval",
                                    "output_file_path": "tests/unit/test_builder_sample.py",
                                    "pending_approval": {
                                        "staged_file": str(staged_file),
                                        "workspace_file": "tests/unit/test_builder_sample.py",
                                    },
                                }
                            ],
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                results_path = runtime / "offhours_task_results.jsonl"
                metrics_path = runtime / "offhours_metrics.jsonl"

                payload = offhours_builder.approve_builder_task(
                    "builder_unit_test",
                    queue_path=queue_path,
                    results_path=results_path,
                    metrics_path=metrics_path,
                    approved_by="test-suite",
                )

                written = root / "tests" / "unit" / "test_builder_sample.py"
                self.assertTrue(written.exists())
                self.assertEqual(written.read_text(encoding="utf-8"), "print('ok')\n")
                self.assertEqual(payload["approved_by"], "test-suite")
                self.assertIn("offhours_task_approved", results_path.read_text(encoding="utf-8"))
        finally:
            offhours_builder.ROOT = old_root
            offhours_builder.RUNTIME = old_runtime
            offhours_builder.DRY_RUN_DIR = old_dry_run

    def test_build_builder_report_normalizes_pending_paths_and_stress_evidence(self):
        old_root = offhours_builder.ROOT
        old_runtime = offhours_builder.RUNTIME
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                runtime = root / "runtime"
                dry_run_dir = runtime / "offhours_results" / "dry_run"
                stress_dir = runtime / "stress_reports"
                dry_run_dir.mkdir(parents=True, exist_ok=True)
                stress_dir.mkdir(parents=True, exist_ok=True)
                staged_file = dry_run_dir / "sample.staged"
                staged_file.write_text("# staged\n", encoding="utf-8")
                stress_report = stress_dir / "stress_report_20260421_010101.json"
                stress_report.write_text(
                    json.dumps({"failure_count": 0, "profile": "bounded", "status": "pass"}),
                    encoding="utf-8",
                )
                queue_path = runtime / "offhours_task_queue.json"
                results_path = runtime / "offhours_task_results.jsonl"
                metrics_path = runtime / "offhours_metrics.jsonl"
                queue_path.write_text(
                    json.dumps(
                        {
                            "version": 1,
                            "tasks": [
                                {
                                    "id": "builder_pending",
                                    "title": "Draft approval handoff",
                                    "status": "awaiting_approval",
                                    "requested_by_instance": "builder-collab",
                                    "target_ref": "off-hours builder lane",
                                    "output_file_path": "docs/generated/offhours_builder_approval_handoff.md",
                                    "updated_utc": "2026-04-21T02:00:00+00:00",
                                    "pending_approval": {
                                        "staged_file": str(staged_file),
                                        "workspace_file": "docs/generated/offhours_builder_approval_handoff.md",
                                    },
                                }
                            ],
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                results_path.write_text(
                    json.dumps(
                        {
                            "ts": "2026-04-21T02:05:00+00:00",
                            "event": "offhours_task_complete",
                            "title": "Draft approval handoff",
                            "status": "awaiting_approval",
                            "output_file": str(root / "runtime" / "offhours_results" / "builder_pending.md"),
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                metrics_path.write_text(
                    json.dumps(
                        {
                            "ts": "2026-04-21T02:06:00+00:00",
                            "event": "builder_task_enqueued",
                            "template_id": "approval_handoff",
                            "requested_by_instance": "builder-collab",
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )

                offhours_builder.ROOT = root
                offhours_builder.RUNTIME = runtime

                report = offhours_builder.build_builder_report(
                    queue_path=queue_path,
                    results_path=results_path,
                    metrics_path=metrics_path,
                )

                self.assertEqual(report["queue_counts"]["awaiting_approval"], 1)
                self.assertEqual(
                    report["pending_approvals"][0]["staged_file"],
                    "runtime/offhours_results/dry_run/sample.staged",
                )
                self.assertEqual(
                    report["stress_validation"]["path"],
                    "runtime/stress_reports/stress_report_20260421_010101.json",
                )
                self.assertEqual(report["stress_validation"]["failure_count"], 0)
                self.assertEqual(
                    report["recent_results"][0]["output_file"],
                    "runtime/offhours_results/builder_pending.md",
                )
                self.assertTrue(
                    any("Draft approval handoff" in item["summary"] for item in report["recent_activity"])
                )
        finally:
            offhours_builder.ROOT = old_root
            offhours_builder.RUNTIME = old_runtime
