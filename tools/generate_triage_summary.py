import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUNTIME = Path("runtime")


def _load_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(fallback)


def _recent_offhours_failures(path: Path, max_lines: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    out: list[dict[str, Any]] = []
    for raw in reversed(lines[-max_lines:]):
        try:
            row = json.loads(raw)
        except Exception:
            continue
        if row.get("event") != "offhours_task_complete":
            continue
        if row.get("ok") is False:
            out.append(row)
    return out[:10]


def _gate_failures(pilot: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for gate in pilot.get("gates", []):
        if not gate.get("passed", False):
            fails.append(str(gate.get("id", gate.get("name", "unknown_gate"))))
    return fails


def _core_stale(logging_snapshot: dict[str, Any]) -> list[str]:
    files = logging_snapshot.get("files", {})
    stale: list[str] = []
    for name in logging_snapshot.get("core_fresh_logs", []):
        rec = files.get(name, {})
        if not rec.get("exists") or not rec.get("fresh"):
            stale.append(str(name))
    return stale


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate nightly triage summary and regression flags.")
    parser.add_argument("--pilot", default="runtime/pilot_exit_report.json")
    parser.add_argument("--logging", dest="logging_path", default="runtime/logging_health_snapshot.json")
    parser.add_argument("--overnight", default="runtime/overnight_low_compute_report.json")
    parser.add_argument("--offhours", default="runtime/offhours_task_results.jsonl")
    parser.add_argument("--state", default="runtime/triage_regression_state.json")
    parser.add_argument("--summary", default="runtime/nightly_triage_summary.md")
    parser.add_argument("--max-offhours-lines", type=int, default=300)
    args = parser.parse_args()

    ts = datetime.now(timezone.utc).isoformat()
    pilot = _load_json(Path(args.pilot), {"verdict": "UNKNOWN", "gates": []})
    logging_snapshot = _load_json(Path(args.logging_path), {"files": {}, "core_fresh_logs": []})
    overnight = _load_json(Path(args.overnight), {"result": "UNKNOWN", "steps": []})
    prior_state = _load_json(Path(args.state), {})

    verdict = str(pilot.get("verdict", "UNKNOWN")).upper()
    failed_gates = _gate_failures(pilot)
    stale_core = _core_stale(logging_snapshot)
    offhours_failures = _recent_offhours_failures(Path(args.offhours), args.max_offhours_lines)

    alerts: list[str] = []
    if verdict not in {"GO", "LIMITED_GO"}:
        alerts.append(f"pilot_verdict={verdict}")
    if failed_gates:
        alerts.append("failed_gates=" + ", ".join(failed_gates))
    if stale_core:
        alerts.append("stale_core_streams=" + ", ".join(stale_core))
    if offhours_failures:
        alerts.append(f"offhours_failures={len(offhours_failures)}")

    prior_failed = set(prior_state.get("failed_gates", []))
    now_failed = set(failed_gates)
    new_failures = sorted(now_failed - prior_failed)
    recovered = sorted(prior_failed - now_failed)
    regression = bool(new_failures or (prior_state.get("verdict") in {"GO", "LIMITED_GO"} and verdict not in {"GO", "LIMITED_GO"}))

    score = {
        "pilot_ready": verdict in {"GO", "LIMITED_GO"},
        "gate_failures": len(failed_gates),
        "stale_core": len(stale_core),
        "offhours_failures": len(offhours_failures),
        "regression": regression,
    }

    summary_lines = [
        "# Nightly Triage Summary",
        "",
        f"Timestamp (UTC): {ts}",
        f"Pilot verdict: {verdict}",
        f"Overnight run result: {overnight.get('result', 'UNKNOWN')}",
        "",
        "## Alerts",
    ]
    if alerts:
        summary_lines.extend([f"- {a}" for a in alerts])
    else:
        summary_lines.append("- none")

    summary_lines.extend(
        [
            "",
            "## Regression Signals",
            f"- regression: {'YES' if regression else 'NO'}",
            f"- new_failures: {', '.join(new_failures) if new_failures else 'none'}",
            f"- recovered: {', '.join(recovered) if recovered else 'none'}",
            "",
            "## Scorecard",
            f"- pilot_ready: {score['pilot_ready']}",
            f"- gate_failures: {score['gate_failures']}",
            f"- stale_core: {score['stale_core']}",
            f"- offhours_failures: {score['offhours_failures']}",
            "",
            "## Suggested Morning Action",
        ]
    )

    if regression or alerts:
        summary_lines.extend(
            [
                "- Run targeted verifiers before full launch:",
                "  - python tools/verify_logging_health.py --emit-probe --require-fresh-core",
                "  - python tools/verify_ollama_runtime.py --prompt ok",
                "  - python tools/verify_provider_runtime.py",
            ]
        )
    else:
        summary_lines.append("- Proceed with normal morning boot.")

    summary_path = Path(args.summary)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    state_payload = {
        "timestamp_utc": ts,
        "verdict": verdict,
        "failed_gates": failed_gates,
        "stale_core": stale_core,
        "offhours_failures": len(offhours_failures),
        "regression": regression,
    }
    state_path = Path(args.state)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state_payload, indent=2), encoding="utf-8")

    print("=== Triage Summary Generator ===")
    print(f"Timestamp (UTC): {ts}")
    print(f"Pilot verdict: {verdict}")
    print(f"Alerts: {len(alerts)}")
    print(f"Regression: {'YES' if regression else 'NO'}")
    print(f"Summary: {summary_path}")
    print(f"State: {state_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
