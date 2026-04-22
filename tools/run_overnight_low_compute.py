import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class CmdResult:
    returncode: int
    stdout: str
    stderr: str


def run_cmd(args: list[str], timeout_s: int) -> CmdResult:
    proc = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_s,
    )
    return CmdResult(proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip())


def run_step(name: str, args: list[str], timeout_s: int) -> dict:
    started = datetime.now(timezone.utc).isoformat()
    res = run_cmd(args, timeout_s=timeout_s)
    ended = datetime.now(timezone.utc).isoformat()
    ok = res.returncode == 0
    return {
        "name": name,
        "ok": ok,
        "returncode": res.returncode,
        "command": " ".join(args),
        "started_utc": started,
        "ended_utc": ended,
        "stdout_tail": res.stdout[-2000:],
        "stderr_tail": res.stderr[-2000:],
    }


def gate_status_from_report(path: Path) -> str:
    if not path.exists():
        return "unknown"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        verdict = str(payload.get("verdict", "unknown")).strip().upper()
        return verdict or "unknown"
    except Exception:
        return "unknown"


def write_morning_summary(path: Path, run_report: dict) -> None:
    steps = run_report.get("steps", [])
    passed = sum(1 for s in steps if s.get("ok"))
    total = len(steps)
    final_gate = run_report.get("final_gate_verdict", "unknown")
    ts = run_report.get("timestamp_utc", "")

    lines = [
        "# Overnight Low-Compute Summary",
        "",
        f"Timestamp (UTC): {ts}",
        f"Run result: {run_report.get('result', 'UNKNOWN')}",
        f"Final pilot verdict: {final_gate}",
        f"Steps passed: {passed}/{total}",
        "",
        "## Step Results",
    ]
    for s in steps:
        status = "PASS" if s.get("ok") else "FAIL"
        lines.append(f"- [{status}] {s.get('name', 'step')}")

    lines.extend(
        [
            "",
            "## Morning Actions",
            "- If final pilot verdict is GO or LIMITED_GO, proceed with normal morning boot.",
            "- If any overnight step failed, run targeted verifiers before launch:",
            "  - python tools/verify_logging_health.py --emit-probe --require-fresh-core",
            "  - python tools/verify_ollama_runtime.py --prompt ok",
            "  - python tools/verify_provider_runtime.py",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run overnight low-compute health cadence and emit a morning summary."
    )
    parser.add_argument("--python", default=sys.executable, help="Python executable to use.")
    parser.add_argument(
        "--cycles",
        type=int,
        default=3,
        help="Number of low-compute cycles to run overnight.",
    )
    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=180,
        help="Minutes between cycles.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Per-step timeout in seconds.",
    )
    parser.add_argument(
        "--skip-final-full-ping",
        action="store_true",
        help="Skip final full ollama ping check.",
    )
    parser.add_argument(
        "--report",
        default="runtime/overnight_low_compute_report.json",
        help="JSON report output path.",
    )
    parser.add_argument(
        "--summary",
        default="runtime/overnight_morning_summary.md",
        help="Markdown morning summary output path.",
    )
    parser.add_argument(
        "--triage-summary",
        default="runtime/nightly_triage_summary.md",
        help="Markdown triage summary output path.",
    )
    args = parser.parse_args()

    ts = datetime.now(timezone.utc).isoformat()
    steps: list[dict] = []

    # Baseline gate before overnight loop.
    steps.append(
        run_step(
            "baseline_pilot_gate",
            [args.python, "tools/pilot_exit_check.py", "--allow-limited-go", "--python", args.python],
            timeout_s=args.timeout,
        )
    )

    cycles = max(1, int(args.cycles))
    interval_s = max(0, int(args.interval_minutes) * 60)
    for i in range(cycles):
        steps.append(
            run_step(
                f"cycle_{i+1}_logging_health",
                [
                    args.python,
                    "tools/verify_logging_health.py",
                    "--emit-probe",
                    "--require-fresh-core",
                ],
                timeout_s=args.timeout,
            )
        )
        steps.append(
            run_step(
                f"cycle_{i+1}_ollama_skip_ping",
                [args.python, "tools/verify_ollama_runtime.py", "--skip-ping"],
                timeout_s=args.timeout,
            )
        )
        if i < cycles - 1 and interval_s > 0:
            time.sleep(interval_s)

    if not args.skip_final_full_ping:
        steps.append(
            run_step(
                "final_ollama_full_ping",
                [args.python, "tools/verify_ollama_runtime.py", "--prompt", "ok"],
                timeout_s=args.timeout,
            )
        )

    steps.append(
        run_step(
            "final_pilot_gate",
            [args.python, "tools/pilot_exit_check.py", "--allow-limited-go", "--python", args.python],
            timeout_s=args.timeout,
        )
    )

    final_gate_verdict = gate_status_from_report(Path("runtime/pilot_exit_report.json"))
    all_ok = all(bool(s.get("ok")) for s in steps)
    result = "PASS" if all_ok and final_gate_verdict in {"GO", "LIMITED_GO"} else "ATTENTION"

    report_payload = {
        "timestamp_utc": ts,
        "result": result,
        "final_gate_verdict": final_gate_verdict,
        "cycles": cycles,
        "interval_minutes": int(args.interval_minutes),
        "steps": steps,
    }

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")

    write_morning_summary(Path(args.summary), report_payload)

    triage_step = run_step(
        "nightly_triage_summary",
        [
            args.python,
            "tools/generate_triage_summary.py",
            "--pilot",
            "runtime/pilot_exit_report.json",
            "--logging",
            "runtime/logging_health_snapshot.json",
            "--overnight",
            str(report_path),
            "--summary",
            args.triage_summary,
        ],
        timeout_s=args.timeout,
    )
    steps.append(triage_step)
    report_path.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")

    print("=== Overnight Low-Compute Runner ===")
    print(f"Timestamp (UTC): {ts}")
    print(f"Cycles: {cycles} | Interval minutes: {int(args.interval_minutes)}")
    print(f"Final pilot verdict: {final_gate_verdict}")
    print(f"Result: {result}")
    print(f"Report: {report_path}")
    print(f"Summary: {args.summary}")
    print(f"Triage summary: {args.triage_summary}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())