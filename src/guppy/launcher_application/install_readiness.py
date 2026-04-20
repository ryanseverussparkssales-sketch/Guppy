"""Track 1 — Desktop install readiness (PL-C5).

Defines explicit acceptance criteria for "basic desktop install works".
Safe to import and call in any environment (CI, no Ollama, no runtime).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

_REPO_ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True, slots=True)
class InstallReadinessCheck:
    name: str
    description: str
    check_fn: Callable[[], bool]


def _file_exists(rel: str) -> bool:
    return (_REPO_ROOT / rel).exists()


def _dir_writable(rel: str) -> bool:
    try:
        path = _REPO_ROOT / rel
        path.mkdir(parents=True, exist_ok=True)
        probe = path / "._install_readiness_probe.tmp"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except Exception:
        return False


def _core_import_static() -> bool:
    try:
        text = (_REPO_ROOT / "guppy_launcher.py").read_text(encoding="utf-8", errors="replace")
        return any(tok in text.lower() for tok in ("launcher_app", "main", "guppy_launcher"))
    except Exception:
        return False


INSTALL_READINESS_CHECKS: list[InstallReadinessCheck] = [
    InstallReadinessCheck("launcher_entrypoint", "guppy_launcher.py exists at repo root",
                          lambda: _file_exists("guppy_launcher.py")),
    InstallReadinessCheck("build_script", "bin/build_executable.bat exists",
                          lambda: _file_exists("bin/build_executable.bat")),
    InstallReadinessCheck("validate_script", "bin/validate_build.bat exists",
                          lambda: _file_exists("bin/validate_build.bat")),
    InstallReadinessCheck("pyinstaller_spec", "bin/Guppy.spec exists",
                          lambda: _file_exists("bin/Guppy.spec")),
    InstallReadinessCheck("packaging_doc", "docs/PACKAGING.md exists",
                          lambda: _file_exists("docs/PACKAGING.md")),
    InstallReadinessCheck("runtime_dir_writable", "runtime/ is writable (created if absent)",
                          lambda: _dir_writable("runtime")),
    InstallReadinessCheck("tmp_dir_writable", ".tmp/dev-workflow/reports/ is writable",
                          lambda: _dir_writable(".tmp/dev-workflow/reports")),
    InstallReadinessCheck("core_import_static",
                          "guppy_launcher.py contains expected entry references (static check)",
                          _core_import_static),
]


def run_install_readiness() -> dict[str, object]:
    """Run all Track 1 install readiness checks.

    Returns a dict with keys: passed (list), failed (list), summary (str).
    """
    passed: list[str] = []
    failed: list[str] = []
    for check in INSTALL_READINESS_CHECKS:
        try:
            ok = check.check_fn()
        except Exception:
            ok = False
        (passed if ok else failed).append(check.name)
    total = len(INSTALL_READINESS_CHECKS)
    summary = f"Track 1 install readiness: {len(passed)}/{total} passed"
    if failed:
        summary += f" — failed: {', '.join(failed)}"
    return {"passed": passed, "failed": failed, "summary": summary}
