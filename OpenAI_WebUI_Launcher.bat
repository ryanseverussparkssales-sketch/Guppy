@echo off
title OpenAI WebUI Launcher
cd /d "C:\Users\Ryan\Guppy"

echo ========================================
echo Starting OpenAI WebUI (Docker)
echo ========================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Ryan\Guppy\launch_openai_webui.ps1"
set EXIT_CODE=%ERRORLEVEL%

if not %EXIT_CODE%==0 (
  echo.
  echo Launcher exited with code %EXIT_CODE%.
  pause
)
