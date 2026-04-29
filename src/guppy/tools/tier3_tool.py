"""Calibre Tier 3 acquisition sources.

- Standard Ebooks: curated, beautifully typeset public-domain ebooks
- Internet Archive: millions of scanned texts (quality varies)
- Mylar3: comics manager (separate library path recommended)

Environment:
    STANDARD_EBOOKS_EMAIL    — free account email for OPDS auth
    STANDARD_EBOOKS_PASSWORD — account password (create at standardebooks.org)
    MYLAR3_URL    — Mylar3 base URL  (default: http://localhost:8090)
    MYLAR3_APIKEY — Mylar3 API key   (Settings → Web Interface)
"""
from __future__ import annotations

import base64
import json
import os
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urlencode
import urllib.request


# ── Shared HTTP helper ────────────────────────────────────────────────────────

def _http_get(url: str, timeout: int = 20, extra_headers: dict | None = None) -> bytes:
    headers = {"User-Agent": "Guppy/1.0 (book-fetcher)"}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _http_json(url: str, timeout: int = 20) -> Any:
    return json.loads(_http_get(url, timeout).decode())


# ── Standard Ebooks ───────────────────────────────────────────────────────────

_SE_OPDS_ALL = "https://standardebooks.org/feeds/opds/all"
_SE_NS = {
    "atom":   "http://www.w3.org/2005/Atom",
    "opds":   "http://opds-spec.org/2010/catalog",
    "dc":     "http://purl.org/dc/terms/",
}


def _se_auth_headers() -> dict:
    """Return Basic-Auth headers for Standard Ebooks if credentials are set."""
    email = os.environ.get("STANDARD_EBOOKS_EMAIL", "").strip()
    password = os.environ.get("STANDARD_EBOOKS_PASSWORD", "").strip()
    if email and password:
        token = base64.b64encode(f"{email}:{password}".encode()).decode()
        return {"Authorization": f"Basic {token}"}
    return {}


def _parse_se_feed(xml_bytes: bytes) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_bytes)
    books: list[dict[str, Any]] = []
    ns = _SE_NS["atom"]
    for entry in root.findall(f"{{{ns}}}entry"):
        title = _text(entry, f"{{{ns}}}title")
        summary = _text(entry, f"{{{ns}}}summary")
        author_el = entry.find(f"{{{ns}}}author")
        author = _text(author_el, f"{{{ns}}}name") if author_el is not None else None
        epub_url = None
        cover_url = None
        for link in entry.findall(f"{{{ns}}}link"):
            rel = link.get("rel", "")
            ltype = link.get("type", "")
            href = link.get("href", "")
            if "acquisition" in rel and "epub" in ltype:
                epub_url = href
            if "http://opds-spec.org/image" in rel and cover_url is None:
                cover_url = href
        if title:
            books.append({
                "title":     title,
                "author":    author,
                "summary":   summary,
                "epub_url":  epub_url,
                "cover_url": cover_url,
                "source":    "Standard Ebooks",
            })
    return books


def _text(el: ET.Element | None, tag: str) -> str | None:
    if el is None:
        return None
    ch = el.find(tag)
    return (ch.text or "").strip() if ch is not None else None


def standard_ebooks_configured() -> bool:
    return bool(os.environ.get("STANDARD_EBOOKS_EMAIL") and os.environ.get("STANDARD_EBOOKS_PASSWORD"))


