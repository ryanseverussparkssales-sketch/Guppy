@echo off
REM launch_idle_worker.bat — supervised idle-task worker launcher for Task Scheduler.

setlocal
cd /d "%~dp0\.."

if not exist "runtime" mkdir "runtime"

set PYTHON=.venv\Scripts\python.exe
if not exist "%PYTHON%" set PYTHON=python

set LOG=runtime\idle_worker_supervisor.log
echo [%date% %time%] starting idle worker >> "%LOG%"
"%PYTHON%" tools\idle_agent_worker.py --poll-seconds 60 --idle-seconds 180 --stale-running-seconds 900 >> "%LOG%" 2>&1
set EXITCODE=%errorlevel%
echo [%date% %time%] idle worker exited code %EXITCODE% >> "%LOG%"
exit /b %EXITCODE%
