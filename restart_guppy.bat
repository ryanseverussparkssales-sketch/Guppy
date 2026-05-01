@echo off
REM restart_guppy.bat — Kills any running Guppy server and restarts with venv Python.
REM Double-click this to restart after code changes.

setlocal
cd /d "%~dp0"

echo [restart] Killing old Guppy server processes...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { ($_.Name -like 'python*' -or $_.Name -eq 'uvicorn.exe') -and ($_.CommandLine -match 'guppy_api\.py' -or $_.CommandLine -match 'src\.guppy\.api\.server') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
timeout /t 2 /nobreak >nul

set PYTHON=.venv\Scripts\python.exe
if not exist "%PYTHON%" (
    echo ERROR: .venv\Scripts\python.exe not found. Run: powershell -File tools\bootstrap_venv.ps1 -Dev
    pause
    exit /b 1
)

echo [restart] Starting Guppy API with venv Python...
start "Guppy API" /min "%PYTHON%" guppy_api.py --port 8081

echo [restart] Waiting for server to bind...
timeout /t 6 /nobreak >nul

curl -s http://localhost:8081/health >nul 2>&1
if errorlevel 1 (
    echo [restart] WARNING: Server may still be starting. Open http://localhost:8081 in browser.
) else (
    echo [restart] Server is healthy. Open http://localhost:8081 in browser.
    echo [restart] Press Ctrl+Shift+R in the browser to load the latest frontend.
)
