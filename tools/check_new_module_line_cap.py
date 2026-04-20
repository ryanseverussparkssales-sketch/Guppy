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
        max_lines=3098,
        rationale="Runtime snapshot hotspot is smaller after shared briefing and telemetry extractions, but still awaits deeper runtime-application splits.",
    ),
    "src/guppy/daemon/daemon.py": Waiver(
        max_lines=1473,
        rationale="Daemon orchestration remains monolithic pending bounded service splits.",
    ),
    "src/guppy/merlin/core.py": Waiver(
        max_lines=1115,
        rationale="Legacy specialist runtime remains in transition and is not part of this tranche.",
    ),
    "src/guppy/memory/memory.py": Waiver(
        max_lines=944,
        rationale="Memory service still exceeds the cap until dedicated persistence/service seams land.",
    ),
    "src/guppy/api/services_realtime.py": Waiver(
        max_lines=713,
        rationale="Realtime API service still bundles too many behaviors pending runtime decomposition.",
    ),
    "src/guppy/api/server_runtime.py": Waiver(
        max_lines=741,
        rationale="Runtime shell now binds extracted startup, briefing, and auth/request helpers directly, but route and request orchestration still keep the API surface above the cap pending the next bounded split.",
    ),
    "src/guppy/debug/console.py": Waiver(
        max_lines=717,
        rationale="Debug console remains oversized but out of scope for the current build tranche.",
    ),
    "src/guppy/voice/voice.py": Waiver(
        max_lines=704,
        rationale="Voice orchestration still needs a later service split and broader device validation.",
    ),
    "ui/launcher/launcher_window.py": Waiver(
        max_lines=3471,
        rationale="Launcher shell hotspot; automation-test coordination, windows-ops completion coordination, and the current C38/C39 launcher chrome and command-start hardening are now extracted or integrated, but the five-hub shell still carries workspace-access, request routing, and top-level orchestration pressure pending the next bounded split.",
    ),
    "ui/launcher/views/settings_operations_panel.py": Waiver(
        max_lines=939,
        rationale="Settings operations panel now owns the extracted diagnostics, recovery, connector-ops, and terminal workflow surface; presenter seams are still pending a later split.",
    ),
    "ui/launcher/views/models_view.py": Waiver(
        max_lines=1542,
        rationale="Models hub now routes some runtime and readiness shaping through a presenter seam, but multi-provider routing and harness evidence still keep the main view oversized pending a later panel split. PL-C3 clarity pass added tooltips to SPAWN, APPLY, DOWNLOAD, UNINSTALL, CHECK HEALTH, REFRESH, SAVE RUNTIME, USE THIS SESSION, APPLY ROUTES, APPLY MIX, and MODEL HEALTH buttons.",
    ),
    "ui/launcher/views/instance_manager_view.py": Waiver(
        max_lines=869,
        rationale="Workspace manager still bundles governance and render logic pending shared snapshots.",
    ),
    "ui/launcher/views/assistant_view.py": Waiver(
        max_lines=1328,
        rationale="Home chat carries active context, starter, and transcript orchestration; capped at observed size while the final Home cleanup keeps compatibility setters in place but removes operator surfaces from the visible daily chat screen. PL-C3 clarity pass added hub-purpose label and tooltips for send, starters, details, IN LIBRARY, and ATTACH NOW buttons.",
    ),
    "ui/launcher/views/library_view.py": Waiver(
        max_lines=832,
        rationale="Library now owns multiline note editing and local media handoff/control while still bundling browse/edit/render behavior; the dedicated media panel reduced some pressure, but deeper presenter extraction is still pending. PL-C3 clarity pass added hub-purpose label and tooltips for PIN NOTE, CANCEL EDIT, PICK FILE, SAVE ARTIFACT, and CANCEL EDIT buttons.",
    ),
    "ui/launcher/views/voices_view.py": Waiver(
        max_lines=866,
        rationale="Voice management remains oversized until experience-config services feed the UI. PL-C3 clarity pass bumped PREVIEW and SELECT button heights to 28px minimum and added tooltips.",
    ),
    "ui/launcher/views/settings_view.py": Waiver(
        max_lines=732,
        rationale="Settings remains transitional while configuration ownership moves out of the UI layer.",
    ),
    "utils/connector_manager.py": Waiver(
        max_lines=670,
        rationale="Connector readiness and workspace binding evidence now route through a dedicated connector-workspace seam; remaining action/auth orchestration still keeps the compatibility facade oversized.",
    ),
    "utils/personalization_config.py": Waiver(
        max_lines=1009,
        rationale="Experience-config persistence expanded with multi-provider registry (6 new providers); awaiting split into provider_registry_service + persona_service under src/guppy/experience_config/.",
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
