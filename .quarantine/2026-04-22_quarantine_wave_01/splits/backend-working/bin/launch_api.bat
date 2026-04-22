@echo off
REM launch_api.bat — Start the Guppy API server
TITLE Guppy API
cd /d "%~dp0\.."

REM Guard: fail fast if port 8081 is already occupied
netstat -ano | findstr ":8081 " >nul 2>&1
if not errorlevel 1 (
    echo ERROR: Port 8081 already in use. Stop the existing process first.
    echo Use:  netstat -ano ^| findstr ":8081"  to find the PID.
    pause
    exit /b 1
)

.venv\Scripts\python.exe src\guppy\cli\launch.py api
pause
