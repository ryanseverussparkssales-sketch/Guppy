from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from .. import tokens as T
from .library_view_components import body_label as _body
from .library_view_components import mono_label as _mono


def _action_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setStyleSheet(
        f"QPushButton {{ background: {T.BG0}; color: {T.PRIMARY}; border: 1px solid {T.BORDER};"
        f" border-radius: 12px; padding: 5px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        f"QPushButton:hover {{ border-color: {T.PRIMARY}; background: #ffffff; }}"
    )
    return button


def rebuild_root_cards(owner) -> None:
    owner._clear_dynamic_layout(owner._roots_layout)
    roots = [
        root
        for root in owner._state.approved_roots
        if owner._matches_query(
            str(root.get("search_text", "") or ""),
            str(root.get("label", "") or ""),
            str(root.get("detail", "") or ""),
        )
    ]
    if not roots:
        owner._roots_layout.addWidget(
            _body(
                "No approved roots match this search yet." if owner._search_query else "No approved roots yet. Add one folder first so Library has a safe place to browse and reuse files from.",
                color=T.DIM,
            )
        )
        return
    for root in roots:
        root_path = str(root.get("root_path", "") or "").strip()
        is_selected = root_path == owner._selected_root_path
        card = QFrame()
        card.setStyleSheet(
            (
                "QFrame { background-color: rgba(255,255,255,0.80); border: 1px solid rgba(70,98,199,0.34); border-radius: 18px; }"
                if is_selected
                else "QFrame { background-color: rgba(255,255,255,0.64); border: 1px solid rgba(214,197,174,0.44); border-radius: 18px; }"
            )
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)
        header = QHBoxLayout()
        header.setSpacing(8)
        if is_selected:
            header.addWidget(_mono("ACTIVE ROOT", T.ACCENT_TEAL, T.FS_TINY, True))
        header.addWidget(_mono(str(root.get("label", "") or "Approved root"), T.ACCENT_ORANGE, T.FS_TINY, True))
        header.addStretch()
        browse_btn = _action_button("BROWSE")
        browse_btn.clicked.connect(lambda _=False, path=root_path: owner._browse_root(path))
        header.addWidget(browse_btn)
        layout.addLayout(header)
        source_line = str(root.get("source_line", "") or "").strip()
        if source_line:
            layout.addWidget(_mono(source_line.upper(), T.ACCENT_TEAL, T.FS_TINY, True))
        layout.addWidget(_body(str(root.get("detail", "") or "")))
        if is_selected:
            layout.addWidget(_body("This is the current folder Guppy will browse for the file lane below.", color=T.ACCENT_TEAL))
        owner._roots_layout.addWidget(card)


def _rebuild_context_cards(owner, *, cards: list[dict[str, str]], target_layout, empty_text: str, action_help: str) -> None:
    owner._clear_dynamic_layout(target_layout)
    if not cards:
        target_layout.addWidget(_body(empty_text, color=T.DIM))
        return
    for card_state in cards:
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background-color: rgba(255,255,255,0.72); border: 1px solid rgba(214,197,174,0.46); border-radius: 20px; }"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(_mono(str(card_state.get("kind", "file") or "file").upper(), T.ACCENT_ORANGE, T.FS_TINY, True))
        top.addStretch()
        action = _action_button(str(card_state.get("action_label", "USE IN CHAT") or "USE IN CHAT"))
        title = str(card_state.get("title", "") or "").strip()
        detail = str(card_state.get("detail", "") or "").strip()
        item_path = str(card_state.get("item_path", "") or "").strip()
        context_ref = str(card_state.get("context_ref", "") or "").strip() or item_path
        prompt = str(card_state.get("prompt", "") or "").strip()
        kind = str(card_state.get("kind", "file") or "file").strip()
        action.clicked.connect(
            lambda _=False, t=title, p=context_ref, k=kind, prompt_text=prompt: owner.context_requested.emit(t, p, k, prompt_text)
        )
        top.addWidget(action)
        owner._add_media_action(top, card_state)
        layout.addLayout(top)
        title_lbl = QLabel(title)
        title_lbl.setWordWrap(True)
        title_lbl.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_HEAD}'; font-size: {T.FS_LABEL}pt; font-weight: 700;"
        )
        layout.addWidget(title_lbl)
        source_line = str(card_state.get("source_line", "") or "").strip()
        if source_line:
            layout.addWidget(_mono(source_line.upper(), T.ACCENT_TEAL, T.FS_TINY, True))
        layout.addWidget(_body(detail, color=T.DIM))
        layout.addWidget(_body(action_help, color=T.ACCENT_TEAL))
        target_layout.addWidget(card)


