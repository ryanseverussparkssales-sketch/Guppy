"""State and chain helpers for launcher Windows Ops orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True, slots=True)
class WindowsOpsChainResult:
    """Normalized chain progression result for multi-step Windows Ops actions."""

    matched: bool
    completed: bool
    next_chain: dict[str, object] | None
    parent_action: str = ""
    overall_ok: bool = False
    summary_text: str = ""
    change_text: str = ""
    steps_completed: int = 0
    steps_total: int = 0


def start_windows_ops_chain(
    action: str,
    expected_steps: list[str] | tuple[str, ...] | None,
    changes: str,
) -> dict[str, object] | None:
    rendered_steps = [str(item).strip().lower() for item in (expected_steps or []) if str(item).strip()]
    if not rendered_steps:
        return None
    return {
        "action": str(action or "").strip().lower(),
        "expected_steps": rendered_steps,
        "results": [],
        "changes": str(changes or "").strip(),
    }


def advance_windows_ops_chain(
    chain: dict[str, object] | None,
    action: str,
    *,
    ok: bool,
    summary: str,
) -> WindowsOpsChainResult:
    if not isinstance(chain, dict):
        return WindowsOpsChainResult(matched=False, completed=False, next_chain=chain)
    normalized_action = str(action or "").strip().lower()
    expected = [str(item).strip().lower() for item in chain.get("expected_steps", []) if str(item).strip()]
    if normalized_action not in expected:
        return WindowsOpsChainResult(matched=False, completed=False, next_chain=chain)
    results = chain.get("results", [])
    if not isinstance(results, list):
        results = []
    results.append(
        {
            "action": normalized_action,
            "ok": bool(ok),
            "summary": str(summary or "").strip(),
        }
    )
    updated_chain = dict(chain)
    updated_chain["results"] = results
    if len(results) < len(expected):
        return WindowsOpsChainResult(
            matched=True,
            completed=False,
            next_chain=updated_chain,
            parent_action=str(updated_chain.get("action", normalized_action) or normalized_action),
            steps_completed=len(results),
            steps_total=len(expected),
        )
    parent_action = str(updated_chain.get("action", normalized_action) or normalized_action)
    rendered = " | ".join(
        f"{str(item.get('action', 'step') or 'step')}={'OK' if bool(item.get('ok', False)) else 'FAIL'}"
        for item in results
        if isinstance(item, dict)
    )
    summary_text = f"{parent_action.replace('_', ' ')} completed | {rendered}"
    change_text = str(updated_chain.get("changes", "") or "").strip()
    final_detail = next(
        (
            str(item.get("summary", "") or "").strip()
            for item in reversed(results)
            if isinstance(item, dict) and str(item.get("summary", "") or "").strip()
        ),
        "",
    )
    if final_detail:
        change_text = f"{change_text} Last result: {final_detail}" if change_text else f"Last result: {final_detail}"
    return WindowsOpsChainResult(
        matched=True,
        completed=True,
        next_chain=None,
        parent_action=parent_action,
        overall_ok=all(bool(item.get("ok", False)) for item in results if isinstance(item, dict)),
        summary_text=summary_text,
        change_text=change_text,
        steps_completed=len(results),
        steps_total=len(expected),
    )


def normalize_windows_ops_artifacts(artifacts: list[dict[str, object]] | None) -> list[dict[str, object]]:
    return [
        {
            "id": str(item.get("id", "") or "").strip(),
            "label": str(item.get("label", "") or "").strip(),
            "path": str(item.get("path", "") or "").strip(),
            "mtime": str(item.get("mtime", "") or "").strip(),
            "size": int(item.get("size", 0) or 0),
        }
        for item in (artifacts or [])
        if isinstance(item, dict) and str(item.get("path", "") or "").strip()
    ]


def normalize_windows_gate_recommendation_details(
    details: list[dict[str, object]] | None,
) -> list[dict[str, str]]:
    return [
        {
            "text": str(item.get("text", "") or "").strip(),
            "fix_target": str(item.get("fix_target", "") or "").strip(),
            "docs_hint": str(item.get("docs_hint", "") or "").strip(),
            "entry_point": str(item.get("entry_point", "") or "").strip(),
        }
        for item in (details or [])
        if isinstance(item, dict) and str(item.get("text", "") or "").strip()
    ]


def normalize_windows_gate_details(gate_details: dict[str, object] | None) -> dict[str, object]:
    raw = gate_details if isinstance(gate_details, dict) else {}
    return {
        "summary": str(raw.get("summary", "") or "").strip(),
        "detail": str(raw.get("detail", "") or "").strip(),
        "checks": [item for item in raw.get("checks", []) if isinstance(item, dict)] if isinstance(raw.get("checks"), list) else [],
        "required_files": [item for item in raw.get("required_files", []) if isinstance(item, dict)] if isinstance(raw.get("required_files"), list) else [],
        "failed_checks": [str(item).strip() for item in raw.get("failed_checks", []) if str(item).strip()] if isinstance(raw.get("failed_checks"), list) else [],
        "missing_files": [str(item).strip() for item in raw.get("missing_files", []) if str(item).strip()] if isinstance(raw.get("missing_files"), list) else [],
        "passed_checks": int(raw.get("passed_checks", 0) or 0) if raw.get("passed_checks") is not None else None,
        "total_checks": int(raw.get("total_checks", 0) or 0) if raw.get("total_checks") is not None else None,
        "recommendations": [str(item).strip() for item in raw.get("recommendations", []) if str(item).strip()] if isinstance(raw.get("recommendations"), list) else [],
        "recommendation_details": normalize_windows_gate_recommendation_details(
            raw.get("recommendation_details", []) if isinstance(raw.get("recommendation_details"), list) else []
        ),
    }


def build_windows_ops_state_payload(
    *,
    action: str,
    ok: bool,
    summary: str,
    changes: str,
    commands: list[str] | None = None,
    event_id: str = "",
    steps_completed: int | None = None,
    steps_total: int | None = None,
    phase: str = "completed",
    next_step: str = "",
    fix_target: str = "",
    docs_hint: str = "",
    entry_point: str = "",
    artifacts: list[dict[str, object]] | None = None,
    release_receipt: str = "",
    release_summary: str = "",
    gate_summary: str = "",
    gate_detail: str = "",
    gate_failed_checks: list[str] | None = None,
    gate_missing_files: list[str] | None = None,
    gate_passed_checks: int | None = None,
    gate_total_checks: int | None = None,
    gate_recommendations: list[str] | None = None,
    gate_recommendation_details: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": str(action or "").strip().lower(),
        "ok": bool(ok),
        "summary": str(summary or "").strip(),
        "changes": str(changes or "").strip(),
        "commands": [str(item).strip() for item in (commands or []) if str(item).strip()],
        "event_id": str(event_id or "").strip(),
        "steps_completed": int(steps_completed or 0) if steps_completed is not None else None,
        "steps_total": int(steps_total or 0) if steps_total is not None else None,
        "phase": str(phase or "completed").strip().lower() or "completed",
        "next_step": str(next_step or "").strip(),
        "fix_target": str(fix_target or "").strip(),
        "docs_hint": str(docs_hint or "").strip(),
        "entry_point": str(entry_point or "").strip(),
        "artifacts": normalize_windows_ops_artifacts(artifacts),
        "release_receipt": str(release_receipt or "").strip(),
        "release_summary": str(release_summary or "").strip(),
        "gate_summary": str(gate_summary or "").strip(),
        "gate_detail": str(gate_detail or "").strip(),
        "gate_failed_checks": [str(item).strip() for item in (gate_failed_checks or []) if str(item).strip()],
        "gate_missing_files": [str(item).strip() for item in (gate_missing_files or []) if str(item).strip()],
        "gate_passed_checks": int(gate_passed_checks or 0) if gate_passed_checks is not None else None,
        "gate_total_checks": int(gate_total_checks or 0) if gate_total_checks is not None else None,
        "gate_recommendations": [str(item).strip() for item in (gate_recommendations or []) if str(item).strip()],
        "gate_recommendation_details": normalize_windows_gate_recommendation_details(gate_recommendation_details),
    }


def build_windows_ops_feedback_kwargs(
    payload: dict[str, object],
    *,
    review_order: list[str] | None = None,
) -> dict[str, object]:
    summary = str(payload.get("summary", "") or "").strip()
    event_id = str(payload.get("event_id", "") or "").strip()
    changes = str(payload.get("changes", "") or "").strip()
    steps_completed = payload.get("steps_completed")
    steps_total = payload.get("steps_total")
    rendered_changes = changes + (
        f" | Steps: {int(steps_completed or 0)}/{int(steps_total or 0)}"
        if steps_completed is not None and steps_total is not None
        else ""
    )
    rendered_summary = summary + (f" | Ref: {event_id}" if event_id else "")
    return {
        "summary": rendered_summary,
        "changes": rendered_changes,
        "ok": bool(payload.get("ok", False)),
        "next_step": str(payload.get("next_step", "") or "").strip(),
        "fix_target": str(payload.get("fix_target", "") or "").strip(),
        "docs_hint": str(payload.get("docs_hint", "") or "").strip(),
        "entry_point": str(payload.get("entry_point", "") or "").strip(),
        "artifacts": normalize_windows_ops_artifacts(payload.get("artifacts", [])),
        "receipt_path": str(payload.get("release_receipt", "") or "").strip(),
        "summary_path": str(payload.get("release_summary", "") or "").strip(),
        "gate_summary": str(payload.get("gate_summary", "") or "").strip(),
        "gate_detail": str(payload.get("gate_detail", "") or "").strip(),
        "gate_recommendations": [str(item).strip() for item in payload.get("gate_recommendations", []) if str(item).strip()] if isinstance(payload.get("gate_recommendations"), list) else [],
        "gate_recommendation_details": normalize_windows_gate_recommendation_details(
            payload.get("gate_recommendation_details", []) if isinstance(payload.get("gate_recommendation_details"), list) else []
        ),
        "review_order": [str(item).strip() for item in (review_order or []) if str(item).strip()],
    }
