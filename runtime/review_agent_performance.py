import json
from collections import Counter
from pathlib import Path
from statistics import mean

LOG_PATH = Path(__file__).resolve().parent / "agent_performance.jsonl"


def load_events():
    if not LOG_PATH.exists():
        return []
    events = []
    with LOG_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def summarize(events):
    if not events:
        print("No performance events found.")
        return

    recent = [e for e in events[-200:] if e.get("event") == "request_complete"]
    if not recent:
        print("No request_complete events in last 200 entries.")
        return

    by_agent = {}
    for e in recent:
        by_agent.setdefault(e.get("agent", "unknown"), []).append(e)

    print(f"Loaded {len(events)} events. Showing summary for last {len(recent)} completed requests.")
    for agent, rows in by_agent.items():
        latencies = [r["latency_ms"] for r in rows if isinstance(r.get("latency_ms"), (int, float))]
        failures  = [r for r in rows if r.get("status") == "error"]
        tools     = [r["tool_calls"] for r in rows if isinstance(r.get("tool_calls"), int)]
        fallbacks = [r for r in rows if r.get("fallback_used")]
        cache_hits = [r for r in rows if r.get("route") == "cache" or r.get("model_used") == "cache"]
        voice_reqs = [r for r in rows if r.get("voice_triggered")]

        task_counts  = Counter(r.get("task_type", "unknown") for r in rows)
        route_counts = Counter(r.get("route", "unknown") for r in rows)
        model_counts = Counter(r.get("model_used", "unknown") for r in rows if r.get("model_used"))

        print("-" * 68)
        print(f"Agent: {agent}  ({len(rows)} requests)")
        print(f"  failures:    {len(failures)}")
        print(f"  cache hits:  {len(cache_hits)}  ({100*len(cache_hits)//max(len(rows),1)}%)")
        print(f"  voice reqs:  {len(voice_reqs)}")
        print(f"  fallbacks:   {len(fallbacks)}")
        if latencies:
            p95_idx = max(0, int(len(latencies) * 0.95) - 1)
            print(f"  latency avg: {mean(latencies):.0f} ms")
            print(f"  latency p95: {sorted(latencies)[p95_idx]:.0f} ms")
        if tools:
            print(f"  avg tools/req: {mean(tools):.2f}")
        if task_counts:
            print(f"  task types:  {dict(task_counts)}")
        if route_counts:
            print(f"  routes:      {dict(route_counts)}")
        if model_counts:
            print(f"  models used: {dict(model_counts)}")


def show_tail(events, n=20):
    complete = [e for e in events if e.get("event") == "request_complete"]
    if not complete:
        return
    tail = complete[-n:]
    print("-" * 68)
    print(f"Last {len(tail)} completed requests:")
    for e in tail:
        ts      = e.get("ts", "")[:19]
        mode    = e.get("mode", "?")
        route   = e.get("route", "?")
        task    = e.get("task_type", "?")
        model   = e.get("model_used", "?")
        latency = e.get("latency_ms", "?")
        status  = e.get("status", "?")
        voice   = " [voice]" if e.get("voice_triggered") else ""
        print(f"  {ts}  {mode}/{route}/{task}  model={model}  {latency}ms  {status}{voice}")


if __name__ == "__main__":
    ev = load_events()
    summarize(ev)
    show_tail(ev, n=15)
