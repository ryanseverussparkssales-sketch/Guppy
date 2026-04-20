"""Explicit launch-grade security gate for Guppy.

Each check_fn returns (passed: bool, detail: str) and must never raise.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

_ROOT = Path(__file__).resolve().parents[3]
_RUNTIME = _ROOT / "runtime"
_SECRET_GLOBS = ("*.env", ".env", "*.key", "*.pem", "secrets.*", "secret.*")


@dataclass(frozen=True)
class SecurityCheck:
    name: str
    category: str
    description: str
    check_fn: Callable[[], tuple[bool, str]]


def _check_secret_storage() -> tuple[bool, str]:
    try:
        import keyring  # noqa: PLC0415
        kr = keyring.get_keyring()
        name = type(kr).__name__
        if any(h in name.lower() for h in ("fail", "null", "plain", "chainer")):
            return False, f"Keyring resolved to degraded backend: {name}"
        return True, f"OS keyring available: {name}"
    except ImportError:
        return False, "keyring not installed; secrets fall back to env vars only"
    except Exception as exc:
        return False, f"keyring probe failed: {exc}"


def _check_network_boundary() -> tuple[bool, str]:
    try:
        src = _ROOT / "src" / "guppy" / "api" / "server_runtime.py"
        if not src.exists():
            return False, f"server_runtime.py not found at {src}"
        text = src.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("HOST") and "=" in s and "0.0.0.0" in s:
                return False, f"Server binds to 0.0.0.0: {s!r}"
        if 'HOST = "127.0.0.1"' in text or "HOST = '127.0.0.1'" in text:
            return True, "API server binds to 127.0.0.1 (localhost only)"
        return False, "Could not confirm HOST=127.0.0.1 in server_runtime.py"
    except Exception as exc:
        return False, f"network boundary check failed: {exc}"


def _check_connector_scope() -> tuple[bool, str]:
    try:
        cm = _ROOT / "utils" / "connector_manager.py"
        if not cm.exists():
            return False, f"connector_manager.py not found"
        text = cm.read_text(encoding="utf-8", errors="replace")
        raw_http = any(t in text for t in ("urllib.request.urlopen", "requests.get(", "requests.post("))
        if raw_http:
            return False, "connector_manager makes raw HTTP calls; verify auth-token gating"
        if "auth_state" in text and ("read_machine_secret" in text or "_governance_read_machine_secret" in text):
            return True, "Connector manager gates access via auth_state checks and secret reads"
        return False, "Could not confirm auth gating in connector_manager.py"
    except Exception as exc:
        return False, f"connector scope check failed: {exc}"


def _check_build_posture() -> tuple[bool, str]:
    try:
        if not _RUNTIME.exists():
            return True, "runtime/ does not exist — no secret files present"
        found = [p.name for g in _SECRET_GLOBS for p in _RUNTIME.glob(g) if p.is_file()]
        if found:
            return False, f"Plaintext secret files in runtime/: {', '.join(found)}"
        return True, "No plaintext secret files in runtime/"
    except Exception as exc:
        return False, f"build posture check failed: {exc}"


def _check_dependency_hygiene() -> tuple[bool, str]:
    try:
        for fname in ("requirements.txt", "pyproject.toml"):
            p = _ROOT / fname
            if not p.exists():
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            pinned = sum(1 for ln in text.splitlines() if "==" in ln and not ln.strip().startswith("#"))
            if pinned > 0:
                return True, f"{fname} present with {pinned} pinned dependency line(s)"
            return False, f"{fname} exists but has no pinned (==) dependencies"
        return False, "No requirements.txt or pyproject.toml found"
    except Exception as exc:
        return False, f"dependency hygiene check failed: {exc}"


SECURITY_GATE_CHECKS: list[SecurityCheck] = [
    SecurityCheck("secret_storage", "SECRET_STORAGE",
                  "OS keyring available; no plaintext-only secret fallback", _check_secret_storage),
    SecurityCheck("network_boundary", "NETWORK_BOUNDARY",
                  "API server binds to 127.0.0.1 only, not 0.0.0.0", _check_network_boundary),
    SecurityCheck("connector_scope", "CONNECTOR_SCOPE",
                  "Connector manager gates all access via auth_state; no raw unauthenticated HTTP",
                  _check_connector_scope),
    SecurityCheck("build_posture", "BUILD_POSTURE",
                  "No .env, *.key, *.pem, or secrets.* files in runtime/", _check_build_posture),
    SecurityCheck("dependency_hygiene", "DEPENDENCY",
                  "requirements.txt or pyproject.toml present with pinned (==) versions",
                  _check_dependency_hygiene),
]


def run_security_gate() -> dict:
    """Run all gate checks. Returns {passed, failed, warnings, launch_ready}."""
    passed: list[tuple[str, str]] = []
    failed: list[tuple[str, str]] = []
    for check in SECURITY_GATE_CHECKS:
        try:
            ok, detail = check.check_fn()
        except Exception as exc:
            ok, detail = False, f"check raised unexpectedly: {exc}"
        (passed if ok else failed).append((check.name, detail))
    return {"passed": passed, "failed": failed, "warnings": [], "launch_ready": len(failed) == 0}


def format_gate_report(result: dict | None = None) -> str:
    """Return a human-readable gate report string."""
    if result is None:
        result = run_security_gate()
    lines = ["=== Guppy Security Gate Report ===", "",
             f"Launch ready: {'YES' if result.get('launch_ready') else 'NO'}", ""]
    for label, key, marker in (("PASSED", "passed", "PASS"), ("FAILED", "failed", "FAIL"),
                                ("WARNINGS", "warnings", "WARN")):
        items = result.get(key, [])
        if items:
            lines.append(f"{label} ({len(items)}):")
            lines.extend(f"  [{marker}] {n}: {d}" for n, d in items)
            lines.append("")
    lines.append("=== End Security Gate Report ===")
    return "\n".join(lines)
