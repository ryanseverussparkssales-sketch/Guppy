"""Semantic memory for Guppy with dual backends.

Default backend: SQLite + llamacpp embeddings (stable).
Optional backend: ChromaDB + llamacpp embeddings (opt-in, hardened settings).

Embedding endpoint: OpenAI-compat /v1/embeddings server (default localhost:8087).
Override with GUPPY_EMBED_BASE_URL env var.
When the embed server is offline, semantic memory degrades gracefully
(operations log a warning and return empty results rather than crashing).
When embeddings are unavailable, recall falls back to lexical matching so memory
remains usable (lower precision).

Select backend with env var:
- GUPPY_SEMANTIC_BACKEND=sqlite (default)
- GUPPY_SEMANTIC_BACKEND=chroma
"""

from __future__ import annotations

import json
import logging
import math
import os
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

from src.guppy.paths import CHROMA_DIR, MEMORY_DB_PATH
from src.guppy.memory.backend_adapter import get_memory_backend_id, get_memory_backend_impl
from src.guppy.memory.mempalace_adapter import mempalace_recall, mempalace_remember
from utils.db_utils import open_db as _open_db

import requests

DB_PATH = MEMORY_DB_PATH
EMBED_MODEL = os.environ.get("GUPPY_EMBED_MODEL", "hermes-3-8b-lorablated").strip() or "hermes-3-8b-lorablated"
CHROMA_PATH = CHROMA_DIR
# Override to point at any OpenAI-compat embedding server: GUPPY_EMBED_BASE_URL=http://127.0.0.1:8087
_EMBED_BASE_URL = os.environ.get("GUPPY_EMBED_BASE_URL", "http://localhost:8087").strip().rstrip("/")
_EMBED_DISABLED_UNTIL: float = 0.0
_EMBED_DISABLE_LOCK: threading.Lock = threading.Lock()


def _embed_temporarily_disabled() -> bool:
    return time.monotonic() < _EMBED_DISABLED_UNTIL


def _disable_embed_for(seconds: float, reason: str) -> None:
    global _EMBED_DISABLED_UNTIL
    deadline = time.monotonic() + max(1.0, seconds)
    with _EMBED_DISABLE_LOCK:
        if deadline > _EMBED_DISABLED_UNTIL:
            _EMBED_DISABLED_UNTIL = deadline
    logger.info("Semantic embeddings temporarily disabled for %.0fs: %s", seconds, reason)


def _backend() -> str:
    return get_memory_backend_impl()


def _backend_id() -> str:
    return get_memory_backend_id()


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
    c.execute("CREATE INDEX IF NOT EXISTS idx_semantic_key ON semantic_memory(memory_key)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_semantic_category ON semantic_memory(category)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_semantic_created ON semantic_memory(created)")
    return c


def _is_openai_compat_embed() -> bool:
    """Always True — we only support OpenAI-compat /v1/embeddings now."""
    return True


def _embed_text(text: str) -> list[float]:
    text = (text or "").strip()
    if not text:
        raise RuntimeError("Cannot embed empty text")
    if _embed_temporarily_disabled():
        return []

    try:
        r = requests.post(
            f"{_EMBED_BASE_URL}/v1/embeddings",
            json={"model": EMBED_MODEL, "input": text},
            timeout=45,
        )
        r.raise_for_status()
        data = r.json()
        emb = (data.get("data") or [{}])[0].get("embedding") or []
        if emb:
            return [float(x) for x in emb]
        raise RuntimeError("Embedding response missing embedding vector")
    except requests.RequestException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in {400, 404, 405, 501}:
            _disable_embed_for(600.0, f"unsupported embeddings endpoint ({status})")
        else:
            _disable_embed_for(30.0, "embed server unreachable")
        logger.warning(
            "Embed server unreachable at %s — semantic memory degraded: %s",
            _EMBED_BASE_URL, exc,
        )
        return []


def _embed_texts(texts: list[str]) -> list[list[float]]:
    cleaned = [str(t or "").strip() for t in texts]
    cleaned = [t for t in cleaned if t]
    if not cleaned:
        raise RuntimeError("Cannot embed empty text list")
    if _embed_temporarily_disabled():
        return [[] for _ in cleaned]

    if _is_openai_compat_embed():
        try:
            r = requests.post(
                f"{_EMBED_BASE_URL}/v1/embeddings",
                json={"model": EMBED_MODEL, "input": cleaned},
                timeout=60,
            )
            r.raise_for_status()
            data = r.json()
            items = data.get("data") or []
            embs = [item.get("embedding") or [] for item in items]
            if embs and all(embs):
                return [[float(x) for x in row] for row in embs]
        except requests.RequestException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in {400, 404, 405, 501}:
                _disable_embed_for(600.0, f"unsupported embeddings endpoint ({status})")
            else:
                _disable_embed_for(30.0, "embed server unreachable")
            logger.warning(
                "Embed server unreachable at %s — semantic memory degraded: %s",
                _EMBED_BASE_URL, exc,
            )
            return [[] for _ in cleaned]
        raise RuntimeError("Batch embedding response malformed")

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


def _simple_text_score(query: str, key: str, value: str) -> float:
    q = query.lower().strip()
    if not q:
        return 0.0
    text = f"{key} {value}".lower()
    if q in text:
        return 1.0 + (text.count(q) * 0.1)
    tokens = [t for t in q.split() if len(t) > 2]
    if not tokens:
        return 0.0
    hits = sum(1 for t in tokens if t in text)
    return float(hits) / float(len(tokens)) if hits else 0.0


