@echo off
echo ========================================
echo Starting Guppy Hold-to-Talk
echo ========================================
echo.
echo Hold Ctrl+Shift+Space to record
echo Release to transcribe and log
echo.
echo Commands logged to: voice_commands.txt
echo.
start "Guppy Hold-to-Talk" python voice_integration.py
echo.
echo Hold-to-talk started in new window
echo.
pause
