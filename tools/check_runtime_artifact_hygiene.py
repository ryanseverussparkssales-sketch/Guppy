"""Fail CI if stale or oversized runtime artifacts are present in the repo.

Checks:
- launcher_events.jsonl must not exceed 10 MB (truncate warning) or 50 MB (fail)
- No *.pyc / __pycache__ directories committed to git
- No *.log files committed to src/ or guppy_core/
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_JSONL_WARN_BYTES = 10 * 1024 * 1024   # 10 MB
_JSONL_FAIL_BYTES = 50 * 1024 * 1024   # 50 MB

_TRACKED_ARTIFACT_PATTERNS = (
    "*.pyc",
    "*.pyo",
)


def _tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    return result.stdout.splitlines()


def check() -> list[str]:
    violations: list[str] = []
    tracked = _tracked_files()

    for rel in tracked:
        path = ROOT / rel
        lower = rel.lower()

        # Committed compiled bytecode
        if lower.endswith(".pyc") or lower.endswith(".pyo"):
            violations.append(f"{rel}: compiled bytecode should not be committed")

        # Committed log files under prod roots
        if lower.endswith(".log") and (
            rel.startswith("src/") or rel.startswith("guppy_core/")
        ):
            violations.append(f"{rel}: log file should not be committed to src/")

    # JSONL event log size check (not a committed-file violation, just hygiene)
    for jsonl in ROOT.rglob("launcher_events.jsonl"):
        try:
            size = jsonl.stat().st_size
        except OSError:
            continue
        rel = jsonl.relative_to(ROOT).as_posix()
        if size >= _JSONL_FAIL_BYTES:
            violations.append(f"{rel}: event log is {size // (1024*1024)} MB — rotate or truncate")
        elif size >= _JSONL_WARN_BYTES:
            print(f"  warning: {rel} is {size // (1024*1024)} MB — consider rotating")

    return violations


def main() -> None:
    violations = check()
    if violations:
        print(f"runtime artifact hygiene check FAILED ({len(violations)} violation(s)):")
        for v in violations:
            print(f"  {v}")
        sys.exit(1)
    print("runtime artifact hygiene check passed")


if __name__ == "__main__":
    main()
