@echo off
TITLE Merlin — The Sorcerer's Study
echo [Merlin] Initializing advanced surface...

set GUPPY_RUNTIME_PROFILE=power
set GUPPY_DEFAULT_SURFACE=guppy
set GUPPY_SHOW_ADVANCED_SURFACES=1

:: Load ANTHROPIC_API_KEY from User environment
for /f "delims=" %%K in ('powershell -NoProfile -Command "[System.Environment]::GetEnvironmentVariable(\"ANTHROPIC_API_KEY\",\"User\")"') do set "ANTHROPIC_API_KEY=%%K"

echo [Merlin] Note: Guppy is the primary app surface; Merlin is an advanced focused mode.

:: Launch the GUI (use venv Python explicitly)
cd /d "%~dp0\.."
.venv\Scripts\python.exe merlin_ui.py

if errorlevel 1 (
    echo.
    echo [ERROR] Merlin failed to start. Check Python and dependencies.
    pause
)
