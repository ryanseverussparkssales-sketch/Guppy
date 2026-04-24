@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT=%%~fI"
set "PACKAGED_ONEDIR=%ROOT%\dist\Guppy\Guppy.exe"
set "PACKAGED_ONEFILE=%ROOT%\dist\Guppy.exe"

:: Repo-local launcher helper.
:: Keep this file in bin\ so the relative repo path stays valid.
:: Use tools\ensure_desktop_launcher.ps1 to create Desktop or Start-facing launchers.

cd /d "%ROOT%"

if exist "%PACKAGED_ONEDIR%" (
    start "" /D "%ROOT%\dist\Guppy" "%PACKAGED_ONEDIR%"
    exit /b 0
)

if exist "%PACKAGED_ONEFILE%" (
    start "" /D "%ROOT%\dist" "%PACKAGED_ONEFILE%"
    exit /b 0
)

if exist ".venv\Scripts\pythonw.exe" (
    start "" /D "%ROOT%" ".venv\Scripts\pythonw.exe" src\guppy\cli\launch.py launcher
    exit /b 0
)

where pythonw >nul 2>&1 && (
    start "" /D "%ROOT%" pythonw src\guppy\cli\launch.py launcher
    exit /b 0
)

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" src\guppy\cli\launch.py launcher
) else (
    python src\guppy\cli\launch.py launcher
)
pause
