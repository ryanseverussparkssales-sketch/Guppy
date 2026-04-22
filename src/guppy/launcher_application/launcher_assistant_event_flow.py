from __future__ import annotations

from typing import Any, Callable

from .launcher_command_policy import humanize_chat_error


def drain_assistant_events(owner: object, *, timer_single_shot: Callable) -> None:
    """Drain queued assistant and voice events for one poll tick."""
    from queue import Empty

    max_events = getattr(owner, "_MAX_ASSISTANT_EVENTS_PER_TICK", 8)
    event_queue = getattr(owner, "_assistant_events", None)
    if event_queue is None:
        return
    assistant_view = getattr(owner, "_assistant_view", None)
    status_panel = getattr(owner, "_status_panel", None)
    processed = 0
    while processed < max_events:
        try:
            kind, payload, seq = event_queue.get_nowait()
        except Empty:
            break
        if kind == "voice_input":
            owner._mic_capture_active = False
            if assistant_view is not None:
                assistant_view.set_mic_capture_state(False)
            text = str(payload or "").strip()
            if text:
                set_act = getattr(owner, "_set_daily_activity", None)
                if callable(set_act):
                    set_act(f"Voice captured: {text[:72]}")
                if status_panel is not None:
                    status_panel.append_syslog("voice capture ready")
                on_cmd = getattr(owner, "_on_assistant_command", None)
                if callable(on_cmd):
                    on_cmd(text)
            elif assistant_view is not None:
                assistant_view.set_status("Ready")
            processed += 1
            continue
        if kind == "voice_error":
            owner._mic_capture_active = False
            if assistant_view is not None:
                assistant_view.set_mic_capture_state(False)
                assistant_view.set_status("Ready")
                assistant_view.add_system_message(str(payload or "Voice capture failed."))
            if status_panel is not None:
                status_panel.append_syslog(f"voice capture failed: {str(payload or '')[:120]}")
            processed += 1
            continue
        canceled_seqs = getattr(owner, "_canceled_request_seqs", set())
        if seq in canceled_seqs:
            canceled_seqs.discard(seq)
            processed += 1
            continue
        if seq != getattr(owner, "_active_request_seq", None):
            processed += 1
            continue
        if kind == "assistant":
            if assistant_view is not None:
                assistant_view.set_status("Ready")
            finish = getattr(owner, "_finish_request_ui", None)
            if callable(finish):
                finish()
            if assistant_view is not None:
                assistant_view.add_assistant_message(payload)
            on_logs = getattr(owner, "_on_instance_logs_requested", None)
            if callable(on_logs):
                on_logs(getattr(owner, "_active_instance_name", ""), quiet=True)
        elif kind == "error":
            if assistant_view is not None:
                assistant_view.set_status("Error")
            finish = getattr(owner, "_finish_request_ui", None)
            if callable(finish):
                finish()
            if assistant_view is not None:
                assistant_view.add_assistant_message(humanize_chat_error(payload))
                timer_single_shot(2500, lambda: assistant_view.set_status("Ready"))
            if status_panel is not None:
                status_panel.append_syslog(f"chat error: {payload[:120]}")
            on_logs = getattr(owner, "_on_instance_logs_requested", None)
            if callable(on_logs):
                on_logs(getattr(owner, "_active_instance_name", ""), quiet=True)
        processed += 1


def rotate_chat_session(
    owner: Any,
    reason: str,
    *,
    mode: str = "",
    persona: str = "",
    instance: str = "",
    clear_live_history: bool = False,
) -> None:
    import time as _time

    active_instance = getattr(owner, "_active_instance_name", "") or ""
    inst = (instance or active_instance or "guppy-primary").strip()
    suffix = f"-{inst}"
    if mode or persona:
        suffix += f"-{mode}-{persona}"
    session_id = f"launcher-{int(_time.time())}{suffix}"
    owner._chat_session_id = session_id
    assistant_view = getattr(owner, "_assistant_view", None)
    if assistant_view is not None:
        assistant_view.set_session_id(session_id)
        if clear_live_history:
            assistant_view.reset_live_history()
    topbar = getattr(owner, "_topbar", None)
    if topbar is not None:
        topbar.set_session(f"{inst} {session_id[-8:]}")
    owner._log_launcher_event(
        "chat_session_rotated",
        reason=reason,
        session_id=session_id,
        instance=inst,
        mode=mode,
        persona=persona,
    )


def apply_chat_context(owner: Any, mode: str, persona: str) -> None:
    active_instance = getattr(owner, "_active_instance_name", "") or ""
    rotate_chat_session(
        owner,
        "context_changed",
        mode=mode,
        persona=persona,
        instance=active_instance,
        clear_live_history=True,
    )
    assistant_view = getattr(owner, "_assistant_view", None)
    if assistant_view is not None:
        assistant_view.add_system_message(
            f"New chat session started for {persona.upper()} / {mode.upper()}."
        )
    status_panel = getattr(owner, "_status_panel", None)
    if status_panel is not None:
        status_panel.append_syslog(f"chat session rotated: {persona}/{mode}")
    update_preview = getattr(owner, "_update_route_preview", None)
    if callable(update_preview):
        update_preview(getattr(owner, "_last_command", ""))


def on_chat_context_changed(owner: Any, mode: str, persona: str) -> None:
    refresh_personalization = getattr(owner, "_refresh_personalization_state", None)
    if callable(refresh_personalization):
        refresh_personalization(preferred_persona=persona)
    update_preview = getattr(owner, "_update_route_preview", None)
    if callable(update_preview):
        update_preview(getattr(owner, "_last_command", ""))
    if getattr(owner, "_request_in_flight", False):
        owner._pending_chat_context = (mode, persona)
        status_panel = getattr(owner, "_status_panel", None)
        if status_panel is not None:
            status_panel.append_syslog(
                f"chat context queued until current request completes: {persona}/{mode}"
            )
        return
    apply_chat_context(owner, mode, persona)


def finish_request_ui(owner: Any) -> None:
    assistant_view = getattr(owner, "_assistant_view", None)
    if assistant_view is not None:
        assistant_view.set_request_in_flight(False)
    owner._request_in_flight = False
    pending = getattr(owner, "_pending_chat_context", None)
    if pending:
        mode, persona = pending
        owner._pending_chat_context = None
        apply_chat_context(owner, mode, persona)


def on_cancel_assistant_request(owner: Any) -> None:
    if not getattr(owner, "_request_in_flight", False):
        return
    seq = getattr(owner, "_active_request_seq", None)
    canceled_seqs = getattr(owner, "_canceled_request_seqs", None)
    if canceled_seqs is not None and seq is not None:
        canceled_seqs.add(seq)
    finish_request_ui(owner)
    assistant_view = getattr(owner, "_assistant_view", None)
    if assistant_view is not None:
        assistant_view.set_status("Ready")
        assistant_view.add_system_message("Request canceled.")
    status_panel = getattr(owner, "_status_panel", None)
    if status_panel is not None:
        status_panel.append_syslog(f"request canceled: seq={seq}")
    owner._log_launcher_event("command_canceled", seq=seq)