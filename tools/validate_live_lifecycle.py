"""Controlled lifecycle validation for hub-managed services.

Runs start/stop/restart checks while preserving initial service states.

Usage:
  python tools/validate_live_lifecycle.py --mode dry
  python tools/validate_live_lifecycle.py --mode live
"""

from __future__ import annotations

import argparse
import json
import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.hub_operator import get_operator

SERVICES = ("api", "cloudflared", "ollama")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("dry", "live"), default="dry")
    args = ap.parse_args()

    dry_run = args.mode == "dry"
    op = get_operator()

    report: dict = {"mode": args.mode, "initial": {}, "actions": [], "final": {}}

    for svc in SERVICES:
        report["initial"][svc] = op._check_service_running(svc)

    for svc in SERVICES:
        initial_running = report["initial"][svc]
        row = {"service": svc, "initial_running": initial_running, "steps": []}

        if initial_running:
            res = op.restart_service(svc, dry_run=dry_run)
            if not dry_run:
                time.sleep(1.0)
            row["steps"].append(
                {
                    "op": "restart",
                    "result": res,
                    "running_after": op._check_service_running(svc),
                }
            )
        else:
            res_start = op.start_service(svc, dry_run=dry_run)
            if not dry_run:
                time.sleep(1.0)
            row["steps"].append(
                {
                    "op": "start",
                    "result": res_start,
                    "running_after": op._check_service_running(svc),
                }
            )

            # Restore original stopped state.
            res_stop = op.stop_service(svc, dry_run=dry_run)
            if not dry_run:
                time.sleep(1.0)
            row["steps"].append(
                {
                    "op": "stop",
                    "result": res_stop,
                    "running_after": op._check_service_running(svc),
                }
            )

        report["actions"].append(row)

    for svc in SERVICES:
        report["final"][svc] = op._check_service_running(svc)

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
