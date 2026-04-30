"""
guppy_core/network_utils.py
Lightweight network health checks — internet reachability and llamacpp backend availability.
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


def check_llamacpp(port: int) -> tuple[bool, str]:
    """Check whether a llamacpp server is running on the given port.

    Pings /v1/models (OpenAI-compat endpoint).
    Returns (ok: bool, error_msg: str).  error_msg is empty when ok is True.
    """
    url = f"http://localhost:{port}/v1/models"
    try:
        with urllib.request.urlopen(url, timeout=3) as r:
            data = json.loads(r.read())
        models = [m.get("id", "") for m in data.get("data", [])]
        model_str = ", ".join(models) if models else "unknown"
        return True, f"llamacpp at port {port} OK — models: {model_str}"
    except urllib.error.URLError:
        return False, (
            f"llamacpp server not running on port {port}.\n"
            "Start it with the appropriate bat file in bin/."
        )
    except Exception as e:
        return False, f"Could not contact llamacpp at port {port}: {e}"
