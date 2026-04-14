"""Semantic memory for Guppy with dual backends.

Default backend: SQLite + local Ollama embeddings (stable).
Optional backend: ChromaDB + local Ollama embeddings (opt-in, hardened settings).

Select backend with env var:
- GUPPY_SEMANTIC_BACKEND=sqlite (default)
- GUPPY_SEMANTIC_BACKEND=chroma
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from src.guppy.paths import CHROMA_DIR, MEMORY_DB_PATH
from utils.db_utils import open_db as _open_db

import requests

DB_PATH = MEMORY_DB_PATH
EMBED_MODEL = "nomic-embed-text"
CHROMA_PATH = CHROMA_DIR


def _backend() -> str:
    return (os.environ.get("GUPPY_SEMANTIC_BACKEND", "sqlite") or "sqlite").strip().lower()


def _conn() -> sqlite3.Connection:
    c = _open_db(DB_PATH)
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS semantic_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_key TEXT NOT NULL,
            category TEXT NOT NULL,
            value TEXT NOT NULL,
            embedding_json TEXT NOT NULL,
            created TEXT NOT NULL
        )
        """
    )
    c.execute("CREATE INDEX IF NOT EXISTS idx_semantic_category ON semantic_memory(category)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_semantic_created ON semantic_memory(created)")
    return c


def _embed_text(text: str) -> list[float]:
    text = (text or "").strip()
    if not text:
        raise RuntimeError("Cannot embed empty text")

    # Prefer modern batch endpoint
    try:
        r = requests.post(
            "http://localhost:11434/api/embed",
            json={"model": EMBED_MODEL, "input": [text]},
            timeout=45,
        )
        r.raise_for_status()
        data = r.json()
        emb = (data.get("embeddings") or [[]])[0]
        if emb:
            return [float(x) for x in emb]
    except Exception:
        pass

    # Back-compat endpoint
    r = requests.post(
        "http://localhost:11434/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": text},
        timeout=45,
    )
    r.raise_for_status()
    data = r.json()
    emb = data.get("embedding")
    if not emb:
        raise RuntimeError("Ollama embedding response missing embedding vector")
    return [float(x) for x in emb]


