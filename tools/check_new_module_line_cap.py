"""Fail CI if active live Python modules exceed the transitional line cap.

Coverage now includes the main live-code roots: ``src/guppy/``, ``ui/``, and
``utils/``. Existing oversized hotspot modules are temporarily waived, but each
waiver is pinned to the current observed file size so the module cannot keep
growing while the strangler refactor lands.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINE_CAP = int(os.environ.get("GUPPY_MODULE_LINE_CAP", "700"))
GUARD_SCOPE = (os.environ.get("GUPPY_GUARD_SCOPE", "delta") or "delta").strip().lower()
WAIVER_DRIFT_WARN_LINES = int(os.environ.get("GUPPY_WAIVER_DRIFT_WARN_LINES", "50"))

ENFORCED_PREFIXES = (
    "src/guppy/",
    "ui/",
    "utils/",
)


@dataclass(frozen=True)
class Waiver:
    max_lines: int
    rationale: str


# Transitional waivers are intentionally narrow and temporary. Each path keeps a
# rationale here so baseline enforcement can start now without hiding where the
# current strangler work still needs to land.
WAIVED_PATHS: dict[str, Waiver] = {
    "src/guppy/api/server_runtime_snapshot.py": Waiver(
        max_lines=789,
        rationale="Runtime snapshot compatibility shell reduced to 789 after auth/cache stubs and prompt-builder block extracted to snapshot_auth_cache_support.py and snapshot_prompt_support.py; further route-family splits remain required.",
    ),
    "ui/launcher/launcher_window.py": Waiver(
        max_lines=993,
        rationale="Launcher shell reduced to 993 after nav/tab/panel/notification family extraction into launcher_nav_handlers.py; remaining orchestration seams are tracked for continued splits.",
    ),
}


def _all_enforced_python_files() -> list[Path]:
    files: list[Path] = []
    for prefix in ENFORCED_PREFIXES:
        base = ROOT / prefix
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if path.is_file():
                files.append(path.relative_to(ROOT))
    return files


def _run_git(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL)


def _changed_python_files() -> list[Path]:
    try:
        raw = _run_git(["diff", "--name-status", "--diff-filter=AM", "HEAD~1", "HEAD"])
    except Exception:
        raw = ""

    changed: list[Path] = []
    for line in raw.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        _, rel = parts
        if not rel.endswith(".py"):
            continue
        path = Path(rel)
        if path.exists():
            changed.append(path)

    if changed:
        return changed

    try:
        raw = _run_git(["status", "--porcelain"])
    except Exception:
        return []

    for line in raw.splitlines():
        if not (line.startswith("A ") or line.startswith("M ") or line.startswith("AM ")):
            continue
        rel = line[3:]
        if rel.endswith(".py"):
            path = Path(rel)
            if path.exists():
                changed.append(path)
    return changed


def _candidate_python_files() -> list[Path]:
    if GUARD_SCOPE == "baseline":
        return _all_enforced_python_files()
    return _changed_python_files()


def _is_enforced(rel_posix: str) -> bool:
    return any(rel_posix.startswith(prefix) for prefix in ENFORCED_PREFIXES)


def _waiver_drift_note(rel_posix: str, line_count: int, waiver: Waiver) -> str:
    headroom = waiver.max_lines - line_count
    if headroom < 0:
        state = "over-cap"
    elif headroom == 0:
        state = "at-cap"
    elif headroom > WAIVER_DRIFT_WARN_LINES:
        state = f"metadata drift: {headroom} lines of stale waiver headroom"
    else:
        state = f"headroom {headroom}"
    return (
        f"{rel_posix}: waived at {line_count}/{waiver.max_lines} lines "
        f"({state}; {waiver.rationale})"
    )


def main() -> int:
    if GUARD_SCOPE not in {"delta", "baseline"}:
        print(f"line-cap check failed: invalid GUPPY_GUARD_SCOPE={GUARD_SCOPE!r}")
        print("Allowed values: delta, baseline")
        return 1

    offenders: list[str] = []
    waived_notes: list[str] = []
    for rel_path in _candidate_python_files():
        rel_posix = rel_path.as_posix()
        if not _is_enforced(rel_posix):
            continue

        line_count = len(rel_path.read_text(encoding="utf-8", errors="replace").splitlines())
        waiver = WAIVED_PATHS.get(rel_posix)

        if waiver is not None:
            if line_count > waiver.max_lines:
                offenders.append(
                    f"{rel_posix}: {line_count} lines exceeds transitional waiver cap "
                    f"{waiver.max_lines} ({waiver.rationale})"
                )
            elif GUARD_SCOPE == "baseline":
                waived_notes.append(_waiver_drift_note(rel_posix, line_count, waiver))
            continue

        if line_count > LINE_CAP:
            offenders.append(f"{rel_posix}: {line_count} lines exceeds cap {LINE_CAP}")

    if offenders:
        print(f"line-cap check failed (scope={GUARD_SCOPE}, cap={LINE_CAP} lines):")
        for item in offenders:
            print(f" - {item}")
        print("Split these modules or add a temporary explicit waiver with rationale.")
        return 1

    print(f"line-cap check passed (scope={GUARD_SCOPE}, cap={LINE_CAP} lines)")
    if waived_notes:
        print("transitional baseline waivers:")
        for item in waived_notes:
            print(f" - {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
