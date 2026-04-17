from __future__ import annotations

from pathlib import Path

from src.guppy.launcher_application.terminal_recipes import (
    TERMINAL_RECIPE_MARKER,
    apply_terminal_recipe_marker,
    build_tracked_terminal_recipe,
    recipe_marker,
)
from src.guppy.launcher_application.workflow_panel import (
    build_workflow_loaded_state,
    build_workflow_panel_state,
    build_workflow_queued_state,
    resolve_workflow_loop_spec,
    workflow_command_strings,
)
from src.guppy.launcher_application.windows_ops_presenter import (
    apply_windows_ops_feedback,
    artifact_display_path,
    build_windows_gate_followup_line,
    build_windows_handoff_line,
    build_windows_ops_panel_state,
    release_gate_is_green,
)


def test_workflow_panel_state_uses_selected_workflow_and_terminal_status() -> None:
    state = build_workflow_panel_state("morning_boot", terminal_status="Shell ready [pid=42]")

    assert state.workflow_id == "morning_boot"
    assert state.title == "MORNING BOOT"
    assert state.status_text == "Workflow shortcuts ready"
    assert state.status_ok is True
    assert state.first_command == "python tools/pilot_exit_check.py --allow-limited-go"
    assert "1. python tools/pilot_exit_check.py --allow-limited-go" in state.steps_text
    assert "shell status: shell ready [pid=42]" in state.evidence_text


def test_workflow_panel_state_falls_back_to_first_workflow_loop() -> None:
    recipe = resolve_workflow_loop_spec("missing-workflow")

    assert recipe is not None
    assert recipe.workflow_id == "morning_boot"
    assert workflow_command_strings("missing-workflow")[0] == "python tools/pilot_exit_check.py --allow-limited-go"


def test_workflow_loaded_and_queued_states_preserve_catalog_copy() -> None:
    loaded = build_workflow_loaded_state("acceptance_snapshot")
    queued = build_workflow_queued_state("acceptance_snapshot")

    assert loaded.status_text == "Loaded ACCEPTANCE SNAPSHOT into the terminal input"
    assert "first command is in the terminal input" in loaded.evidence_text
    assert queued.status_text == "Queued ACCEPTANCE SNAPSHOT in the embedded terminal"
    assert "watch the embedded terminal and operator logs while 8 command(s) run." in queued.next_step_text
    assert "queued 8 command(s)" in queued.outcome_text


def test_windows_ops_panel_state_renders_summary_copy_from_snapshot() -> None:
    state = build_windows_ops_panel_state(
        {
            "install": "Installed on this PC: Ollama CLI: found | Supervisor script: ready | Packager: ready",
            "runtime": "Local AI runtime: ollama | Live backend: llama | Status: ready",
            "next": "Recommended next step: verify runtime and then package",
            "service": "Recent service action: VERIFY | OK | refreshed checks",
            "changes": "Recent changes: runtime verified",
            "gate": "Release check: PASS",
            "gate_fix": "Review next: none",
            "handoff": "Files to share: receipt=runtime/windows_release_receipt.json",
        }
    )

    assert state.install_text == "Ready on this PC: Ollama, supervised launch, desktop packaging"
    assert state.runtime_text == "Local AI health: Llama is connected and ready."
    assert state.next_text == "Next step: verify runtime and then package"
    assert state.service_text == "Recent service action: VERIFY | OK | refreshed checks"


def test_windows_ops_panel_state_defaults_when_snapshot_is_sparse() -> None:
    state = build_windows_ops_panel_state(None)

    assert state.install_text == "Ready on this PC: Core launcher tools found."
    assert state.runtime_text == "Local AI health: Local Ai is selected, but it has not been confirmed yet."
    assert state.handoff_text == "Files to share: unavailable"


