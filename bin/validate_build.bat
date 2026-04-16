@echo off
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT=%%~fI"
pushd "%ROOT%"
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
set BUILD_EXE=dist\Guppy\Guppy.exe
if not exist "%BUILD_EXE%" set BUILD_EXE=dist\Guppy.exe

echo [1] Checking %BUILD_EXE% exists...
if exist "%BUILD_EXE%" (
    for %%A in ("%BUILD_EXE%") do (
        set SIZE=%%~zA
        echo     OK  %BUILD_EXE%  (%%~zA bytes^)
    )
    set /a PASS+=1
) else (
    echo     FAIL  Build output not found. Run bin\build_executable.bat first.
    set /a FAIL+=1
)
echo.

REM 2 — Executable size sanity (should be > 50 MB for a real build)
if exist "%BUILD_EXE%" (
    echo [2] Checking executable size ^> 50 MB...
    for %%A in ("%BUILD_EXE%") do %PYTHON% -c "import sys; b=int('%%~zA'); ok=b>50*1024*1024; print('    OK  ' if ok else '    FAIL  ', f'{b//1024//1024} MB'); sys.exit(0 if ok else 1)" 2>nul
    if errorlevel 1 ( set /a FAIL+=1 ) else ( set /a PASS+=1 )
    echo.
)

REM 3 — Core modules import cleanly
echo [3-6] Running Python integrity checks...
%PYTHON% tools\validate_build_checks.py 2>&1
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
