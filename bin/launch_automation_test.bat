@echo off
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT=%%~fI"
title Guppy Automation Test
cd /d "%ROOT%"

if not exist "src\guppy\cli\launch.py" (
	echo [ERROR] Could not find src\guppy\cli\launch.py
	echo [ERROR] Expected repo root: "%ROOT%"
	pause
	exit /b 1
)

if exist ".venv\Scripts\pythonw.exe" (
	echo [INFO] Launching automation test with .venv\Scripts\pythonw.exe
	start "" ".venv\Scripts\pythonw.exe" src\guppy\cli\launch.py launcher --start automation-test
	exit /b 0
)

if exist ".venv\Scripts\python.exe" (
	echo [INFO] .venv\Scripts\pythonw.exe not found. Falling back to .venv\Scripts\python.exe
	start "" ".venv\Scripts\python.exe" src\guppy\cli\launch.py launcher --start automation-test
	exit /b 0
)

where pythonw >nul 2>&1 && (
	echo [INFO] .venv python not found. Falling back to system pythonw
	start "" pythonw src\guppy\cli\launch.py launcher --start automation-test
	exit /b 0
)

where python >nul 2>&1 && (
	echo [INFO] .venv and pythonw not found. Running with system python
	python src\guppy\cli\launch.py launcher --start automation-test
	if errorlevel 1 (
		echo [ERROR] Automation launcher failed under system python.
		pause
		exit /b 1
	)
	exit /b 0
)

echo [ERROR] No usable Python interpreter found.
echo [ERROR] Install dependencies with: .venv\Scripts\python.exe -m pip install -r requirements.txt
pause
exit /b 1
