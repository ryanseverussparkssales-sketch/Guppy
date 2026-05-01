from pathlib import Path

from src.guppy.launcher_application.embedded_terminal import EmbeddedTerminalSession
from src.guppy.launcher_application.terminal_recipes import build_tracked_terminal_recipe


def test_embedded_terminal_session_handles_recipe_markers_without_shell_process() -> None:
    session = EmbeddedTerminalSession(root=Path("C:/Users/Ryan/Guppy"))
    plan = build_tracked_terminal_recipe(
        ["python tools/verify_local_model_runtime.py --prompt ok", "python tools/verify_runtime_challengers.py"],
        label="WINDOWS VERIFY",
        recipe_context={"kind": "windows_ops", "action": "verify_runtime"},
        recipe_id="recipe-verify",
    )
    session.recipes[plan.recipe_id] = plan.context

    assert session.handle_recipe_marker("__GUPPY_RECIPE__|start|recipe-verify|2|WINDOWS VERIFY").ok is True
    assert session.handle_recipe_marker("__GUPPY_RECIPE__|step|recipe-verify|1|0").ok is True
    assert session.handle_recipe_marker("__GUPPY_RECIPE__|step|recipe-verify|2|1").ok is True
    result = session.handle_recipe_marker("__GUPPY_RECIPE__|end|recipe-verify|1")

    assert result.ok is True
    assert result.completed_payloads
    assert result.completed_payloads[0]["action"] == "verify_runtime"
    assert result.completed_payloads[0]["failed_steps"][0]["index"] == 2


def test_embedded_terminal_session_stop_is_idle_when_process_is_missing() -> None:
    session = EmbeddedTerminalSession(root=Path("C:/Users/Ryan/Guppy"))

    result = session.stop()

    assert result.ok is True
    assert result.status_text == "Shell idle"
