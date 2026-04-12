@echo off
TITLE The Council — Guppy & Merlin
echo [Council] Initializing...

:: Load ANTHROPIC_API_KEY from User environment
for /f "usebackq tokens=*" %%K in (`powershell -NoProfile -Command "[System.Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY','User')"`) do set ANTHROPIC_API_KEY=%%K

if "%ANTHROPIC_API_KEY%"=="" (
    echo [Council] WARNING: ANTHROPIC_API_KEY not set. Guppy will run in Gemma 4 local mode.
) else (
    echo [Council] API key loaded. Guppy running Claude online. Merlin running Gemma 4 local.
)

:: Spotify API Credentials
set SPOTIFY_CLIENT_ID=d6729bd17c664ca289974001ea790136
set SPOTIFY_CLIENT_SECRET=4eba85477e3a4174ad73e741353b85d3

:: Launch the Council (use venv Python explicitly)
cd /d "%~dp0\.."
.venv\Scripts\python.exe council_ui.py

pause
