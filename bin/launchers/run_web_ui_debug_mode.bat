@echo off
REM Web UI Debug Mode
REM Runs Web UI without API - shows mock responses if unavailable
REM Good for UI testing and debugging

setlocal enabledelayedexpansion

echo.
echo ========================================
echo   GUPPY WEB UI DEBUG MODE
echo ========================================
echo.
echo Running Web UI without API dependency
echo Mock responses will be shown if API unavailable
echo.

REM Navigate to repo root
cd /d "%~dp0..\.."

REM Start Web UI
echo.
echo Starting Web UI in debug mode...
cd web

if not exist "node_modules" (
    echo Installing dependencies...
    call npm install
)

REM Set debug flag
set REACT_APP_DEBUG_MODE=true
set VITE_DEBUG_MODE=true

echo.
echo ========================================
echo   ✓ WEB UI DEBUG MODE STARTING
echo ========================================
echo.
echo Features:
echo   - Mock AI responses if API unavailable
echo   - Full chat UI for testing
echo   - Settings UI for testing
echo.
echo Web UI will open at: http://localhost:3000
echo.
echo To test with real API:
echo   1. Open another terminal
echo   2. Run: run_api_only.bat
echo   3. Refresh browser
echo.
timeout /t 2 /nobreak

call npm run dev
