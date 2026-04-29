"""Guppy Web UI — PyInstaller entry point.

Starts the FastAPI server on localhost and opens the web UI in a browser
app-mode window (Edge → Chrome → system default). Run directly with Python
for dev use; PyInstaller bundles this into dist/GuppyWebUI/GuppyWebUI.exe.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path


PORT = int(os.environ.get("GUPPY_API_PORT", "8081"))
_URL = f"http://127.0.0.1:{PORT}/index.html"
_HEALTH = f"http://127.0.0.1:{PORT}/health"

_BROWSER_CANDIDATES = [
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def _load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = val.strip()


def _setup_env() -> None:
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
    _load_env_file(base / ".env")
    _load_env_file(base / ".env.local")

    os.environ.setdefault("GUPPY_JWT_SECRET", "dev-secret-key-change-in-production")
    os.environ.setdefault("TURNSTILE_SECRET", "dev-turnstile-secret")
    os.environ.setdefault("GUPPY_DEFAULT_MODE", "local")
    os.environ.setdefault("GUPPY_LOCAL_RUNTIME_BACKEND", "ollama")
    os.environ.setdefault("GUPPY_ROUTER_MODE", "auto")
    os.environ.setdefault("GUPPY_TOOL_BUDGET", "6")
    os.environ.setdefault("GUPPY_API_OWNS_DAEMON", "0")
    os.environ.setdefault("GUPPY_API_RELOAD", "0")
    os.environ.setdefault("OLLAMA_MODEL", "guppy")
    os.environ.setdefault("OLLAMA_FAST_MODEL", "guppy-fast")
    os.environ.setdefault("OLLAMA_TEACH_MODEL", "guppy-teach")
    os.environ.setdefault("OLLAMA_CODE_MODEL", "guppy-code")
    os.environ.setdefault("GUPPY_WHISPER_MODEL", "large-v3")
    os.environ.setdefault("WEATHER_UNITS", "imperial")


def _open_browser_when_ready() -> None:
    deadline = time.monotonic() + 25.0
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(_HEALTH, timeout=1) as r:
                if r.status < 500:
                    break
        except Exception:
            pass
        time.sleep(0.5)

    browser = next((p for p in _BROWSER_CANDIDATES if Path(p).exists()), None)
    if browser:
        subprocess.Popen(
            [browser, f"--app={_URL}", "--window-size=1280,820", "--window-position=80,60"],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    else:
        import webbrowser
        webbrowser.open(_URL)


def main() -> None:
    _setup_env()

    # Ensure project root (MEIPASS in frozen mode) is on sys.path so
    # src.* and utils.* imports resolve correctly.
    root = getattr(sys, "_MEIPASS", None) or str(Path(__file__).parent)
    if root not in sys.path:
        sys.path.insert(0, root)

    threading.Thread(target=_open_browser_when_ready, daemon=True).start()

    import uvicorn
    from src.guppy.api.server import app  # noqa: PLC0415

    print(f"[guppy] Starting server on http://127.0.0.1:{PORT}")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
