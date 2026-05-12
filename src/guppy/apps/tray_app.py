"""Guppy System Tray — lightweight process monitor + quick launcher.

Runs independently of the API server. Monitors API health and llama.cpp
model health, lets you open the web UI / control panel, and start/stop/restart
any always-on model without touching a terminal.

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
from PIL import Image, ImageDraw

ROOT   = Path(__file__).resolve().parents[3]
PYTHON = str(ROOT / ".venv" / "Scripts" / "pythonw.exe")
if not Path(PYTHON).exists():
    PYTHON = sys.executable

_PORT       = int(os.environ.get("GUPPY_API_PORT", "8081"))
_HEALTH_URL = f"http://127.0.0.1:{_PORT}/health"
_APP_URL    = f"http://127.0.0.1:{_PORT}/"
_CTRL_URL   = f"http://127.0.0.1:{_PORT}/control"

# ── Always-on model definitions ────────────────────────────────────────────────
# Order matters: shown top-to-bottom in the Models submenu.

_MODELS: dict[str, dict] = {
    "llamacpp-hermes4": {
        "label": "Hermes 4.3 36B  (primary)",
        "port":  8086,
        "bat":   r"C:\llama-cpp\launch-hermes-4_3-36b.bat",
    },
    "llamacpp-phi4-mini": {
        "label": "Phi-4-mini  (orchestrator)",
        "port":  8091,
        "bat":   r"C:\llama-cpp\launch-phi4-mini.bat",
    },
    "llamacpp-nomic-embed": {
        "label": "nomic-embed  (embeddings)",
        "port":  8092,
        "bat":   r"C:\llama-cpp\launch-nomic-embed.bat",
    },
}

# Cached liveness — updated by monitor thread; read by menu builder.
_model_status: dict[str, bool] = {k: False for k in _MODELS}


# ── Icon generation ────────────────────────────────────────────────────────────

def _make_icon(color: tuple[int, int, int]) -> Image.Image:
    size = 64
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([2,  2,  size - 2,  size - 2],  fill=(*color, 60))
    pad = 10
    draw.ellipse([pad, pad, size - pad, size - pad], fill=(*color, 255))
    return img


_ICON_GREEN  = _make_icon((74, 222, 128))   # API + primary model healthy
_ICON_YELLOW = _make_icon((251, 191, 36))   # API up but primary model offline
_ICON_RED    = _make_icon((248, 113, 113))  # API down


# ── Liveness helpers ───────────────────────────────────────────────────────────

def _api_alive() -> bool:
    try:
        with urllib.request.urlopen(_HEALTH_URL, timeout=2) as r:
            return r.status < 500
    except Exception:
        return False


def _model_alive(port: int) -> bool:
    try:
        url = f"http://127.0.0.1:{port}/health"
        with urllib.request.urlopen(url, timeout=1) as r:
            return r.status < 500
    except Exception:
        return False


# ── Port / process management ──────────────────────────────────────────────────

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
                        ["taskkill", "/F", "/T", "/PID", pid],
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        capture_output=True,
                    )
    except Exception:
        pass


def _start_model(key: str) -> None:
    cfg = _MODELS[key]
    bat = cfg["bat"]
    if not Path(bat).exists():
        return
    subprocess.Popen(
        ["cmd", "/c", bat],
        creationflags=(
            subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.CREATE_NO_WINDOW
        ),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _stop_model(key: str) -> None:
    _kill_port(_MODELS[key]["port"])


def _restart_model(key: str) -> None:
    _stop_model(key)
    time.sleep(2)
    _start_model(key)


# ── Menu action wrappers ───────────────────────────────────────────────────────

def _model_action(key: str, action: str):
    """Return a pystray handler that runs the model action in a background thread."""
    def _handler(icon: pystray.Icon, item: pystray.MenuItem) -> None:
        def _run() -> None:
            if action == "start":
                _start_model(key)
            elif action == "stop":
                _stop_model(key)
            elif action == "restart":
                _restart_model(key)
        threading.Thread(target=_run, daemon=True).start()
    return _handler


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
    icon.icon  = _ICON_YELLOW
    icon.title = "Guppy — restarting…"
    try:
        import socket
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", _PORT)) == 0:
                _kill_port(_PORT)
                time.sleep(1.5)
    except Exception:
        pass
    _start_api()


# ── Navigation helpers ─────────────────────────────────────────────────────────

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


# ── Menu builder ───────────────────────────────────────────────────────────────

def _all_models_action(action: str):
    """Return a pystray handler that runs an action on all models sequentially."""
    def _handler(icon: pystray.Icon, item: pystray.MenuItem) -> None:
        def _run() -> None:
            for key in _MODELS:
                if action == "start":
                    if not _model_status.get(key):
                        _start_model(key)
                        time.sleep(1)   # stagger so they don't compete for VRAM init
                elif action == "stop":
                    _stop_model(key)
                elif action == "restart":
                    _stop_model(key)
            if action == "restart":
                time.sleep(2)
                for key in _MODELS:
                    _start_model(key)
                    time.sleep(1)
        threading.Thread(target=_run, daemon=True).start()
    return _handler


def _build_menu() -> pystray.Menu:
    model_items: list[pystray.MenuItem] = [
        pystray.MenuItem("Start All",   _all_models_action("start")),
        pystray.MenuItem("Restart All", _all_models_action("restart")),
        pystray.MenuItem("Stop All",    _all_models_action("stop")),
        pystray.Menu.SEPARATOR,
    ]
    for key, cfg in _MODELS.items():
        alive  = _model_status.get(key, False)
        dot    = "● " if alive else "○ "
        bat_ok = Path(cfg["bat"]).exists()
        sub = pystray.Menu(
            pystray.MenuItem("Start",   _model_action(key, "start"),   enabled=bat_ok and not alive),
            pystray.MenuItem("Stop",    _model_action(key, "stop"),    enabled=alive),
            pystray.MenuItem("Restart", _model_action(key, "restart"), enabled=bat_ok),
        )
        model_items.append(pystray.MenuItem(f"{dot}{cfg['label']}", sub))

    return pystray.Menu(
        pystray.MenuItem("Open Guppy",    _open_app,     default=True),
        pystray.MenuItem("Control Panel", _open_control),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Companion",     _open_companion),
        pystray.MenuItem("Workspace",     _open_workspace),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Models", pystray.Menu(*model_items)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Restart API",   _restart_api),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit Tray",     _quit),
    )


# ── Health monitor thread ──────────────────────────────────────────────────────

def _monitor(icon: pystray.Icon) -> None:
    while icon.visible:
        alive = _api_alive()
        for key, cfg in _MODELS.items():
            _model_status[key] = _model_alive(cfg["port"])

        primary_ok = _model_status.get("llamacpp-hermes4", False)
        if alive and primary_ok:
            icon.icon  = _ICON_GREEN
            icon.title = "Guppy — running"
        elif alive:
            icon.icon  = _ICON_YELLOW
            icon.title = "Guppy — primary model offline"
        else:
            icon.icon  = _ICON_RED
            icon.title = "Guppy — API offline"

        # Rebuild menu so ●/○ dots and enabled states reflect current status.
        icon.menu = _build_menu()

        time.sleep(30)


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    if not _api_alive():
        _start_api()

    # Seed initial model status before first menu build
    for key, cfg in _MODELS.items():
        _model_status[key] = _model_alive(cfg["port"])

    initial_icon  = _ICON_YELLOW if not _api_alive() else _ICON_GREEN
    initial_title = "Guppy — starting…" if not _api_alive() else "Guppy — running"

    icon = pystray.Icon(
        name="guppy",
        icon=initial_icon,
        title=initial_title,
        menu=_build_menu(),
    )

    t = threading.Thread(target=_monitor, args=(icon,), daemon=True)
    t.start()

    icon.run()


if __name__ == "__main__":
    main()
