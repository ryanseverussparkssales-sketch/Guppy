from __future__ import annotations

import hashlib
import json
import os
import threading
import time

from src.guppy.paths import RUNTIME_DIR
from utils.db_utils import open_db as _open_db

_RESPONSE_CACHE: dict[str, tuple[str, float]] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_DB = RUNTIME_DIR / "response_cache.sqlite3"
_CACHE_TTL = max(0, int(os.environ.get("GUPPY_RESPONSE_CACHE_TTL", os.environ.get("GUPPY_CACHE_TTL", "300"))))
_CACHE_MAX = max(1, int(os.environ.get("GUPPY_RESPONSE_CACHE_MAX", os.environ.get("GUPPY_CACHE_MAX", "100"))))


def response_cache_enabled() -> bool:
    return _CACHE_TTL > 0


def build_response_cache_key(
    *,
    message: str,
    system_prompt: str,
    mode: str = "auto",
    instance_name: str | None = None,
    instance_type: str | None = None,
) -> str:
    payload = {
        "message": (message or "").strip(),
        "system_prompt": (system_prompt or "").strip(),
        "mode": (mode or "auto").strip().lower(),
        "instance_name": (instance_name or "").strip(),
        "instance_type": (instance_type or "").strip(),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _cache_init() -> None:
    _CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
    with _open_db(_CACHE_DB) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS response_cache (
                cache_key TEXT PRIMARY KEY,
                response_text TEXT NOT NULL,
                created_ts REAL NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_response_cache_ts ON response_cache(created_ts)")


def get_cached_response(cache_key: str) -> str | None:
    if not response_cache_enabled() or not cache_key:
        return None

    now = time.time()
    entry = _RESPONSE_CACHE.get(cache_key)
    if entry:
        cached_text, cached_ts = entry
        if now - cached_ts < _CACHE_TTL:
            return cached_text
        _RESPONSE_CACHE.pop(cache_key, None)

    with _CACHE_LOCK:
        _cache_init()
        with _open_db(_CACHE_DB) as conn:
            row = conn.execute(
                "SELECT response_text, created_ts FROM response_cache WHERE cache_key=?",
                (cache_key,),
            ).fetchone()
            if not row:
                return None
            cached_text, cached_ts = row
            if now - float(cached_ts) >= _CACHE_TTL:
                conn.execute("DELETE FROM response_cache WHERE cache_key=?", (cache_key,))
                conn.commit()
                return None
            _RESPONSE_CACHE[cache_key] = (str(cached_text), float(cached_ts))
            return str(cached_text)


def set_cached_response(cache_key: str, response_text: str) -> None:
    if not response_cache_enabled() or not cache_key or not response_text:
        return

    now = time.time()
    _RESPONSE_CACHE[cache_key] = (response_text, now)
    if len(_RESPONSE_CACHE) > _CACHE_MAX:
        oldest = min(_RESPONSE_CACHE, key=lambda key: _RESPONSE_CACHE[key][1])
        _RESPONSE_CACHE.pop(oldest, None)

    with _CACHE_LOCK:
        _cache_init()
        with _open_db(_CACHE_DB) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO response_cache (cache_key, response_text, created_ts) VALUES (?, ?, ?)",
                (cache_key, response_text, now),
            )
            conn.execute("DELETE FROM response_cache WHERE created_ts < ?", (now - _CACHE_TTL,))
            conn.execute(
                "DELETE FROM response_cache WHERE cache_key NOT IN "
                "(SELECT cache_key FROM response_cache ORDER BY created_ts DESC LIMIT ?)",
                (_CACHE_MAX,),
            )
            conn.commit()
