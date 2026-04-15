import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class CmdResult:
    returncode: int
    stdout: str
    stderr: str


def run_cmd(args: list[str], timeout_s: int = 300) -> CmdResult:
    proc = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_s,
    )
    return CmdResult(proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip())


def _gate_exception_result(*, gate_id: str, name: str, mandatory: bool, command: str, exc: Exception) -> dict:
    detail = f"{type(exc).__name__}: {exc}"
    return {
        "id": gate_id,
        "name": name,
        "passed": False,
        "mandatory": mandatory,
        "command": command,
        "returncode": -1,
        "summary": f"Gate execution failed: {detail}",
        "stdout_tail": "",
        "stderr_tail": detail[-2000:],
    }


def gate_runtime_smoke(py: str, timeout_s: int) -> dict:
    args = [
        py,
        "-m",
        "pytest",
        "-q",
        "tests/smoke/test_runtime_smoke.py",
        "tests/smoke/test_launcher_interactions_smoke.py",
        "tests/unit/test_personalization_resolution.py",
        "tests/unit/test_models_routes.py",
        "tests/unit/test_voices_view_validation.py",
        "tests/unit/test_personalization_config_scaffold.py",
        "tests/unit/test_tool_schema_audit.py",
    ]
    try:
        res = run_cmd(args, timeout_s=timeout_s)
    except Exception as exc:
        return _gate_exception_result(
            gate_id="gate_1_core_runtime_stability",
            name="Core runtime stability",
            mandatory=True,
            command=" ".join(args),
            exc=exc,
        )
    passed = res.returncode == 0
    return {
        "id": "gate_1_core_runtime_stability",
        "name": "Core runtime stability",
        "passed": passed,
        "mandatory": True,
        "command": " ".join(args),
        "returncode": res.returncode,
        "summary": "Smoke suite passed" if passed else "Smoke suite failed",
        "stdout_tail": res.stdout[-2000:],
        "stderr_tail": res.stderr[-2000:],
    }


def gate_ollama(py: str, timeout_s: int, prompt: str) -> dict:
    args = [py, "tools/verify_ollama_runtime.py", "--prompt", prompt]
    try:
        res = run_cmd(args, timeout_s=timeout_s)
    except Exception as exc:
        return _gate_exception_result(
            gate_id="gate_2_local_model_fleet_ready",
            name="Local model fleet ready",
            mandatory=True,
            command=" ".join(args),
            exc=exc,
        )
    passed = res.returncode == 0
    return {
        "id": "gate_2_local_model_fleet_ready",
        "name": "Local model fleet ready",
        "passed": passed,
        "mandatory": True,
        "command": " ".join(args),
        "returncode": res.returncode,
        "summary": "Ollama fleet verifier READY" if passed else "Ollama fleet verifier NOT READY",
        "stdout_tail": res.stdout[-2000:],
        "stderr_tail": res.stderr[-2000:],
        "snapshot": "runtime/model_runtime_snapshot.json",
    }


def gate_logging(py: str, timeout_s: int) -> dict:
    args = [
        py,
        "tools/verify_logging_health.py",
        "--emit-probe",
        "--require-fresh-core",
    ]
    try:
        res = run_cmd(args, timeout_s=timeout_s)
    except Exception as exc:
        return _gate_exception_result(
            gate_id="gate_3_product_telemetry_health",
            name="Product telemetry health",
            mandatory=True,
            command=" ".join(args),
            exc=exc,
        )
    passed = res.returncode == 0
    return {
        "id": "gate_3_product_telemetry_health",
        "name": "Product telemetry health",
        "passed": passed,
        "mandatory": True,
        "command": " ".join(args),
        "returncode": res.returncode,
        "summary": "Logging verifier READY" if passed else "Logging verifier NOT READY",
        "stdout_tail": res.stdout[-2000:],
        "stderr_tail": res.stderr[-2000:],
        "snapshot": "runtime/logging_health_snapshot.json",
    }


def gate_provider(py: str, timeout_s: int) -> dict:
    args = [py, "tools/verify_provider_runtime.py"]
    try:
        res = run_cmd(args, timeout_s=timeout_s)
    except Exception as exc:
        return _gate_exception_result(
            gate_id="gate_5_provider_fallback_baseline",
            name="Provider fallback baseline",
            mandatory=False,
            command=" ".join(args),
            exc=exc,
        )
    passed = res.returncode == 0
    return {
        "id": "gate_5_provider_fallback_baseline",
        "name": "Provider fallback baseline",
        "passed": passed,
        "mandatory": False,
        "command": " ".join(args),
        "returncode": res.returncode,
        "summary": "Provider verifier READY" if passed else "Provider verifier NOT READY",
        "stdout_tail": res.stdout[-2000:],
        "stderr_tail": res.stderr[-2000:],
        "snapshot": "runtime/provider_runtime_snapshot.json",
    }


