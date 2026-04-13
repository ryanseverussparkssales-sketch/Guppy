@echo off
REM launch_api.bat — Start the Guppy API server
REM ============================================
REM
REM Requirements:
REM - Python 3.12+
REM - All dependencies from requirements.txt
REM - GUPPY_JWT_SECRET environment variable (set in production)
REM - TURNSTILE_SECRET environment variable (from Cloudflare)
REM
REM For development, the server will run with default secrets and
REM allow all Turnstile tokens.

echo Starting Guppy API Server...
echo.

REM Supervisor-friendly defaults: API should not own daemon lifecycle.
if "%GUPPY_API_OWNS_DAEMON%"=="" set GUPPY_API_OWNS_DAEMON=0
if "%GUPPY_API_RELOAD%"=="" set GUPPY_API_RELOAD=0

REM ── Load .env if present ────────────────────────────────────────────────────
if exist "%~dp0..\\.env" (
    echo Loading .env...
    for /f "usebackq tokens=1,* delims==" %%A in ("%~dp0..\\.env") do (
        if not "%%A"=="" if not "%%A:~0,1%"=="#" set "%%A=%%B"
    )
)

REM ── Python available? ───────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM ── Required modules installed? ─────────────────────────────────────────────
python -c "import fastapi, uvicorn, jose, httpx" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Required modules not installed. Run:
    echo pip install fastapi uvicorn[standard] python-jose[cryptography] httpx
    pause
    exit /b 1
)

REM ── Port 8081 available? ─────────────────────────────────────────────────────
netstat -ano | findstr ":8081 " >nul 2>&1
if not errorlevel 1 (
    echo ERROR: Port 8081 is already in use. Stop the existing process first.
    echo Use:  netstat -ano ^| findstr ":8081"  to find the PID.
    pause
    exit /b 1
)

REM ── Warn on missing keys ────────────────────────────────────────────────────
if "%ANTHROPIC_API_KEY%"=="" (
    echo WARNING: ANTHROPIC_API_KEY not set — Claude endpoints will fail
)

if "%GUPPY_JWT_SECRET%"=="" (
    echo WARNING: GUPPY_JWT_SECRET not set, using development default
    set GUPPY_JWT_SECRET=dev-secret-key-change-in-production
)

if "%TURNSTILE_SECRET%"=="" (
    echo WARNING: TURNSTILE_SECRET not set, Turnstile verification disabled
    set TURNSTILE_SECRET=dev-turnstile-secret
)

REM ── Start ────────────────────────────────────────────────────────────────────
echo API Server starting on http://localhost:8081 (supervised mode)
echo Press Ctrl+C to stop
echo.

cd /d "%~dp0.."
python guppy_api.py

pause
