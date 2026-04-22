@echo off
REM Claude API Launcher
REM Uses Anthropic Claude instead of local Ollama
REM REQUIRES: Valid sk-ant-* API key in Guppy Settings

setlocal enabledelayedexpansion

echo.
echo ========================================
echo   GUPPY WITH CLAUDE API
echo   ^(No local compute needed^)
echo ========================================
echo.
echo REQUIREMENTS:
echo   1. Valid Anthropic API key (sk-ant-v0-...)
echo   2. Key saved in Guppy Settings ^> Providers ^> Anthropic
echo   3. Anthropic selected as active provider
echo.
echo COST: ~$0.003 per 1K input, $0.015 per 1K output tokens
echo.

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

REM Start API (Ollama not needed)
echo.
echo Starting API server with Claude provider...
set GUPPY_DEV_MODE=1
set GUPPY_LLM_PROVIDER=anthropic

start "Guppy API" /MIN cmd /k "python -m src.guppy.cli.launch api --dev"
echo ⏳ Waiting for API to start (10 seconds)...
timeout /t 10 /nobreak

REM Verify API is accessible
curl -s http://localhost:8000/api/health >nul
if "%ERRORLEVEL%"=="0" (
    echo ✓ API is running
) else (
    echo ✗ API failed to start
    pause
    exit /b 1
)

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
echo   ✓ GUPPY IS RUNNING WITH CLAUDE
echo ========================================
echo.
echo Using: Anthropic Claude API
echo   Response time: 2-5 seconds
echo   Quality: Excellent
echo   Cost: ~$5-50/month depending on usage
echo.
echo Services:
echo   API:     http://localhost:8000 (Claude enabled)
echo   Web UI:  http://localhost:3000
echo.
echo IMPORTANT:
echo   - Verify you have a valid API key in Settings
echo   - Check your Anthropic billing at console.anthropic.com
echo   - Set billing alerts to avoid surprises
echo.
timeout /t 2 /nobreak
start "" http://localhost:3000

echo.
echo For local inference, use: run_full_stack.bat
echo For fastest local response, use: run_with_small_model.bat
echo.
pause
