from src.guppy.launcher_application.windows_ops_state import (
    advance_windows_ops_chain,
    build_windows_ops_feedback_kwargs,
    build_windows_ops_state_payload,
    normalize_windows_gate_details,
    start_windows_ops_chain,
)


def test_windows_ops_chain_helpers_complete_recovery_summary() -> None:
    chain = start_windows_ops_chain("repair_runtime", ["verify_runtime", "start_supervised_api"], "Repairs runtime.")
    assert chain is not None

    first = advance_windows_ops_chain(chain, "verify_runtime", ok=True, summary="verify passed")
    assert first.matched is True
    assert first.completed is False
    assert first.steps_completed == 1
    assert first.next_chain is not None

    second = advance_windows_ops_chain(first.next_chain, "start_supervised_api", ok=False, summary="api still down")
    assert second.completed is True
    assert second.parent_action == "repair_runtime"
    assert second.overall_ok is False
    assert "verify_runtime=OK" in second.summary_text
    assert "start_supervised_api=FAIL" in second.summary_text
    assert "api still down" in second.change_text


def test_windows_ops_state_payload_and_feedback_use_structured_fields() -> None:
    payload = build_windows_ops_state_payload(
        action="release_dry_run",
        ok=False,
        summary="Release dry run failed",
        changes="Pilot gate failed",
        commands=["python tools/beta_release_dry_run.py"],
        event_id="recipe-1",
        steps_completed=1,
        steps_total=1,
        artifacts=[{"id": "report", "label": "report", "path": "runtime/report.json"}],
        release_receipt="runtime/windows_release_receipt.json",
        release_summary="runtime/windows_release_summary.md",
        gate_summary="FAIL | checks 1/2",
        gate_detail="pilot_gate",
        gate_recommendations=["Fix pilot gate"],
        gate_recommendation_details=[
            {
                "text": "Fix pilot gate",
                "fix_target": "tools/pilot_exit_check.py",
                "docs_hint": "docs/PACKAGING.md",
                "entry_point": "python tools/pilot_exit_check.py",
            }
        ],
    )

    feedback = build_windows_ops_feedback_kwargs(
        payload,
        review_order=["runtime/beta_release_dry_run_report.json", "runtime/windows_release_receipt.json"],
    )
    assert feedback["summary"].endswith("Ref: recipe-1")
    assert "Steps: 1/1" in feedback["changes"]
    assert feedback["gate_summary"] == "FAIL | checks 1/2"
    assert feedback["review_order"][0] == "runtime/beta_release_dry_run_report.json"


def test_normalize_windows_gate_details_handles_sparse_input() -> None:
    normalized = normalize_windows_gate_details({"summary": "PASS", "recommendations": ["review receipt"]})
    assert normalized["summary"] == "PASS"
    assert normalized["recommendations"] == ["review receipt"]
    assert normalized["failed_checks"] == []
    assert normalized["recommendation_details"] == []
