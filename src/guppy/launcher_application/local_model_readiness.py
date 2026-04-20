"""Track 2 — Local base-model first-success readiness (PL-C5).

Defines explicit acceptance criteria for "first local model works".
All checks are non-blocking — exceptions are caught and returned as False.
No subprocess call blocks for more than 3 seconds.
Safe to import and call in any environment (CI, no Ollama, no runtime running).
"""

from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

_REPO_ROOT = Path(__file__).resolve().parents[4]
_TIMEOUT = 3


@dataclass(frozen=True, slots=True)
class LocalModelCheck:
    name: str
    description: str
    optional: bool
    check_fn: Callable[[], bool]


def _ollama_cli() -> bool:
    try:
        return shutil.which("ollama") is not None
    except Exception:
        return False


def _ollama_daemon() -> bool:
    try:
        r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=_TIMEOUT)
        return r.returncode == 0
    except Exception:
        return False


def _ollama_model_pulled() -> bool:
    try:
        r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=_TIMEOUT)
        if r.returncode != 0:
            return False
        lines = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
        return len(lines) >= 2  # header + at least one model row
    except Exception:
        return False


def _lemonade_cli() -> bool:
    try:
        return shutil.which("lemonade") is not None
    except Exception:
        return False


def _runtime_hub_alive() -> bool:
    try:
        lock = _REPO_ROOT / "runtime" / "hub.lock"
        return lock.exists() and (time.time() - lock.stat().st_mtime) < 60
    except Exception:
        return False


LOCAL_MODEL_CHECKS: list[LocalModelCheck] = [
    LocalModelCheck("ollama_cli", "Ollama CLI is on PATH", False, _ollama_cli),
    LocalModelCheck("ollama_daemon", "Ollama daemon responds within 3 seconds", False, _ollama_daemon),
    LocalModelCheck("ollama_model_pulled", "At least one model listed by 'ollama list'", False, _ollama_model_pulled),
    LocalModelCheck("lemonade_cli", "Lemonade CLI on PATH — optional, absence reported not failed", True, _lemonade_cli),
    LocalModelCheck("runtime_hub_alive", "runtime/hub.lock updated within 60 seconds", True, _runtime_hub_alive),
]


def run_local_model_readiness() -> dict[str, object]:
    """Run all Track 2 local model readiness checks.

    Returns a dict with keys:
      - passed: list of check names that passed
      - failed: list of required check names that failed
      - optional_absent: list of optional check names that failed
      - summary: human-readable one-liner
    """
    passed: list[str] = []
    failed: list[str] = []
    optional_absent: list[str] = []
    for check in LOCAL_MODEL_CHECKS:
        try:
            ok = check.check_fn()
        except Exception:
            ok = False
        if ok:
            passed.append(check.name)
        elif check.optional:
            optional_absent.append(check.name)
        else:
            failed.append(check.name)
    total = len(LOCAL_MODEL_CHECKS)
    summary = f"Track 2 local model readiness: {len(passed)}/{total} passed"
    if failed:
        summary += f" — required failures: {', '.join(failed)}"
    if optional_absent:
        summary += f" — optional absent: {', '.join(optional_absent)}"
    return {"passed": passed, "failed": failed, "optional_absent": optional_absent, "summary": summary}
