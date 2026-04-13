"""Fail CI if top-level compatibility wrappers drift beyond thin-entrypoint shape."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_WRAPPER_LINES = 30

WRAPPERS = {
    "guppy_launcher.py": "from src.guppy.apps.launcher_app import main",
    "guppy_hub.py": "from src.guppy.apps.hub_app import main",
}


def _validate_wrapper(path: Path, required_import: str) -> list[str]:
    errs: list[str] = []
    if not path.exists():
        errs.append(f"missing wrapper: {path.name}")
        return errs

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    if len(lines) > MAX_WRAPPER_LINES:
        errs.append(f"{path.name} exceeds wrapper line cap ({len(lines)} > {MAX_WRAPPER_LINES})")

    if required_import not in text:
        errs.append(f"{path.name} missing required import: {required_import}")

    main_guard_count = text.count('if __name__ == "__main__":')
    if main_guard_count != 1:
        errs.append(f"{path.name} must contain exactly one main guard (found {main_guard_count})")

    if text.count("Compatibility wrapper") != 1:
        errs.append(f"{path.name} should contain exactly one wrapper docstring header")

    return errs


def main() -> int:
    failures: list[str] = []
    for rel, required_import in WRAPPERS.items():
        failures.extend(_validate_wrapper(ROOT / rel, required_import))

    if failures:
        print("wrapper integrity check failed:")
        for msg in failures:
            print(f" - {msg}")
        return 1

    print("wrapper integrity check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