def test_windows_ops_feedback_and_followup_lines_use_structured_inputs() -> None:
    updated = apply_windows_ops_feedback(
        {"next": "Recommended next step: old"},
        action="WINDOWS RELEASE DRY RUN",
        summary="Dry run finished",
        changes="receipt and summary refreshed",
        ok=False,
        next_step="Fix gate findings before package",
        fix_target="docs/PACKAGING.md",
        docs_hint="docs/PACKAGING.md",
        entry_point=".venv\\Scripts\\python.exe tools/beta_release_dry_run.py",
        artifacts=[{"label": "report", "path": "C:\\Users\\Ryan\\Guppy\\runtime\\beta_release_dry_run_report.json"}],
        receipt_path="C:\\Users\\Ryan\\Guppy\\runtime\\windows_release_receipt.json",
        summary_path="C:\\Users\\Ryan\\Guppy\\runtime\\windows_release_summary.md",
        gate_summary="FAIL",
        gate_detail="missing reviewer bundle",
        gate_recommendation_details=[
            {
                "text": "Run release dry run again after fixing docs.",
                "fix_target": "docs/PACKAGING.md",
                "docs_hint": "docs/PACKAGING.md",
                "entry_point": ".venv\\Scripts\\python.exe tools/beta_release_dry_run.py",
            }
        ],
        review_order=["runtime/beta_release_dry_run_report.json", "runtime/windows_release_receipt.json"],
    )

    assert updated["service"] == "Recent service action: WINDOWS RELEASE DRY RUN | CHECK | Dry run finished"
    assert updated["changes"] == "Recent changes: receipt and summary refreshed"
    assert updated["next"].startswith("Next step: Fix gate findings before package")
    assert updated["gate"] == "Release check: FAIL | missing reviewer bundle"
    assert updated["gate_fix"].startswith("Fix first: Run release dry run again after fixing docs.")
    assert "receipt=runtime/windows_release_receipt.json" in updated["handoff"]


def test_windows_ops_feedback_uses_review_copy_when_release_gate_is_green() -> None:
    updated = apply_windows_ops_feedback(
        {"next": "Recommended next step: old"},
        action="WINDOWS RELEASE DRY RUN",
        summary="Dry run finished",
        changes="receipt and summary refreshed",
        ok=True,
        artifacts=[
            {"label": "report", "path": "C:\\Users\\Ryan\\Guppy\\runtime\\beta_release_dry_run_report.json"},
        ],
        receipt_path="C:\\Users\\Ryan\\Guppy\\runtime\\windows_release_receipt.json",
        summary_path="C:\\Users\\Ryan\\Guppy\\runtime\\windows_release_summary.md",
        gate_summary="PASS with notes",
        gate_recommendation_details=[
            {
                "text": "Review the generated handoff bundle.",
                "fix_target": "runtime/windows_release_receipt.json",
                "docs_hint": "docs/PACKAGING.md",
                "entry_point": "python tools/beta_release_dry_run.py",
            }
        ],
        review_order=[
            "runtime/beta_release_dry_run_report.json",
            "runtime/windows_release_receipt.json",
            "runtime/windows_release_summary.md",
        ],
    )

    assert updated["service"] == "Recent service action: WINDOWS RELEASE DRY RUN | OK | Dry run finished"
    assert updated["gate"] == "Release check: PASS with notes"
    assert updated["gate_fix"].startswith("Review next: Review the generated handoff bundle.")
    assert " | Review: runtime/windows_release_receipt.json" in updated["gate_fix"]
    assert "review order=runtime/beta_release_dry_run_report.json -> runtime/windows_release_receipt.json -> runtime/windows_release_summary.md" in updated["handoff"]
    assert "receipt=runtime/windows_release_receipt.json" in updated["handoff"]
    assert "summary=runtime/windows_release_summary.md" in updated["handoff"]


def test_build_windows_gate_followup_line_falls_back_to_recommendation_text() -> None:
    assert build_windows_gate_followup_line(
        "FAIL",
        ["Re-run release dry run", "Attach reviewer bundle"],
        None,
    ) == "Fix first: Re-run release dry run | Attach reviewer bundle"


