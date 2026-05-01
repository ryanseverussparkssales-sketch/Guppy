"""
check_runtime_health.py — One-command runtime recovery and health report.

Runs all critical runtime checks in sequence and writes a combined report.

Checks performed (in order):
  1. Provider SDKs      — anthropic, openai importable + versioned
  2. Local models       — llamacpp backend liveness (--skip-ping skips port probes)
  3. Voice engines      — edge_tts, kokoro, pyttsx3, elevenlabs
  4. Tool agents        — dispatch / xLAM / hermes4 liveness + basic tool-call
  5. Chat API           — FastAPI /health endpoint on port 8081
  6. Runtime challengers— probe llama.cpp / lemonade / vllm-rocm snapshot

Writes: runtime/runtime_health_report.json
Exit 0 = all critical checks pass; Exit 1 = one or more critical failures.

Usage:
    python tools/check_runtime_health.py
    python tools/check_runtime_health.py --skip-agents      # skip slow agent checks
    python tools/check_runtime_health.py --json             # JSON-only output
    python tools/check_runtime_health.py --fix              # attempt auto-fixes
"""
from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RUNTIME_DIR = ROOT / "runtime"
REPORT_PATH = RUNTIME_DIR / "runtime_health_report.json"

# ── colour helpers (no deps) ────────────────────────────────────────────────
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def _ok(msg: str) -> None:
    print(f"  {GREEN}✔{RESET}  {msg}")


def _warn(msg: str) -> None:
    print(f"  {YELLOW}⚠{RESET}  {msg}")


def _fail(msg: str) -> None:
    print(f"  {RED}✘{RESET}  {msg}")


def _head(msg: str) -> None:
    print(f"\n{BOLD}{CYAN}{msg}{RESET}")


# ── helpers ─────────────────────────────────────────────────────────────────

