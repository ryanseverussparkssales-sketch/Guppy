"""Inference metrics API — time-series data for the AdminPanel dashboard.

GET /api/inference/metrics?window=1h|6h|24h|7d
    Returns per-provider request counts, latency, and bucketed time-series.

GET /api/inference/metrics/summary
    Returns aggregate totals (all-time).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from src.guppy.api.server_context import ServerContext
from src.guppy.paths import MAIN_DB_PATH, USER_DATA_DIR


def _db_path() -> str:
    return str(MAIN_DB_PATH)


def _window_delta(window: str) -> timedelta:
    return {
        "1h":  timedelta(hours=1),
        "6h":  timedelta(hours=6),
        "24h": timedelta(hours=24),
        "7d":  timedelta(days=7),
    }.get(window, timedelta(hours=24))


def _bucket_minutes(window: str) -> int:
    """Return bucket size in minutes for the given window."""
    return {"1h": 5, "6h": 15, "24h": 60, "7d": 360}.get(window, 60)


def _query_metrics(since: datetime) -> Dict[str, Any]:
    """Query inference_metrics table and return aggregated results."""
    since_iso = since.isoformat()

    try:
        with sqlite3.connect(_db_path()) as conn:
            conn.row_factory = sqlite3.Row

            # Per-provider aggregates
            provider_rows = conn.execute(
                """
                SELECT
                    provider,
                    COUNT(*)                                   AS total,
                    SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) AS successes,
                    AVG(CASE WHEN success=1 THEN latency_ms END) AS avg_latency_ms,
                    SUM(cost)                                  AS total_cost,
                    SUM(total_tokens)                          AS total_tokens
                FROM inference_metrics
                WHERE timestamp >= ?
                GROUP BY provider
                ORDER BY total DESC
                """,
                (since_iso,),
            ).fetchall()

            # Raw rows for time-series bucketing
            ts_rows = conn.execute(
                """
                SELECT timestamp, provider, latency_ms, success
                FROM inference_metrics
                WHERE timestamp >= ?
                ORDER BY timestamp ASC
                """,
                (since_iso,),
            ).fetchall()

    except sqlite3.OperationalError:
        # Table doesn't exist yet
        return {"by_provider": [], "time_series": []}

    by_provider = [
        {
            "provider":      r["provider"],
            "total":         r["total"],
            "successes":     r["successes"],
            "errors":        r["total"] - r["successes"],
            "error_rate":    round((r["total"] - r["successes"]) / max(r["total"], 1) * 100, 1),
            "avg_latency_ms": round(r["avg_latency_ms"] or 0, 1),
            "total_cost":    round(r["total_cost"] or 0, 6),
            "total_tokens":  r["total_tokens"] or 0,
        }
        for r in provider_rows
    ]

    return {
        "by_provider": by_provider,
        "time_series": list(ts_rows),  # raw — bucketing done below
    }


def _bucket_time_series(
    raw_rows: List[sqlite3.Row],
    since: datetime,
    bucket_minutes: int,
) -> List[Dict[str, Any]]:
    """Aggregate raw rows into fixed-width time buckets for Recharts."""
    now = datetime.now(timezone.utc)
    buckets: Dict[str, Dict[str, int]] = {}

    cur = since.replace(second=0, microsecond=0)
    while cur <= now:
        key = cur.strftime("%H:%M") if bucket_minutes < 60 else cur.strftime("%m/%d %H:%M")
        buckets[key] = {"requests": 0, "errors": 0, "latency_sum": 0, "latency_count": 0}
        cur += timedelta(minutes=bucket_minutes)

    for row in raw_rows:
        try:
            ts = datetime.fromisoformat(row["timestamp"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue

        # Find bucket
        offset = int((ts - since).total_seconds() // 60 // bucket_minutes) * bucket_minutes
        bucket_time = since + timedelta(minutes=offset)
        key = bucket_time.strftime("%H:%M") if bucket_minutes < 60 else bucket_time.strftime("%m/%d %H:%M")

        if key not in buckets:
            continue
        buckets[key]["requests"] += 1
        if not row["success"]:
            buckets[key]["errors"] += 1
        if row["latency_ms"]:
            buckets[key]["latency_sum"] += row["latency_ms"]
            buckets[key]["latency_count"] += 1

    return [
        {
            "time": key,
            "requests": v["requests"],
            "errors": v["errors"],
            "avg_latency_ms": round(
                v["latency_sum"] / v["latency_count"] if v["latency_count"] else 0, 1
            ),
        }
        for key, v in sorted(buckets.items())
    ]


def build_inference_metrics_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/inference")

    @router.get("/metrics")
    async def get_inference_metrics(
        window: str = "24h",
        _user_id: str = Depends(ctx.require_rate_limit),
    ) -> Dict[str, Any]:
        """Time-series inference metrics for dashboard charts.

        Query params:
            window: 1h | 6h | 24h (default) | 7d
        """
        delta = _window_delta(window)
        since = datetime.now(timezone.utc) - delta
        bucket_min = _bucket_minutes(window)

        result = _query_metrics(since)
        time_series = _bucket_time_series(result.pop("time_series", []), since, bucket_min)

        return {
            "window": window,
            "since": since.isoformat(),
            "by_provider": result["by_provider"],
            "time_series": time_series,
        }

    @router.get("/metrics/summary")
    async def get_inference_summary(
        _user_id: str = Depends(ctx.require_rate_limit),
    ) -> Dict[str, Any]:
        """All-time aggregate totals."""
        try:
            with sqlite3.connect(_db_path()) as conn:
                row = conn.execute(
                    """
                    SELECT
                        COUNT(*)                                   AS total,
                        SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) AS successes,
                        AVG(CASE WHEN success=1 THEN latency_ms END) AS avg_latency_ms,
                        SUM(cost)                                  AS total_cost,
                        SUM(total_tokens)                          AS total_tokens,
                        MIN(timestamp)                             AS first_at,
                        MAX(timestamp)                             AS last_at
                    FROM inference_metrics
                    """
                ).fetchone()
        except sqlite3.OperationalError:
            return {"total": 0, "successes": 0, "avg_latency_ms": 0, "total_cost": 0}

        if not row or not row[0]:
            return {"total": 0, "successes": 0, "avg_latency_ms": 0, "total_cost": 0}

        return {
            "total":          row[0],
            "successes":      row[1],
            "errors":         row[0] - row[1],
            "avg_latency_ms": round(row[2] or 0, 1),
            "total_cost":     round(row[3] or 0, 6),
            "total_tokens":   row[4] or 0,
            "first_at":       row[5],
            "last_at":        row[6],
        }

    return router