def _embed_texts(texts: list[str]) -> list[list[float]]:
    cleaned = [str(t or "").strip() for t in texts]
    cleaned = [t for t in cleaned if t]
    if not cleaned:
        raise RuntimeError("Cannot embed empty text list")

    try:
        r = requests.post(
            "http://localhost:11434/api/embed",
            json={"model": EMBED_MODEL, "input": cleaned},
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        embs = data.get("embeddings")
        if embs and isinstance(embs, list):
            return [[float(x) for x in row] for row in embs]
    except Exception:
        pass

    # Back-compat fallback (single call per text)
    return [_embed_text(t) for t in cleaned]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    a = a[:n]
    b = b[:n]
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


class _OllamaEmbeddingFunction:
    """Chroma-compatible embedding function without extra ollama Python package."""

    def name(self) -> str:
        return f"ollama-http-{EMBED_MODEL}"

    def __call__(self, input):
        texts = input if isinstance(input, list) else [str(input)]
        return _embed_texts([str(t) for t in texts])


def _get_chroma_collection():
    # Explicitly disable telemetry to avoid background posthog thread issues.
    os.environ.setdefault("ANONYMIZED_TELEMETRY", "FALSE")

    import chromadb
    from chromadb.config import Settings

    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    settings = Settings(
        is_persistent=True,
        persist_directory=str(CHROMA_PATH),
        anonymized_telemetry=False,
        allow_reset=False,
    )
    client = chromadb.PersistentClient(path=str(CHROMA_PATH), settings=settings)
    return client.get_or_create_collection("guppy_memory", embedding_function=_OllamaEmbeddingFunction())


def _remember_sqlite(k: str, v: str, c: str) -> str:
    emb = _embed_text(v)
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO semantic_memory (memory_key, category, value, embedding_json, created) VALUES (?,?,?,?,?)",
            (k, c, v, json.dumps(emb), datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()
    return f"Stored in semantic memory: {k}"


def _recall_sqlite(q: str, limit: int, cat: str) -> str:
    q_emb = _embed_text(q)
    conn = _conn()
    try:
        if cat:
            rows = conn.execute(
                "SELECT memory_key, category, value, embedding_json FROM semantic_memory WHERE category=? ORDER BY id DESC LIMIT 1000",
                (cat,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT memory_key, category, value, embedding_json FROM semantic_memory ORDER BY id DESC LIMIT 1000"
            ).fetchall()
    finally:
        conn.close()

    scored = []
    for key, row_cat, value, emb_json in rows:
        try:
            emb = json.loads(emb_json)
            score = _cosine(q_emb, emb)
            scored.append((score, key, row_cat, value))
        except Exception:
            continue

    if not scored:
        return "Nothing found in semantic memory."

    top = sorted(scored, key=lambda x: x[0], reverse=True)[:limit]
    lines = ["Semantic recall results:"]
    for score, key, row_cat, value in top:
        lines.append(f"- {key} [{row_cat}] ({score:.3f}): {value}")
    return "\n".join(lines)


def _remember_chroma(k: str, v: str, c: str) -> str:
    col = _get_chroma_collection()
    # Use key as ID so upsert truly replaces the existing document for this key.
    col.upsert(
        ids=[k],
        documents=[v],
        metadatas=[{"key": k, "category": c, "created": datetime.now().isoformat()}],
    )
    return f"Stored in semantic memory: {k}"


def _recall_chroma(q: str, limit: int, cat: str) -> str:
    col = _get_chroma_collection()
    where = {"category": cat} if cat else None
    results = col.query(query_texts=[q], n_results=limit, where=where)
    docs = (results.get("documents") or [[]])[0]
    metas = (results.get("metadatas") or [[]])[0]
    dists = (results.get("distances") or [[]])[0]

    if not docs:
        return "Nothing found in semantic memory."

    lines = ["Semantic recall results:"]
    for i, doc in enumerate(docs):
        meta = metas[i] if i < len(metas) and isinstance(metas[i], dict) else {}
        key = meta.get("key", "memory")
        row_cat = meta.get("category", "general")
        dist = dists[i] if i < len(dists) else 0.0
        # Approximate score from distance for readability
        score = 1.0 / (1.0 + float(dist)) if dist is not None else 0.0
        lines.append(f"- {key} [{row_cat}] ({score:.3f}): {str(doc).strip()}")
    return "\n".join(lines)


def remember_semantic(key: str, value: str, category: str = "general") -> str:
    k = (key or "").strip()
    v = (value or "").strip()
    c = (category or "general").strip() or "general"
    if not k or not v:
        return "Error: key and value are required for semantic memory."

    try:
        if _backend() == "chroma":
            return _remember_chroma(k, v, c)
        return _remember_sqlite(k, v, c)
    except Exception as e:
        return (
            f"Error: semantic remember failed ({_backend()}). {e}. "
            f"Ensure Ollama is running and model '{EMBED_MODEL}' is installed."
        )


def recall_semantic(query: str, n: int = 5, category: str = "") -> str:
    q = (query or "").strip()
    if not q:
        return "Error: query is required for semantic recall."

    limit = max(1, min(int(n or 5), 20))
    cat = (category or "").strip()

    try:
        if _backend() == "chroma":
            return _recall_chroma(q, limit, cat)
        return _recall_sqlite(q, limit, cat)
    except Exception as e:
        return (
            f"Error: semantic recall failed ({_backend()}). {e}. "
            f"Ensure Ollama is running and model '{EMBED_MODEL}' is installed."
        )


def migrate_sqlite_to_chroma() -> str:
    """One-time migration: copy all SQLite semantic memories into Chroma.

    Safe to re-run — Chroma upsert by key is idempotent.
    Requires Ollama running with nomic-embed-text and GUPPY_SEMANTIC_BACKEND=chroma.
    """
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT memory_key, category, value FROM semantic_memory ORDER BY id"
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return "No SQLite semantic memories to migrate."

    col = _get_chroma_collection()
    migrated = 0
    errors = 0
    for key, category, value in rows:
        try:
            col.upsert(
                ids=[key],
                documents=[value],
                metadatas=[{"key": key, "category": category, "created": datetime.now().isoformat()}],
            )
            migrated += 1
        except Exception as e:
            errors += 1
            print(f"  SKIP {key}: {e}")

    return f"Migration complete: {migrated} memories copied to Chroma, {errors} skipped."
