@echo off
:: ============================================================================
:: build_webui_executable.bat  —  Build dist/GuppyWebUI/GuppyWebUI.exe
::
:: Usage:  bin\build_webui_executable.bat [--skip-frontend]
::
:: Steps:
::   1. Activate virtualenv
::   2. Build React frontend (npm run build) — unless --skip-frontend
::   3. Run PyInstaller with bin/GuppyWebUI.spec
::   4. Report output path
:: ============================================================================

setlocal EnableDelayedExpansion

set ROOT=%~dp0..
cd /d "%ROOT%"

set SKIP_FRONTEND=0
if /I "%~1"=="--skip-frontend" set SKIP_FRONTEND=1

:: ── 1. Activate venv ─────────────────────────────────────────────────────────
if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: .venv not found. Run: powershell -File tools/bootstrap_venv.ps1 -Dev
    exit /b 1
)
call .venv\Scripts\activate.bat

:: ── 2. Build React frontend ───────────────────────────────────────────────────
if "%SKIP_FRONTEND%"=="0" (
    echo [build] Building React frontend...
    cd web
    where npm >nul 2>&1
    if errorlevel 1 (
        echo WARNING: npm not found — skipping frontend build. Use --skip-frontend to suppress this warning.
        cd ..
    ) else (
        npm run build
        if errorlevel 1 (
            echo ERROR: npm run build failed.
            exit /b 1
        )
        cd ..
        echo [build] Frontend build complete.
    )
) else (
    echo [build] Skipping frontend build (--skip-frontend).
)

:: Verify static/index.html exists
if not exist "static\index.html" (
    echo ERROR: static\index.html not found. Build the React frontend first:
    echo         cd web ^&^& npm run build
    exit /b 1
)

:: ── 3. Run PyInstaller ────────────────────────────────────────────────────────
echo [build] Running PyInstaller...
python -m PyInstaller bin\GuppyWebUI.spec --noconfirm --clean

if errorlevel 1 (
    echo ERROR: PyInstaller failed.
    exit /b 1
)

:: ── 4. Report ─────────────────────────────────────────────────────────────────
if exist "dist\GuppyWebUI\GuppyWebUI.exe" (
    echo.
    echo ============================================================
    echo  Build successful!
    echo  Output: %ROOT%\dist\GuppyWebUI\GuppyWebUI.exe
    echo.
    echo  To run:  dist\GuppyWebUI\GuppyWebUI.exe
    echo  To ship: zip dist\GuppyWebUI\ and distribute
    echo ============================================================
) else (
    echo ERROR: GuppyWebUI.exe not found after build — check PyInstaller output above.
    exit /b 1
)

endlocal
