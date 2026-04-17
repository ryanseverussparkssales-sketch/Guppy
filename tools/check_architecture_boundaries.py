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

    def applies_to(self, rel_path: str) -> bool:
        if self.rule_id == "hub-to-launcher-ui":
            return rel_path.startswith("src/guppy/hub/")
        if self.rule_id == "non-launcher-app-to-ui":
            return rel_path.startswith("src/guppy/") and rel_path != "src/guppy/apps/launcher_app.py"
        if self.rule_id.startswith("ui-"):
            return rel_path.startswith("ui/")
        if self.rule_id == "utils-to-ui":
            return rel_path.startswith("utils/")
        return any(rel_path.startswith(prefix) for prefix in ENFORCED_PREFIXES)


RULES = (
    BoundaryRule(
        rule_id="legacy-root-import",
        description="imports legacy root launcher/hub/surface module",
        pattern=re.compile(r"^(from|import)\s+(guppy_ui|merlin_ui|council_ui|guppy_hub|guppy_launcher)\b"),
    ),
    BoundaryRule(
        rule_id="legacy-compat-surface-import",
        description="imports compatibility-only legacy surface package",
        pattern=re.compile(r"^(from|import)\s+compat_shims\.legacy_surfaces\b"),
    ),
    BoundaryRule(
        rule_id="hub-to-launcher-ui",
        description="imports ui.launcher from the hub domain",
        pattern=re.compile(r"^(from|import)\s+ui\.launcher\b"),
    ),
    BoundaryRule(
        rule_id="non-launcher-app-to-ui",
        description="imports ui.launcher outside the launcher composition root",
        pattern=re.compile(r"^(from|import)\s+ui\.launcher\b"),
    ),
    BoundaryRule(
        rule_id="ui-runtime-api-import",
        description="imports runtime API modules directly from the UI layer",
        pattern=re.compile(r"^(from|import)\s+src\.guppy\.api\b"),
    ),
    BoundaryRule(
        rule_id="ui-governance-import",
        description="imports workspace/connector governance modules directly from the UI layer",
        pattern=re.compile(r"^(from|import)\s+utils\.(connector_manager|instance_capabilities)\b"),
    ),
    BoundaryRule(
        rule_id="ui-experience-config-import",
        description="imports user-editable experience config modules directly from the UI layer",
        pattern=re.compile(r"^(from|import)\s+utils\.(personalization_config|runtime_profile)\b"),
    ),
    BoundaryRule(
        rule_id="utils-to-ui",
        description="imports ui.launcher directly from the utils layer",
        pattern=re.compile(r"^(from|import)\s+ui\.launcher\b"),
    ),
)


# Transitional waivers stay file-local and rule-local so new drift shows up
# immediately instead of hiding behind a coarse directory exemption.
TRANSITIONAL_WAIVERS: dict[str, dict[str, str]] = {
    "src/guppy/apps/guppy_surface_app.py": {
        "legacy-compat-surface-import": "Compatibility entrypoint still forwards into a quarantined legacy surface until that launcher alias is fully retired.",
    },
    "ui/launcher/launcher_window.py": {
        "ui-runtime-api-import": "Launcher shell still reaches API auth bootstrap directly pending launcher-application services.",
        "ui-governance-import": "Launcher shell still coordinates governance and connector state pending shared snapshots.",
        "ui-experience-config-import": "Launcher shell still hydrates persona/profile state pending experience-config services.",
    },
    "ui/launcher/views/advanced_view.py": {
        "ui-experience-config-import": "App Mgmt still reads runtime profile settings directly pending workflow/config presenters.",
    },
    "ui/launcher/views/models_view.py": {
        "ui-experience-config-import": "Models still reads/saves runtime and provider configuration directly pending typed view models.",
    },
    "ui/launcher/views/my_pc_view.py": {
        "ui-governance-import": "Windows ops view still reads connector metadata directly pending connector inventory DTOs.",
    },
    "ui/launcher/views/settings_view.py": {
        "ui-experience-config-import": "Settings remains the transitional editor for experience config until services are extracted.",
    },
    "ui/launcher/views/tools_view.py": {
        "ui-governance-import": "Agent Tools still reads workspace capability policy directly pending governance snapshots.",
    },
    "ui/launcher/views/voices_view.py": {
        "ui-experience-config-import": "Voices still binds persona/voice configuration directly pending experience-config services.",
    },
}


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
        for idx, line in enumerate(lines, start=1):
            text = line.strip()
            if not text or text.startswith("#"):
                continue

            for rule in RULES:
                if not rule.applies_to(rel):
                    continue
                if not rule.pattern.match(text):
                    continue

                waiver_reason = TRANSITIONAL_WAIVERS.get(rel, {}).get(rule.rule_id)
                if waiver_reason:
                    if GUARD_SCOPE == "baseline":
                        waived_hits.append(f"{rel}:{idx} {rule.rule_id} waived ({waiver_reason})")
                    continue

                violations.append(f"{rel}:{idx} {rule.description}")

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
