"""
launcher_diagnostics.py

Lane: TR54-D5
Responsibilities:
  - Collect a point-in-time snapshot of launcher health for support export
  - No PII; secrets are never included
  - All fields bounded and serialisable to JSON
  - Callers pass live state; this module only aggregates and formats
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("launcher.diagnostics")

_VERSION = "5.0"


@dataclass
class ProcessInfo:
    pid: int
    name: str
    status: str


@dataclass
class ModelEntry:
    name: str
    size_gb: float
    status: str


@dataclass
class ToolEntry:
    tool_id: str
    status: str
    last_checked: str


@dataclass
class LauncherDiagnosticsSnapshot:
    collected_at: str
    launcher_version: str
    python_version: str
    platform: str
    startup_phases: dict[str, Any]
    startup_over_budget: list[str]
    recent_events: list[dict[str, Any]]
    processes: list[ProcessInfo]
    local_models: list[ModelEntry]
    tools: list[ToolEntry]
    boot_check_summary: str
    boot_check_passed: bool
    active_instance: str
    runtime_backend: str
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def as_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.as_dict(), indent=indent, ensure_ascii=False, default=str)

    def status_lines(self) -> list[tuple[str, str, str]]:
        """Return (label, value, severity) tuples for display."""
        now_ts = time.time()
        lines: list[tuple[str, str, str]] = [
            ("Version", self.launcher_version, "ok"),
            ("Python", self.python_version, "ok"),
            ("Platform", self.platform, "ok"),
            ("Boot checks", self.boot_check_summary, "ok" if self.boot_check_passed else "error"),
            ("Active instance", self.active_instance or "—", "ok"),
            ("Runtime backend", self.runtime_backend or "—", "ok"),
            ("Local models", str(len(self.local_models)), "ok" if self.local_models else "warn"),
            ("Tools", str(len(self.tools)), "ok" if self.tools else "warn"),
            (
                "Over-budget phases",
                ", ".join(self.startup_over_budget) if self.startup_over_budget else "none",
                "warn" if self.startup_over_budget else "ok",
            ),
        ]
        return lines


def _python_version_string() -> str:
    v = sys.version_info
    return f"{v.major}.{v.minor}.{v.micro}"


def _platform_string() -> str:
    return f"{sys.platform} / {os.name}"


def _read_recent_events(runtime_dir: Path, limit: int = 20) -> list[dict[str, Any]]:
    path = runtime_dir / "launcher_events.jsonl"
    if not path.exists():
        return []
    lines: list[str] = []
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        return []
    events = []
    for raw in lines[-limit:]:
        raw = raw.strip()
        if not raw:
            continue
        try:
            events.append(json.loads(raw))
        except json.JSONDecodeError:
            events.append({"raw": raw[:200]})
    return events


def _probe_processes(process_names: list[str]) -> list[ProcessInfo]:
    try:
        import psutil
    except ImportError:
        return []
    results = []
    for name in process_names:
        for proc in psutil.process_iter(["pid", "name", "status"]):
            try:
                if name.lower() in " ".join(proc.cmdline()).lower():
                    results.append(ProcessInfo(
                        pid=proc.pid,
                        name=name,
                        status=proc.status(),
                    ))
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    return results


def collect_diagnostics(
    *,
    runtime_dir: Path,
    active_instance: str = "",
    runtime_backend: str = "",
    startup_phases: Optional[dict[str, Any]] = None,
    startup_over_budget: Optional[list[str]] = None,
    local_models: Optional[list[dict[str, Any]]] = None,
    tools: Optional[list[dict[str, Any]]] = None,
    boot_check_summary: str = "",
    boot_check_passed: bool = True,
    extra: Optional[dict[str, Any]] = None,
) -> LauncherDiagnosticsSnapshot:
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")

    model_entries = [
        ModelEntry(
            name=str(m.get("name", "")),
            size_gb=float(m.get("size_gb", 0.0)),
            status=str(m.get("status", "unknown")),
        )
        for m in (local_models or [])
    ]

    tool_entries = [
        ToolEntry(
            tool_id=str(t.get("tool_id", t.get("id", ""))),
            status=str(t.get("status", "unknown")),
            last_checked=str(t.get("last_checked", "")),
        )
        for t in (tools or [])
    ]

    processes = _probe_processes(["guppy_api.py", "guppy_hub.py"])
    recent_events = _read_recent_events(runtime_dir)

    return LauncherDiagnosticsSnapshot(
        collected_at=now_iso,
        launcher_version=_VERSION,
        python_version=_python_version_string(),
        platform=_platform_string(),
        startup_phases=dict(startup_phases or {}),
        startup_over_budget=list(startup_over_budget or []),
        recent_events=recent_events,
        processes=processes,
        local_models=model_entries,
        tools=tool_entries,
        boot_check_summary=boot_check_summary,
        boot_check_passed=boot_check_passed,
        active_instance=active_instance,
        runtime_backend=runtime_backend,
        extra=dict(extra or {}),
    )


def export_diagnostics_json(snapshot: LauncherDiagnosticsSnapshot, target: Path) -> bool:
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(snapshot.as_json(), encoding="utf-8")
        logger.info("Diagnostics exported to %s", target)
        return True
    except OSError as exc:
        logger.error("Failed to export diagnostics: %s", exc)
        return False
