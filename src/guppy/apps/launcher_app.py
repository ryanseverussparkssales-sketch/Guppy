"""Launcher app — starts the API server and opens the web UI in a browser.

Replaces the old Qt launcher stack. The primary surface is the web UI
at http://localhost:8081. This module handles boot: starts the API server
if it isn't already running, then opens the browser.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_VENV_PYTHON = _ROOT / ".venv" / "Scripts" / "python.exe"
_PYTHON = str(_VENV_PYTHON) if _VENV_PYTHON.exists() else sys.executable

_PORT = int(os.environ.get("GUPPY_API_PORT", "8081"))
_HEALTH_URL = f"http://127.0.0.1:{_PORT}/health"
_APP_URL = f"http://127.0.0.1:{_PORT}/index.html"

_BROWSER_CANDIDATES = [
    os.path.join(os.environ.get("ProgramFiles", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
    os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
    os.path.join(os.environ.get("ProgramFiles", ""), "Google", "Chrome", "Application", "chrome.exe"),
    os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
]


def _api_ready() -> bool:
    try:
        with urllib.request.urlopen(_HEALTH_URL, timeout=1) as r:
            return r.status < 500
    except Exception:
        return False


def _start_api() -> None:
    if _api_ready():
        return
    launch = _ROOT / "src" / "guppy" / "cli" / "launch.py"
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
    subprocess.Popen(
        [_PYTHON, str(launch), "api"],
        cwd=str(_ROOT),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )
    for _ in range(30):
        time.sleep(0.5)
        if _api_ready():
            return


def _open_browser() -> None:
    browser = next((b for b in _BROWSER_CANDIDATES if os.path.isfile(b)), None)
    if browser:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
        subprocess.Popen(
            [browser, f"--app={_APP_URL}", "--window-size=1400,900", "--window-position=60,40"],
            creationflags=flags,
        )
    else:
        import webbrowser
        webbrowser.open(_APP_URL)


def main() -> int:
    _start_api()
    _open_browser()
    return 0
