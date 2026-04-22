from __future__ import annotations

from src.guppy.launcher_application.contracts import LauncherIntent
from src.guppy.launcher_application.workflows import get_workflow_spec, list_workflow_specs


def test_workflow_catalog_has_unique_ids_and_non_empty_commands() -> None:
    workflows = list_workflow_specs()
    workflow_ids = [item.workflow_id for item in workflows]

    assert len(workflow_ids) == len(set(workflow_ids))
    assert workflows
    assert all(item.docs_hint for item in workflows)
    assert all(item.commands for item in workflows)
    assert all(command.command.strip() for item in workflows for command in item.commands)


def test_workflow_category_filters_are_case_insensitive_and_stable() -> None:
    workflow_loops = list_workflow_specs(category="WORKFLOW_LOOP")
    windows_ops = list_workflow_specs(category="windows_ops")

    assert {item.workflow_id for item in workflow_loops} == {
        "morning_boot",
        "acceptance_snapshot",
        "midday_stability",
        "evening_close",
        "overnight_low_compute",
    }
    assert {item.workflow_id for item in windows_ops} == {
        "windows_verify_runtime",
        "windows_update_runtime",
        "windows_package_desktop",
        "windows_release_dry_run",
    }


def test_windows_launcher_intents_map_to_windows_workflow_specs() -> None:
    workflow_by_intent = {
        LauncherIntent.RUN_WINDOWS_VERIFY: "windows_verify_runtime",
        LauncherIntent.RUN_WINDOWS_UPDATE: "windows_update_runtime",
        LauncherIntent.RUN_WINDOWS_PACKAGE: "windows_package_desktop",
        LauncherIntent.RUN_WINDOWS_RELEASE_DRY_RUN: "windows_release_dry_run",
    }

    for intent, workflow_id in workflow_by_intent.items():
        spec = get_workflow_spec(workflow_id)

        assert spec is not None
        assert spec.category == "windows_ops"
        assert spec.first_command
        assert intent.value.startswith("run_windows_")


def test_unknown_workflow_lookup_returns_none() -> None:
    assert get_workflow_spec("missing-workflow") is None
