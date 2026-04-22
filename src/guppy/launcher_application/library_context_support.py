from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.guppy.launcher_application.library_media import describe_library_media_path
from src.guppy.launcher_application.library_storage import (
    list_approved_roots,
    list_workspace_library_items,
)


@dataclass(frozen=True)
class LibraryChatSubmission:
    request_message: str
    history: list[dict[str, str]]
    status_text: str
    background_event: str
    context_notice: str


def build_saved_output_context_item(title: str, summary: str) -> dict[str, str]:
    title_text = str(title or "").strip() or "Saved output"
    summary_text = str(summary or "").strip()
    detail = summary_text[:180].rstrip()
    return {
        "title": title_text,
        "kind": "artifact",
        "detail": detail or "Saved reply artifact from the latest assistant output",
        "origin": "assistant_reply_artifact",
        "source_label": "Saved reply artifact",
    }


def build_library_context_item(title: str, item_path: str, item_kind: str) -> dict[str, str]:
    return build_library_context_item_with_details(title, item_path, item_kind)


def build_library_context_item_with_details(
    title: str,
    item_path: str,
    item_kind: str,
    *,
    detail: str = "",
    source_label: str = "",
    origin: str = "",
    context_ref: str = "",
) -> dict[str, str]:
    title_text = str(title or "").strip() or "Selected library item"
    item_path_text = str(item_path or "").strip()
    kind_text = str(item_kind or "file").strip().lower() or "file"
    normalized_context_ref = str(context_ref or item_path_text or f"{kind_text}:{title_text}").strip()
    media = describe_library_media_path(item_path_text)
    if kind_text == "note":
        return {
            "title": title_text,
            "kind": kind_text,
            "detail": detail or "Pinned note from Library. Use this as the current source for the next reply.",
            "origin": origin or "library_note",
            "source_label": source_label or "Pinned note",
            "context_ref": normalized_context_ref,
        }
    if media.is_media:
        media_label = str(source_label or media.source_label or "Local media").strip() or "Local media"
        return {
            "title": title_text,
            "kind": kind_text,
            "detail": detail or f"{media_label} from Library | {item_path_text or media.path}",
            "origin": origin or "library_media",
            "source_label": media_label,
            "context_ref": normalized_context_ref,
        }
    return {
        "title": title_text,
        "kind": kind_text,
        "detail": detail or item_path_text or f"{kind_text} context from the active workspace library",
        "origin": origin or "library_source",
        "source_label": str(source_label or "").strip(),
        "context_ref": normalized_context_ref,
    }


def primary_context_label(active_items: list[dict[str, str]] | None) -> str:
    items = [item for item in list(active_items or []) if isinstance(item, dict)]
    if not items:
        return ""
    primary = items[0]
    title = str(primary.get("title", "") or "").strip()
    origin = str(primary.get("origin", "") or "").strip().lower()
    if origin == "assistant_reply" and title:
        return f"saved reply note {title}"
    return title


def compose_library_aware_message(cmd: str, active_items: list[dict[str, str]] | None) -> str:
    command_text = str(cmd or "").strip()
    items = [item for item in list(active_items or []) if isinstance(item, dict)]
    if not items:
        return command_text
    context_lines = []
    for item in items[:3]:
        title = str(item.get("title", "") or "").strip() or "Untitled context"
        kind = str(item.get("kind", "file") or "file").strip().lower() or "file"
        source_label = str(item.get("source_label", "") or "").strip()
        detail = str(item.get("detail", "") or "").strip()
        line = f"- {source_label or kind}: {title}"
        if detail:
            line = f"{line} | {detail}"
        context_lines.append(line)
    prefix = "Use the attached Library context below when answering.\n" + "\n".join(context_lines)
    return f"{prefix}\n\nUser request:\n{command_text}"


def build_library_chat_submission(
    cmd: str,
    history: list[dict[str, str]] | None,
    active_items: list[dict[str, str]] | None,
) -> LibraryChatSubmission:
    items = [item for item in list(active_items or []) if isinstance(item, dict)]
    normalized_history = [dict(item) for item in list(history or []) if isinstance(item, dict)]
    request_message = compose_library_aware_message(cmd, items)
    if not items:
        return LibraryChatSubmission(
            request_message=request_message,
            history=normalized_history,
            status_text="Processing...",
            background_event="",
            context_notice="",
        )
    titles = [str(item.get("title", "") or "").strip() for item in items[:2]]
    titles = [title for title in titles if title]
    primary_label = primary_context_label(items)
    notice = "Using attached Library context for this reply."
    if primary_label and str(items[0].get("origin", "") or "").strip().lower() == "assistant_reply":
        notice = f"Using the saved reply note as the current source for this reply: {str(items[0].get('title', '') or '').strip()}."
    elif titles:
        notice = f"Using attached Library context for this reply: {', '.join(titles)}."
    return LibraryChatSubmission(
        request_message=request_message,
        history=[
            *normalized_history,
            {
                "role": "system",
                "content": "Attached Library context is active for the next reply. Prefer those files, notes, and artifacts when relevant.",
            },
        ],
        status_text=f"Processing with {len(items)} context item(s)...",
        background_event=(
            f"Reply will use the saved reply note first: {str(items[0].get('title', '') or '').strip()}"
            if primary_label and str(items[0].get("origin", "") or "").strip().lower() == "assistant_reply"
            else (f"Reply will use attached Library context: {', '.join(titles)}" if titles else "Reply will use attached Library context.")
        ),
        context_notice=notice,
    )


