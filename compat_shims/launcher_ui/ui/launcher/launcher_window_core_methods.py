from __future__ import annotations

import sys

from PySide6.QtCore import QTimer

from src.guppy.launcher_application import (
    LauncherStateSnapshot,
    build_launcher_state_snapshot,
    connector_backend_available,
)
from src.guppy.launcher_application import launcher_nav_handlers as _nav_handlers
from src.guppy.launcher_application.automation_test_support import event_level
from src.guppy.launcher_application.first_run_wizard import FirstRunWizard
from src.guppy.launcher_application.launcher_command_flow import (
    apply_chat_context as _apply_chat_context_fn,
    assistant_model_id as _assistant_model_id_fn,
    chat_timeout_for_request,
    drain_assistant_events,
    finish_request_ui as _finish_request_ui_fn,
    initialize_embedded_agent as _initialize_embedded_agent_fn,
    on_agent_init_requested as _on_agent_init_requested_fn,
    on_cancel_assistant_request as _on_cancel_assistant_request_fn,
    on_chat_context_changed as _on_chat_context_changed_fn,
    on_model_selected as _on_model_selected_fn,
    on_runtime_settings_saved as _on_runtime_settings_saved_fn,
    required_local_model_for_mode,
    rotate_chat_session as _rotate_chat_session_fn,
    validate_mode_ready as _validate_mode_ready_fn,
)
from src.guppy.launcher_application.launcher_command_policy import humanize_chat_error
from src.guppy.launcher_application.launcher_first_run import (
    on_first_run_action_requested as _on_first_run_action_requested_fn,
    refresh_first_run_banner as _refresh_first_run_banner_fn,
)
from src.guppy.launcher_application.launcher_poll_orchestration import (
    complete_startup_phase as _complete_startup_phase_fn,
    sync_topbar_model_context as _sync_topbar_model_context_fn,
)
from src.guppy.launcher_application.launcher_signal_personalization import (
    bootstrap_personalization_scaffold_worker as _bootstrap_personalization_scaffold_worker_fn,
    refresh_personalization_state as _refresh_personalization_state_fn,
    wire_signals as _wire_signals_fn,
)
from src.guppy.launcher_application.launcher_tools_coordination import (
    load_tool_states as _load_tool_states_fn,
    on_settings_saved as _on_settings_saved_fn,
    on_tool_hint_requested as _on_tool_hint_requested_fn,
    on_tool_management_requested as _on_tool_management_requested_fn,
    on_tool_state_changed as _on_tool_state_changed_fn,
    on_voice_bindings_changed as _on_voice_bindings_changed_fn,
)
from src.guppy.launcher_application.recovery_coordination import (
    classify_recovery_summary,
    drain_recovery_events,
    format_recovery_summary,
    push_recovery_outcome,
)
from src.guppy.runtime_application import RuntimeHealthSnapshot
from src.guppy.launcher_application.tool_action_registry import get_home_starter_prompt as _registry_tool_prompt

_CONNECTOR_MANAGER_BACKEND = connector_backend_available()
_SETTINGS_VIEW_INDEX = _nav_handlers.SETTINGS_VIEW_INDEX
_MODELS_VIEW_INDEX = _nav_handlers.MODELS_VIEW_INDEX


def event_level_static(item: dict[str, object]) -> str:
    return event_level(item)


def bootstrap_personalization_scaffold_worker(self) -> None:
    _bootstrap_personalization_scaffold_worker_fn(self)


def wire_signals(self) -> None:
    _wire_signals_fn(self, settings_view_index=_SETTINGS_VIEW_INDEX)


def refresh_personalization_state(self, preferred_persona: str = "") -> None:
    personalization_available = bool(getattr(self, "_personalization_backend_available", False))
    _refresh_personalization_state_fn(
        self,
        preferred_persona=preferred_persona,
        personalization_available=personalization_available,
    )


def complete_startup_phase(self, phase: str, start_at: float | None = None) -> None:
    _complete_startup_phase_fn(self, phase, start_at=start_at)


def sync_topbar_model_context(
    self,
    *,
    main_model: str = "",
    support_model: str = "",
) -> None:
    _sync_topbar_model_context_fn(self, main_model=main_model, support_model=support_model)


def classify_recovery_summary_static(summary: str, ok: bool, default: str = "") -> str:
    return classify_recovery_summary(summary, ok, default)


def format_recovery_summary_static(category: str, summary: str) -> str:
    return format_recovery_summary(category, summary)


def push_recovery_outcome_method(self, action: str, ok: bool, summary: str, category: str = "") -> str:
    return push_recovery_outcome(self, action, ok, summary, category)


