"""
TTS Output Cache
=================

Caches synthesis results by content hash so repeated phrases skip
the synthesis step. LRU eviction with configurable max entries.
"""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from typing import Optional

from guppy.voice.core import TTSResult


class TTSCache:
    """Thread-safe LRU cache for TTSResult objects keyed by text+voice+provider."""

    def __init__(self, max_entries: int = 256):
        self._max_entries = max_entries
        self._cache: "OrderedDict[str, TTSResult]" = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _key(text: str, voice: Optional[str], provider: str) -> str:
        h = hashlib.sha256()
        h.update(provider.encode("utf-8"))
        h.update(b"\0")
        h.update((voice or "").encode("utf-8"))
        h.update(b"\0")
        h.update(text.encode("utf-8"))
        return h.hexdigest()

    def get(self, text: str, voice: Optional[str], provider: str) -> Optional[TTSResult]:
        key = self._key(text, voice, provider)
        with self._lock:
            result = self._cache.get(key)
            if result is None:
                self._misses += 1
                return None
            # LRU: move to end
            self._cache.move_to_end(key)
            self._hits += 1
            return result

    def put(self, text: str, voice: Optional[str], provider: str, result: TTSResult) -> None:
        if result.error:
            return  # don't cache errors
        key = self._key(text, voice, provider)
        with self._lock:
            self._cache[key] = result
            self._cache.move_to_end(key)
            while len(self._cache) > self._max_entries:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> dict:
        with self._lock:
            total = self._hits + self._misses
            return {
                "entries": len(self._cache),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / total if total else 0.0,
            }
