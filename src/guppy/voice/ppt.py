"""
Push-to-Talk State Machine
============================

Manages the lifecycle of voice input: activate → listen → transcribe → deactivate.

States:
  IDLE        - Not listening
  LISTENING   - Recording audio from microphone
  TRANSCRIBING - Processing recorded audio through STT
  ACTIVE      - Speaking (TTS in progress)
  INACTIVE    - Shutdown

Transitions:
  IDLE → LISTENING (on user press)
  LISTENING → TRANSCRIBING (on user release)
  TRANSCRIBING → IDLE (on completion or error)
  IDLE ↔ ACTIVE (TTS can interleave)

This module is a placeholder for the push-to-talk state machine.
Full implementation in Phase 1, Task 1.4.
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable, Any


class PushToTalkState(str, Enum):
    """Push-to-talk state enumeration."""
    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    ACTIVE = "active"  # TTS playing
    INACTIVE = "inactive"  # Shutdown


@dataclass
class PushToTalkEvent:
    """Event in push-to-talk lifecycle."""
    state: PushToTalkState
    timestamp: datetime = field(default_factory=datetime.utcnow)
    duration_ms: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class PushToTalkStateMachine:
    """
    State machine for managing voice input lifecycle.

    Usage:
        ppt = PushToTalkStateMachine()
        ppt.on_event(PushToTalkEvent(PushToTalkState.LISTENING))
        # ... record audio ...
        ppt.on_event(PushToTalkEvent(PushToTalkState.TRANSCRIBING))
        # ... transcribe ...
        ppt.on_event(PushToTalkEvent(PushToTalkState.IDLE))
    """

    def __init__(self) -> None:
        """Initialize state machine in IDLE state."""
        self.state = PushToTalkState.IDLE
        self.event_history: list[PushToTalkEvent] = []
        self.state_change_callback: Optional[Callable[[PushToTalkState], None]] = None

    def on_event(self, event: PushToTalkEvent) -> bool:
        """
        Handle a state transition event.

        Args:
            event: The state event to process

        Returns:
            True if transition was valid, False if invalid
        """
        # State transition validation will be implemented in Phase 1
        if self._is_valid_transition(self.state, event.state):
            self.state = event.state
            self.event_history.append(event)
            if self.state_change_callback:
                self.state_change_callback(self.state)
            return True
        return False

    def _is_valid_transition(
        self, from_state: PushToTalkState, to_state: PushToTalkState
    ) -> bool:
        """Check if a state transition is valid."""
        # Simplified: all transitions are valid for now
        # Full validation in Phase 1
        return True

    def reset(self) -> None:
        """Reset state machine to IDLE."""
        self.state = PushToTalkState.IDLE
        self.event_history = []

    def get_current_state(self) -> PushToTalkState:
        """Get current state."""
        return self.state

    def get_event_history(self) -> list[PushToTalkEvent]:
        """Get list of all state transitions."""
        return self.event_history.copy()