def _lexical_recall(rows: list[tuple], query: str, limit: int) -> str:
    scored = []
    for key, row_cat, value, _emb_json in rows:
        score = _simple_text_score(query, key, value)
        if score <= 0:
            continue
        scored.append((score, key, row_cat, value))
    if not scored:
        return "Nothing found in semantic memory."
    top = sorted(scored, key=lambda x: x[0], reverse=True)[:limit]
    lines = ["Semantic recall results (lexical):"]
    for score, key, row_cat, value in top:
        lines.append(f"- {key} [{row_cat}] ({score:.3f}): {value}")
    return "\n".join(lines)


class _LlamacppEmbeddingFunction:
    """Chroma-compatible embedding function for llamacpp /v1/embeddings."""

    def name(self) -> str:
        return f"llamacpp-{EMBED_MODEL}"

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
    return client.get_or_create_collection("guppy_memory", embedding_function=_LlamacppEmbeddingFunction())


def _remember_sqlite(k: str, v: str, c: str) -> str:
    emb = _embed_text(v)
    conn = _conn()
    try:
        created = datetime.now().isoformat()
        latest = conn.execute(
            "SELECT id FROM semantic_memory WHERE memory_key=? ORDER BY id DESC LIMIT 1",
            (k,),
        ).fetchone()
        if latest:
            keep_id = int(latest[0])
            conn.execute(
                """
                UPDATE semantic_memory
                SET category=?, value=?, embedding_json=?, created=?
                WHERE id=?
                """,
                (c, v, json.dumps(emb), created, keep_id),
            )
            conn.execute("DELETE FROM semantic_memory WHERE memory_key=? AND id<>?", (k, keep_id))
        else:
            conn.execute(
                "INSERT INTO semantic_memory (memory_key, category, value, embedding_json, created) VALUES (?,?,?,?,?)",
                (k, c, v, json.dumps(emb), created),
            )
        conn.commit()
    finally:
        conn.close()
    return f"Stored in semantic memory: {k}"


def _recall_sqlite(q: str, limit: int, cat: str) -> str:
    q_emb = _embed_text(q)
    conn = _conn()
    try:
        latest_rows_sql = """
            SELECT s.memory_key, s.category, s.value, s.embedding_json
            FROM semantic_memory s
            JOIN (
                SELECT memory_key, MAX(id) AS max_id
                FROM semantic_memory
                GROUP BY memory_key
            ) latest
              ON latest.max_id = s.id
        """
        if cat:
            rows = conn.execute(
                latest_rows_sql + " WHERE s.category=? ORDER BY s.id DESC LIMIT 1000",
                (cat,),
            ).fetchall()
        else:
            rows = conn.execute(
                latest_rows_sql + " ORDER BY s.id DESC LIMIT 1000"
            ).fetchall()
    finally:
        conn.close()

    if not q_emb:
        return _lexical_recall(rows, q, limit)

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
        backend = _backend()
        if backend == "mempalace":
            return mempalace_remember(k, v, c)
        if backend == "chroma":
            return _remember_chroma(k, v, c)
        return _remember_sqlite(k, v, c)
    except Exception as e:
        return (
            f"Error: semantic remember failed ({_backend_id()}). {e}. "
            f"Ensure the llama.cpp embedding server is running at {_EMBED_BASE_URL} "
            f"with model '{EMBED_MODEL}'."
        )


def recall_semantic(query: str, n: int = 5, category: str = "") -> str:
    q = (query or "").strip()
    if not q:
        return "Error: query is required for semantic recall."

    limit = max(1, min(int(n or 5), 20))
    cat = (category or "").strip()

    try:
        backend = _backend()
        if backend == "mempalace":
            return mempalace_recall(q, n=limit, category=cat)
        if backend == "chroma":
            return _recall_chroma(q, limit, cat)
        return _recall_sqlite(q, limit, cat)
    except Exception as e:
        return (
            f"Error: semantic recall failed ({_backend_id()}). {e}. "
            f"Ensure the llama.cpp embedding server is running at {_EMBED_BASE_URL} "
            f"with model '{EMBED_MODEL}'."
        )


def build_semantic_prompt_context(query: str, n: int = 4, category: str = "") -> str:
    """Return a prompt-ready semantic memory block or an empty string."""
    recalled = recall_semantic(query, n=n, category=category)
    if not recalled or recalled.startswith("Nothing found") or recalled.startswith("Error:"):
        return ""
    return f"[Relevant Memory]\n{recalled}"


def migrate_sqlite_to_chroma() -> str:
    """One-time migration: copy all SQLite semantic memories into Chroma.

    Safe to re-run — Chroma upsert by key is idempotent.
    Requires an OpenAI-compatible llama.cpp embedding endpoint and
    GUPPY_SEMANTIC_BACKEND=chroma.
    """
    conn = _conn()
    try:
        rows = conn.execute(
            """
            SELECT s.memory_key, s.category, s.value
            FROM semantic_memory s
            JOIN (
                SELECT memory_key, MAX(id) AS max_id
                FROM semantic_memory
                GROUP BY memory_key
            ) latest
              ON latest.max_id = s.id
            ORDER BY s.id
            """
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
