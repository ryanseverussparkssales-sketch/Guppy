@echo off
echo ========================================
echo Starting Guppy Voice Listener
echo ========================================
echo.
echo This will run in a separate window
echo Commands will be logged to: guppy_voice_commands.txt
echo.
start "Guppy Voice Listener" python voice_listener.py
echo.
echo Voice listener started in new window
echo.
pause
