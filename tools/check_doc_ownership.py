"""Fail CI when core docs drift from ownership contract."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


REQUIRED_README_TOKENS = [
    "## doc ownership contract",
    "project_brief.md",
    "only status owner",
    "readme.md",
    "architecture/setup/operations reference only",
]

REQUIRED_ROADMAP_TOKENS = [
    "## doc ownership contract",
    "project_brief.md",
    "canonical status source",
    "roadmap.md",
    "dated handoff execution log",
]

REQUIRED_INSTRUCTIONS_TOKENS = [
    "canonical operator and contributor instruction set",
    "follow this folder first",
    "instructions/ owns executable process instructions",
    "documentation/ owns architecture, security, and truth-audit references",
]

REQUIRED_DOCUMENTATION_TOKENS = [
    "canonical technical documentation source",
    "source of truth",
    "legacy",
]

FORBIDDEN_README_SECTIONS = {
    "## Session Log": "Session logs belong in ROADMAP handoff, not README.",
    "## Active Priorities": "Active priorities belong in ROADMAP, not README.",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _normalize(text: str) -> str:
    return text.lower().replace("`", "")


def main() -> int:
    errors: list[str] = []

    readme = ROOT / "README.md"
    roadmap = ROOT / "ROADMAP.md"
    instructions_readme = ROOT / "instructions" / "README.md"
    documentation_readme = ROOT / "documentation" / "README.md"

    required_files = [readme, roadmap, instructions_readme, documentation_readme]
    if any(not p.exists() for p in required_files):
        print("doc ownership check skipped: one or more required README/ROADMAP files are missing")
        return 0

    readme_txt = _read(readme)
    roadmap_txt = _read(roadmap)
    instructions_txt = _read(instructions_readme)
    documentation_txt = _read(documentation_readme)

    readme_l = _normalize(readme_txt)
    roadmap_l = _normalize(roadmap_txt)
    instructions_l = _normalize(instructions_txt)
    documentation_l = _normalize(documentation_txt)

    for token in REQUIRED_README_TOKENS:
        if token not in readme_l:
            errors.append(f"README.md missing required ownership token: {token}")

    for token in REQUIRED_ROADMAP_TOKENS:
        if token not in roadmap_l:
            errors.append(f"ROADMAP.md missing required ownership token: {token}")

    for token in REQUIRED_INSTRUCTIONS_TOKENS:
        if token not in instructions_l:
            errors.append(f"instructions/README.md missing canonical token: {token}")

    for token in REQUIRED_DOCUMENTATION_TOKENS:
        if token not in documentation_l:
            errors.append(f"documentation/README.md missing canonical token: {token}")

    for section, reason in FORBIDDEN_README_SECTIONS.items():
        if section in readme_txt:
            errors.append(f"README.md contains forbidden section '{section}'. {reason}")

    if errors:
        print("doc ownership check failed:")
        for err in errors:
            print(f" - {err}")
        return 1

    print("doc ownership check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
