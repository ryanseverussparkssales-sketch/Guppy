"""Fail CI when changed src/guppy files violate architecture import boundaries."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD_SCOPE = (os.environ.get("GUPPY_GUARD_SCOPE", "delta") or "delta").strip().lower()

LEGACY_MODULE_PATTERN = re.compile(
    r"^(from|import)\s+(guppy_ui|merlin_ui|council_ui|guppy_hub|guppy_launcher)\b"
)
HUB_TO_LAUNCHER_PATTERN = re.compile(r"^(from|import)\s+ui\.launcher\b")


def _all_scoped_python_files() -> list[Path]:
    scoped_root = ROOT / "src" / "guppy"
    if not scoped_root.exists():
        return []
    return [p.relative_to(ROOT) for p in scoped_root.rglob("*.py") if p.is_file()]


def _run_git(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL)


def _changed_python_files() -> list[Path]:
    try:
        raw = _run_git(["diff", "--name-status", "--diff-filter=AM", "HEAD~1", "HEAD"])
    except Exception:
        raw = ""

    files: list[Path] = []
    for line in raw.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        rel = parts[1]
        if rel.endswith(".py"):
            p = Path(rel)
            if p.exists():
                files.append(p)

    if files:
        return files

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
                files.append(p)
    return files


def _candidate_python_files() -> list[Path]:
    if GUARD_SCOPE == "baseline":
        return _all_scoped_python_files()
    return _changed_python_files()


def main() -> int:
    if GUARD_SCOPE not in {"delta", "baseline"}:
        print(f"architecture boundary check failed: invalid GUPPY_GUARD_SCOPE={GUARD_SCOPE!r}")
        print("Allowed values: delta, baseline")
        return 1

    violations: list[str] = []
    for rel_path in _candidate_python_files():
        rel = rel_path.as_posix()
        if not rel.startswith("src/guppy/"):
            continue

        lines = rel_path.read_text(encoding="utf-8", errors="replace").splitlines()
        for idx, line in enumerate(lines, start=1):
            txt = line.strip()
            if not txt or txt.startswith("#"):
                continue
            if LEGACY_MODULE_PATTERN.match(txt):
                violations.append(f"{rel}:{idx} imports legacy root module")
            if rel.startswith("src/guppy/hub/") and HUB_TO_LAUNCHER_PATTERN.match(txt):
                violations.append(f"{rel}:{idx} imports ui.launcher (forbidden from hub domain)")

    if violations:
        print(f"architecture boundary check failed (scope={GUARD_SCOPE}):")
        for v in violations:
            print(f" - {v}")
        return 1

    print(f"architecture boundary check passed (scope={GUARD_SCOPE})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
