@echo off
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT=%%~fI"
title Guppy
cd /d "%ROOT%"

if exist ".venv\Scripts\pythonw.exe" (
	start "" ".venv\Scripts\pythonw.exe" src\guppy\cli\launch.py guppy
	exit /b 0
)
where pythonw >nul 2>&1 && (
	start "" pythonw src\guppy\cli\launch.py guppy
	exit /b 0
)

.venv\Scripts\python.exe src\guppy\cli\launch.py guppy
if errorlevel 1 pause
