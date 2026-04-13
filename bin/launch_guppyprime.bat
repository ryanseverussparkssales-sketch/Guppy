@echo off
TITLE GuppyPrime
echo =============================================================
echo   GUPPYPRIME — Unified AI Assistant + 5-Agent Local Fleet
echo =============================================================
echo.

REM ── Environment ──────────────────────────────────────────────────────────────
set GUPPY_RUNTIME_PROFILE=power
set GUPPY_DEFAULT_SURFACE=guppy
set GUPPY_SHOW_ADVANCED_SURFACES=1

REM Load ANTHROPIC_API_KEY from User environment
for /f "usebackq tokens=*" %%K in (`powershell -NoProfile -Command "[System.Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY','User')"`) do set ANTHROPIC_API_KEY=%%K

if "%ANTHROPIC_API_KEY%"=="" (
    echo [GuppyPrime] WARNING: ANTHROPIC_API_KEY not set — running in local-only mode.
    echo              Haiku boost and cloud routing will be disabled.
    set GUPPY_HAIKU_BOOST=0
) else (
    echo [GuppyPrime] API key loaded. Cloud routing + Haiku boost active.
    set GUPPY_HAIKU_BOOST=1
)

REM Haiku boost default on (overridden above if no key)
if "%GUPPY_HAIKU_BOOST%"=="" set GUPPY_HAIKU_BOOST=1

REM Semantic classifier default on
if "%GUPPY_SEMANTIC_CLASSIFIER%"=="" set GUPPY_SEMANTIC_CLASSIFIER=1

REM Router mode — auto uses cloud-first with local fallback; set to "local" for offline
if "%GUPPY_ROUTER_MODE%"=="" set GUPPY_ROUTER_MODE=auto

REM Spotify API credentials (must come from user/system env or .env)
if "%SPOTIFY_CLIENT_ID%"=="" (
    for /f "usebackq tokens=*" %%K in (`powershell -NoProfile -Command "[System.Environment]::GetEnvironmentVariable('SPOTIFY_CLIENT_ID','User')"`) do set SPOTIFY_CLIENT_ID=%%K
)
if "%SPOTIFY_CLIENT_SECRET%"=="" (
    for /f "usebackq tokens=*" %%K in (`powershell -NoProfile -Command "[System.Environment]::GetEnvironmentVariable('SPOTIFY_CLIENT_SECRET','User')"`) do set SPOTIFY_CLIENT_SECRET=%%K
)

REM Local model assignments
set OLLAMA_MODEL=guppy
set OLLAMA_FAST_MODEL=guppy-fast
set OLLAMA_TEACH_MODEL=merlin
set OLLAMA_CODE_MODEL=merlin-code
set OLLAMA_VAULT_MODEL=vault-scraper

REM Tool budget
if "%GUPPY_TOOL_BUDGET%"=="" set GUPPY_TOOL_BUDGET=6

REM Whisper
if "%GUPPY_WHISPER_MODEL%"=="" set GUPPY_WHISPER_MODEL=large-v3

REM Load remaining config from .env if present
cd /d "%~dp0\.."
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
        if not "%%A"=="" if not "%%A:~0,1%"=="#" (
            if not defined %%A set %%A=%%B
        )
    )
)

if "%SPOTIFY_CLIENT_ID%"=="" (
    echo [GuppyPrime] INFO: SPOTIFY_CLIENT_ID not set. Spotify controls may be unavailable.
)
if "%SPOTIFY_CLIENT_SECRET%"=="" (
    echo [GuppyPrime] INFO: SPOTIFY_CLIENT_SECRET not set. Spotify controls may be unavailable.
)

REM ── Step 1: Start hub silently in system tray ─────────────────────────────────
echo [GuppyPrime] Starting hub in system tray...

set "PYW="
if exist ".venv\Scripts\pythonw.exe" set "PYW=.venv\Scripts\pythonw.exe"
if "%PYW%"=="" where pythonw >nul 2>&1 && set "PYW=pythonw"
if "%PYW%"=="" set "PYW=.venv\Scripts\python.exe"

start "" /B "%PYW%" guppy_hub.py
timeout /T 2 /NOBREAK >nul

REM ── Step 2: Verify Ollama is reachable ───────────────────────────────────────
echo [GuppyPrime] Checking Ollama...
curl -s http://127.0.0.1:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo [GuppyPrime] WARNING: Ollama not reachable at port 11434.
    echo              Local agents will be unavailable until Ollama is started.
    echo              Run: %%LOCALAPPDATA%%\Ollama\start_ollama.bat
    echo.
)

REM ── Step 3: Open unified launcher ────────────────────────────────────────────
echo [GuppyPrime] Launching unified interface...
echo.
echo   Agents available:
echo     guppy-fast    — fast butler  (qwen2.5:7b)
echo     vault-scraper — seed vault   (qwen2.5:7b)
echo     merlin-code   — code expert  (qwen2.5-coder:14b)
echo     guppy         — butler       (qwen2.5:32b)
echo     merlin        — teacher      (qwen2.5:32b)
echo.

.venv\Scripts\python.exe guppy_launcher.py

pause
