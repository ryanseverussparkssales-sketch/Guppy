from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.guppy.paths import (
    LIBRARY_ARTIFACTS_DIR,
    LIBRARY_DB_PATH,
    LIBRARY_INDEX_DIR,
    REPO_ROOT,
    USER_DATA_DIR,
)
from utils.db_utils import open_db as _open_db

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS approved_roots (
    root_path TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    source TEXT NOT NULL,
    is_enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_approved_roots_enabled
    ON approved_roots(is_enabled, updated_at DESC);

CREATE TABLE IF NOT EXISTS workspace_library_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_name TEXT NOT NULL,
    item_kind TEXT NOT NULL,
    title TEXT NOT NULL,
    item_path TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_library_items_workspace_kind
    ON workspace_library_items(workspace_name, item_kind, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_library_items_workspace_updated
    ON workspace_library_items(workspace_name, updated_at DESC);
"""

_ALLOWED_ITEM_KINDS = {"file", "study", "coding", "artifact", "note"}
_IGNORED_DISCOVERY_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "runtime",
    ".tmp",
}
_STUDY_EXTENSIONS = {
    ".md",
    ".txt",
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".csv",
}
_CODING_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".ini",
    ".ps1",
    ".bat",
    ".sh",
    ".css",
    ".html",
    ".sql",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_path(path: str | Path) -> str:
    return str(Path(path).expanduser().resolve())


def _kind_for_path(path: Path) -> str:
    suffix = path.suffix.strip().lower()
    if suffix in _CODING_EXTENSIONS:
        return "coding"
    if suffix in _STUDY_EXTENSIONS:
        return "study"
    return "file"


def _conn():
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    LIBRARY_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    LIBRARY_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    LIBRARY_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    return _open_db(LIBRARY_DB_PATH, schema_sql=_SCHEMA_SQL)


def ensure_library_storage() -> Path:
    conn = _conn()
    try:
        pass
    finally:
        conn.close()
    return LIBRARY_DB_PATH


def upsert_approved_root(
    root_path: str | Path,
    *,
    label: str,
    source: str = "manual",
    enabled: bool = True,
) -> dict[str, object]:
    normalized_path = _normalize_path(root_path)
    now = _utc_now()
    conn = _conn()
    try:
        conn.execute(
            """
            INSERT INTO approved_roots (root_path, label, source, is_enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(root_path) DO UPDATE SET
                label=excluded.label,
                source=excluded.source,
                is_enabled=excluded.is_enabled,
                updated_at=excluded.updated_at
            """,
            (normalized_path, str(label or "Approved root").strip() or "Approved root", str(source or "manual").strip() or "manual", 1 if enabled else 0, now, now),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "root_path": normalized_path,
        "label": str(label or "Approved root").strip() or "Approved root",
        "source": str(source or "manual").strip() or "manual",
        "enabled": bool(enabled),
    }


def seed_default_library_roots() -> None:
    ensure_library_storage()
    upsert_approved_root(REPO_ROOT, label="Current Guppy repo", source="repo", enabled=True)


def list_approved_roots(*, enabled_only: bool = True, limit: int = 12) -> list[dict[str, object]]:
    seed_default_library_roots()
    sql = """
        SELECT root_path, label, source, is_enabled, updated_at
        FROM approved_roots
    """
    params: list[object] = []
    if enabled_only:
        sql += " WHERE is_enabled = 1"
    sql += " ORDER BY updated_at DESC, label ASC LIMIT ?"
    params.append(max(1, min(int(limit or 12), 100)))
    conn = _conn()
    try:
        rows = conn.execute(sql, tuple(params)).fetchall()
    finally:
        conn.close()
    return [
        {
            "root_path": str(root_path),
            "label": str(label),
            "source": str(source),
            "enabled": bool(is_enabled),
            "updated_at": str(updated_at),
        }
        for root_path, label, source, is_enabled, updated_at in rows
    ]


def save_workspace_library_item(
    workspace_name: str,
    *,
    item_kind: str,
    title: str,
    summary: str = "",
    item_path: str | Path | None = None,
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    normalized_kind = str(item_kind or "note").strip().lower() or "note"
    if normalized_kind not in _ALLOWED_ITEM_KINDS:
        normalized_kind = "note"
    normalized_workspace = str(workspace_name or "guppy-primary").strip() or "guppy-primary"
    normalized_title = str(title or "Untitled item").strip() or "Untitled item"
    normalized_summary = str(summary or "").strip()
    normalized_item_path = _normalize_path(item_path) if item_path else ""
    payload = json.dumps(metadata or {}, sort_keys=True, ensure_ascii=True)
    now = _utc_now()
    conn = _conn()
    try:
        cursor = conn.execute(
            """
            INSERT INTO workspace_library_items (
                workspace_name, item_kind, title, item_path, summary, metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normalized_workspace,
                normalized_kind,
                normalized_title,
                normalized_item_path,
                normalized_summary,
                payload,
                now,
                now,
            ),
        )
        item_id = int(cursor.lastrowid)
        conn.commit()
    finally:
        conn.close()
    return {
        "id": item_id,
        "workspace_name": normalized_workspace,
        "item_kind": normalized_kind,
        "title": normalized_title,
        "item_path": normalized_item_path,
        "summary": normalized_summary,
        "metadata": metadata or {},
        "updated_at": now,
    }


def list_workspace_library_items(
    workspace_name: str,
    *,
    kinds: tuple[str, ...] | None = None,
    limit: int = 8,
) -> list[dict[str, object]]:
    normalized_workspace = str(workspace_name or "guppy-primary").strip() or "guppy-primary"
    selected_kinds = tuple(kind for kind in (kinds or ()) if kind in _ALLOWED_ITEM_KINDS)
    params: list[object] = [normalized_workspace]
    sql = """
        SELECT id, item_kind, title, item_path, summary, metadata_json, updated_at
        FROM workspace_library_items
        WHERE workspace_name = ?
    """
    if selected_kinds:
        placeholders = ", ".join("?" for _ in selected_kinds)
        sql += f" AND item_kind IN ({placeholders})"
        params.extend(selected_kinds)
    sql += " ORDER BY updated_at DESC, id DESC LIMIT ?"
    params.append(max(1, min(int(limit or 8), 100)))
    conn = _conn()
    try:
        rows = conn.execute(sql, tuple(params)).fetchall()
    finally:
        conn.close()
    items: list[dict[str, object]] = []
    for item_id, item_kind, title, item_path, summary, metadata_json, updated_at in rows:
        try:
            metadata = json.loads(metadata_json or "{}")
        except Exception:
            metadata = {}
        items.append(
            {
                "id": int(item_id),
                "item_kind": str(item_kind),
                "title": str(title),
                "item_path": str(item_path or ""),
                "summary": str(summary or ""),
                "metadata": metadata,
                "updated_at": str(updated_at),
            }
        )
    return items


def update_workspace_library_item(
    item_id: int,
    *,
    title: str | None = None,
    summary: str | None = None,
    item_path: str | Path | None = None,
    metadata: dict[str, object] | None = None,
) -> dict[str, object] | None:
    normalized_id = int(item_id or 0)
    if normalized_id <= 0:
        return None
    conn = _conn()
    try:
        row = conn.execute(
            """
            SELECT workspace_name, item_kind, title, item_path, summary, metadata_json
            FROM workspace_library_items
            WHERE id = ?
            """,
            (normalized_id,),
        ).fetchone()
        if row is None:
            return None
        workspace_name, item_kind, existing_title, existing_item_path, existing_summary, existing_metadata_json = row
        try:
            existing_metadata = json.loads(existing_metadata_json or "{}")
        except Exception:
            existing_metadata = {}
        next_title = str(title if title is not None else existing_title or "").strip() or "Untitled item"
        next_summary = str(summary if summary is not None else existing_summary or "").strip()
        if item_path is None:
            next_item_path = str(existing_item_path or "")
        else:
            next_item_path = _normalize_path(item_path) if str(item_path).strip() else ""
        next_metadata = dict(existing_metadata)
        if metadata:
            next_metadata.update(metadata)
        now = _utc_now()
        conn.execute(
            """
            UPDATE workspace_library_items
            SET title = ?, item_path = ?, summary = ?, metadata_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                next_title,
                next_item_path,
                next_summary,
                json.dumps(next_metadata, sort_keys=True, ensure_ascii=True),
                now,
                normalized_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "id": normalized_id,
        "workspace_name": str(workspace_name),
        "item_kind": str(item_kind),
        "title": next_title,
        "item_path": next_item_path,
        "summary": next_summary,
        "metadata": next_metadata,
        "updated_at": now,
    }


def delete_workspace_library_item(item_id: int) -> bool:
    normalized_id = int(item_id or 0)
    if normalized_id <= 0:
        return False
    conn = _conn()
    try:
        cursor = conn.execute(
            "DELETE FROM workspace_library_items WHERE id = ?",
            (normalized_id,),
        )
        conn.commit()
        return int(cursor.rowcount or 0) > 0
    finally:
        conn.close()


def list_root_files(root_path: str | Path, *, limit: int = 10) -> list[dict[str, object]]:
    normalized_root = _normalize_path(root_path)
    root = Path(normalized_root)
    if not root.exists() or not root.is_dir():
        return []
    approved_root = next(
        (item for item in list_approved_roots(limit=24) if str(item.get("root_path", "") or "").strip() == normalized_root),
        None,
    )
    source_label = (
        str((approved_root or {}).get("label", "") or "").strip()
        or root.name
        or normalized_root
    )
    candidates: list[dict[str, object]] = []
    try:
        for child in root.rglob("*"):
            if not child.is_file():
                continue
            try:
                relative_path = child.relative_to(root)
            except ValueError:
                relative_path = Path(child.name)
            if any(part in _IGNORED_DISCOVERY_DIRS for part in relative_path.parts):
                continue
            try:
                stat = child.stat()
            except OSError:
                continue
            candidates.append(
                {
                    "title": child.name,
                    "item_path": str(child),
                    "item_kind": _kind_for_path(child),
                    "source_root": normalized_root,
                    "source_label": source_label,
                    "summary": f"{relative_path.as_posix()} | {source_label}",
                    "updated_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc)
                    .replace(microsecond=0)
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "_sort_mtime": float(stat.st_mtime),
                }
            )
    except OSError:
        return []
    candidates.sort(key=lambda item: float(item.get("_sort_mtime", 0.0) or 0.0), reverse=True)
    trimmed = candidates[: max(1, min(int(limit or 10), 40))]
    for item in trimmed:
        item.pop("_sort_mtime", None)
    return trimmed


def discover_recent_root_files(*, limit_per_root: int = 4, total_limit: int = 10) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for root in list_approved_roots(limit=12):
        root_path = str(root.get("root_path", "") or "").strip()
        if not root_path:
            continue
        path = Path(root_path)
        if not path.exists() or not path.is_dir():
            continue
        seen_for_root = 0
        try:
            for child in path.rglob("*"):
                if not child.is_file():
                    continue
                try:
                    relative_path = child.relative_to(path)
                except ValueError:
                    relative_path = Path(child.name)
                if any(part in _IGNORED_DISCOVERY_DIRS for part in relative_path.parts):
                    continue
                try:
                    stat = child.stat()
                except OSError:
                    continue
                candidates.append(
                    {
                        "title": child.name,
                        "item_path": str(child),
                        "item_kind": _kind_for_path(child),
                        "source_root": root_path,
                        "source_label": str(root.get("label", "") or "").strip() or path.name,
                        "summary": f"Recent file from {str(root.get('label', '') or '').strip() or path.name}",
                        "updated_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc)
                        .replace(microsecond=0)
                        .isoformat()
                        .replace("+00:00", "Z"),
                        "_sort_mtime": float(stat.st_mtime),
                    }
                )
                seen_for_root += 1
                if seen_for_root >= max(1, int(limit_per_root or 4)):
                    break
        except OSError:
            continue

    candidates.sort(key=lambda item: float(item.get("_sort_mtime", 0.0) or 0.0), reverse=True)
    trimmed = candidates[: max(1, min(int(total_limit or 10), 24))]
    for item in trimmed:
        item.pop("_sort_mtime", None)
    return trimmed


def build_workspace_library_snapshot(workspace_name: str) -> dict[str, object]:
    normalized_workspace = str(workspace_name or "guppy-primary").strip() or "guppy-primary"
    roots = list_approved_roots()
    recent_items = list_workspace_library_items(normalized_workspace, limit=6)
    recent_filesystem_items = discover_recent_root_files(limit_per_root=4, total_limit=8)
    kind_counts = {kind: 0 for kind in _ALLOWED_ITEM_KINDS}
    conn = _conn()
    try:
        rows = conn.execute(
            """
            SELECT item_kind, COUNT(*)
            FROM workspace_library_items
            WHERE workspace_name = ?
            GROUP BY item_kind
            """,
            (normalized_workspace,),
        ).fetchall()
    finally:
        conn.close()
    for item_kind, count in rows:
        kind = str(item_kind or "").strip().lower()
        if kind in kind_counts:
            kind_counts[kind] = int(count or 0)
    return {
        "workspace_name": normalized_workspace,
        "db_path": str(LIBRARY_DB_PATH),
        "approved_root_count": len(roots),
        "approved_roots": roots,
        "kind_counts": kind_counts,
        "recent_items": recent_items,
        "recent_filesystem_items": recent_filesystem_items,
        "index_dir": str(LIBRARY_INDEX_DIR),
        "artifacts_dir": str(LIBRARY_ARTIFACTS_DIR),
        "user_data_dir": str(USER_DATA_DIR),
        "repo_root_path": _normalize_path(REPO_ROOT),
    }
