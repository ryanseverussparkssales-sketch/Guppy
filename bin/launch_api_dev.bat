@echo off
REM Launch Guppy API in Development Mode
REM This starts the backend API server on localhost:8000

title Guppy API (Dev Mode)
setlocal enabledelayedexpansion

cd /d "%~dp0\.."

echo.
echo ========================================
echo   GUPPY API - Development Mode
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

echo Checking for Ollama service...
powershell -NoProfile -Command "try { $null = Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 1; Write-Host 'OK: Ollama is running' -ForegroundColor Green } catch { Write-Host 'WARNING: Ollama not detected (http://127.0.0.1:11434)' -ForegroundColor Yellow; Write-Host 'Start Ollama with: ollama serve' -ForegroundColor Yellow }"

echo.
echo Starting API on http://localhost:8000
echo Logs below:
echo.

python -m src.guppy.cli.launch api --dev

pause
