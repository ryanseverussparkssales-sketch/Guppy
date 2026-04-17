"""Pure summary/render helpers for the App Mgmt Windows Ops panel."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True, slots=True)
class WindowsOpsPanelState:
    """Renderable copy for the Windows Ops labels shown in App Mgmt."""

    install_text: str
    runtime_text: str
    paths_text: str
    repair_text: str
    update_text: str
    diagnostics_text: str
    entry_text: str
    next_text: str
    service_text: str
    changes_text: str
    gate_text: str
    gate_followup_text: str
    handoff_text: str


def _pipe_fields(raw: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for part in str(raw or "").split("|"):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        normalized_key = str(key or "").strip().lower()
        normalized_value = str(value or "").strip()
        if normalized_key and normalized_value:
            fields[normalized_key] = normalized_value
    return fields


def artifact_display_path(path: str, *, root: Path | None = None) -> str:
    raw = str(path or "").strip()
    if not raw:
        return ""
    target = Path(raw)
    base = root or _ROOT
    try:
        return str(target.resolve().relative_to(base)).replace("\\", "/")
    except Exception:
        return raw.replace("\\", "/")


def release_gate_is_green(gate_summary: str) -> bool:
    return str(gate_summary or "").strip().upper().startswith("PASS")


def build_windows_handoff_line(
    artifacts: list[dict[str, Any]] | None,
    *,
    receipt_path: str = "",
    summary_path: str = "",
    review_order: list[str] | None = None,
    root: Path | None = None,
) -> str:
    rendered: list[str] = []
    receipt = artifact_display_path(receipt_path, root=root)
    summary = artifact_display_path(summary_path, root=root)
    review_items = [str(item).strip() for item in (review_order or []) if str(item).strip()]
    if review_items:
        rendered.append(f"review order={' -> '.join(review_items)}")
    if receipt:
        rendered.append(f"receipt={receipt}")
    if summary:
        rendered.append(f"summary={summary}")
    for item in artifacts or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "") or item.get("id", "") or "artifact").strip()
        path = artifact_display_path(str(item.get("path", "") or ""), root=root)
        if not path:
            continue
        rendered.append(f"{label}={path}")
    if not rendered:
        return (
            "Files to share: run RELEASE DRY RUN first, then share the dry-run report, receipt, and summary in that order."
        )
    return "Files to share: " + " | ".join(rendered[:4])


def build_windows_gate_followup_line(
    gate_summary: str,
    gate_recommendations: list[str] | None,
    gate_recommendation_details: list[dict[str, object]] | None,
) -> str:
    rendered_recommendations = [str(item).strip() for item in (gate_recommendations or []) if str(item).strip()]
    rendered_recommendation_details = [item for item in (gate_recommendation_details or []) if isinstance(item, dict)]
    primary_gate_fix = rendered_recommendation_details[0] if rendered_recommendation_details else {}
    gate_ok = release_gate_is_green(gate_summary)
    prefix = "Review next" if gate_ok else "Fix first" if str(gate_summary or "").strip() else "Release follow-up"
    target_label = "Review" if gate_ok else "Fix in"
    body = (
        (
            str(primary_gate_fix.get("text", "") or "").strip()
            + (
                f" | {target_label}: {str(primary_gate_fix.get('fix_target', '') or '').strip()}"
                if str(primary_gate_fix.get("fix_target", "") or "").strip()
                else ""
            )
            + (
                f" | Doc: {str(primary_gate_fix.get('docs_hint', '') or '').strip()}"
                if str(primary_gate_fix.get("docs_hint", "") or "").strip()
                else ""
            )
            + (
                f" | Cmd: {str(primary_gate_fix.get('entry_point', '') or '').strip()}"
                if str(primary_gate_fix.get("entry_point", "") or "").strip()
                else ""
            )
        )
        if primary_gate_fix
        else " | ".join(rendered_recommendations[:2])
        if rendered_recommendations
        else "no release-check recommendations recorded yet."
    )
    return f"{prefix}: {body}"


def build_windows_ops_panel_state(snapshot: Mapping[str, str] | None) -> WindowsOpsPanelState:
    raw_snapshot = dict(snapshot or {})
    install_raw = str(raw_snapshot.get("install", "") or "")
    runtime_raw = str(raw_snapshot.get("runtime", "") or "")
    next_raw = str(raw_snapshot.get("next", "") or "")
    service_raw = str(raw_snapshot.get("service", "") or "")
    change_raw = str(raw_snapshot.get("changes", "") or "")
    gate_raw = str(raw_snapshot.get("gate", "") or "")
    gate_fix_raw = str(raw_snapshot.get("gate_fix", "") or "")
    handoff_raw = str(raw_snapshot.get("handoff", "") or "")
    install_bits: list[str] = []
    if "Ollama CLI: found" in install_raw:
        install_bits.append("Ollama")
    if "Lemonade CLI: found" in install_raw:
        install_bits.append("Lemonade")
    if "Supervisor script: ready" in install_raw:
        install_bits.append("supervised launch")
    if "Packager: ready" in install_raw:
        install_bits.append("desktop packaging")
    runtime_fields = _pipe_fields(runtime_raw)
    configured = runtime_fields.get("local ai runtime", "local ai")
    live_backend = runtime_fields.get("live backend", configured)
    state = runtime_fields.get("status", "unknown").lower()
    if state == "ready":
        runtime_text = f"Local AI health: {live_backend.title()} is connected and ready."
    elif state == "unknown":
        runtime_text = f"Local AI health: {configured.title()} is selected, but it has not been confirmed yet."
    else:
        runtime_text = f"Local AI health: {configured.title()} needs attention."
    return WindowsOpsPanelState(
        install_text="Ready on this PC: " + (", ".join(install_bits) if install_bits else "Core launcher tools found."),
        runtime_text=runtime_text,
        paths_text="Saved data: runtime, config, and settings are available on this PC.",
        repair_text="Repair tip: Use Repair if sign-in, startup, or local runtime checks fail.",
        update_text="Update path: Update refreshes dependencies, then runs the built-in post-update checks.",
        diagnostics_text="Diagnostics: launcher logs and the latest diagnostic bundle are available for troubleshooting.",
        entry_text="Useful actions: Package makes a shareable desktop build, and Start API safely restarts the background service.",
        next_text=(next_raw or "Next step: unavailable").replace("Recommended next step:", "Next step:"),
        service_text=service_raw or "Recent service action: unavailable",
        changes_text=change_raw or "Recent changes: unavailable",
        gate_text=gate_raw or "Release check: unavailable",
        gate_followup_text=gate_fix_raw or "Release follow-up: unavailable",
        handoff_text=handoff_raw or "Files to share: unavailable",
    )


def apply_windows_ops_feedback(
    snapshot: Mapping[str, str] | None,
    *,
    action: str,
    summary: str,
    changes: str,
    ok: bool = True,
    next_step: str = "",
    fix_target: str = "",
    docs_hint: str = "",
    entry_point: str = "",
    artifacts: list[dict[str, object]] | None = None,
    receipt_path: str = "",
    summary_path: str = "",
    gate_summary: str = "",
    gate_detail: str = "",
    gate_recommendations: list[str] | None = None,
    gate_recommendation_details: list[dict[str, object]] | None = None,
    review_order: list[str] | None = None,
    root: Path | None = None,
) -> dict[str, str]:
    updated = dict(snapshot or {})
    updated["service"] = f"Recent service action: {action} | {'OK' if ok else 'CHECK'} | {summary}"
    updated["changes"] = f"Recent changes: {changes}"
    updated["gate"] = "Release check: " + (
        str(gate_summary or "").strip()
        + (f" | {str(gate_detail or '').strip()}" if str(gate_detail or "").strip() else "")
        if str(gate_summary or "").strip()
        else "no dry-run result recorded yet."
    )
    updated["gate_fix"] = build_windows_gate_followup_line(
        str(gate_summary or "").strip(),
        gate_recommendations,
        gate_recommendation_details,
    )
    updated["handoff"] = build_windows_handoff_line(
        artifacts,
        receipt_path=receipt_path,
        summary_path=summary_path,
        review_order=review_order,
        root=root,
    )
    if next_step:
        updated["next"] = (
            "Next step: "
            + next_step
            + (f" | Fix in: {fix_target}" if fix_target else "")
            + (f" | Doc: {docs_hint}" if docs_hint else "")
            + (f" | Command: {entry_point}" if entry_point else "")
        )
    return updated
