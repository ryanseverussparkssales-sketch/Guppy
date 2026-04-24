from __future__ import annotations

from src.guppy.launcher_application.connector_state_service import log_connector_policy_denial


def test_log_connector_policy_denial_dedupes_identical_events() -> None:
    emitted: list[tuple[str, dict[str, str]]] = []
    recent: dict[str, float] = {}

    def _log(event_type: str, payload: dict[str, str]) -> None:
        emitted.append((event_type, payload))

    times = iter([10.0, 11.0])

    log_connector_policy_denial(
        "gmail",
        "guppy-primary",
        "connector_host_auth_missing",
        "Missing auth",
        recent_denials=recent,
        dedupe_ttl_s=10.0,
        log_event_fn=_log,
        monotonic_fn=lambda: next(times),
    )
    log_connector_policy_denial(
        "gmail",
        "guppy-primary",
        "connector_host_auth_missing",
        "Missing auth",
        recent_denials=recent,
        dedupe_ttl_s=10.0,
        log_event_fn=_log,
        monotonic_fn=lambda: next(times),
    )

    assert len(emitted) == 1
    assert emitted[0][0] == "connector.policy_denied"

