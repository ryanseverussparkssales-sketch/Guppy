"""Fail CI when generated runtime artifacts are committed.

Default scope is delta (newly added files in commit/worktree). Baseline mode can be
used to audit all tracked runtime files.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD_SCOPE = (os.environ.get("GUPPY_GUARD_SCOPE", "delta") or "delta").strip().lower()

# Runtime files that should never be source-controlled once generated.
DENYLIST = [
    re.compile(r"^runtime/diagnostics_bundle_\d{8}_\d{6}\.json$"),
    re.compile(r"^runtime/(logging_health_snapshot|model_runtime_snapshot|provider_runtime_snapshot)\.json$"),
    re.compile(r"^runtime/pilot_exit_report\.json$"),
    re.compile(r"^runtime/resource_envelope\.status\.json$"),
    re.compile(r"^runtime/offhours_task_worker_state\.json$"),
]


def _run_git(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL)


def _matches_denylist(path: str) -> bool:
    return any(pat.match(path) for pat in DENYLIST)


def _delta_added_files() -> list[str]:
    try:
        raw = _run_git(["diff", "--name-status", "--diff-filter=A", "HEAD~1", "HEAD"])
    except Exception:
        raw = ""

    added: list[str] = []
    for line in raw.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        status, rel = parts
        if status == "A":
            added.append(rel)

    if added:
        return added

    try:
        raw = _run_git(["status", "--porcelain"])
    except Exception:
        return []

    for line in raw.splitlines():
        if line.startswith("A "):
            added.append(line[3:])
    return added


def _tracked_runtime_files() -> list[str]:
    try:
        raw = _run_git(["ls-files", "runtime"]) 
    except Exception:
        return []
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _candidate_files() -> list[str]:
    if GUARD_SCOPE == "baseline":
        return _tracked_runtime_files()
    return _delta_added_files()


def main() -> int:
    if GUARD_SCOPE not in {"delta", "baseline"}:
        print(f"runtime artifact hygiene check failed: invalid GUPPY_GUARD_SCOPE={GUARD_SCOPE!r}")
        print("Allowed values: delta, baseline")
        return 1

    offenders = [p for p in _candidate_files() if _matches_denylist(p)]
    if offenders:
        print(f"runtime artifact hygiene check failed (scope={GUARD_SCOPE}):")
        for rel in offenders:
            print(f" - {rel}")
        print("Do not commit generated runtime snapshots/diagnostics; clean them from the change set.")
        return 1

    print(f"runtime artifact hygiene check passed (scope={GUARD_SCOPE})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
