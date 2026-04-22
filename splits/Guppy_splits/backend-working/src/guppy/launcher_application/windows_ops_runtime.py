"""Windows Ops runtime, receipt, and servicing-result helpers."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def default_windows_ops_event_id(action: str) -> str:
    normalized = str(action or "").strip().lower().replace("_", "-") or "windows-ops"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{normalized}-{timestamp}"


def beta_release_dry_run_report_path(runtime_root: Path) -> Path:
    return runtime_root / "beta_release_dry_run_report.json"


def repo_python_path(runtime_root: Path, *, fallback_executable: str = "") -> Path:
    repo_root = runtime_root.parent
    candidates = [
        repo_root / ".venv" / "Scripts" / "python.exe",
        repo_root / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return Path(fallback_executable or sys.executable)


def run_repo_python(
    runtime_root: Path,
    args: list[str],
    *,
    timeout_s: float = 45.0,
    fallback_executable: str = "",
) -> str:
    python_path = repo_python_path(runtime_root, fallback_executable=fallback_executable)
    try:
        proc = subprocess.run(
            [str(python_path), *args],
            cwd=str(runtime_root.parent),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
        )
    except Exception as exc:
        return f"error:{exc}"
    text = (proc.stdout or "").strip() or (proc.stderr or "").strip()
    if proc.returncode != 0:
        return f"error:{text or proc.returncode}"
    return text


def snapshot_file_signature(path: Path | None) -> dict[str, object]:
    target = path if isinstance(path, Path) else None
    if target is None or not target.exists():
        return {"path": str(target) if target is not None else "", "exists": False, "mtime": "", "size": 0}
    stat = target.stat()
    return {
        "path": str(target),
        "exists": True,
        "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "size": int(stat.st_size),
    }


def latest_runtime_artifact(runtime_root: Path, *patterns: str) -> Path | None:
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(runtime_root.glob(pattern))
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def preferred_package_output(runtime_root: Path) -> Path:
    repo_root = runtime_root.parent
    for candidate in (
        repo_root / "dist" / "Guppy" / "Guppy.exe",
        repo_root / "dist" / "Guppy.exe",
        repo_root / "dist" / "Guppy",
    ):
        if candidate.exists():
            return candidate
    return repo_root / "dist" / "Guppy.exe"


def collect_windows_service_snapshot(
    runtime_root: Path,
    *,
    fallback_executable: str = "",
) -> dict[str, object]:
    return {
        "python_path": str(repo_python_path(runtime_root, fallback_executable=fallback_executable)),
        "python_version": run_repo_python(runtime_root, ["--version"], timeout_s=15.0, fallback_executable=fallback_executable),
        "pip_version": run_repo_python(runtime_root, ["-m", "pip", "--version"], timeout_s=25.0, fallback_executable=fallback_executable),
        "challenger_snapshot": snapshot_file_signature(runtime_root / "runtime_challenger_snapshot.json"),
        "diagnostics_bundle": snapshot_file_signature(
            latest_runtime_artifact(runtime_root, "diagnostics_bundle_*.json", "diagnostics_*.json")
        ),
        "pilot_exit_report": snapshot_file_signature(runtime_root / "pilot_exit_report.json"),
        "beta_policy_report": snapshot_file_signature(runtime_root / "beta_policy_report.json"),
        "beta_release_dry_run_report": snapshot_file_signature(beta_release_dry_run_report_path(runtime_root)),
        "package_output": snapshot_file_signature(preferred_package_output(runtime_root)),
    }


def windows_service_snapshot_changes(before: dict[str, object], after: dict[str, object]) -> str:
    if not isinstance(before, dict) or not isinstance(after, dict):
        return ""
    bits: list[str] = []
    before_pip = str(before.get("pip_version", "") or "").strip()
    after_pip = str(after.get("pip_version", "") or "").strip()
    if before_pip and after_pip and before_pip != after_pip:
        bits.append(f"pip changed: {before_pip} -> {after_pip}")
    before_python = str(before.get("python_version", "") or "").strip()
    after_python = str(after.get("python_version", "") or "").strip()
    if before_python and after_python and before_python != after_python:
        bits.append(f"python changed: {before_python} -> {after_python}")
    for key, label in (
        ("challenger_snapshot", "challenger snapshot refreshed"),
        ("diagnostics_bundle", "diagnostics bundle refreshed"),
        ("pilot_exit_report", "pilot exit report refreshed"),
        ("beta_policy_report", "beta policy report refreshed"),
        ("beta_release_dry_run_report", "beta release dry-run report refreshed"),
        ("package_output", "desktop package refreshed"),
    ):
        previous = before.get(key, {})
        current = after.get(key, {})
        if not isinstance(previous, dict) or not isinstance(current, dict):
            continue
        if bool(current.get("exists")) and (
            str(previous.get("path", "") or "").strip() != str(current.get("path", "") or "").strip()
            or str(previous.get("mtime", "") or "").strip() != str(current.get("mtime", "") or "").strip()
            or int(previous.get("size", 0) or 0) != int(current.get("size", 0) or 0)
        ):
            bits.append(label)
    if not bits:
        return "No file-backed servicing delta was detected beyond command completion."
    return " | ".join(bits)


def windows_ops_artifact_refs(action: str, snapshot: dict[str, object]) -> list[dict[str, object]]:
    if not isinstance(snapshot, dict):
        return []
    normalized = str(action or "").strip().lower()
    requested: list[tuple[str, str, str]] = []
    if normalized in {"verify_runtime", "update_runtime", "repair_runtime", "restart_runtime"}:
        requested.extend(
            [
                ("diagnostics_bundle", "diagnostics", "diagnostics bundle"),
                ("challenger_snapshot", "challenger", "challenger snapshot"),
                ("pilot_exit_report", "pilot_exit", "pilot exit report"),
            ]
        )
    if normalized == "package_desktop":
        requested.extend(
            [
                ("package_output", "package", "desktop package"),
                ("beta_policy_report", "beta_policy", "beta policy report"),
                ("diagnostics_bundle", "diagnostics", "diagnostics bundle"),
            ]
        )
    if normalized == "release_dry_run":
        requested.extend(
            [
                ("beta_release_dry_run_report", "release_dry_run", "release dry-run report"),
                ("pilot_exit_report", "pilot_exit", "pilot exit report"),
                ("beta_policy_report", "beta_policy", "beta policy report"),
            ]
        )
    if normalized == "start_supervised_api":
        requested.append(("diagnostics_bundle", "diagnostics", "diagnostics bundle"))
    seen: set[str] = set()
    artifacts: list[dict[str, object]] = []
    for key, artifact_id, label in requested:
        if key in seen:
            continue
        seen.add(key)
        item = snapshot.get(key, {})
        if not isinstance(item, dict) or not bool(item.get("exists")):
            continue
        path = str(item.get("path", "") or "").strip()
        if not path:
            continue
        artifacts.append(
            {
                "id": artifact_id,
                "label": label,
                "path": path,
                "mtime": str(item.get("mtime", "") or "").strip(),
                "size": int(item.get("size", 0) or 0),
            }
        )
    return artifacts


def summarize_release_dry_run_report(report: dict[str, object]) -> dict[str, object]:
    if not isinstance(report, dict):
        return {}
    checks = [item for item in report.get("checks", []) if isinstance(item, dict)] if isinstance(report.get("checks"), list) else []
    required_files = [item for item in report.get("required_files", []) if isinstance(item, dict)] if isinstance(report.get("required_files"), list) else []
    passed_checks = sum(1 for item in checks if bool(item.get("ok", False)))
    total_checks = len(checks)
    failed_checks = [
        str(item.get("name", "") or "check").strip()
        for item in checks
        if not bool(item.get("ok", False))
    ]
    missing_files = [
        str(item.get("path", "") or "").strip()
        for item in required_files
        if not bool(item.get("exists", False))
    ]
    ok = bool(report.get("ok", False))
    status = "PASS" if ok else "FAIL"
    summary_bits = [status]
    if total_checks:
        summary_bits.append(f"checks {passed_checks}/{total_checks}")
    if required_files:
        summary_bits.append("required files OK" if not missing_files else f"missing files {len(missing_files)}")
    detail_bits: list[str] = []
    if failed_checks:
        detail_bits.append("failed checks: " + ", ".join(failed_checks[:3]))
    if missing_files:
        rendered_missing = ", ".join(Path(path).name or path for path in missing_files[:3])
        detail_bits.append("missing: " + rendered_missing)
    if not detail_bits and ok:
        detail_bits.append("all dry-run checks passed and required handoff files are present")
    recommendations: list[str] = []
    recommendation_details: list[dict[str, str]] = []
    if "beta_policy" in failed_checks:
        text = "Fix the beta policy gate first by rerunning verify_beta_package_policy and reviewing the allowlist/policy docs."
        recommendations.append(text)
        recommendation_details.append(
            {
                "text": text,
                "fix_target": "config/beta_tool_allowlist.txt / docs/REMOTE_BETA_EXE_POLICY.md",
                "docs_hint": "docs/PACKAGING.md",
                "entry_point": "python tools/verify_beta_package_policy.py",
            }
        )
    if "pilot_gate" in failed_checks:
        text = "Fix the pilot gate next by reviewing pilot_exit_check failures and rerunning the release dry-run."
        recommendations.append(text)
        recommendation_details.append(
            {
                "text": text,
                "fix_target": "tools/pilot_exit_check.py / runtime/pilot_exit_report.json",
                "docs_hint": "docs/PACKAGING.md",
                "entry_point": "python tools/pilot_exit_check.py --allow-limited-go",
            }
        )
    for path in missing_files:
        target = Path(path).name or path
        text = f"Restore the required handoff file {target} before the next release dry-run."
        recommendations.append(text)
        recommendation_details.append(
            {
                "text": text,
                "fix_target": str(path),
                "docs_hint": "docs/PACKAGING.md",
                "entry_point": str(path),
            }
        )
    if not recommendations and ok:
        text = "Release gate is green; review the dry-run report, receipt, and summary in that order, then package or hand off the bundle."
        recommendations.append(text)
        recommendation_details.append(
            {
                "text": text,
                "fix_target": "runtime/beta_release_dry_run_report.json -> runtime/windows_release_receipt.json -> runtime/windows_release_summary.md",
                "docs_hint": "docs/PACKAGING.md",
                "entry_point": "python tools/beta_release_dry_run.py",
            }
        )
    return {
        "ok": ok,
        "summary": " | ".join(summary_bits),
        "detail": " | ".join(detail_bits),
        "passed_checks": passed_checks,
        "total_checks": total_checks,
        "failed_checks": failed_checks,
        "missing_files": missing_files,
        "checks": [
            {
                "name": str(item.get("name", "") or "check").strip(),
                "ok": bool(item.get("ok", False)),
                "returncode": int(item.get("returncode", 0) or 0),
            }
            for item in checks
        ],
        "required_files": [
            {
                "path": str(item.get("path", "") or "").strip(),
                "exists": bool(item.get("exists", False)),
            }
            for item in required_files
        ],
        "recommendations": recommendations[:4],
        "recommendation_details": recommendation_details[:4],
    }


def release_dry_run_gate_details(runtime_root: Path) -> dict[str, object]:
    path = beta_release_dry_run_report_path(runtime_root)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    details = summarize_release_dry_run_report(payload if isinstance(payload, dict) else {})
    if not details:
        return {}
    return {**details, "path": str(path)}


def release_review_order(action: str) -> list[str]:
    if str(action or "").strip().lower() == "release_dry_run":
        return [
            "runtime/beta_release_dry_run_report.json",
            "runtime/windows_release_receipt.json",
            "runtime/windows_release_summary.md",
        ]
    return []


def write_windows_release_summary(summary_path: Path, payload: dict[str, object]) -> str:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    release_gate = payload.get("release_gate", {}) if isinstance(payload.get("release_gate"), dict) else {}
    operator_guidance = payload.get("operator_guidance", {}) if isinstance(payload.get("operator_guidance"), dict) else {}
    artifacts = [item for item in payload.get("artifacts", []) if isinstance(item, dict)] if isinstance(payload.get("artifacts"), list) else []
    recommendations = [str(item).strip() for item in release_gate.get("recommendations", []) if str(item).strip()] if isinstance(release_gate.get("recommendations"), list) else []
    recommendation_details = [item for item in release_gate.get("recommendation_details", []) if isinstance(item, dict)] if isinstance(release_gate.get("recommendation_details"), list) else []
    lines = [
        "# Windows Release Summary",
        "",
        f"- Timestamp: {str(payload.get('timestamp', '') or '').strip()}",
        f"- Ref: {str(payload.get('event_id', '') or '').strip()}",
        f"- Stage: {str(payload.get('release_stage', '') or '').strip()}",
        f"- Action: {str(payload.get('action', '') or '').strip()}",
        f"- Result: {'PASS' if bool(payload.get('ok', False)) else 'FAIL'}",
        f"- Summary: {str(payload.get('summary', '') or '').strip()}",
    ]
    lines = [line for line in lines if not line.endswith(": ")]
    changes = str(payload.get("changes", "") or "").strip()
    if changes:
        lines.append(f"- What changed: {changes}")
    gate_summary = str(release_gate.get("summary", "") or "").strip()
    gate_detail = str(release_gate.get("detail", "") or "").strip()
    if gate_summary:
        lines.extend(["", "## Release Gate", "", f"- Verdict: {gate_summary}"])
        if gate_detail:
            lines.append(f"- Detail: {gate_detail}")
        passed = release_gate.get("passed_checks")
        total = release_gate.get("total_checks")
        if passed is not None and total is not None:
            lines.append(f"- Checks: {int(passed or 0)}/{int(total or 0)} passed")
    review_order = (
        [str(item).strip() for item in payload.get("review_order", []) if str(item).strip()]
        if isinstance(payload.get("review_order"), list)
        else []
    )
    if review_order:
        lines.extend(["", "## Review Order", ""])
        for index, item in enumerate(review_order, start=1):
            lines.append(f"{index}. {item}")
    if recommendation_details or recommendations:
        gate_ok = gate_summary.upper().startswith("PASS")
        section_title = "## Next Review Step" if gate_ok else "## Fix-First"
        target_label = "Review" if gate_ok else "Fix in"
        lines.extend(["", section_title, ""])
        if recommendation_details:
            for item in recommendation_details[:3]:
                text = str(item.get("text", "") or "").strip()
                if not text:
                    continue
                lines.append(f"- {text}")
                fix_target = str(item.get("fix_target", "") or "").strip()
                docs_hint = str(item.get("docs_hint", "") or "").strip()
                entry_point = str(item.get("entry_point", "") or "").strip()
                if fix_target:
                    lines.append(f"  {target_label}: {fix_target}")
                if docs_hint:
                    lines.append(f"  Doc: {docs_hint}")
                if entry_point:
                    lines.append(f"  Cmd: {entry_point}")
        else:
            for text in recommendations[:3]:
                lines.append(f"- {text}")
    if artifacts:
        lines.extend(["", "## Artifacts", ""])
        for item in artifacts[:6]:
            label = str(item.get("label", "") or item.get("id", "") or "artifact").strip()
            path = str(item.get("path", "") or "").strip()
            if label and path:
                suffix_bits: list[str] = []
                updated = str(item.get("mtime", "") or "").strip()
                size = int(item.get("size", 0) or 0)
                if updated:
                    suffix_bits.append(f"updated {updated}")
                if size > 0:
                    suffix_bits.append(f"{size} B")
                suffix = f" ({', '.join(suffix_bits)})" if suffix_bits else ""
                lines.append(f"- {label}: {path}{suffix}")
    next_step = str(operator_guidance.get("next_step", "") or "").strip()
    if next_step:
        lines.extend(["", "## Operator Guidance", "", f"- Next step: {next_step}"])
        fix_target = str(operator_guidance.get("fix_target", "") or "").strip()
        docs_hint = str(operator_guidance.get("docs_hint", "") or "").strip()
        entry_point = str(operator_guidance.get("entry_point", "") or "").strip()
        if fix_target:
            lines.append(f"- Fix target: {fix_target}")
        if docs_hint:
            lines.append(f"- Doc: {docs_hint}")
        if entry_point:
            lines.append(f"- Command: {entry_point}")
    summary_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return str(summary_path)


def build_windows_release_receipt_payload(
    state_path: Path,
    receipt_path: Path,
    summary_path: Path,
    action: str,
    summary: str,
    changes: str,
    *,
    ok: bool,
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
    gate_summary: str = "",
    gate_detail: str = "",
    gate_checks: list[dict[str, object]] | None = None,
    gate_required_files: list[dict[str, object]] | None = None,
    gate_failed_checks: list[str] | None = None,
    gate_missing_files: list[str] | None = None,
    gate_passed_checks: int | None = None,
    gate_total_checks: int | None = None,
    gate_recommendations: list[str] | None = None,
    gate_recommendation_details: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    artifact_payload = [
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
    normalized = str(action or "").strip().lower()
    release_stage = "servicing"
    if normalized == "package_desktop":
        release_stage = "package"
    elif normalized == "release_dry_run":
        release_stage = "release_gate"
    elif normalized in {"verify_runtime", "update_runtime"}:
        release_stage = "verification"
    elif normalized == "start_supervised_api":
        release_stage = "supervision"
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "release_stage": release_stage,
        "action": normalized,
        "ok": bool(ok),
        "phase": str(phase or "completed").strip().lower() or "completed",
        "summary": str(summary or "").strip(),
        "changes": str(changes or "").strip(),
        "event_id": str(event_id or "").strip(),
        "steps_completed": int(steps_completed or 0) if steps_completed is not None else None,
        "steps_total": int(steps_total or 0) if steps_total is not None else None,
        "commands": [str(item).strip() for item in (commands or []) if str(item).strip()],
        "artifacts": artifact_payload,
        "operator_guidance": {
            "next_step": str(next_step or "").strip(),
            "fix_target": str(fix_target or "").strip(),
            "docs_hint": str(docs_hint or "").strip(),
            "entry_point": str(entry_point or "").strip(),
        },
        "release_gate": {
            "summary": str(gate_summary or "").strip(),
            "detail": str(gate_detail or "").strip(),
            "passed_checks": int(gate_passed_checks or 0) if gate_passed_checks is not None else None,
            "total_checks": int(gate_total_checks or 0) if gate_total_checks is not None else None,
            "failed_checks": [str(item).strip() for item in (gate_failed_checks or []) if str(item).strip()],
            "missing_files": [str(item).strip() for item in (gate_missing_files or []) if str(item).strip()],
            "checks": [
                {
                    "name": str(item.get("name", "") or "").strip(),
                    "ok": bool(item.get("ok", False)),
                    "returncode": int(item.get("returncode", 0) or 0),
                }
                for item in (gate_checks or [])
                if isinstance(item, dict) and str(item.get("name", "") or "").strip()
            ],
            "required_files": [
                {
                    "path": str(item.get("path", "") or "").strip(),
                    "exists": bool(item.get("exists", False)),
                }
                for item in (gate_required_files or [])
                if isinstance(item, dict) and str(item.get("path", "") or "").strip()
            ],
            "recommendations": [str(item).strip() for item in (gate_recommendations or []) if str(item).strip()],
            "recommendation_details": [
                {
                    "text": str(item.get("text", "") or "").strip(),
                    "fix_target": str(item.get("fix_target", "") or "").strip(),
                    "docs_hint": str(item.get("docs_hint", "") or "").strip(),
                    "entry_point": str(item.get("entry_point", "") or "").strip(),
                }
                for item in (gate_recommendation_details or [])
                if isinstance(item, dict) and str(item.get("text", "") or "").strip()
            ],
        },
        "paths": {
            "state_path": str(state_path),
            "receipt_path": str(receipt_path),
            "summary_path": str(summary_path),
        },
        "review_order": release_review_order(normalized),
    }


def write_windows_release_receipt(
    state_path: Path,
    receipt_path: Path,
    summary_path: Path,
    action: str,
    summary: str,
    changes: str,
    **kwargs: Any,
) -> str:
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_windows_release_receipt_payload(
        state_path,
        receipt_path,
        summary_path,
        action,
        summary,
        changes,
        **kwargs,
    )
    receipt_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_windows_release_summary(summary_path, payload)
    return str(receipt_path)

