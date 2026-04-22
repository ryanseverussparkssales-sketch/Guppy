import json
from pathlib import Path

from src.guppy.launcher_application.windows_ops_coordination import (
    WindowsOpsStateRecord,
    begin_windows_ops_chain,
    complete_windows_ops_terminal_recipe,
    persist_windows_ops_state,
    progress_windows_ops_chain,
)


def _write_state(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_persist_windows_ops_state_writes_payload_and_feedback(tmp_path: Path) -> None:
    state_path = tmp_path / "runtime" / "windows_ops_state.json"
    receipt_path = tmp_path / "runtime" / "windows_release_receipt.json"
    summary_path = tmp_path / "runtime" / "windows_release_summary.md"

    update = persist_windows_ops_state(
        WindowsOpsStateRecord(
            action="verify_runtime",
            summary="WINDOWS VERIFY completed 1/1 servicing step(s).",
            changes="Refreshes readiness evidence.",
            ok=True,
            commands=["python tools/verify_ollama_runtime.py --prompt ok"],
            event_id="recipe-verify-1",
            steps_completed=1,
            steps_total=1,
            phase="completed",
            next_step="Review the runtime evidence in App Mgmt.",
            fix_target="App Mgmt > Windows Ops",
            docs_hint="docs/TROUBLESHOOTING.md",
            entry_point="python src/guppy/cli/launch.py launcher",
            artifacts=[
                {
                    "id": "diagnostics",
                    "label": "diagnostics bundle",
                    "path": "runtime/diagnostics_bundle_20260415_120000.json",
                }
            ],
        ),
        state_path=state_path,
        receipt_path=receipt_path,
        summary_path=summary_path,
        write_state=_write_state,
    )

    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert payload["action"] == "verify_runtime"
    assert payload["event_id"] == "recipe-verify-1"
    assert payload["release_receipt"].endswith("windows_release_receipt.json")
    assert payload["release_summary"].endswith("windows_release_summary.md")
    assert update.feedback["receipt_path"].endswith("windows_release_receipt.json")
    assert update.feedback["summary_path"].endswith("windows_release_summary.md")
    assert receipt_path.exists()
    assert summary_path.exists()


def test_complete_windows_ops_terminal_recipe_includes_gate_fix_fields() -> None:
    completion = complete_windows_ops_terminal_recipe(
        {
            "action": "release_dry_run",
            "label": "WINDOWS RELEASE DRY RUN",
            "ok": False,
            "id": "recipe-release-1",
            "commands": ["python tools/beta_release_dry_run.py"],
            "steps_completed": 1,
            "steps_total": 1,
            "changes": "Runs the beta release dry-run gate.",
        },
        dynamic_changes="beta release dry-run report refreshed",
        artifacts=[
            {
                "id": "release_dry_run",
                "label": "release dry-run report",
                "path": "runtime/beta_release_dry_run_report.json",
            }
        ],
        guidance={
            "next_step": "Fix the failing release gate before packaging.",
            "fix_target": "tools/beta_release_dry_run.py",
            "docs_hint": "docs/PACKAGING.md",
            "entry_point": "python tools/beta_release_dry_run.py",
        },
        gate_details={
            "summary": "FAIL | checks 1/2 | missing files 1",
            "detail": "failed checks: pilot_gate | missing: FINAL_HANDOFF_PREP.md",
            "failed_checks": ["pilot_gate"],
            "missing_files": ["docs/archive/planning-history/FINAL_HANDOFF_PREP.md"],
            "passed_checks": 1,
            "total_checks": 2,
            "recommendations": [
                "Fix the pilot gate next by reviewing pilot_exit_check failures and rerunning the release dry-run."
            ],
            "recommendation_details": [
                {
                    "text": "Fix the pilot gate next by reviewing pilot_exit_check failures and rerunning the release dry-run.",
                    "fix_target": "tools/pilot_exit_check.py / runtime/pilot_exit_report.json",
                    "docs_hint": "docs/PACKAGING.md",
                    "entry_point": "python tools/pilot_exit_check.py --allow-limited-go",
                }
            ],
        },
        receipt_path=Path("runtime/windows_release_receipt.json"),
        summary_path=Path("runtime/windows_release_summary.md"),
    )

    assert "WINDOWS RELEASE DRY RUN failed" in completion.summary
    assert "beta release dry-run report refreshed" in completion.state_record.changes
    assert completion.state_record.gate_summary == "FAIL | checks 1/2 | missing files 1"
    assert completion.event_fields["gate_fix_target"] == "tools/pilot_exit_check.py / runtime/pilot_exit_report.json"
    assert completion.event_fields["gate_fix_command"] == "python tools/pilot_exit_check.py --allow-limited-go"


def test_progress_windows_ops_chain_uses_overall_result_for_guidance() -> None:
    chain = begin_windows_ops_chain(
        "repair_runtime",
        steps=["health_snapshot", "warmup"],
        changes="Captures a snapshot and then warms the runtime.",
    )

    first = progress_windows_ops_chain(
        chain,
        "health_snapshot",
        ok=False,
        summary="snapshot failed",
        guidance_builder=lambda action, overall_ok: {
            "next_step": f"{action} {'ok' if overall_ok else 'fail'}",
            "fix_target": "App Mgmt > Windows Ops",
            "docs_hint": "docs/TROUBLESHOOTING.md",
            "entry_point": "python src/guppy/cli/launch.py launcher",
        },
        artifacts=[],
        receipt_path=Path("runtime/windows_release_receipt.json"),
        summary_path=Path("runtime/windows_release_summary.md"),
    )

    assert first.matched is True
    assert first.completed is False
    assert first.next_chain is not None

    second = progress_windows_ops_chain(
        first.next_chain,
        "warmup",
        ok=True,
        summary="warmup finished",
        guidance_builder=lambda action, overall_ok: {
            "next_step": f"{action} {'ok' if overall_ok else 'fail'}",
            "fix_target": "App Mgmt > Windows Ops",
            "docs_hint": "docs/TROUBLESHOOTING.md",
            "entry_point": "python src/guppy/cli/launch.py launcher",
        },
        artifacts=[
            {
                "id": "diagnostics",
                "label": "diagnostics bundle",
                "path": "runtime/diagnostics_bundle_20260415_120000.json",
            }
        ],
        receipt_path=Path("runtime/windows_release_receipt.json"),
        summary_path=Path("runtime/windows_release_summary.md"),
    )

    assert second.completed is True
    assert second.state_record is not None
    assert second.state_record.ok is False
    assert second.state_record.next_step == "repair_runtime fail"
    assert second.event_fields is not None
    assert second.event_fields["ok"] is False
