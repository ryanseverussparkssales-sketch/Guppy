"""guppy.py — single entry point.

Starts the API server (port 8081) and opens the Launchpad in the browser.
Replaces the assorted .bat / .ps1 / .py launchers in bin/.

Usage:
    python guppy.py [--no-browser]
"""
from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT     = Path(__file__).resolve().parent
API_PORT = int(os.environ.get("GUPPY_API_PORT", "8081"))
UI_URL   = f"http://127.0.0.1:{API_PORT}/launchpad"
API_SCRIPT = ROOT / "guppy_api.py"


def _find_python() -> str:
    """Return the venv python if present, else the running interpreter."""
    for candidate in (
        ROOT / ".venv" / "Scripts" / "python.exe",   # Windows venv
        ROOT / ".venv" / "bin" / "python",            # POSIX venv
    ):
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def _wait_for_api(port: int, timeout: float = 60.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _port_open(port):
            return True
        time.sleep(0.5)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Guppy launcher")
    parser.add_argument("--no-browser", action="store_true", help="Start API but do not open browser")
    args = parser.parse_args()

    if _port_open(API_PORT):
        print(f"[guppy] API already running on port {API_PORT}")
    else:
        python = _find_python()
        print(f"[guppy] Starting API server ({API_SCRIPT.name})…")
        subprocess.Popen([python, str(API_SCRIPT)], cwd=str(ROOT))

        print(f"[guppy] Waiting for API on port {API_PORT}…", end="", flush=True)
        if not _wait_for_api(API_PORT):
            print("\n[guppy] ERROR: API did not start within 60 s. Check logs.")
            return 1
        print(" ready.")

    if not args.no_browser:
        print(f"[guppy] Opening {UI_URL}")
        webbrowser.open(UI_URL)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