def standard_ebooks_search(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search Standard Ebooks curated public-domain library via OPDS.

    Requires a free account at standardebooks.org. Set STANDARD_EBOOKS_EMAIL
    and STANDARD_EBOOKS_PASSWORD in .env to enable.

    Fetches the OPDS feed and filters by query against title + author.
    SE has ~800 curated books; paginates up to 5 pages.
    """
    if not standard_ebooks_configured():
        raise RuntimeError(
            "Standard Ebooks requires a free account. "
            "Set STANDARD_EBOOKS_EMAIL and STANDARD_EBOOKS_PASSWORD in .env."
        )
    auth = _se_auth_headers()
    q = query.lower()
    results: list[dict[str, Any]] = []
    page_url = _SE_OPDS_ALL

    for _ in range(5):  # max 5 pages
        xml_bytes = _http_get(page_url, timeout=20, extra_headers=auth)
        entries = _parse_se_feed(xml_bytes)
        for e in entries:
            haystack = f"{e.get('title','')} {e.get('author','')}".lower()
            if q in haystack:
                results.append(e)
                if len(results) >= limit:
                    return results

        # Find the "next" page link in the Atom feed
        root = ET.fromstring(xml_bytes)
        ns = _SE_NS["atom"]
        next_url = None
        for link in root.findall(f"{{{ns}}}link"):
            if link.get("rel") == "next":
                next_url = link.get("href", "")
                break
        if not next_url:
            break
        page_url = next_url

    return results


# ── Internet Archive ──────────────────────────────────────────────────────────

_IA_SEARCH_URL = "https://archive.org/advancedsearch.php"
_IA_META_URL   = "https://archive.org/metadata"
_IA_DL_URL     = "https://archive.org/download"


def internet_archive_search(
    query: str,
    limit: int = 10,
    media_type: str = "texts",
) -> list[dict[str, Any]]:
    """Search Internet Archive for books/texts."""
    params = urlencode({
        "q":          f"({query}) AND mediatype:{media_type}",
        "fl[]":       "identifier,title,creator,description,year,downloads",
        "output":     "json",
        "rows":       min(limit, 50),
        "sort[]":     "downloads desc",
    })
    # IA uses repeated fl[] — requests would handle this but we use urllib
    url = f"{_IA_SEARCH_URL}?{params}"
    data = _http_json(url)
    docs = data.get("response", {}).get("docs", [])
    return [
        {
            "identifier":   d.get("identifier"),
            "title":        _first(d.get("title")),
            "creator":      _first(d.get("creator")),
            "description":  _first(d.get("description")),
            "year":         d.get("year"),
            "downloads":    d.get("downloads"),
            "detail_url":   f"https://archive.org/details/{d.get('identifier','')}",
            "source":       "Internet Archive",
        }
        for d in docs
        if d.get("identifier")
    ]


def _first(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, list):
        return str(val[0]) if val else None
    return str(val)


def internet_archive_get_download_url(identifier: str, prefer_format: str = "epub") -> str | None:
    """Return the best download URL for an IA item (EPUB preferred, PDF fallback)."""
    data = _http_json(f"{_IA_META_URL}/{identifier}")
    files = data.get("files", [])
    # collect candidates by format preference
    pref_order = [prefer_format, "epub", "pdf", "txt"]
    for fmt in pref_order:
        for f in files:
            name = f.get("name", "")
            if name.lower().endswith(f".{fmt}") and f.get("format", "").lower() != "metadata":
                return f"{_IA_DL_URL}/{identifier}/{name}"
    return None


def internet_archive_download_to_calibre(identifier: str) -> dict[str, Any]:
    """Download an Internet Archive item and add it to the local Calibre library."""
    from src.guppy.tools.calibre_tool import calibre_add, calibre_available
    if not calibre_available():
        raise RuntimeError("Calibre not installed — cannot add to library")
    download_url = internet_archive_get_download_url(identifier)
    if not download_url:
        raise RuntimeError(
            f"No EPUB or PDF found for IA item '{identifier}'. "
            "Try browsing https://archive.org/details/{identifier} manually."
        )
    result = calibre_add(download_url)
    result["ia_identifier"] = identifier
    return result


# ── Mylar3 (comics) ───────────────────────────────────────────────────────────

def _mylar_url() -> str:
    return os.environ.get("MYLAR3_URL", "http://localhost:8090").rstrip("/")


def _mylar_key() -> str:
    return os.environ.get("MYLAR3_APIKEY", "").strip()


def _mylar_api(cmd: str, **params: Any) -> Any:
    key = _mylar_key()
    if not key:
        raise RuntimeError("MYLAR3_APIKEY not configured in .env")
    qs = urlencode({"apikey": key, "cmd": cmd, **params})
    return _http_json(f"{_mylar_url()}/api?{qs}")


def mylar3_alive() -> bool:
    try:
        _mylar_api("getVersion")
        return True
    except Exception:
        return False


def mylar3_search_comic(term: str) -> list[dict[str, Any]]:
    """Search Mylar3 comic database."""
    result = _mylar_api("searchComic", term=term)
    items = result if isinstance(result, list) else result.get("data", [])
    return items


def mylar3_add_comic(comic_id: str) -> dict[str, Any]:
    """Add a comic series to Mylar3 by its ID (from searchComic results)."""
    result = _mylar_api("addComic", comicid=comic_id)
    return {"ok": True, "result": result}


def mylar3_get_wanted() -> list[dict[str, Any]]:
    """Return the Mylar3 wanted/missing issues list."""
    result = _mylar_api("getWanted")
    return result if isinstance(result, list) else result.get("data", [])
