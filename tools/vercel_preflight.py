"""Vercel deployment preflight validator for the Guppy cloud backend.

Run before every ``vercel deploy`` to catch configuration drift early.

Usage:
    python tools/vercel_preflight.py              # exits 0 on pass, 1 on fail
    python tools/vercel_preflight.py --json       # machine-readable output
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "api"

# ── Required items ─────────────────────────────────────────────────────────────

_REQUIRED_API_FILES = [
    "api/__init__.py",
    "api/app.py",
    "api/auth.py",
    "api/index.py",
    "api/routes/__init__.py",
    "api/routes/auth_refresh.py",
    "api/routes/auth_token.py",
    "api/routes/chat.py",
    "api/routes/health.py",
]

_REQUIRED_VERCEL_KEYS = {"rewrites"}

_REQUIRED_PYPROJECT_DEPS = {
    "fastapi",
    "uvicorn",
    "python-jose",
    "httpx",
    "openai",
    "anthropic",
}

_FORBIDDEN_DESKTOP_MODULES = {
    "guppy_core",
    "src.guppy.voice",
    "src.guppy.daemon",
    "src.guppy.launcher_application",
    "utils.env_bootstrap",
    "utils.db_utils",
    "src.guppy.paths",
}

_RECOMMENDED_ENV_VARS = [
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GUPPY_JWT_SECRET",
    "GUPPY_TURNSTILE_SECRET",
    "GUPPY_API_KEY",
    "GUPPY_CORS_ORIGINS",
    "GUPPY_AI_BACKEND",
]


# ── Check helpers ──────────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str
    details: list[str] = field(default_factory=list)


def _check_required_files() -> CheckResult:
    missing = [f for f in _REQUIRED_API_FILES if not (ROOT / f).exists()]
    if missing:
        return CheckResult(
            "required_api_files",
            False,
            f"{len(missing)} required file(s) missing",
            missing,
        )
    return CheckResult("required_api_files", True, f"All {len(_REQUIRED_API_FILES)} required files present")


def _check_vercel_json() -> CheckResult:
    vercel = ROOT / "vercel.json"
    if not vercel.exists():
        return CheckResult("vercel_json", False, "vercel.json not found")
    try:
        data = json.loads(vercel.read_text())
    except json.JSONDecodeError as exc:
        return CheckResult("vercel_json", False, f"vercel.json parse error: {exc}")
    missing = _REQUIRED_VERCEL_KEYS - set(data.keys())
    if missing:
        return CheckResult("vercel_json", False, f"Missing keys in vercel.json: {missing}")
    return CheckResult("vercel_json", True, "vercel.json is valid")


def _check_pyproject_deps() -> CheckResult:
    pyproject = ROOT / "pyproject.toml"
    if not pyproject.exists():
        return CheckResult("pyproject_deps", False, "pyproject.toml not found")
    content = pyproject.read_text()
    missing = {dep for dep in _REQUIRED_PYPROJECT_DEPS if dep not in content}
    if missing:
        return CheckResult(
            "pyproject_deps",
            False,
            f"{len(missing)} required dep(s) missing from pyproject.toml",
            sorted(missing),
        )
    return CheckResult("pyproject_deps", True, f"All {len(_REQUIRED_PYPROJECT_DEPS)} required deps declared")


def _check_no_desktop_imports() -> CheckResult:
    violations: list[str] = []
    for py_file in sorted(API_DIR.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            modules_to_check: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                modules_to_check.append(node.module)
            elif isinstance(node, ast.Import):
                modules_to_check.extend(a.name for a in node.names)
            for module in modules_to_check:
                for forbidden in _FORBIDDEN_DESKTOP_MODULES:
                    if module == forbidden or module.startswith(f"{forbidden}."):
                        rel = py_file.relative_to(ROOT)
                        violations.append(f"{rel}: imports {module}")
    if violations:
        return CheckResult(
            "no_desktop_imports",
            False,
            f"{len(violations)} forbidden desktop import(s) found in api/",
            violations,
        )
    return CheckResult("no_desktop_imports", True, "No forbidden desktop imports in api/")


def _check_index_entry() -> CheckResult:
    index = ROOT / "api" / "index.py"
    if not index.exists():
        return CheckResult("index_entry", False, "api/index.py not found")
    content = index.read_text()
    if "from api.app import app" not in content:
        return CheckResult(
            "index_entry",
            False,
            "api/index.py must import app from api.app",
            [content[:200]],
        )
    return CheckResult("index_entry", True, "api/index.py correctly imports from api.app")


def _check_env_vars() -> CheckResult:
    missing = [v for v in _RECOMMENDED_ENV_VARS if not os.environ.get(v)]
    if missing:
        return CheckResult(
            "env_vars_configured",
            False,
            f"{len(missing)} recommended env var(s) not set in current shell "
            f"(Vercel project settings must have them)",
            missing,
        )
    return CheckResult("env_vars_configured", True, "All recommended env vars are set")


# ── Runner ─────────────────────────────────────────────────────────────────────

def run_preflight(check_env: bool = True) -> list[CheckResult]:
    checks = [
        _check_required_files(),
        _check_vercel_json(),
        _check_pyproject_deps(),
        _check_no_desktop_imports(),
        _check_index_entry(),
    ]
    if check_env:
        checks.append(_check_env_vars())
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Guppy Vercel deployment preflight")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--skip-env",
        action="store_true",
        help="Skip the env-var check (useful in CI where secrets are set differently)",
    )
    args = parser.parse_args()

    results = run_preflight(check_env=not args.skip_env)
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    if args.json:
        print(json.dumps(
            {
                "summary": {"passed": passed, "failed": failed, "total": len(results)},
                "checks": [
                    {
                        "name": r.name,
                        "passed": r.passed,
                        "message": r.message,
                        "details": r.details,
                    }
                    for r in results
                ],
            },
            indent=2,
        ))
        return 0 if failed == 0 else 1

    print("\n=== Guppy Vercel Preflight ===\n")
    for r in results:
        icon = "✓" if r.passed else "✗"
        print(f"  {icon}  {r.name}: {r.message}")
        for detail in r.details:
            print(f"       → {detail}")

    print(f"\n  {passed}/{len(results)} checks passed", end="")
    if failed:
        print(f" ({failed} FAILED)")
        return 1
    print(" — ready to deploy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
