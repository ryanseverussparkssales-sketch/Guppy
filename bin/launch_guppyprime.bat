@echo off
TITLE GuppyPrime
cd /d "%~dp0\.."
.venv\Scripts\python.exe src\guppy\cli\launch.py guppyprime
pause
