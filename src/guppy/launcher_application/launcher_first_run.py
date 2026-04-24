"""
src/guppy/launcher_application/launcher_first_run.py

First-run wizard state rendering and action routing for LauncherWindow.
Extracted as part of Tranche 54 / TR54-B1 module decomposition (Wave 9).

This module handles the first-run banner state that maps wizard checkpoint
status to assistant-view guidance text, and the hub-routing action handler
that opens the correct hub when the user acts on first-run prompts.
"""
from __future__ import annotations

from typing import Any

from src.guppy.launcher_application.first_run_wizard import FirstRunWizard


def refresh_first_run_banner(owner: Any, *, wizard_factory: Any = FirstRunWizard) -> None:
    """Compute and push the current first-run wizard state into the assistant view.

    Extracted from LauncherWindow._refresh_first_run_banner as part of TR54-B1 Wave 9.
    """
    assistant = getattr(owner, "_assistant_view", None)
    if assistant is None or not hasattr(assistant, "set_first_run_status"):
        return

    active_instance_name = getattr(owner, "_active_instance_name", "")
    wizard = wizard_factory(workspace_id=active_instance_name)
    if wizard.should_skip():
        assistant.set_first_run_status(visible=False)
        return

    checkpoint1 = wizard.state.get_status(1).value
    checkpoint2 = wizard.state.get_status(2).value
    checkpoint3 = wizard.state.get_status(3).value

    if checkpoint1 != "passed":
        summary = "Finish desktop install checks first."
        detail = "Open Settings to review install readiness, accounts, logs, and setup guidance before deeper model work."
    elif checkpoint2 != "passed":
        summary = "Choose and verify a local model runtime next."
        detail = "Open Models to confirm Ollama, LM Studio, or the local harness path, then come back here for a short test ask."
    else:
        summary = "Send one short test ask from Home to prove first success."
        detail = "The final checkpoint only closes after a real request verifier path succeeds, so keep this step honest."

    assistant.set_first_run_status(
        visible=True,
        summary=summary,
        detail=detail,
        install_status=checkpoint1,
        model_status=checkpoint2,
        request_status=checkpoint3,
    )


def on_first_run_action_requested(
    owner: Any,
    action: str,
    *,
    settings_view_index: int,
    models_view_index: int,
) -> None:
    """Route a first-run wizard action to the correct hub tab.

    Extracted from LauncherWindow._on_first_run_action_requested as part of TR54-B1 Wave 9.
    """
    target = (action or "").strip().lower()
    tab_change = getattr(owner, "_on_tab_change", None)
    set_activity = getattr(owner, "_set_daily_activity", None)
    if target == "settings":
        if callable(tab_change):
            tab_change(settings_view_index)
        if callable(set_activity):
            set_activity("First-run guidance opened Settings")
        return
    if target == "models":
        if callable(tab_change):
            tab_change(models_view_index)
        if callable(set_activity):
            set_activity("First-run guidance opened Models")
