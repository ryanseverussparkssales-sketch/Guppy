from __future__ import annotations

from src.guppy.daemon.ambient_watcher import AmbientWatcher
from src.guppy.daemon.notifier import GuppyNotifier
from src.guppy.daemon.proactive_loop import ProactiveLoop
from src.guppy.daemon.scheduler import TaskScheduler
from src.guppy.daemon.support import logger
from src.guppy.daemon.window_watcher import WindowWatcher


class DaemonManager:
    """Lifecycle manager for background services."""

    def __init__(self):
        self.notifier = GuppyNotifier()
        self.window_watcher = WindowWatcher()
        self.task_scheduler = TaskScheduler(notifier=self.notifier)
        self.proactive_loop = ProactiveLoop(notifier=self.notifier, scheduler=self.task_scheduler)
        self.ambient_watcher = AmbientWatcher(notifier=self.notifier, window_watcher=self.window_watcher)
        self.is_running = False

    def start(self):
        if self.is_running:
            return

        self.is_running = True
        try:
            self.window_watcher.start()
            self.task_scheduler.start()
            self.proactive_loop.start()
            self.ambient_watcher.start()
            logger.info("✓ All daemons started")
        except Exception as e:
            logger.error(f"Daemon start failed: {e}")
            self.is_running = False

    def stop(self):
        if not self.is_running:
            return

        try:
            self.window_watcher.stop()
            self.task_scheduler.stop()
            self.proactive_loop.stop()
            self.ambient_watcher.stop()
            self.is_running = False
            logger.info("✓ All daemons stopped")
        except Exception as e:
            logger.error(f"Daemon stop failed: {e}")
