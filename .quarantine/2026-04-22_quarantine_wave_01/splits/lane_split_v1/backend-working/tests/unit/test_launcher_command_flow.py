from __future__ import annotations

from pathlib import Path
from queue import SimpleQueue
from types import SimpleNamespace

from src.guppy.launcher_application.launcher_command_flow import (
    build_shell_model_loadout_summary,
    derive_topbar_model_context,
    handle_assistant_command,
)


class _ImmediateThread:
    def __init__(self, *, target=None, args=(), kwargs=None, daemon=None) -> None:
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}
        self.daemon = daemon

    def start(self) -> None:
        if callable(self._target):
            self._target(*self._args, **self._kwargs)


def test_derive_topbar_model_context_reads_route_text_and_runtime_defaults() -> None:
    runtime = SimpleNamespace(backend="ollama", chat_model="llama3", model="fallback")

    result = derive_topbar_model_context(
        route_text="using mistral via local backup qwen",
        runtime=runtime,
    )

    assert result == {
        "main_model": "llama3",
        "support_model": "qwen",
        "backend": "ollama",
        "route": "LOCAL",
    }


def test_build_shell_model_loadout_summary_prefers_settings_then_environment() -> None:
    summary = build_shell_model_loadout_summary(
        active_model="active",
        runtime_backend="lmstudio",
        settings_payload={
            "local_runtime_backend": "ollama",
            "local_main_model": "main-a",
            "local_sub_model_a": "helper-a",
            "local_sub_model_b": "helper-b",
        },
        environment={
            "GUPPY_MAIN_MODEL": "env-main",
            "GUPPY_SUB_MODEL_A": "env-sub-a",
            "GUPPY_SUB_MODEL_B": "env-sub-b",
        },
    )

    assert summary == "MODELS / OLLAMA / MAIN main-a / SUB A helper-a / SUB B helper-b"


def test_handle_assistant_command_submits_and_records_response() -> None:
    logged_messages: list[tuple[str, dict[str, object]]] = []
    launcher_events: list[tuple[str, dict[str, object]]] = []

    class _AssistantView:
        def __init__(self) -> None:
            self.user_messages: list[str] = []
            self.statuses: list[str] = []
            self.in_flight_states: list[bool] = []

        def selected_mode(self) -> str:
            return "auto"

        def recent_history(self, limit: int = 12) -> list[dict[str, str]]:
            del limit
            return []

        def add_user_message(self, text: str) -> None:
            self.user_messages.append(text)

        def set_request_in_flight(self, in_flight: bool) -> None:
            self.in_flight_states.append(in_flight)

        def set_status(self, text: str) -> None:
            self.statuses.append(text)

        def set_background_event(self, _text: str) -> None:
            return

        def add_system_message(self, _text: str) -> None:
            return

    launcher = SimpleNamespace(
        _assistant_view=_AssistantView(),
        _assistant_events=SimpleQueue(),
        _status_panel=SimpleNamespace(lines=[], append_syslog=lambda line: launcher._status_panel.lines.append(line)),
        _active_request_seq=0,
        _chat_session_id="session-1",
        _request_in_flight=False,
        _active_instance_name="guppy-primary",
        _active_library_context_items=[],
        _last_command="",
        _validate_mode_ready=lambda _mode: (True, ""),
        _update_route_preview=lambda _cmd: None,
        _set_daily_activity=lambda _text: None,
        _chat_timeout_for_request=lambda _mode, _command="": 12.0,
        _api_reachable=lambda timeout=0.8: True,
        _ensure_api_reachable_for_command=lambda: (True, "ok"),
        _http_json=lambda path, **kwargs: {"response": "handled"} if path == "/chat" else {},
        _is_unauthorized_error=lambda _text: False,
        _extract_error_code=lambda _text: "",
        _refresh_api_auth_state=lambda _reason: "",
        _log_launcher_event=lambda event, **fields: launcher_events.append((event, fields)),
    )

    def _build_submission(command: str, history: list[dict[str, str]], active_items: list[dict[str, str]]) -> object:
        del history, active_items
        return SimpleNamespace(
            request_message=command,
            history=[],
            context_notice="",
            status_text="Working",
            background_event="context primed",
        )

    handle_assistant_command(
        launcher,
        "status please",
        instance_logger_available=True,
        instance_log_appender=lambda instance, payload: logged_messages.append((instance, payload)),
        library_chat_submission_builder=_build_submission,
        thread_factory=_ImmediateThread,
        uuid_factory=lambda: SimpleNamespace(hex="abc123"),
    )

    assert launcher._last_command == "status please"
    assert launcher._assistant_view.user_messages == ["status please"]
    assert launcher._assistant_view.statuses == ["Working"]
    assert launcher._assistant_view.in_flight_states == [True]
    assert launcher._status_panel.lines[-1] == "command queued"
    assert logged_messages[0][1]["role"] == "user"
    kind, payload, seq = launcher._assistant_events.get_nowait()
    assert (kind, payload, seq) == ("assistant", "handled", 1)
    assert launcher_events[0][0] == "command_submitted"
    assert launcher_events[-1][0] == "command_response"
    assert launcher_events[-1][1]["idempotency_key"] == "launcher-abc123"
