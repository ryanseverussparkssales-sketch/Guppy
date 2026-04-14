import argparse
import json
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from src.guppy.api import server as guppy_api
from src.guppy.daemon.daemon import TaskScheduler
from src.guppy.inference.router import InferenceRouter, resolve_ui_route
from utils.router_scorecard import log_router_scorecard
from utils.session_logger import log_session_event, tail_session_events


def _run_route_resolution_stress(iterations: int) -> dict:
    previous_classifier_mode = os.environ.get("GUPPY_SEMANTIC_CLASSIFIER")
    os.environ["GUPPY_SEMANTIC_CLASSIFIER"] = "0"
    router = InferenceRouter()
    samples = [
        "What time is it in Dallas?",
        "Explain OAuth2 like I am five.",
        "Design a migration strategy for this API.",
        "Remind me to call Alex tomorrow morning.",
        "Debug this intermittent websocket disconnect.",
        "Teach me how distributed systems fail.",
    ]
    modes = ["auto", "claude", "ollama"]

    start = time.perf_counter()
    failures = 0
    counters = {}
    try:
        for _ in range(iterations):
            text = random.choice(samples)
            mode = random.choice(modes)
            decision = resolve_ui_route(
                user_text=text,
                mode=mode,
                voice_triggered=random.choice([True, False]),
                api_key_available=True,
            )
            key = f"{decision.get('route', 'unknown')}|{decision.get('executor', 'unknown')}"
            counters[key] = counters.get(key, 0) + 1
            if not decision.get("task_type"):
                failures += 1

            # Also hammer raw classifier path.
            _ = router._classify_task(text)
    finally:
        if previous_classifier_mode is None:
            os.environ.pop("GUPPY_SEMANTIC_CLASSIFIER", None)
        else:
            os.environ["GUPPY_SEMANTIC_CLASSIFIER"] = previous_classifier_mode

    elapsed = time.perf_counter() - start
    return {
        "name": "route_resolution",
        "iterations": iterations,
        "failures": failures,
        "elapsed_s": round(elapsed, 3),
        "ops_per_s": round(iterations / max(elapsed, 0.001), 2),
        "routes": counters,
    }


def _run_api_endpoint_stress(total_requests: int, workers: int) -> dict:
    app = guppy_api.app
    app.dependency_overrides[guppy_api.require_rate_limit] = lambda: "stress-user"
    client = TestClient(app)

    endpoints = [
        "/status",
        "/metrics",
        "/startup/check",
        "/logs/recent?limit=5",
    ]

    lock = threading.Lock()
    status_counts = {}
    endpoint_latencies = {ep: [] for ep in endpoints}
    failures = []

    def one_call(_i: int):
        ep = random.choice(endpoints)
        t0 = time.perf_counter()
        try:
            r = client.get(ep)
            latency = (time.perf_counter() - t0) * 1000
            with lock:
                key = f"{ep}:{r.status_code}"
                status_counts[key] = status_counts.get(key, 0) + 1
                endpoint_latencies.setdefault(ep, []).append(latency)
                if r.status_code >= 400:
                    failures.append({"endpoint": ep, "status": r.status_code, "body": r.text[:180]})
            return latency
        except Exception as e:
            with lock:
                failures.append({"endpoint": ep, "status": "exception", "body": str(e)[:180]})
            return None

    start = time.perf_counter()
    latencies = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(one_call, i) for i in range(total_requests)]
        for f in as_completed(futures):
            lat = f.result()
            if lat is not None:
                latencies.append(lat)

    elapsed = time.perf_counter() - start
    latencies.sort()
    p95 = latencies[max(0, int(len(latencies) * 0.95) - 1)] if latencies else 0
    hotpath_latencies = []
    for ep, vals in endpoint_latencies.items():
        if ep != "/startup/check":
            hotpath_latencies.extend(vals)
    hotpath_latencies.sort()
    p95_hotpath = hotpath_latencies[max(0, int(len(hotpath_latencies) * 0.95) - 1)] if hotpath_latencies else 0

    endpoint_p95 = {}
    for ep, vals in endpoint_latencies.items():
        ordered = sorted(vals)
        endpoint_p95[ep] = round(ordered[max(0, int(len(ordered) * 0.95) - 1)], 2) if ordered else 0

    return {
        "name": "api_endpoints",
        "requests": total_requests,
        "workers": workers,
        "elapsed_s": round(elapsed, 3),
        "rps": round(total_requests / max(elapsed, 0.001), 2),
        "latency_ms_avg": round(sum(latencies) / max(len(latencies), 1), 2),
        "latency_ms_p95": round(p95, 2),
        "latency_ms_p95_hotpath": round(p95_hotpath, 2),
        "latency_ms_p95_by_endpoint": endpoint_p95,
        "status_counts": status_counts,
        "failure_count": len(failures),
        "failure_samples": failures[:10],
    }


