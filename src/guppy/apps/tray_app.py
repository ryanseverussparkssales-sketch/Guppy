"""Guppy System Tray — lightweight process monitor + quick launcher.

Runs independently of the API server. Monitors API health, lets you
open the web UI / control panel, restart the API, and wake models.

Launch via:
    pythonw src/guppy/cli/launch.py tray
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

import pystray
from PIL import Image, ImageDraw, ImageFont

ROOT   = Path(__file__).resolve().parents[3]
PYTHON = str(ROOT / ".venv" / "Scripts" / "pythonw.exe")
if not Path(PYTHON).exists():
    PYTHON = sys.executable

_PORT       = int(os.environ.get("GUPPY_API_PORT", "8081"))
_HEALTH_URL = f"http://127.0.0.1:{_PORT}/health"
_APP_URL    = f"http://127.0.0.1:{_PORT}/"
_CTRL_URL   = f"http://127.0.0.1:{_PORT}/control"

# ── Icon generation ────────────────────────────────────────────────────────────

def _make_icon(color: tuple[int, int, int]) -> Image.Image:
    size = 64
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Outer ring
    draw.ellipse([2, 2, size - 2, size - 2], fill=(*color, 60))
    # Inner solid circle
    pad = 10
    draw.ellipse([pad, pad, size - pad, size - pad], fill=(*color, 255))
    return img


_ICON_GREEN  = _make_icon((74, 222, 128))   # API healthy
_ICON_YELLOW = _make_icon((251, 191, 36))   # API starting
_ICON_RED    = _make_icon((248, 113, 113))  # API down


# ── API helpers ────────────────────────────────────────────────────────────────

def _api_alive() -> bool:
    try:
        with urllib.request.urlopen(_HEALTH_URL, timeout=2) as r:
            return r.status < 500
    except Exception:
        return False


_api_proc: subprocess.Popen | None = None


def _start_api() -> None:
    global _api_proc
    if _api_alive():
        return
    launch = ROOT / "src" / "guppy" / "cli" / "launch.py"
    flags = (
        subprocess.DETACHED_PROCESS
        | subprocess.CREATE_NEW_PROCESS_GROUP
        | subprocess.CREATE_NO_WINDOW
    ) if sys.platform == "win32" else 0
    _api_proc = subprocess.Popen(
        [PYTHON.replace("pythonw", "python"), str(launch), "api"],
        cwd=str(ROOT),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )


def _restart_api(icon: pystray.Icon, item: pystray.MenuItem) -> None:
    icon.icon = _ICON_YELLOW
    icon.title = "Guppy — restarting…"
    # Kill any existing API process on the port
    try:
        import socket
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", _PORT)) == 0:
                # Port occupied — find and kill it
                _kill_port(_PORT)
                time.sleep(1.5)
    except Exception:
        pass
    _start_api()


def _kill_port(port: int) -> None:
    if sys.platform != "win32":
        return
    try:
        out = subprocess.check_output(
            ["netstat", "-ano"], text=True, creationflags=subprocess.CREATE_NO_WINDOW
        )
        for line in out.splitlines():
            if f":{port} " in line and "LISTENING" in line:
                pid = line.strip().split()[-1]
                if pid and pid != "0":
                    subprocess.run(
                        ["taskkill", "/F", "/PID", pid],
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        capture_output=True,
                    )
    except Exception:
        pass


# ── Menu actions ───────────────────────────────────────────────────────────────

def _open_app(icon: pystray.Icon, item: pystray.MenuItem) -> None:
    webbrowser.open(_APP_URL)


def _open_control(icon: pystray.Icon, item: pystray.MenuItem) -> None:
    if not _api_alive():
        _start_api()
        time.sleep(3)
    webbrowser.open(_CTRL_URL)


def _open_companion(icon: pystray.Icon, item: pystray.MenuItem) -> None:
    webbrowser.open(f"http://127.0.0.1:{_PORT}/companion")


def _open_workspace(icon: pystray.Icon, item: pystray.MenuItem) -> None:
    webbrowser.open(f"http://127.0.0.1:{_PORT}/workspace")


def _quit(icon: pystray.Icon, item: pystray.MenuItem) -> None:
    icon.stop()


# ── Health monitor thread ──────────────────────────────────────────────────────

def _monitor(icon: pystray.Icon) -> None:
    _was_alive = False
    while icon.visible:
        alive = _api_alive()
        if alive:
            icon.icon  = _ICON_GREEN
            icon.title = "Guppy — running"
        else:
            icon.icon  = _ICON_RED
            icon.title = "Guppy — API offline"
        _was_alive = alive
        time.sleep(10)


# ── Build menu ─────────────────────────────────────────────────────────────────

def _build_menu() -> pystray.Menu:
    return pystray.Menu(
        pystray.MenuItem("Open Guppy",        _open_app,      default=True),
        pystray.MenuItem("Control Panel",     _open_control),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Companion",         _open_companion),
        pystray.MenuItem("Workspace",         _open_workspace),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Restart API",       _restart_api),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit Tray",         _quit),
    )


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    # Start API if not running
    if not _api_alive():
        _start_api()

    initial_icon = _ICON_YELLOW if not _api_alive() else _ICON_GREEN
    initial_title = "Guppy — starting…" if not _api_alive() else "Guppy — running"

    icon = pystray.Icon(
        name="guppy",
        icon=initial_icon,
        title=initial_title,
        menu=_build_menu(),
    )

    # Start background health monitor
    t = threading.Thread(target=_monitor, args=(icon,), daemon=True)
    t.start()

    icon.run()


if __name__ == "__main__":
    main()
