"""
settings_io.py

Lane: TR54-C4
Responsibilities:
  - Atomic read/write of runtime settings JSON
  - Validate against RuntimeSettingsSchema on load and save
  - In-memory cache with explicit invalidation
  - Field ownership enforcement: callers must own the key they write
  - Secrets never logged
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

from .runtime_settings_schema import FieldOwner, get_schema

logger = logging.getLogger("launcher.config.settings_io")

_DEFAULT_SETTINGS_PATH = Path.home() / ".guppy" / "runtime_settings.json"

_cache: dict[str, Any] = {}
_cache_loaded = False
_cache_path: Optional[Path] = None


def _resolve_path(path: Optional[Path | str]) -> Path:
    if path is not None:
        return Path(path)
    env_path = os.environ.get("GUPPY_SETTINGS_PATH", "")
    if env_path:
        return Path(env_path)
    return _DEFAULT_SETTINGS_PATH


def load(path: Optional[Path | str] = None) -> dict[str, Any]:
    global _cache, _cache_loaded, _cache_path
    resolved = _resolve_path(path)
    _cache_path = resolved

    if not resolved.exists():
        _cache = {}
        _cache_loaded = True
        return {}

    try:
        raw = resolved.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            logger.warning("settings_io: settings file is not a JSON object, ignoring")
            _cache = {}
            _cache_loaded = True
            return {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("settings_io: failed to load settings from %s: %s", resolved, exc)
        _cache = {}
        _cache_loaded = True
        return {}

    schema = get_schema()
    coerced: dict[str, Any] = {}
    for key, value in data.items():
        if schema.is_secret(key):
            coerced[key] = value
        else:
            coerced[key] = schema.coerce(key, value)

    _cache = coerced
    _cache_loaded = True
    return dict(_cache)


def get(key: str, default: Any = None, path: Optional[Path | str] = None) -> Any:
    global _cache_loaded
    if not _cache_loaded:
        load(path)
    value = _cache.get(key)
    if value is None:
        schema = get_schema()
        schema_default = schema.default_value(key)
        return schema_default if schema_default is not None else default
    return value


def set_value(
    key: str,
    value: Any,
    owner: FieldOwner,
    path: Optional[Path | str] = None,
) -> tuple[bool, str]:
    schema = get_schema()
    field_owner = schema.owner_for(key)
    if field_owner is not None and field_owner != owner:
        return False, f"Key '{key}' is owned by {field_owner.value}, not {owner.value}."

    ok, error = schema.validate(key, value)
    if not ok:
        return False, error

    coerced = schema.coerce(key, value)
    _cache[key] = coerced

    resolved = _resolve_path(path)
    _persist(resolved)
    return True, ""


def set_many(
    updates: dict[str, Any],
    owner: FieldOwner,
    path: Optional[Path | str] = None,
) -> tuple[bool, list[str]]:
    schema = get_schema()
    errors: list[str] = []

    validated: dict[str, Any] = {}
    for key, value in updates.items():
        field_owner = schema.owner_for(key)
        if field_owner is not None and field_owner != owner:
            errors.append(f"Key '{key}' is owned by {field_owner.value}, not {owner.value}.")
            continue
        ok, error = schema.validate(key, value)
        if not ok:
            errors.append(error)
            continue
        validated[key] = schema.coerce(key, value)

    if errors:
        return False, errors

    _cache.update(validated)
    resolved = _resolve_path(path)
    _persist(resolved)
    return True, []


def invalidate() -> None:
    global _cache, _cache_loaded
    _cache = {}
    _cache_loaded = False


def _persist(target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    schema = get_schema()
    sanitized = {
        key: ("***" if schema.is_secret(key) else value)
        for key, value in _cache.items()
    }
    logger.debug("settings_io: persisting %d keys to %s", len(_cache), target)

    try:
        fd, tmp_path = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(_cache, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
            os.replace(tmp_path, target)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except OSError as exc:
        logger.error("settings_io: atomic write failed for %s: %s", target, exc)
