"""Hub application entrypoint and wiring."""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from src.guppy.apps.process_guard import acquire_process_guard
from src.guppy.hub.manager import HubManager
from src.guppy.launcher_application.launcher_api_runtime_control import probe_api_runtime_label as check_api_server
from src.guppy.hub.runtime_checks import (
    check_auth_config,
    check_cloudflared,
    cloudflare_cert_paths,
    is_set,
    model_for_agent,
    parse_iso_ts,
    rolling_agent_stats,
    safe_int,
    tail_agent_performance,
    tail_session_events,
    warm_ollama_model,
)
from src.guppy.hub.shell import SystemTray
from src.guppy.hub.window import HubWindow

logger = logging.getLogger("OmnissiahHub")

try:
    from utils.safe_io import read_json_dict as _read_json_dict, write_json_atomic as _write_json_atomic

    _SAFE_IO = True
except Exception:
    _SAFE_IO = False

    def _read_json_dict(path, **_):  # type: ignore[misc]
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write_json_atomic(path, data):  # type: ignore[misc]
        try:
            Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
            return True
        except Exception:
            return False


_ROOT = Path(__file__).resolve().parents[3]
_RUNTIME = _ROOT / "runtime"
HB_STALE_SECS = int(os.environ.get("GUPPY_HB_STALE_SECS", "30"))


try:
    import psutil
except ImportError:
    psutil = None  # type: ignore[assignment]


try:
    from src.guppy.daemon.daemon import get_window_context

    _DAEMON_AVAILABLE = True
except Exception:
    _DAEMON_AVAILABLE = False

    def get_window_context():
        return {"title": "Sample Window Title"}


try:
    from utils.hub_operator import get_operator as _get_operator

    _OPERATOR_AVAILABLE = True
except Exception as exc:
    logger.warning(f"HubOperator unavailable (operator features disabled): {exc}")
    _OPERATOR_AVAILABLE = False


try:
    from utils.env_bootstrap import load_env_file

    load_env_file()
except Exception as exc:
    logger.warning(f"env_bootstrap failed (env vars may be missing): {exc}")


from src.guppy.experience_config.services import (
    apply_runtime_profile,
    load_runtime_settings as load_app_settings,
    recommend_runtime_profile,
)

try:
    APP_SETTINGS = apply_runtime_profile()
except Exception as exc:
    logger.error(f"runtime_profile load failed - using hard-coded defaults: {exc}")
    APP_SETTINGS = {
        "runtime_profile": os.environ.get("GUPPY_RUNTIME_PROFILE", "standard"),
        "enable_daemon": os.environ.get("GUPPY_ENABLE_DAEMON", "1").strip().lower()
        in {"1", "true", "yes", "on"},
    }


logger.setLevel(logging.INFO)
if not logger.handlers:
    stream = logging.StreamHandler()
    stream.setFormatter(logging.Formatter("[%(levelname)s] %(asctime)s %(name)s: %(message)s", "%H:%M:%S"))
    logger.addHandler(stream)
    try:
        _RUNTIME.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(_RUNTIME / "hub.log", encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("[%(levelname)s] %(asctime)s %(name)s: %(message)s"))
        logger.addHandler(file_handler)
    except Exception:
        pass


_VENV_PYTHON = _ROOT / ".venv" / "Scripts" / "python.exe"
PYTHON = str(_VENV_PYTHON) if _VENV_PYTHON.exists() else sys.executable


def _check_cloudflared() -> str:
    return check_cloudflared(psutil is not None)


def _tail_agent_performance(limit: int = 200) -> list[dict]:
    return tail_agent_performance(_RUNTIME, _SAFE_IO, limit)


def _tail_session_events(limit: int = 200) -> list[dict]:
    return tail_session_events(_RUNTIME, _SAFE_IO, limit)


def main() -> int:
    logger.info("Omnissiah starting...")

    lock = acquire_process_guard(
        _RUNTIME / "hub.lock",
        process_markers=("guppy_hub.py", "src.guppy.hub.app", "src\\guppy\\hub\\app"),
    )
    if lock is None:
        logger.info("Omnissiah already running - exiting duplicate hub start")
        return 0

    pid_path = _RUNTIME / "hub.pid"
    try:
        _RUNTIME.mkdir(parents=True, exist_ok=True)
        pid_path.write_text(str(os.getpid()), encoding="utf-8")
    except Exception as exc:
        logger.warning(f"Could not write hub.pid: {exc}")

    try:
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)

        manager = HubManager()
        operator = _get_operator() if _OPERATOR_AVAILABLE else None

        window = HubWindow(
            manager=manager,
            logger=logger,
            load_settings=load_app_settings,
            get_window_context=get_window_context,
            daemon_available=_DAEMON_AVAILABLE,
            psutil_module=psutil,
            runtime_dir=_RUNTIME,
            root_dir=_ROOT,
            python_executable=PYTHON,
            hb_stale_secs=HB_STALE_SECS,
            operator=operator,
            status_check_fns={
                "recommend_runtime_profile": recommend_runtime_profile,
                "check_api_server": check_api_server,
                "check_cloudflared": _check_cloudflared,
                "check_auth_config": check_auth_config,
                "cloudflare_cert_paths": cloudflare_cert_paths,
                "is_set": is_set,
                "safe_int": safe_int,
            },
            orchestration_fns={
                "tail_agent_performance": _tail_agent_performance,
                "tail_session_events": _tail_session_events,
                "rolling_agent_stats": rolling_agent_stats,
                "parse_iso_ts": parse_iso_ts,
                "warm_ollama_model": warm_ollama_model,
                "model_for_agent": model_for_agent,
            },
        )
        tray = SystemTray(window, app, load_app_settings)

        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("System tray unavailable; showing Omnissiah window instead.")
            window.show()
            app.setQuitOnLastWindowClosed(True)
        else:
            tray.show()
            window.hide()

        logger.info("Omnissiah ready.")
        return app.exec()
    except Exception as exc:
        logger.error(f"Omnissiah failed to start: {exc}")
        raise
    finally:
        try:
            pid_path.unlink(missing_ok=True)
        except Exception:
            pass
        lock.release()
