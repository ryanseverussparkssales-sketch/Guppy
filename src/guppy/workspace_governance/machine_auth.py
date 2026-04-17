"""Machine-auth storage helpers for connector/governance services."""

from __future__ import annotations

import os
from typing import Iterable

try:
    from utils import secret_store as _secret_store

    _SECRET_STORE_AVAILABLE = True
except Exception:
    _secret_store = None  # type: ignore[assignment]
    _SECRET_STORE_AVAILABLE = False


_KEYRING_PREFIX = "connector_secret:"


def keyring_key(secret_key: str, *, prefix: str = _KEYRING_PREFIX) -> str:
    return f"{str(prefix or _KEYRING_PREFIX).strip()}{str(secret_key or '').strip()}"


def read_machine_secret(secret_key: str, *, fallback: str | None = None, prefix: str = _KEYRING_PREFIX) -> str:
    key = str(secret_key or "").strip()
    default = fallback if fallback is not None else os.environ.get(key, "")
    if not key:
        return str(default or "")
    if _SECRET_STORE_AVAILABLE and _secret_store is not None:
        try:
            value = _secret_store.get_secret(keyring_key(key, prefix=prefix), fallback=default)
            return str(value or "")
        except Exception:
            return str(default or "")
    return str(default or "")


def write_machine_secret(secret_key: str, value: str, *, prefix: str = _KEYRING_PREFIX) -> bool:
    key = str(secret_key or "").strip()
    if not key or not _SECRET_STORE_AVAILABLE or _secret_store is None:
        return False
    try:
        return bool(_secret_store.set_secret(keyring_key(key, prefix=prefix), str(value or "")))
    except Exception:
        return False


def clear_machine_secret(secret_key: str, *, prefix: str = _KEYRING_PREFIX) -> bool:
    key = str(secret_key or "").strip()
    if not key or not _SECRET_STORE_AVAILABLE or _secret_store is None:
        return False
    try:
        return bool(_secret_store.delete_secret(keyring_key(key, prefix=prefix)))
    except Exception:
        return False


def secret_source(secret_key: str, *, prefix: str = _KEYRING_PREFIX) -> str:
    key = str(secret_key or "").strip()
    if not key:
        return "none"
    env_value = os.environ.get(key, "").strip()
    keyring_value = ""
    if _SECRET_STORE_AVAILABLE and _secret_store is not None:
        try:
            keyring_value = str(_secret_store.get_secret(keyring_key(key, prefix=prefix), fallback="") or "").strip()
        except Exception:
            keyring_value = ""
    if env_value and keyring_value:
        return "mixed"
    if keyring_value:
        return "keyring"
    if env_value:
        return "env"
    return "none"


def merge_secret_sources(values: Iterable[str]) -> str:
    normalized = [str(value or "").strip().lower() for value in values if str(value or "").strip()]
    unique = sorted(set(normalized))
    if not unique:
        return "none"
    if len(unique) == 1:
        return unique[0]
    return "mixed"


def secret_status(required_fields: list[str], *, prefix: str = _KEYRING_PREFIX) -> dict[str, object]:
    present_fields: list[str] = []
    missing_fields: list[str] = []
    field_sources: dict[str, str] = {}
    for field in required_fields:
        normalized = str(field or "").strip()
        if not normalized:
            continue
        value = read_machine_secret(normalized, prefix=prefix).strip()
        source = secret_source(normalized, prefix=prefix)
        if value:
            present_fields.append(normalized)
        else:
            missing_fields.append(normalized)
        field_sources[normalized] = source
    auth_state = (
        "ready"
        if required_fields and not missing_fields
        else "partial"
        if present_fields
        else "ready"
        if not required_fields
        else "missing"
    )
    return {
        "required_fields": list(required_fields),
        "present_fields": present_fields,
        "missing_fields": missing_fields,
        "field_sources": field_sources,
        "source": merge_secret_sources([field_sources.get(field, "") for field in present_fields]),
        "auth_state": auth_state,
    }
