@echo off
REM API Only Launcher
REM Use this for testing API without Web UI

setlocal enabledelayedexpansion

echo.
echo ========================================
echo   GUPPY API ONLY
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

REM Navigate to repo root
cd /d "%~dp0..\.."

REM Activate venv
if not exist ".venv\Scripts\activate.bat" (
    echo ✗ Virtual environment not found
    echo Run: powershell -ExecutionPolicy Bypass -File tools/bootstrap_venv.ps1 -Dev
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

echo.
echo Starting API Server on port 8000...
set GUPPY_DEV_MODE=1

echo.
echo ========================================
echo   ✓ API STARTING
echo ========================================
echo.
echo API will be available at: http://localhost:8000
echo.
echo Test API with:
echo   curl http://localhost:8000/api/health
echo   curl http://localhost:8000/api/chat ^
echo     -H "Content-Type: application/json" ^
echo     -d "{\"message\":\"Hello\",\"session_id\":\"test\"}"
echo.

python -m src.guppy.cli.launch api --dev
