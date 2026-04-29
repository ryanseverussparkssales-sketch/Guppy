"""Calibre library integration helpers for Guppy tools.

Wraps the calibredb and ebook-convert CLIs. All functions are synchronous —
use asyncio.to_thread at the call site (done in routes_calibre.py).

Environment vars:
    CALIBRE_LIBRARY_PATH  — path to Calibre library directory (optional; uses
                            Calibre's default library if unset)
    KINDLE_EMAIL          — @kindle.com delivery address
    KINDLE_FROM_EMAIL     — sender address (must be on Amazon's whitelist)
    SMTP_HOST             — SMTP relay host (default: smtp.gmail.com)
    SMTP_PORT             — SMTP port      (default: 587)
    SMTP_USER             — SMTP login
    SMTP_PASS             — SMTP password / app-password
"""
from __future__ import annotations

import json
import os
import shutil
import smtplib
import subprocess
import tempfile
import urllib.request
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any
from urllib.parse import urlencode


# ── Calibre binary discovery ──────────────────────────────────────────────────

_WIN_CALIBRE_DIRS = [
    r"C:\Program Files\Calibre2",
    r"C:\Program Files (x86)\Calibre2",
]


def _find_calibre_bin(name: str) -> str | None:
    if shutil.which(name):
        return name
    for d in _WIN_CALIBRE_DIRS:
        candidate = Path(d) / f"{name}.exe"
        if candidate.exists():
            return str(candidate)
    return None


def calibre_available() -> bool:
    return _find_calibre_bin("calibredb") is not None


def ebook_convert_available() -> bool:
    return _find_calibre_bin("ebook-convert") is not None


# ── Library helpers ───────────────────────────────────────────────────────────

def _library_path() -> str | None:
    return os.environ.get("CALIBRE_LIBRARY_PATH", "").strip() or None


def _calibredb_cmd(*args: str) -> list[str]:
    bin_ = _find_calibre_bin("calibredb")
    if not bin_:
        raise RuntimeError(
            "calibredb not found — install Calibre and ensure it is on PATH"
        )
    cmd: list[str] = [bin_, *args]
    lib = _library_path()
    if lib:
        cmd += ["--with-library", lib]
    return cmd


def _run(cmd: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


# ── Local library operations ──────────────────────────────────────────────────

def calibre_search(query: str = "", limit: int = 20) -> list[dict[str, Any]]:
    """Search the local Calibre library. Returns a list of book dicts."""
    args = [
        "list", "--for-machine",
        f"--limit={min(limit, 200)}",
        "--fields=id,title,authors,formats,tags,series,pubdate",
    ]
    if query:
        args.append(f"--search={query}")
    result = _run(_calibredb_cmd(*args))
    if result.returncode != 0:
        raise RuntimeError(f"calibredb list error: {result.stderr.strip()}")
    try:
        books = json.loads(result.stdout) or []
    except json.JSONDecodeError:
        books = []
    # Normalise formats field: calibredb returns comma-separated paths as a string
    for b in books:
        raw = b.get("formats", "")
        if isinstance(raw, str):
            b["formats"] = [f.strip() for f in raw.split(",") if f.strip()]
    return books


def calibre_add(source: str) -> dict[str, Any]:
    """Add a book to Calibre from a local file path or URL.

    For URLs the file is downloaded to a temp path first, then passed to
    calibredb add so calibre can detect the format from the extension.
    """
    if source.startswith(("http://", "https://")):
        return _add_from_url(source)
    return _add_file(source)


def _add_from_url(url: str) -> dict[str, Any]:
    suffix = Path(url.split("?")[0]).suffix or ".epub"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        tmp = f.name
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Guppy/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            Path(tmp).write_bytes(resp.read())
        return _add_file(tmp)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _add_file(path: str) -> dict[str, Any]:
    result = _run(_calibredb_cmd("add", path), timeout=90)
    if result.returncode != 0:
        raise RuntimeError(f"calibredb add failed: {result.stderr.strip()}")
    output = result.stdout.strip()
    # calibredb add outputs: "Added book ids: 123, 456"
    ids: list[int] = []
    if ":" in output:
        for part in output.split(":")[-1].split(","):
            part = part.strip()
            if part.isdigit():
                ids.append(int(part))
    return {"added": True, "book_ids": ids, "output": output}


def calibre_set_metadata(book_id: int, fields: dict[str, str]) -> dict[str, Any]:
    """Update metadata fields for a book already in Calibre.

    fields example: {"tags": "fiction, sci-fi", "series": "Foundation"}
    """
    if not fields:
        raise ValueError("fields must be non-empty")
    args = ["set_metadata"]
    for field, value in fields.items():
        args += ["--field", f"{field}:{value}"]
    args.append(str(book_id))
    result = _run(_calibredb_cmd(*args))
    if result.returncode != 0:
        raise RuntimeError(f"calibredb set_metadata failed: {result.stderr.strip()}")
    return {"ok": True, "book_id": book_id, "updated_fields": list(fields.keys())}


def calibre_convert(book_id: int, output_format: str = "mobi") -> str:
    """Convert a library book to another format; returns the output file path."""
    books = calibre_search(f"id:{book_id}", limit=1)
    if not books:
        raise RuntimeError(f"Book id:{book_id} not found in library")
    formats: list[str] = books[0].get("formats", [])
    if not formats:
        raise RuntimeError(f"Book id:{book_id} has no formats in library")

    # Prefer source formats calibre converts well from
    pref = ["epub", "mobi", "azw3", "pdf", "txt", "html", "rtf"]
    input_path = next(
        (f for ext in pref for f in formats if f.lower().endswith(f".{ext}")),
        formats[0],
    )

    out_dir = Path(tempfile.gettempdir()) / "guppy_calibre"
    out_dir.mkdir(exist_ok=True)
    title = str(books[0].get("title", f"book_{book_id}"))
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)[:60].strip()
    out_path = str(out_dir / f"{safe_title}.{output_format}")

    bin_ = _find_calibre_bin("ebook-convert")
    if not bin_:
        raise RuntimeError("ebook-convert not found — install Calibre")

    result = _run([bin_, input_path, out_path], timeout=180)
    if result.returncode != 0:
        raise RuntimeError(f"ebook-convert failed: {result.stderr.strip()}")
    return out_path