def test_windows_ops_path_helpers_normalize_repo_relative_and_raw_paths() -> None:
    root = Path("C:/Users/Ryan/Guppy")

    assert artifact_display_path("C:/Users/Ryan/Guppy/runtime/windows_release_summary.md", root=root) == (
        "runtime/windows_release_summary.md"
    )
    assert artifact_display_path("D:/shared/file.txt", root=root) == "D:/shared/file.txt"
    assert release_gate_is_green("PASS with notes") is True
    assert release_gate_is_green("FAIL") is False
    assert build_windows_gate_followup_line("", [], []) == (
        "Release follow-up: no release-check recommendations recorded yet."
    )
    assert build_windows_handoff_line([], root=root).startswith("Files to share: run RELEASE DRY RUN first")


def test_build_tracked_terminal_recipe_wraps_commands_and_initial_context() -> None:
    plan = build_tracked_terminal_recipe(
        ["Write-Output ok", "", "Get-Item 'test'"],
        label="MORNING BOOT",
        recipe_context={"workflow_id": "morning_boot"},
        recipe_id="recipe-fixed",
    )

    assert plan.recipe_id == "recipe-fixed"
    assert plan.context["label"] == "MORNING BOOT"
    assert plan.context["workflow_id"] == "morning_boot"
    assert plan.context["steps_total"] == 2
    assert plan.rendered_commands[0] == 'Write-Output "__GUPPY_RECIPE__|start|recipe-fixed|2|MORNING BOOT"'
    assert any("Invoke-Expression 'Get-Item ''test'''" in line for line in plan.rendered_commands)


def test_apply_terminal_recipe_marker_tracks_start_step_and_completion() -> None:
    plan = build_tracked_terminal_recipe(
        ["first-command", "second-command"],
        label="MIDDAY STABILITY",
        recipe_context={"workflow_id": "midday_stability"},
        recipe_id="recipe-123",
    )
    recipes = {plan.recipe_id: plan.context}

    started = apply_terminal_recipe_marker(recipe_marker("start", plan.recipe_id, 2, plan.label), recipes)
    stepped = apply_terminal_recipe_marker(
        recipe_marker("step", plan.recipe_id, 1) + "|0",
        started.recipes,
    )
    finished = apply_terminal_recipe_marker(
        recipe_marker("end", plan.recipe_id) + "|0",
        stepped.recipes,
        shell_pid=77,
        shell_alive=True,
    )

    assert started.consumed is True
    assert started.status_text == "Shell running midday stability"
    assert stepped.recipes[plan.recipe_id]["steps_completed"] == 1
    assert finished.status_text == "Shell ready [pid=77]"
    assert finished.completed_payload is not None
    assert finished.completed_payload["ok"] is False
    assert finished.completed_payload["summary"] == "MIDDAY STABILITY stopped after 1/2 successful step(s)."
    assert plan.recipe_id not in finished.recipes


def test_apply_terminal_recipe_marker_reports_failed_step_details() -> None:
    recipes = {
        "recipe-xyz": {
            "id": "recipe-xyz",
            "label": "ACCEPTANCE SNAPSHOT",
            "commands": ["first", "second"],
            "steps_total": 2,
            "step_results": [{"index": 1, "exit_code": 0, "ok": True, "skipped": False, "command": "first"}],
        }
    }

    stepped = apply_terminal_recipe_marker(
        recipe_marker("step", "recipe-xyz", 2) + "|5",
        recipes,
    )
    finished = apply_terminal_recipe_marker(
        recipe_marker("end", "recipe-xyz") + "|5",
        stepped.recipes,
        shell_alive=False,
    )

    assert finished.completed_payload is not None
    assert finished.completed_payload["ok"] is False
    assert finished.completed_payload["failed_steps"][0]["command"] == "second"
    assert "Failed step 2: second" in finished.completed_payload["summary"]
    assert finished.status_text == "Shell idle"


def test_apply_terminal_recipe_marker_ignores_non_marker_lines() -> None:
    result = apply_terminal_recipe_marker("plain terminal output", {"recipe": {"label": "noop"}})

    assert result.consumed is False
    assert result.recipes == {"recipe": {"label": "noop"}}
    assert result.status_text is None
    assert result.completed_payload is None
    assert TERMINAL_RECIPE_MARKER == "__GUPPY_RECIPE__|"
