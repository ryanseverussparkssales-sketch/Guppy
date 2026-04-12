@echo off
title Guppy - Mobile Optimized Terminal
mode con: cols=80 lines=25

REM Set console to use larger font (requires manual adjustment)
echo.
echo ========================================
echo    GUPPY MOBILE TERMINAL
echo ========================================
echo.
echo To make this more readable on mobile:
echo.
echo 1. Right-click the title bar
echo 2. Select 'Properties'
echo 3. Go to 'Font' tab
echo 4. Choose size 24 or larger
echo 5. Click OK
echo.
echo Then run: interpreter
echo.
cmd /k "cd /d C:\Users\Ryan\AI_Project && venv\Scripts\activate"
