from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.guppy.daemon.support import TOAST_AVAILABLE, logger, win11_toast


class GuppyNotifier:
    """Windows 11 toast notification system."""

    def __init__(self):
        self._toast = win11_toast if TOAST_AVAILABLE else None
        self.app_id = "Guppy"

    def show(self, title: str, msg: str, duration: int = 5, icon: Optional[str] = None):
        """Show a toast notification."""
        if not TOAST_AVAILABLE:
            logger.warning(f"Toast unavailable: {title} - {msg}")
            return

        try:
            kwargs = {"app_id": self.app_id, "duration": str(duration)}
            if icon and Path(icon).exists():
                kwargs["icon"] = icon
            self._toast(title, msg, **kwargs)
        except Exception as e:
            logger.error(f"Toast failed: {e}")

    def reminder(self, text: str):
        self.show("⏰ Guppy Reminder", text, duration=10)

    def task_done(self, task_name: str):
        self.show("✓ Task Complete", task_name, duration=5)

    def error(self, msg: str):
        self.show("⚠️ Error", msg, duration=10)

    def info(self, title: str, msg: str):
        self.show(title, msg, duration=5)