def _http_get(url: str, timeout: float = 4.0) -> tuple[int, str]:
    """Return (status_code, body). Returns (-1, reason) on network failure."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, str(exc)
    except Exception as exc:  # noqa: BLE001
        return -1, str(exc)


def _check_port(port: int, timeout: float = 3.0) -> bool:
    status, _ = _http_get(f"http://127.0.0.1:{port}/v1/models", timeout)
    return status == 200


# ── check 1: provider SDKs ──────────────────────────────────────────────────

def check_providers() -> dict:
    _head("1 / 6  Provider SDKs")
    results: dict[str, str] = {}
    critical_fail = False
    for pkg, import_name in [("anthropic", "anthropic"), ("openai", "openai")]:
        try:
            mod = importlib.import_module(import_name)
            ver = getattr(mod, "__version__", "?")
            _ok(f"{pkg} {ver}")
            results[pkg] = ver
        except ImportError as exc:
            _fail(f"{pkg} not importable: {exc}")
            results[pkg] = "MISSING"
            critical_fail = True
    return {"status": "FAIL" if critical_fail else "OK", "packages": results}


# ── check 2: local model backends ──────────────────────────────────────────

BACKEND_PORTS = {
    "dispatch  (Qwen2.5-3B)   ": 8085,
    "hermes3   (Hermes3 8B)   ": 8087,
    "hermes4   (Hermes4 14B)  ": 8086,
    "xlam      (xLAM-2-8B)    ": 8089,
    "rocinante (Rocinante 12B)": 8088,
}

ALWAYS_ON_PORTS = {8085, 8086, 8087}


def check_local_models(skip_ping: bool = False) -> dict:
    _head("2 / 6  Local Model Backends")
    if skip_ping:
        _warn("--skip-ping: port probe skipped")
        return {"status": "SKIPPED", "backends": {}}
    results: dict[str, str] = {}
    any_always_on_down = False
    for name, port in BACKEND_PORTS.items():
        up = _check_port(port)
        label = name.strip()
        if up:
            _ok(f"port {port}  {label}")
            results[label] = "UP"
        else:
            tag = " (always-on)" if port in ALWAYS_ON_PORTS else " (on-demand)"
            _warn(f"port {port}  {label}  DOWN{tag}")
            results[label] = "DOWN"
            if port in ALWAYS_ON_PORTS:
                any_always_on_down = True
    status = "DEGRADED" if any_always_on_down else "OK"
    return {"status": status, "backends": results}


# ── check 3: voice engines ──────────────────────────────────────────────────

VOICE_ENGINES = {
    "EDGE TTS": ("edge_tts", None),
    "KOKORO": ("kokoro", None),
    "WINDOWS SAPI": ("pyttsx3", None),
    "ELEVENLABS": ("elevenlabs", None),
}


def check_voice() -> dict:
    _head("3 / 6  Voice Engines")
    results: dict[str, str] = {}
    any_ready = False
    for name, (pkg, _) in VOICE_ENGINES.items():
        try:
            importlib.import_module(pkg)
            _ok(f"{name}  ({pkg})")
            results[name] = "READY"
            any_ready = True
        except ImportError:
            _warn(f"{name}  ({pkg})  not installed")
            results[name] = "MISSING"
    return {"status": "OK" if any_ready else "NO_ENGINE", "engines": results}


# ── check 4: tool agents ────────────────────────────────────────────────────

AGENT_PORTS = {"dispatch": 8085, "xlam": 8089, "hermes4": 8086}


def check_agents(skip: bool = False) -> dict:
    _head("4 / 6  Tool Agents")
    if skip:
        _warn("--skip-agents: agent liveness check skipped")
        return {"status": "SKIPPED", "agents": {}}
    results: dict[str, str] = {}
    any_down = False
    for name, port in AGENT_PORTS.items():
        up = _check_port(port)
        if up:
            _ok(f"{name}  port {port}")
            results[name] = "UP"
        else:
            _fail(f"{name}  port {port}  DOWN")
            results[name] = "DOWN"
            any_down = True
    return {"status": "DEGRADED" if any_down else "OK", "agents": results}


# ── check 5: chat API ───────────────────────────────────────────────────────

def check_chat_api() -> dict:
    _head("5 / 6  Chat API  (FastAPI :8081)")
    status_code, body = _http_get("http://127.0.0.1:8081/health", timeout=5.0)
    if status_code == 200:
        _ok(f"/health  →  {status_code}")
        try:
            data = json.loads(body)
            srv_status = data.get("status", "ok")
            _ok(f"server status: {srv_status}")
        except json.JSONDecodeError:
            pass
        return {"status": "OK", "http": status_code}
    else:
        _fail(f"/health  →  {status_code}  ({body[:120]})")
        return {"status": "DOWN", "http": status_code}


# ── check 6: runtime challengers ────────────────────────────────────────────

def check_challengers() -> dict:
    _head("6 / 6  Runtime Challengers")
    snapshot = RUNTIME_DIR / "runtime_challenger_snapshot.json"
    if not snapshot.exists():
        _warn("No challenger snapshot found — run tools/verify_runtime_challengers.py to generate")
        return {"status": "NO_SNAPSHOT"}
    try:
        data = json.loads(snapshot.read_text(encoding="utf-8"))
        ts = data.get("generated_at", "?")
        _ok(f"Snapshot from {ts}")
        summary = data.get("summary", {})
        for role, backend in summary.items():
            _ok(f"  {role}: {backend}")
        return {"status": "OK", "summary": summary}
    except Exception as exc:  # noqa: BLE001
        _warn(f"Could not read snapshot: {exc}")
        return {"status": "ERROR", "error": str(exc)}


# ── auto-fix helpers ─────────────────────────────────────────────────────────

def try_fix_providers() -> None:
    """Attempt to install missing provider SDKs."""
    _head("Auto-fix: Provider SDKs")
    pip = str(ROOT / ".venv" / "Scripts" / "pip.exe")
    if not Path(pip).exists():
        pip = sys.executable.replace("python.exe", "pip.exe")
    try:
        subprocess.run(
            [pip, "install", "anthropic==0.86.0", "openai==2.29.0"],
            check=True,
        )
        _ok("Installed anthropic 0.86.0 and openai 2.29.0")
    except subprocess.CalledProcessError as exc:
        _fail(f"pip install failed: {exc}")


# ── main ─────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--skip-ping", action="store_true", help="Skip local model port probes")
    parser.add_argument("--skip-agents", action="store_true", help="Skip tool agent checks")
    parser.add_argument("--fix", action="store_true", help="Attempt auto-fixes for detected problems")
    parser.add_argument("--json", action="store_true", dest="json_only", help="Machine-readable JSON output only")
    args = parser.parse_args(argv)

    if not args.json_only:
        print(f"\n{BOLD}Guppy Runtime Health Check{RESET}  —  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    report: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checks": {},
    }

    providers = check_providers()
    report["checks"]["providers"] = providers
    if args.fix and providers["status"] == "FAIL":
        try_fix_providers()
        providers = check_providers()
        report["checks"]["providers"] = providers

    report["checks"]["local_models"] = check_local_models(skip_ping=args.skip_ping)
    report["checks"]["voice"] = check_voice()
    report["checks"]["agents"] = check_agents(skip=args.skip_agents)
    report["checks"]["chat_api"] = check_chat_api()
    report["checks"]["challengers"] = check_challengers()

    # ── overall verdict ──────────────────────────────────────────────────────
    critical_statuses = [
        report["checks"]["providers"]["status"],
        report["checks"]["chat_api"]["status"],
    ]
    overall = "PASS" if all(s == "OK" for s in critical_statuses) else "FAIL"
    report["overall"] = overall

    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.json_only:
        print(json.dumps(report, indent=2))
        return 0 if overall == "PASS" else 1

    print(f"\n{'─' * 55}")
    if overall == "PASS":
        print(f"{GREEN}{BOLD}  OVERALL: PASS{RESET}  (critical checks green)")
    else:
        print(f"{RED}{BOLD}  OVERALL: FAIL{RESET}  (see details above)")

    degraded = [
        k for k, v in report["checks"].items()
        if v.get("status") not in ("OK", "SKIPPED", "NO_SNAPSHOT")
    ]
    if degraded:
        print(f"  Degraded: {', '.join(degraded)}")

    print(f"\n  Report saved → {REPORT_PATH.relative_to(ROOT)}")
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
