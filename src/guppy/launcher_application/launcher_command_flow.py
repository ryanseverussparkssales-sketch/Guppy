from __future__ import annotations

import uuid
from typing import Callable

from .launcher_command_policy import (
    assistant_model_id,
    build_shell_model_loadout_summary,
    chat_timeout_for_request,
    derive_topbar_model_context,
    required_local_model_for_mode,
)
from .launcher_assistant_event_flow import (
    drain_assistant_events as _drain_assistant_events,
    finish_request_ui as _finish_request_ui,
    on_cancel_assistant_request as _on_cancel_assistant_request,
)
from .launcher_chat_session import (
    apply_chat_context,
    on_chat_context_changed,
    rotate_chat_session,
)


def handle_assistant_command(
    launcher: object,
    command: str,
    *,
    instance_logger_available: bool,
    instance_log_appender: Callable[[str, dict[str, object]], None],
    library_chat_submission_builder: Callable[[str, list[dict[str, str]], list[dict[str, str]]], object],
    thread_factory: Callable[..., object],
    uuid_factory: Callable[[], object] = uuid.uuid4,
) -> None:
    cmd = (command or "").strip()
    if not cmd:
        return
    assistant_view = getattr(launcher, "_assistant_view", None)
    if assistant_view is None:
        return
    if getattr(launcher, "_request_in_flight", False):
        add_assistant = getattr(assistant_view, "add_assistant_message", None)
        if callable(add_assistant):
            add_assistant("A request is already in progress. Please wait for it to finish.")
        else:
            assistant_view.add_system_message("A request is already in progress. Please wait for it to finish.")
        return

    selected_mode = assistant_view.selected_mode()
    mode_ok, mode_err = launcher._validate_mode_ready(selected_mode)
    if not mode_ok:
        assistant_view.set_status("Ready")
        add_assistant = getattr(assistant_view, "add_assistant_message", None)
        if callable(add_assistant):
            add_assistant(mode_err)
        else:
            assistant_view.add_system_message(mode_err)
        launcher._status_panel.append_syslog(f"chat blocked: {mode_err}")
        return

    launcher._last_command = cmd
    instance_name = getattr(launcher, "_active_instance_name", "guppy-primary") or "guppy-primary"
    chat_context_getter = getattr(assistant_view, "chat_context", None)
    selected_persona = "guppy"
    if callable(chat_context_getter):
        try:
            _mode, selected_persona = chat_context_getter()
        except Exception:
            selected_persona = "guppy"
    route_updater = getattr(launcher, "_update_route_preview", None)
    if callable(route_updater):
        route_updater(cmd)

    launcher._active_request_seq += 1
    req_seq = launcher._active_request_seq
    launcher._request_in_flight = True
    history_getter = getattr(assistant_view, "recent_history", None)
    history = history_getter(limit=12) if callable(history_getter) else []
    active_library_items = list(getattr(launcher, "_active_library_context_items", []))
    library_submission = library_chat_submission_builder(cmd, history, active_library_items)
    request_message = library_submission.request_message
    history = library_submission.history
    idempotency_key = f"launcher-{uuid_factory().hex}"
    if library_submission.context_notice:
        note_context_submission = getattr(assistant_view, "note_active_context_submission", None)
        if callable(note_context_submission):
            note_context_submission(library_submission.context_notice)
    assistant_view.add_user_message(cmd)
    if instance_logger_available:
        instance_log_appender(
            instance_name,
            {
                "role": "user",
                "source_instance": instance_name,
                "message": cmd,
                "status": "submitted",
                "model": selected_mode,
            },
        )
    set_in_flight = getattr(assistant_view, "set_request_in_flight", None)
    if callable(set_in_flight):
        set_in_flight(True)
    assistant_view.set_status(library_submission.status_text)
    if library_submission.background_event:
        assistant_view.set_background_event(library_submission.background_event)
    activity_setter = getattr(launcher, "_set_daily_activity", None)
    if callable(activity_setter):
        activity_setter(f"Working on: {cmd[:96]}")
    launcher._status_panel.append_syslog("command queued")
    launcher._log_launcher_event("command_submitted", command=cmd, seq=req_seq, idempotency_key=idempotency_key)
    request_timeout = chat_timeout_for_request(selected_mode, cmd)
    retry_timeout = max(request_timeout + 20.0, 60.0)

    def _emit_assistant_result(text: str, *, retried_after_401: bool = False) -> None:
        if instance_logger_available:
            instance_log_appender(
                instance_name,
                {
                    "role": "assistant",
                    "source_instance": instance_name,
                    "message": text,
                    "status": "ok",
                    "model": selected_mode,
                },
            )
        launcher._assistant_events.put(("assistant", text, req_seq))
        emitter = getattr(launcher, "assistant_event_queued", None)
        if emitter is not None and hasattr(emitter, "emit"):
            emitter.emit()
        event_payload = {
            "ok": True,
            "chars": len(text),
            "seq": req_seq,
            "idempotency_key": idempotency_key,
        }
        if retried_after_401:
            event_payload["retried_after_401"] = True
        launcher._log_launcher_event("command_response", **event_payload)

    def _emit_error(err_text: str) -> None:
        launcher._assistant_events.put(("error", err_text, req_seq))
        emitter = getattr(launcher, "assistant_event_queued", None)
        if emitter is not None and hasattr(emitter, "emit"):
            emitter.emit()
        launcher._log_launcher_event(
            "command_response",
            ok=False,
            error=err_text,
            seq=req_seq,
            idempotency_key=idempotency_key,
        )

    def _worker() -> None:
        payload = {
            "message": request_message,
            "session_id": launcher._chat_session_id,
            "mode": selected_mode,
            "persona": selected_persona,
            "history": history,
            "idempotency_key": idempotency_key,
        }
        try:
            recovered_before_chat = False
            if not launcher._api_reachable(timeout=0.8):
                recovered, recovery_detail = launcher._ensure_api_reachable_for_command()
                recovered_before_chat = recovered
                launcher._log_launcher_event(
                    "command_api_recovery",
                    seq=req_seq,
                    ok=recovered,
                    detail=recovery_detail,
                    idempotency_key=idempotency_key,
                )
                if not recovered:
                    raise RuntimeError(recovery_detail or "Could not reach the local API service.")
            primary_timeout = max(request_timeout, 30.0) if recovered_before_chat else request_timeout
            try:
                resp = launcher._http_json(
                    "/chat",
                    method="POST",
                    payload=payload,
                    timeout=primary_timeout,
                    retry_auth_on_401=True,
                    auth_retry_reason="chat",
                )
            except Exception as first_exc:
                first_text = str(first_exc)
                lowered = first_text.lower()
                if "timed out" in lowered and recovered_before_chat:
                    launcher._log_launcher_event(
                        "command_recovery_warmup_timeout",
                        seq=req_seq,
                        timeout_s=primary_timeout,
                        idempotency_key=idempotency_key,
                    )
                    raise RuntimeError(
                        "The local API restarted, but the first reply is still warming up. Please retry now."
                    ) from first_exc
                if "timed out" in lowered and primary_timeout < retry_timeout:
                    launcher._log_launcher_event(
                        "command_timeout_retry",
                        seq=req_seq,
                        timeout_s=primary_timeout,
                        retry_timeout_s=retry_timeout,
                        idempotency_key=idempotency_key,
                    )
                    resp = launcher._http_json(
                        "/chat",
                        method="POST",
                        payload=payload,
                        timeout=retry_timeout,
                        retry_auth_on_401=True,
                        auth_retry_reason="chat_timeout_retry",
                    )
                elif any(token in lowered for token in ("10061", "connection refused", "actively refused")):
                    recovered, recovery_detail = launcher._ensure_api_reachable_for_command()
                    launcher._log_launcher_event(
                        "command_api_recovery",
                        seq=req_seq,
                        ok=recovered,
                        detail=recovery_detail,
                        phase="retry_after_refused",
                        idempotency_key=idempotency_key,
                    )
                    if recovered:
                        resp = launcher._http_json(
                            "/chat",
                            method="POST",
                            payload=payload,
                            timeout=retry_timeout,
                            retry_auth_on_401=True,
                            auth_retry_reason="chat_connection_retry",
                        )
                    else:
                        raise
                else:
                    raise
            text = str(resp.get("response") or "").strip()
            if not text:
                text = "No response payload received."
            _emit_assistant_result(text)
        except Exception as exc:
            err_text = str(exc)
            if launcher._is_unauthorized_error(err_text):
                auth_code = launcher._extract_error_code(err_text)
                launcher._log_launcher_event(
                    "command_auth_error",
                    seq=req_seq,
                    auth_code=auth_code,
                    error=err_text,
                    idempotency_key=idempotency_key,
                )
                launcher._refresh_api_auth_state("chat_401")
                try:
                    retry_resp = launcher._http_json(
                        "/chat",
                        method="POST",
                        payload=payload,
                        timeout=retry_timeout,
                        retry_auth_on_401=True,
                        auth_retry_reason="chat_retry",
                    )
                    retry_text = str(retry_resp.get("response") or "").strip()
                    if not retry_text:
                        retry_text = "No response payload received."
                    _emit_assistant_result(retry_text, retried_after_401=True)
                    return
                except Exception as retry_error:
                    retry_auth_code = launcher._extract_error_code(str(retry_error))
                    if retry_auth_code:
                        launcher._log_launcher_event(
                            "command_auth_error",
                            seq=req_seq,
                            auth_code=retry_auth_code,
                            phase="retry",
                            error=str(retry_error),
                            idempotency_key=idempotency_key,
                        )
                    err_text = f"{err_text}; retry failed: {retry_error}"
            _emit_error(err_text)

    thread_factory(target=_worker, daemon=True).start()


