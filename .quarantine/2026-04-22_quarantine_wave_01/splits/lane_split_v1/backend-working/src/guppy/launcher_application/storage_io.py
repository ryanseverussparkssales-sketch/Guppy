"""Launcher seam wrappers for safe JSON I/O and instance log access."""
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from utils.safe_io import (
        append_jsonl as _append_jsonl,
        read_json_dict as _read_json_dict,
        read_jsonl_tail as _read_jsonl_tail,
        write_json_atomic as _write_json_atomic,
    )
except Exception:
    def _append_jsonl(_path: Path, _record: dict[str, Any]) -> None:  # type: ignore[misc]
        return None

    def _read_json_dict(_path: Path) -> dict[str, Any]:  # type: ignore[misc]
        return {}

    def _read_jsonl_tail(_path: Path, limit: int = 50) -> list[dict[str, Any]]:  # type: ignore[misc]
        return []

    def _write_json_atomic(_path: Path, _payload: dict[str, Any]) -> bool:  # type: ignore[misc]
        return False


try:
    from utils.instance_logger import (
        append_instance_log as _append_instance_log,
        read_instance_log_tail as _read_instance_log_tail,
    )

    _INSTANCE_LOGGER_BACKEND = True
except Exception:
    _INSTANCE_LOGGER_BACKEND = False

    def _append_instance_log(*_args: Any, **_kwargs: Any) -> None:  # type: ignore[misc]
        return None

    def _read_instance_log_tail(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:  # type: ignore[misc]
        return []


try:
    from utils import secret_store as _secret_store

    _SECRET_STORE_BACKEND = True
except Exception:
    _secret_store = None  # type: ignore[assignment]
    _SECRET_STORE_BACKEND = False


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    _append_jsonl(path, record)


def read_json_dict(path: Path) -> dict[str, Any]:
    payload = _read_json_dict(path)
    return payload if isinstance(payload, dict) else {}


def read_jsonl_tail(path: Path, limit: int = 50) -> list[dict[str, Any]]:
    payload = _read_jsonl_tail(path, limit=limit)
    return payload if isinstance(payload, list) else []


def write_json_atomic(path: Path, payload: dict[str, Any]) -> bool:
    return bool(_write_json_atomic(path, payload))


def append_instance_log(*args: Any, **kwargs: Any) -> None:
    _append_instance_log(*args, **kwargs)


def read_instance_log_tail(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
    payload = _read_instance_log_tail(*args, **kwargs)
    return payload if isinstance(payload, list) else []


def instance_logger_backend_available() -> bool:
    return _INSTANCE_LOGGER_BACKEND


def get_secret(name: str) -> str:
    if not _SECRET_STORE_BACKEND or _secret_store is None:
        return ""
    try:
        value = _secret_store.get_secret(name)
    except Exception:
        return ""
    return str(value).strip() if value else ""


def secret_store_backend_available() -> bool:
    return _SECRET_STORE_BACKEND


def secret_store_client() -> Any | None:
    return _secret_store if _SECRET_STORE_BACKEND else None
