@echo off
REM System Health Check
REM Tests all dependencies and services

setlocal enabledelayedexpansion

echo.
echo ========================================
echo   GUPPY SETUP HEALTH CHECK
echo ========================================
echo.

REM Test 1: Python
echo [1/8] Checking Python...
python --version >nul 2>&1
if "%ERRORLEVEL%"=="0" (
    for /f "tokens=*" %%i in ('python --version') do set PYTHON_VERSION=%%i
    echo ✓ !PYTHON_VERSION!
) else (
    echo ✗ Python not found
    echo   Install from: https://www.python.org
)

REM Test 2: Node.js
echo [2/8] Checking Node.js...
node --version >nul 2>&1
if "%ERRORLEVEL%"=="0" (
    for /f "tokens=*" %%i in ('node --version') do set NODE_VERSION=%%i
    echo ✓ Node.js !NODE_VERSION!
) else (
    echo ✗ Node.js not found
    echo   Install from: https://nodejs.org
)

REM Test 3: Ollama
echo [3/8] Checking Ollama...
ollama --version >nul 2>&1
if "%ERRORLEVEL%"=="0" (
    for /f "tokens=*" %%i in ('ollama --version') do set OLLAMA_VERSION=%%i
    echo ✓ !OLLAMA_VERSION!
) else (
    echo ✗ Ollama not found
    echo   Install from: https://ollama.ai
)

REM Test 4: Ollama Service
echo [4/8] Checking Ollama service...
curl -s http://127.0.0.1:11434/api/tags >nul 2>&1
if "%ERRORLEVEL%"=="0" (
    echo ✓ Ollama service is running
) else (
    echo ✗ Ollama service not accessible
    echo   Run: ollama serve
)

REM Test 5: Virtual Environment
echo [5/8] Checking Python venv...
if exist ".venv\Scripts\activate.bat" (
    echo ✓ Virtual environment exists
) else (
    echo ✗ Virtual environment not found
    echo   Run: powershell -ExecutionPolicy Bypass -File tools/bootstrap_venv.ps1 -Dev
)

REM Test 6: Node Dependencies
echo [6/8] Checking npm dependencies...
if exist "web\node_modules" (
    echo ✓ npm dependencies installed
) else (
    echo ⚠ npm dependencies not installed
    echo   Run: cd web ^& npm install
)

REM Test 7: Database
echo [7/8] Checking database...
if exist "data\guppy.db" (
    echo ✓ Database file exists
) else (
    echo ⚠ Database file not found
    echo   Will be created on first run
)

REM Test 8: Port Availability
echo [8/8] Checking port availability...

REM Check port 8000
netstat -ano 2>nul | findstr ":8000 " >nul
if "%ERRORLEVEL%"=="0" (
    echo ⚠ Port 8000 is in use (API port)
) else (
    echo ✓ Port 8000 is available
)

REM Check port 3000
netstat -ano 2>nul | findstr ":3000 " >nul
if "%ERRORLEVEL%"=="0" (
    echo ⚠ Port 3000 is in use (Web UI port)
) else (
    echo ✓ Port 3000 is available
)

REM Check port 11434
netstat -ano 2>nul | findstr ":11434 " >nul
if "%ERRORLEVEL%"=="0" (
    echo ✓ Port 11434 in use (Ollama running)
) else (
    echo ⚠ Port 11434 not in use (Ollama not running)
)

echo.
echo ========================================
echo   HEALTH CHECK COMPLETE
echo ========================================
echo.
echo Next steps:
echo   1. Ensure all ✓ items show green
echo   2. Fix any ✗ (red) issues
echo   3. Run launcher: run_full_stack.bat
echo.
echo Common fixes:
echo   - Python not found: Install from https://www.python.org
echo   - Node not found: Install from https://nodejs.org
echo   - Ollama not found: Install from https://ollama.ai
echo   - Ollama not running: Open terminal and run "ollama serve"
echo   - venv not found: Run bootstrap_venv.ps1
echo.
pause
