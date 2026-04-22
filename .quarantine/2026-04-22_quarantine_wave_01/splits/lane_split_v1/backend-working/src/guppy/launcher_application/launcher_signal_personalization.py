from __future__ import annotations

from typing import Any

from src.guppy.experience_config import (
    PersonalizationState,
    build_persona_options,
    ensure_personalization_scaffold,
    list_persona_choices,
    load_persona_config,
    load_voice_bindings,
    resolve_voice_binding,
    voice_binding_summary,
    voice_option_choices,
)


def bootstrap_personalization_scaffold_worker(owner: Any) -> None:
    try:
        owner._scaffold_created = ensure_personalization_scaffold()
        if owner._scaffold_created:
            created = ",".join(sorted(owner._scaffold_created.keys()))
            owner._deferred_syslog.put(f"personalization scaffold ready: {created}")
            owner._log_launcher_event("personalization_scaffold_created", created=list(owner._scaffold_created.keys()))
        owner._log_launcher_event("startup_phase", phase="personalization_scaffold_thread_complete")
    except Exception as exc:
        owner._deferred_syslog.put(f"personalization scaffold failed: {exc}")
        owner._log_launcher_event("personalization_scaffold_error", error=str(exc))
        owner._log_launcher_event("startup_phase", phase="personalization_scaffold_thread_error", error=str(exc))


def wire_signals(owner: Any, *, settings_view_index: int) -> None:
    """Composition helper: all inter-widget signal connections in one seam."""
    owner._sidebar.tab_changed.connect(owner._on_tab_change)
    owner._topbar.nav_requested.connect(owner._on_tab_change)
    owner._settings_hub_view.open_diagnostics_requested.connect(lambda: owner._on_tab_change(settings_view_index))
    owner._settings_hub_view.open_recovery_requested.connect(lambda: owner._on_tab_change(settings_view_index))
    owner._settings_hub_view.open_terminal_requested.connect(lambda: owner._on_tab_change(settings_view_index))
    owner._settings_hub_view.open_connectors_requested.connect(lambda: owner._on_tab_change(settings_view_index))
    owner._settings_hub_view.open_system_requested.connect(lambda: owner._on_tab_change(settings_view_index))
    owner._settings_view.settings_saved.connect(owner._on_settings_saved)
    owner._tools_view.tool_state_changed.connect(owner._on_tool_state_changed)
    owner._tools_view.tool_hint_requested.connect(owner._on_tool_hint_requested)
    owner._tools_view.tool_management_requested.connect(owner._on_tool_management_requested)
    owner._tools_view.builder_task_requested.connect(owner._on_builder_task_requested)
    owner._status_panel.tool_requested.connect(owner._on_tool_hint_requested)
    owner._settings_hub_view.recovery_requested.connect(owner._on_recovery_requested)
    owner._settings_hub_view.windows_ops_requested.connect(owner._on_windows_ops_requested)
    owner._settings_hub_view.connector_action_requested.connect(owner._on_connector_action_requested)
    owner._settings_hub_view.connector_guided_link_requested.connect(owner._on_connector_guided_link_requested)
    owner._settings_hub_view.automation_action_requested.connect(owner._on_automation_action_requested)
    owner._settings_hub_view.terminal_recipe_finished.connect(owner._on_terminal_recipe_finished)
    owner._models_hub_view.model_selected.connect(owner._on_model_selected)
    owner._models_hub_view.runtime_settings_saved.connect(owner._on_runtime_settings_saved)
    owner._models_hub_view.bindings_changed.connect(owner._on_voice_bindings_changed)
    owner._topbar.search_submitted.connect(owner._on_search)
    owner._topbar.quick_action.connect(owner._on_quick_action)
    owner._topbar.launcher_context_requested.connect(lambda: owner._on_quick_action("toggle_drawer"))
    owner._assistant_view.command_submitted.connect(owner._on_assistant_command)
    owner._assistant_view.starter_requested.connect(owner._on_home_starter_requested)
    owner._assistant_view.cancel_requested.connect(owner._on_cancel_assistant_request)
    owner._assistant_view.mic_requested.connect(owner._on_mic_requested)
    owner._assistant_view.assistant_reply_library_requested.connect(owner._on_assistant_reply_library_requested)
    owner._assistant_view.assistant_reply_artifact_requested.connect(owner._on_assistant_reply_artifact_requested)
    owner._assistant_view.latest_saved_output_attach_requested.connect(owner._on_latest_saved_output_attached)
    owner._assistant_view.latest_saved_output_library_requested.connect(owner._on_library_context_opened)
    owner._assistant_view.active_context_refresh_requested.connect(owner._on_active_context_refresh_requested)
    owner._assistant_view.active_context_clear_requested.connect(owner._on_library_context_cleared)
    owner._assistant_view.active_context_focus_requested.connect(owner._on_library_context_focused)
    owner._assistant_view.active_context_default_requested.connect(owner._on_library_context_default_requested)
    owner._assistant_view.active_context_library_requested.connect(owner._on_library_context_opened)
    owner._assistant_view.active_context_remove_requested.connect(owner._on_library_context_removed)
    owner._assistant_view.first_run_action_requested.connect(owner._on_first_run_action_requested)
    owner.assistant_event_queued.connect(owner._drain_assistant_events)
    owner.connector_action_event_queued.connect(owner._drain_connector_action_events)
    owner._assistant_view.chat_context_changed.connect(owner._on_chat_context_changed)
    owner._assistant_view.launcher_summary_changed.connect(owner._topbar.set_launcher_summary)
    owner._library_view.context_requested.connect(owner._on_library_context_requested)
    owner._library_view.approved_root_requested.connect(owner._on_library_root_requested)
    owner._library_view.note_requested.connect(owner._on_library_note_requested)
    owner._library_view.note_updated.connect(owner._on_library_note_updated)
    owner._library_view.artifact_requested.connect(owner._on_library_artifact_requested)
    owner._library_view.artifact_updated.connect(owner._on_library_artifact_updated)
    owner._library_view.library_item_delete_requested.connect(owner._on_library_item_deleted)
    owner._instance_manager_view.refresh_requested.connect(owner._on_instance_manager_refresh)
    owner._instance_manager_view.activate_requested.connect(owner._on_instance_selected)
    owner._instance_manager_view.create_requested.connect(owner._on_instance_create_requested)
    owner._instance_manager_view.governance_save_requested.connect(owner._on_instance_governance_save_requested)
    owner._instance_manager_view.connector_binding_save_requested.connect(owner._on_instance_connector_binding_save_requested)
    owner._instance_manager_view.delete_requested.connect(owner._on_instance_delete_requested)
    owner._instance_manager_view.logs_requested.connect(owner._on_instance_logs_requested)
    owner._topbar.instance_selected.connect(owner._on_instance_selected)
    owner._status_panel.agent_init_requested.connect(owner._on_agent_init_requested)


