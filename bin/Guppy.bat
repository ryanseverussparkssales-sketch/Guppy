@echo off
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT=%%~fI"
:: Guppy desktop launcher (no console window).
:: Drop this on the Desktop or pin to Start. Uses pythonw so no terminal pops up.

cd /d "%ROOT%"

:: Prefer venv pythonw; fall back to system pythonw; fall back to visible python.
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" src\guppy\cli\launch.py launcher
    exit
)
where pythonw >nul 2>&1 && (
    start "" pythonw src\guppy\cli\launch.py launcher
    exit
)
:: Last resort: visible console (so you can see any startup errors).
.venv\Scripts\python.exe src\guppy\cli\launch.py launcher
pause
