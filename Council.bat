@echo off
:: ── Council — desktop shortcut launcher (no console window) ───────────────────
:: Brings up the dual Guppy + Merlin council window silently.
:: Pin to taskbar or Desktop for one-click access.

:: Load env vars quietly
for /f "usebackq tokens=*" %%K in (`powershell -NoProfile -Command "[System.Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY','User')"`) do set ANTHROPIC_API_KEY=%%K
set SPOTIFY_CLIENT_ID=d6729bd17c664ca289974001ea790136
set SPOTIFY_CLIENT_SECRET=4eba85477e3a4174ad73e741353b85d3

cd /d "%~dp0"

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" council_ui.py
    exit
)
where pythonw >nul 2>&1 && (
    start "" pythonw council_ui.py
    exit
)
.venv\Scripts\python.exe council_ui.py
pause
