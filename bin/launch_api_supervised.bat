@echo off
REM launch_api_supervised.bat — Non-interactive API launcher for supervisors/services.
REM Intended for NSSM / Task Scheduler / external process managers.

setlocal
cd /d "%~dp0\.."

if "%GUPPY_API_OWNS_DAEMON%"=="" set GUPPY_API_OWNS_DAEMON=0
if "%GUPPY_API_RELOAD%"=="" set GUPPY_API_RELOAD=0
if "%GUPPY_DEV_MODE%"=="" set GUPPY_DEV_MODE=0

set PYTHON=.venv\Scripts\python.exe
if not exist "%PYTHON%" set PYTHON=python

%PYTHON% guppy_api.py
exit /b %errorlevel%
