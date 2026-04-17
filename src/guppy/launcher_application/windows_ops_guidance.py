"""Outcome and follow-up helpers for launcher Windows Ops flows."""

from __future__ import annotations

from typing import Any


def windows_ops_chain_changes(action: str) -> str:
    normalized = str(action or "").strip().lower()
    if normalized == "restart_runtime":
        return "Restarted the daemon, then refreshed warmup and runtime-audit evidence."
    if normalized == "repair_runtime":
        return "Captured a fresh health snapshot, then reran warmup and runtime-audit evidence."
    return ""


def windows_ops_guidance(action: str, *, ok: bool, phase: str = "completed") -> dict[str, str]:
    normalized = str(action or "").strip().lower()
    lifecycle_phase = str(phase or "completed").strip().lower() or "completed"
    if lifecycle_phase == "queued":
        if normalized in {"verify_runtime", "update_runtime", "package_desktop", "release_dry_run"}:
            return {
                "next_step": "Watch the App Mgmt terminal for completion evidence and wait for the servicing ref to appear.",
                "fix_target": "App Mgmt > Windows Ops",
                "docs_hint": "docs/PACKAGING.md" if normalized in {"package_desktop", "release_dry_run"} else "docs/TROUBLESHOOTING.md",
                "entry_point": (
                    "python tools/beta_release_dry_run.py"
                    if normalized == "release_dry_run"
                    else "bin\\build_executable.bat --no-clean --ci"
                    if normalized == "package_desktop"
                    else "python src/guppy/cli/launch.py launcher"
                ),
            }
        if normalized == "start_supervised_api":
            return {
                "next_step": "Wait for the supervised API reachability check to finish, then verify the runtime if you need full post-start evidence.",
                "fix_target": "bin/launch_api_supervised.bat",
                "docs_hint": "docs/SUPERVISION_WINDOWS.md",
                "entry_point": "bin/launch_api_supervised.bat",
            }
        if normalized in {"restart_runtime", "repair_runtime"}:
            return {
                "next_step": "Wait for the queued recovery chain to finish, then review the final servicing summary before you retry anything.",
                "fix_target": "App Mgmt > Windows Ops",
                "docs_hint": "docs/SUPERVISION_WINDOWS.md",
                "entry_point": "bin/launch_api_supervised.bat",
            }
    if ok:
        lookup = {
            "verify_runtime": {
                "next_step": "Runtime verification passed. If you need a fresh desktop build, run bin\\build_executable.bat --no-clean next.",
                "fix_target": "bin\\build_executable.bat",
                "docs_hint": "docs/PACKAGING.md",
                "entry_point": "bin\\build_executable.bat --no-clean",
            },
            "update_runtime": {
                "next_step": "Update postflight passed. Re-run VERIFY after major runtime changes, or package with bin\\build_executable.bat --no-clean.",
                "fix_target": "bin\\build_executable.bat",
                "docs_hint": "docs/PACKAGING.md",
                "entry_point": "bin\\build_executable.bat --no-clean",
            },
            "package_desktop": {
                "next_step": "Desktop packaging passed. Share the build from dist or rerun VERIFY before broader rollout if runtime changed again.",
                "fix_target": "dist/Guppy or dist/Guppy.exe",
                "docs_hint": "docs/PACKAGING.md",
                "entry_point": "bin\\build_executable.bat --no-clean --ci",
            },
            "release_dry_run": {
                "next_step": "Release dry-run passed. Review the dry-run report, receipt, and summary in that order, then package or hand off the reviewer bundle.",
                "fix_target": "runtime/beta_release_dry_run_report.json",
                "docs_hint": "docs/PACKAGING.md",
                "entry_point": "python tools/beta_release_dry_run.py",
            },
            "start_supervised_api": {
                "next_step": "Supervised API launch passed. Run VERIFY next if you want fresh runtime evidence from inside App Mgmt.",
                "fix_target": "bin/launch_api_supervised.bat",
                "docs_hint": "docs/SUPERVISION_WINDOWS.md",
                "entry_point": "bin/launch_api_supervised.bat",
            },
            "restart_runtime": {
                "next_step": "Restart completed. If the API still looks stale, run REPAIR next; otherwise keep working.",
                "fix_target": "App Mgmt > Windows Ops",
                "docs_hint": "docs/SUPERVISION_WINDOWS.md",
                "entry_point": "bin/launch_api_supervised.bat",
            },
            "repair_runtime": {
                "next_step": "Repair completed. Re-run VERIFY when you want a fresh health read, then package or relaunch as needed.",
                "fix_target": "App Mgmt VERIFY + bin\\build_executable.bat",
                "docs_hint": "docs/TROUBLESHOOTING.md",
                "entry_point": "python src/guppy/cli/launch.py launcher",
            },
        }
        if normalized in lookup:
            return lookup[normalized]
    else:
        lookup = {
            "verify_runtime": {
                "next_step": "Run REPAIR next. If dependency or build checks are the problem, run UPDATE before you retry VERIFY.",
                "fix_target": "App Mgmt REPAIR / UPDATE",
                "docs_hint": "docs/TROUBLESHOOTING.md",
                "entry_point": "python src/guppy/cli/launch.py launcher",
            },
            "update_runtime": {
                "next_step": "Open the terminal evidence, fix requirements or packaging entry points, then rerun UPDATE.",
                "fix_target": "requirements.txt / requirements-optional.txt / bin\\build_executable.bat",
                "docs_hint": "docs/PACKAGING.md",
                "entry_point": "bin\\build_executable.bat --no-clean",
            },
            "package_desktop": {
                "next_step": "Open the packaging evidence, fix the build script or missing assets, then rerun PACKAGE.",
                "fix_target": "bin\\build_executable.bat / bin\\Guppy.spec / docs/PACKAGING.md",
                "docs_hint": "docs/PACKAGING.md",
                "entry_point": "bin\\build_executable.bat --no-clean --ci",
            },
            "release_dry_run": {
                "next_step": "Open the dry-run evidence, fix the failing gate or missing handoff file, then rerun RELEASE DRY RUN.",
                "fix_target": "tools/beta_release_dry_run.py / tools/pilot_exit_check.py / docs/REMOTE_BETA_EXE_POLICY.md",
                "docs_hint": "docs/PACKAGING.md",
                "entry_point": "python tools/beta_release_dry_run.py",
            },
            "start_supervised_api": {
                "next_step": "Check the supervised launch script and API startup prerequisites, then rerun START API or fall back to REPAIR.",
                "fix_target": "bin/launch_api_supervised.bat / guppy_api.py",
                "docs_hint": "docs/SUPERVISION_WINDOWS.md",
                "entry_point": "bin/launch_api_supervised.bat",
            },
            "restart_runtime": {
                "next_step": "Check the supervised API entry point, then rerun RESTART or fall back to REPAIR.",
                "fix_target": "bin/launch_api_supervised.bat",
                "docs_hint": "docs/SUPERVISION_WINDOWS.md",
                "entry_point": "bin/launch_api_supervised.bat",
            },
            "repair_runtime": {
                "next_step": "Inspect launcher logs and supervision guidance before retrying repair so you fix the underlying packaging or runtime fault first.",
                "fix_target": "runtime/launcher_events.jsonl / docs/SUPERVISION_WINDOWS.md",
                "docs_hint": "docs/SUPERVISION_WINDOWS.md",
                "entry_point": "bin/launch_api_supervised.bat",
            },
        }
        if normalized in lookup:
            return lookup[normalized]
    return {
        "next_step": "Review the latest servicing evidence before taking the next installer or repair action.",
        "fix_target": "App Mgmt > Windows Ops",
        "docs_hint": "docs/TROUBLESHOOTING.md",
        "entry_point": "python src/guppy/cli/launch.py launcher",
    }


def summarize_windows_recipe_result(payload: dict[str, object]) -> tuple[str, str]:
    label = str(payload.get("label", "WINDOWS OPS") or "WINDOWS OPS").strip()
    steps_total = int(payload.get("steps_total", 0) or 0)
    steps_completed = int(payload.get("steps_completed", 0) or 0)
    failed_steps = [item for item in payload.get("failed_steps", []) if isinstance(item, dict)] if isinstance(payload.get("failed_steps"), list) else []
    ok = bool(payload.get("ok", False))
    summary = (
        f"{label} completed {steps_completed}/{steps_total} servicing step(s)."
        if ok
        else f"{label} stopped after {steps_completed}/{steps_total} successful servicing step(s)."
    )
    if failed_steps:
        failed = failed_steps[0]
        summary += f" Failed step {int(failed.get('index', 0) or 0)}."
    changes = str(payload.get("changes", "") or "").strip()
    if failed_steps:
        failed = failed_steps[0]
        command = str(failed.get("command", "") or "").strip()
        changes = (
            f"{changes} Failed command: {command}."
            if changes and command
            else f"Failed command: {command}."
            if command
            else changes or "A servicing step failed before the recipe completed."
        )
    return summary, changes
