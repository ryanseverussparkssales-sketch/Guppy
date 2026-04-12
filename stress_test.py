"""stress_test.py — Quick repository stress test for Guppy.

Run this before demos to validate syntax, imports, and basic startup.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable

MODULES = [
    'guppy_core', 'guppy_ui', 'guppy_agent', 'guppy_daemon',
    'guppy_memory', 'guppy_voice', 'guppy_hub', 'guppy_theme',
    'merlin_core', 'merlin_ui', 'council_ui', 'media_tools',
    'debug_console', 'test_reminders',
]


def compile_all() -> bool:
    print('1) Compiling all Python files...')
    ok = True
    for path in sorted(ROOT.rglob('*.py')):
        if '.venv' in path.parts or 'site-packages' in str(path):
            continue
        try:
            subprocess.check_output([PY, '-m', 'py_compile', str(path)], stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as exc:
            ok = False
            print(f'  ❌ Compile failed: {path}')
            print(exc.output.decode(errors='ignore'))
    return ok


def import_modules() -> bool:
    print('2) Importing core modules...')
    ok = True
    for module in MODULES:
        try:
            __import__(module)
            print(f'  ✅ {module}')
        except Exception as exc:
            ok = False
            print(f'  ❌ {module}: {exc}')
    return ok


def run_process(name: str, args: list[str], timeout: int = 10) -> bool:
    print(f'3) Starting process: {name}')
    env = os.environ.copy()
    env['PYTHONUNBUFFERED'] = '1'
    proc = subprocess.Popen(args, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        time.sleep(timeout)
        if proc.poll() is None:
            print(f'  ✅ {name} is still running after {timeout}s')
            proc.terminate()
            time.sleep(1)
            if proc.poll() is None:
                proc.kill()
        else:
            print(f'  ⚠️ {name} exited early with code {proc.returncode}')
    except Exception as exc:
        print(f'  ❌ {name} error: {exc}')
        proc.kill()
        return False
    finally:
        out, err = proc.communicate(timeout=5 if proc.poll() is None else 0)
        if out:
            print('--- stdout ---')
            print(out.strip())
        if err:
            print('--- stderr ---')
            print(err.strip())
    return proc.returncode == 0 or proc.returncode is None


def main():
    print('Guppy Stress Test Starting')
    compile_ok = compile_all()
    import_ok = import_modules()

    hub_ok = run_process('Omnissiah Hub', [PY, str(ROOT / 'guppy_hub.py')], timeout=8)

    print('\nSummary:')
    print(f"  Compile: {'PASS' if compile_ok else 'FAIL'}")
    print(f"  Import: {'PASS' if import_ok else 'FAIL'}")
    print(f"  Hub startup: {'PASS' if hub_ok else 'FAIL'}")
    if compile_ok and import_ok and hub_ok:
        print('\nStress test completed successfully.')
        sys.exit(0)
    else:
        print('\nStress test detected issues.')
        sys.exit(1)


if __name__ == '__main__':
    main()
