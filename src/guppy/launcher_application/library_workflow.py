from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
from pathlib import Path

from src.guppy.launcher_application.library_media import describe_library_media_path
from src.guppy.launcher_application.library_storage import (
    delete_workspace_library_item,
    list_workspace_library_items,
    save_workspace_library_item,
    update_workspace_library_item,
    upsert_approved_root,
)


_LIBRARY_DEFAULTS_PATH = Path(__file__).resolve().parents[3] / "runtime" / "library_workspace_defaults.json"


def _load_workspace_defaults() -> dict[str, str]:
    try:
        payload = json.loads(_LIBRARY_DEFAULTS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    result: dict[str, str] = {}
    for key, value in payload.items():
        name = str(key or "").strip()
        title = str(value or "").strip()
        if name and title:
            result[name] = title
    return result


def _save_workspace_defaults(defaults: dict[str, str]) -> None:
    clean = {
        str(key or "").strip(): str(value or "").strip()
        for key, value in defaults.items()
        if str(key or "").strip() and str(value or "").strip()
    }
    try:
        _LIBRARY_DEFAULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _LIBRARY_DEFAULTS_PATH.write_text(
            json.dumps(clean, ensure_ascii=True, sort_keys=True, indent=2),
            encoding="utf-8",
        )
    except Exception:
        return


def sync_assistant_library_context(assistant_view, library_view, active_items: list[dict[str, str]]) -> None:
    if library_view is not None and hasattr(assistant_view, "set_resource_context"):
        assistant_view.set_resource_context(**library_view.chat_dock_context())
    if hasattr(assistant_view, "set_active_context_items"):
        assistant_view.set_active_context_items(active_items)


def apply_library_payload(assistant_view, library_view, active_items: list[dict[str, str]], active_payload: dict, snapshot: dict) -> None:
    if library_view is None or not isinstance(active_payload, dict):
        return
    library_view.set_instance_context(active_payload, snapshot)
    sync_assistant_library_context(assistant_view, library_view, active_items)


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


def summarize_reply_for_library(content: str) -> tuple[str, str]:
    text = str(content or "").strip()
    if not text:
        return ("Saved chat reply", "")
    lines = [line.strip(" -*#>\t") for line in text.splitlines() if line.strip()]
    title = next((line for line in lines if line), "Saved chat reply")
    title = title[:72].rstrip(" .,:;-") or "Saved chat reply"
    summary = text.replace("\r\n", "\n").replace("\r", "\n")
    if len(summary) > 420:
        summary = summary[:417].rstrip() + "..."
    return (title, summary)


def summarize_reply_artifact(content: str) -> tuple[str, str]:
    title, summary = summarize_reply_for_library(content)
    artifact_title = title if title.lower().endswith("artifact") else f"{title} artifact"
    return (artifact_title[:84].rstrip(), summary)


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
    title_text = str(title or "").strip() or "Selected library item"
    item_path_text = str(item_path or "").strip()
    kind_text = str(item_kind or "file").strip().lower() or "file"
    media = describe_library_media_path(item_path_text)
    if kind_text == "note":
        return {
            "title": title_text,
            "kind": kind_text,
            "detail": "Pinned note from Library. Use this as the current source for the next reply.",
            "origin": "library_note",
            "source_label": "Pinned note",
        }
    if media.is_media:
        media_label = media.source_label or "Local media"
        return {
            "title": title_text,
            "kind": kind_text,
            "detail": f"{media_label} from Library | {item_path_text or media.path}",
            "origin": "library_media",
            "source_label": media_label,
        }
    return {
        "title": title_text,
        "kind": kind_text,
        "detail": item_path_text or f"{kind_text} context from the active workspace library",
        "origin": "library_source",
        "source_label": "",
    }


def _truncate_context_text(text: str, limit: int = 220) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 3)].rstrip() + "..."


@dataclass(frozen=True)
class LibraryChatSubmission:
    request_message: str
    history: list[dict[str, str]]
    status_text: str
    background_event: str
    context_notice: str


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


