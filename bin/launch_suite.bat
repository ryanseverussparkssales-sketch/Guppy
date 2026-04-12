@echo off
TITLE Guppy Suite
echo =============================================================
echo   GUPPY SUITE — Starting Hub + Guppy
echo =============================================================

:: ── Load env vars ──────────────────────────────────────────────────────────────
for /f "usebackq tokens=*" %%K in (`powershell -NoProfile -Command "[System.Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY','User')"`) do set ANTHROPIC_API_KEY=%%K

if "%ANTHROPIC_API_KEY%"=="" (
    echo [Suite] WARNING: ANTHROPIC_API_KEY not set — running in Ollama mode.
) else (
    echo [Suite] API key loaded. Claude mode available.
)

set SPOTIFY_CLIENT_ID=d6729bd17c664ca289974001ea790136
set SPOTIFY_CLIENT_SECRET=4eba85477e3a4174ad73e741353b85d3

cd /d "%~dp0\.."

:: ── Step 1: Start Omnissiah Hub silently in background (tray only) ─────────────
echo [Suite] Starting Omnissiah Hub in system tray...

:: Prefer pythonw (no console window) for the hub
set "PYW="
if exist ".venv\Scripts\pythonw.exe" set "PYW=.venv\Scripts\pythonw.exe"
if "%PYW%"=="" where pythonw >nul 2>&1 && set "PYW=pythonw"
if "%PYW%"=="" set "PYW=.venv\Scripts\python.exe"

start "" /B "%PYW%" guppy_hub.py

:: ── Step 2: Short delay so Hub can settle in tray ──────────────────────────────
echo [Suite] Hub launched. Waiting 2 seconds...
timeout /T 2 /NOBREAK >nul

:: ── Step 3: Start Guppy (main window, foreground) ─────────────────────────────
echo [Suite] Starting Guppy...
.venv\Scripts\python.exe guppy_ui.py

pause