def drain_assistant_events(owner: object, *, timer_single_shot: Callable) -> None:
    _drain_assistant_events(owner, timer_single_shot=timer_single_shot)


def validate_mode_ready(owner: Any, mode: str) -> tuple[bool, str]:
    """Check whether a mode's required local model is available.

    Extracted from LauncherWindow._validate_mode_ready as part of TR54-B1 Wave 6.
    """
    model = required_local_model_for_mode(mode)
    if not model:
        return True, ""
    try:
        from guppy_core.network_utils import check_ollama
        ok, err = check_ollama(model)
        if ok:
            return True, ""
        return False, f"{mode.upper()} mode requires local model '{model}'. {err.splitlines()[0]}"
    except Exception:
        return False, f"{mode.upper()} mode requires local model '{model}', but readiness could not be verified."


def finish_request_ui(owner: Any) -> None:
    _finish_request_ui(owner)


def on_cancel_assistant_request(owner: Any) -> None:
    _on_cancel_assistant_request(owner)


def initialize_embedded_agent(owner: Any, agent_id: str) -> tuple[bool, str]:
    """Activate an embedded agent session in the assistant view.

    Extracted from LauncherWindow._initialize_embedded_agent as part of TR54-B1 Wave 8.
    """
    aid = (agent_id or "").strip().lower()
    if aid != "guppy":
        return False, f"unknown agent: {agent_id}"
    embedded_online = getattr(owner, "_embedded_online", None)
    if embedded_online is not None:
        embedded_online.add(aid)
    assistant_view = getattr(owner, "_assistant_view", None)
    if assistant_view is not None:
        assistant_view.activate_agent(aid)
        assistant_view.add_system_message(f"{aid.upper()} embedded session initialized.")
    set_act = getattr(owner, "_set_daily_activity", None)
    if callable(set_act):
        set_act(f"Embedded {aid.upper()} session initialized")
    return True, "embedded session active"


