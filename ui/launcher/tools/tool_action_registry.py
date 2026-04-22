"""
tool_action_registry.py

Extracted from: src.guppy.launcher_application.tool_action_registry
Purpose: Harden tool action registry with canonical action language
Lane: TR54-C1

Responsibilities:
  - Canonical action names across all tool surfaces
  - Action parameter schema validation
  - Action dispatch routing
  - Action completion reporting
  - Action evidence/trace collection

Action Categories:
  1. CONTROL - Enable/disable, start/stop, activate
  2. MANAGEMENT - Install, uninstall, update, reconfigure
  3. QUERY - Check status, get diagnostics, list items
  4. DATA - Import, export, backup, restore
  5. CONFIGURE - Settings, permissions, bindings

Canonical Action Names (LOCKED):

Control Actions:
  - tool.enable - Enable a disabled tool
  - tool.disable - Disable an enabled tool
  - tool.restart - Restart a running tool worker
  - tool.pause - Pause tool execution
  - tool.resume - Resume paused tool

Management Actions:
  - tool.install - Install new tool
  - tool.uninstall - Remove installed tool
  - tool.update - Update tool to new version
  - tool.configure - Open tool settings
  - tool.verify - Verify tool connectivity/setup

Query Actions:
  - tool.status - Get current tool status
  - tool.diagnostics - Get detailed diagnostics
  - tool.list_items - List tool-managed items
  - tool.get_logs - Retrieve tool logs

Data Actions:
  - tool.export - Export tool data
  - tool.import - Import tool data
  - tool.backup - Create backup
  - tool.restore - Restore from backup

Configuration Actions:
  - tool.set_permissions - Update permissions
  - tool.bind_credential - Bind credential
  - tool.unbind_credential - Remove credential
  - tool.set_preference - Set tool preference

Action Dispatch Rules:

1. ALL ACTIONS must use canonical names
2. ALL ACTIONS must include request_id for tracing
3. ALL ACTIONS must include source (home, settings, tools, etc.)
4. ALL ACTIONS must validate required parameters
5. ALL ACTIONS must have timeout
6. ALL ACTIONS must report completion/error

Action Evidence Rules:

1. Every action generates ActionEvent with:
   - action_name (canonical)
   - timestamp
   - parameters (sanitized)
   - result (success/failure)
   - duration_ms
   - request_id (for tracing)
   - source (which UI surface initiated)

2. Action failures must include:
   - error_code (machine-readable)
   - error_message (user-readable)
   - recovery_suggestion (next steps)

3. Action success must include:
   - result_summary (what changed)
   - affected_count (items affected)
   - new_state (state after action)

Action Naming Convention:

[domain].[operation]
  domain: tool, model, instance, connector
  operation: enable, disable, install, update, verify, etc.

Example:
  - tool.enable
  - model.download
  - instance.delete
  - connector.verify
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
import time
import logging

logger = logging.getLogger("launcher.tools.registry")


class ActionCategory(Enum):
    """Action categories."""
    CONTROL = "control"
    MANAGEMENT = "management"
    QUERY = "query"
    DATA = "data"
    CONFIGURE = "configure"


class ActionStatus(Enum):
    """Action execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class ActionParameter:
    """Defines a parameter for a tool action."""
    name: str
    required: bool
    param_type: str  # "string", "int", "bool", "list", etc.
    description: str
    default_value: Optional[Any] = None

    def validate(self, value: Any) -> tuple[bool, Optional[str]]:
        """
        Validate a parameter value.

        Args:
            value: Value to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if value is None:
            if self.required:
                return False, f"Parameter '{self.name}' is required"
            return True, None

        # Type checking
        expected_type = {
            "string": str,
            "int": int,
            "bool": bool,
            "list": list,
            "dict": dict,
        }.get(self.param_type)

        if expected_type and not isinstance(value, expected_type):
            return (
                False,
                f"Parameter '{self.name}' must be {self.param_type}, got {type(value).__name__}",
            )

        return True, None


@dataclass
class ActionSchema:
    """Defines the schema for a tool action."""
    name: str
    category: ActionCategory
    description: str
    parameters: list[ActionParameter] = field(default_factory=list)
    timeout_ms: int = 30000  # Default 30 second timeout
    idempotent: bool = False  # Can be safely retried
    requires_confirmation: bool = False  # Needs user confirmation

    def validate_parameters(self, params: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate all parameters against schema.

        Args:
            params: Parameter dict to validate

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        for param_schema in self.parameters:
            value = params.get(param_schema.name)
            is_valid, error = param_schema.validate(value)
            if not is_valid:
                errors.append(error)

        return len(errors) == 0, errors


@dataclass
class ActionEvent:
    """Records execution of a tool action."""
    action_name: str
    timestamp: float
    status: ActionStatus
    request_id: str
    source: str  # UI surface that initiated (home, settings, tools, etc.)
    parameters: dict[str, Any] = field(default_factory=dict)
    result_summary: str = ""
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    recovery_suggestion: Optional[str] = None
    affected_count: int = 0
    duration_ms: int = 0

    def is_success(self) -> bool:
        """Check if action succeeded."""
        return self.status == ActionStatus.SUCCESS

    def is_failure(self) -> bool:
        """Check if action failed."""
        return self.status in (ActionStatus.FAILURE, ActionStatus.TIMEOUT)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/storage."""
        return {
            "action_name": self.action_name,
            "timestamp": self.timestamp,
            "status": self.status.value,
            "request_id": self.request_id,
            "source": self.source,
            "parameters": self.parameters,
            "result_summary": self.result_summary,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "recovery_suggestion": self.recovery_suggestion,
            "affected_count": self.affected_count,
            "duration_ms": self.duration_ms,
        }


