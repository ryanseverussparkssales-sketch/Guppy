@echo off
TITLE Omnissiah
echo [Omnissiah] Starting Omnissiah...

:: Load ANTHROPIC_API_KEY from User environment
for /f "usebackq tokens=*" %%K in (`powershell -NoProfile -Command "[System.Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY','User')"`) do set ANTHROPIC_API_KEY=%%K

if "%ANTHROPIC_API_KEY%"=="" (
    echo [Omnissiah] WARNING: ANTHROPIC_API_KEY not set. Guppy will run in local mode.
) else (
    echo [Omnissiah] API key loaded.
)

:: Launch Omnissiah — try the best available Python launcher
cd /d "C:\Users\Ryan\Guppy"
set "PYW=pythonw"
where pythonw >nul 2>&1 || (
    set "PYW=pythonw3.12"
    where pythonw3.12 >nul 2>&1 || set "PYW=py -3w"
)

echo [Omnissiah] Launching with %PYW%...
%PYW% guppy_hub.py
if errorlevel 1 (
    echo [Omnissiah] %PYW% failed, retrying with python for error output...
    python guppy_hub.py
    pause
)

