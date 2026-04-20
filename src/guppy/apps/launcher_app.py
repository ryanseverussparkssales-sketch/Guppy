"""
guppy_launcher.py
Unified OBSIDIAN / COMMAND_INTERFACE entry point.
Launches the PySide6 multi-surface launcher.
On startup, ensures guppy_api.py and guppy_hub.py are running as background
processes so agents, recovery tools, and the daemon are all available.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.guppy.apps.process_guard import acquire_process_guard
from ui.launcher import LauncherWindow
from ui.launcher.components import create_guppy_fish_icon

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("GuppyLauncher")

_VENV_PYTHON = _ROOT / ".venv" / "Scripts" / "python.exe"
_VENV_PYTHONW = _ROOT / ".venv" / "Scripts" / "pythonw.exe"
_PYTHON = str(_VENV_PYTHON) if _VENV_PYTHON.exists() else sys.executable
_BACKGROUND_PYTHON = str(_VENV_PYTHONW) if _VENV_PYTHONW.exists() else _PYTHON
_STARTUP_STAMP_TTL_SECONDS = float(os.environ.get("GUPPY_STARTUP_STAMP_TTL_SECONDS", "20"))

_DETACHED: dict = (
    {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW}
    if sys.platform == "win32" else {}
)


def _append_launcher_event(event: str, **fields: object) -> None:
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source": "launcher_bootstrap",
        "event": event,
        **fields,
    }
    try:
        path = _ROOT / "runtime" / "launcher_events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=True) + "\n")
    except Exception:
        pass


def _api_reachable() -> bool:
    try:
        req = urllib.request.Request("http://127.0.0.1:8081/")
        with urllib.request.urlopen(req, timeout=1.2):
            return True
    except Exception:
        return False


def _cleanup_hub_pid() -> None:
    pid_path = _ROOT / "runtime" / "hub.pid"
    try:
        pid_path.unlink(missing_ok=True)
    except Exception:
        pass


def _startup_stamp_path(name: str) -> Path:
    return _ROOT / "runtime" / f"{name}.starting"


def _mark_startup_attempt(name: str) -> None:
    path = _startup_stamp_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(time.time()), encoding="utf-8")


def _clear_startup_attempt(name: str) -> None:
    try:
        _startup_stamp_path(name).unlink(missing_ok=True)
    except Exception:
        pass


def _startup_attempt_recent(name: str, *, ttl_seconds: float = _STARTUP_STAMP_TTL_SECONDS) -> bool:
    path = _startup_stamp_path(name)
    if not path.exists():
        return False
    try:
        age_seconds = time.time() - path.stat().st_mtime
    except OSError:
        return False
    if age_seconds <= ttl_seconds:
        return True
    _clear_startup_attempt(name)
    return False


def _spawn_background_process(script: Path, *, log_name: str) -> None:
    log_path = _ROOT / "runtime" / log_name
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log_file:
        subprocess.Popen(
            [_BACKGROUND_PYTHON, str(script)],
            cwd=str(_ROOT),
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=log_file,
            **_DETACHED,
        )


def _start_api() -> None:
    """Launch guppy_api.py detached if port 8081 is not answering."""
    if _api_reachable():
        _clear_startup_attempt("api")
        logger.info("API already reachable on :8081 - skipping auto-start")
        return
    if _startup_attempt_recent("api"):
        logger.info("API autostart already attempted recently - skipping duplicate spawn")
        _append_launcher_event("startup_phase", phase="api_autostart_debounced")
        return
    script = _ROOT / "guppy_api.py"
    if not script.exists():
        logger.warning("guppy_api.py not found - skipping API auto-start")
        return
    logger.info("Starting guppy_api.py in background...")
    try:
        _mark_startup_attempt("api")
        _spawn_background_process(script, log_name="launcher_api.log")
        deadline = time.monotonic() + 6.0
        while time.monotonic() < deadline:
            time.sleep(0.5)
            if _api_reachable():
                _clear_startup_attempt("api")
                logger.info("guppy_api.py is up and reachable")
                return
        logger.warning("guppy_api.py started but not yet reachable after 6 s")
    except Exception as exc:
        _clear_startup_attempt("api")
        logger.error("Failed to start guppy_api.py: %s", exc)


def _hub_running() -> bool:
    """Best-effort check: is the hub process alive via pid file?"""
    hb = _ROOT / "runtime" / "hub.pid"
    if not hb.exists():
        return False
    try:
        pid = int(hb.read_text().strip())
    except Exception:
        _cleanup_hub_pid()
        return False
    try:
        import psutil

        if not psutil.pid_exists(pid):
            _cleanup_hub_pid()
            return False
        try:
            process = psutil.Process(pid)
            command_line = " ".join(process.cmdline()).lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
            _cleanup_hub_pid()
            return False
        if "guppy_hub.py" in command_line or "src.guppy.hub.app" in command_line:
            return True
        _cleanup_hub_pid()
        return False
    except ImportError:
        logger.warning("psutil not available - cannot verify hub PID, will launch hub")
        return False


def _start_hub() -> None:
    """Launch guppy_hub.py detached if it's not already running."""
    if _hub_running():
        _clear_startup_attempt("hub")
        logger.info("Hub already running - skipping auto-start")
        return
    if _startup_attempt_recent("hub"):
        logger.info("Hub autostart already attempted recently - skipping duplicate spawn")
        _append_launcher_event("startup_phase", phase="hub_autostart_debounced")
        return
    script = _ROOT / "guppy_hub.py"
    if not script.exists():
        logger.warning("guppy_hub.py not found - skipping hub auto-start")
        return
    logger.info("Starting guppy_hub.py in background...")
    try:
        _mark_startup_attempt("hub")
        _spawn_background_process(script, log_name="launcher_hub.log")
        logger.info("guppy_hub.py launched")
    except Exception as exc:
        _clear_startup_attempt("hub")
        logger.error("Failed to start guppy_hub.py: %s", exc)


