"""Service definitions for the Guppy launcher platform.

Each entry describes one manageable service:
  type "managed"  — we start/stop/restart it via subprocess
  type "external" — we probe health only (e.g. LM Studio, Ollama)
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]   # project root
_npm = "npm.cmd" if sys.platform == "win32" else "npm"
_py  = str(ROOT / ".venv" / "Scripts" / "python.exe") if sys.platform == "win32" else sys.executable
if not Path(_py).exists():
    _py = sys.executable

SERVICES: dict[str, dict] = {
    "api": {
        "label":       "Guppy API",
        "description": "FastAPI backend — auth, chat, queue, providers",
        "cmd":         [_py, str(ROOT / "guppy_api.py")],
        "cwd":         str(ROOT),
        "port":        8081,
        "health_url":  "http://127.0.0.1:8081/status",
        "log_file":    str(ROOT / "runtime" / "_lp_api.log"),
        "type":        "managed",
        "icon":        "server",
        "env_keys":    ["GUPPY_JWT_SECRET", "GUPPY_DEV_MODE", "GUPPY_LOCAL_RUNTIME_BACKEND"],
    },
    "web-dev": {
        "label":       "Web UI (Dev)",
        "description": "Vite dev server — hot-reload React frontend on :3000",
        "cmd":         [_npm, "run", "dev"],
        "cwd":         str(ROOT / "web"),
        "port":        3000,
        "health_url":  "http://127.0.0.1:3000/",
        "log_file":    str(ROOT / "runtime" / "_lp_webui.log"),
        "type":        "managed",
        "icon":        "globe",
        "env_keys":    [],
    },
    "fishbowl": {
        "label":       "Fishbowl",
        "description": "Floating chat overlay — Ctrl+Space to toggle",
        "cmd":         [_py, str(ROOT / "guppy_fishbowl.py")],
        "cwd":         str(ROOT),
        "port":        None,
        "health_url":  None,
        "log_file":    str(ROOT / "runtime" / "_lp_fishbowl.log"),
        "type":        "managed",
        "icon":        "layers",
        "env_keys":    [],
    },
    "qt-launcher": {
        "label":       "Qt Launcher",
        "description": "Desktop launcher UI — PySide6 native app",
        "cmd":         [_py, str(ROOT / "guppy_launcher.py")],
        "cwd":         str(ROOT),
        "port":        None,
        "health_url":  None,
        "log_file":    str(ROOT / "runtime" / "_lp_qt.log"),
        "type":        "managed",
        "icon":        "monitor",
        "env_keys":    [],
    },
    "lmstudio": {
        "label":       "LM Studio",
        "description": "Primary local inference backend — probe only",
        "cmd":         None,
        "cwd":         None,
        "port":        1234,
        "health_url":  "http://127.0.0.1:1234/api/v1/models",
        "log_file":    None,
        "type":        "external",
        "icon":        "cpu",
        "env_keys":    ["GUPPY_LMSTUDIO_API_KEY"],
    },
    "ollama": {
        "label":       "Ollama",
        "description": "Fallback local inference backend",
        "cmd":         ["ollama", "serve"],
        "cwd":         None,
        "port":        11434,
        "health_url":  "http://127.0.0.1:11434/api/tags",
        "log_file":    str(ROOT / "runtime" / "_lp_ollama.log"),
        "type":        "external",
        "icon":        "zap",
        "env_keys":    [],
    },
}
