"""Fail CI when live-code imports drift outside the current architecture guardrails.

This checker intentionally codifies the next-step boundary shape without
pretending the full launcher/application/domain split already exists. Current UI
hotspots that still reach runtime/governance/config modules are tracked as
explicit transitional waivers so new drift is blocked while the real extraction
work continues.
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD_SCOPE = (os.environ.get("GUPPY_GUARD_SCOPE", "delta") or "delta").strip().lower()
ENFORCED_PREFIXES = ("src/guppy/", "ui/", "utils/")


@dataclass(frozen=True)
class BoundaryRule:
    rule_id: str
    description: str
    pattern: re.Pattern[str]
    path_prefixes: tuple[str, ...] = ENFORCED_PREFIXES
    excluded_paths: tuple[str, ...] = ()

    def applies_to(self, rel_path: str) -> bool:
        return (
            any(rel_path.startswith(prefix) for prefix in self.path_prefixes)
            and rel_path not in self.excluded_paths
        )


FORBIDDEN_IMPORT_MAP: dict[str, tuple[tuple[str, str, str], ...]] = {
    "ui/": (
        (
            "ui-runtime-api-import",
            "imports runtime API modules directly from the UI layer",
            r"^(from|import)\s+src\.guppy\.api\b",
        ),
        (
            "ui-governance-import",
            "imports workspace/connector governance modules directly from the UI layer",
            r"^(from|import)\s+utils\.(connector_manager|instance_capabilities)\b",
        ),
        (
            "ui-experience-config-import",
            "imports user-editable experience config modules directly from the UI layer",
            r"^(from|import)\s+utils\.(personalization_config|runtime_profile)\b",
        ),
    ),
    "utils/": (
        (
            "utils-to-ui",
            "imports ui.launcher directly from the utils layer",
            r"^(from|import)\s+ui\.launcher\b",
        ),
    ),
}


def _rules_from_forbidden_import_map() -> tuple[BoundaryRule, ...]:
    rules: list[BoundaryRule] = []
    for prefix, entries in FORBIDDEN_IMPORT_MAP.items():
        for rule_id, description, raw_pattern in entries:
            rules.append(
                BoundaryRule(
                    rule_id=rule_id,
                    description=description,
                    pattern=re.compile(raw_pattern),
                    path_prefixes=(prefix,),
                )
            )
    return tuple(rules)


RULES = (
    BoundaryRule(
        rule_id="legacy-root-import",
        description="imports legacy root launcher/hub/surface module",
        pattern=re.compile(r"^(from|import)\s+(guppy_ui|merlin_ui|council_ui|guppy_hub|guppy_launcher)\b"),
        path_prefixes=ENFORCED_PREFIXES,
    ),
    BoundaryRule(
        rule_id="legacy-compat-surface-import",
        description="imports compatibility-only legacy surface package",
        pattern=re.compile(r"^(from|import)\s+compat_shims\.legacy_surfaces\b"),
        path_prefixes=ENFORCED_PREFIXES,
    ),
    BoundaryRule(
        rule_id="hub-to-launcher-ui",
        description="imports ui.launcher from the hub domain",
        pattern=re.compile(r"^(from|import)\s+ui\.launcher\b"),
        path_prefixes=("src/guppy/hub/",),
    ),
    BoundaryRule(
        rule_id="non-launcher-app-to-ui",
        description="imports ui.launcher outside the launcher composition root",
        pattern=re.compile(r"^(from|import)\s+ui\.launcher\b"),
        path_prefixes=("src/guppy/",),
        excluded_paths=("src/guppy/apps/launcher_app.py",),
    ),
    *_rules_from_forbidden_import_map(),
)


# Transitional waivers stay file-local and rule-local so new drift shows up
# immediately instead of hiding behind a coarse directory exemption.
TRANSITIONAL_WAIVERS: dict[str, dict[str, str]] = {}


def _run_git(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL)


def _all_scoped_python_files() -> list[Path]:
    files: list[Path] = []
    for prefix in ENFORCED_PREFIXES:
        base = ROOT / prefix
        if not base.exists():
            continue
        files.extend(path.relative_to(ROOT) for path in base.rglob("*.py") if path.is_file())
    return files


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
            path = Path(rel)
            if path.exists():
                files.append(path)

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
            path = Path(rel)
            if path.exists():
                files.append(path)
    return files


def _candidate_python_files() -> list[Path]:
    if GUARD_SCOPE == "baseline":
        return _all_scoped_python_files()
    return _changed_python_files()


def _is_enforced(rel_path: str) -> bool:
    return any(rel_path.startswith(prefix) for prefix in ENFORCED_PREFIXES)


def find_boundary_hits(rel_path: str, lines: list[str], scope: str = GUARD_SCOPE) -> tuple[list[str], list[str]]:
    violations: list[str] = []
    waived_hits: list[str] = []
    for idx, line in enumerate(lines, start=1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue

        for rule in RULES:
            if not rule.applies_to(rel_path):
                continue
            if not rule.pattern.match(text):
                continue

            waiver_reason = TRANSITIONAL_WAIVERS.get(rel_path, {}).get(rule.rule_id)
            if waiver_reason:
                if scope == "baseline":
                    waived_hits.append(f"{rel_path}:{idx} {rule.rule_id} waived ({waiver_reason})")
                continue

            violations.append(f"{rel_path}:{idx} {rule.description}")
    return violations, waived_hits


def main() -> int:
    if GUARD_SCOPE not in {"delta", "baseline"}:
        print(f"architecture boundary check failed: invalid GUPPY_GUARD_SCOPE={GUARD_SCOPE!r}")
        print("Allowed values: delta, baseline")
        return 1

    violations: list[str] = []
    waived_hits: list[str] = []
    for rel_path in _candidate_python_files():
        rel = rel_path.as_posix()
        if not _is_enforced(rel):
            continue

        lines = rel_path.read_text(encoding="utf-8", errors="replace").splitlines()
        file_violations, file_waived_hits = find_boundary_hits(rel, lines, scope=GUARD_SCOPE)
        violations.extend(file_violations)
        waived_hits.extend(file_waived_hits)

    if violations:
        print(f"architecture boundary check failed (scope={GUARD_SCOPE}):")
        for violation in violations:
            print(f" - {violation}")
        return 1

    print(f"architecture boundary check passed (scope={GUARD_SCOPE})")
    if waived_hits:
        print("transitional baseline waivers:")
        for note in waived_hits:
            print(f" - {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
