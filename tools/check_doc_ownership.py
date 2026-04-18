"""Fail CI when core docs drift from the ownership contract."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


REQUIRED_README_TOKENS = [
    "## doc ownership contract",
    "project_brief.md",
    "single active status, roadmap, and handoff source",
    "readme.md",
    "architecture/setup/operations reference only",
    "docs/archive/ is historical only",
]

REQUIRED_ROADMAP_STUB_TOKENS = [
    "roadmap compatibility stub",
    "no longer an active truth doc",
    "project_brief.md",
    "archive/root-history/roadmap_2026-04-17.md",
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
    "## Session Log": "Session logs belong in docs/PROJECT_BRIEF.md, not README.",
    "## Active Priorities": "Active priorities belong in docs/PROJECT_BRIEF.md, not README.",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _normalize(text: str) -> str:
    return text.lower().replace("`", "")


def _first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def main() -> int:
    errors: list[str] = []

    readme = ROOT / "README.md"
    instructions_readme = ROOT / "instructions" / "README.md"
    documentation_readme = ROOT / "documentation" / "README.md"

    required_files = [readme, instructions_readme, documentation_readme]
    if any(not p.exists() for p in required_files):
        print("doc ownership check skipped: one or more required canonical docs are missing")
        return 0

    readme_l = _normalize(_read(readme))
    instructions_l = _normalize(_read(instructions_readme))
    documentation_l = _normalize(_read(documentation_readme))

    for token in REQUIRED_README_TOKENS:
        if token not in readme_l:
            errors.append(f"README.md missing required ownership token: {token}")

    roadmap = ROOT / "ROADMAP.md"
    if roadmap.exists():
        roadmap_l = _normalize(_read(roadmap))
        for token in REQUIRED_ROADMAP_STUB_TOKENS:
            if token not in roadmap_l:
                errors.append(f"ROADMAP.md missing required compatibility-stub token: {token}")

    for token in REQUIRED_INSTRUCTIONS_TOKENS:
        if token not in instructions_l:
            errors.append(f"instructions/README.md missing canonical token: {token}")

    for token in REQUIRED_DOCUMENTATION_TOKENS:
        if token not in documentation_l:
            errors.append(f"documentation/README.md missing canonical token: {token}")

    readme_txt = _read(readme)
    if not _first_nonempty_line(readme_txt).startswith("# "):
        errors.append("README.md must start with a top-level heading so the repo front door stays readable.")
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
