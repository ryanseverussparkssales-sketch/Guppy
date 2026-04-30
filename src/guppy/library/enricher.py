from __future__ import annotations

import json
import sqlite3
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from src.guppy.paths import USER_DATA_DIR

_DB_PATH = str(USER_DATA_DIR / "guppy_main.db")
_CACHE_TTL_DAYS = 30


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS library_metadata (
            cache_key TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            author TEXT,
            cover_url TEXT,
            description TEXT,
            subjects_json TEXT,
            publish_year INTEGER,
            isbn TEXT,
            payload_json TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def _cache_key(title: str, author: str) -> str:
    return f"{title.strip().lower()}::{author.strip().lower()}"


def _from_cache(title: str, author: str) -> dict[str, Any] | None:
    key = _cache_key(title, author)
    with _db() as conn:
        row = conn.execute(
            "SELECT payload_json, fetched_at FROM library_metadata WHERE cache_key = ?",
            (key,),
        ).fetchone()
    if not row:
        return None

    fetched_at = datetime.fromisoformat(row["fetched_at"])
    if datetime.now(timezone.utc) - fetched_at > timedelta(days=_CACHE_TTL_DAYS):
        return None

    return json.loads(row["payload_json"])


def _save_cache(title: str, author: str, payload: dict[str, Any]) -> None:
    key = _cache_key(title, author)
    with _db() as conn:
        conn.execute(
            """
            INSERT INTO library_metadata (
                cache_key, title, author, cover_url, description, subjects_json,
                publish_year, isbn, payload_json, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                title=excluded.title,
                author=excluded.author,
                cover_url=excluded.cover_url,
                description=excluded.description,
                subjects_json=excluded.subjects_json,
                publish_year=excluded.publish_year,
                isbn=excluded.isbn,
                payload_json=excluded.payload_json,
                fetched_at=excluded.fetched_at
            """,
            (
                key,
                title,
                author,
                payload.get("cover_url"),
                payload.get("description"),
                json.dumps(payload.get("subjects", []), ensure_ascii=False),
                payload.get("publish_year"),
                payload.get("isbn"),
                json.dumps(payload, ensure_ascii=False),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()


def enrich(title: str, author: str = "") -> dict[str, Any]:
    """Enrich metadata from Open Library with 30-day cache in guppy_main.db."""
    title = title.strip()
    author = author.strip()
    if not title:
        return {
            "cover_url": None,
            "description": "",
            "subjects": [],
            "publish_year": None,
            "isbn": None,
            "source": "none",
            "found": False,
        }

    cached = _from_cache(title, author)
    if cached is not None:
        cached["cached"] = True
        return cached

    query = {"title": title}
    if author:
        query["author"] = author

    search_url = "https://openlibrary.org/search.json?" + urllib.parse.urlencode(query)
    payload: dict[str, Any] = {
        "cover_url": None,
        "description": "",
        "subjects": [],
        "publish_year": None,
        "isbn": None,
        "source": "openlibrary",
        "found": False,
        "cached": False,
    }

    try:
        req = urllib.request.Request(search_url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))

        docs = data.get("docs") or []
        if not docs:
            _save_cache(title, author, payload)
            return payload

        doc = docs[0]
        cover_id = doc.get("cover_i")
        if cover_id:
            payload["cover_url"] = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"

        if isinstance(doc.get("first_sentence"), list) and doc.get("first_sentence"):
            payload["description"] = str(doc.get("first_sentence")[0])
        elif isinstance(doc.get("first_sentence"), str):
            payload["description"] = str(doc.get("first_sentence"))

        subjects = doc.get("subject") or []
        payload["subjects"] = [str(s) for s in subjects[:8]]

        publish_year = doc.get("first_publish_year")
        if isinstance(publish_year, int):
            payload["publish_year"] = publish_year

        isbn_list = doc.get("isbn") or []
        if isbn_list:
            payload["isbn"] = str(isbn_list[0])

        payload["found"] = True
    except Exception:
        pass

    _save_cache(title, author, payload)
    return payload
