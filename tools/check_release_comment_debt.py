"""Scan tracked Python files for unresolved TODO/FIXME markers above a threshold.

Exits 0 (pass) when debt is within acceptable limits.
Exits 1 (fail) when debt exceeds the cap.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent
DEBT_CAP = int(__import__("os").environ.get("GUPPY_RELEASE_COMMENT_DEBT_CAP", "200"))
PATTERN = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)
SKIP_PREFIXES = (".venv", "node_modules", "__pycache__", ".tmp", "migrations")


def _tracked_python_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--", "*.py"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    lines = result.stdout.splitlines()
    return [ROOT / p for p in lines if p.endswith(".py") and (ROOT / p).exists()]


def _should_skip(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    return any(rel.startswith(prefix) for prefix in SKIP_PREFIXES)


def main() -> int:
    files = _tracked_python_files()
    total = 0
    by_file: list[tuple[str, int]] = []

    for path in files:
        if _should_skip(path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        count = len(PATTERN.findall(text))
        if count:
            by_file.append((path.relative_to(ROOT).as_posix(), count))
            total += count

    by_file.sort(key=lambda x: -x[1])

    if total > DEBT_CAP:
        print(f"release comment-debt check FAILED: {total} markers exceed cap {DEBT_CAP}")
        for rel, n in by_file[:10]:
            print(f"  {n:4d}  {rel}")
        return 1

    print(f"release comment-debt check passed: {total} markers (cap={DEBT_CAP})")
    if by_file:
        for rel, n in by_file[:5]:
            print(f"       {n:3d}  {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
