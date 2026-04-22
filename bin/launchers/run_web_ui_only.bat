@echo off
REM Web UI Only Launcher
REM Use this if API is already running in another terminal

setlocal enabledelayedexpansion

echo.
echo ========================================
echo   GUPPY WEB UI ONLY
echo ========================================
echo.
echo This assumes API is already running at http://localhost:8000
echo.

REM Check if API is running
echo Checking if API is accessible...
curl -s http://localhost:8000/api/health >nul
if "%ERRORLEVEL%"=="0" (
    echo ✓ API is running
) else (
    echo ✗ API is not responding at http://localhost:8000
    echo Please start the API first with: run_api_only.bat
    pause
    exit /b 1
)

REM Navigate to repo root
cd /d "%~dp0..\.."

REM Start Web UI
echo.
echo Starting Web UI...
cd web

if not exist "node_modules" (
    echo Installing dependencies...
    call npm install
)

echo.
echo ========================================
echo   ✓ WEB UI STARTING
echo ========================================
echo.
echo Web UI will open at: http://localhost:3000
echo.
timeout /t 2 /nobreak

call npm run dev
