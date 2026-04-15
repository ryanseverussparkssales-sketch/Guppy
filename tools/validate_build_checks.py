import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _preferred_python() -> Path:
    candidates = [
        ROOT / ".venv" / "Scripts" / "python.exe",
        ROOT / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return Path(sys.executable)


VALIDATION_PYTHON = _preferred_python()


def _run_python_snippet(snippet: str) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            [str(VALIDATION_PYTHON), "-c", snippet],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except Exception as exc:
        return False, str(exc)
    detail = (proc.stdout or "").strip() or (proc.stderr or "").strip()
    return proc.returncode == 0, detail


def check_imports() -> bool:
    print("[3] Checking core module imports...")
    print(f"    using {VALIDATION_PYTHON}")
    mods = [
        "guppy_core",
        "guppy_memory",
        "guppy_semantic_memory",
        "guppy_voice",
        "guppy_daemon",
        "merlin_core",
        "inference_router",
        "guppy_api",
        "guppy_api_auth",
        "utils.hub_operator",
        "utils.agent_perf",
        "utils.env_bootstrap",
    ]
    ok = True
    for m in mods:
        success, detail = _run_python_snippet(f"import {m}")
        if success:
            print(f"    OK  {m}")
        else:
            ok = False
            print(f"    FAIL  {m}: {detail}")
    print()
    return ok


def check_tool_count() -> bool:
    print("[4] Checking tool count >= 70...")
    success, detail = _run_python_snippet("import guppy_core; print(len(guppy_core.TOOLS))")
    if not success:
        print(f"    FAIL  {detail}")
        print()
        return False
    try:
        n = int((detail or "0").splitlines()[-1].strip())
    except Exception:
        print(f"    FAIL  unexpected tool count output: {detail}")
        print()
        return False
    good = n >= 70
    print(f"    {'OK' if good else 'FAIL'}  {n} tools registered")
    print()
    return good


def check_syntax() -> bool:
    print("[5] Syntax checking key source files...")
    files = [
        "guppy_launcher.py",
        "ui/launcher/launcher_window.py",
        "guppy_core/__init__.py",
        "guppy_hub.py",
        "guppy_voice.py",
        "guppy_daemon.py",
        "inference_router.py",
        "guppy_api.py",
    ]
    ok = True
    for file_name in files:
        try:
            ast.parse(Path(file_name).read_text(encoding="utf-8-sig"))
            print(f"    OK  {file_name}")
        except FileNotFoundError as e:
            ok = False
            print(f"    FAIL  {file_name}: {e}")
        except SyntaxError as e:
            ok = False
            print(f"    FAIL  {file_name}: {e}")
    print()
    return ok


def check_runtime_write() -> bool:
    print("[6] Checking runtime/ directory is writable...")
    try:
        p = Path("runtime/_validate_write_test.tmp")
        p.parent.mkdir(exist_ok=True)
        p.write_text("ok", encoding="utf-8")
        p.unlink()
        print("    OK  runtime/ is writable")
        print()
        return True
    except Exception as e:
        print(f"    FAIL  {e}")
        print()
        return False


def main() -> int:
    checks = [
        check_imports,
        check_tool_count,
        check_syntax,
        check_runtime_write,
    ]
    failures = 0
    for fn in checks:
        if not fn():
            failures += 1
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
