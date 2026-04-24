@echo off
title OpenAI WebUI Launcher
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo ========================================
echo Starting OpenAI WebUI (Docker)
echo ========================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%launch_openai_webui.ps1"
set EXIT_CODE=%ERRORLEVEL%

if not %EXIT_CODE%==0 (
  echo.
  echo Launcher exited with code %EXIT_CODE%.
  pause
)
