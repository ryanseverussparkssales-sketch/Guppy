@echo off
REM Launcher for Out-of-Compute Scenario
REM Uses smallest model (qwen2.5:7b) for fastest responses

setlocal enabledelayedexpansion

echo.
echo ========================================
echo   GUPPY WITH SMALL MODEL
echo   ^(Fast responses, lower quality^)
echo ========================================
echo.
echo Using: qwen2.5:7b (5GB, ~0.5s response time)
echo.

REM Kill any running Ollama
echo Checking for running Ollama processes...
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo Stopping Ollama...
    taskkill /IM ollama.exe /F >nul 2>&1
    echo ⏳ Waiting for graceful shutdown...
    timeout /t 5 /nobreak
)

REM Start fresh Ollama
echo.
echo Starting Ollama service...
start "Ollama Service" /MIN cmd /c "ollama serve"
echo ⏳ Waiting for Ollama to start (20 seconds)...
timeout /t 20 /nobreak

REM Pull small model if needed
echo.
echo Ensuring small model is available...
ollama pull qwen2.5:7b
if "%ERRORLEVEL%"=="0" (
    echo ✓ Small model is ready
) else (
    echo ✗ Failed to pull model
    pause
    exit /b 1
)

REM Navigate to repo root
cd /d "%~dp0..\.."

REM Activate venv
call .venv\Scripts\activate.bat

REM Start API with small model
echo.
echo Starting API server with small model...
set GUPPY_DEV_MODE=1
set GUPPY_DEFAULT_MODEL=qwen2.5:7b

start "Guppy API" /MIN cmd /k "python -m src.guppy.cli.launch api --dev"
echo ⏳ Waiting for API to start...
timeout /t 5 /nobreak

REM Start Web UI
echo.
echo Starting Web UI...
cd web

if not exist "node_modules" (
    call npm install
)

start "Guppy Web UI" /MIN cmd /k "npm run dev"
echo ⏳ Waiting for Web UI to start...
timeout /t 10 /nobreak

echo.
echo ========================================
echo   ✓ GUPPY IS RUNNING (FAST MODE)
echo ========================================
echo.
echo Using small model for faster responses
echo   Response time: ~0.5-2 seconds
echo   Quality: Good but less detailed
echo.
echo Services:
echo   API:     http://localhost:8000
echo   Web UI:  http://localhost:3000
echo.
timeout /t 2 /nobreak
start "" http://localhost:3000

echo.
echo For better quality (slower), use: run_full_stack.bat
echo For cloud provider (fastest), use: run_with_claude.bat
echo.
pause
