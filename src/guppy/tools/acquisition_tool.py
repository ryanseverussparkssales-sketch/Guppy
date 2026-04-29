"""Automated book acquisition tools — LazyLibrarian + Prowlarr.

LazyLibrarian manages your wanted-book list and downloads automatically.
Prowlarr aggregates 800+ indexers and feeds them to LazyLibrarian.

Environment:
    LAZYLIBRARIAN_URL     — base URL (default: http://localhost:5299)
    LAZYLIBRARIAN_APIKEY  — LazyLibrarian API key (Settings → Interface)
    PROWLARR_URL          — base URL (default: http://localhost:9696)
    PROWLARR_APIKEY       — Prowlarr API key  (Settings → General)
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlencode


# ── Helpers ───────────────────────────────────────────────────────────────────

def _http_json(url: str, timeout: int = 15) -> Any:
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "Guppy/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _post_json(url: str, data: dict[str, Any] | None = None, timeout: int = 15) -> Any:
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "Guppy/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


# ── LazyLibrarian ─────────────────────────────────────────────────────────────

def _ll_url() -> str:
    return os.environ.get("LAZYLIBRARIAN_URL", "http://localhost:5299").rstrip("/")


def _ll_key() -> str:
    return os.environ.get("LAZYLIBRARIAN_APIKEY", "").strip()


def _ll_api(cmd: str, **params: Any) -> Any:
    key = _ll_key()
    if not key:
        raise RuntimeError("LAZYLIBRARIAN_APIKEY not configured in .env")
    qs = urlencode({"apikey": key, "cmd": cmd, **params})
    return _http_json(f"{_ll_url()}/api?{qs}")


def lazylibrarian_alive() -> bool:
    try:
        _ll_api("getVersion")
        return True
    except Exception:
        return False


def lazylibrarian_search_book(title: str = "", author: str = "") -> list[dict[str, Any]]:
    """Search LazyLibrarian's database for books matching title/author."""
    params: dict[str, Any] = {}
    if title:
        params["bookname"] = title
    if author:
        params["authorname"] = author
    result = _ll_api("searchBook", **params)
    books = result if isinstance(result, list) else result.get("books", [])
    return books


def lazylibrarian_get_wanted() -> list[dict[str, Any]]:
    """Return the current wanted-books list."""
    result = _ll_api("getWanted")
    return result if isinstance(result, list) else result.get("books", [])


def lazylibrarian_add_wanted(goodreads_id: str = "", isbn: str = "") -> dict[str, Any]:
    """Add a book to the wanted list by Goodreads ID or ISBN."""
    if not goodreads_id and not isbn:
        raise ValueError("goodreads_id or isbn required")
    params: dict[str, Any] = {}
    if goodreads_id:
        params["bookid"] = goodreads_id
    if isbn:
        params["isbn"] = isbn
    result = _ll_api("addBook", **params)
    return {"ok": True, "result": result}


def lazylibrarian_add_author(author_name: str) -> dict[str, Any]:
    """Add an author to LazyLibrarian — it will watch for all their books."""
    result = _ll_api("addAuthor", authorname=author_name)
    return {"ok": True, "result": result}


def lazylibrarian_get_downloads() -> list[dict[str, Any]]:
    """Return recent/in-progress downloads."""
    result = _ll_api("getHistory")
    return result if isinstance(result, list) else result.get("books", [])


def lazylibrarian_search_by_title(query: str) -> list[dict[str, Any]]:
    """Full-text search across LazyLibrarian's book database."""
    result = _ll_api("searchBook", bookname=query)
    return result if isinstance(result, list) else result.get("books", [])


# ── Prowlarr ──────────────────────────────────────────────────────────────────

def _pr_url() -> str:
    return os.environ.get("PROWLARR_URL", "http://localhost:9696").rstrip("/")


def _pr_key() -> str:
    return os.environ.get("PROWLARR_APIKEY", "").strip()


def _pr_api(path: str, **params: Any) -> Any:
    key = _pr_key()
    if not key:
        raise RuntimeError("PROWLARR_APIKEY not configured in .env")
    qs = urlencode(params) if params else ""
    url = f"{_pr_url()}{path}?apikey={key}"
    if qs:
        url += f"&{qs}"
    return _http_json(url)


def prowlarr_alive() -> bool:
    try:
        _pr_api("/api/v1/health")
        return True
    except Exception:
        return False


def prowlarr_search(
    query: str,
    categories: list[int] | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Search all configured Prowlarr indexers.

    Common book category IDs (Newznab standard):
        7000 — Books (all)
        7020 — Books/eBook
        7030 — Books/Comics
        7040 — Books/Magazines
    """
    params: dict[str, Any] = {"query": query, "limit": min(limit, 100)}
    if categories:
        # Prowlarr accepts repeated `categories` query params
        from urllib.parse import urlencode as _ue
        key = _pr_key()
        cat_qs = "&".join(f"categories={c}" for c in categories)
        qs = _ue(params)
        url = f"{_pr_url()}/api/v1/search?apikey={key}&{qs}&{cat_qs}"
        data = _http_json(url)
    else:
        data = _pr_api("/api/v1/search", **params)
    return data if isinstance(data, list) else []


def prowlarr_list_indexers() -> list[dict[str, Any]]:
    """Return all configured Prowlarr indexers with their status."""
    data = _pr_api("/api/v1/indexer")
    return data if isinstance(data, list) else []


def prowlarr_test_indexers() -> list[dict[str, Any]]:
    """Trigger a connectivity test on all indexers."""
    key = _pr_key()
    if not key:
        raise RuntimeError("PROWLARR_APIKEY not configured in .env")
    data = _post_json(f"{_pr_url()}/api/v1/indexer/testall?apikey={key}")
    return data if isinstance(data, list) else []
