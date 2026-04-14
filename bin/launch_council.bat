@echo off
TITLE Council
cd /d "%~dp0\.."
set GUPPY_ENABLE_LEGACY_SURFACES=1
echo [launch] Council is a compatibility-only surface. Prefer launcher for daily use.
.venv\Scripts\python.exe src\guppy\cli\launch.py council
pause
