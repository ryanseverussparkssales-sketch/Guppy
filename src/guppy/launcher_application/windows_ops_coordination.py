"""Launcher-shell coordination helpers for Windows Ops state and completion flows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .windows_ops_runtime import (
    default_windows_ops_event_id,
    release_review_order,
    write_windows_release_receipt,
)
from .windows_ops_state import (
    advance_windows_ops_chain,
    build_windows_ops_feedback_kwargs,
    build_windows_ops_state_payload,
    normalize_windows_gate_details,
    normalize_windows_ops_artifacts,
    start_windows_ops_chain,
)


StateWriter = Callable[[Path, dict[str, object]], None]


@dataclass(frozen=True, slots=True)
class WindowsOpsStateRecord:
    """Normalized state payload inputs for launcher Windows Ops persistence."""

    action: str
    summary: str
    changes: str
    ok: bool
    commands: list[str] | None = None
    event_id: str = ""
    steps_completed: int | None = None
    steps_total: int | None = None
    phase: str = "completed"
    next_step: str = ""
    fix_target: str = ""
    docs_hint: str = ""
    entry_point: str = ""
    artifacts: list[dict[str, object]] | None = None
    gate_summary: str = ""
    gate_detail: str = ""
    gate_checks: list[dict[str, object]] | None = None
    gate_required_files: list[dict[str, object]] | None = None
    gate_failed_checks: list[str] | None = None
    gate_missing_files: list[str] | None = None
    gate_passed_checks: int | None = None
    gate_total_checks: int | None = None
    gate_recommendations: list[str] | None = None
    gate_recommendation_details: list[dict[str, object]] | None = None


@dataclass(frozen=True, slots=True)
class WindowsOpsStateUpdate:
    """Persisted state payload plus rendered feedback for the Settings hub."""

    action: str
    payload: dict[str, object]
    feedback: dict[str, object]


@dataclass(frozen=True, slots=True)
class WindowsOpsChainProgress:
    """Result of advancing a multi-step Windows Ops recovery chain."""

    matched: bool
    completed: bool
    next_chain: dict[str, object] | None
    state_record: WindowsOpsStateRecord | None = None
    event_fields: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class WindowsOpsTerminalRecipeCompletion:
    """Normalized launcher-facing result for a completed Windows Ops recipe."""

    summary: str
    state_record: WindowsOpsStateRecord
    event_fields: dict[str, object]


def begin_windows_ops_chain(action: str, *, steps: list[str], changes: str) -> dict[str, object] | None:
    """Start a tracked Windows Ops chain using the shared state helper."""

    normalized = str(action or "").strip().lower()
    return start_windows_ops_chain(normalized, steps, changes)


def persist_windows_ops_state(
    record: WindowsOpsStateRecord,
    *,
    state_path: Path,
    receipt_path: Path,
    summary_path: Path,
    write_state: StateWriter,
) -> WindowsOpsStateUpdate:
    """Write launcher Windows Ops state and build the matching feedback payload."""

    artifact_payload = normalize_windows_ops_artifacts(record.artifacts)
    normalized_phase = str(record.phase or "completed").strip().lower() or "completed"
    resolved_event_id = str(record.event_id or "").strip()
    release_receipt = ""
    release_summary = ""
    if normalized_phase != "queued" and not resolved_event_id:
        resolved_event_id = default_windows_ops_event_id(record.action)
    if normalized_phase != "queued":
        release_receipt = write_windows_release_receipt(
            state_path,
            receipt_path,
            summary_path,
            record.action,
            record.summary,
            record.changes,
            ok=record.ok,
            commands=record.commands,
            event_id=resolved_event_id,
            steps_completed=record.steps_completed,
            steps_total=record.steps_total,
            phase=normalized_phase,
            next_step=record.next_step,
            fix_target=record.fix_target,
            docs_hint=record.docs_hint,
            entry_point=record.entry_point,
            artifacts=artifact_payload,
            gate_summary=record.gate_summary,
            gate_detail=record.gate_detail,
            gate_checks=record.gate_checks,
            gate_required_files=record.gate_required_files,
            gate_failed_checks=record.gate_failed_checks,
            gate_missing_files=record.gate_missing_files,
            gate_passed_checks=record.gate_passed_checks,
            gate_total_checks=record.gate_total_checks,
            gate_recommendations=record.gate_recommendations,
            gate_recommendation_details=record.gate_recommendation_details,
        )
        release_summary = str(summary_path)
    payload = build_windows_ops_state_payload(
        action=record.action,
        ok=record.ok,
        summary=record.summary,
        changes=record.changes,
        commands=record.commands,
        event_id=resolved_event_id,
        steps_completed=record.steps_completed,
        steps_total=record.steps_total,
        phase=normalized_phase,
        next_step=record.next_step,
        fix_target=record.fix_target,
        docs_hint=record.docs_hint,
        entry_point=record.entry_point,
        artifacts=artifact_payload,
        release_receipt=release_receipt,
        release_summary=release_summary,
        gate_summary=record.gate_summary,
        gate_detail=record.gate_detail,
        gate_failed_checks=record.gate_failed_checks,
        gate_missing_files=record.gate_missing_files,
        gate_passed_checks=record.gate_passed_checks,
        gate_total_checks=record.gate_total_checks,
        gate_recommendations=record.gate_recommendations,
        gate_recommendation_details=record.gate_recommendation_details,
    )
    write_state(state_path, payload)
    feedback = build_windows_ops_feedback_kwargs(payload, review_order=release_review_order(record.action))
    return WindowsOpsStateUpdate(
        action=str(record.action or "").strip().lower(),
        payload=payload,
        feedback=feedback,
    )


def progress_windows_ops_chain(
    chain: dict[str, object] | None,
    action: str,
    *,
    ok: bool,
    summary: str,
    guidance_builder: Callable[[str, bool], dict[str, str]],
    artifacts: list[dict[str, object]],
    receipt_path: Path,
    summary_path: Path,
) -> WindowsOpsChainProgress:
    """Advance a tracked chain and build the completion payload when it finishes."""

    result = advance_windows_ops_chain(
        chain,
        action,
        ok=ok,
        summary=summary,
    )
    if not result.matched:
        return WindowsOpsChainProgress(matched=False, completed=False, next_chain=chain)
    if not result.completed:
        return WindowsOpsChainProgress(
            matched=True,
            completed=False,
            next_chain=result.next_chain,
        )
    parent_action = result.parent_action
    guidance = guidance_builder(parent_action, result.overall_ok)
    state_record = WindowsOpsStateRecord(
        action=parent_action,
        summary=result.summary_text,
        changes=result.change_text,
        ok=result.overall_ok,
        event_id=default_windows_ops_event_id(parent_action),
        steps_completed=result.steps_completed,
        steps_total=result.steps_total,
        phase="completed",
        next_step=str(guidance.get("next_step", "") or ""),
        fix_target=str(guidance.get("fix_target", "") or ""),
        docs_hint=str(guidance.get("docs_hint", "") or ""),
        entry_point=str(guidance.get("entry_point", "") or ""),
        artifacts=artifacts,
    )
    event_fields = {
        "action": parent_action,
        "ok": result.overall_ok,
        "steps_completed": result.steps_completed,
        "steps_total": result.steps_total,
        "summary": result.summary_text,
        "event_id": state_record.event_id,
        "next_step": state_record.next_step,
        "fix_target": state_record.fix_target,
        "artifacts": artifacts,
        "release_receipt": str(receipt_path),
        "release_summary": str(summary_path),
    }
    return WindowsOpsChainProgress(
        matched=True,
        completed=True,
        next_chain=None,
        state_record=state_record,
        event_fields=event_fields,
    )


def complete_windows_ops_terminal_recipe(
    payload: dict[str, object],
    *,
    dynamic_changes: str,
    artifacts: list[dict[str, object]],
    guidance: dict[str, str],
    gate_details: dict[str, object] | None,
    receipt_path: Path,
    summary_path: Path,
) -> WindowsOpsTerminalRecipeCompletion:
    """Normalize a terminal recipe completion into launcher state and event payloads."""

    action = str(payload.get("action", "") or "").strip().lower()
    label = str(payload.get("label", "") or "").strip()
    ok = bool(payload.get("ok", False))
    completed_steps = int(payload.get("steps_completed", 0) or 0)
    total_steps = int(payload.get("steps_total", 0) or 0)
    status_word = "completed" if ok else "failed"
    summary = (
        f"{label} {status_word} {completed_steps}/{total_steps} servicing step(s)."
        if label
        else f"{action.replace('_', ' ')} {status_word} {completed_steps}/{total_steps} servicing step(s)."
    )
    changes = str(payload.get("changes", "") or "").strip()
    normalized_gate = normalize_windows_gate_details(gate_details)
    if dynamic_changes:
        changes = f"{changes} | {dynamic_changes}" if changes else dynamic_changes
    gate_detail = str(normalized_gate.get("detail", "") or "").strip()
    if gate_detail:
        changes = f"{changes} | {gate_detail}" if changes else gate_detail
    commands = [str(item).strip() for item in payload.get("commands", []) if str(item).strip()] if isinstance(payload.get("commands"), list) else []
    recommendation_details = [
        item for item in normalized_gate.get("recommendation_details", []) if isinstance(item, dict)
    ]
    first_recommendation = recommendation_details[0] if recommendation_details else {}
    state_record = WindowsOpsStateRecord(
        action=action,
        summary=summary,
        changes=changes,
        ok=ok,
        commands=commands,
        event_id=str(payload.get("id", "") or "").strip(),
        steps_completed=completed_steps,
        steps_total=total_steps,
        phase="completed",
        next_step=str(guidance.get("next_step", "") or ""),
        fix_target=str(guidance.get("fix_target", "") or ""),
        docs_hint=str(guidance.get("docs_hint", "") or ""),
        entry_point=str(guidance.get("entry_point", "") or ""),
        artifacts=artifacts,
        gate_summary=str(normalized_gate.get("summary", "") or ""),
        gate_detail=gate_detail,
        gate_checks=[item for item in normalized_gate.get("checks", []) if isinstance(item, dict)],
        gate_required_files=[item for item in normalized_gate.get("required_files", []) if isinstance(item, dict)],
        gate_failed_checks=[str(item).strip() for item in normalized_gate.get("failed_checks", []) if str(item).strip()],
        gate_missing_files=[str(item).strip() for item in normalized_gate.get("missing_files", []) if str(item).strip()],
        gate_passed_checks=normalized_gate.get("passed_checks"),
        gate_total_checks=normalized_gate.get("total_checks"),
        gate_recommendations=[
            str(item).strip() for item in normalized_gate.get("recommendations", []) if str(item).strip()
        ],
        gate_recommendation_details=recommendation_details,
    )
    event_fields = {
        "action": action,
        "ok": ok,
        "steps_completed": completed_steps,
        "steps_total": total_steps,
        "summary": summary,
        "event_id": state_record.event_id,
        "next_step": state_record.next_step,
        "fix_target": state_record.fix_target,
        "artifacts": artifacts,
        "release_receipt": str(receipt_path),
        "release_summary": str(summary_path),
        "gate_summary": state_record.gate_summary,
        "gate_detail": gate_detail,
        "gate_failed_checks": list(state_record.gate_failed_checks or []),
        "gate_missing_files": list(state_record.gate_missing_files or []),
        "gate_passed_checks": state_record.gate_passed_checks,
        "gate_total_checks": state_record.gate_total_checks,
        "gate_recommendations": list(state_record.gate_recommendations or []),
        "gate_fix_target": str(first_recommendation.get("fix_target", "") or "").strip(),
        "gate_fix_docs": str(first_recommendation.get("docs_hint", "") or "").strip(),
        "gate_fix_command": str(first_recommendation.get("entry_point", "") or "").strip(),
    }
    return WindowsOpsTerminalRecipeCompletion(
        summary=summary,
        state_record=state_record,
        event_fields=event_fields,
    )
