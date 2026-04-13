import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def check_imports() -> bool:
    print("[3] Checking core module imports...")
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
        try:
            __import__(m)
            print(f"    OK  {m}")
        except Exception as e:
            ok = False
            print(f"    FAIL  {m}: {e}")
    print()
    return ok


def check_tool_count() -> bool:
    print("[4] Checking tool count >= 70...")
    try:
        import guppy_core

        n = len(guppy_core.TOOLS)
        good = n >= 70
        print(f"    {'OK' if good else 'FAIL'}  {n} tools registered")
        print()
        return good
    except Exception as e:
        print(f"    FAIL  {e}")
        print()
        return False


def check_syntax() -> bool:
    print("[5] Syntax checking key source files...")
    files = [
        "guppy_launcher.py",
        "ui/launcher/launcher_window.py",
        "guppy_core.py",
        "guppy_hub.py",
        "guppy_voice.py",
        "guppy_daemon.py",
        "inference_router.py",
        "guppy_api.py",
    ]
    ok = True
    for file_name in files:
        try:
            ast.parse(Path(file_name).read_text(encoding="utf-8"))
            print(f"    OK  {file_name}")
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
