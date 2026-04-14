@echo off
TITLE Guppy
cd /d "%~dp0\.."
.venv\Scripts\python.exe src\guppy\cli\launch.py guppy
pause
