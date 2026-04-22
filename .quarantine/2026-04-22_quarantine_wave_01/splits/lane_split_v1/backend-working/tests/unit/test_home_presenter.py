from src.guppy.launcher_application.home_presenter import (
    build_home_workspace_copy,
    build_home_starter_state,
    build_home_welcome_message,
    build_home_workspace_state,
    build_home_workspace_summary,
    home_workspace_starter_templates,
)


def test_build_home_workspace_copy_returns_role_aware_builder_copy() -> None:
    copy = build_home_workspace_copy("builder_instance")

    assert copy.role_label == "Builder collaborator workspace"
    assert copy.primary_starter_label == "PLAN NEXT PASS"
    assert "next pass" in copy.input_placeholder.lower()
    assert "Starters are optional" in copy.onboarding_subtitle


def test_home_workspace_starter_templates_switch_titles_by_role() -> None:
    admin_templates = home_workspace_starter_templates("admin_instance")

    assert admin_templates[0].starter_id == "morning_brief"
    assert admin_templates[0].title == "OPS CHECK"
    assert admin_templates[0].mode == "auto"


def test_build_home_workspace_summary_surfaces_saved_and_recent_context() -> None:
    summary = build_home_workspace_summary(
        "builder-collab",
        workspace_type="builder_instance",
        description="Planning partner for review loops.",
        mode="code",
        persona="guppy",
        voice="default",
        last_message="Finish the launcher framing pass and verify the workspace cues.",
    )

    assert "Active workspace: Builder collaborator workspace." in summary
    assert "Saved context: CODE mode | GUPPY persona | DEFAULT voice." in summary
    assert "Next move:" in summary
    assert "Recent context: Finish the launcher framing pass" in summary


def test_build_home_workspace_state_keeps_calm_start_copy_aligned() -> None:
    state = build_home_workspace_state(
        "reference-desk",
        workspace_type="read_only_instance",
        description="Safe research and source review.",
        mode="local",
        persona="guppy",
        voice="default",
        last_message="Compare the current brief with the source material.",
    )

    assert state.entry_hint == "Start here in reference-desk: start with SOURCE RESEARCH if you want evidence first."
    assert state.input_placeholder == "Ask one evidence or source-check question..."
    assert "Saved context: LOCAL mode | GUPPY persona | DEFAULT voice." in state.workspace_summary
    assert "Recent context: Compare the current brief" in state.workspace_summary
    assert state.welcome_message == build_home_welcome_message(
        "read_only_instance",
        description="Safe research and source review.",
    )


def test_build_home_starter_state_returns_role_specific_feedback() -> None:
    starter = build_home_starter_state("admin_instance", "morning_brief")

    assert starter.label == "OPS CHECK"
    assert starter.mode == "auto"
    assert starter.prompt.startswith("Give me an operations check")
    assert starter.background_event == "Starter loaded: OPS CHECK. Edit the draft if needed, then press send."
    assert starter.starter_summary.startswith("OPS CHECK is ready in the composer")
    assert starter.status == "STARTER READY"
