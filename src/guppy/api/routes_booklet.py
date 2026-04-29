"""
Booklet API — Instructions & Knowledge Base for Guppy chat sessions.

Storage: config/booklet.json (plain JSON, git-trackable, human-editable).
Each section has an id, title, markdown content, mode, and sort_order.
Mode controls how the section flows into chat context:
  always   — prepended to every system prompt
  retrieve — available for semantic retrieval (future)
  off      — disabled, not sent anywhere
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from src.guppy.api.server_context import ServerContext

# ---------------------------------------------------------------------------
# Storage path
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent.parent
_BOOKLET_PATH = _REPO_ROOT / "config" / "booklet.json"

SectionMode = Literal["always", "retrieve", "off"]

# ---------------------------------------------------------------------------
# Default sections — seeded on first run
# ---------------------------------------------------------------------------

_DEFAULT_SECTIONS: list[dict] = [
    {
        "id": "identity",
        "title": "Identity & Persona",
        "mode": "always",
        "sort_order": 0,
        "content": (
            "You are Guppy, a technical intelligence assistant for Ryan Sparks. "
            "You are precise, direct, and efficient — no filler, no unnecessary caveats. "
            "Think like a senior engineer, communicate like one. "
            "You can be conversational when the moment calls for it, but always prioritize signal over noise."
        ),
    },
    {
        "id": "rules",
        "title": "Rules & Constraints",
        "mode": "always",
        "sort_order": 1,
        "content": (
            "- Never fabricate facts. If you don't know, say so clearly.\n"
            "- Always confirm before destructive operations (delete, overwrite, force push, format).\n"
            "- When using tools, choose the most targeted one for the job.\n"
            "- If a request is ambiguous, ask one clarifying question — don't assume.\n"
            "- Match response depth to question depth. A quick question gets a quick answer.\n"
            "- Never skip confirmation for actions affecting shared systems, external services, or file deletion."
        ),
    },
    {
        "id": "user_context",
        "title": "User Context",
        "mode": "always",
        "sort_order": 2,
        "content": (
            "Name: Ryan Sparks\n"
            "Role: Technical founder and builder\n"
            "Environment: Windows 11, PowerShell, VS Code, Chrome\n"
            "Stack: Python (FastAPI), React + TypeScript, Tailwind CSS, Vite\n"
            "Local AI: Ollama at localhost:11434\n\n"
            "Preferences:\n"
            "- Concise answers; skip preamble\n"
            "- Code over explanation when possible\n"
            "- No unnecessary emojis or filler phrases"
        ),
    },
    {
        "id": "tool_guidance",
        "title": "Tool Guidance",
        "mode": "always",
        "sort_order": 3,
        "content": (
            "- **web_search**: Use for current data, prices, docs, news. Prefer current info over training knowledge for anything time-sensitive.\n"
            "- **file_read / file_write**: Only when explicitly asked. Confirm paths before writing.\n"
            "- **code_execution**: Good for verifying logic or calculations. Not for production scripts without confirmation.\n"
            "- **screenshot**: Use when the user asks about something visual or for UI debugging.\n"
            "- **recall / remember**: Use proactively to store and retrieve user preferences and project facts.\n"
            "- **shell_execute**: Only with explicit user confirmation. Always show the command before running."
        ),
    },
    {
        "id": "active_projects",
        "title": "Active Projects",
        "mode": "always",
        "sort_order": 4,
        "content": (
            "## Guppy (Active)\n"
            "Local AI assistant platform with web UI and desktop companion.\n"
            "Stack: React + TypeScript + Vite (port 3000), FastAPI (port 8081), Ollama (port 11434)\n"
            "Key paths: web/src/ (frontend), src/guppy/api/ (backend)\n\n"
            "## Digital Seed Vault (Active)\n"
            "Personal media archiving and metadata extraction.\n"
            "Agent: vault-scraper (qwen2.5:7b)\n"
            "Purpose: Structured metadata extraction from personal media files."
        ),
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ID_RE = re.compile(r"^[a-z0-9_-]{1,64}$")


def _load() -> list[dict]:
    if not _BOOKLET_PATH.exists():
        _BOOKLET_PATH.parent.mkdir(parents=True, exist_ok=True)
        _save(_DEFAULT_SECTIONS)
        return list(_DEFAULT_SECTIONS)
    data = json.loads(_BOOKLET_PATH.read_text(encoding="utf-8"))
    return data.get("sections", [])


def _save(sections: list[dict]) -> None:
    _BOOKLET_PATH.write_text(
        json.dumps({"sections": sections}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _sorted(sections: list[dict]) -> list[dict]:
    return sorted(sections, key=lambda s: s.get("sort_order", 99))


def compile_booklet() -> str:
    """Return the full system-prompt text for all 'always' sections."""
    sections = _sorted(_load())
    parts = []
    for s in sections:
        if s.get("mode") == "always" and s.get("content", "").strip():
            parts.append(f"## {s['title']}\n{s['content'].strip()}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class BookletSection(BaseModel):
    id: str
    title: str
    content: str
    mode: SectionMode
    sort_order: int


class CreateSectionRequest(BaseModel):
    id: str
    title: str
    content: str = ""
    mode: SectionMode = "always"

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not _ID_RE.match(v):
            raise ValueError("id must be 1-64 lowercase alphanumeric/dash/underscore")
        return v


class UpdateSectionRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    mode: SectionMode | None = None


class ReorderRequest(BaseModel):
    ids: list[str]  # desired order, front to back


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def build_booklet_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/booklet", tags=["booklet"])

    @router.get("/sections", response_model=list[BookletSection])
    def list_sections(_user_id: str = Depends(ctx.require_rate_limit)):
        return _sorted(_load())

    @router.post("/sections", response_model=BookletSection, status_code=201)
    def create_section(body: CreateSectionRequest, _user_id: str = Depends(ctx.require_rate_limit)):
        sections = _load()
        if any(s["id"] == body.id for s in sections):
            raise HTTPException(409, f"Section '{body.id}' already exists")
        new = {
            "id": body.id,
            "title": body.title,
            "content": body.content,
            "mode": body.mode,
            "sort_order": max((s.get("sort_order", 0) for s in sections), default=-1) + 1,
        }
        sections.append(new)
        _save(sections)
        return new

    @router.patch("/sections/{section_id}", response_model=BookletSection)
    def update_section(section_id: str, body: UpdateSectionRequest, _user_id: str = Depends(ctx.require_rate_limit)):
        sections = _load()
        for s in sections:
            if s["id"] == section_id:
                if body.title is not None:
                    s["title"] = body.title
                if body.content is not None:
                    s["content"] = body.content
                if body.mode is not None:
                    s["mode"] = body.mode
                _save(sections)
                return s
        raise HTTPException(404, f"Section '{section_id}' not found")

    @router.delete("/sections/{section_id}", status_code=204)
    def delete_section(section_id: str, _user_id: str = Depends(ctx.require_rate_limit)):
        sections = _load()
        original = len(sections)
        sections = [s for s in sections if s["id"] != section_id]
        if len(sections) == original:
            raise HTTPException(404, f"Section '{section_id}' not found")
        _save(sections)

    @router.post("/sections/reorder", response_model=list[BookletSection])
    def reorder_sections(body: ReorderRequest, _user_id: str = Depends(ctx.require_rate_limit)):
        sections = _load()
        index = {s["id"]: s for s in sections}
        reordered = []
        for i, sid in enumerate(body.ids):
            if sid not in index:
                raise HTTPException(404, f"Section '{sid}' not found")
            s = dict(index[sid])
            s["sort_order"] = i
            reordered.append(s)
        # Append any sections not in the reorder list at the end
        known = set(body.ids)
        for s in sections:
            if s["id"] not in known:
                s = dict(s)
                s["sort_order"] = len(reordered)
                reordered.append(s)
        _save(reordered)
        return _sorted(reordered)

    @router.get("/compiled")
    def get_compiled(_user_id: str = Depends(ctx.require_rate_limit)):
        return {"compiled": compile_booklet()}

    return router
