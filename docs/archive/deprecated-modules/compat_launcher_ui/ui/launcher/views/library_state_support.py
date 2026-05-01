from __future__ import annotations

from PySide6.QtCore import Qt

from src.guppy.launcher_application.library_presenter import build_library_surface_state


def rebuild_state(owner) -> None:
    owner._state = build_library_surface_state(
        str(owner._instance_context.get("name", "guppy-primary") or "guppy-primary"),
        workspace_type=str(owner._instance_context.get("type", "user_instance") or "user_instance"),
        description=str(owner._instance_context.get("description", "") or ""),
        mode=str(owner._instance_context.get("mode", "auto") or "auto"),
        last_message=str(owner._instance_context.get("last_message", "") or ""),
        selected_root_path=owner._selected_root_path,
    )


def browse_root(owner, root_path: str) -> None:
    owner._selected_root_path = str(root_path or "").strip()
    rebuild_state(owner)
    apply_state(owner)


def set_selected_root(owner, root_path: str) -> None:
    path = str(root_path or "").strip()
    if not path:
        return
    owner._selected_root_path = path
    rebuild_state(owner)
    apply_state(owner)


def on_root_picker_changed(owner, index: int) -> None:
    if index < 0:
        return
    root_path = str(owner._root_picker.itemData(index) or "").strip()
    if not root_path or root_path == owner._selected_root_path:
        return
    browse_root(owner, root_path)


def apply_state(owner) -> None:
    owner._workspace_chip.setText(owner._state.workspace_label.upper())
    owner._summary_lbl.setText(owner._state.library_summary)
    owner._roots_lbl.setText(owner._state.roots_summary)
    owner._recent_lbl.setText(owner._state.recent_summary)
    owner._search.setPlaceholderText(owner._state.search_hint)
    owner._files_copy.setText(owner._state.files_summary)
    owner._study_copy.setText(owner._state.study_summary)
    owner._coding_copy.setText(owner._state.coding_summary)
    owner._artifact_copy.setText(owner._state.artifact_summary)
    owner._search_status_lbl.setText(_search_status_text(owner))
    owner._sync_root_picker()
    owner._rebuild_roots()
    owner._rebuild_browse_cards()
    owner._rebuild_recent_cards()
    owner._rebuild_saved_cards()
    owner._root_label.setPlaceholderText(f"Label for {owner._state.workspace_label.lower()} root")
    if not owner._selected_root_path and owner._state.approved_roots:
        owner._selected_root_path = str(owner._state.approved_roots[0].get("root_path", "") or "").strip()
    if owner.isVisible():
        owner._apply_density_mode(owner.width())
    owner._refresh_artifact_editor_state()


def set_instance_context(owner, instance: dict[str, object], snapshot: dict[str, object] | None = None) -> None:
    del snapshot
    owner._instance_context = dict(instance or {})
    rebuild_state(owner)
    owner._selected_root_path = (
        owner._state.approved_roots[0]["root_path"]
        if owner._state.approved_roots and not owner._selected_root_path
        else owner._selected_root_path
    )
    rebuild_state(owner)
    apply_state(owner)


def apply_search_query(owner, text: str) -> None:
    owner._search_query = str(text or "").strip().lower()
    apply_state(owner)


def _search_status_text(owner) -> str:
    browse_count = len(filtered_root_file_cards(owner))
    recent_count = len(filtered_recent_cards(owner))
    saved_count = len(filtered_saved_item_cards(owner))
    if owner._search_query:
        return (
            f'Matches for "{owner._search_query}": '
            f"{browse_count} browse | {recent_count} recent | {saved_count} saved."
        )
    root_label = owner._state.selected_root_label or "approved root"
    return (
        f"Current root: {root_label}. Browse covers approved files, Recent covers quick reuse, "
        "and Pinned keeps durable notes and artifacts."
    )


def focus_search_query(owner, text: str) -> None:
    query = str(text or "").strip()
    owner._search.setText(query)
    owner._search.setFocus(Qt.FocusReason.OtherFocusReason)


def matches_query(owner, *parts: str) -> bool:
    query = owner._search_query
    if not query:
        return True
    haystack = " ".join(str(part or "") for part in parts).lower()
    return query in haystack


def matches_card_query(owner, card: dict[str, str], *fallback_parts: str) -> bool:
    search_text = str(card.get("search_text", "") or "").strip()
    if search_text:
        return matches_query(owner, search_text)
    return matches_query(owner, *fallback_parts)


def filtered_root_file_cards(owner) -> list[dict[str, str]]:
    return [
        card
        for card in owner._state.root_file_cards
        if matches_card_query(
            owner,
            card,
            str(card.get("title", "") or ""),
            str(card.get("detail", "") or ""),
            str(card.get("kind", "") or ""),
        )
    ]


def filtered_recent_cards(owner) -> list[dict[str, str]]:
    return [
        card
        for card in owner._state.recent_cards
        if matches_card_query(
            owner,
            card,
            str(card.get("title", "") or ""),
            str(card.get("detail", "") or ""),
            str(card.get("kind", "") or ""),
        )
    ]


def filtered_saved_item_cards(owner) -> list[dict[str, str]]:
    return [
        card
        for card in owner._state.saved_item_cards
        if matches_card_query(
            owner,
            card,
            str(card.get("title", "") or ""),
            str(card.get("detail", "") or ""),
            str(card.get("kind", "") or ""),
            str(card.get("summary", "") or ""),
        )
    ]


def current_source_summary(owner, lane: str, fallback: str) -> str:
    kind_map = {
        "files": {"file"},
        "study": {"study", "note"},
        "coding": {"coding", "artifact"},
    }
    target_kinds = kind_map.get(lane, {lane})
    for origin, cards in (
        ("saved", filtered_saved_item_cards(owner)),
        ("recent", filtered_recent_cards(owner)),
        ("root", filtered_root_file_cards(owner)),
    ):
        for card in cards:
            kind = str(card.get("kind", "") or "").strip().lower()
            if kind not in target_kinds:
                continue
            title = str(card.get("title", "") or "").strip()
            if not title:
                continue
            detail_bits: list[str] = []
            if origin == "root" and owner._state.selected_root_label:
                detail_bits.append(f"from {owner._state.selected_root_label}")
            elif origin == "saved":
                detail_bits.append("from saved Library items")
            elif origin == "recent":
                detail_bits.append("from recent Library items")
            if owner._search_query:
                detail_bits.append(f'matching "{owner._search_query}"')
            suffix = f" ({'; '.join(detail_bits)})" if detail_bits else ""
            return f"Current source: {title}{suffix}."
    return fallback


def chat_dock_context(owner) -> dict[str, str]:
    return {
        "files": current_source_summary(owner, "files", owner._state.files_summary),
        "study": current_source_summary(owner, "study", owner._state.study_summary),
        "coding": current_source_summary(owner, "coding", owner._state.coding_summary),
    }
