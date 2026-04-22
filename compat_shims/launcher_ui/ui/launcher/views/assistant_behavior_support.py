from __future__ import annotations

from PySide6.QtCore import Qt

from src.guppy.launcher_application.home_presenter import build_home_workspace_state

from .assistant_active_context import clear_active_context_row, populate_active_context_row
from .assistant_context import (
    build_composer_guidance as context_build_composer_guidance,
    build_grounding_cue as context_build_grounding_cue,
    format_active_context_summary as context_format_active_context_summary,
    normalize_context_items as context_normalize_context_items,
)
from .. import tokens as T


def set_status(view, text: str) -> None:
    status = (text or "Ready").strip().upper()
    view._status_strip.setText(status)
    color = T.PRIMARY
    if "ERROR" in status:
        color = T.ERROR
    elif "READY" in status:
        color = T.GREEN
    view._status_strip.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 2px;"
    )


def set_active_instance(
    view,
    instance: str,
    *,
    workspace_type: str = "user_instance",
    description: str = "",
    mode: str = "auto",
    persona: str = "guppy",
    voice: str = "default",
    last_message: str = "",
    continuity_snapshot: dict[str, object] | None = None,
) -> None:
    name = (instance or "guppy-primary").strip() or "guppy-primary"
    if name != view._workspace_name:
        view.set_active_context_items([])
        view.clear_latest_saved_output()
    state = build_home_workspace_state(
        name,
        workspace_type=workspace_type,
        description=description,
        mode=mode,
        persona=persona,
        voice=voice,
        last_message=last_message,
        continuity_snapshot=continuity_snapshot,
    )
    view._workspace_name = name
    view._workspace_type = (workspace_type or "user_instance").strip().lower() or "user_instance"
    view._workspace_role = state.role_label
    view._workspace_purpose = state.purpose
    view.set_chat_context(mode, persona)
    view._refresh_empty_state_copy()
    view._refresh_starter_buttons()
    view._base_starter_summary = state.starter_summary
    view._base_input_placeholder = state.input_placeholder
    view._refresh_composer_guidance()
    view._instance_chip.setText(f"WORKSPACE / {name.upper()}")
    view._identity_workspace_chip.setText(f"WORKSPACE / {name.upper()}")
    view._identity_note.setText(state.entry_hint)
    view._workspace_summary.setText(state.workspace_summary)
    view._workspace_summary.setVisible(view._home_operator_details_enabled)
    hero_subtitle_for_workspace = getattr(view, "_hero_subtitle_for_workspace", None)
    if callable(hero_subtitle_for_workspace):
        subtitle = str(hero_subtitle_for_workspace(view._workspace_type) or "").strip()
        resume_hint = str(state.resume_hint or "").strip()
        view._hero_subtitle.setText(f"{subtitle} {resume_hint}".strip())
    view._entry_hint.setText(state.entry_hint)
    view._refresh_resource_context()
    view._sync_context_bar_visibility()


def set_request_in_flight(view, in_flight: bool) -> None:
    view._request_in_flight_ui = in_flight
    view._input.setEnabled(not in_flight)
    view._send_btn.setEnabled(not in_flight)
    view._cancel_btn.setEnabled(in_flight)
    view._mic_btn.setEnabled(view._mic_capture_active or not in_flight)


def set_mic_capture_state(view, listening: bool) -> None:
    view._mic_capture_active = listening
    if listening:
        view._mic_btn.setText("\u25c9")
        view._mic_btn.setToolTip("Listening now. Click to stop capture.")
        view._status_strip.setText("LISTENING")
        view._mic_btn.setEnabled(True)
        return
    view._mic_btn.setText("\u25cf")
    view._mic_btn.setToolTip("Push to talk. Click again while listening to stop capture.")
    view._mic_btn.setEnabled(not view._request_in_flight_ui)


def set_session_id(view, session_id: str) -> None:
    sid = (session_id or "").strip()
    suffix = sid[-8:] if sid else "--"
    view._session_strip.setText(f"SESSION: {suffix}")


def restore_history(view, history: list[dict[str, str]]) -> None:
    view.clear_transcript()
    for item in history:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "") or "").strip()
        if not content:
            continue
        if role == "user":
            view.add_user_message(content)
        elif role == "assistant":
            view.add_assistant_message(content)
    view._refresh_resource_context()
    view._refresh_empty_state()


