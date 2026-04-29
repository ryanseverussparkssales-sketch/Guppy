@echo off
:: Launch Screenpipe daemon (screen OCR only, audio transcription disabled to avoid ORT 1.19 conflict)
:: Captures both monitors. API on http://localhost:3030
:: Run this before starting Guppy if you want the Screen tab to work.

set SCREENPIPE_EXE=%LOCALAPPDATA%\screenpipe\package\bin\screenpipe.exe

if not exist "%SCREENPIPE_EXE%" (
    echo [ERROR] screenpipe not found at %SCREENPIPE_EXE%
    echo Run the install steps in docs or ask Claude to reinstall.
    pause
    exit /b 1
)

echo Starting Screenpipe on port 3030 (both monitors, audio transcription disabled)...
"%SCREENPIPE_EXE%" record --disable-audio
