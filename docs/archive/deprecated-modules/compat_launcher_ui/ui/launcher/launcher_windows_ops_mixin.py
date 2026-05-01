from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

from src.guppy.launcher_application import (
    beta_release_dry_run_report_path,
    build_windows_ops_descriptor,
    collect_windows_service_snapshot,
    default_windows_ops_event_id,
    release_dry_run_gate_details,
    repo_python_path,
    run_repo_python,
    snapshot_file_signature,
    summarize_release_dry_run_report,
    summarize_windows_recipe_result,
    windows_ops_artifact_refs,
    windows_ops_chain_changes,
    windows_ops_guidance,
    windows_service_snapshot_changes,
    workspace_first_run_recipe,
    workspace_onboarding_ready_message,
    workspace_role_label,
    write_windows_release_receipt,
    write_windows_release_summary,
)
from src.guppy.launcher_application.windows_ops_coordination import (
    WindowsOpsStateRecord,
    complete_windows_ops_terminal_recipe,
    persist_windows_ops_state,
)
from src.guppy.launcher_application.windows_ops_request_flow import (
    start_windows_ops_chain_request,
    update_windows_ops_chain_request,
)
from src.guppy.launcher_application.storage_io import write_json_atomic
from src.guppy.runtime_application import route_evidence_summary

_RUNTIME = Path(__file__).resolve().parent.parent.parent / "runtime"


def _compat_module_value(owner, name: str, default):
    import sys as _sys

    module = _sys.modules.get(owner.__class__.__module__)
    if module is not None and hasattr(module, name):
        return getattr(module, name)
    launcher_module = _sys.modules.get("ui.launcher.launcher_window")
    if launcher_module is not None and hasattr(launcher_module, name):
        return getattr(launcher_module, name)
    return default


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not write_json_atomic(path, payload):
        raise OSError(f"Atomic write failed for {path}")