# ── Gutenberg / Gutendex ──────────────────────────────────────────────────────

_GUTENDEX_BASE = "https://gutendex.com"


def _http_json(url: str, timeout: int = 15) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "Guppy/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def gutenberg_search(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search Project Gutenberg via Gutendex (no auth required)."""
    params = urlencode({"search": query, "languages": "en"})
    data = _http_json(f"{_GUTENDEX_BASE}/books?{params}")
    results = (data.get("results") or [])[:limit]
    out = []
    for b in results:
        fmts = b.get("formats", {})
        out.append({
            "id": b.get("id"),
            "title": b.get("title"),
            "authors": [a.get("name") for a in (b.get("authors") or [])],
            "download_count": b.get("download_count"),
            "epub_url": fmts.get("application/epub+zip"),
            "text_url": fmts.get("text/plain; charset=utf-8") or fmts.get("text/plain"),
            "subjects": b.get("subjects", [])[:5],
        })
    return out


def gutenberg_download_to_calibre(gutenberg_id: int) -> dict[str, Any]:
    """Fetch a Gutenberg book by ID and add the EPUB to the local Calibre library."""
    data = _http_json(f"{_GUTENDEX_BASE}/books/{gutenberg_id}")
    fmts = data.get("formats", {})
    epub_url = fmts.get("application/epub+zip")
    if not epub_url:
        raise RuntimeError(
            f"No EPUB available for Gutenberg book {gutenberg_id}. "
            f"Available formats: {list(fmts.keys())}"
        )
    result = calibre_add(epub_url)
    result["gutenberg_id"] = gutenberg_id
    result["title"] = data.get("title")
    return result


# ── Open Library ──────────────────────────────────────────────────────────────

_OL_BASE = "https://openlibrary.org"


