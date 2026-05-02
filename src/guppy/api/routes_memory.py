"""Memory Browse API — CRUD over the semantic_memory SQLite table.

GET    /api/memory/entries            — list all entries (?category=&limit=100&offset=0)
GET    /api/memory/entries/search     — semantic/lexical search (?q=<query>&n=10)
POST   /api/memory/entries            — create entry: {key, value, category?}
DELETE /api/memory/entries/{key}      — delete one entry by key
DELETE /api/memory/entries            — clear all entries (requires ?confirm=true)
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.guppy.api.server_context import ServerContext
from src.guppy.memory.semantic import remember_semantic, recall_semantic, DB_PATH

logger = logging.getLogger(__name__)

_DB_PATH = str(DB_PATH)


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    from src.guppy.memory.semantic import _conn as _semantic_conn
    return _semantic_conn()


def _row(r: sqlite3.Row) -> dict[str, Any]:
    return {
        "key":      r["memory_key"],
        "category": r["category"],
        "value":    r["value"],
        "created":  r["created"],
    }


# ── Pydantic ───────────────────────────────────────────────────────────────────

class MemoryCreate(BaseModel):
    key:      str
    value:    str
    category: str = "general"


# ── Router ─────────────────────────────────────────────────────────────────────

def build_memory_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/memory", tags=["memory"])

    @router.get("/entries/search")
    def search_entries(
        q:        str = Query(..., min_length=1),
        n:        int = Query(10, ge=1, le=50),
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        raw = recall_semantic(q, n=n)
        # recall_semantic returns a formatted text string; parse it back into
        # structured entries so the UI can render cards.
        conn = _conn()
        try:
            # Fetch all latest entries to match against recalled keys
            rows = conn.execute(
                """
                SELECT s.memory_key, s.category, s.value, s.created
                FROM semantic_memory s
                JOIN (
                    SELECT memory_key, MAX(id) AS max_id
                    FROM semantic_memory
                    GROUP BY memory_key
                ) latest ON latest.max_id = s.id
                ORDER BY s.id DESC LIMIT 1000
                """
            ).fetchall()
        finally:
            conn.close()

        # Extract recalled keys from the formatted string
        recalled_keys: set[str] = set()
        for line in raw.splitlines():
            if line.startswith("- "):
                # Format: "- <key> [<cat>] (<score>): <value>"
                parts = line[2:].split(" [", 1)
                if parts:
                    recalled_keys.add(parts[0].strip())

        if not recalled_keys and (raw.startswith("Nothing found") or raw.startswith("Error:")):
            return {"entries": [], "total": 0, "raw": raw}

        entries = [_row(r) for r in rows if r["memory_key"] in recalled_keys]
        # Preserve recall order
        key_order = {k: i for i, k in enumerate(recalled_keys)}
        entries.sort(key=lambda e: key_order.get(e["key"], 999))
        return {"entries": entries, "total": len(entries), "raw": raw}

    @router.get("/entries")
    def list_entries(
        category: str = "",
        limit:    int = Query(100, ge=1, le=1000),
        offset:   int = Query(0, ge=0),
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        conn = _conn()
        try:
            base_sql = """
                SELECT s.memory_key, s.category, s.value, s.created
                FROM semantic_memory s
                JOIN (
                    SELECT memory_key, MAX(id) AS max_id
                    FROM semantic_memory
                    GROUP BY memory_key
                ) latest ON latest.max_id = s.id
            """
            count_sql = """
                SELECT COUNT(*) FROM (
                    SELECT s.memory_key
                    FROM semantic_memory s
                    JOIN (
                        SELECT memory_key, MAX(id) AS max_id
                        FROM semantic_memory
                        GROUP BY memory_key
                    ) latest ON latest.max_id = s.id
                    {where}
                )
            """
            if category:
                where = "WHERE s.category=?"
                rows = conn.execute(
                    base_sql + " WHERE s.category=? ORDER BY s.created DESC LIMIT ? OFFSET ?",
                    (category, limit, offset),
                ).fetchall()
                total = conn.execute(
                    count_sql.format(where=where), (category,)
                ).fetchone()[0]
            else:
                rows = conn.execute(
                    base_sql + " ORDER BY s.created DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
                total = conn.execute(
                    count_sql.format(where="")
                ).fetchone()[0]
        finally:
            conn.close()

        return {"entries": [_row(r) for r in rows], "total": total}

    @router.post("/entries")
    def create_entry(
        body: MemoryCreate,
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        key = (body.key or "").strip()
        value = (body.value or "").strip()
        category = (body.category or "general").strip() or "general"
        if not key:
            raise HTTPException(400, "key is required")
        if not value:
            raise HTTPException(400, "value is required")
        result = remember_semantic(key, value, category)
        if result.startswith("Error:"):
            raise HTTPException(500, result)
        return {"ok": True, "key": key, "message": result}

    @router.delete("/entries")
    def clear_all_entries(
        confirm: bool = Query(False),
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        if not confirm:
            raise HTTPException(400, "Pass ?confirm=true to clear all memory entries")
        conn = _conn()
        try:
            conn.execute("DELETE FROM semantic_memory")
            conn.commit()
        finally:
            conn.close()
        return {"ok": True, "message": "All memory entries cleared"}

    @router.delete("/entries/{key:path}")
    def delete_entry(
        key: str,
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        key = (key or "").strip()
        if not key:
            raise HTTPException(400, "key is required")
        conn = _conn()
        try:
            cur = conn.execute("DELETE FROM semantic_memory WHERE memory_key=?", (key,))
            conn.commit()
            if cur.rowcount == 0:
                raise HTTPException(404, f"Memory entry '{key}' not found")
        finally:
            conn.close()
        return {"ok": True, "key": key}

    return router
