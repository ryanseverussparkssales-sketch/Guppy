"""Fail CI if changed Python modules exceed a line cap.

This guard is intentionally scoped to changed files in the current commit range.
Large transitional modules can be explicitly waived until they are split.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINE_CAP = int(os.environ.get("GUPPY_MODULE_LINE_CAP", "700"))
GUARD_SCOPE = (os.environ.get("GUPPY_GUARD_SCOPE", "delta") or "delta").strip().lower()

WAIVED_PATHS: set[str] = set()

ENFORCED_PREFIXES = (
    "src/guppy/",
)


def _all_enforced_python_files() -> list[Path]:
    files: list[Path] = []
    for prefix in ENFORCED_PREFIXES:
        base = ROOT / prefix
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            if p.is_file():
                files.append(p.relative_to(ROOT))
    return files


def _run_git(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL)


def _changed_python_files() -> list[Path]:
    # Prefer the last commit delta (simple and deterministic for CI push/PR runs).
    try:
        raw = _run_git(["diff", "--name-status", "--diff-filter=AM", "HEAD~1", "HEAD"])
    except Exception:
        # Fallback for shallow/single-commit contexts.
        raw = ""

    changed: list[Path] = []
    for line in raw.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        _, rel = parts
        if not rel.endswith(".py"):
            continue
        p = Path(rel)
        if p.exists():
            changed.append(p)

    if changed:
        return changed

    # Final fallback: if no commit baseline is available, inspect changed files staged in git status.
    try:
        raw = _run_git(["status", "--porcelain"])
    except Exception:
        return []

    for line in raw.splitlines():
        if not (line.startswith("A ") or line.startswith("M ") or line.startswith("AM ")):
            continue
        rel = line[3:]
        if rel.endswith(".py"):
            p = Path(rel)
            if p.exists():
                changed.append(p)
    return changed


def _candidate_python_files() -> list[Path]:
    if GUARD_SCOPE == "baseline":
        return _all_enforced_python_files()
    return _changed_python_files()


def main() -> int:
    if GUARD_SCOPE not in {"delta", "baseline"}:
        print(f"line-cap check failed: invalid GUPPY_GUARD_SCOPE={GUARD_SCOPE!r}")
        print("Allowed values: delta, baseline")
        return 1

    offenders: list[tuple[str, int]] = []
    for rel_path in _candidate_python_files():
        rel_posix = rel_path.as_posix()
        if not rel_posix.startswith(ENFORCED_PREFIXES):
            continue
        if rel_posix in WAIVED_PATHS:
            continue
        line_count = len(rel_path.read_text(encoding="utf-8", errors="replace").splitlines())
        if line_count > LINE_CAP:
            offenders.append((rel_posix, line_count))

    if offenders:
        print(f"line-cap check failed (scope={GUARD_SCOPE}, cap={LINE_CAP} lines):")
        for path, count in offenders:
            print(f" - {path}: {count}")
        print("Split these modules or add a temporary explicit waiver with rationale.")
        return 1

    print(f"line-cap check passed (scope={GUARD_SCOPE}, cap={LINE_CAP} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