def _run_reminder_scheduler_stress(reminders: int) -> dict:
    scheduler = TaskScheduler(notifier=None)
    scheduler.start()
    start = time.perf_counter()

    created = []
    failures = 0
    for i in range(reminders):
        msg = scheduler.schedule_reminder(f"stress reminder {i}", "in 30 minutes")
        if "Reminder scheduled" in msg:
            created.append(next(reversed(scheduler.jobs.keys())))
        else:
            failures += 1

    listed = scheduler.get_scheduled_reminders()

    cancelled = 0
    for rid in list(created):
        out = scheduler.cancel_reminder(rid)
        if "cancelled" in out.lower():
            cancelled += 1

    left_after_cancel = len(scheduler.get_scheduled_reminders())
    scheduler.stop()

    elapsed = time.perf_counter() - start
    return {
        "name": "reminder_scheduler",
        "requested": reminders,
        "created": len(created),
        "list_count_mid": len(listed),
        "cancelled": cancelled,
        "left_after_cancel": left_after_cancel,
        "failures": failures,
        "elapsed_s": round(elapsed, 3),
    }


def _run_logging_stress(events: int) -> dict:
    start = time.perf_counter()
    for i in range(events):
        log_session_event("stress", "session_event_stress", idx=i)
        log_router_scorecard(
            session_id="stress",
            request_id=f"stress:{i}",
            mode="auto",
            task_type=random.choice(["simple", "complex", "teaching"]),
            route=random.choice(["haiku", "sonnet", "ollama_teaching"]),
            route_reason="stress_harness",
            model_used=random.choice(["claude-haiku-4-5-20251001", "claude-sonnet-4-6", "merlin"]),
            voice_triggered=False,
            fallback_used=False,
            fallback_count=0,
            tool_calls=random.randint(0, 3),
            tool_errors=random.randint(0, 1),
            tool_budget_hit=False,
            latency_ms=random.randint(400, 12000),
            first_token_ms=random.randint(120, 3200),
            slo_target_ms=random.choice([2500, 3000, 10000]),
            slo_met=random.choice([True, True, True, False]),
            status=random.choice(["ok", "ok", "degraded", "error"]),
            error="" if random.random() > 0.15 else "stress simulated",
        )

    tail = tail_session_events(limit=20)
    elapsed = time.perf_counter() - start
    return {
        "name": "logging_io",
        "events_written": events,
        "session_tail_seen": len(tail),
        "elapsed_s": round(elapsed, 3),
        "ops_per_s": round((events * 2) / max(elapsed, 0.001), 2),
    }


def run_stress(api_requests: int, api_workers: int, route_iterations: int, reminders: int, log_events: int) -> dict:
    sections = []
    sections.append(_run_route_resolution_stress(route_iterations))
    sections.append(_run_api_endpoint_stress(api_requests, api_workers))
    sections.append(_run_reminder_scheduler_stress(reminders))
    sections.append(_run_logging_stress(log_events))

    ok = True
    gate_failures = []
    for s in sections:
        if s.get("failure_count", 0) > 0:
            ok = False
        if s.get("failures", 0) > 0:
            ok = False
        if s.get("left_after_cancel", 0) > 0:
            ok = False

        if s.get("name") == "api_endpoints":
            avg_ms = float(s.get("latency_ms_avg", 0) or 0)
            p95_ms = float(s.get("latency_ms_p95", 0) or 0)
            p95_hot_ms = float(s.get("latency_ms_p95_hotpath", 0) or 0)
            max_avg_ms = float(os.environ.get("GUPPY_STRESS_MAX_API_AVG_MS", "1500"))
            max_p95_ms = float(os.environ.get("GUPPY_STRESS_MAX_API_P95_MS", "5000"))
            max_p95_hot_ms = float(os.environ.get("GUPPY_STRESS_MAX_API_P95_HOT_MS", "1100"))
            if avg_ms > max_avg_ms:
                ok = False
                gate_failures.append(
                    f"api_avg_ms {avg_ms:.2f} exceeded threshold {max_avg_ms:.2f}"
                )
            if p95_ms > max_p95_ms:
                ok = False
                gate_failures.append(
                    f"api_p95_ms {p95_ms:.2f} exceeded threshold {max_p95_ms:.2f}"
                )
            if p95_hot_ms > max_p95_hot_ms:
                ok = False
                gate_failures.append(
                    f"api_p95_hot_ms {p95_hot_ms:.2f} exceeded threshold {max_p95_hot_ms:.2f}"
                )

    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "ok": ok,
        "sections": sections,
        "gates": {
            "api_latency": {
                "max_avg_ms": float(os.environ.get("GUPPY_STRESS_MAX_API_AVG_MS", "1500")),
                "max_p95_ms": float(os.environ.get("GUPPY_STRESS_MAX_API_P95_MS", "5000")),
                "max_p95_hot_ms": float(os.environ.get("GUPPY_STRESS_MAX_API_P95_HOT_MS", "1100")),
            },
            "failures": gate_failures,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Extensive local stress test harness for Guppy runtime")
    parser.add_argument("--api-requests", type=int, default=500)
    parser.add_argument("--api-workers", type=int, default=20)
    parser.add_argument("--route-iterations", type=int, default=5000)
    parser.add_argument("--reminders", type=int, default=250)
    parser.add_argument("--log-events", type=int, default=3000)
    args = parser.parse_args()

    result = run_stress(
        api_requests=args.api_requests,
        api_workers=args.api_workers,
        route_iterations=args.route_iterations,
        reminders=args.reminders,
        log_events=args.log_events,
    )

    runtime_dir = Path(__file__).resolve().parent.parent / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    out = runtime_dir / f"stress_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(json.dumps(result, indent=2))
    print(f"\nReport written: {out}")


if __name__ == "__main__":
    main()
