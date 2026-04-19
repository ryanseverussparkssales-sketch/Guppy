from __future__ import annotations

from dataclasses import dataclass

from src.guppy.launcher_application.library_storage import (
    build_workspace_library_snapshot,
    list_root_files,
)


def _truncate(text: str, limit: int = 92) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 3)].rstrip() + "..."


def _workspace_label(workspace_type: str) -> str:
    key = str(workspace_type or "user_instance").strip().lower()
    return {
        "user_instance": "Daily workspace",
        "builder_instance": "Builder workspace",
        "read_only_instance": "Reference workspace",
        "admin_instance": "Operations workspace",
    }.get(key, "Workspace")


@dataclass(frozen=True)
class LibrarySurfaceState:
    workspace_label: str
    library_summary: str
    roots_summary: str
    files_summary: str
    study_summary: str
    coding_summary: str
    artifact_summary: str
    recent_summary: str
    search_hint: str
    approved_roots: list[dict[str, str]]
    selected_root_label: str
    selected_root_hint: str
    root_file_cards: list[dict[str, str]]
    saved_item_cards: list[dict[str, str]]
    recent_cards: list[dict[str, str]]


def _item_detail(item: dict[str, object]) -> str:
    summary = str(item.get("summary", "") or "").strip()
    item_path = str(item.get("item_path", "") or "").strip()
    source_label = str(item.get("source_label", "") or "").strip()
    parts = [part for part in (summary, source_label, item_path) if part]
    joined = " | ".join(parts)
    return _truncate(joined, limit=160)


def _item_prompt(item: dict[str, object], workspace_name: str) -> str:
    title = str(item.get("title", "") or "").strip() or "this item"
    item_path = str(item.get("item_path", "") or "").strip()
    kind = str(item.get("item_kind", "file") or "file").strip().lower()
    if kind == "coding":
        return f"Use {title} as coding context for {workspace_name} and help me work through it."
    if kind == "study":
        return f"Use {title} as study context for {workspace_name} and help me review it."
    if kind == "artifact":
        return f"Use {title} as artifact context for {workspace_name} and help me work with the latest outputs."
    if kind == "note":
        return f"Use the pinned note {title} as context for {workspace_name} and help me continue from it."
    return f"Use {title} as file context for {workspace_name} and help me work with it."


