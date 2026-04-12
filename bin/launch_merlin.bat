@echo off
TITLE Merlin — The Sorcerer's Study
echo [Merlin] Initializing...

:: Load ANTHROPIC_API_KEY from User environment
for /f "delims=" %%K in ('powershell -NoProfile -Command "[System.Environment]::GetEnvironmentVariable(\"ANTHROPIC_API_KEY\",\"User\")"') do set "ANTHROPIC_API_KEY=%%K"

:: Launch the GUI (use venv Python explicitly)
cd /d "%~dp0\.."
.venv\Scripts\python.exe merlin_ui.py

if errorlevel 1 (
    echo.
    echo [ERROR] Merlin failed to start. Check Python and dependencies.
    pause
)
