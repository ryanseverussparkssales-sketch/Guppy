"""Fail when Guppy workflow detects cross-project edits in the Guppy-pi workspace.

Policy:
- Guppy and Guppy-pi must be developed independently.
- Running Guppy guardrails should not proceed when Guppy-pi has tracked changes.

Set GUPPY_ALLOW_CROSS_PROJECT_DIRTY=1 only for emergency local bypasses.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = "Guppy-pi"
ALLOW_DIRTY = (os.environ.get("GUPPY_ALLOW_CROSS_PROJECT_DIRTY", "") or "").strip() == "1"


def _git_status_porcelain() -> list[str]:
    try:
        output = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return []
    return [line.rstrip("\n") for line in output.splitlines() if line.strip()]


def _cross_project_lines(lines: list[str]) -> list[str]:
    hits: list[str] = []
    for line in lines:
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if path == TARGET or path.startswith(f"{TARGET}/"):
            hits.append(line)
    return hits


def main() -> int:
    lines = _git_status_porcelain()
    hits = _cross_project_lines(lines)

    if not hits:
        print("project isolation check passed")
        return 0

    if ALLOW_DIRTY:
        print("project isolation check bypassed (GUPPY_ALLOW_CROSS_PROJECT_DIRTY=1)")
        for hit in hits:
            print(f" - {hit}")
        return 0

    print("project isolation check failed: cross-project changes detected under Guppy-pi")
    print("Guppy and Guppy-pi must remain isolated; do not run shared guardrails with mixed edits.")
    print("Detected entries:")
    for hit in hits:
        print(f" - {hit}")
    print("If this is intentional local-only work, run with GUPPY_ALLOW_CROSS_PROJECT_DIRTY=1.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