def set_chat_context(view, mode: str, persona: str) -> None:
    mode_key = (mode or "").strip().lower()
    persona_key = (persona or "").strip().lower()
    for idx in range(view._cb_mode.count()):
        if view._cb_mode.itemText(idx).strip().lower() == mode_key:
            view._cb_mode.setCurrentIndex(idx)
            break
    for idx in range(view._cb_persona.count()):
        option_key = str(view._cb_persona.itemData(idx) or view._cb_persona.itemText(idx)).strip().lower()
        if option_key == persona_key:
            view._cb_persona.setCurrentIndex(idx)
            break
    view._refresh_resource_context()


def set_resource_context(view, *, files: str, study: str, coding: str) -> None:
    view._files_context_lbl.setText(files)
    view._study_context_lbl.setText(study)
    view._coding_context_lbl.setText(coding)


def set_latest_saved_output(
    view,
    *,
    title: str,
    summary: str,
    source_label: str = "Saved reply artifact",
) -> None:
    title_text = str(title or "").strip()
    summary_text = str(summary or "").strip()
    if not title_text:
        clear_latest_saved_output(view)
        return
    view._latest_saved_output = {
        "title": title_text,
        "summary": summary_text,
        "source_label": str(source_label or "Saved reply artifact").strip() or "Saved reply artifact",
    }
    view._latest_output_title.setText(str(view._latest_saved_output["source_label"]).upper())
    view._latest_output_summary.setText(f"{title_text}. {summary_text}" if summary_text else title_text)
    view._latest_output_host.setVisible(True)
    view._update_workspace_details_visibility()


def clear_latest_saved_output(view) -> None:
    view._latest_saved_output = {}
    view._latest_output_summary.setText("")
    view._latest_output_host.setVisible(False)
    view._update_workspace_details_visibility()


def emit_latest_saved_output_attach(view) -> None:
    if not view._latest_saved_output:
        return
    view.latest_saved_output_attach_requested.emit(
        str(view._latest_saved_output.get("title", "")),
        str(view._latest_saved_output.get("summary", "")),
    )


def emit_latest_saved_output_library(view) -> None:
    if not view._latest_saved_output:
        return
    view.latest_saved_output_library_requested.emit(str(view._latest_saved_output.get("title", "")))


def set_active_context_items(view, items: list[dict[str, str]]) -> None:
    view._active_context_items = context_normalize_context_items(items)
    clear_active_context_row(view._active_context_row)
    if not view._active_context_items:
        view._last_context_notice = ""
        view._focused_context_title = ""
        view._previewed_context_title = ""
        view._swap_source_target_title = ""
        view._active_context_refresh_btn.setVisible(False)
        view._active_context_pin_default_btn.setVisible(False)
        view._active_context_swap_btn.setVisible(False)
        view._active_context_host.setVisible(False)
        refresh_grounding_cue(view)
        view._refresh_starter_buttons()
        refresh_composer_guidance(view)
        view._refresh_empty_state_guidance()
        view._update_workspace_details_visibility()
        return
    primary_title = view._active_context_items[0]["title"]
    previous_focus = view._focused_context_title
    view._focused_context_title = primary_title
    primary_origin = str(view._active_context_items[0].get("origin", "") or "").strip().lower()
    saved_origins = {"assistant_reply", "assistant_reply_artifact"}
    view._swap_source_target_title = ""
    if primary_origin in saved_origins:
        for item in view._active_context_items[1:]:
            item_origin = str(item.get("origin", "") or "").strip().lower()
            if item_origin not in saved_origins and str(item.get("title", "") or "").strip():
                view._swap_source_target_title = str(item.get("title", "") or "").strip()
                break
    view._active_context_refresh_btn.setVisible(bool(primary_origin in saved_origins and view._latest_assistant_reply_text))
    view._active_context_pin_default_btn.setVisible(bool(primary_title))
    pinned_default = primary_title == view._default_context_source_title
    view._active_context_pin_default_btn.setText("DEFAULT PINNED" if pinned_default else "PIN PRIMARY")
    view._active_context_pin_default_btn.setEnabled(not pinned_default)
    view._active_context_pin_default_btn.setToolTip(
        "This source is already the workspace default"
        if pinned_default
        else "Pin the primary source as this workspace default"
    )
    view._active_context_swap_btn.setVisible(bool(view._swap_source_target_title))
    view._active_context_swap_btn.setText("MAKE PRIMARY SOURCE")
    available_titles = {item["title"] for item in view._active_context_items}
    if previous_focus != primary_title or view._previewed_context_title not in available_titles:
        view._previewed_context_title = primary_title
    view._active_context_summary.setText(context_format_active_context_summary(view._active_context_items))
    populate_active_context_row(
        view._active_context_row,
        items=view._active_context_items,
        primary_title=primary_title,
        default_title=view._default_context_source_title,
        previewed_title=view._previewed_context_title,
        on_toggle_preview=view._toggle_active_context_preview,
        on_focus=view.active_context_focus_requested.emit,
        on_open_library=view.active_context_library_requested.emit,
        on_remove=view.active_context_remove_requested.emit,
    )
    view._active_context_host.setVisible(True)
    refresh_grounding_cue(view)
    view._refresh_starter_buttons()
    refresh_composer_guidance(view)
    view._refresh_empty_state_guidance()
    view._update_workspace_details_visibility()


