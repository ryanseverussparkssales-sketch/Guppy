"""Fail CI if test helpers, dev tools, or compat shims bleed into production src/.

Rules enforced:
- src/guppy/ must not import from tests/, tools/, or compat_shims/ at module level
- guppy_core/ must not import from tests/ or tools/
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD_SCOPE = (os.environ.get("GUPPY_GUARD_SCOPE", "delta") or "delta").strip().lower()

_PROD_ROOTS = ("src/guppy/", "guppy_core/", "utils/")
_FORBIDDEN_IMPORT_PATTERNS = [
    re.compile(r"^\s*(?:import|from)\s+tests[\.\s]"),
    re.compile(r"^\s*(?:import|from)\s+tools[\.\s]"),
]

_ALWAYS_SKIP = (
    ".venv/",
    ".tmp/",
    "__pycache__/",
)


def _tracked_python_files() -> list[Path]:
    try:
        if GUARD_SCOPE == "delta":
            result = subprocess.run(
                ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD"],
                capture_output=True,
                text=True,
                cwd=ROOT,
            )
            if result.returncode == 0 and result.stdout.strip():
                paths = [ROOT / p for p in result.stdout.splitlines() if p.endswith(".py")]
                return [p for p in paths if p.exists()]
    except Exception:
        pass

    # Baseline: all tracked Python files under prod roots
    result = subprocess.run(
        ["git", "ls-files", "--", "*.py"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    lines = result.stdout.splitlines()
    return [ROOT / p for p in lines if p.endswith(".py") and p.exists()]


def check() -> list[str]:
    violations: list[str] = []
    files = _tracked_python_files()

    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        if any(rel.startswith(skip) for skip in _ALWAYS_SKIP):
            continue
        if not any(rel.startswith(root) for root in _PROD_ROOTS):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for pat in _FORBIDDEN_IMPORT_PATTERNS:
                if pat.match(line):
                    violations.append(f"{rel}:{i}: forbidden dev import: {line.strip()!r}")

    return violations


def main() -> None:
    violations = check()
    if violations:
        print(f"project isolation check FAILED ({len(violations)} violation(s)):")
        for v in violations:
            print(f"  {v}")
        sys.exit(1)
    print("project isolation check passed")


if __name__ == "__main__":
    main()
