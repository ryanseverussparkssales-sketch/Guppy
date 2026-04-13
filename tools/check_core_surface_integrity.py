"""Fail CI when guppy_core canonical surface contract is violated.

Contract:
- guppy_core/__init__.py is the canonical implementation entry surface.
- guppy_core.py is a thin compatibility shim only.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_SHIM_LINES = 40


def main() -> int:
    failures: list[str] = []

    canonical = ROOT / "guppy_core" / "__init__.py"
    shim = ROOT / "guppy_core.py"

    if not canonical.exists():
        failures.append("missing canonical package entrypoint: guppy_core/__init__.py")
    if not shim.exists():
        failures.append("missing compatibility shim: guppy_core.py")

    if shim.exists():
        text = shim.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()

        if len(lines) > MAX_SHIM_LINES:
            failures.append(
                f"guppy_core.py exceeds shim line cap ({len(lines)} > {MAX_SHIM_LINES})"
            )

        required_tokens = [
            "Compatibility shim",
            '_import_module("guppy_core")',
            "globals().update",
        ]
        for token in required_tokens:
            if token not in text:
                failures.append(f"guppy_core.py missing required shim token: {token}")

        forbidden_tokens = [
            "TOOLS = [",
            "def _exec_tool",
            "SYSTEM =",
            "def run_tool",
        ]
        for token in forbidden_tokens:
            if token in text:
                failures.append(
                    f"guppy_core.py contains implementation token not allowed in shim: {token}"
                )

    if failures:
        print("core surface integrity check failed:")
        for msg in failures:
            print(f" - {msg}")
        return 1

    print("core surface integrity check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