def resolve_saved_context_payload(
    workspace_name: str,
    *,
    title: str,
    item_path: str,
    item_kind: str,
) -> tuple[str, str, str]:
    normalized_kind = str(item_kind or "file").strip().lower() or "file"
    normalized_title = str(title or "").strip()
    normalized_path = str(item_path or "").strip()
    normalized_item_id = _library_item_id_from_ref(normalized_path)
    media = describe_library_media_path(normalized_path)
    root_label, relative_path = _approved_root_detail(normalized_path)

    if normalized_kind in {"note", "artifact"}:
        candidates = list_workspace_library_items(workspace_name, kinds=(normalized_kind,), limit=24)
        matched: dict[str, object] | None = None
        for item in candidates:
            if not isinstance(item, dict):
                continue
            candidate_id = int(str(item.get("id", "0") or "0"))
            candidate_title = str(item.get("title", "") or "").strip()
            candidate_path = str(item.get("item_path", "") or "").strip()
            if normalized_item_id > 0 and candidate_id == normalized_item_id:
                matched = item
                break
            if normalized_path and candidate_path and candidate_path == normalized_path:
                matched = item
                break
            if normalized_title and candidate_title == normalized_title:
                matched = item
                if not normalized_path:
                    break
        if isinstance(matched, dict):
            metadata = matched.get("metadata", {}) if isinstance(matched.get("metadata", {}), dict) else {}
            source = str(metadata.get("source", "") or "").strip().lower()
            saved_summary = _truncate_context_text(str(matched.get("summary", "") or ""))
            if normalized_kind == "note":
                return (
                    saved_summary or "Pinned note from Library. Use this as the current source for the next reply.",
                    "Saved reply note" if source == "assistant_reply" else (_metadata_source_label(metadata) or "Pinned note"),
                    "assistant_reply" if source == "assistant_reply" else "library_note",
                )
            detail_bits = [bit for bit in (saved_summary, relative_path, root_label) if bit]
            if not detail_bits and normalized_path:
                detail_bits.append(normalized_path)
            if source == "assistant_reply_artifact":
                return (
                    " | ".join(detail_bits) or "Saved reply artifact from the latest assistant output",
                    "Saved reply artifact",
                    "assistant_reply_artifact",
                )
            if media.is_media:
                media_label = media.source_label or "Local media"
                return (
                    " | ".join(detail_bits) or f"{media_label} from Library | {normalized_path or media.path}",
                    media_label,
                    "library_media",
                )
            return (
                " | ".join(detail_bits) or normalized_path or "artifact context from the active workspace library",
                _metadata_source_label(metadata) or root_label,
                "library_source",
            )

    if normalized_kind == "note":
        return (
            "Pinned note from Library. Use this as the current source for the next reply.",
            "Pinned note",
            "library_note",
        )

    detail_bits = [bit for bit in (relative_path, root_label) if bit]
    detail = " | ".join(detail_bits) or normalized_path
    if media.is_media:
        media_label = media.source_label or "Local media"
        if detail:
            detail = f"{media_label} from {root_label or 'Library'} | {detail}"
        return detail, media_label, "library_media"
    return detail, root_label, "library_source"


def _truncate_context_text(text: str, limit: int = 220) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 3)].rstrip() + "..."


def _metadata_source_label(metadata: dict[str, object] | object) -> str:
    if not isinstance(metadata, dict):
        return ""
    explicit = str(metadata.get("source_label", "") or "").strip()
    if explicit:
        return explicit
    source = str(metadata.get("source", "") or "").strip().lower()
    if source == "assistant_reply":
        return "Saved reply note"
    if source == "assistant_reply_artifact":
        return "Saved reply artifact"
    return ""


def _approved_root_detail(item_path: str) -> tuple[str, str]:
    normalized = str(item_path or "").strip()
    if not normalized:
        return "", ""
    try:
        resolved = Path(normalized).expanduser().resolve()
    except OSError:
        return "", ""
    for root in list_approved_roots(limit=24):
        root_path = str(root.get("root_path", "") or "").strip()
        if not root_path:
            continue
        try:
            root_resolved = Path(root_path).expanduser().resolve()
            relative = resolved.relative_to(root_resolved)
        except (OSError, ValueError):
            continue
        label = str(root.get("label", "") or "").strip() or root_resolved.name or str(root_resolved)
        return label, relative.as_posix()
    return "", ""


def _library_item_id_from_ref(item_ref: str) -> int:
    normalized = str(item_ref or "").strip()
    if not normalized.lower().startswith("library-item://"):
        return 0
    try:
        return int(normalized.rsplit("/", 1)[-1].strip())
    except Exception:
        return 0
