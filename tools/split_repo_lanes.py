from __future__ import annotations

import argparse
import shutil
from pathlib import Path

IGNORE_NAMES = {
    ".git",
    ".venv",
    ".pytest_cache",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".tmp",
    "dist",
    "build",
}

LANES: dict[str, list[str]] = {
    "backend-working": [
        "app.py",
        "conftest.py",
        "guppy_api.py",
        "guppy_hub.py",
        "pyproject.toml",
        "pytest.ini",
        "requirements.txt",
        "requirements-dev.txt",
        "requirements-optional.txt",
        "README.md",
        "ROADMAP.md",
        "entities.json",
        "mempalace.yaml",
        "src",
        "api",
        "guppy_core",
        "utils",
        "tools",
        "tests",
        "config",
        "runtime",
        "instructions",
        "bin",
    ],
    "qt-creator-ui": [
        "compat_shims/launcher_ui/ui",
        "compat_shims/launcher_ui/guppy_launcher.py",
        "compat_shims/launcher_ui/launcher_app.py",
        "compat_shims/launcher_ui/tests",
        "assets",
        ".qtcreator",
        "src/guppy/apps/process_guard.py",
        "src/guppy/apps/__init__.py",
        "requirements.txt",
        "requirements-optional.txt",
        "pyproject.toml",
    ],
    "archive-clutter": [
        "docs/archive",
        "docs/generated",
        "compat_shims/legacy_surfaces",
        "compat_shims/launcher_ui",
    ],
}


def _ignore(_dir: str, names: list[str]) -> set[str]:
    return {name for name in names if name in IGNORE_NAMES}


def _copy_path(repo_root: Path, rel_path: str, lane_root: Path) -> str:
    src = repo_root / rel_path
    dest = lane_root / rel_path

    if not src.exists():
        return f"missing: {rel_path}"

    dest.parent.mkdir(parents=True, exist_ok=True)

    if src.is_dir():
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest, ignore=_ignore)
        return f"copied dir: {rel_path}"

    shutil.copy2(src, dest)
    return f"copied file: {rel_path}"


def build_lane(repo_root: Path, out_root: Path, lane_name: str, rel_paths: list[str]) -> list[str]:
    lane_root = out_root / lane_name
    lane_root.mkdir(parents=True, exist_ok=True)

    results: list[str] = []
    for rel_path in rel_paths:
        results.append(_copy_path(repo_root, rel_path, lane_root))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Split this repo into backend/ui/archive lanes")
    parser.add_argument(
        "--out",
        default="splits",
        help="Output directory where lane folders will be created (default: splits)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete existing output folder before regenerating",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    out_root = (repo_root / args.out).resolve()

    if args.clean and out_root.exists():
        shutil.rmtree(out_root)

    out_root.mkdir(parents=True, exist_ok=True)

    for lane_name, rel_paths in LANES.items():
        print(f"\n== {lane_name} ==")
        for line in build_lane(repo_root, out_root, lane_name, rel_paths):
            print(line)

    print(f"\nSplit lanes generated under: {out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
