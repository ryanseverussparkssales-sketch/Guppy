@echo off
TITLE Guppy Web UI
cd /d "%~dp0\.."

REM Start API if not already running
netstat -ano | findstr ":8081 " >nul 2>&1
if errorlevel 1 (
    echo [Guppy] Starting API server...
    start "Guppy API" /min .venv\Scripts\python.exe src\guppy\cli\launch.py api
    echo [Guppy] Waiting for API to be ready...
    timeout /t 4 /nobreak >nul
)

REM Open in Edge app mode (dedicated window, no browser chrome)
start "" "msedge.exe" --app=http://127.0.0.1:8081/index.html --window-size=1280,900