def toggle_active_context_preview(view, title: str) -> None:
    title_text = str(title or "").strip()
    if not title_text:
        return
    view._previewed_context_title = "" if view._previewed_context_title == title_text else title_text
    set_active_context_items(view, view._active_context_items)


def emit_active_context_refresh_requested(view) -> None:
    if not view._active_context_items:
        return
    latest_reply = str(view._latest_assistant_reply_text or "").strip()
    if not latest_reply:
        return
    origin = str(view._active_context_items[0].get("origin", "") or "").strip().lower()
    view.active_context_refresh_requested.emit(latest_reply, origin == "assistant_reply_artifact")


def emit_active_context_swap_requested(view) -> None:
    title = str(view._swap_source_target_title or "").strip()
    if title:
        view.active_context_focus_requested.emit(title)


def emit_active_context_default_requested(view) -> None:
    if not view._active_context_items:
        return
    primary_title = str(view._active_context_items[0].get("title", "") or "").strip()
    if primary_title:
        view.active_context_default_requested.emit(primary_title)


def set_default_context_source(view, title: str) -> None:
    view._default_context_source_title = str(title or "").strip()
    if view._active_context_items:
        set_active_context_items(view, view._active_context_items)


def note_active_context_submission(view, text: str) -> None:
    notice = str(text or "").strip()
    if not notice:
        return
    view._last_context_notice = notice
    if view._active_context_items:
        view._active_context_summary.setText(
            context_format_active_context_summary(view._active_context_items, used_for_latest_reply=True)
        )
        view._active_context_host.setVisible(True)
        view._update_workspace_details_visibility()
    refresh_grounding_cue(view)
    refresh_composer_guidance(view)
    view.add_system_message(notice)


def refresh_grounding_cue(view) -> None:
    if not view._active_context_items:
        view._grounding_chip.clear()
        view._grounding_chip.setToolTip("")
        view._grounding_chip.setVisible(False)
        return
    label, tooltip = context_build_grounding_cue(view._active_context_items[0])
    view._grounding_chip.setText(label)
    view._grounding_chip.setToolTip(tooltip)
    view._grounding_chip.setVisible(True)


def refresh_composer_guidance(view) -> None:
    placeholder, starter_summary = context_build_composer_guidance(
        view._base_input_placeholder,
        view._base_starter_summary,
        view._active_context_items,
    )
    view._input.setPlaceholderText(placeholder)
    view._starter_summary.setText(starter_summary)
    update_visibility = getattr(view, "_update_starter_visibility", None)
    if callable(update_visibility):
        update_visibility()


def set_first_run_status(
    view,
    *,
    visible: bool,
    summary: str = "",
    detail: str = "",
    install_status: str = "pending",
    model_status: str = "pending",
    request_status: str = "pending",
) -> None:
    view._first_run_banner_visible = bool(visible)
    view._first_run_frame.set_status(
        visible=visible,
        summary=summary,
        detail=detail,
        install_status=install_status,
        model_status=model_status,
        request_status=request_status,
    )
    apply_density_mode(view, view.width())


def apply_density_mode(view, width: int) -> None:
    width = max(int(width or 0), 0)
    compact = width < 1120
    tight = width < 920
    ultra = width < 780
    view._identity_frame.setVisible(False)
    view._identity_mode_chip.setVisible(not ultra)
    view._instance_chip.setVisible(not tight)
    view._first_run_frame.apply_density_mode(width)
    update_visibility = getattr(view, "_update_starter_visibility", None)
    if callable(update_visibility):
        update_visibility()
    view._workspace_details_btn.setText(
        "OPEN"
        if compact and not view._workspace_details_expanded
        else ("HIDE DETAILS" if view._workspace_details_expanded else "DETAILS")
    )
    view._identity_details_btn.setText(
        "OPEN"
        if compact and not view._workspace_details_expanded
        else ("HIDE DETAILS" if view._workspace_details_expanded else "DETAILS")
    )
