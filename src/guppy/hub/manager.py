"""Hub recommendation manager logic."""
from __future__ import annotations

import logging
import os

from PySide6.QtCore import QObject, Signal

try:
    import anthropic

    _CLAUDE_OK = True
except ImportError:
    _CLAUDE_OK = False

try:
    from utils.runtime_profile import load_app_settings
except Exception:
    def load_app_settings():
        return {"show_advanced_surfaces": True}

logger = logging.getLogger("OmnissiahHub")


class HubManager(QObject):
    """Determines which agent to recommend based on window context and load."""

    recommendation_changed = Signal(str, str)

    def __init__(self):
        super().__init__()
        self._mode = "claude" if (_CLAUDE_OK and os.environ.get("ANTHROPIC_API_KEY")) else "ollama"
        self._context_summary = "No context available"
        self._recommendation_summary = "Standing by."
        self._recommended_agent = "guppy"
        self._auto_last_action = "Idle"
        logger.info(f"HubManager initialized with mode: {self.mode}")

    @property
    def mode(self) -> str:
        if not _CLAUDE_OK:
            return "DISABLED"
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "CLAUDE"
        return "OLLAMA"

    def recommend(self, title: str, running_agents: list[str]) -> str:
        title_text = title or ""
        del running_agents
        rec = "guppy"
        logger.debug(f"Recommending {rec} for '{title_text}'")
        return rec

    def ask(self, prompt: str) -> str:
        if os.environ.get("ANTHROPIC_API_KEY") and _CLAUDE_OK:
            try:
                client = anthropic.Anthropic()
                msg = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=512,
                    messages=[{"role": "user", "content": prompt}],
                )
                return msg.content[0].text if msg.content else "No response from Omnissiah."
            except Exception as e:
                return f"Omnissiah error: {e}"
        return "Claude unavailable: ANTHROPIC_API_KEY not set."

    def update_context(self, title: str, running: list[str]):
        self._context_summary = title or "No context"
        rec = self.recommend(title, running)
        _ = load_app_settings()
        self._recommended_agent = rec
        self._recommendation_summary = f"Recommended: {rec}"
        self.recommendation_changed.emit(rec, self._recommendation_summary)
