from __future__ import annotations

import json
from pathlib import Path

from src.guppy.launcher_application.launcher_shell_support import (
    build_notification_badge_state,
    build_quick_action_plan,
    build_runtime_badge_state,
)


def test_build_quick_action_plan_for_terminal_preserves_focus_copy() -> None:
    plan = build_quick_action_plan(
        action="terminal",
        workspaces_view_index=1,
        settings_ops_index=4,
        runtime_parent=Path("C:/Users/Ryan/Guppy"),
        last_command="python tools/dev_workflow.py release-check",
    )

    assert plan.tab_index == 4
    assert plan.operator_logs_focus is not None
    assert plan.operator_logs_focus.level == "ALL"
    assert "Last command: python tools/dev_workflow.py release-check" in plan.operator_logs_focus.note
    assert plan.terminal_focus is not None
    assert "cwd=" in plan.terminal_focus.note
    assert "Users" in plan.terminal_focus.note
    assert "Guppy" in plan.terminal_focus.note
    assert plan.launcher_event == {
        "action": "terminal",
        "last_command": "python tools/dev_workflow.py release-check",
    }


def test_build_quick_action_plan_marks_unknown_actions_unavailable() -> None:
    plan = build_quick_action_plan(
        action="mystery",
        workspaces_view_index=1,
        settings_ops_index=4,
        runtime_parent=Path("C:/Users/Ryan/Guppy"),
    )

    assert plan.unsupported_message == "quick action unavailable: mystery"


def test_build_notification_badge_state_counts_warn_and_error_events(tmp_path) -> None:
    events_path = tmp_path / "launcher_events.jsonl"
    payload = [
        {"event": "runtime_warning", "summary": "warming"},
        {"event": "command_response", "error": "failed"},
        {"event": "heartbeat", "status": "ok"},
    ]
    events_path.write_text("\n".join(json.dumps(item) for item in payload), encoding="utf-8")

    state = build_notification_badge_state(events_path=events_path, previous_mtime=0.0)

    assert state.changed is True
    assert state.count == 2
    assert state.severity == "error"


def test_build_notification_badge_state_skips_unchanged_files(tmp_path) -> None:
    events_path = tmp_path / "launcher_events.jsonl"
    events_path.write_text(json.dumps({"event": "heartbeat", "status": "ok"}) + "\n", encoding="utf-8")
    current_mtime = events_path.stat().st_mtime

    state = build_notification_badge_state(events_path=events_path, previous_mtime=current_mtime)

    assert state.changed is False


def test_build_runtime_badge_state_marks_starting_before_first_poll() -> None:
    state = build_runtime_badge_state(
        api_status={},
        runtime_overall="UNKNOWN",
        startup_summary="startup unknown",
        startup_first_poll_ok=False,
        startup_over_budget=False,
    )

    assert state.label == "STARTING"
    assert state.severity == "info"
    assert "startup unknown" in state.detail


def test_build_runtime_badge_state_marks_degraded_and_warn_states() -> None:
    degraded = build_runtime_badge_state(
        api_status={"status": "degraded"},
        runtime_overall="PARTIAL",
        startup_summary="startup partial | chat partial",
        startup_first_poll_ok=True,
        startup_over_budget=False,
    )
    over_budget = build_runtime_badge_state(
        api_status={"status": "healthy"},
        runtime_overall="READY",
        startup_summary="startup ready | chat ready",
        startup_first_poll_ok=True,
        startup_over_budget=True,
    )

    assert degraded.label == "CHECK"
    assert degraded.severity == "warn"
    assert "startup partial" in degraded.detail
    assert over_budget.label == "STARTUP WARN"
    assert over_budget.severity == "warn"
    assert "longer than the current launcher budget" in over_budget.detail
