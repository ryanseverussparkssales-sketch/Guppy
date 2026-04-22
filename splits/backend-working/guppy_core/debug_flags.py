"""
guppy_core/debug_flags.py
Runtime constants, circuit-breaker config, and thread pool.
Import from here instead of guppy_core directly when you only need these values.
"""
from __future__ import annotations

import os
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor

SAFE_MODE = False
TOOL_LOG: deque = deque(maxlen=50)

TOOL_EXEC_TIMEOUT_SECONDS    = int(os.environ.get("GUPPY_TOOL_TIMEOUT_SECONDS",   "90"))
TOOL_CIRCUIT_FAIL_THRESHOLD  = int(os.environ.get("GUPPY_TOOL_FAIL_THRESHOLD",    "3"))
TOOL_CIRCUIT_COOLDOWN_SECONDS = int(os.environ.get("GUPPY_TOOL_COOLDOWN_SECONDS", "30"))
TOOL_MAX_OUTPUT_CHARS        = int(os.environ.get("GUPPY_TOOL_MAX_OUTPUT_CHARS", "2000"))

_TOOL_EXECUTOR   = ThreadPoolExecutor(max_workers=max(4, (os.cpu_count() or 4)))
_TOOL_GUARD_LOCK = threading.RLock()
_TOOL_GUARDS: dict[str, dict] = {}
_TOOL_METRICS: dict = {
    "calls": 0,
    "success": 0,
    "errors": 0,
    "timeouts": 0,
    "blocked": 0,
    "total_ms": 0.0,
    "per_tool": {},
}
