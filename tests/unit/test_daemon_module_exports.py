from src.guppy.daemon import daemon


def test_daemon_compat_exports_bound_services():
    assert daemon.GuppyNotifier.__module__ == "src.guppy.daemon.notifier"
    assert daemon.WindowWatcher.__module__ == "src.guppy.daemon.window_watcher"
    assert daemon.TaskScheduler.__module__ == "src.guppy.daemon.scheduler"
    assert daemon.ProactiveLoop.__module__ == "src.guppy.daemon.proactive_loop"
    assert daemon.AmbientWatcher.__module__ == "src.guppy.daemon.ambient_watcher"
    assert daemon.DaemonManager.__module__ == "src.guppy.daemon.manager"


def test_daemon_singleton_manager_still_constructs():
    daemon._daemon_manager = None
    manager = daemon.get_daemon_manager()
    assert manager.__class__.__module__ == "src.guppy.daemon.manager"
    assert manager.notifier.__class__.__module__ == "src.guppy.daemon.notifier"
    daemon._daemon_manager = None
