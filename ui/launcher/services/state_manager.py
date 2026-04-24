"""
StateManager - Centralized state for LauncherWindow
Replaces 50+ mutable widget attributes with structured state
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from enum import Enum


class StartupPhase(Enum):
    """Startup sequence phases."""
    INITIALIZED = "initialized"
    PERSONALIZATION_LOADED = "personalization_loaded"
    FIRST_POLL_COMPLETED = "first_poll_completed"
    READY = "ready"


@dataclass
class RuntimeStatus:
    """Runtime health status."""
    is_healthy: bool = False
    uptime_seconds: float = 0.0
    active_model: Optional[str] = None
    last_update: Optional[datetime] = None


@dataclass
class WorkspaceSnapshot:
    """Cached workspace instance data."""
    id: str
    name: str
    status: str
    instances_count: int = 0
    last_update: Optional[datetime] = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatSession:
    """Current chat session state."""
    session_id: str
    workspace_id: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    pending_context: Optional[dict[str, Any]] = None
    request_in_flight: bool = False
    active_request_seq: int = 0


@dataclass
class LauncherState:
    """Complete launcher application state."""
    
    # ─── Session & Identity ───────────────────────────────────────
    chat_session_id: str = ""
    session_start_time: float = field(default_factory=time.time)
    
    # ─── Workspace / Instance Management ──────────────────────────
    active_instance_name: str = "guppy-primary"
    instances: list[dict[str, Any]] = field(default_factory=list)
    instance_snapshots: dict[str, WorkspaceSnapshot] = field(default_factory=dict)
    instance_histories: dict[str, list[str]] = field(default_factory=dict)
    
    # ─── Chat & Assistant ─────────────────────────────────────────
    chat: ChatSession = field(default_factory=lambda: ChatSession("", ""))
    messages: list[dict[str, Any]] = field(default_factory=list)
    
    # ─── Models & Runtime ─────────────────────────────────────────
    models: list[dict[str, Any]] = field(default_factory=list)
    active_model: Optional[str] = None
    runtime_status: RuntimeStatus = field(default_factory=RuntimeStatus)
    
    # ─── Library & Context ────────────────────────────────────────
    library_items: list[dict[str, Any]] = field(default_factory=list)
    active_library_context: list[str] = field(default_factory=list)
    library_context_cache: dict[str, Any] = field(default_factory=dict)
    
    # ─── Connectors & Integrations ────────────────────────────────
    connector_inventory: list[dict[str, Any]] = field(default_factory=list)
    
    # ─── Settings & Configuration ─────────────────────────────────
    user_settings: dict[str, Any] = field(default_factory=dict)
    personalization_scaffold: dict[str, Any] = field(default_factory=dict)
    
    # ─── Startup & Initialization ─────────────────────────────────
    startup_phase: StartupPhase = StartupPhase.INITIALIZED
    startup_started_at: float = field(default_factory=time.time)
    startup_phase_timings: dict[str, float] = field(default_factory=dict)
    startup_over_budget_phases: list[str] = field(default_factory=list)
    startup_budget_ms: int = 3000
    startup_complete: bool = False
    first_poll_completed: bool = False
    
    # ─── Authentication ────────────────────────────────────────────
    api_bearer_token: str = ""
    api_token_source: str = "none"
    auth_self_check_ok: bool = False
    
    # ─── Polling & Health ─────────────────────────────────────────
    last_poll_time: Optional[datetime] = None
    last_poll_warn_time: float = 0.0
    health_check_interval_ms: int = 3000
    
    # ─── Queues & Events ───────────────────────────────────────────
    # These use their own storage (SimpleQueue) but tracked here
    pending_assistant_events: int = 0
    pending_recovery_events: int = 0
    pending_connector_events: int = 0
    pending_syslog_entries: int = 0
    
    # ─── Caching & TTLs ────────────────────────────────────────────
    snapshot_cache_ttl_seconds: float = 5.0
    last_snapshot_fetch: Optional[datetime] = None
    snapshot_signatures: dict[str, str] = field(default_factory=dict)
    
    # ─── UI State ──────────────────────────────────────────────────
    sidebar_collapsed: bool = False
    status_panel_visible: bool = True
    active_tab_index: int = 0
    home_drawer_open: bool = False
    
    # ─── Backend Integration ───────────────────────────────────────
    active_request_seq: int = 0
    canceled_request_seqs: set[int] = field(default_factory=set)
    request_in_flight: bool = False
    
    # ─── Features & Tools ─────────────────────────────────────────
    mic_capture_active: bool = False
    notification_badge_count: int = 0
    
    # ─── Metadata ──────────────────────────────────────────────────
    last_updated: datetime = field(default_factory=datetime.utcnow)


class StateManager:
    """Centralized state management for the launcher."""
    
    def __init__(self):
        """Initialize state manager with default state."""
        self._state = LauncherState()
        self._watchers: dict[str, list[callable]] = {}
    
    # ─── State Access ─────────────────────────────────────────────────
    
    @property
    def state(self) -> LauncherState:
        """Get complete current state."""
        return self._state
    
    def get_state_snapshot(self) -> dict[str, Any]:
        """Get state as dictionary."""
        return self._state.__dict__.copy()
    
    # ─── Session Management ───────────────────────────────────────────
    
    def set_chat_session(self, session_id: str, workspace_id: str) -> None:
        """Create new chat session."""
        self._state.chat_session_id = session_id
        self._state.chat = ChatSession(session_id, workspace_id)
        self._notify_watchers("chat_session_changed")
    
    def add_message(self, role: str, content: str) -> None:
        """Add message to current conversation."""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._state.messages.append(message)
        self._state.chat.messages.append(message)
        self._notify_watchers("messages_updated")
    
    def clear_messages(self) -> None:
        """Clear conversation history."""
        self._state.messages.clear()
        self._state.chat.messages.clear()
        self._notify_watchers("messages_cleared")
    
    # ─── Workspace Management ──────────────────────────────────────────
    
    def set_instances(self, instances: list[dict[str, Any]]) -> None:
        """Update list of available instances."""
        self._state.instances = instances
        self._notify_watchers("instances_updated")
    
    def set_active_instance(self, instance_name: str) -> None:
        """Set active workspace instance."""
        self._state.active_instance_name = instance_name
        self._notify_watchers("active_instance_changed")
    
    def add_instance_history(self, instance_name: str, entry: str) -> None:
        """Add to instance activity history."""
        if instance_name not in self._state.instance_histories:
            self._state.instance_histories[instance_name] = []
        self._state.instance_histories[instance_name].append(entry)
    
    # ─── Models & Runtime ─────────────────────────────────────────────
    
    def set_models(self, models: list[dict[str, Any]]) -> None:
        """Update available models."""
        self._state.models = models
        self._notify_watchers("models_updated")
    
    def set_active_model(self, model_id: str) -> None:
        """Set active model."""
        self._state.active_model = model_id
        self._notify_watchers("active_model_changed")
    
    def update_runtime_status(self, status: RuntimeStatus) -> None:
        """Update runtime health status."""
        self._state.runtime_status = status
        self._notify_watchers("runtime_status_updated")
    
    # ─── Library & Context ────────────────────────────────────────────
    
    def set_library_items(self, items: list[dict[str, Any]]) -> None:
        """Update library items list."""
        self._state.library_items = items
        self._notify_watchers("library_updated")
    
    def add_to_active_context(self, item_id: str) -> None:
        """Add item to active library context."""
        if item_id not in self._state.active_library_context:
            self._state.active_library_context.append(item_id)
        self._notify_watchers("active_context_changed")
    
    def remove_from_active_context(self, item_id: str) -> None:
        """Remove item from active context."""
        if item_id in self._state.active_library_context:
            self._state.active_library_context.remove(item_id)
        self._notify_watchers("active_context_changed")
    
    def clear_active_context(self) -> None:
        """Clear active library context."""
        self._state.active_library_context.clear()
        self._notify_watchers("active_context_cleared")
    
    # ─── Startup Management ────────────────────────────────────────────
    
    def complete_startup_phase(self, phase: StartupPhase, duration_ms: float) -> None:
        """Mark a startup phase as complete."""
        self._state.startup_phase = phase
        self._state.startup_phase_timings[phase.value] = duration_ms
        
        if duration_ms > self._state.startup_budget_ms:
            self._state.startup_over_budget_phases.append(phase.value)
        
        if phase == StartupPhase.READY:
            self._state.startup_complete = True
        
        if phase == StartupPhase.FIRST_POLL_COMPLETED:
            self._state.first_poll_completed = True
        
        self._notify_watchers("startup_phase_changed")
    
    # ─── Authentication ────────────────────────────────────────────────
    
    def set_api_token(self, token: str, source: str) -> None:
        """Set API bearer token."""
        self._state.api_bearer_token = token
        self._state.api_token_source = source
        self._notify_watchers("auth_token_changed")
    
    def set_auth_check_ok(self, ok: bool) -> None:
        """Set auth self-check result."""
        self._state.auth_self_check_ok = ok
    
    # ─── Polling & Health ──────────────────────────────────────────────
    
    def record_poll(self) -> None:
        """Record that a poll completed."""
        self._state.last_poll_time = datetime.utcnow()
        self._notify_watchers("poll_completed")
    
    def record_poll_warning(self) -> None:
        """Record poll warning timestamp."""
        self._state.last_poll_warn_time = time.time()
    
    # ─── Request Coordination ──────────────────────────────────────────
    
    def start_request(self) -> int:
        """Start new request, return generation token."""
        self._state.active_request_seq += 1
        self._state.request_in_flight = True
        return self._state.active_request_seq
    
    def end_request(self, seq: int, success: bool = True) -> None:
        """End request."""
        if seq == self._state.active_request_seq:
            self._state.request_in_flight = False
    
    def cancel_request(self, seq: int) -> None:
        """Cancel request by sequence number."""
        self._state.canceled_request_seqs.add(seq)
    
    def is_request_canceled(self, seq: int) -> bool:
        """Check if request was canceled."""
        return seq in self._state.canceled_request_seqs
    
    # ─── UI State ──────────────────────────────────────────────────────
    
    def toggle_sidebar(self) -> None:
        """Toggle sidebar collapsed state."""
        self._state.sidebar_collapsed = not self._state.sidebar_collapsed
        self._notify_watchers("sidebar_toggled")
    
    def set_status_panel_visible(self, visible: bool) -> None:
        """Set status panel visibility."""
        self._state.status_panel_visible = visible
        self._notify_watchers("status_panel_visibility_changed")
    
    def set_active_tab(self, tab_index: int) -> None:
        """Set active tab."""
        self._state.active_tab_index = tab_index
        self._notify_watchers("active_tab_changed")
    
    # ─── Observer Pattern ──────────────────────────────────────────────
    
    def watch(self, event_name: str, callback: callable) -> None:
        """Subscribe to state changes."""
        if event_name not in self._watchers:
            self._watchers[event_name] = []
        self._watchers[event_name].append(callback)
    
    def unwatch(self, event_name: str, callback: callable) -> None:
        """Unsubscribe from state changes."""
        if event_name in self._watchers:
            self._watchers[event_name].remove(callback)
    
    def _notify_watchers(self, event_name: str) -> None:
        """Notify all watchers of a state change."""
        if event_name in self._watchers:
            for callback in self._watchers[event_name]:
                try:
                    callback(self._state)
                except Exception as e:
                    import logging
                    logging.exception(f"Error in state watcher for {event_name}: {e}")


# Global instance for convenient access
_state_manager: Optional[StateManager] = None


def get_state_manager() -> StateManager:
    """Get or create global state manager."""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager


def init_state_manager() -> StateManager:
    """Initialize global state manager."""
    global _state_manager
    _state_manager = StateManager()
    return _state_manager