def refresh_personalization_state(
    owner: Any,
    *,
    preferred_persona: str = "",
    personalization_available: bool,
) -> None:
    try:
        persona_config = load_persona_config() if personalization_available else {}
        voice_bindings = load_voice_bindings() if personalization_available else {}
        persona_choices = list_persona_choices(persona_config)
        target_persona = preferred_persona or owner._assistant_view.chat_context()[1]
        active_model_id = owner._assistant_model_id(owner._assistant_view.selected_mode())
        voice_choice = resolve_voice_binding(
            persona_id=target_persona,
            model_id=active_model_id,
            voice_bindings=voice_bindings,
        )
        empty_state = PersonalizationState.empty()
        personalization_state = PersonalizationState(
            persona_options=build_persona_options(persona_choices) or empty_state.persona_options,
            voice_options=tuple(voice_option_choices(voice_bindings)) or empty_state.voice_options,
            voice_summary=voice_binding_summary(voice_choice),
            model_id=active_model_id,
            voice_choice=voice_choice if isinstance(voice_choice, dict) else {},
        )
        owner._assistant_view.set_persona_options(list(personalization_state.persona_options), selected=target_persona)
        owner._instance_manager_view.set_persona_options(list(personalization_state.persona_options), selected=target_persona)
        owner._instance_manager_view.set_voice_options(list(personalization_state.voice_options), selected="default")
        owner._models_hub_view.refresh_voice_assignments()
        owner._assistant_view.set_runtime_facts(
            profile=owner._assistant_view._cb_profile.currentText().strip().lower() or "standard",
            model=personalization_state.model_id,
            voice=personalization_state.voice_summary,
            latency="-",
            last_query=owner._last_command or "-",
        )
        owner._settings_hub_view.set_daily_context_runtime(owner._assistant_view._runtime_facts.text())
    except Exception as exc:
        owner._status_panel.append_syslog(f"personalization refresh failed: {exc}")