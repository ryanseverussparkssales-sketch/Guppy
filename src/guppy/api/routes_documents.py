"""Document upload + AI analysis API.

Accepts file uploads (drag-and-drop or picker) from any surface — Companion,
Workspace, or Codespace. Files are stored in runtime/uploads/. An optional
AI analysis step asks the configured local llama.cpp runtime to summarise the
document content.

GET    /api/documents                 — list uploaded documents (newest first)
POST   /api/documents/upload          — multipart upload (file + optional metadata)
GET    /api/documents/{id}            — single document metadata + text preview
DELETE /api/documents/{id}            — delete document + file
POST   /api/documents/{id}/analyze    — trigger AI summary via local runtime
GET    /api/documents/{id}/download   — serve the original file
"""
from __future__ import annotations

import json
import logging
import mimetypes
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from src.guppy.api.server_context import ServerContext
from src.guppy.inference.local_client import _BACKEND_DEFAULT_MODELS, local_chat
from src.guppy.paths import MAIN_DB_PATH

logger = logging.getLogger(__name__)

_DB_PATH   = str(MAIN_DB_PATH)
_UPLOAD_DIR = Path("runtime/uploads")

# ── DB ────────────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    MAIN_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS uploaded_documents (
            id           TEXT PRIMARY KEY,
            filename     TEXT NOT NULL,
            mime_type    TEXT NOT NULL DEFAULT 'application/octet-stream',
            size_bytes   INTEGER NOT NULL DEFAULT 0,
            file_path    TEXT NOT NULL,
            surface      TEXT NOT NULL DEFAULT 'workspace',
            text_preview TEXT NOT NULL DEFAULT '',
            summary      TEXT NOT NULL DEFAULT '',
            tags         TEXT NOT NULL DEFAULT '[]',
            created_at   TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def _doc_row(r: sqlite3.Row, full: bool = False) -> dict[str, Any]:
    d = {
        "id":           r["id"],
        "filename":     r["filename"],
        "mime_type":    r["mime_type"],
        "size_bytes":   r["size_bytes"],
        "surface":      r["surface"],
        "summary":      r["summary"],
        "tags":         json.loads(r["tags"] or "[]"),
        "created_at":   r["created_at"],
    }
    if full:
        d["text_preview"] = r["text_preview"]
        d["file_path"]    = r["file_path"]
    return d


# ── Text extraction ───────────────────────────────────────────────────────────

def _extract_text(file_path: Path, mime: str) -> str:
    """Best-effort text extraction for preview and AI analysis."""
    try:
        if mime.startswith("text/") or mime in ("application/json", "application/xml"):
            return file_path.read_text(errors="replace")[:8000]
        if mime == "application/pdf":
            try:
                import pypdf
                reader = pypdf.PdfReader(str(file_path))
                return "\n".join(p.extract_text() or "" for p in reader.pages)[:8000]
            except ImportError:
                pass
        if mime in (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        ):
            try:
                import docx
                doc = docx.Document(str(file_path))
                return "\n".join(p.text for p in doc.paragraphs)[:8000]
            except ImportError:
                pass
    except Exception as exc:
        logger.debug("[documents] text extraction failed for %s: %s", file_path.name, exc)
    return ""


def _ask_local_summary(text: str) -> str:
    """Call the local OpenAI-compatible runtime for a short document summary."""
    if not text.strip():
        return ""
    prompt = (
        "Summarize the following document in 2-3 concise sentences. "
        "Focus on the main topic and key information.\n\n"
        f"DOCUMENT:\n{text[:4000]}\n\nSUMMARY:"
    )
    try:
        backend = (os.environ.get("GUPPY_DOCUMENT_SUMMARY_BACKEND", "") or "").strip().lower()
        model = (os.environ.get("GUPPY_DOCUMENT_SUMMARY_MODEL", "") or "").strip()
        if not model:
            model = _BACKEND_DEFAULT_MODELS.get(backend, "") if backend else ""
        if not model:
            model = _BACKEND_DEFAULT_MODELS.get("llamacpp-hermes4", "local-model")
        result = local_chat(
            model,
            [
                {"role": "system", "content": "You summarize documents clearly and concisely."},
                {"role": "user", "content": prompt},
            ],
            timeout=40,
            num_predict=160,
            max_retries=0,
            backend=backend or None,
        )
        if not result:
            return ""
        return str(result.get("response") or "").strip()
    except Exception as exc:
        logger.debug("[documents] local summary failed: %s", exc)
        return ""


