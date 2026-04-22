from __future__ import annotations

import threading
from pathlib import Path
from queue import Empty
from typing import Any, Callable


def sync_recovery_outcome(
    owner: Any,
    *,
    runtime_path: Path,
    read_jsonl_tail: Callable[..., list[dict[str, object]]],
) -> None:
    path = runtime_path / "launcher_events.jsonl"
    if not path.exists():
        return
    try:
        mtime = path.stat().st_mtime
    except Exception:
        mtime = 0.0
    if mtime == owner._recovery_outcome_mtime:
        return
    owner._recovery_outcome_mtime = mtime
    events = read_jsonl_tail(path, limit=80)
    target = None
    for item in reversed(events):
        if item.get("event") in {"recovery_result", "recovery_error"}:
            target = item
            break
    if not target:
        return

    action = str(target.get("action", "recovery"))
    ok = bool(target.get("ok", False))
    summary = str(target.get("summary", target.get("error", "")))
    signature = f"{target.get('ts', '')}|{target.get('event', '')}|{action}|{ok}|{summary}"
    if signature == owner._last_recovery_signature:
        return
    owner._last_recovery_signature = signature
    owner._status_panel.set_recovery_outcome(action, ok, summary)


def classify_recovery_summary(summary: str, ok: bool, default: str = "") -> str:
    text = (summary or "").lower()
    if "http 401" in text or "unauthorized" in text or "jwt_" in text:
        return "auth_failed"
    if (
        "network error" in text
        or "connection refused" in text
        or "not yet reachable" in text
        or "api unreachable" in text
    ):
        return "api_unreachable"
    if "stale" in text or "missing" in text or "offline" in text:
        return "runtime_stale"
    if default:
        return default
    return "recovery_ok" if ok else "recovery_error"


def format_recovery_summary(category: str, summary: str) -> str:
    text = (summary or "").strip()
    prefix = {
        "api_unreachable": "API unreachable",
        "auth_failed": "Auth failed",
        "runtime_stale": "Runtime stale",
    }.get(category, "")
    if not prefix:
        return text
    if not text:
        return prefix
    lowered = text.lower()
    if lowered.startswith(prefix.lower()):
        return text
    return f"{prefix}: {text}"


def push_recovery_outcome(
    owner: Any,
    action: str,
    ok: bool,
    summary: str,
    category: str = "",
) -> str:
    resolved_category = category or classify_recovery_summary(summary, ok)
    formatted = format_recovery_summary(resolved_category, summary)
    owner._recovery_events.put(
        {
            "kind": "outcome",
            "action": action,
            "ok": ok,
            "summary": formatted,
            "category": resolved_category,
        }
    )
    owner._log_launcher_event(
        "recovery_result" if ok else "recovery_error",
        action=action,
        ok=ok,
        category=resolved_category,
        summary=formatted,
    )
    return formatted


def drain_recovery_events(owner: Any) -> None:
    processed = 0
    while processed < owner._MAX_RECOVERY_EVENTS_PER_TICK:
        try:
            evt = owner._recovery_events.get_nowait()
        except Empty:
            break
        kind = str(evt.get("kind", ""))
        if kind == "status":
            text = str(evt.get("text", ""))
            owner._settings_view.set_recovery_status(text)
            owner._settings_hub_view.set_recovery_status(text)
            owner._set_daily_activity(text)
            owner._assistant_view.set_recovery_summary(text, healthy="error" not in text.lower())
            owner._settings_hub_view.set_daily_context_recovery(
                owner._assistant_view._recovery_summary.text(),
                ok="error" not in text.lower(),
            )
        elif kind == "syslog":
            text = str(evt.get("text", ""))
            owner._status_panel.append_syslog(text)
            owner._settings_hub_view.append_log(text)
            owner._set_daily_activity(text)
        elif kind == "outcome":
            action = str(evt.get("action", "recovery"))
            ok = bool(evt.get("ok", False))
            summary = str(evt.get("summary", ""))
            owner._status_panel.set_recovery_outcome(action, ok, summary)
            owner._settings_hub_view.set_recovery_status(f"{action}: {summary}")
            owner._settings_hub_view.append_log(f"Recovery {action}: {summary}")
            owner._set_daily_activity(f"Recovery {action}: {summary}")
            owner._assistant_view.set_recovery_summary(f"{action}: {summary}", healthy=ok)
            owner._settings_hub_view.set_daily_context_recovery(owner._assistant_view._recovery_summary.text(), ok=ok)
            if owner._update_windows_ops_chain(action, ok=ok, summary=summary):
                processed += 1
                continue
            recovery_changes = {
                "health_snapshot": "Refreshed the launcher-visible health snapshot and operator evidence.",
                "warmup": "Refreshed startup-readiness and runtime-freshness evidence.",
                "restart_daemon": "Restarted the daemon and prepared the runtime for follow-up health checks.",
                "audit_runtime": "Re-ran runtime audit evidence and refreshed diagnostics guidance.",
            }.get(action, "")
            if recovery_changes:
                owner._record_windows_ops_state(action, summary, recovery_changes, ok=ok)
        processed += 1


