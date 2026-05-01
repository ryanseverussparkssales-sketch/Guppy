"""Track 2 - Local base-model first-success readiness (PL-C5).

Defines explicit acceptance criteria for "first local model works".
All checks are non-blocking - exceptions are caught and returned as False.
No subprocess call blocks for more than 3 seconds.
Safe to import and call in any environment (CI, no Ollama, no runtime running).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from utils.personalization_config import load_provider_registry

_REPO_ROOT = Path(__file__).resolve().parents[3]
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
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=_TIMEOUT)
        return result.returncode == 0
    except Exception:
        return False


def _ollama_model_pulled() -> bool:
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=_TIMEOUT)
        if result.returncode != 0:
            return False
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return len(lines) >= 2
    except Exception:
        return False


def _lemonade_cli() -> bool:
    try:
        return shutil.which("lemonade") is not None
    except Exception:
        return False


def _lemonade_runtime() -> bool:
    for url in (
        "http://127.0.0.1:13305/api/v1/models",
        "http://localhost:13305/api/v1/models",
        "http://127.0.0.1:13305/health",
        "http://localhost:13305/health",
    ):
        if _http_ok(url):
            return True
    return False


def _runtime_hub_alive() -> bool:
    try:
        lock = _REPO_ROOT / "runtime" / "hub.lock"
        return lock.exists() and (time.time() - lock.stat().st_mtime) < 60
    except Exception:
        return False


def _http_ok(url: str) -> bool:
    try:
        request = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            return int(getattr(response, "status", 500) or 500) < 500
    except Exception:
        return False


def _lmstudio_runtime() -> bool:
    return _http_ok("http://127.0.0.1:1234/v1/models")


def _local_harness_runtime() -> bool:
    for url in (
        "http://127.0.0.1:8001/health",
        "http://127.0.0.1:8001/status",
        "http://127.0.0.1:8001/v1/models",
    ):
        if _http_ok(url):
            return True
    return False


def _declared_local_runtime_ids() -> list[str]:
    try:
        registry = load_provider_registry()
    except Exception:
        registry = {}
    providers = registry.get("providers", []) if isinstance(registry, dict) else []
    declared: list[str] = []
    for item in providers:
        if not isinstance(item, dict):
            continue
        provider_id = str(item.get("id", "") or "").strip().lower()
        api_base = str(item.get("api_base", "") or "").strip().lower()
        enabled = bool(item.get("enabled", False))
        if enabled and provider_id and api_base.startswith("http://127.0.0.1"):
            declared.append(provider_id)
    selected_backend = str(os.environ.get("GUPPY_LOCAL_RUNTIME_BACKEND", "") or "").strip().lower()
    if selected_backend == "lemonade":
        declared.append("lemonade_local")
    if declared:
        return list(dict.fromkeys(declared))
    return ["local", "lmstudio_local", "local_harness"]


LOCAL_MODEL_CHECKS: list[LocalModelCheck] = [
    LocalModelCheck("ollama_cli", "Ollama CLI is on PATH", False, _ollama_cli),
    LocalModelCheck("ollama_daemon", "Ollama daemon responds within 3 seconds", False, _ollama_daemon),
    LocalModelCheck("ollama_model_pulled", "At least one model listed by 'ollama list'", False, _ollama_model_pulled),
    LocalModelCheck("lemonade_cli", "Lemonade CLI on PATH - optional, absence reported not failed", True, _lemonade_cli),
    LocalModelCheck("lemonade_runtime", "Lemonade local runtime answers on its local models or health endpoint", True, _lemonade_runtime),
    LocalModelCheck("lmstudio_runtime", "LM Studio local runtime answers on http://127.0.0.1:1234/v1/models", True, _lmstudio_runtime),
    LocalModelCheck("local_harness_runtime", "Local harness answers on its local health or models endpoint", True, _local_harness_runtime),
    LocalModelCheck("runtime_hub_alive", "runtime/hub.lock updated within 60 seconds", True, _runtime_hub_alive),
]


def run_local_model_readiness() -> dict[str, object]:
    """Run all Track 2 local model readiness checks."""
    results_by_name: dict[str, bool] = {}
    passed: list[str] = []
    failed: list[str] = []
    optional_absent: list[str] = []
    for check in LOCAL_MODEL_CHECKS:
        try:
            ok = check.check_fn()
        except Exception:
            ok = False
        results_by_name[check.name] = ok
        if ok:
            passed.append(check.name)
        else:
            optional_absent.append(check.name)
    ready_runtimes: list[str] = []
    if all(results_by_name.get(name, False) for name in ("ollama_cli", "ollama_daemon", "ollama_model_pulled")):
        ready_runtimes.append("ollama")
    if results_by_name.get("lemonade_runtime", False):
        ready_runtimes.append("lemonade")
    if results_by_name.get("lmstudio_runtime", False):
        ready_runtimes.append("lmstudio")
    if results_by_name.get("local_harness_runtime", False):
        ready_runtimes.append("local_harness")

    if not ready_runtimes:
        failed.append("ready_local_runtime")

    declared_runtime_ids = _declared_local_runtime_ids()
    declared_runtime_labels = {
        "local": "ollama",
        "lemonade_local": "lemonade",
        "lemonade": "lemonade",
        "lmstudio_local": "lmstudio",
        "local_harness": "local_harness",
    }
    declared_routes = [
        declared_runtime_labels.get(item, item)
        for item in declared_runtime_ids
    ]
    declared_but_unavailable = [
        route
        for route in declared_routes
        if route in {"ollama", "lemonade", "lmstudio", "local_harness"} and route not in ready_runtimes
    ]

    total = len(LOCAL_MODEL_CHECKS)
    summary = f"Track 2 local model readiness: {len(passed)}/{total} passed"
    if failed:
        summary += f" - required failures: {', '.join(failed)}"
    if optional_absent:
        summary += f" - optional absent: {', '.join(optional_absent)}"
    if ready_runtimes:
        summary += f" - ready via: {', '.join(ready_runtimes)}"
    elif declared_routes:
        summary += f" - declared local routes checked: {', '.join(declared_routes)}"
    return {
        "passed": passed,
        "failed": failed,
        "optional_absent": optional_absent,
        "ready_runtimes": ready_runtimes,
        "declared_routes": declared_routes,
        "declared_but_unavailable": declared_but_unavailable,
        "summary": summary,
    }
