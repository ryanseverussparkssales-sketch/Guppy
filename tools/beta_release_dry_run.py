import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"


def run_cmd(args: list[str]) -> dict:
    try:
        proc = subprocess.run(
            args,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=900,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "cmd": args,
            "stdout_tail": (proc.stdout or "")[-3000:],
            "stderr_tail": (proc.stderr or "")[-1500:],
        }
    except Exception as exc:
        return {
            "ok": False,
            "returncode": -1,
            "cmd": args,
            "stdout_tail": "",
            "stderr_tail": str(exc),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one-command remote beta release dry-run checks.")
    parser.add_argument("--report", default="runtime/beta_release_dry_run_report.json")
    parser.add_argument("--skip-pilot", action="store_true")
    args = parser.parse_args()

    py = sys.executable
    checks: list[dict] = []

    checks.append(
        {
            "name": "beta_policy",
            **run_cmd([py, "tools/verify_beta_package_policy.py"]),
        }
    )

    if not args.skip_pilot:
        checks.append(
            {
                "name": "pilot_gate",
                **run_cmd([py, "tools/pilot_exit_check.py", "--allow-limited-go"]),
            }
        )

    required_files = [
        ROOT / "config" / "beta_tool_allowlist.txt",
        ROOT / "docs" / "REMOTE_BETA_EXE_POLICY.md",
        ROOT / "docs" / "FINAL_HANDOFF_PREP.md",
    ]
    file_checks = [{"path": str(p), "exists": p.exists()} for p in required_files]
    files_ok = all(x["exists"] for x in file_checks)

    ok = all(c["ok"] for c in checks) and files_ok

    payload = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "ok": ok,
        "checks": checks,
        "required_files": file_checks,
        "beta_restricted_mode_env": os.environ.get("GUPPY_BETA_RESTRICTED_MODE", ""),
    }

    report_path = ROOT / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("=== Beta Release Dry Run ===")
    print(f"Timestamp (UTC): {payload['timestamp_utc']}")
    print(f"Checks: {len(checks)}")
    print(f"Required files OK: {files_ok}")
    print(f"Report: {report_path}")
    print("Result: PASS" if ok else "Result: FAIL")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
