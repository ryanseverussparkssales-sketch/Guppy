"""Chat session lifecycle helpers extracted from launcher_command_flow.

Provides session rotation, context application, and context-changed signal
handling as a dedicated seam.  All three symbols are re-exported from
``launcher_command_flow`` for backward compatibility.
"""
from __future__ import annotations

from .launcher_assistant_event_flow import (
    apply_chat_context,
    on_chat_context_changed,
    rotate_chat_session,
)

__all__ = [
    "apply_chat_context",
    "on_chat_context_changed",
    "rotate_chat_session",
]
