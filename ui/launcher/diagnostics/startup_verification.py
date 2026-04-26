"""
startup_verification.py

Lane: TR54-D3
Responsibilities:
  - Run a checklist before the launcher UI appears
  - Classify each check as PASS / WARN / FAIL
  - Return a structured report; callers decide how to surface failures
  - Never raise — every check is wrapped so one bad import can't abort the rest
"""

from __future__ import annotations

import importlib
import logging
import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger("launcher.diagnostics.startup_verification")

_REQUIRED_STDLIB = ["json", "logging", "pathlib", "sqlite3", "threading", "time", "urllib.request"]
_REQUIRED_APP = [
    "src.guppy.launcher_application",
    "src.guppy.experience_config",
    "src.guppy.inference.router",
]
_MIN_PYTHON = (3, 12)


class CheckStatus(Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class CheckResult:
    name: str
    status: CheckStatus
    detail: str
    recovery: str = ""


@dataclass
class StartupVerificationReport:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.status != CheckStatus.FAIL for c in self.checks)

    @property
    def has_warnings(self) -> bool:
        return any(c.status == CheckStatus.WARN for c in self.checks)

    def failures(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status == CheckStatus.FAIL]

    def warnings(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status == CheckStatus.WARN]

    def summary(self) -> str:
        total = len(self.checks)
        passed = sum(1 for c in self.checks if c.status == CheckStatus.PASS)
        warned = sum(1 for c in self.checks if c.status == CheckStatus.WARN)
        failed = sum(1 for c in self.checks if c.status == CheckStatus.FAIL)
        parts = [f"{passed}/{total} checks passed"]
        if warned:
            parts.append(f"{warned} warning{'s' if warned != 1 else ''}")
        if failed:
            parts.append(f"{failed} failure{'s' if failed != 1 else ''}")
        return " · ".join(parts)

    def as_dict(self) -> dict:
        return {
            "passed": self.passed,
            "summary": self.summary(),
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "detail": c.detail,
                    "recovery": c.recovery,
                }
                for c in self.checks
            ],
        }


def _check_python_version() -> CheckResult:
    version = sys.version_info
    if version >= _MIN_PYTHON:
        return CheckResult(
            "python_version",
            CheckStatus.PASS,
            f"Python {version.major}.{version.minor}.{version.micro}",
        )
    return CheckResult(
        "python_version",
        CheckStatus.FAIL,
        f"Python {version.major}.{version.minor} — minimum required is {_MIN_PYTHON[0]}.{_MIN_PYTHON[1]}",
        recovery=f"Install Python {_MIN_PYTHON[0]}.{_MIN_PYTHON[1]}+ and relaunch.",
    )


def _check_required_modules() -> CheckResult:
    missing = []
    for mod in _REQUIRED_STDLIB:
        try:
            importlib.import_module(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        return CheckResult(
            "required_stdlib",
            CheckStatus.FAIL,
            f"Missing standard library modules: {', '.join(missing)}",
            recovery="Your Python installation may be incomplete. Reinstall Python.",
        )
    return CheckResult("required_stdlib", CheckStatus.PASS, "All standard library modules importable")


def _check_app_modules() -> CheckResult:
    missing = []
    for mod in _REQUIRED_APP:
        try:
            importlib.import_module(mod)
        except ImportError as exc:
            missing.append(f"{mod} ({exc})")
        except Exception:
            pass
    if missing:
        return CheckResult(
            "app_modules",
            CheckStatus.WARN,
            f"Some app modules could not be imported: {'; '.join(missing)}",
            recovery="Run bootstrap_venv.ps1 -Dev to restore the virtual environment.",
        )
    return CheckResult("app_modules", CheckStatus.PASS, "Core app modules importable")


def _check_qt_available() -> CheckResult:
    try:
        importlib.import_module("PySide6.QtWidgets")
        return CheckResult("qt_available", CheckStatus.PASS, "PySide6 available")
    except ImportError as exc:
        return CheckResult(
            "qt_available",
            CheckStatus.FAIL,
            f"PySide6 not importable: {exc}",
            recovery="Run: pip install PySide6",
        )


def _check_config_directory() -> CheckResult:
    config_dir = Path.home() / ".guppy"
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
        probe = config_dir / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return CheckResult("config_directory", CheckStatus.PASS, f"Config dir writable: {config_dir}")
    except OSError as exc:
        return CheckResult(
            "config_directory",
            CheckStatus.FAIL,
            f"Cannot write to config dir {config_dir}: {exc}",
            recovery=f"Check permissions on {config_dir} or HOME directory.",
        )


def _check_runtime_directory(root: Path) -> CheckResult:
    runtime_dir = root / "runtime"
    try:
        runtime_dir.mkdir(parents=True, exist_ok=True)
        probe = runtime_dir / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return CheckResult("runtime_directory", CheckStatus.PASS, f"Runtime dir writable: {runtime_dir}")
    except OSError as exc:
        return CheckResult(
            "runtime_directory",
            CheckStatus.FAIL,
            f"Cannot write to runtime dir {runtime_dir}: {exc}",
            recovery="Run the launcher from its install directory, or check folder permissions.",
        )


def _check_network_optional() -> CheckResult:
    import urllib.request
    try:
        urllib.request.urlopen("http://127.0.0.1:8081/", timeout=0.8)
        return CheckResult("api_reachable", CheckStatus.PASS, "Guppy API reachable on :8081")
    except Exception:
        return CheckResult(
            "api_reachable",
            CheckStatus.WARN,
            "Guppy API not yet reachable on :8081 — will attempt auto-start",
            recovery="The launcher will start the API automatically.",
        )


def run_startup_verification(
    root: Path,
    *,
    skip_network: bool = False,
) -> StartupVerificationReport:
    report = StartupVerificationReport()
    checks = [
        _check_python_version,
        _check_required_modules,
        _check_app_modules,
        _check_qt_available,
        _check_config_directory,
        lambda: _check_runtime_directory(root),
    ]
    if not skip_network:
        checks.append(_check_network_optional)

    for check_fn in checks:
        try:
            result = check_fn()
            report.checks.append(result)
            if result.status == CheckStatus.FAIL:
                logger.error("Boot check FAIL [%s]: %s", result.name, result.detail)
            elif result.status == CheckStatus.WARN:
                logger.warning("Boot check WARN [%s]: %s", result.name, result.detail)
            else:
                logger.debug("Boot check PASS [%s]", result.name)
        except Exception as exc:
            logger.exception("Boot check raised unexpectedly: %s", exc)
            report.checks.append(
                CheckResult(
                    "unexpected_error",
                    CheckStatus.FAIL,
                    f"Unexpected error during boot check: {exc}",
                    recovery="Report this error to the Guppy support channel.",
                )
            )

    return report
