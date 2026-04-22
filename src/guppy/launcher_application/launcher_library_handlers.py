"""Shell-side library context handler functions.

Each function takes *owner* (a ``LauncherWindow`` instance) as first argument
and delegates through the library workflow controller or library presentation
helpers.  Moving these out of the shell keeps ``launcher_window.py`` thin.
"""
from __future__ import annotations

from src.guppy.launcher_application import (
    LibraryWorkflowController,
    apply_library_payload,
    compose_library_aware_message as _compose_library_aware_message,
    resolve_active_instance_payload,
    sync_assistant_library_context as _sync_assistant_library_context,
)


# ── Library workflow controller ───────────────────────────────────────────────

def ensure_library_workflow(owner):
    """Return the owner's LibraryWorkflowController, creating it if absent."""
    instance_factory = getattr(owner, "_ensure_library_workflow", None)
    class_factory = getattr(type(owner), "_ensure_library_workflow", None)
    if callable(instance_factory) and class_factory is None:
        return instance_factory()
    workflow = getattr(owner, "_library_workflow", None)
    if workflow is not None:
        return workflow
    workflow = LibraryWorkflowController(
        assistant_view=getattr(owner, "_assistant_view", None),
        status_panel=getattr(owner, "_status_panel", None),
        get_active_items=lambda: list(getattr(owner, "_active_library_context_items", [])),
        set_active_items=lambda items: setattr(owner, "_active_library_context_items", list(items)),
        get_active_instance_name=lambda: getattr(owner, "_active_instance_name", "guppy-primary"),
        get_library_view=lambda: getattr(owner, "_library_view", None),
        refresh_library_surface=lambda: getattr(owner, "_refresh_library_surface", lambda: None)(),
        on_tab_change=lambda index: getattr(owner, "_on_tab_change", lambda _index: None)(index),
        set_daily_activity=lambda text: getattr(owner, "_set_daily_activity", lambda _text: None)(text),
        log_launcher_event=lambda event, **fields: getattr(owner, "_log_launcher_event", lambda *_args, **_kwargs: None)(event, **fields),
    )
    setattr(owner, "_library_workflow", workflow)
    return workflow


# ── Library context sync ──────────────────────────────────────────────────────

def sync_assistant_library_context(owner, library_view) -> None:
    _sync_assistant_library_context(
        owner._assistant_view, library_view, owner._active_library_context_items
    )


def compose_library_aware_message(cmd: str, active_items) -> str:
    return _compose_library_aware_message(cmd, active_items)


def refresh_library_surface(owner) -> None:
    snapshot = owner._last_instance_snapshot if isinstance(owner._last_instance_snapshot, dict) else {}
    active_payload = resolve_active_instance_payload(snapshot, owner._active_instance_name)
    library_view = getattr(owner, "_library_view", None)
    if library_view is not None and isinstance(active_payload, dict):
        apply_library_payload(
            owner._assistant_view,
            library_view,
            owner._active_library_context_items,
            active_payload,
            snapshot,
        )


# ── Library signal handlers ───────────────────────────────────────────────────

def on_library_context_requested(owner, title: str, item_path: str, item_kind: str, prompt: str) -> None:
    ensure_library_workflow(owner).handle_context_requested(title, item_path, item_kind, prompt)


def on_library_context_cleared(owner) -> None:
    ensure_library_workflow(owner).handle_context_cleared()


def on_library_context_focused(owner, title: str) -> None:
    ensure_library_workflow(owner).handle_context_focused(title)


def on_library_context_default_requested(owner, title: str) -> None:
    ensure_library_workflow(owner).handle_default_source_requested(title)


def on_library_context_opened(owner, title: str) -> None:
    title_text = str(title or "").strip()
    owner._on_tab_change(2)
    library_view = getattr(owner, "_library_view", None)
    if library_view is not None and hasattr(library_view, "focus_search_query"):
        library_view.focus_search_query(title_text)
    owner._set_daily_activity(f"Library opened for source: {title_text}")
    owner._status_panel.append_syslog(f"library source opened: {title_text}")
    owner._log_launcher_event("library_context_opened", title=title_text)


def on_library_context_removed(owner, title: str) -> None:
    ensure_library_workflow(owner).handle_context_removed(title)


def on_library_root_requested(owner, root_path: str, label: str) -> None:
    ensure_library_workflow(owner).handle_root_requested(root_path, label)


def on_library_note_requested(owner, title: str, summary: str) -> None:
    ensure_library_workflow(owner).handle_note_requested(title, summary)


def on_library_note_updated(owner, item_id: int, title: str, summary: str) -> None:
    ensure_library_workflow(owner).handle_note_updated(item_id, title, summary)


def on_library_artifact_requested(owner, title: str, item_path: str, summary: str) -> None:
    ensure_library_workflow(owner).handle_artifact_requested(title, item_path, summary)


def on_library_artifact_updated(owner, item_id: int, title: str, item_path: str, summary: str) -> None:
    ensure_library_workflow(owner).handle_artifact_updated(item_id, title, item_path, summary)


def on_library_item_deleted(owner, item_id: int, title: str) -> None:
    ensure_library_workflow(owner).handle_item_deleted(item_id, title)


def on_assistant_reply_library_requested(owner, content: str, attach_next: bool) -> None:
    ensure_library_workflow(owner).handle_reply_saved(content, attach_next=attach_next)


def on_assistant_reply_artifact_requested(owner, content: str) -> None:
    ensure_library_workflow(owner).handle_reply_artifact_saved(content)


def on_latest_saved_output_attached(owner, title: str, summary: str) -> None:
    ensure_library_workflow(owner).handle_latest_output_attached(title, summary)


def on_active_context_refresh_requested(owner, content: str, as_artifact: bool) -> None:
    workflow = ensure_library_workflow(owner)
    if as_artifact:
        workflow.handle_reply_artifact_saved(content, attach_now=True)
    else:
        workflow.handle_reply_saved(content, attach_next=True)