class LauncherWindowsOpsMixin:
    def _tool_state_path(self) -> Path:
        return _compat_module_value(self, "_RUNTIME", _RUNTIME) / "launcher_tools_state.json"

    def _windows_ops_state_path(self) -> Path:
        return _compat_module_value(self, "_RUNTIME", _RUNTIME) / "windows_ops_state.json"

    def _windows_release_receipt_path(self) -> Path:
        return _compat_module_value(self, "_RUNTIME", _RUNTIME) / "windows_release_receipt.json"

    def _windows_release_summary_path(self) -> Path:
        return _compat_module_value(self, "_RUNTIME", _RUNTIME) / "windows_release_summary.md"

    @staticmethod
    def _default_windows_ops_event_id(action: str) -> str:
        return default_windows_ops_event_id(action)

    def _beta_release_dry_run_report_path(self) -> Path:
        return beta_release_dry_run_report_path(_compat_module_value(self, "_RUNTIME", _RUNTIME))

    @staticmethod
    def _windows_ops_chain_steps(action: str) -> list[str]:
        descriptor = build_windows_ops_descriptor(action)
        return [step.name for step in descriptor.chain_steps if str(step.name).strip()]

    @staticmethod
    def _windows_ops_chain_changes(action: str) -> str:
        return windows_ops_chain_changes(action)

    def _repo_python_path(self) -> Path:
        return repo_python_path(
            _compat_module_value(self, "_RUNTIME", _RUNTIME),
            fallback_executable=sys.executable,
        )

    def _run_repo_python(self, args: list[str], *, timeout_s: float = 45.0) -> str:
        return run_repo_python(
            _compat_module_value(self, "_RUNTIME", _RUNTIME),
            args,
            timeout_s=timeout_s,
            fallback_executable=sys.executable,
        )

    @staticmethod
    def _snapshot_file_signature(path: Path | None) -> dict[str, object]:
        return snapshot_file_signature(path)

    def _latest_runtime_artifact(self, *patterns: str) -> Path | None:
        runtime_dir = _compat_module_value(self, "_RUNTIME", _RUNTIME)
        matches: list[Path] = []
        for pattern in patterns:
            matches.extend(runtime_dir.glob(pattern))
        files = [path for path in matches if path.is_file()]
        if not files:
            return None
        return max(files, key=lambda item: item.stat().st_mtime)

    def _preferred_package_output(self) -> Path:
        return (_compat_module_value(self, "_RUNTIME", _RUNTIME).parent / "dist" / "Guppy" / "Guppy.exe").resolve()

    def _collect_windows_service_snapshot(self) -> dict[str, object]:
        return collect_windows_service_snapshot(
            _compat_module_value(self, "_RUNTIME", _RUNTIME),
            fallback_executable=sys.executable,
        )

    @staticmethod
    def _windows_service_snapshot_changes(before: dict[str, object], after: dict[str, object]) -> str:
        return windows_service_snapshot_changes(before, after)

    @staticmethod
    def _windows_ops_artifact_refs(action: str, snapshot: dict[str, object]) -> list[dict[str, object]]:
        return windows_ops_artifact_refs(action, snapshot)

    @staticmethod
    def _summarize_release_dry_run_report(report: dict[str, object]) -> dict[str, object]:
        return summarize_release_dry_run_report(report)

    @staticmethod
    def _route_evidence_summary(payload: dict[str, object]) -> str:
        launcher_module = sys.modules.get("ui.launcher.launcher_window")
        runtime_path = getattr(launcher_module, "_RUNTIME", _RUNTIME) if launcher_module is not None else _RUNTIME
        return route_evidence_summary(payload, runtime_path=runtime_path)

    @staticmethod
    def _workspace_role_label(workspace_type: str) -> str:
        normalized = str(workspace_type or "user_instance").strip().lower() or "user_instance"
        return {
            "builder_instance": "Builder collaborator workspace",
            "admin_instance": "Operations workspace",
        }.get(normalized, workspace_role_label(workspace_type))

    @staticmethod
    def _workspace_first_run_recipe(workspace_type: str) -> str:
        return workspace_first_run_recipe(workspace_type)

    @staticmethod
    def _workspace_onboarding_ready_message(name: str, workspace_type: str) -> str:
        return workspace_onboarding_ready_message(name, workspace_type)

    def _release_dry_run_gate_details(self) -> dict[str, object]:
        return release_dry_run_gate_details(_compat_module_value(self, "_RUNTIME", _RUNTIME))

    @staticmethod
    def _write_windows_release_summary(summary_path: Path, payload: dict[str, object]) -> str:
        return write_windows_release_summary(summary_path, payload)

    def _write_windows_release_receipt(
        self,
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
    ) -> str:
        return write_windows_release_receipt(
            self._windows_ops_state_path(),
            self._windows_release_receipt_path(),
            self._windows_release_summary_path(),
            action,
            summary,
            changes,
            ok=ok,
            commands=commands,
            event_id=event_id,
            steps_completed=steps_completed,
            steps_total=steps_total,
            phase=phase,
            next_step=next_step,
            fix_target=fix_target,
            docs_hint=docs_hint,
            entry_point=entry_point,
            artifacts=artifacts,
            gate_summary=gate_summary,
            gate_detail=gate_detail,
            gate_checks=gate_checks,
            gate_required_files=gate_required_files,
            gate_failed_checks=gate_failed_checks,
            gate_missing_files=gate_missing_files,
            gate_passed_checks=gate_passed_checks,
            gate_total_checks=gate_total_checks,
            gate_recommendations=gate_recommendations,
            gate_recommendation_details=gate_recommendation_details,
        )

    @staticmethod
    def _windows_ops_guidance(action: str, *, ok: bool, phase: str = "completed") -> dict[str, str]:
        return windows_ops_guidance(action, ok=ok, phase=phase)

    @staticmethod
    def _summarize_windows_recipe_result(payload: dict[str, object]) -> tuple[str, str]:
        return summarize_windows_recipe_result(payload)

    def _record_windows_ops_state(
        self,
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
    ) -> None:
        update = persist_windows_ops_state(
            WindowsOpsStateRecord(
                action=action,
                summary=summary,
                changes=changes,
                ok=ok,
                commands=commands,
                event_id=event_id,
                steps_completed=steps_completed,
                steps_total=steps_total,
                phase=phase,
                next_step=next_step,
                fix_target=fix_target,
                docs_hint=docs_hint,
                entry_point=entry_point,
                artifacts=artifacts,
                gate_summary=gate_summary,
                gate_detail=gate_detail,
                gate_checks=gate_checks,
                gate_required_files=gate_required_files,
                gate_failed_checks=gate_failed_checks,
                gate_missing_files=gate_missing_files,
                gate_passed_checks=gate_passed_checks,
                gate_total_checks=gate_total_checks,
                gate_recommendations=gate_recommendations,
                gate_recommendation_details=gate_recommendation_details,
            ),
            state_path=self._windows_ops_state_path(),
            receipt_path=self._windows_release_receipt_path(),
            summary_path=self._windows_release_summary_path(),
            write_state=_write_json,
        )
        feedback = dict(update.feedback)
        self._settings_hub_view.set_windows_ops_feedback(
            update.action,
            str(feedback.pop("summary", "") or ""),
            str(feedback.pop("changes", "") or ""),
            **feedback,
        )
        snapshot_getter = getattr(self._settings_hub_view, "windows_ops_snapshot", None)
        if callable(snapshot_getter):
            self._settings_hub_view.set_windows_snapshot(snapshot_getter())

    def _start_windows_ops_chain(self, action: str) -> None:
        start_windows_ops_chain_request(self, action)

    def _update_windows_ops_chain(self, action: str, *, ok: bool, summary: str) -> bool:
        return update_windows_ops_chain_request(self, action, ok=ok, summary=summary)

    def _on_terminal_recipe_finished(self, payload: dict) -> None:
        if not isinstance(payload, dict):
            return
        if str(payload.get("kind", "") or "").strip().lower() != "windows_ops":
            return
        action = str(payload.get("action", "") or "").strip().lower()
        pre_snapshot = payload.get("pre_snapshot", {}) if isinstance(payload.get("pre_snapshot"), dict) else {}
        post_snapshot = self._collect_windows_service_snapshot()
        dynamic_changes = self._windows_service_snapshot_changes(pre_snapshot, post_snapshot)
        artifacts = self._windows_ops_artifact_refs(action, post_snapshot)
        completion = complete_windows_ops_terminal_recipe(
            payload,
            dynamic_changes=dynamic_changes,
            artifacts=artifacts,
            guidance=self._windows_ops_guidance(
                action,
                ok=bool(payload.get("ok", False)),
                phase="completed",
            ),
            gate_details=self._release_dry_run_gate_details() if action == "release_dry_run" else {},
            receipt_path=self._windows_release_receipt_path(),
            summary_path=self._windows_release_summary_path(),
        )
        self._record_windows_ops_state(**asdict(completion.state_record))
        self._log_launcher_event("windows_ops_completed", **completion.event_fields)
        if hasattr(self._status_panel, "append_syslog"):
            self._status_panel.append_syslog(completion.summary)
        append_log = getattr(self._settings_hub_view, "append_log", None)
        if callable(append_log):
            append_log(completion.summary)
        self._set_daily_activity(completion.summary)
