@echo off
TITLE Guppy Automation Test
cd /d "%~dp0\.."
.venv\Scripts\python.exe src\guppy\cli\launch.py launcher --start automation-test
pause
