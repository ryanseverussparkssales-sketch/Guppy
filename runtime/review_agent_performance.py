import json
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

    recent = events[-200:]
    by_agent = {}
    for e in recent:
        by_agent.setdefault(e.get("agent", "unknown"), []).append(e)

    print(f"Loaded {len(events)} events. Showing summary for last {len(recent)} events.")
    for agent, rows in by_agent.items():
        latencies = [r.get("latency_ms") for r in rows if isinstance(r.get("latency_ms"), (int, float))]
        failures = [r for r in rows if r.get("status") == "error"]
        tools = [r.get("tool_calls", 0) for r in rows if isinstance(r.get("tool_calls"), int)]
        fallbacks = [r for r in rows if r.get("fallback_used")]

        print("-" * 68)
        print(f"Agent: {agent}")
        print(f"  requests: {len(rows)}")
        print(f"  failures: {len(failures)}")
        if latencies:
            print(f"  latency avg ms: {mean(latencies):.1f}")
            print(f"  latency p95 ms: {sorted(latencies)[int(len(latencies) * 0.95) - 1]:.1f}")
        if tools:
            print(f"  avg tool calls: {mean(tools):.2f}")
        print(f"  fallback count: {len(fallbacks)}")


def show_tail(events, n=20):
    if not events:
        return
    print("-" * 68)
    print(f"Last {min(n, len(events))} events:")
    for e in events[-n:]:
        print(json.dumps(e, ensure_ascii=True))


if __name__ == "__main__":
    ev = load_events()
    summarize(ev)
    show_tail(ev, n=15)