def build_library_surface_state(
    workspace_name: str,
    *,
    workspace_type: str = "user_instance",
    description: str = "",
    mode: str = "auto",
    last_message: str = "",
    selected_root_path: str = "",
    include_root_file_cards: bool = True,
) -> LibrarySurfaceState:
    name = str(workspace_name or "guppy-primary").strip() or "guppy-primary"
    kind = str(workspace_type or "user_instance").strip().lower() or "user_instance"
    purpose = str(description or "").strip()
    latest = _truncate(last_message)
    mode_text = str(mode or "auto").strip().upper() or "AUTO"
    workspace_label = _workspace_label(kind)
    try:
        storage = build_workspace_library_snapshot(name)
    except Exception:
        storage = {
            "approved_root_count": 0,
            "approved_roots": [],
            "kind_counts": {},
            "recent_items": [],
            "user_data_dir": "",
        }

    root_labels = [
        str(root.get("label", "") or "").strip()
        for root in list(storage.get("approved_roots", []))
        if isinstance(root, dict)
    ]
    root_labels = [label for label in root_labels if label]
    root_rollup = ", ".join(root_labels[:3]) if root_labels else "No approved roots yet"
    kind_counts = dict(storage.get("kind_counts", {})) if isinstance(storage.get("kind_counts", {}), dict) else {}
    file_count = int(kind_counts.get("file", 0) or 0)
    study_count = int(kind_counts.get("study", 0) or 0)
    coding_count = int(kind_counts.get("coding", 0) or 0)
    artifact_count = int(kind_counts.get("artifact", 0) or 0)
    recent_items = list(storage.get("recent_items", [])) if isinstance(storage.get("recent_items", []), list) else []
    recent_filesystem_items = (
        list(storage.get("recent_filesystem_items", []))
        if isinstance(storage.get("recent_filesystem_items", []), list)
        else []
    )
    approved_roots = [
        {
            "label": str(root.get("label", "") or "").strip(),
            "detail": _truncate(str(root.get("root_path", "") or "").strip(), limit=92),
            "root_path": str(root.get("root_path", "") or "").strip(),
        }
        for root in list(storage.get("approved_roots", []))[:4]
        if isinstance(root, dict)
    ]
    selected_root = str(selected_root_path or "").strip()
    if not selected_root and approved_roots:
        selected_root = str(approved_roots[0].get("root_path", "") or "").strip()
    selected_root_label = next(
        (
            str(root.get("label", "") or "").strip()
            for root in approved_roots
            if str(root.get("root_path", "") or "").strip() == selected_root
        ),
        "",
    )
    root_file_cards: list[dict[str, str]] = []
    if selected_root and include_root_file_cards:
        for item in list_root_files(selected_root, limit=8):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "") or "").strip()
            if not title:
                continue
            root_file_cards.append(
                {
                    "title": _truncate(title, limit=52),
                    "detail": _item_detail(item),
                    "kind": str(item.get("item_kind", "file") or "file").strip().lower(),
                    "item_path": str(item.get("item_path", "") or "").strip(),
                    "action_label": "USE IN CHAT",
                    "prompt": _item_prompt(item, name),
                }
            )

    saved_item_cards: list[dict[str, str]] = []
    for item in recent_items:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("item_kind", "file") or "file").strip().lower()
        if kind not in {"note", "artifact"}:
            continue
        title = str(item.get("title", "") or "").strip()
        if not title:
            continue
        saved_item_cards.append(
            {
                "id": str(item.get("id", "") or "").strip(),
                "title": _truncate(title, limit=48),
                "full_title": title,
                "detail": _item_detail(item),
                "kind": kind,
                "item_path": str(item.get("item_path", "") or "").strip(),
                "summary": str(item.get("summary", "") or "").strip(),
                "action_label": "USE IN CHAT",
                "prompt": _item_prompt(item, name),
            }
        )

    recent_cards: list[dict[str, str]] = []
    for item in recent_items + recent_filesystem_items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "") or "").strip()
        if not title:
            continue
        recent_cards.append(
            {
                "title": _truncate(title, limit=48),
                "detail": _item_detail(item),
                "kind": str(item.get("item_kind", "file") or "file").strip().lower(),
                "item_path": str(item.get("item_path", "") or "").strip(),
                "action_label": "USE IN CHAT",
                "prompt": _item_prompt(item, name),
            }
        )
        if len(recent_cards) >= 6:
            break

    files_summary = {
        "user_instance": "Keep notes, PDFs, inbox exports, and recurring reference files together.",
        "builder_instance": "Collect specs, repo notes, issue snippets, test plans, and generated artifacts in one place.",
        "read_only_instance": "Pin trusted sources, screenshots, and comparison material for safe reference work.",
        "admin_instance": "Keep receipts, logs, runbooks, and recovery artifacts close to the workspace that needs them.",
    }.get(kind, "Keep the files that matter to this workspace together.")

    study_summary = {
        "user_instance": "Turn saved material into summaries, study packets, reading lists, and follow-up questions.",
        "builder_instance": "Convert source sets into review checklists, outlines, comparison notes, and teaching aids.",
        "read_only_instance": "Use source packs for evidence review, fact checking, and side-by-side comparisons.",
        "admin_instance": "Capture repair notes, release evidence, and repeatable operator guidance for later use.",
    }.get(kind, "Capture reading context, summaries, and notes here.")

    coding_summary = {
        "user_instance": "Save lightweight file drafts, snippets, and repeatable templates when a request grows beyond chat.",
        "builder_instance": "Keep module targets, failing-test notes, generated diffs, and review prompts together for coding support.",
        "read_only_instance": "Track source locations, read-only findings, and safe excerpts without crossing into write actions.",
        "admin_instance": "Save commands, diagnostics, and repair sequences that belong with this system workflow.",
    }.get(kind, "Save coding context, snippets, and outputs that belong to this workspace.")

    summary_bits = [f"{workspace_label} for {name}."]
    if purpose:
        summary_bits.append(purpose)
    summary_bits.append(f"Default mode: {mode_text}.")
    summary_bits.append(
        f"Approved roots: {int(storage.get('approved_root_count', 0) or 0)}. "
        f"Saved items: {file_count + study_count + coding_count + artifact_count}."
    )
    library_summary = " ".join(summary_bits)
    roots_summary = (
        f"Approved roots stay explicit so Guppy does not crawl your whole PC by default. "
        f"Current roots: {root_rollup}."
    )

    if file_count:
        files_summary = f"{files_summary} Saved file/source items: {file_count}. Approved roots: {root_rollup}."
    else:
        files_summary = f"{files_summary} Approved roots: {root_rollup}."

    if study_count:
        study_summary = f"{study_summary} Saved study items: {study_count}."

    if coding_count:
        coding_summary = f"{coding_summary} Saved coding items: {coding_count}."

    artifact_summary = (
        "Library storage is isolated under Guppy user data so local indexes and databases stay out of the repo. "
        "Use approved roots to point at repo folders, external drives, or connected storage without granting full-PC crawl access."
    )
    if artifact_count:
        artifact_summary = f"{artifact_summary} Saved artifact bundles: {artifact_count}."

    if recent_items:
        recent_titles = [
            _truncate(str(item.get("title", "") or ""), limit=44)
            for item in recent_items[:3]
            if isinstance(item, dict)
        ]
        recent_titles = [title for title in recent_titles if title]
        recent_summary = f"Recent library items: {' | '.join(recent_titles)}"
    elif recent_filesystem_items:
        recent_titles = [
            _truncate(str(item.get("title", "") or ""), limit=44)
            for item in recent_filesystem_items[:3]
            if isinstance(item, dict)
        ]
        recent_titles = [title for title in recent_titles if title]
        recent_summary = f"Recent approved-root files: {' | '.join(recent_titles)}"
    elif latest:
        recent_summary = f"Current thread: {latest}"
    else:
        recent_summary = "Recent thread context will land here once files or notes are saved."

    search_hint = {
        "builder_instance": "Search files, specs, repo notes, and generated artifacts",
        "read_only_instance": "Search sources, notes, and evidence",
        "admin_instance": "Search logs, receipts, and repair notes",
    }.get(kind, "Search files, notes, approved roots, and saved workspace context")

    return LibrarySurfaceState(
        workspace_label=workspace_label,
        library_summary=library_summary,
        roots_summary=roots_summary,
        files_summary=files_summary,
        study_summary=study_summary,
        coding_summary=coding_summary,
        artifact_summary=artifact_summary,
        recent_summary=recent_summary,
        search_hint=search_hint,
        approved_roots=approved_roots,
        selected_root_label=selected_root_label or "Approved root",
        selected_root_hint=(
            f"Active root: {selected_root_label or 'Approved root'}. Browse files here, then use USE IN CHAT to attach one as source context."
            if selected_root
            else "Pick an approved root to browse files before using USE IN CHAT. Guppy only browses approved folders."
        ),
        root_file_cards=root_file_cards,
        saved_item_cards=saved_item_cards,
        recent_cards=recent_cards,
    )
