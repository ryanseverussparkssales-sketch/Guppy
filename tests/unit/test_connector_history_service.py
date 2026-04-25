"""Unit tests for connector_history_service."""

import pytest
from src.guppy.launcher_application.connector_history_service import (
    estimate_connector_performance,
    export_analytics,
    get_action_history,
    get_usage_stats,
)


def test_get_usage_stats_empty_history():
    """Test usage stats with no history."""
    def mock_history_fn(connector_id):
        return {
            "connector": connector_id,
            "recent_events": [],
        }

    stats = get_usage_stats("test_connector", history_payload_fn=mock_history_fn)

    assert stats["connector"] == "test_connector"
    assert stats["total_actions"] == 0
    assert stats["successful_actions"] == 0
    assert stats["success_rate"] == 0.0


def test_get_usage_stats_with_history():
    """Test usage stats with action history."""
    def mock_history_fn(connector_id):
        return {
            "connector": connector_id,
            "last_action": "verify",
            "last_action_at": "2026-04-22T10:00:00+00:00",
            "last_action_ok": True,
            "last_result": "Verified successfully",
            "last_verified_at": "2026-04-22T10:00:00+00:00",
            "last_verify_ok": True,
            "recent_events": [
                {"ok": True, "action": "verify", "at": "2026-04-22T09:00:00+00:00", "summary": "OK"},
                {"ok": True, "action": "connect", "at": "2026-04-22T08:00:00+00:00", "summary": "Connected"},
                {"ok": False, "action": "verify", "at": "2026-04-22T07:00:00+00:00", "summary": "Failed"},
            ],
        }

    stats = get_usage_stats("test_connector", history_payload_fn=mock_history_fn)

    assert stats["total_actions"] == 3
    assert stats["successful_actions"] == 2
    assert stats["success_rate"] == pytest.approx(66.67, 0.01)
    assert stats["last_action"] == "verify"
    assert stats["last_action_ok"] is True


def test_get_action_history_limit():
    """Test action history respects limit."""
    def mock_history_fn(connector_id):
        return {
            "recent_events": [
                {"event_id": f"event-{i}", "action": "verify", "ok": True, "at": f"2026-04-22T{i:02d}:00:00+00:00", "summary": f"Action {i}"}
                for i in range(1, 11)  # 10 events
            ],
        }

    actions = get_action_history("test_connector", limit=5, history_payload_fn=mock_history_fn)

    assert len(actions) == 5
    # Should be reversed (most recent first)
    assert actions[0]["event_id"] == "event-10"
    assert actions[4]["event_id"] == "event-6"


def test_estimate_connector_performance_healthy():
    """Test performance estimation for healthy connector."""
    def mock_history_fn(connector_id):
        return {
            "recent_events": [
                {"ok": True, "action": "verify", "at": "2026-04-22T05:00:00+00:00"},
                {"ok": True, "action": "verify", "at": "2026-04-22T04:00:00+00:00"},
                {"ok": True, "action": "verify", "at": "2026-04-22T03:00:00+00:00"},
                {"ok": True, "action": "verify", "at": "2026-04-22T02:00:00+00:00"},
                {"ok": True, "action": "verify", "at": "2026-04-22T01:00:00+00:00"},
            ],
        }

    perf = estimate_connector_performance("test_connector", history_payload_fn=mock_history_fn)

    assert perf["status"] == "healthy"
    assert perf["recent_success_rate"] == 100.0
    assert perf["consecutive_successes"] == 5


def test_estimate_connector_performance_degraded():
    """Test performance estimation for degraded connector."""
    def mock_history_fn(connector_id):
        return {
            "recent_events": [
                {"ok": False, "action": "verify", "at": "2026-04-22T05:00:00+00:00"},
                {"ok": True, "action": "verify", "at": "2026-04-22T04:00:00+00:00"},
                {"ok": True, "action": "verify", "at": "2026-04-22T03:00:00+00:00"},
                {"ok": False, "action": "verify", "at": "2026-04-22T02:00:00+00:00"},
                {"ok": True, "action": "verify", "at": "2026-04-22T01:00:00+00:00"},
            ],
        }

    perf = estimate_connector_performance("test_connector", history_payload_fn=mock_history_fn)

    assert perf["status"] == "degraded"
    assert perf["recent_success_rate"] == 60.0
    assert perf["consecutive_successes"] == 0  # Last action failed


def test_estimate_connector_performance_failing():
    """Test performance estimation for failing connector."""
    def mock_history_fn(connector_id):
        return {
            "recent_events": [
                {"ok": False, "action": "verify", "at": "2026-04-22T05:00:00+00:00"},
                {"ok": False, "action": "verify", "at": "2026-04-22T04:00:00+00:00"},
                {"ok": True, "action": "verify", "at": "2026-04-22T03:00:00+00:00"},
            ],
        }

    perf = estimate_connector_performance("test_connector", history_payload_fn=mock_history_fn)

    assert perf["status"] == "failing"
    assert perf["recent_success_rate"] == pytest.approx(33.33, 0.01)


def test_export_analytics():
    """Test analytics export."""
    def mock_history_fn(connector_id):
        events = {
            "crm": 3,  # 3 events
            "gmail": 2,  # 2 events
            "calendar": 1,  # 1 event
        }
        num_events = events.get(connector_id, 0)
        return {
            "connector": connector_id,
            "recent_events": [
                {"ok": i % 2 == 0, "action": "verify", "at": f"2026-04-22T{i:02d}:00:00+00:00"}
                for i in range(num_events)
            ],
        }

    connectors = ["crm", "gmail", "calendar"]
    analytics = export_analytics(
        connectors,
        history_payload_fn=mock_history_fn,
        date_range=("2026-04-22", "2026-04-22"),
    )

    assert analytics["summary"]["total_connectors"] == 3
    assert analytics["summary"]["total_actions"] == 6  # 3 + 2 + 1
    assert "crm" in analytics["connectors"]
    assert "gmail" in analytics["connectors"]
    assert "calendar" in analytics["connectors"]
    assert analytics["date_range"]["start"] == "2026-04-22"


def test_get_usage_stats_invalid_history():
    """Test usage stats handles invalid history gracefully."""
    def mock_history_fn(connector_id):
        return {
            "connector": connector_id,
            "recent_events": "not a list",  # Invalid type
        }

    stats = get_usage_stats("test_connector", history_payload_fn=mock_history_fn)

    assert stats["total_actions"] == 0
    assert stats["successful_actions"] == 0
    assert stats["success_rate"] == 0.0


def test_estimate_connector_performance_no_history():
    """Test performance estimation with no history."""
    def mock_history_fn(connector_id):
        return {"recent_events": []}

    perf = estimate_connector_performance("test_connector", history_payload_fn=mock_history_fn)

    assert perf["status"] == "unknown"
    assert perf["reliability_score"] == 0
    assert perf["consecutive_successes"] == 0
