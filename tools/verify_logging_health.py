import argparse
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


RUNTIME = Path("runtime")
TRACKED_LOGS = [
    "session_events.jsonl",
    "integration_events.jsonl",
    "hub_patterns.jsonl",
    "reminder_events.jsonl",
    "router_scorecard.jsonl",
    "agent_performance.jsonl",
]
CORE_FRESH_LOGS = [
    "session_events.jsonl",
    "router_scorecard.jsonl",
    "agent_performance.jsonl",
]


def _freshness_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _is_fresh(path: Path, max_age_minutes: int) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc) >= cutoff


def _sqlite_summary(db_path: Path) -> dict:
    if not db_path.exists():
        return {"exists": False, "tables": {}}
    tables: dict[str, int] = {}
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        names = [r[0] for r in cur.fetchall()]
        for name in names:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {name}")
                tables[name] = int(cur.fetchone()[0])
            except Exception:
                tables[name] = -1
    return {"exists": True, "tables": tables}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Guppy runtime logging health.")
    parser.add_argument("--max-age-minutes", type=int, default=120)
    parser.add_argument("--emit-probe", action="store_true", help="Write a probe event JSONL entry.")
    parser.add_argument(
        "--require-fresh-core",
        action="store_true",
        help="Require core streams to be fresh for READY status.",
    )
    parser.add_argument("--snapshot-file", default="runtime/logging_health_snapshot.json")
    args = parser.parse_args()

    ts = datetime.now(timezone.utc).isoformat()
    RUNTIME.mkdir(parents=True, exist_ok=True)

    if args.emit_probe:
        probe = {
            "ts": ts,
            "event": "logging_health_probe",
            "source": "tools/verify_logging_health.py",
        }
        for probe_name in ["session_events.jsonl", "agent_performance.jsonl", "router_scorecard.jsonl"]:
            probe_path = RUNTIME / probe_name
            with probe_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(probe) + "\n")

    print("=== Guppy Logging Health Verifier ===")
    print(f"Timestamp (UTC): {ts}")

    files: dict[str, dict] = {}
    print("\n[1] Runtime log files")
    for rel in TRACKED_LOGS:
        p = RUNTIME / rel
        if p.exists():
            fresh = _is_fresh(p, args.max_age_minutes)
            files[rel] = {
                "exists": True,
                "size": p.stat().st_size,
                "mtime_utc": _freshness_iso(p),
                "fresh": fresh,
            }
            print(f"- {'OK' if fresh else 'STALE'} {rel} ({p.stat().st_size} bytes)")
        else:
            files[rel] = {"exists": False, "fresh": False}
            print(f"- MISSING {rel}")

    print("\n[2] SQLite telemetry mirror")
    sqlite_path = RUNTIME / "ops_telemetry.sqlite3"
    sqlite_info = _sqlite_summary(sqlite_path)
    if sqlite_info["exists"]:
        print(f"- OK {sqlite_path}")
        for name, count in sqlite_info["tables"].items():
            print(f"  - {name}: {count}")
    else:
        print("- MISSING runtime/ops_telemetry.sqlite3")

    out = {
        "timestamp_utc": ts,
        "max_age_minutes": args.max_age_minutes,
        "files": files,
        "sqlite": sqlite_info,
        "require_fresh_core": bool(args.require_fresh_core),
        "core_fresh_logs": CORE_FRESH_LOGS,
    }
    out_path = Path(args.snapshot_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nSnapshot written: {out_path}")

    any_present = any(v.get("exists", False) for v in files.values())
    ready = any_present and sqlite_info.get("exists", False)
    if args.require_fresh_core:
        core_missing_or_stale = [
            name
            for name in CORE_FRESH_LOGS
            if not files.get(name, {}).get("exists") or not files.get(name, {}).get("fresh")
        ]
        if core_missing_or_stale:
            ready = False
            print("Core streams not fresh: " + ", ".join(core_missing_or_stale))
    print("Overall:", "READY" if ready else "NOT READY")
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
