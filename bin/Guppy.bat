@echo off
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT=%%~fI"
:: ── Guppy — desktop shortcut launcher (no console window) ─────────────────────
:: Drop this on the Desktop or pin to Start. Uses pythonw so no terminal pops up.

set GUPPY_RUNTIME_PROFILE=standard
set GUPPY_DEFAULT_SURFACE=guppy

:: Load env vars quietly
for /f "usebackq tokens=*" %%K in (`powershell -NoProfile -Command "[System.Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY','User')"`) do set ANTHROPIC_API_KEY=%%K
set SPOTIFY_CLIENT_ID=d6729bd17c664ca289974001ea790136
set SPOTIFY_CLIENT_SECRET=4eba85477e3a4174ad73e741353b85d3

cd /d "%ROOT%"

:: Prefer venv pythonw; fall back to system pythonw; fall back to visible python
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" guppy_launcher.py
    exit
)
where pythonw >nul 2>&1 && (
    start "" pythonw guppy_launcher.py
    exit
)
:: Last resort: visible console (so you can see any startup errors)
.venv\Scripts\python.exe guppy_launcher.py
pause