def on_agent_init_requested(owner: Any, agent_id: str) -> None:
    """Handle an agent initialisation request from the UI.

    Extracted from LauncherWindow._on_agent_init_requested as part of TR54-B1 Wave 8.
    """
    aid = (agent_id or "").strip().lower()
    if not aid:
        return
    stack = getattr(owner, "_stack", None)
    if stack is not None:
        stack.setCurrentIndex(0)
    sidebar = getattr(owner, "_sidebar", None)
    if sidebar is not None:
        sidebar.set_active(0)
    status_panel = getattr(owner, "_status_panel", None)
    if status_panel is not None:
        status_panel.append_syslog(f"init requested: {aid}")
    owner._log_launcher_event("agent_init_requested", agent=aid)
    ok, summary = initialize_embedded_agent(owner, aid)
    if status_panel is not None:
        status_panel.append_syslog(f"init {aid}: {'OK' if ok else 'ERROR'} — {summary}")
    owner._log_launcher_event("agent_init_result", agent=aid, ok=ok, summary=summary)


def on_model_selected(owner: Any, model: str, *, models_view_index: int) -> None:
    """React to a model selection change from the models hub.

    Extracted from LauncherWindow._on_model_selected as part of TR54-B1 Wave 8.
    """
    status_panel = getattr(owner, "_status_panel", None)
    if status_panel is not None:
        status_panel.append_syslog(f"active model -> {model}")
    refresh = getattr(owner, "_refresh_personalization_state", None)
    if callable(refresh):
        refresh()
    update_preview = getattr(owner, "_update_route_preview", None)
    if callable(update_preview):
        update_preview(getattr(owner, "_last_command", ""))
    stack = getattr(owner, "_stack", None)
    if stack is not None and stack.currentIndex() == models_view_index:
        sync_summary = getattr(owner, "_sync_shell_model_summary", None)
        if callable(sync_summary):
            sync_summary(active_model=model)


def on_runtime_settings_saved(owner: Any, settings: dict, *, models_view_index: int) -> None:
    """React to a local runtime backend settings save.

    Extracted from LauncherWindow._on_runtime_settings_saved as part of TR54-B1 Wave 8.
    """
    backend = str(settings.get("local_runtime_backend", "ollama") or "ollama").strip().lower() or "ollama"
    status_panel = getattr(owner, "_status_panel", None)
    if status_panel is not None:
        status_panel.append_syslog(f"local runtime saved -> {backend}")
    refresh = getattr(owner, "_refresh_personalization_state", None)
    if callable(refresh):
        refresh()
    update_preview = getattr(owner, "_update_route_preview", None)
    if callable(update_preview):
        update_preview(getattr(owner, "_last_command", ""))
    stack = getattr(owner, "_stack", None)
    if stack is not None and stack.currentIndex() == models_view_index:
        sync_summary = getattr(owner, "_sync_shell_model_summary", None)
        if callable(sync_summary):
            sync_summary(runtime_backend=backend)
    owner._log_launcher_event("local_runtime_saved", backend=backend)
