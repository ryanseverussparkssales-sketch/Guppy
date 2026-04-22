from __future__ import annotations

import os

BACKEND_ALIASES = {
    "sqlite": "semantic-sqlite",
    "semantic-sqlite": "semantic-sqlite",
    "chroma": "semantic-chroma",
    "semantic-chroma": "semantic-chroma",
    "mempalace": "mempalace-adapter",
    "mempalace-adapter": "mempalace-adapter",
}

BACKEND_IMPLEMENTATIONS = {
    "semantic-sqlite": "sqlite",
    "semantic-chroma": "chroma",
    "mempalace-adapter": "mempalace",
}


def normalize_memory_backend(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    return BACKEND_ALIASES.get(value, "semantic-sqlite")


def get_memory_backend_id(raw: str | None = None) -> str:
    if raw is None:
        raw = os.environ.get("GUPPY_SEMANTIC_BACKEND", "sqlite")
    return normalize_memory_backend(raw)


def get_memory_backend_impl(raw: str | None = None) -> str:
    return BACKEND_IMPLEMENTATIONS[get_memory_backend_id(raw)]
