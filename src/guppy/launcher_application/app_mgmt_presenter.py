"""Presenter helpers for App Mgmt status, context, and automation copy."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .app_mgmt_connector_inventory import (
    ConnectorActionButtonState,
    ConnectorInventoryState,
    ConnectorSelectorOption,
    build_connector_inventory_state,
    validate_connector_action,
)
from .packaging_audit import packaging_audit_summary
from .security_gate import security_gate_summary
from .windows_ops_presenter import build_windows_gate_followup_line, build_windows_handoff_line
from .windows_ops_runtime import latest_runtime_artifact


@dataclass(frozen=True, slots=True)
class DailyContextState:
    activity_text: str
    workspace_text: str
    runtime_text: str
    route_text: str
    recovery_text: str
    recovery_ok: bool


@dataclass(frozen=True, slots=True)
class StatusSnapshotState:
    health_text: str
    voice_text: str
    route_health_text: str
    resource_text: str
    windows_runtime_text: str


@dataclass(frozen=True, slots=True)
class InstanceSnapshotState:
    instances_text: str


@dataclass(frozen=True, slots=True)
class AutomationSnapshotState:
    workspace_text: str
    queue_text: str
    staged_text: str
    result_text: str
    approval_text: str
    report_text: str
    evidence_text: str
    stress_text: str
    recent_text: str
    validation_text: str
    status_text: str


def build_windows_ops_snapshot(
    root: Path,
    *,
    configured_backend: str,
    launcher_python: str,
) -> dict[str, str]:
    runtime_dir = root / "runtime"
    config_dir = root / "config"
    settings_path = runtime_dir / "app_settings.json"
    launcher_events = runtime_dir / "launcher_events.jsonl"
    state_path = runtime_dir / "windows_ops_state.json"
    venv_python = root / ".venv" / "Scripts" / "python.exe"
    supervisor_script = root / "bin" / "launch_api_supervised.bat"
    build_script = root / "bin" / "build_executable.bat"
    repair_file = runtime_dir / "repair_token.txt"
    latest_bundle = latest_runtime_artifact(runtime_dir, "diagnostics_bundle_*.json", "diagnostics_*.json")
    latest_bundle_text = str(latest_bundle) if latest_bundle is not None else "none yet"
    packaging = packaging_audit_summary(root)
    security = security_gate_summary()
    install_bits = [
        f"Launcher python: {launcher_python}",
        f"Repo python: {'present' if venv_python.exists() else 'missing'}",
        f"Ollama CLI: {'found' if shutil.which('ollama') else 'missing'}",
        f"Lemonade CLI: {'found' if shutil.which('lemonade') else 'missing'}",
        f"Supervisor script: {'ready' if supervisor_script.exists() else 'missing'}",
        f"Packager: {'ready' if build_script.exists() else 'missing'}",
    ]

    repair_hint = (
        "keyring-backed first; file fallback present"
        if repair_file.exists()
        else "keyring-backed first; file fallback not present"
    )
    state_payload: dict[str, object] = {}
    if state_path.exists():
        try:
            parsed = json.loads(state_path.read_text(encoding="utf-8"))
            state_payload = parsed if isinstance(parsed, dict) else {}
        except Exception:
            state_payload = {}
    last_action = str(state_payload.get("action", "") or "").strip()
    last_timestamp = str(state_payload.get("timestamp", "") or "").strip()
    last_summary = str(state_payload.get("summary", "") or "").strip()
    last_changes = str(state_payload.get("changes", "") or "").strip()
    last_phase = str(state_payload.get("phase", "") or "").strip().lower()
    last_event_id = str(state_payload.get("event_id", "") or "").strip()
    next_step = str(state_payload.get("next_step", "") or "").strip()
    fix_target = str(state_payload.get("fix_target", "") or "").strip()
    docs_hint = str(state_payload.get("docs_hint", "") or "").strip()
    entry_point = str(state_payload.get("entry_point", "") or "").strip()
    steps_completed = state_payload.get("steps_completed")
    steps_total = state_payload.get("steps_total")
    ok = bool(state_payload.get("ok", False))
    artifacts = (
        [item for item in state_payload.get("artifacts", []) if isinstance(item, dict)]
        if isinstance(state_payload.get("artifacts"), list)
        else []
    )
    receipt_path = str(state_payload.get("release_receipt", "") or "").strip()
    summary_path = str(state_payload.get("release_summary", "") or "").strip()
    gate_summary = str(state_payload.get("gate_summary", "") or "").strip()
    gate_detail = str(state_payload.get("gate_detail", "") or "").strip()
    gate_recommendations = (
        [str(item).strip() for item in state_payload.get("gate_recommendations", []) if str(item).strip()]
        if isinstance(state_payload.get("gate_recommendations"), list)
        else []
    )
    gate_recommendation_details = (
        [item for item in state_payload.get("gate_recommendation_details", []) if isinstance(item, dict)]
        if isinstance(state_payload.get("gate_recommendation_details"), list)
        else []
    )
    review_order = (
        [str(item).strip() for item in state_payload.get("review_order", []) if str(item).strip()]
        if isinstance(state_payload.get("review_order"), list)
        else []
    )
    step_text = (
        f" | Steps: {int(steps_completed or 0)}/{int(steps_total or 0)}"
        if steps_completed is not None and steps_total is not None
        else ""
    )
    phase_text = f" | Phase: {last_phase}" if last_phase else ""
    ref_text = f" | Ref: {last_event_id}" if last_event_id else ""
    return {
        "install": "Installed on this PC: " + " | ".join(install_bits),
        "runtime": f"Local AI runtime: {configured_backend} | Live backend: waiting for first status poll",
        "paths": f"Data locations: runtime={runtime_dir} | config={config_dir} | settings={settings_path}",
        "repair": f"Repair help: {repair_hint} | API relaunch: {supervisor_script}",
        "update": (
            "Update steps: python -m pip install -r requirements.txt | "
            "optional extras: python -m pip install -r requirements-optional.txt | "
            "postflight: python tools/validate_build_checks.py + python tools/verify_provider_runtime.py | "
            "daily launcher: python src/guppy/cli/launch.py launcher"
        ),
        "diagnostics": (
            f"Diagnostics: launcher log={launcher_events} | latest bundle={latest_bundle_text} | "
            f"security gate={security['summary']} | packaging audit={packaging['summary']} | "
            "runtime check: python tools/verify_provider_runtime.py"
        ),
        "entry": (
            "Useful entry points: launcher=python src/guppy/cli/launch.py launcher | "
            "package=bin/build_executable.bat --no-clean | "
            f"supervisor={supervisor_script}"
        ),
        "next": (
            "Recommended next step: "
            + (
                next_step
                + (f" | Fix in: {fix_target}" if fix_target else "")
                + (f" | Doc: {docs_hint}" if docs_hint else "")
                + (f" | Command: {entry_point}" if entry_point else "")
            )
            if next_step
            else (
                "Review the Security Gate in Backend Stats first. " + str(security["detail"])
                if not bool(security["ok"])
                else "Review the Packaging Audit in Backend Stats next. " + str(packaging["detail"])
                if not bool(packaging["ok"])
                else "Recommended next step: choose VERIFY, UPDATE, PACKAGE, RELEASE DRY RUN, SUPERVISED API, RESTART, or REPAIR."
            )
        ),
        "service": (
            f"Recent service action: {last_action} @ {last_timestamp} | {'OK' if ok else 'CHECK'} | {last_summary}{phase_text}{step_text}{ref_text}"
            if last_action
            else "Recent service action: none recorded yet"
        ),
        "changes": f"Recent changes: {last_changes or 'No service summary recorded yet.'}",
        "gate": "Release check: "
        + (gate_summary + (f" | {gate_detail}" if gate_detail else "") if gate_summary else "no dry-run result recorded yet."),
        "gate_fix": build_windows_gate_followup_line(
            gate_summary,
            gate_recommendations,
            gate_recommendation_details,
        ),
        "handoff": build_windows_handoff_line(
            artifacts,
            receipt_path=receipt_path,
            summary_path=summary_path,
            review_order=review_order,
            root=root,
        ),
    }


def build_daily_context_state(
    *,
    activity: str = "",
    workspace: str = "",
    runtime: str = "",
    route: str = "",
    recovery: str = "",
    recovery_ok: bool = True,
) -> DailyContextState:
    activity_msg = (activity or "launcher ready").strip() or "launcher ready"
    workspace_msg = (workspace or "workspace context unavailable").strip() or "workspace context unavailable"
    runtime_msg = (runtime or "runtime details unavailable").strip() or "runtime details unavailable"
    route_msg = (route or "route preview unavailable").strip() or "route preview unavailable"
    recovery_msg = (recovery or "Recovery: all clear").strip() or "Recovery: all clear"
    return DailyContextState(
        activity_text=f"Recent activity: {activity_msg}",
        workspace_text=workspace_msg,
        runtime_text=runtime_msg if ":" in runtime_msg else f"Ready now: {runtime_msg}",
        route_text=route_msg,
        recovery_text=recovery_msg,
        recovery_ok=recovery_ok,
    )


def build_status_snapshot_state(
    payload: Mapping[str, object] | None,
    *,
    configured_backend: str,
    previous_windows_runtime: str = "",
) -> StatusSnapshotState:
    source = payload if isinstance(payload, Mapping) else {}
    api_state = str(source.get("status", "unknown") or "unknown").upper()
    startup = source.get("startup_readiness", {})
    startup_overall = "UNKNOWN"
    if isinstance(startup, Mapping):
        startup_overall = str(startup.get("overall", startup.get("status", "unknown")) or "unknown").upper()

    voice_tts = str(source.get("voice_tts_backend", "unknown") or "unknown")
    voice_stt = str(source.get("voice_stt_backend", "unknown") or "unknown")
    binding = str(source.get("voice_binding", "") or "").strip()

    route_evidence = str(source.get("route_evidence", "") or "").strip()
    route_text = f"Why the next route was chosen: {route_evidence or 'waiting for the next route preview'}"

    resource_text = "System headroom: unknown"
    envelope = source.get("resource_envelope", {})
    if isinstance(envelope, Mapping):
        state = str(envelope.get("state", "unknown") or "unknown")
        detail = str(envelope.get("message", envelope.get("detail", "")) or "").strip()
        resource_text = f"System headroom: {state}" + (f" | {detail}" if detail else "")

    windows_runtime_text = previous_windows_runtime
    local_runtime = source.get("local_runtime", {})
    if isinstance(local_runtime, Mapping):
        live_backend = str(local_runtime.get("backend", configured_backend.lower()) or configured_backend).strip().upper()
        live_state = str(local_runtime.get("state", "unknown") or "unknown").strip().upper()
        live_detail = str(local_runtime.get("detail", "") or "").strip()
        windows_runtime_text = (
            f"Local AI runtime: {configured_backend} | Live backend: {live_backend} | Status: {live_state}"
            + (f" | {live_detail}" if live_detail else "")
        )

    return StatusSnapshotState(
        health_text=f"API health: {api_state} | Startup readiness: {startup_overall}",
        voice_text=f"Voice services: tts={voice_tts} | stt={voice_stt}" + (f" | {binding}" if binding else ""),
        route_health_text=route_text,
        resource_text=resource_text,
        windows_runtime_text=windows_runtime_text,
    )


def build_instance_snapshot_state(payload: Mapping[str, object] | None) -> InstanceSnapshotState:
    source = payload if isinstance(payload, Mapping) else {}
    limits = source.get("limits", {})
    configured = int(limits.get("configured", 0) or 0) if isinstance(limits, Mapping) else 0
    max_configured = int(limits.get("max_configured", 5) or 5) if isinstance(limits, Mapping) else 5
    active_runtime = int(limits.get("active_runtime", 0) or 0) if isinstance(limits, Mapping) else 0
    max_active_runtime = int(limits.get("max_active_runtime", 2) or 2) if isinstance(limits, Mapping) else 2
    active_instance = str(source.get("active_instance", "-") or "-")
    return InstanceSnapshotState(
        instances_text=(
            f"Workspaces: active={active_instance} | configured {configured}/{max_configured} | "
            f"live {active_runtime}/{max_active_runtime}"
        )
    )


def build_automation_snapshot_state(payload: Mapping[str, object] | None) -> AutomationSnapshotState:
    source = payload if isinstance(payload, Mapping) else {}
    workspace = str(source.get("workspace", "") or "").strip()
    queue_counts = str(source.get("queue_counts", "") or "").strip()
    staged_file = str(source.get("staged_file", "") or "").strip()
    result_path = str(source.get("result_path", "") or "").strip()
    approval_state = str(source.get("approval_state", "") or "").strip()
    report_path = str(source.get("report_path", "") or "runtime/offhours_builder_report.json").strip()
    evidence_pack_path = str(source.get("evidence_pack_path", "") or "runtime/user_test_evidence.md").strip()
    stress_report_path = str(source.get("stress_report_path", "") or "").strip()
    recent_events = str(source.get("recent_events", "") or "").strip()
    validation_command = str(source.get("validation_command", "") or "").strip()
    status = str(source.get("status", "") or "").strip()
    return AutomationSnapshotState(
        workspace_text=workspace or "Workspace step: active workspace telemetry is not available yet.",
        queue_text=queue_counts or "Queue counts: builder queue status is not available yet.",
        staged_text=staged_file or "Latest staged output: nothing is waiting for approval yet.",
        result_text=result_path or "Latest result: no approved builder output has been recorded yet.",
        approval_text=approval_state or "Latest approval: no staged task is awaiting approval yet.",
        report_text=f"Builder report: {report_path}",
        evidence_text=f"Evidence pack: {evidence_pack_path}",
        stress_text=(
            f"Latest stress run: {stress_report_path}"
            if stress_report_path
            else "Latest stress run: no stress report recorded yet."
        ),
        recent_text=recent_events or "Recent operator notes: no recent launcher notes recorded yet.",
        validation_text=(
            f"Validation command: {validation_command}"
            if validation_command
            else "Validation command: unavailable"
        ),
        status_text=status,
    )
