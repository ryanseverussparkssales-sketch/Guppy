@echo off
REM launch_webui.bat — Start the API (if needed) then open the web UI in a
REM dedicated app-mode browser window (no tabs, no address bar).
TITLE Guppy Web UI
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT=%%~fI"
cd /d "%ROOT%"

set "PORT=8081"
set "URL=http://127.0.0.1:%PORT%"

REM ── 1. Start the API server if port is not yet occupied ──────────────────
netstat -ano | findstr ":%PORT% " >nul 2>&1
if errorlevel 1 (
    echo Starting Guppy API on port %PORT%...
    start "Guppy API" /min ".venv\Scripts\pythonw.exe" src\guppy\cli\launch.py api
    REM Wait up to 8 s for the port to open
    set /a TRIES=0
    :wait_loop
    timeout /t 1 /nobreak >nul
    netstat -ano | findstr ":%PORT% " >nul 2>&1
    if not errorlevel 1 goto api_ready
    set /a TRIES+=1
    if %TRIES% lss 8 goto wait_loop
    echo WARNING: API may not be ready yet — opening browser anyway.
)
:api_ready

REM ── 2. Open in a dedicated app window ────────────────────────────────────
REM Try Microsoft Edge --app mode first (ships with Windows 11)
set "EDGE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE%" set "EDGE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"

set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"

if exist "%EDGE%" (
    start "" "%EDGE%" --app="%URL%" --window-size=1280,820 --window-position=80,60
    goto done
)
if exist "%CHROME%" (
    start "" "%CHROME%" --app="%URL%" --window-size=1280,820 --window-position=80,60
    goto done
)

REM Fallback: open in default browser
echo Note: Edge/Chrome not found — opening in default browser.
start "" "%URL%"

:done
exit /b 0