def resolve_stack_index_static(index: int) -> int:
    return _nav_handlers.resolve_stack_index(index)


def visible_nav_index_static(index: int) -> int:
    return _nav_handlers.visible_nav_index(index)


def refresh_first_run_banner(self) -> None:
    launcher_module = (
        sys.modules.get("ui.launcher.launcher_window")
        or sys.modules.get("compat_shims.launcher_ui.ui.launcher.launcher_window")
    )
    wizard_factory = getattr(launcher_module, "FirstRunWizard", FirstRunWizard)
    _refresh_first_run_banner_fn(self, wizard_factory=wizard_factory)


def on_first_run_action_requested(self, action: str) -> None:
    _on_first_run_action_requested_fn(
        self,
        action,
        settings_view_index=_SETTINGS_VIEW_INDEX,
        models_view_index=_MODELS_VIEW_INDEX,
    )


def build_launcher_state_snapshot_method(
    self,
    snapshot: dict,
    typed_connector_inventory,
    windows_snapshot: dict[str, str],
    runtime_health: RuntimeHealthSnapshot | None = None,
) -> LauncherStateSnapshot:
    return build_launcher_state_snapshot(
        snapshot,
        typed_connector_inventory if _CONNECTOR_MANAGER_BACKEND else (),
        windows_snapshot if isinstance(windows_snapshot, dict) else {},
        active_view="home",
        runtime_health=runtime_health,
    )


def on_settings_saved(self, settings: dict) -> None:
    _on_settings_saved_fn(self, settings)


def on_voice_bindings_changed(self, _bindings: dict) -> None:
    _on_voice_bindings_changed_fn(self)


def load_tool_states(self) -> None:
    _load_tool_states_fn(self)


def on_tool_state_changed(self, tool_key: str, enabled: bool) -> None:
    _on_tool_state_changed_fn(self, tool_key, enabled)


def drain_assistant_events_method(self) -> None:
    drain_assistant_events(self, timer_single_shot=QTimer.singleShot)


def humanize_chat_error_method(self, raw: str) -> str:
    return humanize_chat_error(raw)


def chat_timeout_for_request_static(mode: str, command: str = "") -> float:
    return chat_timeout_for_request(mode, command)


def required_local_model_for_mode_static(mode: str) -> str | None:
    return required_local_model_for_mode(mode)


def assistant_model_id_static(mode: str, active_model: str = "") -> str:
    return _assistant_model_id_fn(mode, active_model)


def validate_mode_ready(self, mode: str) -> tuple[bool, str]:
    return _validate_mode_ready_fn(self, mode)


def rotate_chat_session(
    self,
    reason: str,
    mode: str = "",
    persona: str = "",
    instance: str = "",
    clear_live_history: bool = False,
) -> None:
    _rotate_chat_session_fn(
        self,
        reason,
        mode=mode,
        persona=persona,
        instance=instance,
        clear_live_history=clear_live_history,
    )


def on_chat_context_changed(self, mode: str, persona: str) -> None:
    _on_chat_context_changed_fn(self, mode, persona)


def apply_chat_context(self, mode: str, persona: str) -> None:
    _apply_chat_context_fn(self, mode, persona)


def finish_request_ui(self) -> None:
    _finish_request_ui_fn(self)


def on_cancel_assistant_request(self) -> None:
    _on_cancel_assistant_request_fn(self)


def drain_recovery_events_method(self) -> None:
    drain_recovery_events(self)


def on_tool_hint_requested(self, tool_key: str) -> None:
    _on_tool_hint_requested_fn(
        self,
        tool_key,
        settings_view_index=_SETTINGS_VIEW_INDEX,
        tool_prompt_fn=self._tool_prompt_for_home,
    )


def on_tool_management_requested(self, payload: dict) -> None:
    _on_tool_management_requested_fn(self, payload, settings_view_index=_SETTINGS_VIEW_INDEX)


def initialize_embedded_agent(self, agent_id: str) -> tuple[bool, str]:
    return _initialize_embedded_agent_fn(self, agent_id)


def on_agent_init_requested(self, agent_id: str) -> None:
    _on_agent_init_requested_fn(self, agent_id)


def on_model_selected(self, model: str) -> None:
    _on_model_selected_fn(self, model, models_view_index=_MODELS_VIEW_INDEX)


def on_runtime_settings_saved(self, settings: dict) -> None:
    _on_runtime_settings_saved_fn(self, settings, models_view_index=_MODELS_VIEW_INDEX)


def tool_prompt_for_home_static(tool_key: str) -> str:
    return _registry_tool_prompt(tool_key)
