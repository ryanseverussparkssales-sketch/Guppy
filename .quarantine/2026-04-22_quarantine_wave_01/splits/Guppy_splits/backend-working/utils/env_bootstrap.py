"""Minimal .env loader for local app entrypoints.

Keeps startup independent from external dotenv dependency.
Only fills unset environment variables unless override=True.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_env_file(env_path: str | None = None, override: bool = False) -> int:
    path = Path(env_path) if env_path else (Path(__file__).resolve().parent.parent / ".env")
    if not path.exists():
        return 0

    loaded = 0
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        val = value.strip().strip('"').strip("'")
        if not override and os.environ.get(key):
            continue
        os.environ[key] = val
        loaded += 1
    return loaded
