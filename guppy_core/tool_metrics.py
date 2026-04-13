"""
guppy_core/tool_metrics.py
Tool circuit-breaker and metrics helpers.
Import from here instead of guppy_core directly when you only need metrics.
"""
from __future__ import annotations

import time

from guppy_core.debug_flags import (
    _TOOL_GUARD_LOCK,
    _TOOL_GUARDS,
    _TOOL_METRICS,
    TOOL_EXEC_TIMEOUT_SECONDS,
    TOOL_CIRCUIT_FAIL_THRESHOLD,
    TOOL_CIRCUIT_COOLDOWN_SECONDS,
)


def _tool_metric(name: str) -> dict:
    bucket = _TOOL_METRICS["per_tool"].get(name)
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
        _TOOL_METRICS["per_tool"][name] = bucket
    return bucket


def _record_tool_call(name: str, elapsed_ms: float, state: str, last_error: str = "") -> None:
    with _TOOL_GUARD_LOCK:
        _TOOL_METRICS["calls"] += 1
        _TOOL_METRICS["total_ms"] += elapsed_ms
        bucket = _tool_metric(name)
        bucket["calls"] += 1
        bucket["total_ms"] += elapsed_ms

        if state == "success":
            _TOOL_METRICS["success"] += 1
            bucket["success"] += 1
            bucket["last_error"] = ""
        elif state == "timeout":
            _TOOL_METRICS["timeouts"] += 1
            bucket["timeouts"] += 1
            if last_error:
                bucket["last_error"] = last_error
        elif state == "blocked":
            _TOOL_METRICS["blocked"] += 1
            bucket["blocked"] += 1
            if last_error:
                bucket["last_error"] = last_error
        else:
            _TOOL_METRICS["errors"] += 1
            bucket["errors"] += 1
            if last_error:
                bucket["last_error"] = last_error


def _tool_guard(name: str) -> dict:
    guard = _TOOL_GUARDS.get(name)
    if guard is None:
        guard = {"failures": 0, "open_until": 0.0, "last_error": ""}
        _TOOL_GUARDS[name] = guard
    return guard


def _is_tool_blocked(name: str) -> tuple[bool, str]:
    now = time.time()
    with _TOOL_GUARD_LOCK:
        guard = _tool_guard(name)
        open_until = guard.get("open_until", 0.0)
        if open_until > now:
            wait_seconds = max(1, int(open_until - now))
            msg = guard.get("last_error", "Tool temporarily unavailable.")
            return True, f"Tool {name} is cooling down ({wait_seconds}s): {msg}"
        return False, ""


def _mark_tool_success(name: str) -> None:
    with _TOOL_GUARD_LOCK:
        guard = _tool_guard(name)
        guard["failures"] = 0
        guard["open_until"] = 0.0
        guard["last_error"] = ""


def _mark_tool_failure(name: str, error_msg: str) -> None:
    with _TOOL_GUARD_LOCK:
        guard = _tool_guard(name)
        guard["failures"] = int(guard.get("failures", 0)) + 1
        guard["last_error"] = error_msg
        if guard["failures"] >= TOOL_CIRCUIT_FAIL_THRESHOLD:
            guard["open_until"] = time.time() + TOOL_CIRCUIT_COOLDOWN_SECONDS


def get_tool_health_snapshot() -> dict:
    """Return tool-runner metrics and circuit-breaker state for diagnostics."""
    with _TOOL_GUARD_LOCK:
        per_tool = {}
        for name, metric in _TOOL_METRICS["per_tool"].items():
            avg_ms = (metric["total_ms"] / metric["calls"]) if metric["calls"] else 0.0
            guard = _TOOL_GUARDS.get(name, {"failures": 0, "open_until": 0.0, "last_error": ""})
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

        total_calls = _TOOL_METRICS["calls"]
        avg_ms = (_TOOL_METRICS["total_ms"] / total_calls) if total_calls else 0.0
        return {
            "calls": total_calls,
            "success": _TOOL_METRICS["success"],
            "errors": _TOOL_METRICS["errors"],
            "timeouts": _TOOL_METRICS["timeouts"],
            "blocked": _TOOL_METRICS["blocked"],
            "avg_ms": round(avg_ms, 2),
            "timeout_seconds": TOOL_EXEC_TIMEOUT_SECONDS,
            "circuit_fail_threshold": TOOL_CIRCUIT_FAIL_THRESHOLD,
            "circuit_cooldown_seconds": TOOL_CIRCUIT_COOLDOWN_SECONDS,
            "per_tool": per_tool,
        }
