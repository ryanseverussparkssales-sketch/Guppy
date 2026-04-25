"""Audit pyproject.toml dependencies for version pins and known advisories.

Checks:
- All dependencies have an upper bound (< or == specifier)
- No packages with known CVEs in the advisory list
Exits 0 on pass, 1 on failure.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-reuse-module]

ROOT = Path(__file__).parent.parent
PYPROJECT = ROOT / "pyproject.toml"

# Packages known to have had serious CVEs; update as advisories land.
ADVISORY_BLOCKLIST: list[str] = []


def _parse_deps(data: dict) -> list[str]:
    return data.get("project", {}).get("dependencies", [])


def _has_upper_bound(spec: str) -> bool:
    return bool(re.search(r"(<|==)", spec))


def main() -> int:
    if not PYPROJECT.exists():
        print("dependency audit FAILED: pyproject.toml not found")
        return 1

    with PYPROJECT.open("rb") as f:
        data = tomllib.load(f)

    deps = _parse_deps(data)
    failures: list[str] = []

    for dep in deps:
        name = re.split(r"[><=!,\[]", dep)[0].strip().lower()
        if name in ADVISORY_BLOCKLIST:
            failures.append(f"ADVISORY: {dep}")
        if not _has_upper_bound(dep):
            failures.append(f"no upper bound: {dep}")

    if failures:
        print(f"dependency audit FAILED ({len(failures)} issue(s)):")
        for f in failures:
            print(f"  {f}")
        return 1

    print(f"dependency audit passed: {len(deps)} dependencies checked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
