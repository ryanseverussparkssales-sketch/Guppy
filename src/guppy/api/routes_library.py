"""
Library API — saved prompts, templates, and artifacts.

Storage: config/library.json (plain JSON, git-trackable).
Collections group items; item_count is computed dynamically.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator

from src.guppy.api.server_context import ServerContext

_REPO_ROOT = Path(__file__).parent.parent.parent.parent
_LIBRARY_PATH = _REPO_ROOT / "config" / "library.json"

ItemType = Literal["prompt", "template", "artifact"]

_COLORS = [
    "bg-blue-500", "bg-purple-500", "bg-green-500",
    "bg-orange-500", "bg-pink-500", "bg-teal-500",
]

_ID_RE = re.compile(r"^[a-z0-9_-]{1,64}$")

# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def _load() -> dict:
    if not _LIBRARY_PATH.exists():
        _LIBRARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        _save({"collections": [], "items": []})
    data = json.loads(_LIBRARY_PATH.read_text(encoding="utf-8"))
    data.setdefault("collections", [])
    data.setdefault("items", [])
    return data


def _save(data: dict) -> None:
    _LIBRARY_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _with_counts(collections: list[dict], items: list[dict]) -> list[dict]:
    counts: dict[str, int] = {}
    for item in items:
        cid = item.get("collection") or ""
        counts[cid] = counts.get(cid, 0) + 1
    return [{**c, "item_count": counts.get(c["id"], 0)} for c in collections]


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class Collection(BaseModel):
    id: str
    name: str
    color: str
    item_count: int = 0


class CreateCollectionRequest(BaseModel):
    name: str
    color: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v


class LibraryItem(BaseModel):
    id: str
    type: ItemType
    title: str
    content: str
    collection: str | None = None
    tags: list[str] = []
    is_favorite: bool = False
    created_at: str
    updated_at: str


class CreateItemRequest(BaseModel):
    type: ItemType = "prompt"
    title: str
    content: str
    collection: str | None = None
    tags: list[str] = []

    @field_validator("title", "content")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be empty")
        return v.strip()


class UpdateItemRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    collection: str | None = None
    tags: list[str] | None = None
    is_favorite: bool | None = None


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def build_library_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/library", tags=["library"])

    # ── Collections ──────────────────────────────────────────────────────────

    @router.get("/collections", response_model=list[Collection])
    def list_collections(_user_id: str = Depends(ctx.require_rate_limit)):
        data = _load()
        return _with_counts(data["collections"], data["items"])

    @router.post("/collections", response_model=Collection, status_code=201)
    def create_collection(
        body: CreateCollectionRequest,
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        data = _load()
        slug = re.sub(r"[^a-z0-9]+", "-", body.name.lower()).strip("-")
        cid = slug or "collection"
        # Deduplicate ID
        existing_ids = {c["id"] for c in data["collections"]}
        base, n = cid, 2
        while cid in existing_ids:
            cid = f"{base}-{n}"
            n += 1
        color = body.color or _COLORS[len(data["collections"]) % len(_COLORS)]
        new = {"id": cid, "name": body.name.strip(), "color": color}
        data["collections"].append(new)
        _save(data)
        return {**new, "item_count": 0}

    @router.delete("/collections/{collection_id}", status_code=204)
    def delete_collection(
        collection_id: str,
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        data = _load()
        orig = len(data["collections"])
        data["collections"] = [c for c in data["collections"] if c["id"] != collection_id]
        if len(data["collections"]) == orig:
            raise HTTPException(404, f"Collection '{collection_id}' not found")
        # Orphan items (null out their collection)
        for item in data["items"]:
            if item.get("collection") == collection_id:
                item["collection"] = None
        _save(data)

    # ── Items ────────────────────────────────────────────────────────────────

    @router.get("/items", response_model=list[LibraryItem])
    def list_items(
        collection: str | None = Query(default=None),
        type: ItemType | None = Query(default=None),
        q: str | None = Query(default=None),
        favorites: bool = Query(default=False),
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        items = _load()["items"]
        if collection:
            items = [i for i in items if i.get("collection") == collection]
        if type:
            items = [i for i in items if i.get("type") == type]
        if favorites:
            items = [i for i in items if i.get("is_favorite")]
        if q:
            ql = q.lower()
            items = [
                i for i in items
                if ql in i.get("title", "").lower()
                or ql in i.get("content", "").lower()
                or any(ql in t.lower() for t in i.get("tags", []))
            ]
        return sorted(items, key=lambda i: i.get("updated_at", ""), reverse=True)

    @router.post("/items", response_model=LibraryItem, status_code=201)
    def create_item(
        body: CreateItemRequest,
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        data = _load()
        now = _now()
        new = {
            "id": str(uuid.uuid4()),
            "type": body.type,
            "title": body.title,
            "content": body.content,
            "collection": body.collection,
            "tags": body.tags,
            "is_favorite": False,
            "created_at": now,
            "updated_at": now,
        }
        data["items"].append(new)
        _save(data)
        return new

    @router.patch("/items/{item_id}", response_model=LibraryItem)
    def update_item(
        item_id: str,
        body: UpdateItemRequest,
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        data = _load()
        for item in data["items"]:
            if item["id"] == item_id:
                if body.title is not None:
                    item["title"] = body.title.strip()
                if body.content is not None:
                    item["content"] = body.content.strip()
                if body.collection is not None:
                    item["collection"] = body.collection
                if body.tags is not None:
                    item["tags"] = body.tags
                if body.is_favorite is not None:
                    item["is_favorite"] = body.is_favorite
                item["updated_at"] = _now()
                _save(data)
                return item
        raise HTTPException(404, f"Item '{item_id}' not found")

    @router.delete("/items/{item_id}", status_code=204)
    def delete_item(
        item_id: str,
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        data = _load()
        orig = len(data["items"])
        data["items"] = [i for i in data["items"] if i["id"] != item_id]
        if len(data["items"]) == orig:
            raise HTTPException(404, f"Item '{item_id}' not found")
        _save(data)

    return router
