from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
PACKAGE_ROOT = SRC_ROOT / "guppy"

RUNTIME_DIR = REPO_ROOT / "runtime"
CONFIG_DIR = REPO_ROOT / "config"


def _resolve_path(raw: str) -> Path:
    return Path(raw).expanduser().resolve()


def _default_user_data_dir() -> Path:
    configured = (os.environ.get("GUPPY_USER_DATA_DIR", "") or "").strip()
    if configured:
        return _resolve_path(configured)
    local_app_data = (os.environ.get("LOCALAPPDATA", "") or "").strip()
    if local_app_data:
        return _resolve_path(local_app_data) / "Guppy"
    if os.name == "nt":
        return Path.home().resolve() / "AppData" / "Local" / "Guppy"
    return Path.home().resolve() / ".guppy"


def _env_path(name: str, default: Path) -> Path:
    configured = (os.environ.get(name, "") or "").strip()
    if configured:
        return _resolve_path(configured)
    return default.resolve()


USER_DATA_DIR = _default_user_data_dir().resolve()
MEMORY_DB_PATH = _env_path("GUPPY_MEMORY_DB_PATH", USER_DATA_DIR / "guppy_memory.db")
LIBRARY_DB_PATH = _env_path("GUPPY_LIBRARY_DB_PATH", USER_DATA_DIR / "library.db")
USER_MEMORY_DIR = _env_path("GUPPY_MEMORY_DIR", USER_DATA_DIR / "memory")
USER_INDEX_DIR = _env_path("GUPPY_INDEX_DIR", USER_DATA_DIR / "indexes")
USER_ARTIFACTS_DIR = _env_path("GUPPY_ARTIFACTS_DIR", USER_DATA_DIR / "artifacts")
CHROMA_DIR = _env_path("GUPPY_CHROMA_PATH", USER_INDEX_DIR / "semantic-chroma")
MEMPALACE_DIR = _env_path("GUPPY_DEFAULT_MEMPALACE_DIR", USER_MEMORY_DIR / "mempalace")
LIBRARY_INDEX_DIR = _env_path("GUPPY_LIBRARY_INDEX_DIR", USER_INDEX_DIR / "library")
LIBRARY_ARTIFACTS_DIR = _env_path("GUPPY_LIBRARY_ARTIFACTS_DIR", USER_ARTIFACTS_DIR / "library")


def ensure_user_data_dir() -> Path:
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return USER_DATA_DIR


def ensure_user_storage_dirs() -> dict[str, Path]:
    ensure_user_data_dir()
    dirs = {
        "memory": USER_MEMORY_DIR,
        "indexes": USER_INDEX_DIR,
        "artifacts": USER_ARTIFACTS_DIR,
        "semantic_chroma": CHROMA_DIR,
        "mempalace": MEMPALACE_DIR,
        "library_indexes": LIBRARY_INDEX_DIR,
        "library_artifacts": LIBRARY_ARTIFACTS_DIR,
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs
