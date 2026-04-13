@echo off
TITLE Guppy
echo [Guppy] Initializing...

set GUPPY_RUNTIME_PROFILE=standard
set GUPPY_DEFAULT_SURFACE=guppy

:: Load ANTHROPIC_API_KEY from User environment (set via SetEnvironmentVariable)
for /f "usebackq tokens=*" %%K in (`powershell -NoProfile -Command "[System.Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY','User')"`) do set ANTHROPIC_API_KEY=%%K

if "%ANTHROPIC_API_KEY%"=="" (
    echo [Guppy] WARNING: ANTHROPIC_API_KEY not set. Running in local Ollama mode only.
) else (
    echo [Guppy] API key loaded. Claude mode available.
)

:: Spotify API Credentials
set SPOTIFY_CLIENT_ID=d6729bd17c664ca289974001ea790136
set SPOTIFY_CLIENT_SECRET=4eba85477e3a4174ad73e741353b85d3

:: Load remaining config from .env if present
cd /d "%~dp0\.."
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
        if not "%%A"=="" if not "%%A:~0,1%"=="#" set %%A=%%B
    )
)

:: Model config
if "%OLLAMA_MODEL%"==""         set OLLAMA_MODEL=guppy
if "%GUPPY_WHISPER_MODEL%"==""  set GUPPY_WHISPER_MODEL=large-v3
if "%WEATHER_UNITS%"==""        set WEATHER_UNITS=imperial

:: Launch the unified GUI surface (use venv Python explicitly)
.venv\Scripts\python.exe guppy_launcher.py

pause