def openlibrary_search(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search Open Library for books and metadata."""
    params = urlencode({
        "q": query,
        "limit": min(limit, 50),
        "fields": "title,author_name,isbn,cover_i,first_publish_year,subject,key",
    })
    data = _http_json(f"{_OL_BASE}/search.json?{params}")
    docs = data.get("docs", [])
    out = []
    for d in docs:
        isbn_list = d.get("isbn") or []
        out.append({
            "title": d.get("title"),
            "authors": d.get("author_name", []),
            "isbn": isbn_list[0] if isbn_list else None,
            "first_publish_year": d.get("first_publish_year"),
            "subjects": (d.get("subject") or [])[:5],
            "cover_url": (
                f"https://covers.openlibrary.org/b/id/{d['cover_i']}-M.jpg"
                if d.get("cover_i") else None
            ),
            "ol_key": d.get("key"),
        })
    return out


# ── Send-to-Kindle via SMTP ───────────────────────────────────────────────────

def send_to_kindle(book_id: int) -> dict[str, Any]:
    """Convert a Calibre book to MOBI and deliver it to a Kindle via SMTP.

    Requires:
        KINDLE_EMAIL  — @kindle.com address from Amazon account
        SMTP_USER     — sender email (must be whitelisted in Amazon's
                        'Approved Personal Document E-mail List')
        SMTP_PASS     — SMTP password or app-password
    Optional:
        KINDLE_FROM_EMAIL — override sender (defaults to SMTP_USER)
        SMTP_HOST         — relay host (default: smtp.gmail.com)
        SMTP_PORT         — relay port (default: 587)

    Note: only works for DRM-free books. DRM-protected purchases cannot be
    converted by calibre.
    """
    kindle_email = os.environ.get("KINDLE_EMAIL", "").strip()
    smtp_user = os.environ.get("SMTP_USER", "").strip()
    smtp_pass = os.environ.get("SMTP_PASS", "").strip()
    from_email = os.environ.get("KINDLE_FROM_EMAIL", smtp_user).strip()
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))

    if not kindle_email:
        raise RuntimeError("KINDLE_EMAIL not configured in .env")
    if not smtp_user or not smtp_pass:
        raise RuntimeError("SMTP_USER and SMTP_PASS required for Kindle delivery")

    mobi_path = calibre_convert(book_id, "mobi")
    try:
        _smtp_send(mobi_path, from_email, kindle_email, smtp_host, smtp_port, smtp_user, smtp_pass)
    finally:
        try:
            os.unlink(mobi_path)
        except OSError:
            pass

    return {"ok": True, "sent_to": kindle_email, "book_id": book_id}


def kindle_send_direct(source: str, output_format: str = "mobi") -> dict[str, Any]:
    """Download a URL (or use a local file) and deliver it to Kindle via SMTP.

    Unlike send_to_kindle(book_id), this does NOT require the book to exist in
    the Calibre library — it downloads the file, optionally converts it, then
    emails it. Great for sending any EPUB/PDF you found online.

    Requires the same KINDLE_EMAIL / SMTP_* env vars as send_to_kindle().
    DRM-protected files cannot be converted; use a DRM-free source.
    """
    kindle_email = os.environ.get("KINDLE_EMAIL", "").strip()
    smtp_user = os.environ.get("SMTP_USER", "").strip()
    smtp_pass = os.environ.get("SMTP_PASS", "").strip()
    from_email = os.environ.get("KINDLE_FROM_EMAIL", smtp_user).strip()
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))

    if not kindle_email:
        raise RuntimeError("KINDLE_EMAIL not configured in .env")
    if not smtp_user or not smtp_pass:
        raise RuntimeError("SMTP_USER and SMTP_PASS required for Kindle delivery")

    # --- acquire file ---
    if source.startswith(("http://", "https://")):
        suffix = Path(source.split("?")[0]).suffix or ".epub"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            tmp_src = f.name
        req = urllib.request.Request(source, headers={"User-Agent": "Guppy/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            Path(tmp_src).write_bytes(resp.read())
    else:
        if not Path(source).exists():
            raise RuntimeError(f"File not found: {source}")
        tmp_src = None  # use source path directly
        suffix = Path(source).suffix.lower()

    try:
        src_path = tmp_src or source
        src_suffix = Path(src_path).suffix.lower().lstrip(".")

        # Convert if the source isn't already in the target format
        if src_suffix != output_format:
            bin_ = _find_calibre_bin("ebook-convert")
            if not bin_:
                raise RuntimeError("ebook-convert not found — install Calibre for format conversion")
            out_dir = Path(tempfile.gettempdir()) / "guppy_kindle"
            out_dir.mkdir(exist_ok=True)
            stem = Path(src_path).stem[:60]
            conv_path = str(out_dir / f"{stem}.{output_format}")
            result = _run([bin_, src_path, conv_path], timeout=180)
            if result.returncode != 0:
                raise RuntimeError(f"ebook-convert failed: {result.stderr.strip()}")
            send_path = conv_path
        else:
            send_path = src_path

        _smtp_send(send_path, from_email, kindle_email, smtp_host, smtp_port, smtp_user, smtp_pass)

        # clean up converted file (not the original download if caller provided a path)
        if send_path != src_path:
            try:
                os.unlink(send_path)
            except OSError:
                pass

    finally:
        if tmp_src:
            try:
                os.unlink(tmp_src)
            except OSError:
                pass

    return {"ok": True, "sent_to": kindle_email, "source": source, "format": output_format}


def _smtp_send(
    attachment_path: str,
    from_addr: str,
    to_addr: str,
    host: str,
    port: int,
    user: str,
    password: str,
) -> None:
    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = "Convert"  # Amazon converts to Kindle format on receipt
    msg.attach(MIMEText("Sent by Guppy"))

    with open(attachment_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    fname = Path(attachment_path).name
    part.add_header("Content-Disposition", f'attachment; filename="{fname}"')
    msg.attach(part)

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.login(user, password)
        server.sendmail(from_addr, to_addr, msg.as_string())
