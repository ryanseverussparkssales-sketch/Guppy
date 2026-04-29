@echo off
REM launch_api_supervised.bat — Self-restarting API launcher with crash backoff.
REM For NSSM / Task Scheduler: point supervisor at this script; it handles restarts.
REM For interactive use with auto-restart: run this directly in a terminal.

setlocal enabledelayedexpansion
cd /d "%~dp0\.."

if "%GUPPY_API_OWNS_DAEMON%"=="" set GUPPY_API_OWNS_DAEMON=0
if "%GUPPY_API_RELOAD%"==""     set GUPPY_API_RELOAD=0
if "%GUPPY_DEV_MODE%"==""       set GUPPY_DEV_MODE=0

set PYTHON=.venv\Scripts\python.exe
if not exist "%PYTHON%" set PYTHON=python

set MAX_RETRIES=10
set RETRY_DELAY=3
set RETRY_COUNT=0

:RESTART_LOOP
echo [supervisor] Starting Guppy API (attempt !RETRY_COUNT! of %MAX_RETRIES%)...
%PYTHON% guppy_api.py
set EXIT_CODE=%errorlevel%

REM Exit code 0 = clean shutdown (e.g. /api/shutdown called). Don't restart.
if %EXIT_CODE% EQU 0 (
    echo [supervisor] Clean shutdown (exit 0). Stopping.
    exit /b 0
)

set /a RETRY_COUNT+=1
if %RETRY_COUNT% GEQ %MAX_RETRIES% (
    echo [supervisor] Max retries (%MAX_RETRIES%) reached. Giving up.
    exit /b %EXIT_CODE%
)

REM Exponential-ish backoff: delay doubles each crash up to 30s
set /a RETRY_DELAY_NOW=%RETRY_DELAY%*%RETRY_COUNT%
if %RETRY_DELAY_NOW% GTR 30 set RETRY_DELAY_NOW=30

echo [supervisor] Crashed (exit %EXIT_CODE%). Restarting in %RETRY_DELAY_NOW%s...
timeout /t %RETRY_DELAY_NOW% /nobreak >nul

goto RESTART_LOOP