class LibraryWorkflowController:
    def __init__(
        self,
        *,
        assistant_view,
        status_panel,
        get_active_items: Callable[[], list[dict[str, str]]],
        set_active_items: Callable[[list[dict[str, str]]], None],
        get_active_instance_name: Callable[[], str],
        get_library_view: Callable[[], object | None],
        refresh_library_surface: Callable[[], None],
        on_tab_change: Callable[[int], None],
        set_daily_activity: Callable[[str], None],
        log_launcher_event: Callable[..., None],
    ) -> None:
        self._assistant_view = assistant_view
        self._status_panel = status_panel
        self._get_active_items = get_active_items
        self._set_active_items = set_active_items
        self._get_active_instance_name = get_active_instance_name
        self._get_library_view = get_library_view
        self._refresh_library_surface = refresh_library_surface
        self._on_tab_change = on_tab_change
        self._set_daily_activity = set_daily_activity
        self._log_launcher_event = log_launcher_event
        self._workspace_default_sources: dict[str, str] = _load_workspace_defaults()

    def _active_workspace_name(self) -> str:
        return str(self._get_active_instance_name() or "guppy-primary").strip() or "guppy-primary"

    def _workspace_default_title(self) -> str:
        return str(self._workspace_default_sources.get(self._active_workspace_name(), "") or "").strip()

    def _set_workspace_default_title(self, title: str) -> None:
        workspace = self._active_workspace_name()
        normalized = str(title or "").strip()
        if normalized:
            self._workspace_default_sources[workspace] = normalized
        elif workspace in self._workspace_default_sources:
            self._workspace_default_sources.pop(workspace, None)
        _save_workspace_defaults(self._workspace_default_sources)

    def _prioritize_workspace_default(self, items: list[dict[str, str]]) -> list[dict[str, str]]:
        default_title = self._workspace_default_title()
        if not default_title:
            return items[:3]
        match = None
        remainder: list[dict[str, str]] = []
        for item in items:
            title = str(item.get("title", "") or "").strip()
            if match is None and title == default_title:
                match = item
                continue
            remainder.append(item)
        if match is None:
            return items[:3]
        return [match, *remainder][:3]

    def sync(self, library_view=None) -> None:
        sync_assistant_library_context(
            self._assistant_view,
            library_view if library_view is not None else self._get_library_view(),
            self._get_active_items(),
        )
        if hasattr(self._assistant_view, "set_default_context_source"):
            self._assistant_view.set_default_context_source(self._workspace_default_title())

    def handle_context_requested(self, title: str, item_path: str, item_kind: str, prompt: str) -> None:
        title_text = str(title or "").strip() or "Selected library item"
        item_path_text = str(item_path or "").strip()
        kind_text = str(item_kind or "file").strip().lower() or "file"
        prompt_text = str(prompt or "").strip() or f"Use {title_text} as context and help me work with it."
        next_primary = build_library_context_item(title_text, item_path_text, kind_text)
        if kind_text == "note":
            for item in list_workspace_library_items(self._active_workspace_name(), kinds=("note",), limit=24):
                item_title = str(item.get("title", "") or "").strip()
                if item_title != title_text:
                    continue
                metadata = item.get("metadata", {}) if isinstance(item.get("metadata", {}), dict) else {}
                source = str(metadata.get("source", "") or "").strip().lower()
                note_body = _truncate_context_text(str(item.get("summary", "") or ""))
                next_primary["detail"] = note_body or next_primary["detail"]
                next_primary["source_label"] = "Saved reply note" if source == "assistant_reply" else "Pinned note"
                break
        active_items = self._get_active_items()
        next_items = [
            next_primary,
            *[
                item
                for item in active_items
                if str(item.get("title", "")).strip() != title_text
            ],
        ][:3]
        next_items = self._prioritize_workspace_default(next_items)
        self._set_active_items(next_items)
        if hasattr(self._assistant_view, "set_active_context_items"):
            self._assistant_view.set_active_context_items(next_items)
        if hasattr(self._assistant_view, "set_input_text"):
            self._assistant_view.set_input_text(prompt_text)
        if hasattr(self._assistant_view, "set_background_event"):
            self._assistant_view.set_background_event(f"Library context ready: {title_text}")
        self._assistant_view.set_status("Context primed")
        self._on_tab_change(0)
        self._set_daily_activity(f"Chat primed with library context: {title_text}")
        self._status_panel.append_syslog(f"library context primed: {title_text}")
        self._log_launcher_event(
            "library_context_primed",
            title=title_text,
            item_kind=kind_text,
            item_path=item_path_text,
        )

    def handle_context_cleared(self) -> None:
        self._set_active_items([])
        self.sync()
        self._assistant_view.set_status("Ready")
        self._status_panel.append_syslog("library context cleared")
        self._set_daily_activity("Library context cleared from chat")
        self._log_launcher_event("library_context_cleared")

    def handle_context_removed(self, title: str) -> None:
        title_text = str(title or "").strip()
        next_items = [
            item
            for item in self._get_active_items()
            if str(item.get("title", "")).strip() != title_text
        ]
        if self._workspace_default_title() == title_text:
            self._set_workspace_default_title("")
        self._set_active_items(next_items)
        self.sync()
        self._status_panel.append_syslog(f"library context removed: {title_text}")
        self._log_launcher_event("library_context_removed", title=title_text)

    def handle_context_focused(self, title: str) -> None:
        title_text = str(title or "").strip()
        active_items = [item for item in self._get_active_items() if isinstance(item, dict)]
        if not title_text or len(active_items) < 2:
            return
        focused = None
        remaining: list[dict[str, str]] = []
        for item in active_items:
            if focused is None and str(item.get("title", "")).strip() == title_text:
                focused = item
                continue
            remaining.append(item)
        if focused is None:
            return
        next_items = [focused, *remaining][:3]
        self._set_active_items(next_items)
        self.sync()
        self._assistant_view.set_status("Context focused")
        if hasattr(self._assistant_view, "set_background_event"):
            self._assistant_view.set_background_event(f"Focused Library source: {title_text}")
        self._status_panel.append_syslog(f"library context focused: {title_text}")
        self._set_daily_activity(f"Library focus set to: {title_text}")
        self._log_launcher_event("library_context_focused", title=title_text)

    def handle_default_source_requested(self, title: str) -> None:
        title_text = str(title or "").strip()
        if not title_text:
            self._status_panel.append_syslog("default source rejected: missing title")
            self._log_launcher_event("library_default_source_rejected", reason="missing_title")
            return
        active_titles = {
            str(item.get("title", "") or "").strip()
            for item in self._get_active_items()
            if isinstance(item, dict)
        }
        if title_text not in active_titles:
            self._status_panel.append_syslog(f"default source rejected: not attached ({title_text})")
            self._log_launcher_event(
                "library_default_source_rejected",
                reason="title_not_attached",
                title=title_text,
            )
            return
        self._set_workspace_default_title(title_text)
        next_items = self._prioritize_workspace_default(self._get_active_items())
        self._set_active_items(next_items)
        self.sync()
        self._assistant_view.set_status("Default source pinned")
        if hasattr(self._assistant_view, "set_background_event"):
            self._assistant_view.set_background_event(f"Default source pinned for this workspace: {title_text}")
        if hasattr(self._assistant_view, "set_default_context_source"):
            self._assistant_view.set_default_context_source(title_text)
        self._status_panel.append_syslog(f"default source pinned: {title_text}")
        self._set_daily_activity(f"Default source pinned: {title_text}")
        self._log_launcher_event("library_default_source_pinned", title=title_text)

    def handle_root_requested(self, root_path: str, label: str) -> None:
        library_view = self._get_library_view()
        raw_path = str(root_path or "").strip()
        if not raw_path:
            self._status_panel.append_syslog("approved root rejected: missing path")
            self._set_daily_activity("Library root rejected: missing path")
            self._log_launcher_event("library_root_rejected", reason="missing_path")
            if library_view is not None and hasattr(library_view, "set_root_feedback"):
                library_view.set_root_feedback("Root rejected: missing path.", is_error=True)
            return
        candidate = Path(raw_path).expanduser()
        try:
            resolved = candidate.resolve()
        except OSError:
            self._status_panel.append_syslog("approved root rejected: unreadable path")
            self._set_daily_activity("Library root rejected: unreadable path")
            self._log_launcher_event("library_root_rejected", reason="unreadable_path", root_path=raw_path)
            if library_view is not None and hasattr(library_view, "set_root_feedback"):
                library_view.set_root_feedback("Root rejected: unreadable path.", is_error=True)
            return
        if not resolved.exists() or not resolved.is_dir():
            self._status_panel.append_syslog("approved root rejected: folder not found")
            self._set_daily_activity("Library root rejected: folder not found")
            self._log_launcher_event("library_root_rejected", reason="missing_folder", root_path=str(resolved))
            if library_view is not None and hasattr(library_view, "set_root_feedback"):
                library_view.set_root_feedback("Root rejected: folder not found.", is_error=True)
            return
        normalized_path = str(resolved)
        root_label = str(label or "").strip() or (resolved.name.strip() if resolved.name else "Approved root")
        saved = upsert_approved_root(normalized_path, label=root_label, source="library_ui", enabled=True)
        self._refresh_library_surface()
        self._status_panel.append_syslog(f"approved root saved: {saved['label']}")
        self._set_daily_activity(f"Library root saved: {saved['label']}")
        self._log_launcher_event("library_root_saved", label=saved["label"], root_path=saved["root_path"])
        if library_view is not None and hasattr(library_view, "set_root_feedback"):
            library_view.set_root_feedback(f"Approved root saved: {saved['label']}", is_error=False)

    def handle_note_requested(self, title: str, summary: str) -> None:
        saved = save_workspace_library_item(
            self._get_active_instance_name(),
            item_kind="note",
            title=title,
            summary=summary,
            metadata={"source": "library_ui"},
        )
        self._refresh_library_surface()
        self._status_panel.append_syslog(f"pinned note saved: {saved['title']}")
        self._set_daily_activity(f"Library note saved: {saved['title']}")
        self._log_launcher_event("library_note_saved", title=saved["title"])

    def handle_note_updated(self, item_id: int, title: str, summary: str) -> None:
        saved = update_workspace_library_item(
            item_id,
            title=title,
            summary=summary,
            metadata={"source": "library_ui"},
        )
        if not saved:
            self._status_panel.append_syslog("library note update failed")
            return
        self._refresh_library_surface()
        self._status_panel.append_syslog(f"pinned note updated: {saved['title']}")
        self._set_daily_activity(f"Library note updated: {saved['title']}")
        self._log_launcher_event("library_note_updated", item_id=item_id, title=saved["title"])

    def handle_artifact_requested(self, title: str, item_path: str, summary: str) -> None:
        saved = save_workspace_library_item(
            self._get_active_instance_name(),
            item_kind="artifact",
            title=title,
            summary=summary,
            item_path=item_path or None,
            metadata={"source": "library_ui"},
        )
        self._refresh_library_surface()
        self._status_panel.append_syslog(f"artifact saved: {saved['title']}")
        self._set_daily_activity(f"Library artifact saved: {saved['title']}")
        self._log_launcher_event("library_artifact_saved", title=saved["title"], item_path=saved["item_path"])

    def handle_artifact_updated(self, item_id: int, title: str, item_path: str, summary: str) -> None:
        saved = update_workspace_library_item(
            item_id,
            title=title,
            summary=summary,
            item_path=item_path or "",
            metadata={"source": "library_ui"},
        )
        if not saved:
            self._status_panel.append_syslog("library artifact update failed")
            return
        self._refresh_library_surface()
        self._status_panel.append_syslog(f"artifact updated: {saved['title']}")
        self._set_daily_activity(f"Library artifact updated: {saved['title']}")
        self._log_launcher_event(
            "library_artifact_updated",
            item_id=item_id,
            title=saved["title"],
            item_path=saved["item_path"],
        )

    def handle_item_deleted(self, item_id: int, title: str) -> None:
        title_text = str(title or "").strip() or "Library item"
        if not delete_workspace_library_item(item_id):
            self._status_panel.append_syslog(f"library delete failed: {title_text}")
            return
        if self._workspace_default_title() == title_text:
            self._set_workspace_default_title("")
        next_items = [
            item
            for item in self._get_active_items()
            if str(item.get("title", "")).strip() != title_text
        ]
        self._set_active_items(next_items)
        self._refresh_library_surface()
        self._status_panel.append_syslog(f"library item deleted: {title_text}")
        self._set_daily_activity(f"Library item removed: {title_text}")
        self._log_launcher_event("library_item_deleted", item_id=item_id, title=title_text)

    def handle_reply_saved(self, content: str, *, attach_next: bool = False) -> None:
        title, summary = summarize_reply_for_library(content)
        if not summary:
            self._status_panel.append_syslog("reply save skipped: empty reply")
            return
        saved = save_workspace_library_item(
            self._get_active_instance_name(),
            item_kind="note",
            title=title,
            summary=summary,
            metadata={"source": "assistant_reply", "attach_next": bool(attach_next)},
        )
        if attach_next:
            detail = f"Saved from the latest assistant reply in {self._get_active_instance_name()}"
            next_items = [
                {
                    "title": saved["title"],
                    "kind": "note",
                    "detail": detail,
                    "origin": "assistant_reply",
                    "source_label": "Saved reply note",
                },
                *[
                    item
                    for item in self._get_active_items()
                    if str(item.get("title", "")).strip() != str(saved["title"]).strip()
                ],
            ][:3]
            self._set_active_items(next_items)
            self.sync()
            self._assistant_view.set_status("Reply attached")
            if hasattr(self._assistant_view, "set_background_event"):
                self._assistant_view.set_background_event(f"Saved and attached reply: {saved['title']}")
            self._status_panel.append_syslog(f"assistant reply attached: {saved['title']}")
            self._set_daily_activity(f"Reply saved and attached: {saved['title']}")
            self._log_launcher_event("assistant_reply_attached", title=saved["title"])
        else:
            self._refresh_library_surface()
            self._assistant_view.set_status("Reply saved")
            if hasattr(self._assistant_view, "set_background_event"):
                self._assistant_view.set_background_event(f"Saved reply to Library: {saved['title']}")
            self._status_panel.append_syslog(f"assistant reply saved: {saved['title']}")
            self._set_daily_activity(f"Reply saved to Library: {saved['title']}")
            self._log_launcher_event("assistant_reply_saved", title=saved["title"])

    def handle_reply_artifact_saved(self, content: str, *, attach_now: bool = False) -> None:
        title, summary = summarize_reply_artifact(content)
        if not summary:
            self._status_panel.append_syslog("reply artifact save skipped: empty reply")
            return
        saved = save_workspace_library_item(
            self._get_active_instance_name(),
            item_kind="artifact",
            title=title,
            summary=summary,
            metadata={"source": "assistant_reply_artifact", "source_label": "Saved reply artifact"},
        )
        self._refresh_library_surface()
        self._assistant_view.set_status("Artifact saved")
        if hasattr(self._assistant_view, "set_latest_saved_output"):
            self._assistant_view.set_latest_saved_output(
                title=saved["title"],
                summary=summary,
                source_label="Saved reply artifact",
            )
        if hasattr(self._assistant_view, "set_background_event"):
            self._assistant_view.set_background_event(f"Saved reply artifact to Library: {saved['title']}")
        self._status_panel.append_syslog(f"assistant reply artifact saved: {saved['title']}")
        self._set_daily_activity(f"Reply saved as artifact: {saved['title']}")
        self._log_launcher_event("assistant_reply_artifact_saved", title=saved["title"])
        if attach_now:
            self.handle_latest_output_attached(saved["title"], summary)

    def handle_latest_output_attached(self, title: str, summary: str) -> None:
        item = build_saved_output_context_item(title, summary)
        next_items = [
            item,
            *[
                existing
                for existing in self._get_active_items()
                if str(existing.get("title", "")).strip() != item["title"]
            ],
        ][:3]
        next_items = self._prioritize_workspace_default(next_items)
        self._set_active_items(next_items)
        self.sync()
        self._assistant_view.set_status("Output attached")
        if hasattr(self._assistant_view, "set_background_event"):
            self._assistant_view.set_background_event(f"Latest saved output attached: {item['title']}")
        self._status_panel.append_syslog(f"latest saved output attached: {item['title']}")
        self._set_daily_activity(f"Latest saved output attached: {item['title']}")
        self._log_launcher_event("latest_saved_output_attached", title=item["title"])