def main() -> int:
    lock = acquire_process_guard(
        _ROOT / "runtime" / "launcher.lock",
        process_markers=("guppy_launcher.py", "src.guppy.apps.launcher_app", "src\\guppy\\apps\\launcher_app"),
    )
    if lock is None:
        logger.info("Launcher already running - skipping duplicate start")
        _append_launcher_event("startup_phase", phase="launcher_duplicate_instance")
        return 0

    _append_launcher_event("startup_phase", phase="launcher_enter")
    startup_budget_ms = int(os.environ.get("GUPPY_STARTUP_PHASE_WARN_MS", "3000"))
    try:
        app = QApplication(sys.argv)
        app.setApplicationName("Guppy AI")
        app.setApplicationDisplayName("COMMAND_INTERFACE")
        app.setApplicationVersion("5.0")
        app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
        app.setWindowIcon(create_guppy_fish_icon())

        window = LauncherWindow()
        window.setWindowIcon(create_guppy_fish_icon())
        window.show()
        _append_launcher_event("startup_phase", phase="window_shown")

        def _bootstrap_services() -> None:
            t0 = time.monotonic()
            _append_launcher_event("startup_phase", phase="bootstrap_services_begin")
            skip_all = os.environ.get("GUPPY_SKIP_ALL_BOOTSTRAP", "0").strip().lower() in {
                "1", "true", "yes", "on"
            }
            if skip_all:
                logger.info("All background bootstrap skipped by GUPPY_SKIP_ALL_BOOTSTRAP")
                _append_launcher_event("startup_phase", phase="bootstrap_services_skipped_all")
                dur_ms = int((time.monotonic() - t0) * 1000)
                _append_launcher_event(
                    "startup_phase_duration",
                    phase="bootstrap_services",
                    duration_ms=dur_ms,
                    budget_ms=startup_budget_ms,
                    over_budget=dur_ms > startup_budget_ms,
                )
                return

            _start_api()
            skip_hub = os.environ.get("GUPPY_SKIP_HUB_AUTOSTART", "0").strip().lower() in {
                "1", "true", "yes", "on"
            }
            if skip_hub:
                logger.info("Hub autostart skipped by GUPPY_SKIP_HUB_AUTOSTART")
                _append_launcher_event("startup_phase", phase="hub_autostart_skipped")
            else:
                _start_hub()
            _append_launcher_event("startup_phase", phase="bootstrap_services_complete")
            dur_ms = int((time.monotonic() - t0) * 1000)
            _append_launcher_event(
                "startup_phase_duration",
                phase="bootstrap_services",
                duration_ms=dur_ms,
                budget_ms=startup_budget_ms,
                over_budget=dur_ms > startup_budget_ms,
            )
            if dur_ms > startup_budget_ms:
                _append_launcher_event(
                    "startup_phase_over_budget",
                    phase="bootstrap_services",
                    duration_ms=dur_ms,
                    budget_ms=startup_budget_ms,
                )

        threading.Thread(target=_bootstrap_services, daemon=True).start()

        return app.exec()
    finally:
        lock.release()


if __name__ == "__main__":
    sys.exit(main())
