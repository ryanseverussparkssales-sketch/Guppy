from __future__ import annotations

import sys
import threading
from pathlib import Path

from PySide6.QtCore import QTimer

from src.guppy.launcher_application import build_library_chat_submission, build_windows_ops_plan
from src.guppy.launcher_application import launcher_nav_handlers as _nav_handlers
from src.guppy.launcher_application.automation_test_coordination import (
    approve_latest_builder_task,
    build_launcher_automation_test_snapshot,
    handle_automation_action_request,
    handle_builder_task_requested,
    queue_builder_task as _queue_builder_task_fn,
    sync_launcher_automation_test_state,
    user_test_evidence_paths,
    write_launcher_automation_report,
    write_launcher_user_test_evidence_pack,
)
from src.guppy.launcher_application.automation_test_support import (
    display_repo_path,
    latest_stress_report_path,
    recent_launcher_event_summaries,
    write_user_test_evidence_summary,
)
from src.guppy.launcher_application.launcher_command_flow import handle_assistant_command
from src.guppy.launcher_application.launcher_shell_support import (
    on_home_starter_requested as _on_home_starter_requested_fn,
)
from src.guppy.launcher_application.launcher_voice_strip import (
    ensure_voice_capture as _ensure_voice_capture_fn,
    on_mic_requested as _on_mic_requested_fn,
)
from src.guppy.launcher_application.recovery_coordination import (
    run_recovery_request,
    start_recovery_request,
)
from src.guppy.launcher_application.storage_io import (
    append_instance_log,
    instance_logger_backend_available,
)
from src.guppy.launcher_application.windows_ops_request_flow import (
    dispatch_windows_ops_request,
)

try:
    from src.guppy.voice.voice import GuppyVoice

    _VOICE_CAPTURE_AVAILABLE = True
except Exception:
    GuppyVoice = None  # type: ignore[assignment]
    _VOICE_CAPTURE_AVAILABLE = False

_INSTANCE_LOGGER_AVAILABLE = instance_logger_backend_available()
_RUNTIME = Path(__file__).resolve().parent.parent.parent / "runtime"
_AUTOMATION_TEST_VALIDATION_COMMAND = (
    ".venv\\Scripts\\python.exe -m pytest tests/unit/test_offhours_builder.py tests/unit/test_instance_controls.py -q"
)


def _launcher_module():
    return (
        sys.modules.get("ui.launcher.launcher_window")
        or sys.modules.get("compat_shims.launcher_ui.ui.launcher.launcher_window")
    )


def _runtime_dir() -> Path:
    launcher_module = _launcher_module()
    runtime_dir = getattr(launcher_module, "_RUNTIME", _RUNTIME)
    return runtime_dir if isinstance(runtime_dir, Path) else Path(runtime_dir)


def _automation_report_path() -> Path:
    return _runtime_dir() / "offhours_builder_report.json"


def available_instance_names(self) -> set[str]:
    snapshot = self._last_instance_snapshot if isinstance(self._last_instance_snapshot, dict) else {}
    items = snapshot.get("instances", []) if isinstance(snapshot, dict) else []
    return {
        str(item.get("name", "")).strip()
        for item in items
        if isinstance(item, dict) and bool(item.get("enabled", True)) and str(item.get("name", "")).strip()
    }


def user_test_evidence_path(self) -> Path:
    return user_test_evidence_paths(_runtime_dir())[0]


def user_test_evidence_summary_path(self) -> Path:
    return user_test_evidence_paths(_runtime_dir())[1]


def display_repo_path_static(path: Path | str | None) -> str:
    return display_repo_path(_runtime_dir().parent, path)


def latest_stress_report_path_static() -> Path | None:
    return latest_stress_report_path(_runtime_dir())


def recent_launcher_event_summaries_method(self, limit: int = 4) -> list[str]:
    return recent_launcher_event_summaries(_runtime_dir(), limit=limit)


def write_user_test_evidence_summary_static(summary_path: Path, payload: dict[str, object]) -> str:
    return write_user_test_evidence_summary(summary_path, payload)


def write_user_test_evidence_pack(
    self,
    *,
    report_path: Path | None = None,
    status: str = "",
) -> dict[str, str]:
    return write_launcher_user_test_evidence_pack(
        self,
        report_path=report_path,
        status=status,
        runtime_dir=_runtime_dir(),
        automation_report_path=_automation_report_path(),
        validation_command=_AUTOMATION_TEST_VALIDATION_COMMAND,
    )


