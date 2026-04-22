"""
guppy_daemon.py - Background services, notifications, scheduling.

Compatibility module that preserves the public daemon import surface while
delegating the implementation to bounded service modules under
``src.guppy.daemon``.
"""

from __future__ import annotations

from typing import Dict

from src.guppy.daemon.ambient_watcher import AmbientWatcher
from src.guppy.daemon.manager import DaemonManager
from src.guppy.daemon.notifier import GuppyNotifier
from src.guppy.daemon.proactive_loop import ProactiveLoop
from src.guppy.daemon.scheduler import TaskScheduler
from src.guppy.daemon.support import PSUTIL_AVAILABLE, TOAST_AVAILABLE, WIN32_AVAILABLE, logger
from src.guppy.daemon.window_watcher import WindowWatcher


_daemon_manager = None


def get_daemon_manager() -> DaemonManager:
    """Get or create the global daemon manager."""
    global _daemon_manager
    if _daemon_manager is None:
        _daemon_manager = DaemonManager()
    return _daemon_manager


def show_notification(title: str, msg: str, duration: int = 5):
    """Convenience function for showing toast notifications."""
    get_daemon_manager().notifier.show(title, msg, duration)


def get_window_context() -> Dict[str, str]:
    """Get current window/app context."""
    return get_daemon_manager().window_watcher.get_context()


def schedule_reminder(text: str, run_time: str) -> str:
    """Schedule a reminder (convenience function)."""
    return get_daemon_manager().task_scheduler.schedule_reminder(text, run_time)


__all__ = [
    "AmbientWatcher",
    "DaemonManager",
    "GuppyNotifier",
    "PSUTIL_AVAILABLE",
    "ProactiveLoop",
    "TOAST_AVAILABLE",
    "TaskScheduler",
    "WIN32_AVAILABLE",
    "WindowWatcher",
    "get_daemon_manager",
    "get_window_context",
    "logger",
    "schedule_reminder",
    "show_notification",
]
