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
    re.compile(r"^runtime/.*\.pid$"),
    re.compile(r"^runtime/repair_token\.txt$"),
    re.compile(r"^runtime/instance_state\.json$"),
    re.compile(r"^runtime/diagnostics_bundle_\d{8}_\d{6}\.json$"),
    re.compile(r"^runtime/(logging_health_snapshot|model_runtime_snapshot|provider_runtime_snapshot)\.json$"),
    re.compile(r"^runtime/beta_policy_report\.json$"),
    re.compile(r"^runtime/pilot_exit_report\.json$"),
    re.compile(r"^runtime/resource_envelope\.status\.json$"),
    re.compile(r"^runtime/tool_schema_audit\.json$"),
    re.compile(r"^runtime/logs/.*\.(jsonl|summary\.json)$"),
    re.compile(r"^runtime/offhours_results/.*\.(md|json|jsonl|staged)$"),
    re.compile(r"^runtime/nightly_.*\.md$"),
    re.compile(r"^runtime/overnight_.*\.(md|json)$"),
    re.compile(r"^runtime/canary/.*\.(json|jsonl|md)$"),
    re.compile(r"^runtime/offhours_task_queue\.json$"),
    re.compile(r"^runtime/offhours_task_worker_state\.json$"),
]


def _run_git(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL)


def _matches_denylist(path: str) -> bool:
    return any(pat.match(path) for pat in DENYLIST)


def _delta_changed_files() -> list[str]:
    # Prefer the current worktree so local verification reflects the actual change set.
    try:
        raw = _run_git(["status", "--porcelain", "--untracked-files=all", "runtime"])
    except Exception:
        raw = ""

    changed: list[str] = []
    saw_worktree_entries = False
    for line in raw.splitlines():
        if not line:
            continue
        saw_worktree_entries = True
        status = line[:2]
        rel = line[3:].strip()
        if not rel:
            continue
        if status in {"A ", "AM", " M", "M ", "??"}:
            changed.append(rel)

    if saw_worktree_entries:
        return changed

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
    return _delta_changed_files()


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
