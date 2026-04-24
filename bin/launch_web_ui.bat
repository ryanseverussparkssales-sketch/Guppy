@echo off
REM Launch Guppy Web UI Hub
REM This starts both the API and Web UI

title Guppy Web UI
setlocal enabledelayedexpansion

cd /d "%~dp0\.."

echo.
echo ========================================
echo   GUPPY WEB UI HUB
echo ========================================
echo.

REM Activate venv
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo ERROR: Virtual environment not found
    echo Run: python -m venv .venv
    pause
    exit /b 1
)

REM Set dev mode
set GUPPY_DEV_MODE=1

echo Checking prerequisites...

REM Check Ollama
powershell -NoProfile -Command "try { $null = Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 1; Write-Host 'OK: Ollama is running' -ForegroundColor Green } catch { Write-Host 'WARNING: Ollama not detected' -ForegroundColor Yellow; Write-Host 'Start with: ollama serve' -ForegroundColor Yellow }"

echo.
echo Starting Web UI Hub...
echo - API: http://localhost:8000
echo - Web: http://localhost:3000
echo.

python -m src.guppy.cli.launch hub --dev

pause
