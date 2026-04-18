"""Shell-level status and daily-context helpers for the launcher window."""

from __future__ import annotations

import os

from src.guppy.inference.router import resolve_ui_route
from src.guppy.runtime_application import route_evidence_summary

from .instance_manager_presenter import workspace_default_purpose, workspace_role_label


def update_route_preview(owner, text: str = "") -> None:
    sample = (text or owner._last_command or "").strip()
    if not sample:
        owner._assistant_view.set_route_preview(reason="waiting for command")
        owner._advanced_view.set_daily_context_route(owner._assistant_view._route_facts.text())
        return
    mode, _persona = owner._assistant_view.chat_context()
    try:
        decision = resolve_ui_route(
            user_text=sample,
            mode=mode,
            api_key_available=bool((os.environ.get("ANTHROPIC_API_KEY", "") or "").strip()),
        )
        owner._assistant_view.set_route_preview(
            task_type=str(decision.get("task_type", "unknown")),
            route=str(decision.get("route", "pending")),
            model=str(decision.get("model", "")),
            backup_model=str(decision.get("backup_model", "")),
            reason=str(decision.get("route_reason", "")),
            evidence=route_evidence_summary(decision, runtime_path=owner._runtime_dir),
        )
        owner._advanced_view.set_daily_context_route(owner._assistant_view._route_facts.text())
    except Exception as exc:
        owner._assistant_view.set_route_preview(reason=f"preview failed: {exc}")
        owner._advanced_view.set_daily_context_route(owner._assistant_view._route_facts.text())


def set_daily_activity(owner, text: str) -> None:
    owner._assistant_view.set_background_event(text)
    owner._advanced_view.set_daily_context_activity(text)


def sync_right_tray(owner, active_payload: dict[str, object]) -> None:
    workspace_name = str(active_payload.get("name", owner._active_instance_name) or owner._active_instance_name)
    workspace_type = str(active_payload.get("type", "user_instance") or "user_instance")
    owner._status_panel.set_workspace(workspace_name, workspace_type)
    owner._status_panel.set_tool_states(owner._tools_view.current_tool_states())
    description = str(
        active_payload.get("description", "") or workspace_default_purpose(workspace_type)
    ).strip()
    mode = str(active_payload.get("mode", "auto") or "auto").strip().upper()
    persona = str(active_payload.get("persona", "guppy") or "guppy").strip().upper()
    voice = str(active_payload.get("voice", "default") or "default").strip().upper()
    owner._advanced_view.set_daily_context_workspace(
        f"Workspace: {workspace_role_label(workspace_type)}. {description} | Saved context: {mode} mode / {persona} persona / {voice} voice"
    )
    owner._advanced_view.set_daily_context_runtime(owner._assistant_view._runtime_facts.text())
