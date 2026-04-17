from __future__ import annotations

from pathlib import Path

from src.guppy.launcher_application.windows_ops_guidance import (
    summarize_windows_recipe_result,
    windows_ops_guidance,
)
from src.guppy.launcher_application.windows_ops_runtime import (
    build_windows_release_receipt_payload,
    summarize_release_dry_run_report,
)


def test_summarize_release_dry_run_report_builds_fix_first_guidance() -> None:
    summary = summarize_release_dry_run_report(
        {
            "ok": False,
            "checks": [
                {"name": "beta_policy", "ok": False, "returncode": 1},
                {"name": "pilot_gate", "ok": False, "returncode": 1},
            ],
            "required_files": [
                {"path": "runtime/windows_release_summary.md", "exists": False},
            ],
        }
    )

    assert summary["summary"] == "FAIL | checks 0/2 | missing files 1"
    assert "beta_policy" in summary["failed_checks"]
    assert "runtime/windows_release_summary.md" in summary["missing_files"]
    assert summary["recommendation_details"][0]["fix_target"] == (
        "config/beta_tool_allowlist.txt / docs/REMOTE_BETA_EXE_POLICY.md"
    )


def test_build_windows_release_receipt_payload_preserves_release_review_order() -> None:
    payload = build_windows_release_receipt_payload(
        Path("runtime/windows_ops_state.json"),
        Path("runtime/windows_release_receipt.json"),
        Path("runtime/windows_release_summary.md"),
        "release_dry_run",
        "Dry run passed",
        "review bundle refreshed",
        ok=True,
        event_id="evt-123",
        gate_summary="PASS",
    )

    assert payload["release_stage"] == "release_gate"
    assert payload["event_id"] == "evt-123"
    assert payload["review_order"] == [
        "runtime/beta_release_dry_run_report.json",
        "runtime/windows_release_receipt.json",
        "runtime/windows_release_summary.md",
    ]


def test_windows_ops_guidance_and_recipe_summary_cover_common_paths() -> None:
    queued = windows_ops_guidance("release_dry_run", ok=True, phase="queued")
    failed = windows_ops_guidance("repair_runtime", ok=False, phase="completed")
    summary, changes = summarize_windows_recipe_result(
        {
            "label": "WINDOWS VERIFY",
            "steps_total": 3,
            "steps_completed": 2,
            "ok": False,
            "changes": "Runtime checks refreshed.",
            "failed_steps": [{"index": 3, "command": "python tools/verify_runtime_challengers.py"}],
        }
    )

    assert queued["entry_point"] == "python tools/beta_release_dry_run.py"
    assert "Inspect launcher logs" in failed["next_step"]
    assert summary == "WINDOWS VERIFY stopped after 2/3 successful servicing step(s). Failed step 3."
    assert changes == "Runtime checks refreshed. Failed command: python tools/verify_runtime_challengers.py."