class ToolActionRegistry:
    """Registry of canonical tool actions."""

    # Canonical action schemas (LOCKED)
    CANONICAL_ACTIONS = {
        # Control actions
        "tool.enable": ActionSchema(
            "tool.enable",
            ActionCategory.CONTROL,
            "Enable a disabled tool",
            parameters=[ActionParameter("tool_key", True, "string", "Tool identifier")],
            idempotent=True,
        ),
        "tool.disable": ActionSchema(
            "tool.disable",
            ActionCategory.CONTROL,
            "Disable an enabled tool",
            parameters=[ActionParameter("tool_key", True, "string", "Tool identifier")],
            idempotent=True,
        ),
        "tool.restart": ActionSchema(
            "tool.restart",
            ActionCategory.CONTROL,
            "Restart a tool worker",
            parameters=[ActionParameter("tool_key", True, "string", "Tool identifier")],
            timeout_ms=45000,
        ),
        "tool.pause": ActionSchema(
            "tool.pause",
            ActionCategory.CONTROL,
            "Pause tool execution",
            parameters=[ActionParameter("tool_key", True, "string", "Tool identifier")],
            idempotent=True,
        ),
        "tool.resume": ActionSchema(
            "tool.resume",
            ActionCategory.CONTROL,
            "Resume paused tool",
            parameters=[ActionParameter("tool_key", True, "string", "Tool identifier")],
            idempotent=True,
        ),
        # Management actions
        "tool.install": ActionSchema(
            "tool.install",
            ActionCategory.MANAGEMENT,
            "Install new tool",
            parameters=[
                ActionParameter("tool_key", True, "string", "Tool identifier"),
                ActionParameter("version", False, "string", "Specific version to install"),
            ],
            timeout_ms=120000,
            requires_confirmation=True,
        ),
        "tool.uninstall": ActionSchema(
            "tool.uninstall",
            ActionCategory.MANAGEMENT,
            "Remove installed tool",
            parameters=[ActionParameter("tool_key", True, "string", "Tool identifier")],
            timeout_ms=60000,
            requires_confirmation=True,
        ),
        "tool.update": ActionSchema(
            "tool.update",
            ActionCategory.MANAGEMENT,
            "Update tool to new version",
            parameters=[ActionParameter("tool_key", True, "string", "Tool identifier")],
            timeout_ms=120000,
            requires_confirmation=True,
        ),
        "tool.configure": ActionSchema(
            "tool.configure",
            ActionCategory.MANAGEMENT,
            "Open tool settings",
            parameters=[ActionParameter("tool_key", True, "string", "Tool identifier")],
        ),
        "tool.verify": ActionSchema(
            "tool.verify",
            ActionCategory.MANAGEMENT,
            "Verify tool connectivity/setup",
            parameters=[ActionParameter("tool_key", True, "string", "Tool identifier")],
            timeout_ms=30000,
        ),
        # Query actions
        "tool.status": ActionSchema(
            "tool.status",
            ActionCategory.QUERY,
            "Get current tool status",
            parameters=[ActionParameter("tool_key", True, "string", "Tool identifier")],
            timeout_ms=5000,
        ),
        "tool.diagnostics": ActionSchema(
            "tool.diagnostics",
            ActionCategory.QUERY,
            "Get detailed diagnostics",
            parameters=[ActionParameter("tool_key", True, "string", "Tool identifier")],
            timeout_ms=10000,
        ),
    }

    def __init__(self) -> None:
        """Initialize registry."""
        self.actions = self.CANONICAL_ACTIONS.copy()
        self.action_handlers: dict[str, Callable] = {}
        self.event_history: list[ActionEvent] = []

    def get_action_schema(self, action_name: str) -> Optional[ActionSchema]:
        """Get schema for an action."""
        return self.actions.get(action_name)

    def validate_action(
        self, action_name: str, parameters: dict[str, Any]
    ) -> tuple[bool, list[str]]:
        """
        Validate an action with parameters.

        Args:
            action_name: Canonical action name
            parameters: Action parameters

        Returns:
            Tuple of (is_valid, error_messages)
        """
        schema = self.get_action_schema(action_name)
        if not schema:
            return False, [f"Unknown action: {action_name}"]

        return schema.validate_parameters(parameters)

    def register_handler(
        self, action_name: str, handler: Callable
    ) -> None:
        """Register a handler for an action."""
        if action_name not in self.actions:
            logger.warning(f"Registering handler for unknown action: {action_name}")
        self.action_handlers[action_name] = handler

    def record_event(self, event: ActionEvent) -> None:
        """Record an action event."""
        self.event_history.append(event)
        if len(self.event_history) > 1000:  # Keep last 1000 events
            self.event_history = self.event_history[-1000:]

        logger.debug(f"Action event: {event.action_name} -> {event.status.value}")

    def get_action_history(
        self, action_name: Optional[str] = None, limit: int = 10
    ) -> list[ActionEvent]:
        """Get recent action events."""
        events = self.event_history

        if action_name:
            events = [e for e in events if e.action_name == action_name]

        return events[-limit:]

    def create_action_event(
        self,
        action_name: str,
        request_id: str,
        source: str,
        parameters: dict[str, Any],
    ) -> ActionEvent:
        """Create a new action event."""
        return ActionEvent(
            action_name=action_name,
            timestamp=time.monotonic(),
            status=ActionStatus.PENDING,
            request_id=request_id,
            source=source,
            parameters=parameters,
        )

    def get_canonical_action_names(self) -> list[str]:
        """Get all canonical action names."""
        return list(self.actions.keys())

    def get_actions_by_category(self, category: ActionCategory) -> list[ActionSchema]:
        """Get all actions in a category."""
        return [a for a in self.actions.values() if a.category == category]


def create_action_registry() -> ToolActionRegistry:
    """Factory function to create a tool action registry."""
    return ToolActionRegistry()