def start_recovery_request(
    owner: Any,
    action: str,
    *,
    thread_factory: Callable[..., threading.Thread] = threading.Thread,
) -> None:
    act = (action or "").strip().lower()
    owner._recovery_events.put({"kind": "status", "text": f"Recovery: {act}..."})
    owner._recovery_events.put({"kind": "syslog", "text": f"recovery: {act}"})
    owner._log_launcher_event("recovery_requested", action=act)
    thread_factory(target=run_recovery_request, args=(owner, act), daemon=True).start()


def run_recovery_request(owner: Any, act: str) -> None:
    """Run recovery work off the UI thread; enqueue UI updates for main-thread drain."""
    if not act:
        return

    try:
        api_state, api_detail = owner._api_reachability_status()
        if api_state == "reachable":
            if act == "health_snapshot":
                status = owner._http_json("/status", method="GET")
                startup = owner._http_json("/startup/check?deep=true", method="GET")
                status_state = str(status.get("status", "unknown")).upper()
                startup_state = str(startup.get("overall", "unknown")).upper()
                summary = f"status={status_state} startup={startup_state}"
                category = "runtime_ready"
                if startup_state not in {"GO", "READY", "OK", "PASS"}:
                    category = "runtime_stale"
                formatted = push_recovery_outcome(owner, "health_snapshot", category == "runtime_ready", summary, category)
                msg = f"Snapshot {'OK' if category == 'runtime_ready' else 'ERROR'}: {formatted}"
            elif act in {"warmup", "restart_daemon", "audit_runtime"}:
                result = owner._http_json(
                    "/repair",
                    method="POST",
                    payload={"action": act, "dry_run": False},
                    timeout=12.0,
                )
                ok = bool(result.get("ok", False))
                summary = str(result.get("summary", "done"))
                category = classify_recovery_summary(summary, ok, "recovery_ok" if ok else "recovery_error")
                if act == "restart_daemon":
                    owner._refresh_api_auth_state("restart_daemon_api")
                formatted = push_recovery_outcome(owner, act, ok, summary, category)
                msg = f"Recovery {act}: {'OK' if ok else 'ERROR'} - {formatted}"
            else:
                raise ValueError(f"unsupported action: {act}")

            owner._recovery_events.put({"kind": "status", "text": msg})
            owner._recovery_events.put({"kind": "syslog", "text": msg})
            return

        if api_state == "auth_failed":
            formatted = push_recovery_outcome(owner, act, False, api_detail, "auth_failed")
            msg = f"Recovery {act}: ERROR - {formatted}"
            owner._recovery_events.put({"kind": "status", "text": msg})
            owner._recovery_events.put({"kind": "syslog", "text": msg})
            return

        api_summary = format_recovery_summary("api_unreachable", api_detail or "running direct recovery")
        owner._recovery_events.put({"kind": "syslog", "text": api_summary})

        if act == "health_snapshot":
            result = owner._direct_health_snapshot()
        elif act == "warmup":
            result = owner._direct_warmup()
        elif act == "restart_daemon":
            owner._recovery_events.put({"kind": "syslog", "text": "starting api server..."})
            started, detail = owner._start_api_subprocess()
            result = {
                "ok": started,
                "summary": detail,
                "category": "runtime_ready" if started else "api_unreachable",
            }
            owner._refresh_api_auth_state("restart_daemon_direct")
        elif act == "audit_runtime":
            result = owner._direct_audit_runtime()
        else:
            raise ValueError(f"unsupported action: {act}")

        ok = bool(result.get("ok", False))
        summary = str(result.get("summary", "done"))
        category = str(result.get("category", "")) or classify_recovery_summary(summary, ok, "api_unreachable")
        formatted = push_recovery_outcome(owner, act, ok, summary, category)
        msg = f"Direct {act}: {'OK' if ok else 'ERROR'} - {formatted}"
        owner._recovery_events.put({"kind": "status", "text": msg})
        owner._recovery_events.put({"kind": "syslog", "text": msg})

    except Exception as exc:
        formatted = push_recovery_outcome(owner, act or "recovery", False, str(exc))
        msg = f"Recovery {act} error: {formatted}"
        owner._recovery_events.put({"kind": "status", "text": msg})
        owner._recovery_events.put({"kind": "syslog", "text": msg})
