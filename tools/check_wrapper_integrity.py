"""Fail CI if top-level compatibility wrappers drift beyond thin-entrypoint shape."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_WRAPPER_LINES = 30

WRAPPERS = {
    "guppy_launcher.py": "from src.guppy.apps.launcher_app import main",
    "guppy_hub.py": "from src.guppy.apps.hub_app import main",
    # Legacy-surface compatibility wrappers (implementations live in legacy_surfaces/)
    "guppy_ui.py": "from src.guppy.apps.guppy_surface_app import main",
    "merlin_ui.py": "from src.guppy.apps.merlin_surface_app import main",
    "council_ui.py": "from src.guppy.apps.council_surface_app import main",
}

# sys.modules-redirect shims: maps root filename → canonical dotted module path
SHIMS = {
    "guppy_api.py":             "src.guppy.api.server",
    "guppy_api_auth.py":        "src.guppy.api.auth",
    "inference_router.py":      "src.guppy.inference.router",
    "merlin_core.py":           "src.guppy.merlin.core",
    "media_tools.py":           "src.guppy.tools.media",
    "debug_console.py":         "src.guppy.debug.console",
    "guppy_memory.py":          "src.guppy.memory.memory",
    "guppy_voice.py":           "src.guppy.voice.voice",
    "guppy_daemon.py":          "src.guppy.daemon.daemon",
    "guppy_agent.py":           "src.guppy.cli.agent",
    "crm_voip_integrations.py": "src.guppy.integrations.crm_voip",
    "guppy_semantic_memory.py": "src.guppy.memory.semantic",
    "github_tools.py":          "src.guppy.tools.github",
    "guppy_theme.py":           "src.guppy.ui.theme",
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

    if "sys.modules[__name__]" not in text and "_sys.modules[__name__]" not in text:
        errs.append(f"{path.name} missing sys.modules[__name__] redirect")

    if "Compatibility shim" not in text:
        errs.append(f"{path.name} should contain 'Compatibility shim' in docstring")

    return errs


def main() -> int:
    failures: list[str] = []
    for rel, required_import in WRAPPERS.items():
        failures.extend(_validate_wrapper(ROOT / rel, required_import))
    for rel, canonical in SHIMS.items():
        failures.extend(_validate_shim(ROOT / rel, canonical))

    if failures:
        print("wrapper integrity check failed:")
        for msg in failures:
            print(f" - {msg}")
        return 1

    print("wrapper integrity check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
