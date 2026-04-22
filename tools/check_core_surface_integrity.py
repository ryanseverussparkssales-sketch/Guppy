"""Fail CI when guppy_core canonical surface contract is violated.

Contract:
- guppy_core/__init__.py is the canonical implementation entry surface.
- root-level guppy_core.py has been deliberately retired to avoid a second,
  ambiguous import surface shadowing the package.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    failures: list[str] = []

    canonical = ROOT / "guppy_core" / "__init__.py"
    shim = ROOT / "guppy_core.py"

    if not canonical.exists():
        failures.append("missing canonical package entrypoint: guppy_core/__init__.py")
    if shim.exists():
        failures.append("legacy root shim should remain retired: delete guppy_core.py")

    if failures:
        print("core surface integrity check failed:")
        for msg in failures:
            print(f" - {msg}")
        return 1

    print("core surface integrity check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
