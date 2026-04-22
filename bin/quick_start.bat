@echo off
REM Quick Start Script for Guppy
REM This starts the API with dev mode enabled

setlocal enabledelayedexpansion

cd /d "%~dp0\.."

echo.
echo ========================================
echo   GUPPY QUICK START
echo ========================================
echo.
echo Checking prerequisites...

REM Check if venv exists
if not exist ".venv\" (
    echo ERROR: Virtual environment not found at .venv
    echo Please run: python -m venv .venv
    echo Then: .venv\Scripts\activate
    echo Then: pip install -e .
    pause
    exit /b 1
)

REM Activate venv
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

echo [OK] Virtual environment activated
echo.

REM Check Ollama
echo Checking if Ollama is running...
powershell -NoProfile -Command "try { $null = Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 1; Write-Host 'OK Ollama is running' } catch { Write-Host 'WARNING: Ollama not responding. Make sure it is running (ollama serve)' }"
echo.

REM Start API in dev mode
echo Starting Guppy API...
echo API will run on: http://localhost:8000
echo.

set GUPPY_DEV_MODE=1
python -m src.guppy.cli.launch api --dev

pause
