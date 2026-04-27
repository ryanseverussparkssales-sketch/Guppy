"""Fail CI if active live Python modules exceed the transitional line cap.

Coverage includes the main live-code roots: ``src/guppy/``, ``ui/``,
``compat_shims/launcher_ui/ui/launcher/``, and ``utils/``. Existing oversized
hotspot modules are temporarily waived, but each waiver is pinned to the current
observed file size so the module cannot keep growing while the strangler refactor
lands.

The baseline run also reports softer hardening tiers so the team can keep moving
large modules toward a healthier dispersed shape before they hit the fail cap.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDEAL_MODULE_LINES = int(os.environ.get("GUPPY_IDEAL_MODULE_LINES", "250"))
HEALTHY_MODULE_LINES = int(os.environ.get("GUPPY_HEALTHY_MODULE_LINES", "400"))
REVIEW_MODULE_LINES = int(os.environ.get("GUPPY_REVIEW_MODULE_LINES", "600"))
LINE_CAP = int(os.environ.get("GUPPY_MODULE_LINE_CAP", "700"))
GUARD_SCOPE = (os.environ.get("GUPPY_GUARD_SCOPE", "delta") or "delta").strip().lower()
WAIVER_DRIFT_WARN_LINES = int(os.environ.get("GUPPY_WAIVER_DRIFT_WARN_LINES", "50"))

ENFORCED_PREFIXES = (
    "src/guppy/",
    "ui/",
    "compat_shims/launcher_ui/ui/launcher/",
    "utils/",
)


@dataclass(frozen=True)
class Waiver:
    max_lines: int
    rationale: str


# Transitional waivers are intentionally narrow and temporary. Existing large
# modules stay visible in the baseline watchlist, but only active over-cap files
# should remain waived here.
WAIVED_PATHS: dict[str, Waiver] = {
    "utils/tool_registry.py": Waiver(
        max_lines=800,
        rationale="Pure data file: 78 tool JSON schemas. Splitting would add indirection with no benefit.",
    ),
    "src/guppy/api/realtime_inference_support.py": Waiver(
        max_lines=1060,
        rationale=(
            "Unified streaming inference pipeline: agentic tool-call loop, "
            "multi-backend SSE fan-out, steer/vision/TTS modes. "
            "Single cohesive boundary — split would scatter the control flow "
            "across multiple files with no clean seam. "
            "Pinned 2026-04-26; refactor to sub-modules (stream_llamacpp.py, "
            "stream_ollama.py, stream_anthropic.py) planned."
        ),
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


def classify_module_size(line_count: int) -> str:
    if line_count <= IDEAL_MODULE_LINES:
        return "ideal"
    if line_count <= HEALTHY_MODULE_LINES:
        return "healthy"
    if line_count <= REVIEW_MODULE_LINES:
        return "review"
    if line_count <= LINE_CAP:
        return "urgent"
    return "oversized"


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


def _module_size_summary(rel_path: Path, line_count: int) -> str:
    return f"{rel_path.as_posix()}: {line_count} lines [{classify_module_size(line_count)}]"


def main() -> int:
    if GUARD_SCOPE not in {"delta", "baseline"}:
        print(f"line-cap check failed: invalid GUPPY_GUARD_SCOPE={GUARD_SCOPE!r}")
        print("Allowed values: delta, baseline")
        return 1

    offenders: list[str] = []
    waived_notes: list[str] = []
    tier_counts = {
        "ideal": 0,
        "healthy": 0,
        "review": 0,
        "urgent": 0,
        "oversized": 0,
    }
    watchlist: list[tuple[int, Path]] = []
    for rel_path in _candidate_python_files():
        rel_posix = rel_path.as_posix()
        if not _is_enforced(rel_posix):
            continue

        line_count = len(rel_path.read_text(encoding="utf-8", errors="replace").splitlines())
        tier_counts[classify_module_size(line_count)] += 1
        waiver = WAIVED_PATHS.get(rel_posix)

        if waiver is not None:
            if line_count > waiver.max_lines:
                offenders.append(
                    f"{rel_posix}: {line_count} lines exceeds transitional waiver cap "
                    f"{waiver.max_lines} ({waiver.rationale})"
                )
            elif GUARD_SCOPE == "baseline":
                waived_notes.append(_waiver_drift_note(rel_posix, line_count, waiver))
                watchlist.append((line_count, rel_path))
            continue

        if line_count > LINE_CAP:
            offenders.append(f"{rel_posix}: {line_count} lines exceeds cap {LINE_CAP}")
        elif GUARD_SCOPE == "baseline" and line_count > HEALTHY_MODULE_LINES:
            watchlist.append((line_count, rel_path))

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
    if GUARD_SCOPE == "baseline":
        print(
            "module size tiers:"
            f" ideal<={IDEAL_MODULE_LINES} healthy<={HEALTHY_MODULE_LINES}"
            f" review<={REVIEW_MODULE_LINES} urgent<={LINE_CAP}"
        )
        print(
            "module size counts:"
            f" ideal={tier_counts['ideal']}"
            f" healthy={tier_counts['healthy']}"
            f" review={tier_counts['review']}"
            f" urgent={tier_counts['urgent']}"
            f" oversized={tier_counts['oversized']}"
        )
        if watchlist:
            print("baseline size watchlist:")
            for line_count, rel_path in sorted(watchlist, reverse=True)[:12]:
                print(f" - {_module_size_summary(rel_path, line_count)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
