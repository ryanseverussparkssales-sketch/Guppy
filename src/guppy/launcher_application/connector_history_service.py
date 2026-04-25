"""Connector usage history and analytics service."""

from __future__ import annotations

from typing import Any, Callable


def get_usage_stats(
    connector_id: str,
    *,
    history_payload_fn: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    """
    Calculate connector usage statistics.

    Returns:
    - success_rate: Percentage of successful actions
    - total_actions: Total number of recorded actions
    - recent_actions: Last 5 actions performed
    - last_action: Most recent action details
    - last_verified_at: Timestamp of last successful verify
    """
    history = history_payload_fn(connector_id)

    recent_events = history.get("recent_events", [])
    if not isinstance(recent_events, list):
        recent_events = []

    total_actions = len(recent_events)
    successful_actions = sum(1 for e in recent_events if isinstance(e, dict) and e.get("ok") is True)
    success_rate = (successful_actions / total_actions * 100) if total_actions > 0 else 0.0

    return {
        "connector": connector_id,
        "total_actions": total_actions,
        "successful_actions": successful_actions,
        "success_rate": round(success_rate, 2),
        "last_action": history.get("last_action", ""),
        "last_action_at": history.get("last_action_at", ""),
        "last_action_ok": bool(history.get("last_action_ok", False)),
        "last_result": str(history.get("last_result", "") or ""),
        "last_verified_at": history.get("last_verified_at", ""),
        "last_verify_ok": bool(history.get("last_verify_ok", False)),
        "recent_events": [
            {
                "action": str(e.get("action", "") or ""),
                "ok": bool(e.get("ok", False)),
                "at": str(e.get("at", "") or ""),
                "summary": str(e.get("summary", "") or ""),
            }
            for e in recent_events
            if isinstance(e, dict)
        ],
    }


def export_analytics(
    connector_ids: list[str],
    *,
    history_payload_fn: Callable[[str], dict[str, Any]],
    date_range: tuple[str, str] | None = None,
) -> dict[str, Any]:
    """
    Export connector analytics for reporting.

    Args:
        connector_ids: List of connector IDs to export
        history_payload_fn: Function to load history for a connector
        date_range: Optional (start_date, end_date) tuple in ISO format

    Returns:
        Dictionary with analytics summary and per-connector stats
    """
    analytics = {
        "date_range": {
            "start": date_range[0] if date_range else "",
            "end": date_range[1] if date_range else "",
        },
        "summary": {
            "total_connectors": len(connector_ids),
            "total_actions": 0,
            "total_successes": 0,
            "overall_success_rate": 0.0,
        },
        "connectors": {},
    }

    total_actions = 0
    total_successes = 0

    for connector_id in connector_ids:
        stats = get_usage_stats(connector_id, history_payload_fn=history_payload_fn)
        analytics["connectors"][connector_id] = stats
        total_actions += stats["total_actions"]
        total_successes += stats["successful_actions"]

    if total_actions > 0:
        analytics["summary"]["total_actions"] = total_actions
        analytics["summary"]["total_successes"] = total_successes
        analytics["summary"]["overall_success_rate"] = round(total_successes / total_actions * 100, 2)

    return analytics


def get_action_history(
    connector_id: str,
    *,
    limit: int = 10,
    history_payload_fn: Callable[[str], dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Retrieve recent actions for a connector.

    Args:
        connector_id: The connector ID
        limit: Maximum number of actions to return
        history_payload_fn: Function to load history for a connector

    Returns:
        List of action records, most recent first
    """
    history = history_payload_fn(connector_id)
    recent_events = history.get("recent_events", [])

    if not isinstance(recent_events, list):
        recent_events = []

    # Filter and format events
    actions = [
        {
            "event_id": str(e.get("event_id", "") or ""),
            "action": str(e.get("action", "") or ""),
            "connector": str(e.get("connector", "") or ""),
            "provider": str(e.get("provider", "") or ""),
            "ok": bool(e.get("ok", False)),
            "summary": str(e.get("summary", "") or ""),
            "at": str(e.get("at", "") or ""),
            "result_code": str(e.get("result_code", "") or ""),
            "next_step": str(e.get("next_step", "") or ""),
        }
        for e in recent_events
        if isinstance(e, dict)
    ]

    # Return most recent first, limited by count
    return list(reversed(actions))[:limit]


def estimate_connector_performance(
    connector_id: str,
    *,
    history_payload_fn: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    """
    Calculate connector reliability metrics.

    Returns:
        - reliability_score: 0-100 based on recent success rate
        - recent_success_rate: Success rate over last 5 actions
        - consecutive_successes: Number of recent consecutive successes
        - status: "healthy", "degraded", or "failing"
    """
    history = history_payload_fn(connector_id)
    recent_events = history.get("recent_events", [])

    if not isinstance(recent_events, list):
        recent_events = []

    # Calculate recent success rate (last 5 actions)
    recent = [e for e in recent_events if isinstance(e, dict)][-5:]
    if not recent:
        return {
            "connector": connector_id,
            "reliability_score": 0,
            "recent_success_rate": 0.0,
            "consecutive_successes": 0,
            "status": "unknown",
            "note": "No recent action history",
        }

    successful = sum(1 for e in recent if e.get("ok") is True)
    recent_rate = (successful / len(recent) * 100) if recent else 0.0

    # Count consecutive successes from most recent (events are most-recent-first)
    consecutive = 0
    for e in recent:
        if e.get("ok") is True:
            consecutive += 1
        else:
            break

    # Determine health status
    if recent_rate >= 80 and consecutive >= 2:
        status = "healthy"
    elif recent_rate >= 50:
        status = "degraded"
    else:
        status = "failing"

    return {
        "connector": connector_id,
        "reliability_score": round(recent_rate, 2),
        "recent_success_rate": round(recent_rate, 2),
        "consecutive_successes": consecutive,
        "total_recent": len(recent),
        "status": status,
    }
