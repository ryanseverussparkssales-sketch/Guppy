"""Fail CI if top-level compatibility wrappers drift beyond thin-entrypoint shape."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPAT = ROOT / "compat_shims"
MAX_WRAPPER_LINES = 30

WRAPPERS = {
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

    if text.count("main()") != 1:
        errs.append(f"{path.name} must call main() exactly once")

    if "sys.exit(main())" not in text and "SystemExit(main())" not in text:
        errs.append(f"{path.name} must terminate via sys.exit(main()) or SystemExit(main())")

    main_guard_count = text.count('if __name__ == "__main__":')
    if main_guard_count != 1:
        errs.append(f"{path.name} must contain exactly one main guard (found {main_guard_count})")

    if text.count("Compatibility wrapper") != 1:
        errs.append(f"{path.name} should contain exactly one wrapper docstring header")

    if "compat_shims" in text:
        errs.append(f"{path.name} must not import or reference compat_shims")

    return errs


def _validate_shim(path: Path, canonical: str) -> list[str]:
    errs: list[str] = []
    if not path.exists():
        errs.append(f"missing shim: {path.name}")
        return errs

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    if len(lines) > MAX_WRAPPER_LINES:
        errs.append(f"{path.name} exceeds shim line cap ({len(lines)} > {MAX_WRAPPER_LINES})")

    if f'import_module("{canonical}")' not in text:
        errs.append(f"{path.name} missing import_module(\"{canonical}\")")

    if f'run_module("{canonical}"' not in text:
        errs.append(f"{path.name} missing run_module(\"{canonical}\", ...) for __main__ execution")

    if "sys.modules[__name__]" not in text and "_sys.modules[__name__]" not in text:
        errs.append(f"{path.name} missing sys.modules[__name__] redirect")

    if "Compatibility shim" not in text:
        errs.append(f"{path.name} should contain 'Compatibility shim' in docstring")

    if "compat_shims" in text:
        errs.append(f"{path.name} must not import or reference compat_shims")

    main_guard_count = text.count('if __name__ == "__main__":')
    if main_guard_count != 1:
        errs.append(f"{path.name} must contain exactly one main guard (found {main_guard_count})")

    return errs


def _validate_legacy_surface_package(path: Path) -> list[str]:
    errs: list[str] = []
    if not path.exists():
        errs.append(f"missing legacy surface package marker: {path}")
        return errs

    text = path.read_text(encoding="utf-8", errors="replace")
    if "Quarantined legacy desktop surfaces" not in text:
        errs.append(f"{path.name} must clearly mark legacy surfaces as quarantined")
    if "__all__" not in text:
        errs.append(f"{path.name} should define an explicit __all__")
    return errs


def main() -> int:
    failures: list[str] = []
    for rel, required_import in WRAPPERS.items():
        failures.extend(_validate_wrapper(ROOT / rel, required_import))
    failures.extend(_validate_shim(ROOT / "guppy_api.py", "src.guppy.api.server"))
    failures.extend(_validate_legacy_surface_package(COMPAT / "legacy_surfaces" / "__init__.py"))

    if failures:
        print("wrapper integrity check failed:")
        for msg in failures:
            print(f" - {msg}")
        return 1

    print("wrapper integrity check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
