from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
PACKAGE_ROOT = SRC_ROOT / "guppy"

RUNTIME_DIR = REPO_ROOT / "runtime"
CONFIG_DIR = REPO_ROOT / "config"
CHROMA_DIR = REPO_ROOT / "chroma_db"

USER_DATA_DIR = Path.home() / "Guppy"
MEMORY_DB_PATH = USER_DATA_DIR / "guppy_memory.db"


def ensure_user_data_dir() -> Path:
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return USER_DATA_DIR
