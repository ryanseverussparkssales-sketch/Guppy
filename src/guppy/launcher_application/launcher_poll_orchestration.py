"""
src/guppy/launcher_application/launcher_poll_orchestration.py

Status poll orchestration helper for LauncherWindow.
Extracted as part of Tranche 54 / TR54-B1 module decomposition.

This module handles the per-tick work that was previously inlined in
LauncherWindow._poll_status: voice binding resolution, snapshot building,
runtime badge composition, and surface sync.
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any

from src.guppy.experience_config import (
    load_voice_bindings,
    resolve_voice_binding,
    voice_binding_summary,
)
from src.guppy.runtime_application import summarize_startup_readiness
from .launcher_shell_support import build_runtime_badge_state
from .status_poll import build_launcher_status_poll_snapshot, fetch_api_status
from .storage_io import read_json_dict


def orchestrate_status_poll(
    owner: Any,
    *,
    runtime_path: Path,
    personalization_available: bool,
    start_time: float,
) -> None:
    """Run one status poll tick, updating all surfaces on *owner*.

    This is the extracted body of LauncherWindow._poll_status.
    Pass module-level constants (*runtime_path*, *personalization_available*,
    *start_time*) so the function remains independent of the launcher module's
    global scope.

    Exceptions are caught here so a single bad tick never breaks the poll loop.
    The topbar and status panel are degraded to a visible error state rather
    than left showing stale "healthy" data.
    """
    try:
        _orchestrate_status_poll_inner(
            owner,
            runtime_path=runtime_path,
            personalization_available=personalization_available,
            start_time=start_time,
        )
    except Exception as exc:  # noqa: BLE001
        _exc_str = str(exc)
        try:
            owner._topbar.set_runtime_status(
                "poll error",
                detail=f"Status poll failed: {_exc_str}",
                severity="error",
            )
        except Exception:
            pass
        try:
            owner._status_panel.append_syslog(f"poll error: {_exc_str}")
        except Exception:
            pass


def _orchestrate_status_poll_inner(
    owner: Any,
    *,
    runtime_path: Path,
    personalization_available: bool,
    start_time: float,
) -> None:
    """Inner implementation of one status poll tick (called by orchestrate_status_poll)."""
    poll_t0 = time.monotonic()
    startup_budget_ms: int = getattr(owner, "_startup_budget_ms", 800)

    # ── Drain queued events ───────────────────────────────────────────────────
    owner._drain_deferred_syslog()
    owner._drain_assistant_events()
    owner._drain_recovery_events()
    owner._update_sys_strip()

    # ── Heartbeats ────────────────────────────────────────────────────────────
    guppy_online = (runtime_path / "guppy.heartbeat").exists()

    # ── Status data ───────────────────────────────────────────────────────────
    gs = read_json_dict(runtime_path / "guppy.status")
    gs["guppy_online"] = guppy_online
    api_status = fetch_api_status(owner._http_json)

    voice_summary = str(gs.get("tts_engine", os.environ.get("GUPPY_TTS_ENGINE", "edge")) or "edge")
    active_model_id = owner._assistant_model_id(
        owner._assistant_view.selected_mode(),
        str(gs.get("active_model", "") or ""),
    )
    if personalization_available:
        try:
            voice_summary = voice_binding_summary(
                resolve_voice_binding(
                    persona_id=owner._assistant_view.chat_context()[1],
                    model_id=active_model_id,
                    voice_bindings=load_voice_bindings(),
                )
            )
        except Exception:
            pass

    poll_snapshot = build_launcher_status_poll_snapshot(
        launcher_status=gs,
        api_status=api_status,
        environment=os.environ,
        active_instance_name=owner._active_instance_name,
        last_instance_snapshot=owner._last_instance_snapshot,
        embedded_online=owner._embedded_online,
        fallback_last_query=owner._last_command,
        voice_summary=voice_summary,
        route_evidence=owner._assistant_view._route_facts.text(),
    )
    data = poll_snapshot.data

    # ── Update surfaces ───────────────────────────────────────────────────────
    owner._status_panel.update_status(data)
    owner._assistant_view.set_runtime_facts(
        profile=str(data.get("profile", "standard") or "standard"),
        model=active_model_id,
        voice=voice_summary,
        latency=str(data.get("latency", "-") or "-"),
        last_query=str(data.get("last_query", "-") or "-"),
    )
    owner._settings_hub_view.set_daily_context_runtime(owner._assistant_view._runtime_facts.text())
    owner._settings_hub_view.set_daily_context_route(owner._assistant_view._route_facts.text())
    owner._sync_topbar_model_context(main_model=active_model_id)

    # ── Agent cards ───────────────────────────────────────────────────────────
    guppy_load = poll_snapshot.guppy_load
    guppy_online = poll_snapshot.guppy_online

    owner._status_panel.update_agent_status("guppy", guppy_online, "—", guppy_load)
    owner._assistant_view.set_background_status(
        poll_snapshot.background_summary,
        healthy=guppy_online,
    )
    owner._settings_hub_view.set_daily_context_recovery(
        f"Recovery: {'stable' if guppy_online else 'needs attention'}",
        ok=guppy_online,
    )

    # ── Runtime badge ─────────────────────────────────────────────────────────
    runtime_health = poll_snapshot.runtime_health
    owner._runtime_health_snapshot = runtime_health
    startup_summary = summarize_startup_readiness(
        poll_snapshot.api_status.get("startup_readiness", {})
    )
    runtime_badge = build_runtime_badge_state(
        api_status=poll_snapshot.api_status,
        runtime_overall=runtime_health.overall,
        startup_summary=startup_summary,
        startup_first_poll_ok=owner._startup_first_poll_ok,
        startup_over_budget=bool(owner._startup_over_budget),
    )
    owner._topbar.set_runtime_status(
        runtime_badge.label,
        detail=runtime_badge.detail,
        severity=runtime_badge.severity,
    )

    # ── Hub snapshots ─────────────────────────────────────────────────────────
    owner._models_hub_view.set_status_snapshot(poll_snapshot.api_status)
    owner._settings_hub_view.set_status_snapshot(poll_snapshot.settings_status_snapshot)

    windows_snapshot = owner._settings_hub_view.windows_ops_snapshot()
    windows_snapshot_signature = owner._payload_signature(windows_snapshot)
    if windows_snapshot_signature != owner._last_windows_snapshot_signature:
        owner._settings_hub_view.set_windows_snapshot(windows_snapshot)
        owner._last_windows_snapshot_signature = windows_snapshot_signature

    owner._refresh_notification_badge()
    owner._sync_recovery_outcome()

    # ── Instance refresh (idle only) ──────────────────────────────────────────
    if not owner._request_in_flight and owner._bootstrap_instance_refresh_complete:
        owner._refresh_instance_views(load_logs=False)

    # ── Startup completion logging ────────────────────────────────────────────
    if not owner._startup_logged_first_poll:
        owner._startup_logged_first_poll = True
        owner._startup_first_poll_ok = True
        owner._complete_startup_phase("first_status_poll", start_at=owner._startup_phase_started["window_init"])
        owner._log_launcher_event("startup_phase", phase="first_status_poll_complete")
        if owner._startup_over_budget:
            summary = ", ".join(owner._startup_over_budget)
            owner._status_panel.append_syslog(f"startup budget warning: {summary}")
        else:
            owner._status_panel.append_syslog(
                f"startup budget OK (<={startup_budget_ms}ms phases)"
            )

    # ── Auth self-check (deferred) ────────────────────────────────────────────
    if (
        not owner._auth_self_check_ok
        and not owner._auth_self_check_inflight
        and bool(api_status)
        and (time.monotonic() - owner._auth_self_check_last_attempt) >= 5.0
    ):
        owner._auth_self_check_inflight = True
        owner._auth_self_check_last_attempt = time.monotonic()
        threading.Thread(target=owner._run_auth_self_check, daemon=True).start()

    # ── Poll budget warning ───────────────────────────────────────────────────
    poll_ms = int((time.monotonic() - poll_t0) * 1000)
    if poll_ms > startup_budget_ms:
        now = time.monotonic()
        if now - owner._last_poll_warn_ts > 10.0:
            owner._last_poll_warn_ts = now
            owner._log_launcher_event(
                "ui_poll_over_budget",
                poll_ms=poll_ms,
                budget_ms=startup_budget_ms,
            )
            owner._status_panel.append_syslog(
                f"ui poll over budget: {poll_ms}ms (budget {startup_budget_ms}ms)"
            )


def complete_startup_phase(
    owner: Any,
    phase: str,
    *,
    start_at: float | None = None,
) -> None:
    """Record the duration of a startup phase and warn if over budget.

    Extracted from LauncherWindow._complete_startup_phase as part of TR54-B1 Wave 7.
    """
    started = (
        start_at
        if start_at is not None
        else owner._startup_phase_started.get(phase, time.monotonic())
    )
    dur_ms = int((time.monotonic() - started) * 1000)
    owner._startup_phase_durations_ms[phase] = dur_ms
    owner._log_launcher_event(
        "startup_phase_duration",
        phase=phase,
        duration_ms=dur_ms,
        budget_ms=owner._startup_budget_ms,
        over_budget=dur_ms > owner._startup_budget_ms,
    )
    if dur_ms > owner._startup_budget_ms:
        owner._startup_over_budget.append(f"{phase}:{dur_ms}ms")
        owner._log_launcher_event(
            "startup_phase_over_budget",
            phase=phase,
            duration_ms=dur_ms,
            budget_ms=owner._startup_budget_ms,
        )
        status_panel = getattr(owner, "_status_panel", None)
        if status_panel is not None:
            status_panel.append_syslog(f"startup phase over budget: {phase}={dur_ms}ms")


def sync_topbar_model_context(
    owner: Any,
    *,
    main_model: str = "",
    support_model: str = "",
) -> None:
    """Push the current model/runtime context into the topbar widget.

    Extracted from LauncherWindow._sync_topbar_model_context as part of TR54-B1 Wave 9.
    """
    from .launcher_command_flow import derive_topbar_model_context  # local import avoids circular
    topbar = getattr(owner, "_topbar", None)
    setter = getattr(topbar, "set_model_context", None)
    if not callable(setter):
        return
    assistant_view = getattr(owner, "_assistant_view", None)
    route_text = ""
    if assistant_view is not None:
        route_label = getattr(assistant_view, "_route_facts", None)
        if route_label is not None and hasattr(route_label, "text"):
            route_text = str(route_label.text())
    health_snapshot = getattr(owner, "_runtime_health_snapshot", None)
    local_runtime = getattr(health_snapshot, "local_runtime", "") if health_snapshot is not None else ""
    setter(
        **derive_topbar_model_context(
            route_text=route_text,
            runtime=local_runtime,
            main_model=main_model,
            support_model=support_model,
        )
    )
