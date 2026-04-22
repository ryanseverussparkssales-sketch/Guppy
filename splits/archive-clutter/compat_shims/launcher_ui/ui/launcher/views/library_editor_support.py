from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog

from src.guppy.launcher_application.library_presenter import validate_library_root

from .. import tokens as T


def apply_density_mode(view, width: int) -> None:
    compact = width <= 1120
    tight = width <= 920
    view._search.setPlaceholderText("Search Library" if tight else "Search files, notes, and saved workspace context")
    view._root_repo_btn.setText("REPO" if tight else "USE REPO")
    view._root_browse_btn.setText("FOLDER" if tight else "PICK FOLDER")
    view._root_save_btn.setText("SAVE" if compact else "SAVE ROOT")
    view._note_save_btn.setText(
        "UPDATE" if view._editing_note_id > 0 and tight else
        "UPDATE NOTE" if view._editing_note_id > 0 else
        "SAVE NOTE" if compact else
        "PIN NOTE"
    )
    view._note_cancel_btn.setText("CANCEL" if compact else "CANCEL EDIT")
    view._artifact_browse_btn.setText("FILE" if compact else "PICK FILE")
    view._artifact_save_btn.setText(
        "UPDATE" if view._editing_artifact_id > 0 and compact else
        "UPDATE ARTIFACT" if view._editing_artifact_id > 0 else
        "SAVE" if compact else
        "SAVE ARTIFACT"
    )
    view._artifact_cancel_btn.setText("CANCEL" if compact else "CANCEL EDIT")
    view._roots_hint.setVisible(not tight)
    view._recent_hint.setVisible(not tight)
    view._saved_hint.setVisible(not tight)


def fill_repo_root(view) -> None:
    for root in view._state.approved_roots:
        if str(root.get("label", "")).strip().lower() == "current guppy repo":
            view._root_label.setText(str(root.get("label", "") or "").strip())
            view._root_path.setText(str(root.get("root_path", "") or "").strip())
            set_root_feedback(view, "", is_error=False)
            return


def choose_root_path(view) -> None:
    current = view._root_path.text().strip() or view._selected_root_path
    chosen = QFileDialog.getExistingDirectory(view, "Select approved root", current)
    chosen = str(chosen or "").strip()
    if not chosen:
        return
    view._root_path.setText(chosen)
    if not view._root_label.text().strip():
        normalized = chosen.replace("\\", "/").rstrip("/")
        default_label = normalized.rsplit("/", 1)[-1].strip() or "Approved root"
        view._root_label.setText(default_label)
    set_root_feedback(view, "", is_error=False)


def choose_artifact_path(view) -> None:
    current = view._artifact_path.text().strip() or view._root_path.text().strip()
    chosen, _ = QFileDialog.getOpenFileName(view, "Select artifact file", current)
    chosen = str(chosen or "").strip()
    if chosen:
        view._artifact_path.setText(chosen)


def begin_note_edit(view, item_id: int, title: str, summary: str) -> None:
    view._editing_note_id = max(0, int(item_id or 0))
    view._note_title.setText(title)
    view._note_body.setPlainText(summary)
    refresh_note_editor_state(view)
    if view.isVisible():
        apply_density_mode(view, view.width())
    view._note_body.setFocus(Qt.FocusReason.OtherFocusReason)


def begin_artifact_edit(view, item_id: int, title: str, item_path: str) -> None:
    view._editing_artifact_id = max(0, int(item_id or 0))
    view._artifact_title.setText(title)
    view._artifact_path.setText(item_path)
    view._artifact_save_btn.setText("UPDATE ARTIFACT")
    view._artifact_cancel_btn.setVisible(True)
    if view.isVisible():
        apply_density_mode(view, view.width())


def reset_note_editor(view) -> None:
    view._editing_note_id = 0
    view._note_title.clear()
    view._note_body.clear()
    refresh_note_editor_state(view)
    if view.isVisible():
        apply_density_mode(view, view.width())


def reset_artifact_editor(view) -> None:
    view._editing_artifact_id = 0
    view._artifact_title.clear()
    view._artifact_path.clear()
    view._artifact_save_btn.setText("SAVE ARTIFACT")
    view._artifact_cancel_btn.setVisible(False)
    if view.isVisible():
        apply_density_mode(view, view.width())


def emit_root_request(view) -> None:
    raw_path = view._root_path.text().strip()
    label = view._root_label.text().strip() or "Approved root"
    ok, msg = validate_library_root(raw_path)
    if not ok:
        set_root_feedback(view, msg or "Invalid path.", is_error=True)
        return
    resolved = str(Path(raw_path).expanduser().resolve())
    view.approved_root_requested.emit(resolved, label)
    view._root_path.clear()
    view._root_label.clear()
    set_root_feedback(view, "Root save requested. Confirmation will appear in status.", is_error=False)


def set_root_feedback(view, message: str, *, is_error: bool) -> None:
    text = str(message or "").strip()
    if not text:
        view._root_feedback_lbl.clear()
        view._root_feedback_lbl.setVisible(False)
        return
    color = T.ERROR if is_error else T.GREEN
    view._root_feedback_lbl.setText(text)
    view._root_feedback_lbl.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_BODY}'; font-size: {T.FS_TINY}pt;"
    )
    view._root_feedback_lbl.setVisible(True)


def sync_root_picker(view) -> None:
    view._root_picker.blockSignals(True)
    try:
        view._root_picker.clear()
        for root in view._state.approved_roots:
            label = str(root.get("label", "") or "Approved root").strip() or "Approved root"
            detail = str(root.get("detail", "") or "").strip()
            text = label if not detail else f"{label} - {detail}"
            view._root_picker.addItem(text, str(root.get("root_path", "") or "").strip())
        if view._root_picker.count() > 0:
            selected_index = next(
                (
                    index
                    for index, root in enumerate(view._state.approved_roots)
                    if str(root.get("root_path", "") or "").strip() == view._selected_root_path
                ),
                0,
            )
            view._root_picker.setCurrentIndex(max(0, min(selected_index, view._root_picker.count() - 1)))
    finally:
        view._root_picker.blockSignals(False)
    view._root_picker.setVisible(view._root_picker.count() > 0)


def refresh_note_editor_state(view) -> None:
    editing = view._editing_note_id > 0
    title = view._note_title.text().strip()
    body_text = view._note_body.toPlainText()
    stripped_body = body_text.strip()
    line_count = len([line for line in body_text.splitlines() if line.strip()])
    view._note_save_btn.setText("UPDATE NOTE" if editing else "PIN NOTE")
    view._note_cancel_btn.setVisible(editing)
    view._note_save_btn.setEnabled(bool(title))
    if editing:
        hint = f"Editing pinned note: {title or 'untitled note'}."
        if stripped_body:
            hint += f" Body ready: {len(stripped_body)} chars across {max(1, line_count)} line(s)."
        else:
            hint += " Add or revise the body, then update it in place."
    elif stripped_body:
        hint = f"New pinned note draft: {len(stripped_body)} chars across {max(1, line_count)} line(s)."
    else:
        hint = "Multiline notes stay in Library and can be reused in Home with USE IN CHAT."
    view._note_editor_hint.setText(hint)

