"""Fail CI if core API surface modules are broken or missing expected exports.

Validates that the key production modules are importable and expose their
required public symbols. This catches accidental deletions and broken imports
before they reach the smoke test suite.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (module_dotpath, [required_symbols])
_SURFACE_CONTRACTS: list[tuple[str, list[str]]] = [
    ("src.guppy.api.auth", ["get_token_expiry", "validate_environment"]),
    ("src.guppy.api.routes_realtime", ["build_realtime_router"]),
    ("src.guppy.api.realtime_inference_support", ["stream_unified_inference"]),
    ("src.guppy.api.routes_chat_history", ["ChatHistoryDB"]),
    ("src.guppy.api.routes_settings", ["SettingsDB"]),
    ("src.guppy.api.routes_workspaces", ["WorkspaceDB"]),
    ("src.guppy.paths", ["ensure_user_data_dir"]),
]

# Add repo root to sys.path so module dotpaths resolve
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def check() -> list[str]:
    violations: list[str] = []

    for module_path, required_symbols in _SURFACE_CONTRACTS:
        try:
            mod = importlib.import_module(module_path)
        except Exception as exc:
            violations.append(f"{module_path}: import failed — {exc}")
            continue

        for symbol in required_symbols:
            if not hasattr(mod, symbol):
                violations.append(f"{module_path}: missing expected export {symbol!r}")

    return violations


def main() -> None:
    violations = check()
    if violations:
        print(f"core surface integrity check FAILED ({len(violations)} violation(s)):")
        for v in violations:
            print(f"  {v}")
        sys.exit(1)
    print("core surface integrity check passed")


if __name__ == "__main__":
    main()