def gate_lifecycle_dry_run(py: str, timeout_s: int) -> dict:
    args = [
        py,
        "tools/validate_live_lifecycle.py",
        "--mode",
        "dry",
        "--report",
        "runtime/lifecycle_validation_report.json",
    ]
    try:
        res = run_cmd(args, timeout_s=timeout_s)
    except Exception as exc:
        return _gate_exception_result(
            gate_id="gate_6_lifecycle_dry_run",
            name="Lifecycle dry-run validation",
            mandatory=False,
            command=" ".join(args),
            exc=exc,
        )
    passed = res.returncode == 0
    return {
        "id": "gate_6_lifecycle_dry_run",
        "name": "Lifecycle dry-run validation",
        "passed": passed,
        "mandatory": False,
        "command": " ".join(args),
        "returncode": res.returncode,
        "summary": "Lifecycle dry-run validation passed" if passed else "Lifecycle dry-run validation failed",
        "stdout_tail": res.stdout[-2000:],
        "stderr_tail": res.stderr[-2000:],
        "snapshot": "runtime/lifecycle_validation_report.json",
    }


def decide(gates: list[dict], allow_limited_go: bool) -> tuple[str, str]:
    mandatory = [g for g in gates if g.get("mandatory", False)]
    optional = [g for g in gates if not g.get("mandatory", False)]
    mandatory_pass = all(g.get("passed", False) for g in mandatory)
    optional_pass = all(g.get("passed", False) for g in optional) if optional else True

    if mandatory_pass and optional_pass:
        return "GO", "All mandatory and optional pilot gates passed."
    if mandatory_pass and allow_limited_go:
        failed_optional = [g["id"] for g in optional if not g.get("passed", False)]
        if failed_optional:
            return (
                "LIMITED_GO",
                "Mandatory gates passed; optional provider baseline failed: " + ", ".join(failed_optional),
            )
    return "NO_GO", "One or more mandatory pilot gates failed."


def print_gate(gate: dict) -> None:
    status = "PASS" if gate.get("passed") else "FAIL"
    kind = "MANDATORY" if gate.get("mandatory") else "OPTIONAL"
    print(f"- [{status}] {gate['name']} ({kind})")
    print(f"  {gate.get('summary', '')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run pilot exit gates and emit GO/NO-GO report.")
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable used to run gate scripts/tests.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Per-gate timeout in seconds.",
    )
    parser.add_argument(
        "--ollama-prompt",
        default="Reply with exactly OK",
        help="Prompt used by Ollama runtime verifier.",
    )
    parser.add_argument(
        "--allow-limited-go",
        action="store_true",
        help="Allow LIMITED_GO when mandatory gates pass but optional provider gate fails.",
    )
    parser.add_argument(
        "--report",
        default="runtime/pilot_exit_report.json",
        help="JSON output path for consolidated pilot report.",
    )
    args = parser.parse_args()

    ts = datetime.now(timezone.utc).isoformat()
    print("=== Guppy Pilot Exit Check ===")
    print(f"Timestamp (UTC): {ts}")
    print(f"Python: {args.python}")
    print()

    gates = [
        gate_runtime_smoke(args.python, timeout_s=args.timeout),
        gate_ollama(args.python, timeout_s=args.timeout, prompt=args.ollama_prompt),
        gate_logging(args.python, timeout_s=args.timeout),
        gate_provider(args.python, timeout_s=args.timeout),
        gate_lifecycle_dry_run(args.python, timeout_s=args.timeout),
    ]

    print("Gate results")
    for gate in gates:
        print_gate(gate)

    verdict, reason = decide(gates, allow_limited_go=args.allow_limited_go)
    score = sum(1 for g in gates if g.get("passed", False))

    report = {
        "timestamp_utc": ts,
        "verdict": verdict,
        "reason": reason,
        "score": {
            "passed": score,
            "total": len(gates),
        },
        "rules": {
            "go": "all mandatory and optional pass",
            "limited_go": "mandatory pass and optional provider gate fails (when --allow-limited-go)",
            "no_go": "any mandatory gate fails",
        },
        "gates": gates,
    }

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print()
    print(f"Score: {score}/{len(gates)}")
    print(f"Verdict: {verdict}")
    print(f"Reason: {reason}")
    print(f"Report: {report_path}")

    if verdict == "GO":
        return 0
    if verdict == "LIMITED_GO":
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
