from __future__ import annotations

import os
import re
import uuid
from typing import Callable


def derive_topbar_model_context(
    *,
    route_text: str,
    runtime: object,
    main_model: str = "",
    support_model: str = "",
) -> dict[str, str]:
    using_match = re.search(r"\busing\s+([A-Za-z0-9._:/-]+)", route_text, flags=re.IGNORECASE)
    backup_match = re.search(r"\bbackup\s+([A-Za-z0-9._:/-]+)", route_text, flags=re.IGNORECASE)
    route_match = re.search(r"\bvia\s+([A-Za-z0-9._:/-]+)", route_text, flags=re.IGNORECASE)

    normalized_main = str(main_model or getattr(runtime, "chat_model", "") or getattr(runtime, "model", "") or "").strip()
    normalized_support = str(support_model or (backup_match.group(1) if backup_match else "")).strip()
    if not normalized_main and using_match is not None:
        normalized_main = str(using_match.group(1) or "").strip()
    backend = str(getattr(runtime, "backend", "") or "").strip().lower()
    route_name = str(route_match.group(1) if route_match else "").strip().upper()
    return {
        "main_model": normalized_main,
        "support_model": normalized_support,
        "backend": backend,
        "route": route_name,
    }


def build_shell_model_loadout_summary(
    *,
    active_model: str = "",
    runtime_backend: str = "",
    settings_payload: dict[str, object] | None = None,
    environment: dict[str, str] | None = None,
) -> str:
    settings = settings_payload if isinstance(settings_payload, dict) else {}
    env = environment if isinstance(environment, dict) else dict(os.environ)
    backend = (
        str(settings.get("local_runtime_backend", "") or "").strip()
        or str(runtime_backend or "").strip()
        or str(env.get("GUPPY_LOCAL_RUNTIME_BACKEND", "ollama") or "ollama").strip()
        or "ollama"
    )
    main_model = (
        str(settings.get("local_main_model", "") or "").strip()
        or str(env.get("GUPPY_MAIN_MODEL", "") or "").strip()
        or str(active_model or "").strip()
        or str(env.get("OLLAMA_MODEL", "") or "").strip()
        or "unset"
    )
    sub_a_model = (
        str(settings.get("local_sub_model_a", "") or "").strip()
        or str(env.get("GUPPY_SUB_MODEL_A", "") or "").strip()
        or str(env.get("GUPPY_LOCAL_FAST_MODEL", "") or "").strip()
        or "unset"
    )
    sub_b_model = (
        str(settings.get("local_sub_model_b", "") or "").strip()
        or str(env.get("GUPPY_SUB_MODEL_B", "") or "").strip()
        or str(env.get("GUPPY_LOCAL_CODE_MODEL", "") or "").strip()
        or "unset"
    )
    return (
        f"MODELS / {backend.upper()} / "
        f"MAIN {main_model} / SUB A {sub_a_model} / SUB B {sub_b_model}"
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
    request_timeout = launcher._chat_timeout_for_request(selected_mode, cmd)
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