def rebuild_browse_cards(owner) -> None:
    root_name = owner._state.selected_root_label or "Approved root"
    owner._selected_root_status.setText(f"CURRENT ROOT · {root_name.upper()}")
    owner._selected_root_status.setVisible(bool(owner._selected_root_path or owner._state.root_file_cards))
    owner._browse_hint.setText(owner._state.selected_root_hint)
    cards = [
        card
        for card in owner._state.root_file_cards
        if owner._matches_card_query(
            card,
            str(card.get("title", "") or ""),
            str(card.get("detail", "") or ""),
            str(card.get("kind", "") or ""),
        )
    ]
    _rebuild_context_cards(
        owner,
        cards=cards,
        target_layout=owner._browse_layout,
        empty_text="No browsable files match this search for the selected root." if owner._search_query else "No browsable files yet for the current root. Pick a different approved root or add files here, then use USE IN CHAT to send one to Home.",
        action_help="USE IN CHAT sends this to Home as the source context for your next reply.",
    )


def rebuild_recent_cards(owner) -> None:
    cards = [
        card
        for card in owner._state.recent_cards
        if owner._matches_card_query(
            card,
            str(card.get("title", "") or ""),
            str(card.get("detail", "") or ""),
            str(card.get("kind", "") or ""),
        )
    ]
    _rebuild_context_cards(
        owner,
        cards=cards,
        target_layout=owner._recent_layout,
        empty_text="No recent Library items match this search." if owner._search_query else "Recent files, study notes, and coding artifacts from approved roots will show up here after you browse, save, or reuse something from Library.",
        action_help="USE IN CHAT keeps this available on Home as source context for the next reply.",
    )


def rebuild_saved_cards(owner) -> None:
    owner._clear_dynamic_layout(owner._saved_layout)
    cards = [
        card
        for card in owner._state.saved_item_cards
        if owner._matches_card_query(
            card,
            str(card.get("title", "") or ""),
            str(card.get("detail", "") or ""),
            str(card.get("kind", "") or ""),
            str(card.get("summary", "") or ""),
        )
    ]
    if not cards:
        owner._saved_layout.addWidget(
            _body(
                "No pinned notes or artifacts match this search." if owner._search_query else "Pinned notes and saved artifacts stay here until you edit them, send them to Home with USE IN CHAT, or remove them.",
                color=T.DIM,
            )
        )
        return
    for card_state in cards:
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background-color: rgba(255,255,255,0.72); border: 1px solid rgba(214,197,174,0.46); border-radius: 20px; }"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(_mono(str(card_state.get("kind", "note") or "note").upper(), T.SECONDARY, T.FS_TINY, True))
        top.addStretch()
        use_btn = _action_button("USE IN CHAT")
        edit_btn = _action_button("EDIT")
        delete_btn = _action_button("DELETE")
        item_id = int(str(card_state.get("id", "0") or "0"))
        title = str(card_state.get("full_title", card_state.get("title", "")) or "").strip()
        detail = str(card_state.get("detail", "") or "").strip()
        item_path = str(card_state.get("item_path", "") or "").strip()
        context_ref = str(card_state.get("context_ref", "") or "").strip() or item_path
        summary = str(card_state.get("summary", "") or "").strip()
        prompt = str(card_state.get("prompt", "") or "").strip()
        kind = str(card_state.get("kind", "note") or "note").strip()
        use_btn.clicked.connect(
            lambda _=False, t=title, p=context_ref, k=kind, prompt_text=prompt: owner.context_requested.emit(t, p, k, prompt_text)
        )
        if kind == "note":
            edit_btn.clicked.connect(lambda _=False, i=item_id, t=title, s=summary: owner._begin_note_edit(i, t, s))
        else:
            edit_btn.clicked.connect(lambda _=False, i=item_id, t=title, p=item_path: owner._begin_artifact_edit(i, t, p))
        delete_btn.clicked.connect(
            lambda _=False, i=item_id, t=title: owner.library_item_delete_requested.emit(i, t)
        )
        top.addWidget(use_btn)
        owner._add_media_action(top, card_state)
        top.addWidget(edit_btn)
        top.addWidget(delete_btn)
        layout.addLayout(top)
        layout.addWidget(_body(title, color=T.INK, size=T.FS_LABEL))
        source_line = str(card_state.get("source_line", "") or "").strip()
        date_label = str(card_state.get("date_label", "") or "").strip()
        meta_line = " · ".join(part for part in (source_line.upper(), date_label) if part)
        if meta_line:
            layout.addWidget(_mono(meta_line, T.ACCENT_TEAL, T.FS_TINY, True))
        layout.addWidget(_body(detail, color=T.DIM))
        layout.addWidget(_body("USE IN CHAT makes this note or artifact available on Home without leaving the current session.", color=T.TERTIARY))
        owner._saved_layout.addWidget(card)
