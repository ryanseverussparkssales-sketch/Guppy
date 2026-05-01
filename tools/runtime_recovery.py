#!/usr/bin/env python
"""One-command runtime recovery + verification pass for Guppy.

Runs the core checks needed to validate agents, chat/API, voice, and challenger
readiness. Exits non-zero when critical checks fail.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "http://127.0.0.1:8080"


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    critical: bool = True


def _run_py(tool_path: str, *args: str) -> tuple[bool, str]:
    command = [sys.executable, str(REPO_ROOT / tool_path), *args]
    proc = subprocess.run(command, capture_output=True, text=True)
    output = (proc.stdout or "") + (proc.stderr or "")
    output = output.strip()
    if proc.returncode == 0:
        return True, output.splitlines()[-1] if output else "ok"
    tail = "\n".join(output.splitlines()[-20:]) if output else "no output"
    return False, tail


def _http_get(url: str, timeout: float = 8.0) -> tuple[bool, str]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            if resp.status >= 400:
                return False, f"HTTP {resp.status}: {body[:400]}"
            return True, body[:400]
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return False, f"HTTP {exc.code}: {body[:400]}"
    except Exception as exc:
        return False, str(exc)


def _http_post_json(url: str, payload: dict, timeout: float = 12.0) -> tuple[bool, str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            if resp.status >= 400:
                return False, f"HTTP {resp.status}: {body[:400]}"
            return True, body[:400]
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return False, f"HTTP {exc.code}: {body[:400]}"
    except Exception as exc:
        return False, str(exc)


def _start_backends(base_url: str) -> list[CheckResult]:
    checks: list[CheckResult] = []
    for backend in ("llamacpp-dispatch", "llamacpp-hermes4", "llamacpp-hermes3", "llamacpp-xlam"):
        ok, detail = _http_post_json(f"{base_url}/api/backends/llamacpp/{backend}/start", {})
        checks.append(CheckResult(name=f"start:{backend}", ok=ok, detail=detail, critical=False))
    return checks


def _chat_probe(base_url: str) -> CheckResult:
    payload = {
        "message": "health probe",
    }
    ok, detail = _http_post_json(f"{base_url}/api/conversations/chat/stream", payload)
    if ok:
        return CheckResult(name="chat_probe", ok=True, detail="stream endpoint reachable")

    # If auth is enforced this may return 401/403, which means routing is alive.
    if "HTTP 401" in detail or "HTTP 403" in detail:
        return CheckResult(name="chat_probe", ok=True, detail=f"reachable with auth required ({detail})")
    return CheckResult(name="chat_probe", ok=False, detail=detail)


def run_recovery(base_url: str, start_backends: bool) -> int:
    results: list[CheckResult] = []

    if start_backends:
        results.extend(_start_backends(base_url))

    ok, detail = _http_get(f"{base_url}/health")
    results.append(CheckResult(name="api_health", ok=ok, detail=detail))

    ok, detail = _http_get(f"{base_url}/api/status")
    results.append(CheckResult(name="api_status", ok=ok, detail=detail))

    results.append(_chat_probe(base_url))

    ok, detail = _run_py("tools/verify_tool_agents.py")
    results.append(CheckResult(name="verify_tool_agents", ok=ok, detail=detail))

    ok, detail = _run_py("tools/verify_voice_runtime.py")
    results.append(CheckResult(name="verify_voice_runtime", ok=ok, detail=detail))

    ok, detail = _run_py("tools/verify_runtime_challengers.py")
    results.append(CheckResult(name="verify_runtime_challengers", ok=ok, detail=detail))

    print("\n== Runtime Recovery Summary ==")
    for item in results:
        state = "PASS" if item.ok else "FAIL"
        suffix = " [warn]" if (not item.critical and not item.ok) else ""
        print(f"- {state:<4} {item.name}{suffix}")
        if item.detail:
            print(f"  {item.detail}")

    failed_critical = [item for item in results if item.critical and not item.ok]
    if failed_critical:
        print("\nCritical failures detected.")
        return 1

    print("\nRuntime recovery checks completed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Guppy runtime recovery checks")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Base API URL (default: http://127.0.0.1:8080)")
    parser.add_argument(
        "--start-backends",
        action="store_true",
        help="Call backend start endpoints for dispatch/hermes4/hermes3/xLAM before checks",
    )
    args = parser.parse_args()
    return run_recovery(base_url=args.base_url.rstrip("/"), start_backends=args.start_backends)


if __name__ == "__main__":
    raise SystemExit(main())
