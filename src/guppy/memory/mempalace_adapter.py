from __future__ import annotations

import json
import math
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from src.guppy.paths import RUNTIME_DIR
import requests

DEFAULT_PALACE_PATH = RUNTIME_DIR / "local_memory" / "palace"
EMBED_MODEL = "nomic-embed-text"
DB_FILENAME = "mempalace_drawers.sqlite3"

def get_mempalace_path() -> Path:
    raw = (os.environ.get("GUPPY_MEMPALACE_PATH", "") or "").strip()
    return Path(raw).expanduser().resolve() if raw else DEFAULT_PALACE_PATH.resolve()


def _embed_texts(texts: list[str]) -> list[list[float]]:
    cleaned = [str(text or "").strip() for text in texts]
    cleaned = [text for text in cleaned if text]
    if not cleaned:
        raise RuntimeError("Cannot embed empty text list")

    try:
        response = requests.post(
            "http://localhost:11434/api/embed",
            json={"model": EMBED_MODEL, "input": cleaned},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        embeddings = payload.get("embeddings")
        if embeddings and isinstance(embeddings, list):
            return [[float(value) for value in row] for row in embeddings]
    except Exception:
        pass

    vectors: list[list[float]] = []
    for text in cleaned:
        response = requests.post(
            "http://localhost:11434/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text},
            timeout=45,
        )
        response.raise_for_status()
        payload = response.json()
        embedding = payload.get("embedding")
        if not embedding:
            raise RuntimeError("Ollama embedding response missing embedding vector")
        vectors.append([float(value) for value in embedding])
    return vectors


def _db_path() -> Path:
    return get_mempalace_path() / DB_FILENAME


def _conn() -> sqlite3.Connection:
    db_path = _db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mempalace_drawers (
            id TEXT PRIMARY KEY,
            wing TEXT NOT NULL,
            room TEXT NOT NULL,
            memory_key TEXT NOT NULL,
            source_file TEXT NOT NULL,
            created TEXT NOT NULL,
            value TEXT NOT NULL,
            embedding_json TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mempalace_wing_room ON mempalace_drawers(wing, room)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mempalace_created ON mempalace_drawers(created DESC)")
    return conn


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    width = min(len(a), len(b))
    if width == 0:
        return 0.0
    a = a[:width]
    b = b[:width]
    dot = sum(left * right for left, right in zip(a, b))
    norm_a = math.sqrt(sum(value * value for value in a))
    norm_b = math.sqrt(sum(value * value for value in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def mempalace_status() -> dict[str, Any]:
    palace_path = get_mempalace_path()
    try:
        conn = _conn()
        try:
            drawer_count = int(conn.execute("SELECT COUNT(*) FROM mempalace_drawers").fetchone()[0])
        finally:
            conn.close()
        return {
            "ok": True,
            "palace_path": str(palace_path),
            "drawer_count": drawer_count,
            "embedding_model": EMBED_MODEL,
        }
    except Exception as exc:
        return {
            "ok": False,
            "palace_path": str(palace_path),
            "error": str(exc),
        }


def mempalace_remember(key: str, value: str, category: str = "general") -> str:
    k = (key or "").strip()
    v = (value or "").strip()
    c = (category or "general").strip() or "general"
    if not k or not v:
        return "Error: key and value are required for MemPalace memory."

    try:
        doc_id = f"guppy::{c}::{k}"
        embedding = _embed_texts([v])[0]
        conn = _conn()
        try:
            conn.execute(
                """
                INSERT INTO mempalace_drawers (
                    id, wing, room, memory_key, source_file, created, value, embedding_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    wing=excluded.wing,
                    room=excluded.room,
                    memory_key=excluded.memory_key,
                    source_file=excluded.source_file,
                    created=excluded.created,
                    value=excluded.value,
                    embedding_json=excluded.embedding_json
                """,
                (
                    doc_id,
                    "guppy",
                    c,
                    k,
                    f"{k}.txt",
                    datetime.now().isoformat(),
                    v,
                    json.dumps(embedding),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return f"Stored in MemPalace memory: {k}"
    except Exception as exc:
        return f"Error: MemPalace remember failed (mempalace-adapter). {exc}"


def mempalace_recall(query: str, n: int = 5, category: str = "") -> str:
    q = (query or "").strip()
    if not q:
        return "Error: query is required for MemPalace recall."

    try:
        room = (category or "").strip() or None
        query_embedding = _embed_texts([q])[0]
        conn = _conn()
        try:
            if room:
                rows = conn.execute(
                    """
                    SELECT memory_key, room, value, embedding_json
                    FROM mempalace_drawers
                    WHERE wing = ? AND room = ?
                    ORDER BY created DESC
                    LIMIT 1000
                    """,
                    ("guppy", room),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT memory_key, room, value, embedding_json
                    FROM mempalace_drawers
                    WHERE wing = ?
                    ORDER BY created DESC
                    LIMIT 1000
                    """,
                    ("guppy",),
                ).fetchall()
        finally:
            conn.close()
        scored: list[tuple[float, str, str, str]] = []
        for memory_key, hit_room, value, embedding_json in rows:
            try:
                score = _cosine(query_embedding, json.loads(embedding_json))
            except Exception:
                continue
            scored.append((score, memory_key, hit_room, value))
        if not scored:
            return "Nothing found in MemPalace memory."
        lines = ["MemPalace recall results:"]
        for score, memory_key, hit_room, value in sorted(scored, key=lambda item: item[0], reverse=True)[: max(1, min(int(n or 5), 20))]:
            snippet = str(value or "").strip().replace("\n", " ")
            if len(snippet) > 240:
                snippet = snippet[:237] + "..."
            lines.append(
                f"- {memory_key} "
                f"[{hit_room or 'general'}] ({score:.3f}): {snippet}"
            )
        return "\n".join(lines)
    except Exception as exc:
        return f"Error: MemPalace recall failed (mempalace-adapter). {exc}"


def mempalace_wake_up(wing: str = "guppy") -> str:
    try:
        conn = _conn()
        try:
            rows = conn.execute(
                """
                SELECT room, value
                FROM mempalace_drawers
                WHERE wing = ?
                ORDER BY created DESC
                LIMIT 8
                """,
                (wing,),
            ).fetchall()
        finally:
            conn.close()
        if not rows:
            return "## L1 - No palace found. Run: mempalace mine <dir>"
        lines = ["## L1 - ESSENTIAL STORY"]
        for room, value in rows[:8]:
            snippet = str(value or "").strip().replace("\n", " ")
            if len(snippet) > 180:
                snippet = snippet[:177] + "..."
            lines.append(f"- [{room}] {snippet}")
        return "\n".join(lines)
    except Exception as exc:
        return f"Error: MemPalace wake-up failed (mempalace-adapter). {exc}"
