from queue import Queue

from src.guppy.launcher_application.recovery_coordination import (
    classify_recovery_summary,
    format_recovery_summary,
    push_recovery_outcome,
)


class _RecoveryOwner:
    def __init__(self) -> None:
        self._recovery_events = Queue()
        self.logged: list[tuple[str, dict[str, object]]] = []

    def _log_launcher_event(self, event: str, **fields: object) -> None:
        self.logged.append((event, fields))


def test_recovery_summary_helpers_classify_and_format() -> None:
    assert classify_recovery_summary("HTTP 401 from repair endpoint", False) == "auth_failed"
    assert format_recovery_summary("api_unreachable", "connection refused") == "API unreachable: connection refused"


def test_push_recovery_outcome_enqueues_event_and_logs() -> None:
    owner = _RecoveryOwner()

    formatted = push_recovery_outcome(owner, "warmup", False, "network error while checking runtime")
    event = owner._recovery_events.get_nowait()

    assert formatted == "API unreachable: network error while checking runtime"
    assert event["kind"] == "outcome"
    assert event["category"] == "api_unreachable"
    assert owner.logged == [
        (
            "recovery_error",
            {
                "action": "warmup",
                "ok": False,
                "category": "api_unreachable",
                "summary": "API unreachable: network error while checking runtime",
            },
        )
    ]
