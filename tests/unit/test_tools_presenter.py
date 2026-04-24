from __future__ import annotations

from src.guppy.launcher_application.tools_presenter import build_tools_surface_state


def test_build_tools_surface_state_splits_available_setup_first_and_restricted_counts() -> None:
    rows = [
        {"key": "read_file", "category": "READ", "dry_run": False},
        {"key": "run_python", "category": "CODE", "dry_run": True},
        {"key": "send_email", "category": "CONNECTOR", "dry_run": False},
        {"key": "write_file", "category": "WRITE", "dry_run": True},
    ]

    state = build_tools_surface_state(
        rows,
        {
            "read_file": "ready",
            "run_python": "ready",
            "send_email": "restricted",
            "write_file": "restricted",
        },
    )

    assert state.available_now == 1
    assert state.setup_first == 1
    assert state.restricted_here == 2
    assert state.planned == 0
    assert state.summary_line == "Available now: 1 | Set up first: 1 | Restricted here: 2"


def test_build_tools_surface_state_excludes_planned_tools_from_bucket_counts() -> None:
    rows = [
        {"key": "read_file", "category": "READ", "dry_run": False},
        {"key": "voip_place_call", "category": "CONNECTOR", "dry_run": True},
    ]

    state = build_tools_surface_state(rows, {"read_file": "ready", "voip_place_call": "ready"})

    assert state.available_now == 1
    assert state.setup_first == 0
    assert state.planned == 1
    assert "Planned: 1" in state.summary_line


def test_build_tools_surface_state_planned_connector_does_not_count_as_connector_ready() -> None:
    rows = [
        {"key": "send_email", "category": "CONNECTOR", "dry_run": False},
        {"key": "voip_place_call", "category": "CONNECTOR", "dry_run": True},
    ]

    state = build_tools_surface_state(rows, {"send_email": "ready", "voip_place_call": "ready"})

    assert state.available_now == 1
    assert state.planned == 1
    assert "Planned: 1" in state.summary_line
    assert "connector tools are usable right now" in state.guidance_line


def test_build_tools_surface_state_calls_out_planned_adapter_lanes() -> None:
    state = build_tools_surface_state([], {})

    assert "planned adapter lanes" in state.planning_line.lower()
    assert "anythingllm" in state.planning_line.lower()
    assert "hugging face local" in state.planning_line.lower()
