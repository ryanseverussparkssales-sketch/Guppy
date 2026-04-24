import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inject synthetic failures to verify nightly triage alerting without mutating live runtime files."
    )
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--out-dir", default="runtime/canary")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).isoformat()

    pilot_path = out_dir / "pilot_exit_report_fault.json"
    logging_path = out_dir / "logging_health_snapshot_fault.json"
    overnight_path = out_dir / "overnight_low_compute_report_fault.json"
    offhours_path = out_dir / "offhours_task_results_fault.jsonl"
    state_path = out_dir / "triage_regression_state_fault.json"
    summary_path = out_dir / "nightly_triage_summary_fault.md"

    pilot_payload = {
        "timestamp_utc": ts,
        "verdict": "NO_GO",
        "gates": [
            {
                "id": "gate_1_core_runtime_stability",
                "passed": False,
                "mandatory": True,
            },
            {
                "id": "gate_2_local_model_fleet_ready",
                "passed": True,
                "mandatory": True,
            },
            {
                "id": "gate_5_provider_fallback_baseline",
                "passed": False,
                "mandatory": False,
            },
        ],
    }

    logging_payload = {
        "timestamp_utc": ts,
        "files": {
            "session_events.jsonl": {"exists": True, "fresh": False},
            "router_scorecard.jsonl": {"exists": True, "fresh": True},
            "agent_performance.jsonl": {"exists": True, "fresh": True},
        },
        "core_fresh_logs": [
            "session_events.jsonl",
            "router_scorecard.jsonl",
            "agent_performance.jsonl",
        ],
    }

    overnight_payload = {
        "timestamp_utc": ts,
        "result": "ATTENTION",
        "final_gate_verdict": "NO_GO",
        "steps": [],
    }

    prior_state = {
        "timestamp_utc": ts,
        "verdict": "GO",
        "failed_gates": [],
        "stale_core": [],
        "offhours_failures": 0,
        "regression": False,
    }

    _write_json(pilot_path, pilot_payload)
    _write_json(logging_path, logging_payload)
    _write_json(overnight_path, overnight_payload)
    _write_json(state_path, prior_state)
    offhours_path.write_text(
        json.dumps(
            {
                "ts": ts,
                "event": "offhours_task_complete",
                "task_id": "fault_case",
                "ok": False,
                "status": "failed",
                "error": "synthetic failure",
            },
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
    )

    cmd = [
        args.python,
        "tools/generate_triage_summary.py",
        "--pilot",
        str(pilot_path),
        "--logging",
        str(logging_path),
        "--overnight",
        str(overnight_path),
        "--offhours",
        str(offhours_path),
        "--state",
        str(state_path),
        "--summary",
        str(summary_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")

    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        print("FAIL: triage summary generator returned non-zero")
        return 1

    summary_text = summary_path.read_text(encoding="utf-8", errors="ignore") if summary_path.exists() else ""
    required_markers = [
        "pilot_verdict=NO_GO",
        "failed_gates=gate_1_core_runtime_stability, gate_5_provider_fallback_baseline",
        "stale_core_streams=session_events.jsonl",
        "offhours_failures=1",
        "regression: YES",
    ]

    missing = [m for m in required_markers if m not in summary_text]
    if missing:
        print("FAIL: canary summary missing expected markers")
        for marker in missing:
            print(f"- missing: {marker}")
        print(f"Summary path: {summary_path}")
        return 1

    print("=== Triage Fault Canary ===")
    print("Result: PASS")
    print(f"Summary: {summary_path}")
    print(f"State: {state_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