# ── Router ────────────────────────────────────────────────────────────────────

def build_documents_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/documents", tags=["documents"])

    @router.get("")
    def list_documents(
        surface: str = "",
        limit:   int = 100,
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        limit = min(limit, 500)
        with _conn() as conn:
            if surface:
                rows = conn.execute(
                    "SELECT * FROM uploaded_documents WHERE surface=? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (surface, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM uploaded_documents ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [_doc_row(r) for r in rows]

    @router.post("/upload")
    async def upload_document(
        file:    UploadFile = File(...),
        surface: str = "workspace",
        tags:    str = "[]",
        _uid: str = Depends(ctx.require_rate_limit),
    ):
        _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        doc_id = str(uuid.uuid4())
        orig   = Path(file.filename or "upload.bin")
        dest   = _UPLOAD_DIR / f"{doc_id}{orig.suffix}"

        data = await file.read()
        dest.write_bytes(data)

        mime = (
            file.content_type
            or mimetypes.guess_type(str(orig))[0]
            or "application/octet-stream"
        )

        # Extract text for preview + eventual analysis
        text_preview = _extract_text(dest, mime)

        now = datetime.now(timezone.utc).isoformat()
        try:
            tag_list = json.loads(tags)
        except Exception:
            tag_list = []

        with _conn() as conn:
            conn.execute(
                "INSERT INTO uploaded_documents "
                "(id, filename, mime_type, size_bytes, file_path, surface, text_preview, tags, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (doc_id, orig.name, mime, len(data), str(dest),
                 surface, text_preview[:4000], json.dumps(tag_list), now),
            )
            conn.commit()

        logger.info("[documents] uploaded %s (%d bytes) to %s surface", orig.name, len(data), surface)
        return {
            "ok":       True,
            "id":       doc_id,
            "filename": orig.name,
            "mime":     mime,
            "size":     len(data),
            "has_text": bool(text_preview),
        }

    @router.get("/{doc_id}")
    def get_document(doc_id: str, _uid: str = Depends(ctx.require_rate_limit)):
        with _conn() as conn:
            row = conn.execute(
                "SELECT * FROM uploaded_documents WHERE id=?", (doc_id,)
            ).fetchone()
        if not row:
            raise HTTPException(404, "Document not found")
        return _doc_row(row, full=True)

    @router.delete("/{doc_id}")
    def delete_document(doc_id: str, _uid: str = Depends(ctx.require_rate_limit)):
        with _conn() as conn:
            row = conn.execute(
                "SELECT file_path FROM uploaded_documents WHERE id=?", (doc_id,)
            ).fetchone()
            if row:
                try:
                    Path(row["file_path"]).unlink(missing_ok=True)
                except Exception:
                    pass
            conn.execute("DELETE FROM uploaded_documents WHERE id=?", (doc_id,))
            conn.commit()
        return {"ok": True}

    @router.post("/{doc_id}/analyze")
    def analyze_document(doc_id: str, _uid: str = Depends(ctx.require_rate_limit)):
        with _conn() as conn:
            row = conn.execute(
                "SELECT * FROM uploaded_documents WHERE id=?", (doc_id,)
            ).fetchone()
        if not row:
            raise HTTPException(404, "Document not found")

        text = row["text_preview"]
        if not text:
            return {"ok": False, "message": "No text content to analyze"}

        # Run synchronously; analysis failures should not affect document storage.
        summary = _ask_local_summary(text)
        if summary:
            with _conn() as conn:
                conn.execute(
                    "UPDATE uploaded_documents SET summary=? WHERE id=?",
                    (summary, doc_id),
                )
                conn.commit()
            return {"ok": True, "summary": summary}
        raise HTTPException(
            status_code=503,
            detail="AI summary unavailable: local llama.cpp runtime did not return a response",
        )

    @router.get("/{doc_id}/download")
    def download_document(doc_id: str, _uid: str = Depends(ctx.require_rate_limit)):
        with _conn() as conn:
            row = conn.execute(
                "SELECT file_path, filename, mime_type FROM uploaded_documents WHERE id=?",
                (doc_id,),
            ).fetchone()
        if not row:
            raise HTTPException(404, "Document not found")
        path = Path(row["file_path"])
        if not path.exists():
            raise HTTPException(410, "File no longer on disk")
        return FileResponse(
            str(path),
            media_type=row["mime_type"],
            filename=row["filename"],
        )

    return router
