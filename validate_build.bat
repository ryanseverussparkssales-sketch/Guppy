@echo off
REM validate_build.bat — Smoke-test the dist\Guppy.exe build before distributing.
REM Checks that the executable exists, is a reasonable size, and that all expected
REM source imports resolve cleanly in the current environment.
REM Does NOT launch the full GUI — safe to run on CI or before distributing.

setlocal
set PYTHON=.venv\Scripts\python.exe
if not exist "%PYTHON%" set PYTHON=python

set PASS=0
set FAIL=0

echo ============================================
echo Guppy Build Validator
echo ============================================
echo.

REM 1 — Executable exists
echo [1] Checking dist\Guppy.exe exists...
if exist "dist\Guppy.exe" (
    for %%A in ("dist\Guppy.exe") do (
        set SIZE=%%~zA
        echo     OK  dist\Guppy.exe  (%%~zA bytes)
    )
    set /a PASS+=1
) else (
    echo     FAIL  dist\Guppy.exe not found. Run build_executable.bat first.
    set /a FAIL+=1
)
echo.

REM 2 — Executable size sanity (should be > 50 MB for a real build)
if exist "dist\Guppy.exe" (
    echo [2] Checking executable size ^> 50 MB...
    for %%A in ("dist\Guppy.exe") do set BYTES=%%~zA
    %PYTHON% -c "import sys; b=int('%BYTES%'); ok=b>50*1024*1024; print('    OK  ' if ok else '    FAIL ', f'{b//1024//1024} MB'); sys.exit(0 if ok else 1)" 2>nul
    if errorlevel 1 ( set /a FAIL+=1 ) else ( set /a PASS+=1 )
    echo.
)

REM 3 — Core modules import cleanly
echo [3] Checking core module imports...
%PYTHON% -c "
import sys, traceback
mods = [
    'guppy_core', 'guppy_memory', 'guppy_semantic_memory',
    'guppy_voice', 'guppy_daemon', 'merlin_core', 'inference_router',
    'guppy_api', 'guppy_api_auth', 'utils.hub_operator',
    'utils.agent_perf', 'utils.env_bootstrap',
]
failed = []
for m in mods:
    try:
        __import__(m)
        print(f'    OK  {m}')
    except Exception as e:
        print(f'    FAIL  {m}: {e}')
        failed.append(m)
sys.exit(len(failed))
" 2>&1
if errorlevel 1 ( set /a FAIL+=1 ) else ( set /a PASS+=1 )
echo.

REM 4 — Tool count sanity
echo [4] Checking tool count ^>= 70...
%PYTHON% -c "
import sys
try:
    import guppy_core
    n = len(guppy_core.TOOLS)
    ok = n >= 70
    print(f'    {\"OK\" if ok else \"FAIL\"}  {n} tools registered')
    sys.exit(0 if ok else 1)
except Exception as e:
    print(f'    FAIL  {e}')
    sys.exit(1)
" 2>&1
if errorlevel 1 ( set /a FAIL+=1 ) else ( set /a PASS+=1 )
echo.

REM 5 — Syntax check key files
echo [5] Syntax checking key source files...
%PYTHON% -c "
import ast, sys
files = ['guppy_ui.py','guppy_core.py','guppy_hub.py','guppy_voice.py',
         'guppy_daemon.py','inference_router.py','guppy_api.py']
failed = []
for f in files:
    try:
        ast.parse(open(f, encoding='utf-8').read())
        print(f'    OK  {f}')
    except SyntaxError as e:
        print(f'    FAIL  {f}: {e}')
        failed.append(f)
sys.exit(len(failed))
" 2>&1
if errorlevel 1 ( set /a FAIL+=1 ) else ( set /a PASS+=1 )
echo.

REM 6 — runtime/ directory writable
echo [6] Checking runtime/ directory is writable...
%PYTHON% -c "
import sys
from pathlib import Path
try:
    p = Path('runtime/_validate_write_test.tmp')
    p.parent.mkdir(exist_ok=True)
    p.write_text('ok')
    p.unlink()
    print('    OK  runtime/ is writable')
    sys.exit(0)
except Exception as e:
    print(f'    FAIL  {e}')
    sys.exit(1)
" 2>&1
if errorlevel 1 ( set /a FAIL+=1 ) else ( set /a PASS+=1 )
echo.

REM 7 — .env exists (warn only, not a hard fail)
echo [7] Checking .env exists (warn only)...
if exist ".env" (
    echo     OK  .env found
) else (
    echo     WARN  .env not found. Set ANTHROPIC_API_KEY and other keys before running.
)
echo.

REM Summary
echo ============================================
echo Results: %PASS% passed, %FAIL% failed
echo ============================================
if %FAIL% GTR 0 (
    echo.
    echo Some checks failed. Fix the issues above before distributing.
    exit /b 1
) else (
    echo.
    echo All checks passed. Build looks good.
    exit /b 0
)
