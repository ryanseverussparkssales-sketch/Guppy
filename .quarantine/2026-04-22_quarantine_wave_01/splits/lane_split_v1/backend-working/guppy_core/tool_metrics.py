"""
guppy_core/tool_metrics.py
Tool circuit-breaker and metrics helpers.
Import from here instead of guppy_core directly when you only need metrics.
"""
from __future__ import annotations

import logging
import threading
import time

from guppy_core import debug_flags as _debug_flags
from guppy_core.debug_flags import (
    TOOL_EXEC_TIMEOUT_SECONDS,
    TOOL_CIRCUIT_FAIL_THRESHOLD,
    TOOL_CIRCUIT_COOLDOWN_SECONDS,
)


logger = logging.getLogger(__name__)

_FALLBACK_TOOL_GUARD_LOCK = threading.RLock()
_FALLBACK_TOOL_GUARDS: dict[str, dict] = {}
_FALLBACK_TOOL_METRICS: dict = {
    "calls": 0,
    "success": 0,
    "errors": 0,
    "timeouts": 0,
    "blocked": 0,
    "total_ms": 0.0,
    "per_tool": {},
}
_STATE_WARNING_EMITTED = False


def _shared_metrics_state() -> tuple[threading.RLock, dict[str, dict], dict]:
    global _STATE_WARNING_EMITTED

    lock = getattr(_debug_flags, "_TOOL_GUARD_LOCK", None)
    guards = getattr(_debug_flags, "_TOOL_GUARDS", None)
    metrics = getattr(_debug_flags, "_TOOL_METRICS", None)
    degraded = False

    if lock is None:
        lock = _FALLBACK_TOOL_GUARD_LOCK
        degraded = True
    if not isinstance(guards, dict):
        guards = _FALLBACK_TOOL_GUARDS
        degraded = True
    if not isinstance(metrics, dict):
        metrics = _FALLBACK_TOOL_METRICS
        degraded = True

    metrics.setdefault("calls", 0)
    metrics.setdefault("success", 0)
    metrics.setdefault("errors", 0)
    metrics.setdefault("timeouts", 0)
    metrics.setdefault("blocked", 0)
    metrics.setdefault("total_ms", 0.0)
    metrics.setdefault("per_tool", {})

    if degraded and not _STATE_WARNING_EMITTED:
        logger.warning("Tool metrics state unavailable; using fallback in-process state")
        _STATE_WARNING_EMITTED = True

    return lock, guards, metrics


def _tool_metric(name: str, metrics: dict | None = None) -> dict:
    metrics_map = metrics if metrics is not None else _shared_metrics_state()[2]
    bucket = metrics_map["per_tool"].get(name)
    if bucket is None:
        bucket = {
            "calls": 0,
            "success": 0,
            "errors": 0,
            "timeouts": 0,
            "blocked": 0,
            "total_ms": 0.0,
            "last_error": "",
        }
        metrics_map["per_tool"][name] = bucket
    return bucket


def _record_tool_call(name: str, elapsed_ms: float, state: str, last_error: str = "") -> None:
    lock, _guards, metrics = _shared_metrics_state()
    with lock:
        metrics["calls"] += 1
        metrics["total_ms"] += elapsed_ms
        bucket = _tool_metric(name, metrics)
        bucket["calls"] += 1
        bucket["total_ms"] += elapsed_ms

        if state == "success":
            metrics["success"] += 1
            bucket["success"] += 1
            bucket["last_error"] = ""
        elif state == "timeout":
            metrics["timeouts"] += 1
            bucket["timeouts"] += 1
            if last_error:
                bucket["last_error"] = last_error
        elif state == "blocked":
            metrics["blocked"] += 1
            bucket["blocked"] += 1
            if last_error:
                bucket["last_error"] = last_error
        else:
            metrics["errors"] += 1
            bucket["errors"] += 1
            if last_error:
                bucket["last_error"] = last_error


def _tool_guard(name: str, guards: dict | None = None) -> dict:
    guard_map = guards if guards is not None else _shared_metrics_state()[1]
    guard = guard_map.get(name)
    if guard is None:
        guard = {"failures": 0, "open_until": 0.0, "last_error": ""}
        guard_map[name] = guard
    return guard


def _is_tool_blocked(name: str) -> tuple[bool, str]:
    now = time.time()
    lock, guards, _metrics = _shared_metrics_state()
    with lock:
        guard = _tool_guard(name, guards)
        open_until = guard.get("open_until", 0.0)
        if open_until > now:
            wait_seconds = max(1, int(open_until - now))
            msg = guard.get("last_error", "Tool temporarily unavailable.")
            return True, f"Tool {name} is cooling down ({wait_seconds}s): {msg}"
        return False, ""


def _mark_tool_success(name: str) -> None:
    lock, guards, _metrics = _shared_metrics_state()
    with lock:
        guard = _tool_guard(name, guards)
        guard["failures"] = 0
        guard["open_until"] = 0.0
        guard["last_error"] = ""


def _mark_tool_failure(name: str, error_msg: str) -> None:
    lock, guards, _metrics = _shared_metrics_state()
    with lock:
        guard = _tool_guard(name, guards)
        guard["failures"] = int(guard.get("failures", 0)) + 1
        guard["last_error"] = error_msg
        if guard["failures"] >= TOOL_CIRCUIT_FAIL_THRESHOLD:
            guard["open_until"] = time.time() + TOOL_CIRCUIT_COOLDOWN_SECONDS


def get_tool_health_snapshot() -> dict:
    """Return tool-runner metrics and circuit-breaker state for diagnostics."""
    lock, guards, metrics = _shared_metrics_state()
    with lock:
        per_tool = {}
        for name, metric in metrics["per_tool"].items():
            avg_ms = (metric["total_ms"] / metric["calls"]) if metric["calls"] else 0.0
            guard = guards.get(name, {"failures": 0, "open_until": 0.0, "last_error": ""})
            per_tool[name] = {
                "calls": metric["calls"],
                "success": metric["success"],
                "errors": metric["errors"],
                "timeouts": metric["timeouts"],
                "blocked": metric["blocked"],
                "avg_ms": round(avg_ms, 2),
                "failures": guard.get("failures", 0),
                "circuit_open_until": guard.get("open_until", 0.0),
                "last_error": guard.get("last_error", ""),
            }

        total_calls = metrics["calls"]
        avg_ms = (metrics["total_ms"] / total_calls) if total_calls else 0.0
        return {
            "calls": total_calls,
            "success": metrics["success"],
            "errors": metrics["errors"],
            "timeouts": metrics["timeouts"],
            "blocked": metrics["blocked"],
            "avg_ms": round(avg_ms, 2),
            "timeout_seconds": TOOL_EXEC_TIMEOUT_SECONDS,
            "circuit_fail_threshold": TOOL_CIRCUIT_FAIL_THRESHOLD,
            "circuit_cooldown_seconds": TOOL_CIRCUIT_COOLDOWN_SECONDS,
            "per_tool": per_tool,
        }
