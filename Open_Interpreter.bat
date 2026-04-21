@echo off 
title Open Interpreter - Butler Mode 
cd /d "C:\Users\Ryan\AI_Project" 
 
echo ================================ 
echo    Open Interpreter Butler        
echo ================================ 
echo. 
REM Set environment to avoid proxy issues 
set HTTP_PROXY= 
set HTTPS_PROXY= 
set http_proxy= 
set https_proxy= 
 
echo Starting Open Interpreter... 
echo. 
venv\Scripts\interpreter.exe 
 
echo. 
echo Open Interpreter has exited. 
pause 