def automation_test_snapshot(
    self,
    *,
    report_path: Path | None = None,
    status: str = "",
    evidence_pack_path: str = "",
    stress_report_path: str = "",
    recent_events: str = "",
) -> dict[str, str]:
    return build_launcher_automation_test_snapshot(
        self,
        report_path=report_path,
        status=status,
        evidence_pack_path=evidence_pack_path,
        stress_report_path=stress_report_path,
        recent_events=recent_events,
        runtime_dir=_runtime_dir(),
        automation_report_path=_automation_report_path(),
        validation_command=_AUTOMATION_TEST_VALIDATION_COMMAND,
    )


def sync_automation_test_state(
    self,
    *,
    status: str = "",
    ok: bool = True,
    report_path: Path | None = None,
    persist: bool = False,
) -> None:
    sync_launcher_automation_test_state(
        self,
        status=status,
        ok=ok,
        report_path=report_path,
        persist=persist,
        runtime_dir=_runtime_dir(),
        automation_report_path=_automation_report_path(),
        validation_command=_AUTOMATION_TEST_VALIDATION_COMMAND,
    )


def queue_builder_task(
    self,
    *,
    template_id: str,
    target_ref: str,
    instance_name: str,
    announce_text: str,
) -> dict[str, object]:
    return _queue_builder_task_fn(
        self,
        template_id=template_id,
        target_ref=target_ref,
        instance_name=instance_name,
        announce_text=announce_text,
        automation_report_path=_automation_report_path(),
    )


def write_automation_report(self) -> Path:
    return write_launcher_automation_report(
        self,
        automation_report_path=_automation_report_path(),
        validation_command=_AUTOMATION_TEST_VALIDATION_COMMAND,
    )


def approve_latest_builder_task_method(self) -> dict[str, object]:
    return approve_latest_builder_task(self)


def on_builder_task_requested(self, payload: dict[str, object]) -> None:
    handle_builder_task_requested(
        self,
        payload,
        automation_report_path=_automation_report_path(),
    )


def on_automation_action_requested(self, action: str) -> None:
    handle_automation_action_request(
        self,
        action,
        automation_report_path=_automation_report_path(),
        validation_command=_AUTOMATION_TEST_VALIDATION_COMMAND,
    )


def on_recovery_requested(self, action: str) -> None:
    start_recovery_request(self, action, thread_factory=threading.Thread)


def run_recovery_request_method(self, act: str) -> None:
    run_recovery_request(self, act)


def on_search(self, query: str) -> None:
    _nav_handlers.on_search(self, query)


def windows_ops_plan_static(action: str) -> dict[str, object]:
    return build_windows_ops_plan(action)


def windows_ops_recipe_static(action: str) -> tuple[str, list[str]]:
    plan = windows_ops_plan_static(action)
    return str(plan.get("label", "") or ""), [str(item) for item in plan.get("commands", []) if str(item).strip()]


def on_windows_ops_requested(self, action: str) -> None:
    dispatch_windows_ops_request(self, action, delayed_scheduler=QTimer.singleShot)


def on_home_starter_requested(self, starter_id: str, prompt: str) -> None:
    _on_home_starter_requested_fn(self, starter_id, prompt)


def on_assistant_command(self, command: str) -> None:
    handle_assistant_command(
        self,
        command,
        instance_logger_available=_INSTANCE_LOGGER_AVAILABLE,
        instance_log_appender=append_instance_log,
        library_chat_submission_builder=build_library_chat_submission,
        thread_factory=threading.Thread,
    )


def on_quick_action(self, action: str) -> None:
    _nav_handlers.on_quick_action(self, action)


def refresh_notification_badge(self) -> None:
    _nav_handlers.refresh_notification_badge(self, events_path=_runtime_dir() / "launcher_events.jsonl")


def ensure_voice_capture(self) -> tuple[bool, str]:
    return _ensure_voice_capture_fn(
        self,
        voice_capture_available=_VOICE_CAPTURE_AVAILABLE,
        voice_class=GuppyVoice,
    )


def on_mic_requested(self) -> None:
    _on_mic_requested_fn(self, thread_factory=threading.Thread)
