from __future__ import annotations

import json
from pathlib import Path

from src.guppy.launcher_application.windows_ops_presenter import artifact_display_path


def event_level(item: dict[str, object]) -> str:
    event = str(item.get("event", "") or "").lower()
    summary = json.dumps(item, ensure_ascii=True).lower()
    if "error" in event or "error" in summary or "failed" in summary:
        return "ERROR"
    if "warn" in event or "warning" in summary or "over_budget" in event:
        return "WARN"
    return "INFO"


def read_launcher_events(root: Path, *, limit: int = 120) -> list[dict[str, object]]:
    path = root / "runtime" / "launcher_events.jsonl"
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    items: list[dict[str, object]] = []
    for line in lines[-limit:]:
        txt = line.strip()
        if not txt:
            continue
        try:
            obj = json.loads(txt)
        except Exception:
            continue
        if isinstance(obj, dict):
            items.append(obj)
    return items


def build_operator_log_lines(
    items: list[dict[str, object]],
    *,
    log_filter: str,
    root: Path,
) -> list[str]:
    lines: list[str] = []
    for item in items:
        level = event_level(item)
        if log_filter != "ALL" and level != log_filter:
            continue
        ts = str(item.get("ts", ""))
        event = str(item.get("event", "event"))
        detail = _event_detail(item, root=root)
        lines.append(f"[{level}] {ts} {event}" + (f" :: {detail}" if detail else ""))
    return lines


def _event_detail(item: dict[str, object], *, root: Path) -> str:
    event = str(item.get("event", "event"))
    if event in {"recovery_result", "recovery_error"}:
        return str(item.get("summary", ""))
    if event == "auth_retry_result":
        return str(item.get("error", "ok"))
    if event == "ui_poll_over_budget":
        return f"poll_ms={item.get('poll_ms', '?')}"
    if event == "startup_phase_over_budget":
        return f"phase={item.get('phase', '?')} duration={item.get('duration_ms', '?')}ms"
    if event == "connector_action_result":
        return _connector_action_detail(item)
    if event in {"windows_ops_action", "windows_ops_completed"}:
        return _windows_ops_detail(item, root=root)
    return ""


def _connector_action_detail(item: dict[str, object]) -> str:
    connector = str(item.get("connector", "") or "").strip() or "connector"
    action = str(item.get("action", "") or "").strip() or "action"
    result = "OK" if bool(item.get("ok", False)) else "FAIL"
    ref = str(item.get("event_id", "") or "").strip()
    provider = str(item.get("provider", "") or "").strip()
    account_id = str(item.get("account_id", "") or "").strip()
    summary = str(item.get("summary", "") or "").strip()
    result_code = str(item.get("result_code", "") or "").strip()
    next_step = str(item.get("next_step", "") or "").strip()
    bits = [f"{connector}.{action}", result]
    if ref:
        bits.append(f"ref={ref}")
    if result_code:
        bits.append(f"code={result_code}")
    if provider:
        bits.append(f"provider={provider}")
    if account_id:
        bits.append(f"account={account_id}")
    detail = " | ".join(bits)
    if summary:
        detail += f" | {summary}"
    if next_step:
        detail += f" | next={next_step}"
    return detail


def _windows_ops_detail(item: dict[str, object], *, root: Path) -> str:
    action = str(item.get("action", "") or "").strip() or "windows_ops"
    queued = item.get("queued")
    ok = item.get("ok")
    steps_completed = str(item.get("steps_completed", "") or "").strip()
    steps_total = str(item.get("steps_total", "") or "").strip()
    summary = str(item.get("summary", "") or "").strip()
    event_id = str(item.get("event_id", "") or "").strip()
    next_step = str(item.get("next_step", "") or "").strip()
    fix_target = str(item.get("fix_target", "") or "").strip()
    gate_summary = str(item.get("gate_summary", "") or "").strip()
    gate_detail = str(item.get("gate_detail", "") or "").strip()
    gate_failed_checks = _string_list(item.get("gate_failed_checks"))
    gate_missing_files = _string_list(item.get("gate_missing_files"))
    gate_passed_checks = str(item.get("gate_passed_checks", "") or "").strip()
    gate_total_checks = str(item.get("gate_total_checks", "") or "").strip()
    gate_recommendations = _string_list(item.get("gate_recommendations"))
    gate_recommendation_details = (
        [row for row in item.get("gate_recommendation_details", []) if isinstance(row, dict)]
        if isinstance(item.get("gate_recommendation_details"), list)
        else []
    )
    bits = [action]
    if queued is not None:
        bits.append("QUEUED" if bool(queued) else "QUEUE_FAIL")
    if ok is not None:
        bits.append("OK" if bool(ok) else "FAIL")
    if steps_completed and steps_total:
        bits.append(f"steps={steps_completed}/{steps_total}")
    if event_id:
        bits.append(f"ref={event_id}")
    if fix_target:
        bits.append(f"fix={fix_target}")
    receipt_path = artifact_display_path(str(item.get("release_receipt", "") or ""), root=root)
    summary_path = artifact_display_path(str(item.get("release_summary", "") or ""), root=root)
    artifacts = [row for row in item.get("artifacts", []) if isinstance(row, dict)] if isinstance(item.get("artifacts"), list) else []
    artifact_refs: list[str] = []
    for artifact in artifacts[:3]:
        label = str(artifact.get("id", "") or artifact.get("label", "") or "artifact").strip()
        path = artifact_display_path(str(artifact.get("path", "") or ""), root=root)
        if label and path:
            artifact_refs.append(f"{label}={path}")
    detail = " | ".join(bits)
    if summary:
        detail += f" | {summary}"
    if next_step:
        detail += f" | next={next_step}"
    if gate_summary:
        detail += f" | gate={gate_summary}"
        if gate_detail:
            detail += f" | gate_detail={gate_detail}"
        if gate_passed_checks and gate_total_checks:
            detail += f" | gate_checks={gate_passed_checks}/{gate_total_checks}"
        if gate_failed_checks:
            detail += f" | gate_failed={','.join(gate_failed_checks[:3])}"
        if gate_missing_files:
            rendered_missing = ",".join(Path(path).name or path for path in gate_missing_files[:3])
            detail += f" | gate_missing={rendered_missing}"
        if gate_recommendations:
            detail += f" | gate_fix={'; '.join(gate_recommendations[:2])}"
        if gate_recommendation_details:
            first_fix = gate_recommendation_details[0]
            fix_target = str(first_fix.get("fix_target", "") or "").strip()
            fix_docs = str(first_fix.get("docs_hint", "") or "").strip()
            fix_command = str(first_fix.get("entry_point", "") or "").strip()
            if fix_target:
                detail += f" | gate_fix_target={fix_target}"
            if fix_docs:
                detail += f" | gate_fix_doc={fix_docs}"
            if fix_command:
                detail += f" | gate_fix_cmd={fix_command}"
    if receipt_path:
        detail += f" | receipt={receipt_path}"
    if summary_path:
        detail += f" | summary={summary_path}"
    if artifact_refs:
        detail += f" | handoff={', '.join(artifact_refs)}"
    return detail


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(row).strip() for row in value if str(row).strip()]
