@echo off
TITLE Guppy Suite
cd /d "%~dp0\.."
.venv\Scripts\python.exe src\guppy\cli\launch.py launcher
pause
