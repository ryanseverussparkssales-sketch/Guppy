"""
guppy_core/network_utils.py
Lightweight network health checks — internet reachability and Ollama availability.
No heavy deps; safe to import early in startup.
"""
from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request


def is_online() -> bool:
    """Return True if we can reach the internet (DNS via 8.8.8.8:53)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect(("8.8.8.8", 53))
        s.close()
        return True
    except OSError:
        return False


def check_ollama(model: str) -> tuple[bool, str]:
    """Check whether Ollama is running and `model` is available.

    Returns (ok: bool, error_msg: str).  error_msg is empty when ok is True.
    """
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3) as r:
            data = json.loads(r.read())
        names = [m.get("name", "") for m in data.get("models", [])]
        model_base = model.split(":")[0]
        if any(n == model or n.split(":")[0] == model_base for n in names):
            return True, ""
        available = ", ".join(names) if names else "none"
        return False, (
            f"Ollama is running but the '{model}' model is not available.\n"
            f"Available: {available}\n"
            f"Run:  ollama pull {model}"
        )
    except urllib.error.URLError:
        return False, (
            "Ollama is not running.\n"
            "Start it with:  ollama serve\n"
            "Or switch to Claude mode with the button above."
        )
    except Exception as e:
        return False, f"Could not contact Ollama: {e}"
