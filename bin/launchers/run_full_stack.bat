@echo off
REM Full Stack Launcher - Ollama + API + Web UI
REM Opens all components and browser automatically

setlocal enabledelayedexpansion

echo.
echo ========================================
echo   GUPPY FULL STACK LAUNCHER
echo ========================================
echo.

REM Check if Ollama is running
echo Checking Ollama service...
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo ✓ Ollama is running
) else (
    echo ✗ Ollama not running, starting...
    start "Ollama Service" /MIN cmd /c "ollama serve"
    echo ⏳ Waiting for Ollama to start (30 seconds)...
    timeout /t 30 /nobreak
)

REM Verify Ollama is accessible
echo Verifying Ollama accessibility...
curl -s http://127.0.0.1:11434/api/tags >nul
if "%ERRORLEVEL%"=="0" (
    echo ✓ Ollama is accessible at 127.0.0.1:11434
) else (
    echo ✗ Ollama not responding. Check:
    echo   1. Ollama is installed: https://ollama.ai
    echo   2. Ollama service is running
    echo   3. Try: taskkill /IM ollama.exe /F ^& ollama serve
    pause
    exit /b 1
)

REM Start API Server
echo.
echo Starting API server...
set GUPPY_DEV_MODE=1
cd /d "%~dp0..\.."

REM Activate venv
if not exist ".venv\Scripts\activate.bat" (
    echo ✗ Virtual environment not found
    echo Run: powershell -ExecutionPolicy Bypass -File tools/bootstrap_venv.ps1 -Dev
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

REM Start API in background
start "Guppy API" /MIN cmd /k "python -m src.guppy.cli.launch api --dev"
echo ⏳ Waiting for API to start...
timeout /t 5 /nobreak

REM Verify API is accessible
:api_check
curl -s http://localhost:8000/api/health >nul
if "%ERRORLEVEL%"=="0" (
    echo ✓ API is running at http://localhost:8000
) else (
    echo ⏳ API still starting...
    timeout /t 3 /nobreak
    goto api_check
)

REM Start Web UI
echo.
echo Starting Web UI...
cd web
if not exist "node_modules" (
    echo Installing dependencies...
    call npm install
)

start "Guppy Web UI" /MIN cmd /k "npm run dev"
echo ⏳ Waiting for Web UI to start...
timeout /t 10 /nobreak

echo.
echo ========================================
echo   ✓ GUPPY IS RUNNING
echo ========================================
echo.
echo Services:
echo   API:     http://localhost:8000
echo   Web UI:  http://localhost:3000
echo.
echo Opening browser...
timeout /t 2 /nobreak

REM Open browser
start "" http://localhost:3000

echo.
echo Press Ctrl+C in any terminal window to stop services
echo For troubleshooting, see: bin\launchers\README.md
echo.
pause
